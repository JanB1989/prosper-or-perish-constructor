"""EU5 market access for every location and market (engine rules reverse-engineered 2026-09-27;
docs/market_rulebook.md section 3).

    access(L, M) = clamp(1 - C(centre(M) -> L) + local_market_access(L), 0, 1)

C = shortest path outward from the market centre over the location graph (Dijkstra, directed edge costs).
Edge cost of a step u -> v, K = 0.0024 per pixel (= MARKET_BASE_DISTANCE_FACTOR 0.006 x 0.4), d = distance between
the bounding-box centres of the two locations in locations.png (horizontal wrap):

* land -> land: K d favg min(road, river); f = 1 + (topography movement_cost - 1)/2 + (vegetation movement_cost - 1)/2,
  favg the mean of both ends; road = 1 + the road type's market_access when negative (gravel 0.9, navigable 0.4,
  improved 0.2; positive values are ignored); river = 0.5 downstream, 0.8 upstream (rivers.png traced), else 1;
* water -> water: K d favg S road, S = 0.2, or 0.4 when either tile is open sea (no passable land neighbour) or
  the step is between a lake and a sea tile;
* land <-> water: (K d 0.15 + P) road, P = 0.02 (1 - harbour) when the land location is owned, has a port and the
  water tile is its port sea zone or a lake, else 0.1 (no port);
* impassable locations are not part of the graph; local_market_access counts at the end location only.

Pure rules (game files + roads, owners and local_market_access of a save) put 65 % of saved accesses within 0.005
and 94 % within 0.05; most of the rest is rivers (a quarter of the traced river edges carry no river factor in the
game, unexplained). ``calibrated=True`` reads the river class of every edge on the save's market_parent tree and the
effective harbour of each port off the save: 99 % within 0.005. The saved market_access lags the live value by the
local_market_access changes since the last tick; ``lma`` picks the live (dumped) or the field value.
"""

from __future__ import annotations

import glob
import re
from collections import Counter
from pathlib import Path

import numpy as np
import polars as pl

K = 0.0024
PARAMS = dict(K=K, sea=0.2, open=0.4, lake=0.2, lake_sea=0.4, trans=0.15, port_pen=0.02, noport_pen=0.1,
              down=0.5, up=0.8)
ROAD_MARKET_ACCESS = {"gravel_road": -0.1, "paved_road": -0.2, "modern_road": -0.3, "railroad": -0.4,
                      "pp_navigation_navigable": -0.6, "pp_navigation_improved": -0.8, "pp_navigation_difficult": 0.5,
                      "pp_navigation_improvable": 1.0, "pp_navigation_barrier": 2.0}
WATER_TOPOGRAPHY = {"coastal_ocean", "inland_sea", "narrows", "ocean", "deep_ocean", "lakes", "high_lakes", "salt_pans",
                    "ocean_wasteland"}
LAKE_TOPOGRAPHY = {"lakes", "high_lakes", "salt_pans"}
WIDTH = 16384
CACHE = Path("artifacts/data/markets")


# ------------------------------------------------------------------------------------------------ map cache
def _colors(map_dir: Path, vanilla_map_dir: Path) -> dict[int, str]:
    colors: dict[int, str] = {}
    for path in sorted(glob.glob(str(vanilla_map_dir / "named_locations" / "*.txt"))) + sorted(
            glob.glob(str(map_dir / "named_locations" / "*.txt"))):
        for line in open(path, encoding="utf-8-sig"):
            line = line.split("#")[0].strip()
            if "=" in line:
                name, color = [x.strip() for x in line.split("=", 1)]
                if color:
                    colors[int(color, 16)] = name
    return colors


