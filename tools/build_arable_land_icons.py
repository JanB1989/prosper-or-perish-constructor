"""Build every Arable Land icon (the population capacity, renamed 2026-10-10) into the mod.

- Arable Land itself: the tilled-field painting (assets/icons/arable_land/arable_land.png). It replaces vanilla's
  population capacity concept icon (modifier_types/total_population_capacity_modifier.dds) and the map mode icon.
- Arable Land modifiers: the field with vanilla's capacity symbol (an arrow up to a bar, as on vanilla's capacity
  icons), in vanilla's shared slot modifier_types/global_population_capacity_modifier.dds, which every population
  capacity modifier type points at.
- The three states (location view land chip, Europedia, concepts, strength markers), redrawn 2026-10-27 (Jan: the
  land plates with peasants and chevrons were too busy and not distinct): the same field, graded lush / plain /
  parched, and one round badge in the lower right whose colour and mark tell the state apart at chip size (30 px):
  green with two chevrons up (abundant), gold with one chevron up (available), red with two chevrons down (overused).

Rerun after a game update:

    uv run python tools/build_arable_land_icons.py                  # write the DDS into the mod
    uv run python tools/build_arable_land_icons.py --preview X.png  # also a sheet at full and chip size
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from eu5_building_pipeline.dds import write_game_dds


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mod/Prosper or Perish (Population Growth & Food Rework)"
FIELD = ROOT / "assets/icons/arable_land/arable_land.png"
ICONS_DIR = "gfx/interface/icons/pp_arable_land"   # under the mod's main_menu: abundant.dds, available.dds, overused.dds
BASE_TARGETS = {   # under the mod's main_menu/gfx/interface/icons -> "field" or "modifier"
    "modifier_types/total_population_capacity_modifier.dds": "field",
    "map_modes/pp_population_capacity.dds": "field",
    "modifier_types/global_population_capacity_modifier.dds": "modifier",
}
SIZE = 128


def _field() -> Image.Image:
    with Image.open(FIELD) as source:
        return source.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)


def _capacity_symbol() -> Image.Image:
    """Vanilla's capacity mark, redrawn at this size: a pale bar with an arrow pointing up to it, dark outline."""
    sym = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(sym)
    fill, line = (228, 222, 204, 255), (48, 42, 34, 255)
    d.rectangle((80, 70, 124, 79), fill=fill, outline=line, width=3)
    d.polygon([(102, 84), (82, 104), (93, 104), (93, 124), (111, 124), (111, 104), (122, 104)], fill=fill, outline=line)
    d.line([(102, 84), (82, 104), (93, 104), (93, 124), (111, 124), (111, 104), (122, 104), (102, 84)], fill=line, width=3)
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow.putalpha(sym.getchannel("A").point(lambda a: int(a * 0.55)).filter(ImageFilter.GaussianBlur(2)))
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.alpha_composite(shadow, (2, 2))
    out.alpha_composite(sym)
    return out


def base_icons() -> dict[str, Image.Image]:
    field = _field()
    modifier = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    modifier.alpha_composite(field.resize((104, 104), Image.LANCZOS), (0, 0))
    modifier.alpha_composite(_capacity_symbol())
    return {"field": field, "modifier": modifier}


def _tint(im: Image.Image, rgb: tuple[int, int, int], amount: float) -> Image.Image:
    """Shift the colour toward ``rgb``, keeping the shading and the alpha."""
    lum = im.convert("L")
    colour = Image.merge("RGB", tuple(lum.point(lambda v, c=c: int(v * c / 255)) for c in rgb))
    mixed = Image.blend(im.convert("RGB"), colour, amount)
    mixed.putalpha(im.getchannel("A"))
    return mixed


# state -> field grade (tint, amount, saturation, brightness), badge (light, dark), chevrons (count, pointing up)
STATES = {
    "abundant": (((96, 200, 64), 0.45, 1.35, 1.08), ((120, 214, 84), (34, 104, 30)), (2, True)),
    "available": ((None, 0.0, 1.0, 1.0), ((246, 206, 92), (150, 104, 22)), (1, True)),
    "overused": (((190, 92, 50), 0.45, 0.65, 0.88), ((236, 88, 70), (126, 22, 18)), (2, False)),
}
_SS = 4   # supersampling of the badge


