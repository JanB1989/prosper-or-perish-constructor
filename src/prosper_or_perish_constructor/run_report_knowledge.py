"""The data of the run report's knowledge and work page (`knowledge.html`): technology, literacy, schools, classes and jobs.

One save at a time (`save_knowledge`, cached per save as parquet): two tables, `cells` (sums per owner and world region of
the locations: people and literacy per pop type, each class's people, idle people, jobs, filled jobs and jobs in closed
buildings, the RGOs' places, school levels) and `countries` (per land owner: research points held, of the tree and per
age). Every figure of a scope (world, world region, country) is a sum over its cells, so the page needs no second pass
over the saves (`build_knowledge_data`: `knowledge/index.js`, `knowledge/summary.js` for the world and the regions,
`knowledge/c<n>.js` per country).

- Technology: a country's research points are the research cost of every advance it holds, summed (the cost while the
  advance's age is current, `advance_research_cost.costs`). The tree is every advance any country can research: the
  general advances of all ages (`start_technology.gate_classes`: free, or gated by an institution or by an institution
  or geography). Advances locked by a `potential`, a government, a country type or another `allow` condition (country,
  culture, religion and government advances) are not in it; a country holding some counts them in its points, not in
  its share of the tree. World and regions: the people-weighted mean over the owned land (each location counts its
  owner's figures).
- Literacy: the pops of the save (`population`), weighted by their size; unowned land counts.
- Jobs: a building's jobs are its level x its type's employment size, for the pop type it employs (the built mod over
  vanilla and its DLC folders, script values resolved as `building_footprint` and `job_room` do); filled = its workers
  (at most its jobs); a closed building's jobs stay unfilled. The RGOs' places (`max_raw_material_workers`, filled
  `rgo_employed`) count as laborer jobs. At work = the class's people - its idle people (`unemployed_<class>`).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import polars as pl

from prosper_or_perish_constructor.run_report_charts import POP_SERIES, land_region_expr, region_palette, titleize
from prosper_or_perish_constructor.run_report_data import write_data

if TYPE_CHECKING:
    from prosper_or_perish_constructor.run_report import RunData

CACHE_VERSION = "knowledge-1"
TABLES = ("cells", "countries")
POP_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers", "peasants", "slaves", "tribesmen")
CLASSES = ("burghers", "laborers", "soldiers", "clergy", "nobles", "peasants")
SCHOOLS: tuple[tuple[str, str, str], ...] = (
    ("pp_village_school", "Village School", "#1baf7a"),
    ("pp_trade_school", "Trade School", "#eda100"),
    ("library", "Library", "#2a78d6"),
    ("university", "University", "#4a3aa7"),
    ("pp_academy_of_sciences", "Society of Sciences", "#e34948"),
)
VILLAGE_SCHOOL = "pp_village_school"
LOW_LITERACY = 5.0  # literacy (0..100) at or below which a pop counts as barely literate
TOP_COUNTRIES = 30  # countries of each save in the page's list (by people)
LEADERS = 25  # rows of the leading countries table per save
QUANTILES = ((0.1, "q10"), (0.25, "q25"), (0.5, "q50"), (0.75, "q75"), (0.9, "q90"))
WORLD = "world"
OTHER_REGION = "other"
POP_COLOURS = {key: colour for key, _, colour in POP_SERIES}


# --------------------------------------------------------------------------------------------------------
# game data: the tree and the jobs


@dataclass
class KnowledgeData:
    costs: dict[str, float]  # advance -> research cost while its age is current
    ages: dict[str, int]  # advance -> age index (0 = the first age)
    tree: frozenset[str]  # the advances any country can research
    age_keys: list[str]  # age key per index
    jobs: pl.DataFrame  # building_type, pop_type, per_level (employment size)
    unresolved: list[str] = field(default_factory=list)  # buildings whose employment size did not resolve

    @property
    def digest(self) -> str:
        digest = hashlib.sha1()
        digest.update(json.dumps([self.costs, self.ages, sorted(self.tree)], sort_keys=True).encode())
        digest.update(self.jobs.sort("building_type").write_csv().encode())
        return digest.hexdigest()[:12]

    def tree_totals(self) -> dict[str, Any]:
        """n and points of the whole tree and per age."""
        ages = [{"n": 0, "points": 0.0} for _ in self.age_keys]
        for key in self.tree:
            age = ages[self.ages.get(key, 0)]
            age["n"] += 1
            age["points"] += self.costs.get(key, 0.0)
        return {"n": len(self.tree), "points": sum(self.costs.get(k, 0.0) for k in self.tree), "ages": ages}


def job_sizes(vanilla_root: Path, mod_root: Path) -> tuple[pl.DataFrame, list[str]]:
    """building_type, pop_type, per_level for every building of vanilla, its DLC folders and the mod: the last mod
    definition (REPLACE / CREATE) or the mod's INJECT over vanilla, top-level lines only, script values resolved."""
    from prosper_or_perish_constructor import building_footprint as bf
    from prosper_or_perish_constructor import job_room as jr

    owners = bf.owner_blocks(mod_root, vanilla_root)
    vanilla = bf.vanilla_definitions(vanilla_root)
    values = bf.script_values(vanilla_root, mod_root)
    rows, unresolved = [], []
    for key in sorted(set(vanilla) | set(owners)):
        block = owners.get(key)
        if block is not None:
            text = bf._read(block.path)
            body = text[block.open + 1: block.close]
            inherited = vanilla.get(key, "") if block.mode in bf._INJECT_MODES else ""
        else:
            body, inherited = vanilla[key], ""
        tops = bf._depth_zero_text(body) + "\n" + (bf._depth_zero_text(inherited) if inherited else "")
        pop = jr._POP_RE.search(tops)
        size = jr._EMPLOYMENT_RE.search(tops)
        per_level = bf._resolve(size.group("value"), values) if size else None
        if size and per_level is None:
            unresolved.append(key)
        if pop and per_level is not None and per_level > 0:
            rows.append((key, pop.group("pop"), float(per_level)))
    frame = pl.DataFrame(rows, schema={"building_type": pl.String, "pop_type": pl.String, "per_level": pl.Float64}, orient="row")
    return frame, unresolved


