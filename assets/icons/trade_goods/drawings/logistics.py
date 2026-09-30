"""Trade good ``logistics`` (haulage / freight): a spoked cart wheel behind a roped freight crate and a sack.

Drawn in code with ``eu5_building_pipeline.iconkit`` like the building icons, but finished as a goods icon
(vanilla ``icons/trade_goods`` format: 128 px, content ~121 px wide, ~4 px margins, soft black outline,
more saturated than building icons). Writes both files the build turns into DDS (``good_icons.py``):

- ``assets/icons/trade_goods/icon_goods_logistics.png`` (128 x 128)
- ``assets/icons/trade_goods/illustrations/icon_goods_logistics.png`` (1080 x 440, the icon at 400 px centred
  on a transparent strip, like the offset and manual_labor illustrations)

Run (from eu5-building-pipeline, which provides the kit):
  uv run python ../ProsperOrPerishConstructor/assets/icons/trade_goods/drawings/logistics.py
Add ``--preview <dir>`` to also write the 1024 px art and a comparison sheet against vanilla goods icons.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SCALE, SIZE
from eu5_building_pipeline.iconkit.finalize import grade, outline, soften

SEED = 7
ROOT = Path(__file__).resolve().parents[1]  # assets/icons/trade_goods
ICON_PNG = ROOT / "icon_goods_logistics.png"
ILLUSTRATION_PNG = ROOT / "illustrations" / "icon_goods_logistics.png"
IRON = (46, 44, 42)


# ---------------------------------------------------------------- helpers (from the transport-family drawings)
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def rope(ic: Icon, pts, width: int = 12) -> None:
    """Twisted hemp rope: dark core line, light strand, short twist ticks."""
    ic.line(pts, width + 8, (54, 36, 18))
    ic.line(pts, width, (196, 158, 96))
    seg = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / (width * 0.9)))
        for i in range(n):
            t = (i + 0.5) / n
            seg.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, math.atan2(y1 - y0, x1 - x0)))
    ic.overlay(lambda d: [d.line([(x - math.cos(a + 0.9) * width * 0.5, y - math.sin(a + 0.9) * width * 0.5),
                                  (x + math.cos(a + 0.9) * width * 0.5, y + math.sin(a + 0.9) * width * 0.5)],
                                 fill=(90, 60, 28, 200), width=4) for x, y, a in seg])
    ic.line([(x, y - width * 0.25) for x, y in pts], max(2, width // 4), (240, 214, 160, 150))


def boards(ic: Icon, pts, c1, c2, n: int, vertical: bool = False) -> Image.Image:
    """Plank face: ``n`` boards across the quad ``pts`` (tl, tr, br, bl) with per-board tone and grain."""
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.18)
    (tlx, tly), (trx, try_), (brx, bry), (blx, bly) = pts
    rnd = ic.random.uniform
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(n):
        a, b = i / n, (i + 1) / n
        if vertical:
            q = [(tlx + (trx - tlx) * a, tly + (try_ - tly) * a), (tlx + (trx - tlx) * b, tly + (try_ - tly) * b),
                 (blx + (brx - blx) * b, bly + (bry - bly) * b), (blx + (brx - blx) * a, bly + (bry - bly) * a)]
        else:
            q = [(tlx + (blx - tlx) * a, tly + (bly - tly) * a), (trx + (brx - trx) * a, try_ + (bry - try_) * a),
                 (trx + (brx - trx) * b, try_ + (bry - try_) * b), (tlx + (blx - tlx) * b, tly + (bly - tly) * b)]
        t = rnd(-1, 1)
        d.polygon(q, fill=(255, 226, 180, int(34 * t)) if t > 0 else (20, 10, 4, int(-50 * t)))
        for _ in range(4):  # grain along the board
            f = rnd(0.2, 0.8)
            p0 = (q[0][0] + (q[3][0] - q[0][0]) * f, q[0][1] + (q[3][1] - q[0][1]) * f)
            p1 = (q[1][0] + (q[2][0] - q[1][0]) * f, q[1][1] + (q[2][1] - q[1][1]) * f)
            g0 = rnd(0, 0.5)
            d.line([(p0[0] + (p1[0] - p0[0]) * g0, p0[1] + (p1[1] - p0[1]) * g0),
                    (p0[0] + (p1[0] - p0[0]) * (g0 + 0.4), p0[1] + (p1[1] - p0[1]) * (g0 + 0.4))],
                   fill=(60, 34, 14, 80), width=3)
        d.line([q[3], q[2]], fill=(40, 22, 10, 170), width=5)
        d.line([q[0], q[1]], fill=(255, 230, 190, 70), width=3)
    paste_clipped(ic, lay, m)
    return m


def wheel(ic: Icon, cx, cy, r, spokes: int = 12) -> None:
    """Big spoked cart wheel, upright and slightly turned: felloes lit top-left, iron tyre, turned hub."""
    sx = 0.9  # turned a little away: an ellipse, not a circle
    rx, ry = r * sx, r

    def E(f):
        return (cx - rx * f, cy - ry * f, cx + rx * f, cy + ry * f)

    # tyre thickness seen on the right side (the wheel's rim face)
    face = ImageChops.subtract(ic.mask("ellipse", (cx - rx + 26, cy - ry, cx + rx + 26, cy + ry)),
                               ic.mask("ellipse", E(0.8)))
    ic.fill(face, "#6a4424", "#24160a", (cx - rx, cx + rx), vertical=False, noise=0.1)
    ring = ImageChops.subtract(ic.mask("ellipse", E(1)), ic.mask("ellipse", E(0.8)))
    sw = int(r * 0.075)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes + 0.2
        p0 = (cx + math.cos(a) * rx * 0.18, cy + math.sin(a) * ry * 0.18)
        p1 = (cx + math.cos(a) * rx * 0.84, cy + math.sin(a) * ry * 0.84)
        ic.line([p0, p1], sw + 8, (50, 30, 14))
        lit = 0.5 + 0.5 * math.cos(a + 2.4)
        ic.line([p0, p1], sw, (int(118 + 90 * lit), int(76 + 66 * lit), int(36 + 40 * lit)))
        ic.line([(p0[0] - 3, p0[1] - 3), (p1[0] - 3, p1[1] - 3)], 3, (255, 226, 170, int(40 + 80 * lit)))
    ic.fill(ring, "#c48a4a", "#5a3414", radial=(cx - rx * 0.7, cy - ry * 0.8, r * 2.1), noise=0.16)
    for i in range(6):  # felloe joints
        a = 2 * math.pi * i / 6 + 0.5
        ic.line([(cx + math.cos(a) * rx * 0.8, cy + math.sin(a) * ry * 0.8),
                 (cx + math.cos(a) * rx * 0.95, cy + math.sin(a) * ry * 0.95)], 5, (50, 28, 12, 190))
    tw = int(r * 0.07)
    ic.overlay(lambda d: d.ellipse(E(1), outline=(58, 56, 56, 255), width=tw))
    ic.overlay(lambda d: d.arc((cx - rx + 6, cy - ry + 6, cx + rx - 6, cy + ry - 6), 190, 270, fill=(214, 206, 196, 190),
                               width=6))
    for i in range(12):  # tyre nails
        a = 2 * math.pi * i / 12
        x, y = cx + math.cos(a) * (rx - tw / 2), cy + math.sin(a) * (ry - tw / 2)
        ic.draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(120, 116, 110, 255))
    hr = r * 0.2
    hub = (cx - hr * sx, cy - hr, cx + hr * sx, cy + hr)
    ic.fill(ic.mask("ellipse", hub), "#b88450", "#4a2a10", radial=(cx - hr * 0.6, cy - hr * 0.7, hr * 2), noise=0.12)
    ic.overlay(lambda d: d.ellipse(hub, outline=IRON + (255,), width=10))
    ic.draw.ellipse((cx - hr * 0.35, cy - hr * 0.35, cx + hr * 0.35, cy + hr * 0.35), fill=(40, 36, 34, 255))
    ic.draw.ellipse((cx - hr * 0.3, cy - hr * 0.32, cx - hr * 0.05, cy - hr * 0.1), fill=(150, 146, 140, 255))


def crate(ic: Icon) -> Image.Image:
    """Freight crate in three-quarter view with corner battens, a diagonal brace and rope lashing."""
    front = [(360, 520), (780, 520), (780, 930), (360, 930)]
    top = [(360, 520), (780, 520), (900, 420), (480, 420)]
    side = [(780, 520), (900, 420), (900, 820), (780, 930)]
    boards(ic, side, "#8a5a2e", "#3e2410", 4)
    sm = ic.poly_mask(side)
    tint(ic, sm, sm, (20, 8, 0), 0.3)
    boards(ic, top, "#e8b878", "#b07c44", 4, vertical=True)
    fm = boards(ic, front, "#c88c4c", "#6e4420", 5)
    tint(ic, ic.mask("rectangle", (560, 520, 800, 940)), fm, (30, 12, 0), 0.22, 40)
    tint(ic, ic.mask("rectangle", (340, 800, 800, 950)), fm, (20, 8, 0), 0.25, 30)
    tint(ic, ic.mask("rectangle", (340, 500, 500, 700)), fm, (255, 236, 200), 0.15, 40)
    # battens round the front and a diagonal brace
    for p0, p1, w in (((378, 530), (378, 922), 36), ((762, 530), (762, 922), 36), ((370, 540), (770, 540), 30),
                      ((370, 910), (770, 910), 30), ((392, 890), (748, 560), 34)):
        ic.line([p0, p1], w + 8, (54, 30, 12))
        ic.line([p0, p1], w, (176, 120, 64))
        ic.line([(p0[0] - 4, p0[1] - 4), (p1[0] - 4, p1[1] - 4)], 4, (255, 222, 170, 110))
    for x, y in ((378, 540), (762, 540), (378, 910), (762, 910)):  # iron corner plates and nails
        ic.rect((x - 26, y - 26, x + 26, y + 26), "#6a6662", "#2e2c2a", edge=4)
        ic.draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(170, 166, 160, 255))
    for p0, p1 in (((780, 520), (900, 420)), ((900, 420), (900, 820))):
        ic.line([p0, p1], 22, (120, 78, 38))
    ic.outline(front, 5, (40, 20, 6, 220))
    ic.outline(top, 5, (40, 20, 6, 220))
    ic.outline(side, 5, (40, 20, 6, 220))
    # rope lashing: over the top and down the front and side, knotted on the front
    rope(ic, [(540, 930), (548, 520), (660, 420)], 14)
    rope(ic, [(660, 420), (840, 420 + 50), (842, 870)], 14)
    rope(ic, [(360, 700), (780, 700), (900, 600)], 14)
    ic.ellipse((526, 676, 574, 724), "#c4945a", "#6a4a24", edge=5)
    rope(ic, [(548, 720), (536, 790), (556, 836)], 10)
    return union(ic.poly_mask(front), ic.poly_mask(top), sm)


def sack(ic: Icon, cx, base, w, h) -> None:
    """Jute sack slumped against the crate, tied at the neck."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 60, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.08 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.7:
            y = min(y, base)
        pts.append((cx + co * rx, y))
    body = ic.poly_mask(pts)
    ic.fill(body, "#e8c07c", "#6a4418", radial=(cx - w * 0.3, base - h * 0.8, w * 1.0), noise=0.18)
    ic.overlay(lambda d: [d.line([(cx - w / 2, y), (cx + w / 2, y)], fill=(110, 80, 40, 60), width=3)
                          for y in np.arange(base - h, base, 12)], body)
    tint(ic, ic.mask("ellipse", (cx, base - h * 0.6, cx + w, base + 20)), body, (30, 16, 4), 0.3, 20)
    neck = [(cx - 40, base - h * 0.8), (cx - 34, base - h * 1.02), (cx - 60, base - h * 1.14), (cx, base - h * 1.08),
            (cx + 54, base - h * 1.16), (cx + 34, base - h * 1.0), (cx + 42, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), "#e2c68e", "#8a6a3a", noise=0.16)
    ic.outline(neck, 4, (60, 40, 20, 200))
    ic.line([(cx - 38, base - h * 0.95), (cx + 38, base - h * 0.94)], 12, (120, 80, 40))
    ic.outline(pts, 5, (60, 40, 20, 200))