def build_map_cache(map_dir: Path, vanilla_map_dir: Path, out: Path) -> dict[str, int]:
    """adjacency (4-neighbour pixel contacts + adjacencies.csv), bounding-box centres and traced river crossings
    of the mod map into ``out`` (parquet). Minutes of numpy on the 16384 x 8192 map; rerun after a map change."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    out.mkdir(parents=True, exist_ok=True)
    colors = _colors(map_dir, vanilla_map_dir)
    img = np.asarray(Image.open(map_dir / "locations.png").convert("RGB")).astype(np.uint32)
    code = (img[:, :, 0] << 16) | (img[:, :, 1] << 8) | img[:, :, 2]
    del img
    # adjacency
    pairs: Counter = Counter()
    for a, b in ((code[:, :-1], code[:, 1:]), (code[:-1, :], code[1:, :]), (code[:, -1:], code[:, :1])):
        m = a != b
        x, y = a[m].astype(np.uint64), b[m].astype(np.uint64)
        key = (np.minimum(x, y) << np.uint64(24)) | np.maximum(x, y)
        u, c = np.unique(key, return_counts=True)
        for k, n in zip(u.tolist(), c.tolist()):
            pairs[k] += n
    rows = [(colors.get(k >> 24), colors.get(k & 0xFFFFFF)) for k in pairs]
    adj = [r for r in rows if None not in r]
    straits = pl.read_csv(map_dir / "adjacencies.csv", separator=";", infer_schema_length=0, truncate_ragged_lines=True)
    adj += [(a, b) for a, b in zip(straits["From"].to_list(), straits["To"].to_list()) if a and b]
    pl.DataFrame(adj, schema=["a", "b"], orient="row").unique().write_parquet(out / "adjacency.parquet")
    # bounding-box centres (wrap-aware)
    flat = code.ravel()
    order = np.argsort(flat, kind="stable")
    fs = flat[order]
    cut = np.flatnonzero(np.diff(fs)) + 1
    boxes = []
    for s, e in zip(np.concatenate(([0], cut)), np.concatenate((cut, [fs.size]))):
        ys, xs = np.divmod(order[s:e], WIDTH)
        xs = xs.astype(float)
        if xs.max() - xs.min() > WIDTH / 2:
            xs = np.where(xs < WIDTH / 2, xs + WIDTH, xs)
        name = colors.get(int(fs[s]))
        if name:
            boxes.append((name, (xs.min() + xs.max()) / 2 % WIDTH, (ys.min() + ys.max()) / 2))
    pl.DataFrame(boxes, schema=["slug", "bx", "by"], orient="row").write_parquet(out / "positions.parquet")
    # rivers: walk from every source pixel (0), then from merge pixels (1) that touch walked river, reversed
    riv = np.asarray(Image.open(map_dir / "rivers.png")).astype(np.int16)
    crossings = _trace_rivers(code, riv)
    pl.DataFrame([(colors.get(a), colors.get(b), n) for (a, b), n in crossings.items()],
                 schema=["a", "b", "n"], orient="row").drop_nulls().write_parquet(out / "rivers.parquet")
    (out / "source.txt").write_text(f"{map_dir}\n", encoding="utf-8")
    return {"adjacency": len(adj), "positions": len(boxes), "river_crossings": len(crossings)}


def _trace_rivers(code: np.ndarray, riv: np.ndarray) -> Counter:
    height, width = riv.shape
    is_river = riv < 254
    wide = np.where((riv >= 3) & (riv < 254), riv, 0)
    steps = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    visited = np.zeros(riv.shape, bool)
    crossings: Counter = Counter()

    def walk(y: int, x: int, reverse: bool) -> None:
        visited[y, x] = True
        while True:
            cand = [(y + dy, (x + dx) % width) for dy, dx in steps
                    if 0 <= y + dy < height and is_river[y + dy, (x + dx) % width]
                    and riv[y + dy, (x + dx) % width] != 0 and not visited[y + dy, (x + dx) % width]]
            if not cand:
                return
            if len(cand) > 1:
                best = max(wide[p] for p in cand)
                cand = [p for p in cand if wide[p] == best] or cand
            ny, nx = cand[0]
            a, b = int(code[y, x]), int(code[ny, nx])
            if a != b:
                crossings[(b, a) if reverse else (a, b)] += 1
            y, x = ny, nx
            visited[y, x] = True

    for y, x in np.argwhere(riv == 0).tolist():
        if not visited[y, x]:
            walk(y, x, False)
    merges = np.argwhere(riv == 1).tolist()
    for _ in range(30):
        progress = 0
        for y, x in merges:
            if visited[y, x]:
                continue
            if any(0 <= y + dy < height and visited[y + dy, (x + dx) % width] and is_river[y + dy, (x + dx) % width]
                   for dy, dx in steps):
                walk(y, x, True)
                progress += 1
        if not progress:
            break
    return crossings


# ------------------------------------------------------------------------------------------------ game files
def _map_list(text: str, name: str) -> set[str]:
    i = text.find("\n" + name + " = {")
    j = text.find("}", i)
    body = "\n".join(line.split("#")[0] for line in text[i:j].split("{", 1)[1].splitlines())
    return set(body.split())


def _movement_costs(vanilla_common: Path, mod_common: Path, kind: str) -> dict[str, float]:
    out: dict[str, float] = {}
    vanilla = sorted(glob.glob(str(vanilla_common / kind / "*.txt")))
    mod = sorted(glob.glob(str(mod_common / kind / "*.txt")))
    names = {Path(f).name for f in mod}
    for path in [f for f in vanilla if Path(f).name not in names] + mod:
        text = "\n".join(line.split("#")[0] for line in open(path, encoding="utf-8-sig").read().splitlines())
        for m in re.finditer(r"^([A-Za-z_:0-9]+)\s*=\s*\{", text, re.M):
            i, depth = m.end(), 1
            while depth and i < len(text):
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            top = re.sub(r"\{[^{}]*\}", "", re.sub(r"\{[^{}]*\}", "", text[m.end():i]))
            key = m.group(1).split(":")[-1]
            found = re.search(r"\bmovement_cost\s*=\s*([-\d.]+)", top)
            out.setdefault(key, 1.0)
            if found:
                out[key] = float(found.group(1))
    return out


def _templates(map_dir: Path, vanilla_common: Path, mod_common: Path) -> pl.DataFrame:
    topo = _movement_costs(vanilla_common, mod_common, "topography")
    veg = _movement_costs(vanilla_common, mod_common, "vegetation")
    rows = []
    for line in open(map_dir / "location_templates.txt", encoding="utf-8-sig"):
        m = re.match(r"\s*(\w+)\s*=\s*\{(.*)\}", line)
        if not m:
            continue
        name, body = m.groups()
        t = re.search(r"topography\s*=\s*(\w+)", body)
        v = re.search(r"vegetation\s*=\s*(\w+)", body)
        h = re.search(r"natural_harbor_suitability\s*=\s*([\d.]+)", body)
        t, v = (t.group(1) if t else None), (v.group(1) if v else None)
        rows.append((name, t, topo.get(t, 1.0), veg.get(v, 1.0), float(h.group(1)) if h else 0.0))
    return pl.DataFrame(rows, schema=["slug", "topography", "t_mc", "v_mc", "harbor"], orient="row")


# ------------------------------------------------------------------------------------------------ graph
class Graph:
    """Nodes (locations with their map and save attributes) and directed edges for one save state."""

    def __init__(self, locations: pl.DataFrame, roads: pl.DataFrame, lma: pl.DataFrame, *, map_dir: Path,
                 vanilla_root: Path, mod_root: Path, cache: Path):
        text = (map_dir / "default.map").read_text(encoding="utf-8-sig")
        sea, lakes, impassable = _map_list(text, "sea_zones"), _map_list(text, "lakes"), _map_list(text, "impassable_mountains")
        ports = pl.read_csv(map_dir / "ports.csv", separator=";", truncate_ragged_lines=True, infer_schema_length=0)
        pos = pl.read_parquet(cache / "positions.parquet")
        tpl = _templates(map_dir, vanilla_root / "game" / "in_game" / "common", mod_root / "in_game" / "common")
        n = (locations.join(tpl, on="slug", how="left", suffix="_t").join(pos, on="slug", how="left")
             .join(lma, on="location_id", how="left")
             .with_columns(pl.col("slug").is_in(list(sea)).alias("is_sea"), pl.col("slug").is_in(list(lakes)).alias("is_lake"),
                           pl.col("slug").is_in(list(impassable)).alias("impassable"),
                           pl.col("slug").is_in(ports["LandProvince"].to_list()).alias("has_port"),
                           pl.col("t_mc").fill_null(1.0), pl.col("v_mc").fill_null(1.0), pl.col("harbor").fill_null(0.0),
                           pl.col("lma_live").fill_null(0.0)))
        n = n.with_columns((pl.col("is_sea") | pl.col("is_lake") | pl.col("topography").is_in(list(WATER_TOPOGRAPHY))).alias("water"),
                           (pl.col("is_lake") | pl.col("topography").is_in(list(LAKE_TOPOGRAPHY))).alias("lake"))
        field_ok = (pl.col("acc_live").is_not_null() & pl.col("market_access").is_not_null() & (pl.col("acc_live") < 0.99999)
                    & (pl.col("market_access") < 0.99999) & (pl.col("market_access") > 0))
        n = n.with_columns(pl.when(field_ok).then(pl.col("lma_live") - (pl.col("acc_live") - pl.col("market_access")))
                           .otherwise(pl.col("lma_live")).alias("lma_field")).sort("location_id")
        ids = dict(zip(n["slug"].to_list(), n["location_id"].to_list()))
        adj = pl.read_parquet(cache / "adjacency.parquet")
        e = pl.DataFrame({"ia": adj["a"].replace_strict(ids, default=None), "ib": adj["b"].replace_strict(ids, default=None)}).drop_nulls()
        e = pl.concat([e, e.select(pl.col("ib").alias("ia"), pl.col("ia").alias("ib"))]).unique()
        rd = pl.concat([roads.select(pl.col("from").alias("ia"), pl.col("to").alias("ib"), "type"),
                        roads.select(pl.col("to").alias("ia"), pl.col("from").alias("ib"), "type")]).unique(["ia", "ib"])
        e = e.join(rd, on=["ia", "ib"], how="left")
        pp = ports.select(pl.col("LandProvince").replace_strict(ids, default=None).alias("a"),
                          pl.col("SeaZone").replace_strict(ids, default=None).alias("b")).drop_nulls()
        pp = pl.concat([pp.select(pl.col("a").alias("ia"), pl.col("b").alias("ib")),
                        pp.select(pl.col("b").alias("ia"), pl.col("a").alias("ib"))]).unique().with_columns(pl.lit(True).alias("portpair"))
        e = e.join(pp, on=["ia", "ib"], how="left").with_columns(pl.col("portpair").fill_null(False))
        rivers = pl.read_parquet(cache / "rivers.parquet")
        count = {(a, b): c for a, b, c in rivers.iter_rows()}
        down = [(ids.get(a), ids.get(b)) for (a, b), c in count.items() if c >= count.get((b, a), 0)]
        rdf = pl.DataFrame([x for x in down if None not in x], schema=["ia", "ib"], orient="row").with_columns(pl.lit(True).alias("riv_down"))
        e = (e.join(rdf, on=["ia", "ib"], how="left")
             .join(rdf.rename({"ia": "ib", "ib": "ia", "riv_down": "riv_up"}), on=["ia", "ib"], how="left")
             .with_columns(pl.col("riv_down").fill_null(False), pl.col("riv_up").fill_null(False)).sort("ia", "ib"))
        self.n, self.e = n, e
        self.size = int(n["location_id"].max()) + 1
        idx = n["location_id"].to_numpy()
        g: dict[str, np.ndarray] = {}
        for c in ["bx", "by", "t_mc", "v_mc", "harbor", "lma_live", "lma_field"]:
            a = np.zeros(self.size)
            a[idx] = n[c].cast(pl.Float64).fill_null(0).to_numpy()
            g[c] = a
        for c in ["water", "lake", "impassable", "has_port"]:
            a = np.zeros(self.size, bool)
            a[idx] = n[c].fill_null(False).to_numpy()
            g[c] = a
        owned = np.zeros(self.size, bool)
        owned[idx] = n["owner"].is_not_null().to_numpy()
        g["owned"] = owned
        ia, ib = e["ia"].to_numpy(), e["ib"].to_numpy()
        coastal = np.zeros(self.size, bool)
        m = g["water"][ia] & ~g["water"][ib] & ~g["impassable"][ib]
        coastal[ia[m]] = True
        g["open"] = g["water"] & ~coastal
        self.g = g

    def edge_costs(self, p=PARAMS, river=None):
        e, g = self.e, self.g
        ia, ib = e["ia"].to_numpy(), e["ib"].to_numpy()
        dx = np.abs(g["bx"][ia] - g["bx"][ib])
        dx = np.minimum(dx, WIDTH - dx)
        d = np.sqrt(dx * dx + (g["by"][ia] - g["by"][ib]) ** 2)
        f = 1 + (g["t_mc"] - 1) / 2 + (g["v_mc"] - 1) / 2
        ft = (f[ia] + f[ib]) / 2
        wa, wb, la, lb = g["water"][ia], g["water"][ib], g["lake"][ia], g["lake"][ib]
        rma = np.array([ROAD_MARKET_ACCESS.get(t, 0.0) if t is not None else 0.0 for t in e["type"].to_list()])
        rf = np.where(rma < 0, 1 + rma, 1.0)
        riv = np.where(e["riv_down"].to_numpy(), p["down"], np.where(e["riv_up"].to_numpy(), p["up"], 1.0))
        if river is not None:
            riv = np.where(np.isnan(river), riv, river)
        sf = np.where(g["open"][ia] | g["open"][ib], p["open"], np.where(la & lb, p["lake"], np.where(la ^ lb, p["lake_sea"], p["sea"])))
        land, water = np.where(wa, ib, ia), np.where(wa, ia, ib)
        port = g["owned"][land] & g["has_port"][land] & (e["portpair"].to_numpy() | g["lake"][water])
        pen = np.where(port, p["port_pen"] * (1 - g["harbor"][land]), p["noport_pen"])
        w = np.where(wa ^ wb, (p["K"] * d * p["trans"] + pen) * rf,
                     np.where(wa & wb, p["K"] * d * ft * sf * rf, p["K"] * d * ft * np.minimum(rf, riv)))
        blocked = g["impassable"][ia] | g["impassable"][ib]
        return ia, ib, w, blocked, d, rf

    def costs(self, centres: np.ndarray, p=PARAMS, river=None) -> np.ndarray:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import dijkstra

        ia, ib, w, blocked, *_ = self.edge_costs(p, river)
        k = ~blocked
        graph = csr_matrix((np.maximum(w[k], 1e-12), (ia[k], ib[k])), shape=(self.size, self.size))
        return dijkstra(graph, directed=True, indices=centres)

    def calibrate(self, markets: pl.DataFrame, p=PARAMS, tol: float = 0.003) -> np.ndarray:
        """River class per edge and harbour per port from the save's market_parent tree and access fields."""
        n, g = self.n, self.g
        cost: dict[tuple[int, int], float] = {}
        for lid, m1, a1, m2, a2, lma in n.select("location_id", "market_id", "market_access", "second_best_market_id",
                                                 "second_best_market_access", "lma_field").iter_rows():
            if m1 is not None and a1 is not None and 0.001 < a1 < 0.99999:
                cost[(lid, m1)] = 1 - a1 + lma
            if m2 is not None and a2 is not None and 0.001 < a2 < 0.99999:
                cost[(lid, m2)] = 1 - a2 + lma
        for m, c in markets.select("market_id", "center_location_id").iter_rows():
            cost[(c, m)] = 0.0
        current = dict(zip(n["location_id"].to_list(), n["market_id"].to_list()))
        ia, ib, w, blocked, d, rf = self.edge_costs(p)
        edge = {(a, b): k for k, (a, b) in enumerate(zip(ia.tolist(), ib.tolist()))}
        rd, ru = self.e["riv_down"].to_numpy(), self.e["riv_up"].to_numpy()
        mirror = {0.5: 0.8, 0.8: 0.5, 1.0: 1.0}
        river: dict[tuple[int, int], float] = {}
        harbour: dict[int, list[float]] = {}
        for c, parent in n.select("location_id", "market_parent").drop_nulls().iter_rows():
            m = current.get(c)
            k = edge.get((parent, c))
            if m is None or k is None or (c, m) not in cost or (parent, m) not in cost:
                continue
            step = cost[(c, m)] - cost[(parent, m)]
            if not g["water"][parent] and not g["water"][c] and step > 0.002:
                used = min(rf[k], p["down"] if rd[k] else (p["up"] if ru[k] else 1.0))
                factor = step / (w[k] / used)
                cls = 0.5 if factor < 0.65 else (0.8 if factor < 0.85 else 1.0)
                river[(parent, c)], river[(c, parent)] = cls, mirror[cls]
            elif g["water"][parent] != g["water"][c]:
                land = c if g["water"][parent] else parent
                if g["owned"][land] and g["has_port"][land]:
                    pen = step / rf[k] - p["K"] * d[k] * p["trans"]
                    if -0.01 < pen < 0.035:
                        harbour.setdefault(land, []).append(min(1.0, max(0.0, 1 - pen / p["port_pen"])))
        h = g["harbor"].copy()
        for loc, values in harbour.items():
            h[loc] = float(np.median(values))
        self.g = {**g, "harbor": h}
        override = np.array([river.get((a, b), np.nan) for a, b in zip(ia.tolist(), ib.tolist())])
        # shortest-path consistency: raise rule-based river factors that would make a path too cheap
        ia, ib, w, blocked, d, rf = self.edge_costs(p, override)
        by_location: dict[int, list[tuple[int, float]]] = {}
        for (lid, m), c in cost.items():
            by_location.setdefault(lid, []).append((m, c))
        for k in range(len(ia)):
            a, b = ia[k], ib[k]
            if self.g["water"][a] or self.g["water"][b] or not (rd[k] or ru[k]) or not np.isnan(override[k]):
                continue
            now = p["down"] if rd[k] else p["up"]
            base = w[k] / min(now, rf[k])
            need = max([(cb - cost[(a, m)] - tol) / base for m, cb in by_location.get(b, []) if (a, m) in cost] or [0.0])
            if need > now:
                cls = next((x for x in (p["down"], p["up"], 1.0) if x >= need), 1.0)
                river[(a, b)], river[(b, a)] = cls, mirror[cls]
        return np.array([river.get((a, b), np.nan) for a, b in zip(ia.tolist(), ib.tolist())])