def load_knowledge_data(repo: Path, project: Path) -> KnowledgeData:
    import re
    import tomllib

    from prosper_or_perish_constructor import advance_research_cost as arc
    from prosper_or_perish_constructor import start_technology as st
    from prosper_or_perish_constructor.worldbuilder.stage import vanilla_root as find_vanilla

    mod_setting = tomllib.loads(project.read_text(encoding="utf-8")).get("project", {}).get("mod_root") or "mod/pp"
    mod_root = Path(mod_setting) if Path(mod_setting).is_absolute() else repo / mod_setting
    vanilla_root = find_vanilla(repo, project)
    rows = arc.costs(vanilla_root, mod_root)
    advances = st.effective_advances(vanilla_root, mod_root)
    for key, (mode, body) in st.output_blocks(mod_root).items():  # the ladder's REPLACE blocks, as costs() reads them
        if mode in st._REPLACE_MODES and key in advances:
            advances[key].body = body
    classes = st.gate_classes(advances)
    age_keys: dict[int, str] = {}
    for advance in advances.values():
        match = re.match(r"^age_(\d+)_", advance.age or "")
        if match:
            age_keys[int(match.group(1)) - 1] = advance.age
    jobs, unresolved = job_sizes(vanilla_root, mod_root)
    return KnowledgeData(
        costs={r.advance: r.current for r in rows}, ages={r.advance: r.age_index for r in rows},
        tree=frozenset(r.advance for r in rows if classes.get(r.advance) in st.GENERAL_GATES),
        age_keys=[age_keys[i] for i in sorted(age_keys)], jobs=jobs, unresolved=unresolved)


# --------------------------------------------------------------------------------------------------------
# one save


def _sum_columns() -> list[str]:
    cols = ["people", "owned_people", "locations", "owned_locations", "vs_locations", "rgo_places", "rgo_filled"]
    cols += [f"{k}_{p}" for p in POP_TYPES for k in ("size", "lit", "low")]
    cols += [f"{k}_{c}" for c in CLASSES for k in ("pop", "idle", "jobs", "filled", "closed_jobs", "closed")]
    cols += [f"lv_{s}" for s, _, _ in SCHOOLS]
    return cols


