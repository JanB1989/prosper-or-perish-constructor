"""Village Schools (advance icon pp_village_schools_advance): a still life of the village schoolroom. A hornbook (the
child's first reader: an oak paddle with the alphabet and the Lord's Prayer under clear horn, held by a brass strip)
leans in front of a framed writing slate with chalk letters, the schoolmaster's brass handbell beside them.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans),
256 px, transparent; the game cuts their lower corners round (``advance_icon_mask``), so the foot stays narrow. The
DDS goes where the game reads advance icons. Run from the constructor:

  uv run python assets/icon_drawings/pp_village_schools_advance/draw.py [--preview <png>] [--png <png>]

Each object is painted upright on its own layer and turned into place (``layer``, ``put``); front objects shade the
ones behind (``cast``). Local helpers: ``hornbook``, ``slate``, ``handbell``, ``grain``, ``text_block``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, rim, soften

SEED = 53
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/pp_village_schools_advance.dds"
SERIF = ("/usr/share/fonts/opentype/urw-base35/P052-Roman.otf", "/usr/share/fonts/opentype/urw-base35/C059-Roman.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
SERIF_BOLD = ("/usr/share/fonts/opentype/urw-base35/P052-Bold.otf", "/usr/share/fonts/opentype/urw-base35/C059-Bold.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
INK = (54, 34, 20)
EDGE = (36, 22, 12, 230)


def font(paths, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- layers
def layer(seed: int) -> Icon:
    """A fresh canvas for one object, drawn upright around the canvas centre."""
    return Icon(seed=seed)


def put(ic: Icon, obj: Icon, degrees: float, at) -> Image.Image:
    """Turn ``obj`` about the canvas centre, move its centre to ``at`` and lay it over ``ic``. Returns the placed
    image (for shadows)."""
    img = obj.image.rotate(degrees, resample=Image.BICUBIC, center=(512, 512),
                           translate=(at[0] - 512, at[1] - 512))
    ic.image.alpha_composite(img)
    return img


def cast(ic: Icon, placed: Image.Image, dx: float, dy: float, blur: float, alpha: float) -> None:
    """Shadow of an object that is about to be laid on top, falling down-right onto what is already there."""
    m = ImageChops.offset(placed.getchannel("A"), int(dx), int(dy))
    ic.shade(m, (12, 6, 2), alpha, blur=blur)


def grain(ic: Icon, mask: Image.Image, box, vertical: bool = True, strength: int = 60, step: float = 7) -> None:
    """Wood grain: long wavy fibres along the board, a few darker growth lines."""
    x0, y0, x1, y1 = box
    rnd = ic.random.uniform

    def paint(d):
        if vertical:
            x = x0
            while x < x1:
                ph, amp = rnd(0, 6.3), rnd(2, 7)
                pts = [(x + amp * math.sin(ph + y / rnd(60, 120)), y) for y in np.arange(y0, y1 + 10, 10)]
                a = int(rnd(0.3, 1) * strength)
                d.line(pts, fill=(40, 22, 10, a) if ic.random.random() < 0.7 else (255, 236, 200, a // 2), width=2)
                x += step * rnd(0.6, 1.4)
        else:
            y = y0
            while y < y1:
                ph, amp = rnd(0, 6.3), rnd(2, 7)
                pts = [(x, y + amp * math.sin(ph + x / rnd(60, 120))) for x in np.arange(x0, x1 + 10, 10)]
                a = int(rnd(0.3, 1) * strength)
                d.line(pts, fill=(40, 22, 10, a) if ic.random.random() < 0.7 else (255, 236, 200, a // 2), width=2)
                y += step * rnd(0.6, 1.4)

    ic.overlay(paint, mask)


def text_block(size, lines, color, blur: float = 0.6) -> Image.Image:
    """Lines of text on a transparent sheet: ``lines`` = [(x, y, text, font), ...]."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, text, f in lines:
        d.text((x, y), text, font=f, fill=color)
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img