def _grade(field: Image.Image, tint: tuple[int, int, int] | None, amount: float, saturation: float, brightness: float) -> Image.Image:
    out = _tint(field, tint, amount) if tint else field.copy()
    alpha = out.getchannel("A")
    out = ImageEnhance.Brightness(ImageEnhance.Color(out).enhance(saturation)).enhance(brightness)
    out.putalpha(alpha)
    return out


def _badge(light: tuple[int, int, int], dark: tuple[int, int, int], count: int, up: bool) -> Image.Image:
    """A round badge (radial light-to-dark fill, dark rim, thin light inner ring) with 1-2 bold white chevrons."""
    n = SIZE * _SS
    cx, cy, r = 92 * _SS, 92 * _SS, 34 * _SS
    badge = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    d.ellipse((cx - r - 3 * _SS, cy - r - 3 * _SS, cx + r + 3 * _SS, cy + r + 3 * _SS), fill=(30, 24, 18, 255))
    for i in range(r, 0, -_SS):   # radial fill, lighter toward the upper left
        t = i / r
        c = tuple(int(dark[k] + (light[k] - dark[k]) * (1 - t) ** 0.6) for k in range(3))
        o = int((r - i) * 0.25)
        d.ellipse((cx - i - o, cy - i - o, cx + i - o, cy + i - o), fill=(*c, 255))
    d.ellipse((cx - r + 3 * _SS, cy - r + 3 * _SS, cx + r - 3 * _SS, cy + r - 3 * _SS),
              outline=(255, 255, 255, 70), width=2 * _SS)
    w, h, stroke, gap = 40 * _SS, 14 * _SS, 9 * _SS, 15 * _SS
    tops = [cy - h // 2] if count == 1 else [cy - h // 2 - gap // 2, cy - h // 2 + gap // 2]
    for top in tops:
        apex, base = (top, top + h) if up else (top + h, top)
        pts = [(cx - w // 2, base), (cx, apex), (cx + w // 2, base)]
        d.line(pts, fill=(30, 24, 18, 200), width=stroke + 4 * _SS, joint="curve")   # dark edge
        d.line(pts, fill=(255, 252, 240, 255), width=stroke, joint="curve")
    badge = badge.resize((SIZE, SIZE), Image.LANCZOS)
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow.putalpha(badge.getchannel("A").point(lambda a: int(a * 0.6)).filter(ImageFilter.GaussianBlur(3)))
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.alpha_composite(shadow, (2, 3))
    out.alpha_composite(badge)
    return out


def icons() -> dict[str, Image.Image]:
    field = _field().resize((112, 112), Image.LANCZOS)
    built = {}
    for name, (grade, (light, dark), (count, up)) in STATES.items():
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.alpha_composite(_grade(field, *grade), (0, 0))
        canvas.alpha_composite(_badge(light, dark, count, up))
        built[name] = canvas
    return built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="also write a preview sheet (full size and chip size)")
    parser.add_argument("--no-write", action="store_true", help="only the preview")
    args = parser.parse_args(argv)
    built = icons()
    base = base_icons()
    if args.preview:
        shown = [base["field"], base["modifier"], *built.values()]
        sheet = Image.new("RGBA", (len(shown) * 150 + len(shown) * 50, 150), (52, 60, 74, 255))
        for i, im in enumerate(shown):
            sheet.alpha_composite(im, (i * 150 + 10, 10))
            sheet.alpha_composite(im.resize((30, 30), Image.LANCZOS), (len(shown) * 150 + i * 50 + 10, 60))
        sheet.save(args.preview)
    if not args.no_write:
        target = MOD / "main_menu" / ICONS_DIR
        target.mkdir(parents=True, exist_ok=True)
        for name, im in built.items():
            write_game_dds(im, target / f"{name}.dds")   # DXT5 + full mips (eu5_building_pipeline.dds)
            print((target / f"{name}.dds").relative_to(ROOT))
        for rel, kind in BASE_TARGETS.items():
            path = MOD / "main_menu/gfx/interface/icons" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            write_game_dds(base[kind], path)   # DXT5 + full mips (eu5_building_pipeline.dds)
            print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