def draw(ic: Icon) -> None:
    wheel(ic, 400, 420, 330)
    crate(ic)
    sack(ic, 250, 950, 270, 330)


# ---------------------------------------------------------------- goods finish
def finish(ic: Icon) -> Image.Image:
    """Vanilla goods format at 1024: warm grade, black outline, silhouette 121/128 wide, 5 px margins."""
    art = grade(ic.image, 1.08, 0.88, 0.2)
    art = soften(art, 1.0)
    full = outline(art)
    a = np.asarray(full.getchannel("A")) > 128
    ys, xs = np.nonzero(a)
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    scale = min(121 * SCALE / bw, 119 * SCALE / bh)
    crop = full.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.alpha_composite(crop, ((SIZE - crop.width) // 2, SIZE - 5 * SCALE - crop.height))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path, help="Also write the 1024 px art and a sheet next to vanilla goods icons.")
    args = ap.parse_args()
    ic = Icon(seed=SEED)
    draw(ic)
    full = finish(ic)
    icon = full.resize((128, 128), Image.LANCZOS).filter(ImageFilter.UnsharpMask(0.8, 70, 2))
    ICON_PNG.parent.mkdir(parents=True, exist_ok=True)
    icon.save(ICON_PNG)
    ill = Image.new("RGBA", (1080, 440), (0, 0, 0, 0))
    art = full.resize((400, 400), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.0, 50, 2))
    ill.alpha_composite(art, ((1080 - 400) // 2, (440 - 400) // 2))
    ILLUSTRATION_PNG.parent.mkdir(parents=True, exist_ok=True)
    ill.save(ILLUSTRATION_PNG)
    print("wrote", ICON_PNG, ILLUSTRATION_PNG)
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=True)
        full.save(args.preview / "logistics_1024.png")
        van = Path.home() / ".cache/eu5-vanilla/game/main_menu/gfx/interface/icons/trade_goods"
        cells = [Image.open(van / f"icon_goods_{g}.dds").convert("RGBA").resize((128, 128)) for g in ("tools", "lumber")]
        cells.insert(1, icon)
        cells.append(Image.open(ROOT / "icon_goods_offset.png").convert("RGBA").resize((128, 128)))
        for zoom in (1, 3):
            sheet = Image.new("RGBA", (len(cells) * (128 + 12) * zoom + 12 * zoom, (128 + 24) * zoom), (58, 52, 45, 255))
            for i, c in enumerate(cells):
                c = c.resize((128 * zoom, 128 * zoom), Image.NEAREST)
                sheet.alpha_composite(c, (12 * zoom + i * (128 + 12) * zoom, 12 * zoom))
            sheet.save(args.preview / f"logistics_compare_{zoom}x.png")


if __name__ == "__main__":
    main()
