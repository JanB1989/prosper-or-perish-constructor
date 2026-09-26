"""Saiger Silver Mine (silver_mine_improved): the silver mine grown into a saiger works, with a
tiled liquation hall beside the timbered adit.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/silver_mine_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/silver_mine_improved

Identity: the liquation hearth. A long ashlar hall under red tiles with a tall stack; its big front
arch shows copper-lead saiger cakes standing on edge on the sloping hearth over glowing charcoal,
molten lead running off into the gutter. On the left the grey outcrop with silver veins and a
railed adit, a laden mine cart on the rails; a stack of cakes and a small heap of pale ore in front.
Same rock, ore and timber palette as silver_mine (tier 0), with better materials and more plant.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 43
REFS = ("schwaz_mine", "local_smelters", "minting_office", "bog_iron_smelter")

ROCK, ROCK_DK = "#9c8e7e", "#463c36"
SILVER, SILVER_DK = "#d4d8da", "#6a7078"
GALENA, GALENA_DK = "#5c606a", "#24262c"
TIMBER = (112, 78, 50)
IRON = (46, 44, 46)
DARK = (28, 18, 12)


# ---------------------------------------------------------------- helpers (copied / new)
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines (from cookshop)."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay, d = layer()
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.8, 1.15)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.2, 2.5)
            j = lambda: rnd(-3, 3)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 55)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=5)
            x += w
        y += h
    composite(ic, lay, m)


def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: strands down the slope, layered courses, weathered blotches (from tavern)."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay, d = layer()
    shadow = Image.new("L", (SIZE, SIZE), 0)
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    composite(ic, lay, m)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    ic.outline(pts, 6)
    return m


def smoke(ic: Icon, puffs) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath (from cookshop)."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, "#dcd8d0", "#7e7a74", radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#ffb04a", "#c2401a"), inner=("#fff0c0", "#ffb449")) -> None:
    """Tongue of flame; the brighter inner tongue sits low in the outer one (from cookshop)."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (inner, 0.5, 0.62)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def glints(ic: Icon, pts, r: float = 7, color=(255, 255, 250)) -> None:
    """Small metallic sparkles: a bright dot with a short cross, blended (new)."""
    lay, d = layer()
    for x, y in pts:
        d.line([(x - r * 1.8, y), (x + r * 1.8, y)], fill=color + (150,), width=3)
        d.line([(x, y - r * 1.8), (x, y + r * 1.8)], fill=color + (150,), width=3)
        d.ellipse((x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7), fill=color + (235,))
    composite(ic, lay)


def adit(ic: Icon, x0: float, x1: float, top: float, base: float, sets: int = 3) -> None:
    """Timber-set adit: dark mouth, receding sets, two leaning front posts under a heavy cap."""
    w = x1 - x0
    mouth = [(x0, base), (x0 + w * 0.06, top), (x1 - w * 0.06, top), (x1, base)]
    ic.poly(mouth, "#26201c", "#0b0907", edge=0, noise=0.1)
    for k in range(sets):
        inset = w * (0.14 + 0.1 * k)
        t = top + (base - top) * (0.16 + 0.13 * k)
        col = tuple(int(c * (0.62 - 0.14 * k)) for c in TIMBER)
        bw = int(max(6, 16 - 4 * k))
        ic.beam((x0 + inset, base), (x0 + inset + 6, t), bw, col)
        ic.beam((x1 - inset, base), (x1 - inset - 6, t), bw, col)
        ic.beam((x0 + inset - 8, t), (x1 - inset + 8, t), bw, col)
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.3, blur=18)
    ic.beam((x0 - 8, base + 4), (x0 + w * 0.06 + 6, top - 8), 34, TIMBER)
    ic.beam((x1 + 8, base + 4), (x1 - w * 0.06 - 6, top - 8), 34, TIMBER)
    ic.shade(ic.poly_mask([(x0 + 20, top), (x1 - 20, top), (x1 - 20, top + 50), (x0 + 20, top + 50)]),
             alpha=0.5, blur=10)
    ic.rect((x0 - 36, top - 48, x1 + 36, top), "#8e603c", "#5a3c24")
    ic.line([(x0 - 34, top - 44), (x1 + 34, top - 44)], 4, (255, 226, 180, 90))
    for x in (x0 - 16, x1 + 16):
        ic.ellipse((x - 9, top - 33, x + 9, top - 15), "#4a4648", "#2c2a2c", edge=3)
    ic.shade(ic.poly_mask([(x0 - 6, top), (x0 + 10, top), (x0 - 2, base), (x0 - 22, base)]), (255, 240, 220), 0.18)