def save_knowledge(dataset: Path, playthrough: str, snapshot: str, data: KnowledgeData) -> dict[str, pl.DataFrame] | None:
    """cells (owner_country_id, region and the sums of `_sum_columns`) and countries (country_id, tag, name, people,
    points, tree_points, tree_n, age_<i>; points null when the save has no researched advances); None without locations."""
    from prosper_or_perish_constructor.run_report_goods import _read

    def read(table: str, columns: list[str]) -> pl.DataFrame:
        return _read(dataset, table, playthrough, snapshot, columns)

    numeric = ["total_population", "max_raw_material_workers", "rgo_employed",
               *[f"population_{c}" for c in CLASSES], *[f"unemployed_{c}" for c in CLASSES]]
    locations = read("locations", ["location_id", "owner_country_id", "macro_region", "super_region", *numeric])
    if locations.is_empty():
        return None
    locations = locations.with_columns(
        pl.col(numeric).cast(pl.Float64).fill_null(0.0), pl.col("owner_country_id").cast(pl.Int64),
        pl.when(land_region_expr()).then(pl.col("macro_region")).otherwise(pl.lit(OTHER_REGION)).alias("region"))

    pops = read("population", ["location_id", "pop_type", "size", "literacy"]).with_columns(
        pl.col("size").cast(pl.Float64).fill_null(0.0), pl.col("literacy").cast(pl.Float64).fill_null(0.0))
    literacy = pops.group_by("location_id").agg(
        *[pl.col("size").filter(pl.col("pop_type") == p).sum().alias(f"size_{p}") for p in POP_TYPES],
        *[(pl.col("size") * pl.col("literacy")).filter(pl.col("pop_type") == p).sum().alias(f"lit_{p}") for p in POP_TYPES],
        *[pl.col("size").filter((pl.col("pop_type") == p) & (pl.col("literacy") <= LOW_LITERACY)).sum().alias(f"low_{p}")
          for p in POP_TYPES])

    buildings = read("buildings", ["building_type", "location_id", "level", "employed", "open"])
    standing = (
        buildings.with_columns(pl.col("level").cast(pl.Float64).fill_null(0.0), pl.col("employed").cast(pl.Float64).fill_null(0.0),
                               (pl.col("open") == False).fill_null(False).alias("closed"))  # noqa: E712 - null open: open
        .join(data.jobs, on="building_type", how="left")
        .with_columns((pl.col("level") * pl.col("per_level").fill_null(0.0)).alias("jobs"))
        .with_columns(pl.when(pl.col("closed")).then(0.0).otherwise(pl.min_horizontal("employed", "jobs")).alias("filled"))
    )
    work = standing.group_by("location_id").agg(
        *[pl.col("jobs").filter(pl.col("pop_type") == c).sum().alias(f"jobs_{c}") for c in CLASSES],
        *[pl.col("filled").filter(pl.col("pop_type") == c).sum().alias(f"filled_{c}") for c in CLASSES],
        *[pl.col("jobs").filter((pl.col("pop_type") == c) & pl.col("closed")).sum().alias(f"closed_jobs_{c}") for c in CLASSES],
        *[((pl.col("pop_type") == c) & pl.col("closed")).sum().cast(pl.Float64).alias(f"closed_{c}") for c in CLASSES],
        *[pl.col("level").filter(pl.col("building_type") == s).sum().alias(f"lv_{s}") for s, _, _ in SCHOOLS],
    )
    owned = pl.col("owner_country_id").is_not_null()
    cells = (
        locations.join(literacy, on="location_id", how="left").join(work, on="location_id", how="left")
        .with_columns(pl.exclude("location_id", "owner_country_id", "macro_region", "super_region", "region").fill_null(0.0))
        .with_columns(
            pl.col("total_population").alias("people"),
            pl.when(owned).then(pl.col("total_population")).otherwise(0.0).alias("owned_people"),
            pl.lit(1.0).alias("locations"), owned.cast(pl.Float64).alias("owned_locations"),
            (owned & (pl.col(f"lv_{VILLAGE_SCHOOL}") > 0)).cast(pl.Float64).alias("vs_locations"),
            pl.col("max_raw_material_workers").alias("rgo_places"), pl.col("rgo_employed").alias("rgo_filled"),
            *[pl.col(f"population_{c}").alias(f"pop_{c}") for c in CLASSES],
            *[pl.col(f"unemployed_{c}").alias(f"idle_{c}") for c in CLASSES],
            # the RGOs' places are laborer jobs
            (pl.col("jobs_laborers") + pl.col("max_raw_material_workers")).alias("jobs_laborers"),
            (pl.col("filled_laborers") + pl.min_horizontal("rgo_employed", "max_raw_material_workers")).alias("filled_laborers"),
        )
        .group_by("owner_country_id", "region").agg(pl.col(c).sum() for c in _sum_columns())
    )

    advances = read("country_advances", ["country_id", "advance"])
    price = pl.DataFrame({
        "advance": list(data.costs), "cost": list(data.costs.values()),
        "in_tree": [k in data.tree for k in data.costs], "age": [data.ages.get(k, 0) for k in data.costs],
    }, schema={"advance": pl.String, "cost": pl.Float64, "in_tree": pl.Boolean, "age": pl.Int64})
    tech_columns = ["points", "tree_points", "tree_n", *[f"age_{i}" for i in range(len(data.age_keys))]]
    people = cells.filter(pl.col("owner_country_id").is_not_null()).group_by("owner_country_id").agg(
        pl.col("people").sum()).rename({"owner_country_id": "country_id"})
    if advances.is_empty():
        held = people.select("country_id").with_columns(pl.lit(None, dtype=pl.Float64).alias(c) for c in tech_columns)
    else:
        tree = pl.col("in_tree").fill_null(False)
        held = (
            advances.with_columns(pl.col("country_id").cast(pl.Int64)).join(price, on="advance", how="left")
            .group_by("country_id").agg(
                pl.col("cost").fill_null(0.0).sum().alias("points"),
                pl.col("cost").filter(tree).sum().alias("tree_points"),
                tree.sum().cast(pl.Float64).alias("tree_n"),
                *[pl.col("cost").filter(tree & (pl.col("age") == i)).sum().alias(f"age_{i}") for i in range(len(data.age_keys))])
        )
        held = people.select("country_id").join(held, on="country_id", how="left").with_columns(pl.col(tech_columns).fill_null(0.0))
    meta = read("countries", ["country_id", "country_tag", "country_name"])
    if meta.is_empty():
        meta = pl.DataFrame(schema={"country_id": pl.Int64, "country_tag": pl.String, "country_name": pl.String})
    countries = (
        people.join(held, on="country_id", how="left")
        .join(meta.select(pl.col("country_id").cast(pl.Int64), pl.col("country_tag").alias("tag"), pl.col("country_name").alias("name"))
              .unique("country_id"), on="country_id", how="left")
        .select("country_id", "tag", "name", "people", *[pl.col(c).cast(pl.Float64) for c in tech_columns])
    )
    return {"cells": cells, "countries": countries}


