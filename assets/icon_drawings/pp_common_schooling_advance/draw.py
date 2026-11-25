"""Common Schooling (advance icon pp_common_schooling_advance): a still life of schooling by ordinance. A printed school
ordinance with a red wax seal on its ribbons stands behind a bundle of identical printed primers, tied with twine for
the parishes; one primer lies open on top at its alphabet page with a woodcut apple.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans),
256 px, transparent; the game cuts their lower corners round (``advance_icon_mask``), so the foot stays narrow. The
DDS goes where the game reads advance icons. Run from the constructor:

  uv run python assets/icon_drawings/pp_common_schooling_advance/draw.py [--preview <png>] [--png <png>]

Objects are painted on their own layers, flat ones tipped into view with a perspective warp (``tip``), and laid
together back to front; front objects shade the ones behind (``cast``). Local helpers: ``ordinance``, ``seal``,
``primer_stack``, ``open_primer``, ``bevel``, ``text_block``, ``contour``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, rim, soften

SEED = 71
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/pp_common_schooling_advance.dds"
SERIF = ("/usr/share/fonts/opentype/urw-base35/P052-Roman.otf", "/usr/share/fonts/opentype/urw-base35/C059-Roman.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
SERIF_BOLD = ("/usr/share/fonts/opentype/urw-base35/P052-Bold.otf", "/usr/share/fonts/opentype/urw-base35/C059-Bold.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
ITALIC = ("/usr/share/fonts/opentype/urw-base35/P052-Italic.otf", "/usr/share/fonts/opentype/urw-base35/C059-Italic.otf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")
INK = (40, 26, 16)
EDGE = (36, 22, 12, 230)
TEXT = ("Every parish shall keep a school,", "and every child, boy and girl,", "from the fifth year to the",
        "thirteenth, shall be sent to it", "winter and summer, to learn", "to read, to write and to reckon,",
        "and the catechism. Parents who", "keep their children at home", "shall pay a fine to the poor box.",
        "The schoolmaster shall be paid", "by the parish and the church.")


def font(paths, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- layers
def layer(seed: int) -> Icon:
    return Icon(seed=seed)


def tip(img: Image.Image, src, dst) -> Image.Image:
    """Perspective warp: the quad ``src`` of ``img`` lands on the quad ``dst``."""
    rows = []
    for (xs, ys), (xd, yd) in zip(src, dst):
        rows.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
        rows.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd])
    coeffs = np.linalg.solve(np.array(rows, float), np.array(src, float).reshape(8))
    return img.transform(img.size, Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def turned(img: Image.Image, degrees: float, at) -> Image.Image:
    return img.rotate(degrees, resample=Image.BICUBIC, center=(512, 512), translate=(at[0] - 512, at[1] - 512))


def cast(ic: Icon, placed: Image.Image, dx: float, dy: float, blur: float, alpha: float) -> None:
    """Shadow of an object that is about to be laid on top, falling onto what is already there."""
    m = ImageChops.offset(placed.getchannel("A"), int(dx), int(dy))
    ic.shade(m, (12, 6, 2), alpha, blur=blur)


def bevel(ic: Icon, mask: Image.Image, width: int = 12, lit: float = 0.35, dark: float = 0.45) -> None:
    """Rounded edge on a flat object: light along the upper left rim, shade along the lower right rim."""
    inner = mask.filter(ImageFilter.MinFilter(width | 1))
    ring = ImageChops.subtract(mask, inner)
    up = ImageChops.subtract(ring, ImageChops.offset(ring, -width // 2, -width // 2))
    down = ImageChops.subtract(ring, ImageChops.offset(ring, width // 2, width // 2))
    ic.shade(ic.intersect(up, mask), (255, 238, 206), lit, blur=2)
    ic.shade(ic.intersect(down, mask), (14, 8, 4), dark, blur=2)


def text_block(size, lines, blur: float = 0.6) -> Image.Image:
    """Text on a transparent sheet: ``lines`` = [(x, y, text, font, colour, anchor), ...]."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, text, f, col, anchor in lines:
        d.text((x, y), text, font=f, fill=col, anchor=anchor)
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img


