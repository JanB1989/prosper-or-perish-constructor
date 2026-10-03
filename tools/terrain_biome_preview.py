"""Approximate EU5 1.4 ground rendering from biomes.txt + materials.txt, for review outside the game.

Each location takes the biome its climate, vegetation and topography match (worldbuilder/biomes.py rules; the keyless
default when nothing matches) and is painted with that biome's materials: the coast slot of its topography within 2 px
of water and the coastline transition up to 4 px, the rivers/lakes slot on river pixels, the vegetation / climate
transition slots within 2 px of a neighbour whose vegetation / climate differs, elsewhere the variation slots chosen by
two octaves of smooth noise. The textures are the game's own diffuse maps, tiled; hillshade from the game heightmap.
The engine's own masks are not public, so the patch shapes and band widths are an approximation, not a capture.

usage (constructor root):
  uv run python tools/terrain_biome_preview.py OUT --region prussia=8700,1420,520,360 [--region ...] [--world]
      [--variants vanilla,before,parents,final] [--scale 3]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from prosper_or_perish_constructor.worldbuilder import biomes as wb_biomes  # noqa: E402
from prosper_or_perish_constructor.worldbuilder import compat as wb_compat  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
MOD = REPO / "mod" / "Prosper or Perish (Population Growth & Food Rework)"
WATER = np.array([86, 118, 140], np.float32)
TOPO_COAST = {"flatland": 0, "hills": 1, "plateau": 2, "mountains": 3, "wetlands": 4}


def vanilla_game() -> Path:
    import tomllib

    load_order = tomllib.loads((REPO / "constructor.load_order.local.toml").read_text(encoding="utf-8")) \
        if (REPO / "constructor.load_order.local.toml").is_file() else {}
    root = (load_order.get("paths") or {}).get("vanilla_root")
    return Path(root) / "game" if root else Path.home() / ".cache/eu5-vanilla/game"


class Source:
    """One map + one biome/material pair."""

    def __init__(self, label: str, map_dir: Path, biomes_text: str, materials_text: str, game: Path, families):
        self.label = label
        self.map_dir = map_dir
        self.defs = wb_biomes.definitions(biomes_text)
        names, self.palettes = wb_biomes.parse_materials(materials_text)
        self.diffuse = dict(re.findall(r'name\s*=\s*"([^"]+)"\s*diffuse\s*=\s*"([^"]+)"', materials_text))
        self.game = game
        self.colors = {}
        for folder in (game / "in_game/map_data/named_locations", map_dir / "named_locations"):
            for path in sorted(folder.glob("*.txt")) if folder.is_dir() else []:
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    line = line.split("#")[0].strip()
                    if "=" in line:
                        name, color = (x.strip() for x in line.split("=", 1))
                        if color:
                            self.colors[int(color, 16)] = name
        tm = (map_dir / "location_templates.txt").read_text(encoding="utf-8-sig")
        self.attrs = {m[1]: dict(re.findall(r"\b(climate|vegetation|topography)\s*=\s*([A-Za-z0-9_]+)", m[2]))
                      for m in re.finditer(r"(?m)^([\w.-]+)\s*=\s*\{([^{}]*)\}", tm)}
        self.parent_topo = {c: p for p, cs in families.get("topography", {}).items() for c in cs}
        self._biome_cache: dict[str, str] = {}

    def biome(self, name: str | None) -> str:
        if name is None:
            return "default_biome"
        if name not in self._biome_cache:
            hits = wb_biomes.matching(self.defs, self.attrs.get(name, {}))
            self._biome_cache[name] = next((b for n, _, b in self.defs if hits and n == hits[0]), "default_biome")
        return self._biome_cache[name]


class Textures:
    def __init__(self, game: Path, tile: int):
        self.root = game / "in_game/gfx/terrain2/terrain_textures"
        self.tile = tile
        self.cache: dict[str, np.ndarray] = {}
        self.mean: dict[str, np.ndarray] = {}

    def get(self, path: str | None) -> np.ndarray:
        key = path or ""
        if key not in self.cache:
            file = self.root / key if path else None
            if file is not None and file.is_file():
                im = Image.open(file).convert("RGB")
                self.mean[key] = np.asarray(im.resize((64, 64)), np.float32).reshape(-1, 3).mean(0)
                self.cache[key] = np.asarray(im.resize((self.tile, self.tile), Image.LANCZOS), np.float32)
            else:
                self.mean[key] = np.array([150, 150, 150], np.float32)
                self.cache[key] = np.full((self.tile, self.tile, 3), 150, np.float32)
        return self.cache[key]


def smooth_noise(shape, seed: int, scale: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = ndimage.gaussian_filter(rng.random((shape[0] + 64, shape[1] + 64)), scale)[32:-32, 32:-32]
    flat = a.ravel().argsort().argsort().astype(np.float32) / a.size        # rank-normalised to 0..1
    return flat.reshape(shape)


def slot_map(src: Source, box, pad: int = 8, downsample: int = 1):
    x0, y0, w, h = box
    X0, Y0, X1, Y1 = x0 - pad * downsample, y0 - pad * downsample, x0 + w + pad * downsample, y0 + h + pad * downsample
    loc = np.asarray(Image.open(src.map_dir / "locations.png").convert("RGB").crop((X0, Y0, X1, Y1)))[::downsample, ::downsample]
    riv = np.asarray(Image.open(src.map_dir / "rivers.png").crop((X0, Y0, X1, Y1)))[::downsample, ::downsample]
    code = (loc[..., 0].astype(np.int64) << 16) | (loc[..., 1].astype(np.int64) << 8) | loc[..., 2]
    uniq, inv = np.unique(code, return_inverse=True)
    inv = inv.reshape(code.shape)
    names = [src.colors.get(int(c)) for c in uniq]
    attrs = [src.attrs.get(n, {}) if n else {} for n in names]
    palettes = []
    for n in names:
        palettes.append(src.palettes.get(src.biome(n)) or src.palettes.get("default_biome") or ["fallback_material"])
    veg = np.array([hash(a.get("vegetation")) % 1_000_003 for a in attrs])[inv]
    clim = np.array([hash(a.get("climate")) % 1_000_003 for a in attrs])[inv]
    topo = np.array([TOPO_COAST.get(src.parent_topo.get(a.get("topography"), a.get("topography")), 0) for a in attrs])[inv]
    water = riv == 254
    dist = ndimage.distance_transform_edt(~water)
    river = ndimage.binary_dilation(riv < 16) & ~water
    band = 1

    def differs(field):
        out = np.zeros(field.shape, bool)
        for dy in range(-band, band + 1):
            for dx in range(-band, band + 1):
                if dy or dx:
                    out |= field != np.roll(np.roll(field, dy, 0), dx, 1)
        return out
    nb_loc = differs(inv)
    vt = nb_loc & differs(veg) & ~water
    ct = nb_loc & differs(clim) & ~water
    n1 = smooth_noise(code.shape, 1, 6 / downsample)
    n2 = smooth_noise(code.shape, 2, 2.5 / downsample)
    nvar = np.array([max(len(p) - wb_biomes.VARIATION_START, 1) for p in palettes])[inv]
    var = np.minimum(((0.7 * n1 + 0.3 * n2) * nvar).astype(int), nvar - 1)
    slot = wb_biomes.VARIATION_START + var
    slot = np.where(ct, 9, slot)
    slot = np.where(vt, 8, slot)
    slot = np.where(river, 6, slot)
    slot = np.where((dist <= 4) & (dist > 2), 5, slot)
    slot = np.where(dist <= 2, topo, slot)
    border = nb_loc & ~water
    edge = np.zeros(code.shape, bool)
    edge[:, 1:] |= inv[:, 1:] != inv[:, :-1]
    edge[1:, :] |= inv[1:, :] != inv[:-1, :]
    p = pad
    cut = (slice(p, -p), slice(p, -p))
    return (inv[cut], slot[cut], water[cut], edge[cut] & ~water[cut], palettes, names)


def hillshade(game: Path, box, scale_out: int, downsample: int = 1):
    x0, y0, w, h = box
    hm = Image.open(game / "in_game/gfx/terrain2/heightmap.png")
    crop = np.asarray(hm.crop((x0 // 2 - 4, y0 // 2 - 4, (x0 + w) // 2 + 5, (y0 + h) // 2 + 5)), np.float32)
    crop = ndimage.gaussian_filter(crop, 1.6)
    gy, gx = np.gradient(crop)
    shade = np.clip(1.0 - 0.0025 * (gx + gy), 0.8, 1.12)[4:-4, 4:-4]
    big = Image.fromarray(shade.astype(np.float32)).resize(((w // downsample) * scale_out, (h // downsample) * scale_out), Image.BILINEAR)
    return np.asarray(big, np.float32)


def render(src: Source, tex: Textures, box, scale_out: int, *, downsample: int = 1, textured: bool = True) -> Image.Image:
    inv, slot, water, edge, palettes, names = slot_map(src, box, downsample=downsample)
    h, w = inv.shape
    mats = sorted({m for p in palettes for m in p})
    mid = {m: i for i, m in enumerate(mats)}
    lut = np.full((len(palettes), 32), 0, np.int32)
    for i, p in enumerate(palettes):
        ids = [mid[m] for m in p]
        lut[i, :len(ids)] = ids
        lut[i, len(ids):] = ids[-1]
    material = lut[inv, np.minimum(slot, 31)]
    big = np.kron(material, np.ones((scale_out, scale_out), np.int32))
    H, W = big.shape
    if textured:
        stack = np.stack([tex.get(src.diffuse.get(m)) for m in mats])
        yy, xx = np.mgrid[0:H, 0:W]
        rgb = stack[big, yy % tex.tile, xx % tex.tile]
    else:
        for m in mats:
            tex.get(src.diffuse.get(m))
        means = np.stack([tex.mean[src.diffuse.get(m) or ""] for m in mats])
        rgb = means[big]
    rgb = rgb * hillshade(src.game, box, scale_out, downsample)[:H, :W, None]
    wbig = np.kron(water, np.ones((scale_out, scale_out), bool))
    rgb[wbig] = WATER
    ebig = np.kron(edge, np.ones((scale_out, scale_out), bool))
    rgb[ebig] = rgb[ebig] * 0.78
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def label(img: Image.Image, text: str) -> Image.Image:
    out = img.copy()
    d = ImageDraw.Draw(out)
    d.rectangle((0, 0, 9 * len(text) + 16, 26), fill=(20, 20, 20))
    d.text((8, 6), text, fill=(240, 240, 240))
    return out


def sources(game: Path, which: list[str], final_root: Path = MOD) -> dict[str, Source]:
    families = wb_compat.load_families(REPO / "../EU5WorldBuilder/artifacts/geography_test/EU5 World Builder")
    nav = json.loads((REPO / "config/river_navigation.json").read_text())
    channels = [t["key"] for t in nav["topographies"].values()]
    full = wb_biomes.with_channels(families, channels)
    vb = (game / wb_biomes.RELATIVE_PATH).read_text(encoding="utf-8-sig")
    vm = (game / wb_biomes.MATERIALS_PATH).read_text(encoding="utf-8-sig")
    mod_map = MOD / "in_game/map_data"
    out = {}
    for w in which:
        if w == "vanilla":
            out[w] = Source("vanilla 1.4 (vanilla map)", game / "in_game/map_data", vb, vm, game, {})
        elif w == "before":
            out[w] = Source("PP before (vanilla biome files)", mod_map, vb, vm, game, full)
        elif w == "parents":
            out[w] = Source("PP classes as their vanilla parent", mod_map, wb_biomes.widen(vb, full)[0], vm, game, full)
        elif w == "final":
            fb = (final_root / wb_biomes.RELATIVE_PATH).read_text(encoding="utf-8-sig")
            fm = (final_root / wb_biomes.MATERIALS_PATH).read_text(encoding="utf-8-sig")
            out[w] = Source("PP with own biomes", mod_map, fb, fm, game, full)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--region", action="append", default=[])
    ap.add_argument("--variants", default="vanilla,before,parents,final")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--tile", type=int, default=96, help="output pixels per texture repeat")
    ap.add_argument("--final", type=Path, default=MOD, help="mod root holding the generated biomes.txt / materials.txt")
    ap.add_argument("--world", action="store_true", help="also render the whole map at 1/4 resolution (mean colours)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    game = vanilla_game()
    srcs = sources(game, args.variants.split(","), args.final)
    tex = Textures(game, args.tile)
    for spec in args.region:
        name, nums = spec.split("=")
        box = tuple(int(v) for v in nums.split(","))
        panels = [label(render(s, tex, box, args.scale), s.label) for s in srcs.values()]
        for key, p in zip(srcs, panels):
            p.save(args.out / f"{name}_{key}.png", optimize=True)
        print(name, flush=True)
    if args.world:
        for key, s in srcs.items():
            if key not in ("before", "parents", "final"):
                continue
            img = render(s, tex, (0, 0, 16384, 8192), 1, downsample=4, textured=False)
            img.save(args.out / f"world_{key}.png", optimize=True)
            print("world", key, flush=True)


if __name__ == "__main__":
    main()