def bevel(ic: Icon, mask: Image.Image, width: int = 12, lit: float = 0.35, dark: float = 0.45) -> None:
    """Rounded edge on a flat object: light along the upper left rim, shade along the lower right rim."""
    inner = mask.filter(ImageFilter.MinFilter(width | 1))
    ring = ImageChops.subtract(mask, inner)
    up = ImageChops.subtract(ring, ImageChops.offset(ring, -width // 2, -width // 2))
    down = ImageChops.subtract(ring, ImageChops.offset(ring, width // 2, width // 2))
    ic.shade(ic.intersect(up, mask), (255, 238, 206), lit, blur=2)
    ic.shade(ic.intersect(down, mask), (14, 8, 4), dark, blur=2)


# ---------------------------------------------------------------- objects
def hornbook(ob: Icon) -> None:
    """Oak paddle, a printed sheet (cross row, alphabet, vowels, syllables, the Pater noster) under clear horn, a brass
    strip nailed round it, a hole in the handle for the cord."""
    cx, cy = 512, 430
    W, H = 360, 460  # board
    board = ob.mask("rounded_rectangle", (cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2), radius=34)
    handle = ob.mask("rounded_rectangle", (cx - 50, cy + H / 2 - 40, cx + 50, cy + H / 2 + 230), radius=46)
    neck = ob.poly_mask([(cx - 110, cy + H / 2 - 2), (cx + 110, cy + H / 2 - 2), (cx + 50, cy + H / 2 + 60),
                         (cx - 50, cy + H / 2 + 60)])
    shape = ImageChops.lighter(ImageChops.lighter(board, handle), neck.filter(ImageFilter.GaussianBlur(10)).point(
        lambda v: 255 if v > 110 else 0))
    hole = ob.mask("ellipse", (cx - 15, cy + H / 2 + 172, cx + 15, cy + H / 2 + 202))
    shape = ImageChops.subtract(shape, hole)
    # board thickness to the lower right
    side = ImageChops.subtract(ImageChops.offset(shape, 9, 12), shape)
    ob.fill(side, "#5a3a20", "#2a180a", noise=0.1)
    ob.fill(shape, "#b88450", "#4a2a12", radial=(cx - W * 0.4, cy - H * 0.45, H * 1.5), noise=0.12, chroma=0.06)
    grain(ob, shape, (cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2 + 240), vertical=True, strength=55, step=8)
    bevel(ob, shape, 14)
    ob.overlay(lambda d: d.ellipse((cx - 15, cy + H / 2 + 172, cx + 15, cy + H / 2 + 202), outline=(40, 24, 12, 230),
                                   width=4))
    # the printed sheet
    px0, py0, px1, py1 = cx - 138, cy - 186, cx + 138, cy + 166
    sheet = ob.mask("rectangle", (px0, py0, px1, py1))
    ob.fill(sheet, "#ecdcb4", "#bc9e6c", radial=(px0 + 40, py0 + 30, 460), noise=0.07, chroma=0.04)
    for _ in range(9):  # foxing and finger marks
        x, y, r = ob.random.uniform(px0, px1), ob.random.uniform(py0, py1), ob.random.uniform(10, 34)
        ob.shade(ob.intersect(ob.mask("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8)), sheet), (150, 110, 60),
                 ob.random.uniform(0.05, 0.14), blur=8)
    f1, f2, f3 = font(SERIF_BOLD, 34), font(SERIF, 30), font(SERIF, 19)
    lines = [(16, 10, "+ A a b c d e f g", f1), (16, 52, "h i k l m n o p q", f1), (16, 94, "r s t v u w x y z", f1),
             (16, 138, "a  e  i  o  u", f2), (16, 176, "ab eb ib ob ub", f2)]
    for k, t in enumerate(("In the Name of the Father,", "and of the Son, and of the", "Holy Ghost. Amen.",
                           "Our Father, which art in", "Heaven, hallowed be thy")):
        lines.append((18, 222 + k * 24, t, f3))
    txt = text_block((int(px1 - px0), int(py1 - py0)), lines, INK + (230,), blur=0.7)
    ob.image.alpha_composite(txt, (int(px0), int(py0)))
    ob.line([(px0 + 14, py0 + 214), (px1 - 14, py0 + 214)], 3, (90, 60, 34, 160))
    # horn: a warm film with glossy streaks
    ob.shade(sheet, (232, 196, 120), 0.18)
    for a, w, al in ((-80, 60, 0.32), (10, 26, 0.24), (150, 40, 0.16)):
        streak = ob.poly_mask([(px0 + a + 120, py0), (px0 + a + 120 + w, py0), (px0 + a - 60 + w, py1), (px0 + a - 60, py1)])
        ob.shade(ob.intersect(streak, sheet), (255, 252, 240), al, blur=8)
    ob.shade(ob.intersect(ob.mask("rectangle", (px0, py1 - 80, px1, py1)), sheet), (90, 60, 20), 0.15, blur=20)
    # brass strip with nails
    t = 14
    for box in ((px0 - t, py0 - t, px1 + t, py0 + 2), (px0 - t, py1 - 2, px1 + t, py1 + t),
                (px0 - t, py0 - t, px0 + 2, py1 + t), (px1 - 2, py0 - t, px1 + t, py1 + t)):
        m = ob.mask("rectangle", box)
        ob.fill(m, "#dcb466", "#6a4412", radial=(px0, py0, 560), noise=0.1)
    strip = ImageChops.subtract(ob.mask("rectangle", (px0 - t, py0 - t, px1 + t, py1 + t)), sheet)
    bevel(ob, strip, 6, 0.45, 0.5)
    for x, y in ([(x, py0 - t / 2) for x in np.linspace(px0, px1, 6)] + [(x, py1 + t / 2) for x in np.linspace(px0, px1, 6)]
                 + [(px0 - t / 2, y) for y in np.linspace(py0 + 60, py1 - 60, 4)]
                 + [(px1 + t / 2, y) for y in np.linspace(py0 + 60, py1 - 60, 4)]):
        ob.draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(64, 42, 14, 255))
        ob.draw.ellipse((x - 4, y - 5, x + 1, y), fill=(250, 226, 160, 255))
    ob.overlay(lambda d: d.rectangle((px0 - t, py0 - t, px1 + t, py1 + t), outline=(70, 44, 14, 220), width=3))
    # contour
    edge = ImageChops.subtract(shape.filter(ImageFilter.MaxFilter(5)), shape)
    ob.shade(edge, EDGE[:3], 0.85, clip=False)


def slate(ob: Icon) -> None:
    """A child's writing slate in a pine frame, chalk letters and a sum on it, a cord through the frame."""
    cx, cy = 512, 512
    W, H, F = 600, 430, 40
    outer = ob.mask("rectangle", (cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2))
    side = ImageChops.subtract(ImageChops.offset(outer, 8, 10), outer)
    ob.fill(side, "#6a4a28", "#2e1e0e", noise=0.1)
    ob.fill(outer, "#d6aa6c", "#8a5e30", radial=(cx - W * 0.4, cy - H * 0.5, W * 1.1), noise=0.1, chroma=0.05)
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    for box, vert in (((x0, y0, x1, y0 + F), False), ((x0, y1 - F, x1, y1), False), ((x0, y0, x0 + F, y1), True),
                      ((x1 - F, y0, x1, y1), True)):
        grain(ob, ob.mask("rectangle", box), box, vertical=vert, strength=60, step=6)
    for (a, b) in (((x0, y0), (x0 + F, y0 + F)), ((x1, y0), (x1 - F, y0 + F)), ((x0, y1), (x0 + F, y1 - F)),
                   ((x1, y1), (x1 - F, y1 - F))):
        ob.line([a, b], 3, (70, 44, 20, 200))
    bevel(ob, outer, 10)
    inner = ob.mask("rectangle", (x0 + F, y0 + F, x1 - F, y1 - F))
    ob.fill(inner, "#4a5458", "#1e2428", radial=(x0 + F + 60, y0 + F + 40, W * 0.9), noise=0.12, chroma=0.04)
    for _ in range(7):  # rubbed-out chalk
        x, y = ob.random.uniform(x0 + 80, x1 - 80), ob.random.uniform(y0 + 70, y1 - 70)
        ob.shade(ob.intersect(ob.mask("ellipse", (x - 90, y - 26, x + 90, y + 26)), inner), (210, 214, 210), 0.08, blur=14)
    ob.shade(ob.intersect(ob.mask("rectangle", (x0 + F, y0 + F, x1 - F, y0 + F + 30)), inner), (0, 0, 0), 0.4, blur=10)
    fb, fr = font(SERIF_BOLD, 92), font(SERIF, 64)
    chalk = text_block((int(W - 2 * F), int(H - 2 * F)), [(36, 6, "A  B  C", fb), (250, 118, "d e f", fr),
                                                          (238, 210, "2+2=4", fr)],
                       (238, 238, 230, 225), blur=1.4)
    chalk = chalk.rotate(-2, resample=Image.BICUBIC)
    clip = Image.new("RGBA", (ob.size, ob.size), (0, 0, 0, 0))
    clip.paste(chalk, (int(x0 + F), int(y0 + F)))
    ob.image.alpha_composite(Image.composite(clip, Image.new("RGBA", clip.size, (0, 0, 0, 0)), inner))
    ob.overlay(lambda d: d.rectangle((x0 + F, y0 + F, x1 - F, y1 - F), outline=(40, 26, 12, 220), width=4))
    # cord through a hole in the top bar
    ob.draw.ellipse((cx - 9, y0 + 12, cx + 9, y0 + 30), fill=(30, 18, 8, 255))
    edge = ImageChops.subtract(outer.filter(ImageFilter.MaxFilter(5)), outer)
    ob.shade(edge, EDGE[:3], 0.85, clip=False)


def handbell(ob: Icon) -> None:
    """The schoolmaster's brass handbell: flared bell with a bright reflection, dark mouth and clapper, a turned
    wooden handle."""
    cx, base = 512, 700
    bw, bh = 230, 210
    knots = [(0.0, 0.24), (0.08, 0.32), (0.3, 0.35), (0.6, 0.39), (0.85, 0.47), (1.0, 0.52)]
    ss = np.linspace(0, 1, 40)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * bw
    top = base - bh
    pts = [(cx - v, top + bh * s) for s, v in zip(ss, hw)] + [(cx + v, top + bh * s) for s, v in zip(ss[::-1], hw[::-1])]
    m = ob.poly_mask(pts)
    ob.fill(m, "#f2c260", "#4a2a08", (cx - bw * 0.42, cx + bw * 0.52), vertical=False, noise=0.06, chroma=0.04)
    ob.shade(ob.intersect(ob.mask("rectangle", (cx + bw * 0.06, top, cx + bw, base)), m), (30, 12, 0), 0.5, blur=18)
    ob.shade(ob.intersect(ob.mask("rectangle", (cx + bw * 0.4, top, cx + bw, base)), m), (255, 170, 80), 0.3, blur=8)
    ob.shade(ob.intersect(ob.poly_mask([(cx - bw * 0.2, top + 8), (cx - bw * 0.1, top + 8), (cx - bw * 0.25, base - 20),
                                        (cx - bw * 0.37, base - 20)]), m), (255, 252, 232), 0.8, blur=7)
    ob.shade(ob.intersect(ob.mask("rectangle", (cx - bw, top, cx - bw * 0.4, base)), m), (60, 30, 0), 0.25, blur=10)
    for f in (0.12, 0.8, 0.9):  # mouldings
        y = top + bh * f
        half = float(np.interp(f, ss, hw))
        ob.line([(cx - half, y), (cx + half, y + 2)], 4, (90, 56, 16, 170))
        ob.line([(cx - half, y - 4), (cx, y - 3)], 3, (255, 240, 190, 140))
    # mouth: a dark ellipse with the clapper
    mouth = (cx - bw * 0.5, base - 26, cx + bw * 0.5, base + 26)
    ob.fill(ob.mask("ellipse", mouth), "#2a1806", "#0c0602", noise=0.05)
    ob.overlay(lambda d: d.arc(mouth, 0, 180, fill=(255, 220, 150, 230), width=6))
    ob.fill(ob.mask("ellipse", (cx - 22, base - 4, cx + 22, base + 34)), "#6a5a44", "#1e160c",
            radial=(cx - 10, base + 4, 40), noise=0.05)
    ob.outline(pts, 4, EDGE)
    # turned handle: a short waisted grip with a round knob
    prof = [(0.0, 36), (0.1, 42), (0.18, 26), (0.42, 24), (0.56, 30), (0.66, 26), (0.74, 40), (0.88, 46), (0.97, 30),
            (1.0, 12)]
    hh = 170
    hs = np.linspace(0, 1, 40)
    hwid = np.interp(hs, [p[0] for p in prof], [p[1] for p in prof])
    htop = top - hh + 10
    hp = [(cx - v, top + 10 - hh * s) for s, v in zip(hs, hwid)] + [(cx + v, top + 10 - hh * s) for s, v in zip(hs[::-1], hwid[::-1])]
    hm = ob.poly_mask(hp)
    ob.fill(hm, "#9a5e34", "#241006", (cx - 44, cx + 44), vertical=False, noise=0.08)
    ob.shade(ob.intersect(ob.mask("rectangle", (cx - 26, htop, cx - 14, top + 10)), hm), (255, 226, 190), 0.5, blur=4)
    ob.outline(hp, 4, EDGE)
    ob.fill(ob.mask("ellipse", (cx - 46, top - 4, cx + 46, top + 22)), "#e8c070", "#6a4614", (cx - 46, cx + 46),
            vertical=False, noise=0.06)  # brass collar


# ---------------------------------------------------------------- composition
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.9
    ic.grade["light"] = 0.14
    s = layer(SEED + 1)
    slate(s)
    h = layer(SEED + 2)
    hornbook(h)
    b = layer(SEED + 3)
    handbell(b)
    for ob in (s, h, b):
        ob.image = rim(ob.image, 0.3, 22)
    put(ic, s, -9, (606, 330))
    hb = h.image.rotate(8, resample=Image.BICUBIC, center=(512, 512), translate=(420 - 512, 500 - 512))
    cast(ic, hb, 20, 24, 18, 0.55)
    ic.image.alpha_composite(hb)
    bb = b.image.rotate(-4, resample=Image.BICUBIC, center=(512, 512), translate=(736 - 512, 610 - 512))
    cast(ic, bb, -16, 14, 16, 0.5)
    ic.image.alpha_composite(bb)


def finished(ic: Icon) -> Image.Image:
    """Colour grade and soften as the building icons get them, no outline, fitted into the vanilla frame."""
    art = soften(grade(ic.image, ic.grade["mute"], ic.grade["gamma"], ic.grade["light"]), ic.grade["soften"])
    art = art.crop(art.getbbox())
    inner = SIDE - 16
    scale = inner / max(art.size)
    art = fit(art, (max(1, round(art.width * scale)), max(1, round(art.height * scale))))
    canvas = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    canvas.alpha_composite(art, ((SIDE - art.width) // 2, (SIDE - art.height) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", type=Path, help="write a preview sheet here instead of the DDS")
    ap.add_argument("--png", type=Path, help="write the finished 256 px PNG here instead of the DDS")
    args = ap.parse_args()
    ic = Icon(seed=SEED)
    draw(ic)
    image = finished(ic)
    if args.png:
        args.png.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.png)
    if args.preview:
        sheet = Image.new("RGBA", (SIDE + 90, SIDE + 12), (60, 60, 70, 255))
        sheet.alpha_composite(image, (6, 6))
        sheet.alpha_composite(image.resize((64, 64), Image.LANCZOS), (SIDE + 16, 6))
        sheet.save(args.preview)
    if args.png or args.preview:
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encode_dds(image, "DXT5"))
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