def contour(ob: Icon, alpha: float = 0.85) -> None:
    """Thin dark painted edge round everything on the layer."""
    a = ob.alpha().point(lambda v: 255 if v > 40 else 0)
    ob.shade(ImageChops.subtract(a.filter(ImageFilter.MaxFilter(5)), a), EDGE[:3], alpha, clip=False)


def paste_clipped(ob: Icon, sheet: Image.Image, at, clip: Image.Image) -> None:
    lay = Image.new("RGBA", (ob.size, ob.size), (0, 0, 0, 0))
    lay.paste(sheet, (int(at[0]), int(at[1])))
    ob.image.alpha_composite(Image.composite(lay, Image.new("RGBA", lay.size, (0, 0, 0, 0)), clip))


# ---------------------------------------------------------------- objects
def ordinance(ob: Icon) -> None:
    """The printed ordinance: a title in capitals, a woodcut rule, a drop initial and the text, the top edge curling
    forward, foxed paper."""
    cx, cy = 512, 512
    W, H = 500, 640
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    paper = ob.poly_mask([(x0, y0 + 30), (x1, y0 + 30), (x1 + 6, y1), (x0 - 4, y1 - 6)])
    ob.fill(paper, "#f0e2bc", "#c2a676", radial=(x0 + 60, y0 + 80, H * 1.0), noise=0.07, chroma=0.04)
    for _ in range(12):
        x, y, r = ob.random.uniform(x0, x1), ob.random.uniform(y0, y1), ob.random.uniform(12, 44)
        ob.shade(ob.intersect(ob.mask("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8)), paper), (150, 108, 58),
                 ob.random.uniform(0.05, 0.14), blur=10)
    ft, fs, fb, fi, fd = font(SERIF_BOLD, 58), font(ITALIC, 30), font(SERIF, 25), font(SERIF_BOLD, 112), font(ITALIC, 24)
    lines = [(W / 2, 62, "ORDINANCE", ft, INK + (240,), "ma"), (W / 2, 130, "for the Schools of the Land", fs, INK + (230,), "ma")]
    for k, t in enumerate(TEXT):
        indent = 96 if k < 3 else 30
        lines.append((indent if k < 3 else 30, 206 + k * 34, t if k else t[6:] if False else t, fb, INK + (225,), "la"))
    lines.append((30, 206, "", fb, INK, "la"))
    lines.append((W - 40, 600, "Given at our Residence.", fd, INK + (220,), "ra"))
    txt = text_block((int(W), int(H)), lines, blur=0.7)
    deco = Image.new("RGBA", (int(W), int(H)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(deco)
    for y in (172, 180):
        dd.line([(36, y), (W - 36, y)], fill=INK + (210,), width=3 if y == 172 else 2)
    for x in np.arange(60, W - 50, 22):  # woodcut vine on the rule
        dd.ellipse((x - 5, 186, x + 5, 196), outline=INK + (170,), width=2)
    dd.rectangle((28, 204, 88, 304), outline=INK + (200,), width=3)  # drop initial frame
    dd.text((58, 254), "E", font=fi, fill=(150, 34, 24, 235), anchor="mm")
    deco = deco.filter(ImageFilter.GaussianBlur(0.6))
    paste_clipped(ob, deco, (x0, y0), paper)
    paste_clipped(ob, txt, (x0, y0), paper)
    # the top edge curls forward into a loose roll
    roll = ob.mask("rounded_rectangle", (x0 - 8, y0 - 6, x1 + 8, y0 + 46), radius=26)
    ob.fill(roll, "#f6ead0", "#a88a5c", (y0 - 6, y0 + 46), noise=0.06)
    ob.shade(ob.intersect(ob.mask("rectangle", (x0 - 10, y0 + 22, x1 + 10, y0 + 48)), roll), (70, 44, 18), 0.4, blur=6)
    ob.shade(ob.intersect(ob.mask("rectangle", (x0 - 10, y0 - 6, x1 + 10, y0 + 8)), roll), (255, 250, 236), 0.35, blur=4)
    ob.shade(ob.intersect(ob.mask("rectangle", (x0, y0 + 46, x1, y0 + 80)), paper), (60, 40, 16), 0.3, blur=10)
    ob.overlay(lambda d: d.rounded_rectangle((x0 - 8, y0 - 6, x1 + 8, y0 + 46), radius=26, outline=(110, 84, 50, 200),
                                             width=3))
    ob.shade(ob.intersect(ob.mask("rectangle", (cx + 80, y0, x1 + 20, y1 + 10)), paper), (40, 24, 8), 0.12, blur=50)
    contour(ob)


def seal(ob: Icon, cx, cy, r) -> None:
    """Red wax seal on two ribbon tails: an irregular blob, an impressed ring and rosette, glossy highlights."""
    for dx, ang, col in ((-14, 104, ("#3e5a7a", "#16243a")), (14, 78, ("#c8b07a", "#6a5228"))):
        a = math.radians(ang)
        p0 = (cx + dx, cy)
        p1 = (cx + dx + math.cos(a) * r * 2.6, cy + math.sin(a) * r * 2.6)
        n = (-math.sin(a) * 16, math.cos(a) * 16)
        tail = [(p0[0] - n[0], p0[1] - n[1]), (p0[0] + n[0], p0[1] + n[1]), (p1[0] + n[0], p1[1] + n[1]),
                (p1[0], p1[1] - 18), (p1[0] - n[0], p1[1] - n[1])]
        tm = ob.poly_mask(tail)
        ob.fill(tm, col[0], col[1], radial=(p0[0], p0[1], r * 3), noise=0.08)
        ob.overlay(lambda d, t=tail: d.line(t + [t[0]], fill=EDGE, width=3))
    blob = ob.jitter(cx, cy, r, r * 0.95, 18, 0.06)
    bm = ob.poly_mask(blob).filter(ImageFilter.GaussianBlur(4)).point(lambda v: 255 if v > 120 else 0)
    ob.fill(bm, "#d0402c", "#5a0e08", radial=(cx - r * 0.4, cy - r * 0.4, r * 1.7), noise=0.08, chroma=0.03)
    ring = (cx - r * 0.66, cy - r * 0.66, cx + r * 0.66, cy + r * 0.66)
    ob.overlay(lambda d: d.ellipse(ring, outline=(80, 10, 6, 210), width=5))
    ob.overlay(lambda d: d.ellipse((ring[0] + 3, ring[1] + 3, ring[2] + 3, ring[3] + 3), outline=(255, 150, 120, 120),
                                   width=3))
    for k in range(8):  # rosette
        a = k * math.pi / 4
        ob.overlay(lambda d, a=a: d.ellipse((cx + math.cos(a) * r * 0.32 - r * 0.12, cy + math.sin(a) * r * 0.32 - r * 0.12,
                                             cx + math.cos(a) * r * 0.32 + r * 0.12, cy + math.sin(a) * r * 0.32 + r * 0.12),
                                            outline=(90, 12, 8, 200), width=3))
    ob.shade(ob.intersect(ob.mask("ellipse", (cx - r * 0.7, cy - r * 0.8, cx - r * 0.1, cy - r * 0.35)), bm),
             (255, 220, 200), 0.55, blur=5)
    ob.overlay(lambda d: d.line(blob + [blob[0]], fill=(60, 8, 4, 200), width=3))


def primer_stack(ob: Icon, n: int = 4) -> list:
    """A bundle of identical primers lying with their spines to us, seen a little from the right and above: rounded
    calf spines with a paper label, the page edges at the right end, marbled blue boards on top, tied crosswise with
    hemp twine. Returns the top face's corners (front left, front right, back right, back left)."""
    cx, base = 512, 780
    W, T = 370, 58
    vx, vy = 52, -112  # depth: the books run back up and to the right
    ends = []
    for k in range(n):
        y = base - (k + 1) * T
        sx = cx - W / 2 + (k % 2) * 8 - k * 3
        ends.append((sx, y))
        end = [(sx + W, y), (sx + W + vx, y + vy), (sx + W + vx, y + vy + T), (sx + W, y + T)]
        em = ob.poly_mask(end)
        ob.fill(em, "#efe2c0", "#a68e64", (sx + W, sx + W + vx), vertical=False, noise=0.06)
        ob.overlay(lambda d, sx=sx, y=y: [d.line([(sx + W, y + t), (sx + W + vx, y + vy + t)], fill=(130, 108, 76, 140),
                                                  width=2) for t in np.arange(10, T - 8, 6)], em)
        for t, col in ((0, "#5a7086"), (T - 8, "#3a4c5c")):  # boards above and below the pages
            ob.fill(ob.poly_mask([(sx + W, y + t), (sx + W + vx, y + vy + t), (sx + W + vx, y + vy + t + 8),
                                  (sx + W, y + t + 8)]), col, col, noise=0.1)
        ob.overlay(lambda d, e=end: d.line(e + [e[0]], fill=EDGE, width=3))
        spine = ob.mask("rounded_rectangle", (sx, y, sx + W, y + T), radius=12)
        ob.fill(spine, "#9a5e38", "#3a1a0a", (y + T * 0.3, y + T), noise=0.1, chroma=0.05)
        ob.shade(ob.intersect(ob.mask("rectangle", (sx, y, sx + W, y + T * 0.3)), spine), (30, 12, 4), 0.25, blur=4)
        ob.shade(ob.intersect(ob.mask("rectangle", (sx, y + T * 0.28, sx + W, y + T * 0.44)), spine), (255, 228, 196),
                 0.32, blur=4)
        for bx in (sx + 34, sx + 46, sx + W - 46, sx + W - 34):  # gilt fillets near the ends
            ob.line([(bx, y + 8), (bx, y + T - 8)], 3, (226, 184, 96, 210))
        lx = cx + (k % 2) * 8 - k * 3
        ob.draw.ellipse((lx - 7, y + T / 2 - 7, lx + 7, y + T / 2 + 7), fill=(214, 172, 86, 255))  # gilt fleuron
        ob.overlay(lambda d, sx=sx, y=y: d.rounded_rectangle((sx, y, sx + W, y + T), radius=12, outline=EDGE, width=3))
    # top face of the uppermost book (marbled boards seen from above)
    sx, y = ends[-1]
    top = [(sx + 4, y + 2), (sx + W, y + 2), (sx + W + vx, y + vy + 2), (sx + vx + 4, y + vy + 2)]
    tm = ob.poly_mask(top)
    ob.fill(tm, "#7e96aa", "#34485a", radial=(sx + 60, y + vy, W), noise=0.16, chroma=0.08)
    for _ in range(46):  # marbling
        x, yy = ob.random.uniform(sx, sx + W + vx), ob.random.uniform(y + vy, y)
        r = ob.random.uniform(6, 20)
        ob.shade(ob.intersect(ob.mask("ellipse", (x - r * 1.6, yy - r * 0.5, x + r * 1.6, yy + r * 0.5)), tm),
                 ob.random.choice([(236, 226, 206), (24, 34, 54), (160, 96, 60)]), ob.random.uniform(0.12, 0.3), blur=2)
    ob.overlay(lambda d: d.line(top + [top[0]], fill=EDGE, width=3))
    # hemp twine: two loops down the spines and back over the top
    hemp, hemp_dk, hemp_lt = (150, 118, 70), (70, 50, 26), (236, 212, 160, 235)
    for tx in (cx - 110, cx + 104):
        path = [(tx, base + 2), (tx + 3, y + 2), (tx + 3 + vx * 0.9, y + 2 + vy * 0.9)]
        ob.line([(x + 3, yy + 2) for x, yy in path], 16, hemp_dk)
        ob.line(path, 13, hemp)
        ob.line([(x - 3, yy) for x, yy in path], 4, hemp_lt)
    mid = [(sx + 4 + vx * 0.5, y + 2 + vy * 0.5), (sx + W + vx * 0.5, y + 2 + vy * 0.5)]
    ob.line([(x, yy + 3) for x, yy in mid], 16, hemp_dk)
    ob.line(mid, 13, hemp)
    ob.line([(mid[0][0], mid[0][1] - 3), (mid[1][0], mid[1][1] - 3)], 4, hemp_lt)
    contour(ob)
    return top


def open_primer(ob: Icon) -> None:
    """An open primer from above: the alphabet page with a woodcut apple, syllables on the facing page."""
    cx, cy = 512, 512
    W, H = 420, 300
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    cover = ob.mask("rounded_rectangle", (x0 - 14, y0 - 10, x1 + 14, y1 + 22), radius=10)
    ob.fill(cover, "#6e8496", "#2a3846", radial=(x0, y0, W), noise=0.14)
    block = ob.mask("rectangle", (x0 + 4, y1 - 4, x1 - 4, y1 + 14))
    ob.fill(block, "#e4d4b0", "#9a8460", noise=0.06)
    fb, fs = font(SERIF_BOLD, 64), font(SERIF, 28)
    for side in (-1, 1):
        ts = np.linspace(0, 1, 24)
        top = [(cx + side * (4 + (W / 2 - 4) * t), y0 + 12 - 16 * t ** 1.5) for t in ts]
        bot = [(cx + side * (4 + (W / 2 - 4) * t), y1 - 2 * t) for t in ts[::-1]]
        page = ob.poly_mask(top + bot)
        ob.fill(page, "#f6eccc", "#c8b286", radial=(cx - W * 0.25, y0, W * 0.8), noise=0.06)
        pw, ph = int(W / 2 - 24), int(H - 24)
        px = int(cx + 16) if side > 0 else int(cx - 16 - pw)
        sheet = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheet)
        if side < 0:
            sd.rectangle((10, 10, 96, 104), outline=INK + (220,), width=3)  # woodcut frame with an apple
            sd.ellipse((26, 34, 82, 92), fill=(176, 50, 32, 230), outline=INK + (230,), width=3)
            sd.line([(54, 36), (60, 18)], fill=INK + (230,), width=4)
            sd.ellipse((60, 14, 82, 28), fill=(90, 120, 50, 220))
            for k in range(6):
                sd.line([(30 + k * 8, 92), (40 + k * 8, 100)], fill=INK + (120,), width=2)
            sd.text((150, 56), "Aa", font=fb, fill=INK + (240,), anchor="mm")
            sd.text((24, 160), "Bb Cc", font=font(SERIF_BOLD, 56), fill=INK + (235,), anchor="lm")
            sd.text((20, 232), "a b c d e f", font=fs, fill=INK + (225,), anchor="lm")
        else:
            for k, t in enumerate(("ab  eb  ib", "ob  ub", "ba  be  bi", "bo  bu", "ca  ce  ci")):
                sd.text((20, 30 + k * 48), t, font=fs, fill=INK + (225,), anchor="lm")
        sheet = sheet.filter(ImageFilter.GaussianBlur(0.6))
        paste_clipped(ob, sheet, (px, y0 + 14), page)
        g = ob.mask("rectangle", (cx - 50, y0 - 20, cx + 50, y1 + 10))
        ob.shade(ob.intersect(g, page), (60, 36, 14), 0.4, blur=20)
        ob.overlay(lambda d, p=top + bot: d.line(p + [p[0]], fill=(120, 96, 64, 200), width=3))
    contour(ob)


# ---------------------------------------------------------------- composition
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.9
    ic.grade["light"] = 0.12
    od = layer(SEED + 1)
    ordinance(od)
    seal(od, 512 - 150, 512 + 300, 54)
    oimg = turned(rim(od.image, 0.22, 20), -6, (430, 400))
    ic.image.alpha_composite(oimg)
    st = layer(SEED + 2)
    top = primer_stack(st)
    at = (548, 660)
    simg = turned(rim(st.image, 0.22, 20), 0, at)
    cast(ic, simg, 18, 18, 18, 0.55)
    ic.image.alpha_composite(simg)
    # the open primer stands propped open on the bundle, leaning back against the ordinance
    fl, fr, br, bl = [(x + at[0] - 512, y + at[1] - 512) for x, y in top]
    foot = ((fl[1] + bl[1]) / 2 + 8)
    op = layer(SEED + 3)
    open_primer(op)
    oimg2 = tip(rim(op.image, 0.18, 16), [(284, 352), (740, 352), (740, 684), (284, 684)],
                [(330, 400), (742, 392), (776, 640), (296, 650)])
    oimg2 = turned(oimg2, 3, (626 - 24, foot - 645 + 512))
    cast(ic, oimg2, 14, 14, 16, 0.55)
    ic.image.alpha_composite(oimg2)


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