def access_matrix(locations: pl.DataFrame, markets: pl.DataFrame, roads: pl.DataFrame, lma: pl.DataFrame, *,
                  map_dir: Path, vanilla_root: Path, mod_root: Path, cache: Path, calibrated: bool = True,
                  field: bool = False, min_access: float = 0.0) -> pl.DataFrame:
    """(location_id, market_id, access) for every pair with access > ``min_access``.

    ``locations``: eu5save locations (location_id, slug, owner, market_id, market_access, second_best_market_id,
    second_best_market_access, market_parent); ``markets``: market_id, center_location_id; ``roads``: from, to, type;
    ``lma``: location_id, lma_live (dumped local_market_access), acc_live (dumped market_access).
    ``field`` = use the local_market_access in effect at the last tick (matches the saved access fields)."""
    graph = Graph(locations, roads, lma, map_dir=map_dir, vanilla_root=vanilla_root, mod_root=mod_root, cache=cache)
    river = graph.calibrate(markets) if calibrated else None
    centres = markets["center_location_id"].to_numpy()
    cost = graph.costs(centres, PARAMS, river)
    lid = graph.n["location_id"].to_numpy()
    local = graph.g["lma_field" if field else "lma_live"][lid]
    access = np.clip(1 - cost[:, lid] + local[None, :], 0, 1)
    access = np.where(np.isfinite(access), access, -np.inf)
    mi, li = np.nonzero(access > min_access)
    return pl.DataFrame({"location_id": lid[li], "market_id": markets["market_id"].to_numpy()[mi], "access": access[mi, li]})