def _cached(folder: Path | None, compute: Callable[[], dict[str, pl.DataFrame] | None]) -> dict[str, pl.DataFrame] | None:
    if folder is not None and (folder / "done").is_file():
        try:
            return {name: pl.read_parquet(folder / f"{name}.parquet") for name in TABLES}
        except (OSError, pl.exceptions.PolarsError):
            pass
    flows = compute()
    if flows is not None and folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
        for name in TABLES:
            flows[name].write_parquet(folder / f"{name}.parquet")
        (folder / "done").write_text("", encoding="utf-8")
    return flows


# --------------------------------------------------------------------------------------------------------
# from cells to a scope's figures


def weighted(cells: pl.DataFrame, countries: pl.DataFrame, ages: int) -> pl.DataFrame:
    """The cells with the owner's technology times the cell's owned people (pw_*), so a sum over any cells is the
    people-weighted sum of the owners' figures."""
    tech = ["points", "tree_points", "tree_n", *[f"age_{i}" for i in range(ages)]]
    joined = cells.join(countries.select(pl.col("country_id").alias("owner_country_id"), *tech), on="owner_country_id", how="left")
    have = pl.col("points").is_not_null()
    return joined.with_columns(
        pl.when(have).then(pl.col("owned_people")).otherwise(0.0).alias("tech_people"),
        *[(pl.col(c).fill_null(0.0) * pl.col("owned_people")).alias(f"pw_{c}") for c in tech],
    ).drop(tech)


