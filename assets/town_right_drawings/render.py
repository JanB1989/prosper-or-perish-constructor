"""Render the 34 specialization town right icons (17 lines x charter/rights) and write their DDS files.

Run from the constructor repo:

    uv run python assets/town_right_drawings/render.py                 # all icons -> PNG + DDS
    uv run python assets/town_right_drawings/render.py --only cloth glass --no-dds
    uv run python assets/town_right_drawings/render.py --sheet /tmp/sheet.png [--zoom 2]

PNGs (128 px and 1024 px) go to ``artifacts/icons/town_rights/``; DDS files (DXT5, 128 px, full mip chain,
the vanilla ``icons/town_rights`` format) go to the mod's ``main_menu/gfx/interface/icons/town_rights/``,
named after the town right key, which is how the game finds a town right's icon.
"""

from __future__ import annotations

import argparse
import importlib.util
import struct
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import frame  # noqa: E402

GOODS = ("cloth", "fine_cloth", "leather", "pottery", "furniture", "glass", "jewelry", "porcelain", "lacquerware",
         "beer", "liquor", "books", "tools", "weaponry", "firearms", "cannons", "naval_supplies")
TIERS = {"charter": "pp_{good}_charter", "rights": "pp_{good}_rights"}
PNG_DIR = REPO / "artifacts" / "icons" / "town_rights"
DDS_DIR = REPO / "mod" / "Prosper or Perish (Population Growth & Food Rework)" / "main_menu" / "gfx" / "interface" / \
    "icons" / "town_rights"
VANILLA = Path.home() / ".cache" / "eu5-vanilla" / "game" / "main_menu" / "gfx" / "interface" / "icons" / "town_rights"
VANILLA_PAIRS = ("textile", "tooling", "weaponry", "book", "brewing", "naval")


def load_good(good: str):
    path = HERE / "goods" / f"{good}.py"
    spec = importlib.util.spec_from_file_location(f"town_right_{good}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def render_one(job: tuple[str, str, bool]) -> tuple[str, str]:
    good, tier, dds = job
    key = TIERS[tier].format(good=good)
    icon = frame.compose(load_good(good), tier)
    images = frame.finish(icon)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    png = PNG_DIR / f"{key}.png"
    images[128].save(png)
    images[1024].save(PNG_DIR / f"{key}_1024.png")
    if dds:
        from prosper_or_perish_constructor.good_icons import write_dxt5

        dds_path = DDS_DIR / f"{key}.dds"
        write_dxt5(png, dds_path, (128, 128))
        # vanilla headers carry the top level's byte size as linear size (16 bytes per 4x4 block); Pillow writes a pitch
        data = bytearray(dds_path.read_bytes())
        struct.pack_into("<I", data, 20, 128 * 128)
        dds_path.write_bytes(bytes(data))
    return good, tier


def contact_sheet(goods: tuple[str, ...], out: Path, zoom: int = 1, cols: int = 1) -> None:
    """Vanilla pairs on top, then one row per line: name, charter, rights (128 px), then both at 48 px."""
    cell = 128 * zoom
    small = 48 * zoom
    pad = 10 * zoom
    label_w = 150 * zoom
    rows: list[tuple[str, Image.Image, Image.Image]] = []
    for p in VANILLA_PAIRS:
        a, b = VANILLA / f"{p}_charter.dds", VANILLA / f"royal_{p}_rights.dds"
        if a.exists() and b.exists():
            rows.append((f"vanilla {p}", Image.open(a).convert("RGBA"), Image.open(b).convert("RGBA")))
    for g in goods:
        a, b = PNG_DIR / f"pp_{g}_charter.png", PNG_DIR / f"pp_{g}_rights.png"
        if a.exists() and b.exists():
            rows.append((g, Image.open(a).convert("RGBA"), Image.open(b).convert("RGBA")))
    per_col = (len(rows) + cols - 1) // cols
    entry_w = label_w + 2 * cell + 2 * small + 5 * pad
    entry_h = cell + pad
    sheet = Image.new("RGBA", (cols * entry_w + pad, per_col * entry_h + pad), (34, 31, 28, 255))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 15 * zoom)
    except OSError:
        font = ImageFont.load_default()
    for i, (name, a, b) in enumerate(rows):
        c, r = divmod(i, per_col)
        x, y = pad + c * entry_w, pad + r * entry_h
        d.text((x, y + cell // 2 - 8 * zoom), name, fill=(220, 210, 190, 255), font=font)
        x += label_w
        for im in (a, b):
            sheet.alpha_composite(im.resize((cell, cell), Image.LANCZOS if zoom == 1 else Image.NEAREST), (x, y))
            x += cell + pad
        for im in (a, b):
            sm = im.resize((48, 48), Image.LANCZOS)
            sm = sm.resize((small, small), Image.NEAREST)
            sheet.alpha_composite(sm, (x, y + (cell - small) // 2))
            x += small + pad
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", choices=GOODS, help="render only these lines")
    ap.add_argument("--no-dds", action="store_true", help="write PNGs only")
    ap.add_argument("--sheet", type=Path, help="also write a contact sheet PNG here")
    ap.add_argument("--zoom", type=int, default=1)
    ap.add_argument("--cols", type=int, default=1, help="columns of entries in the contact sheet")
    ap.add_argument("--no-render", action="store_true", help="only rebuild the contact sheet")
    args = ap.parse_args()
    goods = tuple(args.only) if args.only else GOODS
    if not args.no_render:
        jobs = [(g, t, not args.no_dds) for g in goods for t in TIERS]
        with ProcessPoolExecutor(max_workers=min(8, len(jobs))) as ex:
            for good, tier in ex.map(render_one, jobs):
                print(f"rendered {TIERS[tier].format(good=good)}")
    if args.sheet:
        contact_sheet(goods, args.sheet, args.zoom, args.cols)
        print(f"sheet {args.sheet}")


if __name__ == "__main__":
    main()