def ore_heap(ic: Icon, x0, x1, base, top, r, rows) -> None:
    """Heap of pale silver ore with dark galena lumps and a few sparkles."""
    ic.heap(x0, x1, base, top, r, rows, body=("#7a7c82", "#34363c"), lump=("#cdd0d2", "#5a5e66"),
            odd=(GALENA, GALENA_DK), odd_share=0.28)


def basket_of_ore(ic: Icon, x0, y0, x1, y1) -> None:
    w = x1 - x0
    for i, (fx, fy, fr) in enumerate(((0.22, -0.02, 0.2), (0.5, -0.1, 0.24), (0.78, -0.01, 0.19), (0.36, 0.06, 0.16),
                                      (0.64, 0.07, 0.17))):
        colors = (GALENA, GALENA_DK) if i == 2 else ("#d2d4d4", "#5c6068")
        ic.chunk(x0 + w * fx, y0 + w * fy, w * fr, *colors, glint=(255, 255, 255))
    ic.basket(x0, y0, x1, y1)

def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles with per-tile tone and course shadows (from cookshop)."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow = Image.new("L", (SIZE, SIZE), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = min(ys), 0
    while y < max(ys):
        off = (k % 2) * stagger / 2 + rnd(-6, 6)
        x = min(xs) - stagger + off
        while x < max(xs):
            w = stagger * rnd(0.85, 1.15)
            q = [(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + course), (x + 2, y + course)]
            t = rnd(-1, 1)
            td.polygon(q, fill=(20, 10, 6, int(-t * 60)) if t < 0 else (255, 236, 210, int(t * 40)))
            td.line([(x + w - 2, y + 6), (x + w - 2, y + course - 2)], fill=(40, 22, 14, 90), width=3)
            x += w
        yl = y + course + rnd(-2, 2)
        td.line([(0, yl - 4), (SIZE, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (SIZE, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    composite(ic, tone, m)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def crag(ic: Icon, outline, lit, darks, crevices, strata, base="#88786a", dark="#443a32") -> Image.Image:
    """Blocky stratified rock mass: mid-tone front, lit top-left ledge faces, dark undersides and
    crevices, horizontal strata bands and warm ochre staining; no outline lines on the facets."""
    m = ic.poly_mask(outline)
    ys = [p[1] for p in outline]
    ic.fill(m, base, dark, (min(ys), max(ys)), noise=0.24, chroma=0.06)
    with ic.clipped(m):
        # strata: a light top edge and a dark bottom edge per band, wobbling and broken
        lay, d = layer()
        rnd = ic.random.uniform
        for y, x0, x1, tilt in strata:
            x = x0
            while x < x1:
                seg = rnd(70, 170)
                ya, yb = y + tilt * (x - x0), y + tilt * (x + seg - x0) + rnd(-6, 6)
                d.line([(x, ya), (x + seg, yb)], fill=(255, 238, 210, 70), width=7)
                d.line([(x, ya + 12), (x + seg, yb + 12)], fill=(24, 18, 14, 95), width=9)
                x += seg + rnd(6, 30)
        for k in range(len(strata) - 1):
            ya, yb = sorted((strata[k][0], strata[k + 1][0]))
            x = strata[k][1] + rnd(10, 60)
            while x < strata[k][2]:
                sl = rnd(-12, 12)
                if ic.random.random() < 0.6:
                    yt = ya + 14 + rnd(0, (yb - ya) * 0.3)
                    d.line([(x, yt), (x + sl, yb)], fill=(20, 16, 12, 110), width=6)
                    d.line([(x + 7, yt), (x + 7 + sl, yb)], fill=(255, 238, 210, 45), width=5)
                x += rnd(100, 210)
        composite(ic, lay, m)
        # warm ochre / rust staining
        for (cx, cy, rx, ry, a) in ((150, 800, 90, 40, 0.4), (430, 580, 110, 50, 0.34), (560, 700, 60, 130, 0.42),
                                    (330, 440, 60, 30, 0.3), (250, 740, 50, 90, 0.34), (470, 780, 60, 60, 0.3)):
            ic.shade(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), (156, 98, 44), a, blur=26)
        for pts in lit:
            ic.shade(ic.poly_mask(pts), (255, 240, 212), 0.46, blur=3)
        for pts in darks:
            ic.shade(ic.poly_mask(pts), (18, 14, 12), 0.6, blur=4)
        for pts in crevices:
            ic.shade(ic.poly_mask(pts), (10, 8, 6), 0.72, blur=2)
        # darker foot and a dark rim towards the bottom-right edges
        ic.shade(ic.mask("rectangle", (0, 800, 1024, 1024)), (30, 24, 20), 0.35, blur=30)
        rim = ImageChops.subtract(m, ImageChops.offset(m, -14, -14))
        ic.shade(rim, (14, 10, 8), 0.4, blur=6)
        top = ImageChops.subtract(m, ImageChops.offset(m, 10, 12))
        ic.shade(top, (255, 244, 220), 0.22, blur=3)
    ic.outline(outline, 6)
    return m


def silver_vein(ic: Icon, pts, gaps=()) -> None:
    """Thin, broken, zig-zag bright vein with a dark selvage; ``gaps`` are skipped segment indices."""
    for i in range(len(pts) - 1):
        if i in gaps:
            continue
        seg = [pts[i], pts[i + 1]]
        ic.line(seg, 16, (40, 36, 38, 170))
    for i in range(len(pts) - 1):
        if i in gaps:
            continue
        seg = [pts[i], pts[i + 1]]
        ic.line(seg, 8, (222, 228, 232))
        ic.line([(seg[0][0], seg[0][1] - 2), (seg[1][0], seg[1][1] - 2)], 3, (255, 255, 255, 200))


def cake_edge(ic: Icon, x, y, lean: float, h: float = 96, rx: float = 17, thick: float = 14) -> None:
    """Saiger cake: a thick copper-lead disc standing on its edge at (x, y), leaning by ``lean`` degrees
    and turned almost edge-on; dark copper-brown, lit copper rim upper left, hot orange rim at the
    bottom only (new)."""
    ry = h / 2
    ang = np.linspace(0, 2 * math.pi, 48, endpoint=False)

    def disc(dx):
        return ic.rotate([(dx + math.cos(a) * rx, -ry + math.sin(a) * ry) for a in ang], (x, y), lean)

    for dx in np.arange(thick, 0, -3):
        ic.fill(ic.poly_mask(disc(dx)), "#3a2216", "#140a06", noise=0.1)
    face = disc(0)
    fm = ic.poly_mask(face)
    ic.fill(fm, "#74462e", "#28140c", radial=(x - rx, y - h, h * 1.1), noise=0.2)
    ic.overlay(lambda d: d.line(disc(0)[26:40], fill=(236, 170, 116, 170), width=4))
    low = ic.poly_mask(ic.rotate([(-60, -h * 0.24), (60, -h * 0.24), (60, 10), (-60, 10)], (x, y), lean))
    ic.shade(ic.intersect(low, fm), (255, 124, 36), 0.85, blur=3)
    low2 = ic.poly_mask(ic.rotate([(-60, -h * 0.1), (60, -h * 0.1), (60, 10), (-60, 10)], (x, y), lean))
    ic.shade(ic.intersect(low2, fm), (255, 214, 120), 0.6)
    ic.outline(face, 4, (26, 12, 6, 230))


def pig(ic: Icon, x0, y0, x1, y1) -> None:
    """Dull lead-grey pig (cast bar) seen from the front and slightly above (new)."""
    w = x1 - x0
    ic.poly([(x0, y1), (x0 + w * 0.08, y0 + 10), (x1 - w * 0.08, y0 + 10), (x1, y1)], "#7e8084", "#3a3c42",
            noise=0.16, edge=4)
    ic.poly([(x0 + w * 0.08, y0 + 10), (x0 + w * 0.14, y0), (x1 - w * 0.14, y0), (x1 - w * 0.08, y0 + 10)],
            "#a2a4a8", "#80848a", noise=0.12, edge=3)
    ic.shade(ic.mask("rectangle", (x1 - w * 0.25, y0, x1, y1)), alpha=0.3, blur=6)


def silver_cake(ic: Icon, cx, cy, rx, ry) -> None:
    """Refined silver cake: bright domed top with a crisp specular highlight on a shallow rim (new)."""
    ic.fill(ic.mask("ellipse", (cx - rx, cy - ry + 14, cx + rx, cy + ry + 14)), "#8a9096", "#3c4046", noise=0.1)
    ic.fill(ic.mask("rectangle", (cx - rx, cy, cx + rx, cy + 14)), "#8a9096", "#3c4046", vertical=False, noise=0.1)
    ang = np.linspace(math.pi, 2 * math.pi, 40)
    dome = [(cx + math.cos(a) * rx, cy + math.sin(a) * ry * 1.9) for a in ang]
    dome += [(cx + math.cos(a) * rx, cy + math.sin(a) * ry * 0.7) for a in np.linspace(0, math.pi, 30)[1:-1]]
    ic.fill(ic.poly_mask(dome), "#fbfcfc", "#8e969e", radial=(cx - rx * 0.35, cy - ry * 1.2, rx * 1.9), noise=0.06,
            chroma=0.02)
    ic.outline(dome, 4, (40, 36, 40, 220))
    ic.ellipse((cx - rx * 0.46, cy - ry * 1.46, cx - rx * 0.1, cy - ry * 1.1), "#ffffff", "#ffffff", edge=0, noise=0)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 1.0

    # ---- outcrop with a railed adit on the left: same stratified, faceted rock as silver_mine
    outline = [(20, 905), (24, 800), (40, 760), (110, 744), (150, 748), (156, 700), (170, 672), (214, 664),
               (220, 610), (206, 586), (246, 566), (254, 512), (284, 496), (300, 462), (334, 452), (346, 474),
               (378, 470), (392, 520), (420, 528), (430, 580), (452, 596), (470, 640), (478, 905)]
    lit = [
        [(24, 800), (40, 760), (110, 744), (150, 748), (146, 768), (90, 770), (40, 796)],
        [(156, 700), (170, 672), (214, 664), (212, 684), (170, 694)],
        [(206, 586), (246, 566), (254, 512), (270, 512), (262, 570), (222, 600)],
        [(254, 512), (284, 496), (300, 462), (334, 452), (346, 474), (378, 470), (372, 488), (340, 490),
         (320, 478), (300, 500), (270, 520)],
        [(392, 520), (420, 528), (414, 544), (394, 538)],
        [(430, 580), (452, 596), (446, 612), (430, 602)],
        [(280, 600), (330, 594), (326, 648), (284, 652)],
    ]
    darks = [
        [(378, 470), (392, 520), (394, 538), (380, 542), (374, 500)],
        [(420, 528), (430, 580), (420, 592), (414, 546)],
        [(452, 596), (470, 640), (478, 905), (446, 905), (452, 650), (440, 612)],
        [(240, 612), (300, 562), (380, 556), (430, 590), (380, 602), (300, 604)],
        [(24, 812), (100, 788), (150, 792), (152, 820), (100, 818), (24, 842)],
        [(150, 752), (160, 706), (180, 752), (170, 905), (150, 905)],
        [(206, 586), (222, 600), (220, 664), (212, 664)],
    ]
    crevices = [
        [(214, 690), (222, 690), (212, 780), (204, 780)],
        [(400, 620), (408, 620), (410, 720), (402, 720)],
        [(80, 836), (88, 836), (92, 900), (84, 900)],
        [(318, 482), (326, 482), (320, 540), (312, 540)],
    ]
    strata = [(530, 254, 390, -0.04), (620, 160, 470, 0.04), (700, 24, 470, -0.03), (780, 24, 470, 0.03),
              (850, 24, 470, -0.02)]
    crag(ic, outline, lit, darks, crevices, strata)
    silver_vein(ic, [(262, 540), (296, 534), (330, 542), (366, 536), (398, 546)], gaps=(2,))
    silver_vein(ic, [(392, 770), (420, 762), (450, 772), (474, 766)], gaps=())
    silver_vein(ic, [(28, 776), (62, 770), (98, 778), (136, 772)], gaps=(1,))
    for x, y in ((310, 556), (430, 786), (80, 792), (360, 520)):
        ic.ellipse((x - 10, y - 7, x + 10, y + 7), GALENA, GALENA_DK, edge=0, noise=0.1)
    glints(ic, [(296, 534), (420, 762), (98, 778)], 6)
    for gx, gy, gw in ((110, 746, 30), (330, 456, 28)):
        ic.poly(ic.jitter(gx, gy, gw, 9, 7, 0.3), "#7e8a48", "#4a5428", edge=0)
    adit(ic, 232, 356, 704, 902, sets=3)

    # ---- saiger hall
    hx0, hx1, eave, ridge, foot = 470, 1000, 584, 404, 902
    # tall stack at the left end, smoke bent sideways by the wind
    smoke(ic, [(784, 238, 36), (716, 226, 44), (652, 240, 42), (596, 268, 34)])
    stones(ic, (524, 300, 614, 600), "#9a7a66", "#5e4638", course=28)
    ic.outline([(524, 300), (614, 300), (614, 600), (524, 600)], 6)
    ic.rect((510, 284, 628, 312), "#8a6c5a", "#5a4234", edge=6)
    ic.fill(ic.mask("ellipse", (534, 278, 604, 296)), "#1e1a18", "#0e0c0a", noise=0.05)
    ic.shade(ic.mask("rectangle", (584, 312, 614, 600)), alpha=0.38, blur=6)
    # walls: dressed stone
    stones(ic, (hx0 + 12, eave, hx1 - 12, foot), "#b8a88e", "#7a6a56", course=34)
    ic.outline([(hx0 + 12, eave), (hx1 - 12, eave), (hx1 - 12, foot), (hx0 + 12, foot)], 6)
    ic.shade(ic.mask("rectangle", (hx1 - 100, eave, hx1 - 12, foot)), alpha=0.3, blur=26)
    ic.shade(ic.mask("rectangle", (hx0 + 12, eave, hx0 + 60, foot)), alpha=0.3, blur=16)
    # roof of red tiles
    shingles(ic, [(hx0 - 16, eave + 12), (hx1 + 14, eave + 12), (hx1 - 30, ridge), (hx0 + 40, ridge)],
             "#b06a4a", "#6a3424", course=30, stagger=40)
    ic.line([(hx0 + 40, ridge + 2), (hx1 - 30, ridge + 2)], 14, (92, 46, 32))
    ic.shade(ic.mask("rectangle", (hx0 + 12, eave + 12, hx1 - 12, eave + 60)), alpha=0.5, blur=12)
    # the stack rises through the roof: repaint its lower part over the tiles
    stones(ic, (524, 404, 614, 470), "#9a7a66", "#5e4638", course=28)
    ic.line([(524, 404), (524, 470)], 6, (40, 28, 20, 200))
    ic.line([(614, 404), (614, 470)], 6, (40, 28, 20, 200))
    ic.shade(ic.mask("rectangle", (584, 404, 614, 470)), alpha=0.38, blur=6)
    ic.shade(ic.poly_mask([(614, 470), (674, 470), (654, 404), (614, 404)]), alpha=0.35, blur=10)

    # ---- liquation hearth in a wide arch: a hearth plate sloping down to the left, saiger cakes
    # leaning in a row on it, a low band of glowing charcoal underneath, lead running out
    ax0, ax1, ay0 = 580, 890, 666
    aw = ax1 - ax0
    ic.fill(ic.mask("ellipse", (ax0 - 26, ay0 - 26, ax1 + 26, ay0 + 150)), "#a09078", "#6a5a48", noise=0.2)
    ic.fill(ic.mask("rectangle", (ax0 - 26, ay0 + 60, ax1 + 26, foot)), "#a09078", "#6a5a48", noise=0.2)
    for a in range(186, 356, 17):  # voussoirs
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        cx, cy = (ax0 + ax1) / 2, ay0 + 62
        ic.line([(cx + (aw / 2) * ca, cy + 62 * sa), (cx + (aw / 2 + 26) * ca, cy + 88 * sa)], 4, (50, 40, 30, 150))
    arch = union(ic.mask("ellipse", (ax0, ay0, ax1, ay0 + 124)), ic.mask("rectangle", (ax0, ay0 + 62, ax1, foot)))
    ic.fill(arch, "#2a1c16", "#0e0806", (ay0, foot), noise=0.08)
    slope = 0.21  # about 12 degrees, lower on the left

    def plate_y(x):
        return 858 - (x - ax0) * slope

    with ic.clipped(arch):
        # charcoal: a low glowing band just under the plate
        band = [(ax0, plate_y(ax0) + 22), (ax1, plate_y(ax1) + 22), (ax1, plate_y(ax1) + 62), (ax0, plate_y(ax0) + 62)]
        ic.fill(ic.poly_mask(band), "#ffa848", "#a8401a", noise=0.3)
        for x in np.arange(ax0 + 8, ax1, 26):
            ic.chunk(x + ic.random.uniform(-5, 5), plate_y(x) + 46 + ic.random.uniform(-3, 5), 14, "#4a3a34",
                     "#1a1210", glint=(255, 150, 60))
        ic.shade(ic.poly_mask([(ax0, plate_y(ax0) - 40), (ax1, plate_y(ax1) - 40), (ax1, plate_y(ax1) + 70),
                               (ax0, plate_y(ax0) + 70)]), (255, 120, 40), 0.35, blur=20)
        # sloping hearth plate
        ic.poly([(ax0 - 4, plate_y(ax0 - 4)), (ax1 + 4, plate_y(ax1 + 4)), (ax1 + 4, plate_y(ax1 + 4) + 22),
                 (ax0 - 4, plate_y(ax0 - 4) + 22)], "#6e5e50", "#3a3028", edge=4)
        # cakes leaning in a row, perpendicular to the plate plus a little lean
        for i, x in enumerate(np.linspace(ax0 + 46, ax1 - 64, 6)):
            cake_edge(ic, x, plate_y(x) + 2, 16 + 5 * ((i % 2) - 0.5), h=100)
        # molten lead: a bright trickle along the plate, off its low end and down to the arch foot
        lay, d = layer()
        path = [(ax0 + 110, plate_y(ax0 + 110) + 3), (ax0 + 30, plate_y(ax0 + 30) + 4),
                (ax0 + 18, plate_y(ax0 + 18) + 30), (ax0 + 26, foot + 4)]
        d.line(path, fill=(120, 124, 130, 255), width=14, joint="curve")
        d.line(path, fill=(236, 240, 242, 255), width=8, joint="curve")
        d.line([(p[0] - 2, p[1] - 3) for p in path], fill=(255, 255, 255, 220), width=3, joint="curve")
        composite(ic, lay)
    ic.shade(ic.mask("rectangle", (ax0 - 60, 760, ax1 + 60, foot)), (255, 150, 60), 0.08, blur=30)
    ic.window(930, 660, 970, 716)
    ic.shade(ic.mask("rectangle", (hx0 + 12, foot - 30, hx1 - 12, foot)), (30, 28, 20), 0.35, blur=10)

    # ---- ground, rails, cart, ore heap
    apron = [(20, 968), (60, 900), (330, 894), (700, 910), (960, 906), (1004, 968)]
    ic.poly(apron, "#8a765e", "#524232", noise=0.3)
    ic.shade(ic.poly_mask([(236, 900), (356, 900), (386, 950), (216, 955)]), (40, 34, 30), 0.35, blur=10)
    for y in (918, 944, 968):
        ic.line([(250 - (y - 902) * 0.9, y), (338 + (y - 902) * 0.3, y)], 9, (98, 70, 46))
    for x0, x1 in ((258, 186), (330, 356)):
        ic.line([(x0, 902), (x1, 976)], 10, (60, 56, 56))
        ic.line([(x0, 900), (x1, 972)], 4, (150, 146, 140))

    # lead gutter from the arch foot to a small pool in front
    gut = [(ax0 + 10, foot - 4), (ax0 + 44, foot - 4), (ax0 - 4, 950), (ax0 - 44, 950)]
    ic.poly(gut, "#8a7c6a", "#54483c", edge=5)
    lay, d = layer()
    d.line([(ax0 + 26, foot - 2), (ax0 - 22, 944)], fill=(236, 240, 242, 255), width=12)
    d.line([(ax0 + 24, foot - 4), (ax0 - 24, 942)], fill=(255, 255, 255, 230), width=4)
    composite(ic, lay)
    ic.ellipse((ax0 - 96, 928, ax0 + 10, 972), "#6e6254", "#40362c", edge=5)
    ic.ellipse((ax0 - 84, 934, ax0 - 2, 964), "#f4f6f8", "#9aa2aa", noise=0.05, edge=0)
    ic.shade(ic.mask("ellipse", (ax0 - 70, 936, ax0 - 30, 948)), (255, 255, 255), 0.8)

    # mine cart (hund) laden with pale ore
    cx0, cx1, cy0, cy1 = 120, 290, 812, 912
    for i, (fx, fy, fr) in enumerate(((0.2, -0.02, 0.17), (0.45, -0.1, 0.21), (0.72, -0.03, 0.18), (0.32, 0.06, 0.14),
                                      (0.6, 0.05, 0.15))):
        colors = (GALENA, GALENA_DK) if i == 3 else ("#d2d4d4", "#5c6068")
        ic.chunk(cx0 + (cx1 - cx0) * fx, cy0 + (cx1 - cx0) * fy, (cx1 - cx0) * fr, *colors, glint=(255, 255, 255))
    ic.poly([(cx0 - 6, cy0), (cx1 + 6, cy0), (cx1 - 10, cy1), (cx0 + 10, cy1)], "#9a6e46", "#553a22", noise=0.2)
    for y in (cy0 + 30, cy0 + 62):
        ic.line([(cx0 + 2, y), (cx1 - 2, y)], 8, (52, 50, 52))
    ic.shade(ic.poly_mask([(cx0 - 6, cy0), (cx1 + 6, cy0), (cx1 + 4, cy0 + 12), (cx0 - 4, cy0 + 12)]),
             (255, 240, 220), 0.3)
    for wx in (cx0 + 36, cx1 - 36):
        ic.ellipse((wx - 26, cy1 - 20, wx + 26, cy1 + 32), "#5a5654", "#2a2826", edge=5)
        ic.ellipse((wx - 8, cy1 - 2, wx + 8, cy1 + 14), "#8a8480", "#4a4644", edge=3)

    ore_heap(ic, 356, 500, 985, 850, 32, 3)
    glints(ic, [(420, 890)], 5)

    # lead pigs bottom right, a domed silver cake on top
    for x0, y0 in ((748, 930), (832, 934), (914, 928)):
        pig(ic, x0, y0, x0 + 84, y0 + 40)
    for x0, y0 in ((790, 892), (872, 894)):
        pig(ic, x0, y0, x0 + 84, y0 + 40)
    ic.shade(ic.mask("ellipse", (780, 878, 970, 904)), alpha=0.35, blur=8)
    silver_cake(ic, 872, 886, 58, 22)
    glints(ic, [(846, 856)], 7)