def sum_columns(ages: int) -> list[str]:
    return [*_sum_columns(), "tech_people", *[f"pw_{c}" for c in ("points", "tree_points", "tree_n", *[f"age_{i}" for i in range(ages)])]]


def _div(a: float | None, b: float | None) -> float | None:
    return None if a is None or not b else a / b


def scope_figures(sums: dict[str, float], totals: dict[str, Any]) -> dict[str, float | None]:
    """The page's figures of one scope in one save from its summed cells (`sum_columns`)."""
    out: dict[str, float | None] = {}
    tech = sums.get("tech_people") or 0.0
    out["tech_share"] = _div(_div(sums.get("pw_tree_points"), tech), totals["points"])
    out["tech_held"] = _div(sums.get("pw_tree_n"), tech)
    out["tech_held_share"] = _div(out["tech_held"], totals["n"])
    out["tech_points"] = _div(sums.get("pw_points"), tech)
    for i, age in enumerate(totals["ages"]):
        out[f"tech_age_{i}"] = _div(_div(sums.get(f"pw_age_{i}"), tech), age["points"])
    size = sum(sums.get(f"size_{p}", 0.0) for p in POP_TYPES)
    out["lit_all"] = _div(sum(sums.get(f"lit_{p}", 0.0) for p in POP_TYPES), size)
    out["low_all"] = _div(sum(sums.get(f"low_{p}", 0.0) for p in POP_TYPES), size)
    for p in POP_TYPES:
        out[f"lit_{p}"] = _div(sums.get(f"lit_{p}"), sums.get(f"size_{p}"))
        out[f"low_{p}"] = _div(sums.get(f"low_{p}"), sums.get(f"size_{p}"))
        out[f"size_{p}"] = sums.get(f"size_{p}")
    out["people"] = sums.get("people")
    for school, _, _ in SCHOOLS:
        out[f"lv_{school}"] = sums.get(f"lv_{school}")
    out["vs_share"] = _div(sums.get("vs_locations"), sums.get("owned_locations"))
    out["owned_locations"] = sums.get("owned_locations")
    out["rgo_places"], out["rgo_filled"] = sums.get("rgo_places"), sums.get("rgo_filled")
    for c in CLASSES:
        people, idle = sums.get(f"pop_{c}", 0.0), sums.get(f"idle_{c}", 0.0)
        jobs, filled = sums.get(f"jobs_{c}", 0.0), sums.get(f"filled_{c}", 0.0)
        out[f"pop_{c}"], out[f"idle_{c}"], out[f"work_{c}"] = people, idle, max(0.0, people - idle)
        out[f"jobs_{c}"], out[f"filled_{c}"], out[f"unfilled_{c}"] = jobs, filled, max(0.0, jobs - filled)
        out[f"closed_jobs_{c}"], out[f"closed_{c}"] = sums.get(f"closed_jobs_{c}"), sums.get(f"closed_{c}")
        out[f"share_{c}"] = _div(people, sums.get("people"))
    return out


def weighted_quantiles(frame: pl.DataFrame) -> dict[str, float | None]:
    """share, people -> the tree share at which each quantile of the people (sorted by share) is reached, and the max."""
    frame = frame.filter((pl.col("people") > 0) & pl.col("share").is_not_null()).sort("share")
    if frame.is_empty():
        return {key: None for _, key in QUANTILES} | {"qmax": None}
    total = float(frame["people"].sum())
    cum = (frame["people"].cum_sum() / total).to_list()
    shares = frame["share"].to_list()
    out: dict[str, float | None] = {}
    for q, key in QUANTILES:
        out[key] = next(s for s, c in zip(shares, cum) if c >= q - 1e-12)
    out["qmax"] = max(shares)
    return out


# --------------------------------------------------------------------------------------------------------
# page data


def _scope_key(kind: str, value: object = None) -> str:
    return WORLD if kind == WORLD else f"{kind}:{value}"


def build_knowledge_data(run: RunData, dataset: Path, out: Path, data: KnowledgeData, *, cache: Path | None = None,
                         log: Callable[[str], None] = print) -> dict[str, Any] | None:
    from prosper_or_perish_constructor.run_report_goods import _sig

    started = time.perf_counter()
    folder = out / "knowledge"
    folder.mkdir(parents=True, exist_ok=True)
    ages = len(data.age_keys)
    totals = data.tree_totals()
    snapshots = run.snapshots.select("snapshot_id", "year", "date").to_dicts()
    loaded: list[dict[str, pl.DataFrame] | None] = []
    computed = 0
    for snap in snapshots:
        snapshot = snap["snapshot_id"]
        target = cache / f"{snapshot}.{data.digest}.{CACHE_VERSION}" if cache else None
        was_cached = target is not None and (target / "done").is_file()
        loaded.append(_cached(target, lambda s=snapshot: save_knowledge(dataset, run.playthrough_id, s, data)))
        computed += 0 if was_cached else 1
    if not any(f is not None for f in loaded):
        return None

    palette = region_palette(run)
    land = {key for key, _, _ in palette}
    scopes: list[str] = [WORLD, *[_scope_key("r", key) for key, _, _ in palette], _scope_key("r", OTHER_REGION)]
    tops: list[list[int]] = []
    names: dict[int, tuple[str | None, str | None]] = {}
    for flows in loaded:
        if flows is None:
            tops.append([])
            continue
        top = flows["countries"].sort("people", descending=True).head(TOP_COUNTRIES)
        tops.append(top["country_id"].to_list())
        for cid, tag, name in top.select("country_id", "tag", "name").iter_rows():
            names[cid] = (tag, name)
    known = sorted({c for top in tops for c in top})
    scopes += [_scope_key("c", c) for c in known]
    position = {key: i for i, key in enumerate(scopes)}
    count = len(snapshots)
    series: dict[int, dict[str, list[Any]]] = {}
    columns = sum_columns(ages)

    def note(scope: int, n: int, sums: dict[str, float]) -> None:
        figures = scope_figures(sums, totals)
        entry = series.setdefault(scope, {})
        for key, value in figures.items():
            entry.setdefault(key, [None] * count)[n] = _sig(value, 4) if value is not None else None

    saves: list[dict[str, Any]] = []
    for n, (snap, flows) in enumerate(zip(snapshots, loaded)):
        save: dict[str, Any] = {"id": snap["snapshot_id"], "label": str(snap.get("year") or snap.get("date")), "date": snap.get("date"),
                                "top": [position[_scope_key("c", c)] for c in tops[n]], "leaders": []}
        saves.append(save)
        if flows is None:
            continue
        cells = weighted(flows["cells"], flows["countries"], ages).with_columns(
            pl.when(pl.col("region").is_in(sorted(land))).then(pl.col("region")).otherwise(pl.lit(OTHER_REGION)).alias("region"))
        world = cells.select(pl.col(c).sum() for c in columns).row(0, named=True)
        note(0, n, world)
        shares = cells.join(flows["countries"].select(pl.col("country_id").alias("owner_country_id"),
                                                      (pl.col("tree_points") / totals["points"]).alias("share")),
                            on="owner_country_id", how="inner").select("region", "share", pl.col("owned_people").alias("people"))
        quantiles = {0: weighted_quantiles(shares)}
        for (region,), part in cells.partition_by("region", as_dict=True).items():
            key = position[_scope_key("r", region)]
            note(key, n, part.select(pl.col(c).sum() for c in columns).row(0, named=True))
            quantiles[key] = weighted_quantiles(shares.filter(pl.col("region") == region))
        for scope, values in quantiles.items():
            entry = series.setdefault(scope, {})
            for key, value in values.items():
                entry.setdefault(key, [None] * count)[n] = _sig(value, 4)
        owned = cells.filter(pl.col("owner_country_id").is_in(known)).group_by("owner_country_id").agg(pl.col(c).sum() for c in columns)
        for row in owned.iter_rows(named=True):
            note(position[_scope_key("c", row["owner_country_id"])], n, row)
        leaders = flows["countries"].filter(pl.col("points").is_not_null()).sort(["tree_points", "people"], descending=True).head(LEADERS)
        save["leaders"] = [
            [run.labels.country(r["tag"], r["name"]), _sig(r["people"]), _sig(r["points"]), _sig(r["tree_points"] / totals["points"] if totals["points"] else None),
             _sig(r["tree_n"])] for r in leaders.iter_rows(named=True)]

    files: dict[int, str] = {}
    summary: dict[str, Any] = {}
    for scope, entry in series.items():
        if scopes[scope].startswith("c:"):
            name = f"knowledge/c{scope}.js"
            write_data(out, name, entry)
            files[scope] = name
        else:
            summary[str(scope)] = entry
    write_data(out, "knowledge/summary.js", summary)
    regions = {key: (label, colour) for key, label, colour in palette}
    scope_list = []
    for i, key in enumerate(scopes):
        if key == WORLD:
            scope_list.append({"id": key, "name": "World", "kind": "world"})
        elif key.startswith("r:"):
            label, colour = regions.get(key[2:], ("Seas and other", "#9a9a96"))
            scope_list.append({"id": key, "name": label, "kind": "region", "color": colour, "has": i in series})
        else:
            tag, name = names.get(int(key[2:]), (None, None))
            scope_list.append({"id": key, "name": run.labels.country(tag, name), "kind": "country", "tag": tag, "file": files.get(i)})
    log(f"knowledge page: {count} saves ({computed} computed, {count - computed} cached), {len(known)} countries, "
        f"{time.perf_counter() - started:.1f}s")
    return {"saves": saves, "scopes": scope_list, "totals": totals}


def index_payload(run: RunData, built: dict[str, Any], data: KnowledgeData) -> dict[str, Any]:
    labels = run.labels

    def age_name(key: str) -> str:
        text = labels._text(key)
        return text or titleize(key.split("_", 2)[-1])

    return {
        "run": run.name, "years": list(run.years), "saves": built["saves"], "scopes": built["scopes"],
        "tree": built["totals"], "ages": [{"id": k, "name": age_name(k)} for k in data.age_keys],
        "popTypes": [{"id": p, "name": titleize(p), "color": POP_COLOURS.get(p, "#9a9a96")} for p in POP_TYPES],
        "classes": [{"id": c, "name": titleize(c), "color": POP_COLOURS.get(c, "#9a9a96")} for c in CLASSES],
        "schools": [{"id": s, "name": name, "color": colour} for s, name, colour in SCHOOLS],
        "lowLiteracy": LOW_LITERACY, "quantiles": [{"id": key, "q": q} for q, key in QUANTILES],
    }


def write_knowledge_page(run: RunData, out: Path, *, repo: Path, project: Path, dataset: Path, cache: Path | None = None,
                         data: KnowledgeData | None = None, log: Callable[[str], None] = print) -> Path | None:
    """The knowledge and work page; None when the run has no save with locations."""
    data = data or load_knowledge_data(repo, project)
    if data.unresolved:
        log(f"knowledge page: {len(data.unresolved)} buildings without a resolvable employment size count no jobs")
    built = build_knowledge_data(run, dataset, out, data, cache=cache, log=log)
    if built is None:
        log("knowledge page: no save with locations; skipped")
        return None
    write_data(out, "knowledge/index.js", index_payload(run, built, data))
    from prosper_or_perish_constructor.run_report_knowledge_page import knowledge_page_html

    path = out / "knowledge.html"
    path.write_text(knowledge_page_html(run.name, run.years), encoding="utf-8")
    return path
