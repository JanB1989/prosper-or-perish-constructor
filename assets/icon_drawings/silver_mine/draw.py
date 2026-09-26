"""Silver Mine (silver_mine): a hand-cut adit in a grey hillside with pale silver veins, and a small
smelting hut beside it.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/silver_mine/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/silver_mine

Composition: a cool blue-grey outcrop on the left with white-silver veins and dark galena patches,
a low timber-set adit cut into it; on the right a rubble smelting hut under thatch with a squat
stone stack trailing smoke and a glowing furnace mouth; a heap of pale grey hand-sorted ore and a
basket of ore in front. The family's tier 1 (silver_mine_improved) grows this into a tiled saiger
works with a headframe.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 41
REFS = ("schwaz_mine", "local_smelters", "stone_quarry", "charcoal_maker")

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


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 1.0

    # ---- outcrop: the dominant mass, a low slab on the left and a tall broken shoulder behind the
    # adit, stepping down in ledges towards the hut
    outline = [(18, 905), (22, 790), (34, 748), (150, 730), (196, 736), (200, 690), (214, 660), (262, 650),
               (268, 590), (250, 560), (290, 540), (300, 470), (330, 452), (352, 400), (380, 388), (392, 340),
               (430, 330), (446, 344), (470, 316), (496, 330), (502, 392), (540, 398), (556, 440), (560, 470),
               (596, 478), (606, 540), (630, 560), (640, 640), (648, 905)]
    lit = [
        [(22, 790), (34, 748), (150, 730), (196, 736), (192, 760), (120, 756), (40, 792)],
        [(200, 690), (214, 660), (262, 650), (262, 674), (214, 686)],
        [(250, 560), (290, 540), (300, 470), (318, 474), (306, 548), (268, 582)],
        [(300, 470), (330, 452), (352, 400), (380, 388), (392, 340), (430, 330), (446, 344), (470, 316),
         (496, 330), (484, 354), (456, 348), (438, 368), (404, 364), (394, 402), (362, 422), (340, 466), (312, 488)],
        [(502, 392), (540, 398), (534, 416), (504, 412)],
        [(560, 470), (596, 478), (592, 496), (560, 490)],
        # sunlit block faces on the front
        [(330, 560), (380, 552), (376, 610), (334, 618)],
        [(160, 800), (196, 796), (196, 850), (164, 856)],
    ]
    darks = [
        [(496, 330), (502, 392), (504, 412), (490, 424), (486, 362)],
        [(540, 398), (556, 440), (560, 470), (548, 482), (540, 432)],
        [(596, 478), (606, 540), (630, 560), (640, 640), (648, 905), (606, 905), (614, 640), (598, 560)],
        [(310, 520), (380, 490), (460, 486), (530, 504), (560, 522), (520, 542), (450, 522), (370, 534)],
        [(40, 804), (120, 776), (196, 784), (198, 816), (120, 810), (40, 836)],
        [(196, 740), (210, 694), (232, 740), (220, 905), (196, 905)],
        [(262, 650), (268, 590), (286, 600), (280, 660)],
        [(376, 552), (420, 556), (416, 616), (376, 610)],
    ]
    crevices = [
        [(262, 676), (270, 676), (258, 760), (250, 820), (242, 820), (252, 750)],
        [(560, 560), (570, 562), (582, 650), (576, 720), (568, 720), (572, 650)],
        [(420, 380), (430, 382), (424, 450), (414, 460)],
        [(110, 830), (118, 830), (124, 900), (114, 900)],
        [(496, 600), (504, 600), (500, 690), (492, 690)],
    ]
    strata = [(446, 330, 520, -0.04), (560, 300, 640, 0.05), (626, 200, 640, -0.03), (700, 200, 640, 0.04),
              (780, 20, 640, -0.03), (850, 20, 640, 0.02)]
    crag(ic, outline, lit, darks, crevices, strata)
    # a separate fallen boulder at the slab foot
    ic.rock([(150, 905), (158, 858), (196, 840), (238, 852), (250, 905)], "#8a8074", "#4a423a", facets=2)

    # ---- silver veins: thin broken bright lines along the strata, galena spots beside them
    silver_vein(ic, [(214, 716), (250, 712), (284, 720), (316, 714), (352, 722), (384, 716)], gaps=(2,))
    silver_vein(ic, [(460, 600), (494, 606), (526, 600), (560, 610), (596, 604), (632, 612)], gaps=(3,))
    silver_vein(ic, [(30, 842), (66, 836), (100, 844), (140, 838), (176, 846)], gaps=(1,))
    silver_vein(ic, [(330, 500), (366, 494), (400, 500), (436, 492), (470, 498)], gaps=(1,))
    for x, y in ((300, 738), (340, 700), (512, 622), (584, 588), (120, 858), (420, 514)):
        ic.ellipse((x - 10, y - 7, x + 10, y + 7), GALENA, GALENA_DK, edge=0, noise=0.1)
    glints(ic, [(284, 720), (560, 610), (66, 836), (400, 500)], 6)
    # grass tufts on the ledges
    for gx, gy, gw in ((150, 718, 36), (456, 326, 30), (548, 436, 26)):
        ic.poly(ic.jitter(gx, gy, gw, 9, 7, 0.3), "#7e8a48", "#4a5428", edge=0)

    # ---- adit under the shoulder
    adit(ic, 318, 470, 640, 902)

    # ---- smelting hut on the right, smaller and lower than the rock
    hx0, hx1, eave, ridge, foot = 652, 1000, 706, 586, 902
    smoke(ic, [(718, 422, 30), (756, 382, 40), (806, 346, 48), (700, 462, 26)])
    stones(ic, (688, 486, 758, 640), "#a89a8a", "#6a5e54", course=28)
    ic.outline([(688, 486), (758, 486), (758, 640), (688, 640)], 6)
    ic.rect((678, 474, 768, 496), "#8e8278", "#5e544c", edge=6)
    ic.fill(ic.mask("ellipse", (694, 468, 752, 484)), "#1e1a18", "#0e0c0a", noise=0.05)
    ic.shade(ic.mask("rectangle", (734, 486, 758, 640)), alpha=0.35, blur=6)
    # walls
    stones(ic, (hx0 + 10, eave, hx1 - 14, foot), "#aa9e8c", "#6e6456", course=34)
    ic.outline([(hx0 + 10, eave), (hx1 - 14, eave), (hx1 - 14, foot), (hx0 + 10, foot)], 6)
    ic.shade(ic.mask("rectangle", (hx1 - 80, eave, hx1 - 14, foot)), alpha=0.28, blur=24)
    # thatch roof: straw streaks down the slope, darker eave band, dark underside
    roof = [(hx0 - 18, eave + 12), (hx1 + 14, eave + 12), (hx1 - 22, ridge), (hx0 + 28, ridge)]
    rm = thatch(ic, roof, "#b39662", "#5c4828", course=36)
    lay, d = layer()
    for k in range(26):
        t = (k + ic.random.uniform(0.1, 0.9)) / 26
        xt = hx0 + 28 + (hx1 - hx0 - 50) * t
        xb = hx0 - 18 + (hx1 - hx0 + 32) * t
        col = (255, 236, 190, 70) if k % 3 == 0 else (40, 26, 10, 90)
        d.line([(xt, ridge + ic.random.uniform(4, 30)), (xb, eave + 6)], fill=col, width=int(ic.random.uniform(4, 7)))
    composite(ic, lay, rm)
    ic.shade(ic.poly_mask([(hx0 - 18, eave - 14), (hx1 + 14, eave - 14), (hx1 + 14, eave + 12), (hx0 - 18, eave + 12)]),
             (40, 26, 10), 0.5, blur=3)
    ic.poly([(hx0 - 18, eave + 12), (hx1 + 14, eave + 12), (hx1 + 8, eave + 26), (hx0 - 12, eave + 26)],
            "#4e3a20", "#2e2212", edge=4, noise=0.2)
    ic.line([(hx0 + 28, ridge + 2), (hx1 - 22, ridge + 2)], 12, (74, 58, 34))
    ic.shade(ic.mask("rectangle", (hx0 + 10, eave + 26, hx1 - 14, eave + 80)), alpha=0.55, blur=12)
    # furnace mouth glowing inside an arched opening
    fx0, fx1, fy0 = 704, 812, 772
    ic.fill(ic.mask("ellipse", (fx0 - 20, fy0 - 20, fx1 + 20, fy0 + 96)), "#9a8e7c", "#5e5448", noise=0.2)
    ic.fill(ic.mask("rectangle", (fx0 - 20, fy0 + 38, fx1 + 20, foot)), "#9a8e7c", "#5e5448", noise=0.2)
    ic.fill(ic.mask("ellipse", (fx0, fy0, fx1, fy0 + 76)), "#2a1a12", "#120a06", noise=0.08)
    ic.fill(ic.mask("rectangle", (fx0, fy0 + 38, fx1, foot)), "#2a1a12", "#120a06", noise=0.08)
    ic.shade(ic.mask("ellipse", (fx0 - 10, fy0 + 50, fx1 + 10, foot + 40)), (255, 120, 40), 0.55, blur=18)
    flame(ic, 740, foot - 14, 50, 86, lean=-6)
    flame(ic, 778, foot - 12, 40, 66, lean=8)
    ic.fill(ic.mask("rectangle", (fx0 + 6, foot - 24, fx1 - 6, foot)), "#ffcf70", "#b84a18", noise=0.2)
    ic.shade(ic.mask("rectangle", (fx0 - 40, fy0 - 40, fx1 + 40, foot)), (255, 150, 60), 0.12, blur=30)
    # plank door
    ic.door(880, 790, 940, foot - 2, arched=False, surround=None)
    ic.shade(ic.mask("rectangle", (hx0 + 10, foot - 30, hx1 - 14, foot)), (30, 28, 20), 0.35, blur=10)

    # ---- ground apron
    apron = [(14, 968), (60, 900), (330, 892), (700, 896), (960, 900), (1004, 968)]
    ic.poly(apron, "#8a765e", "#524232", noise=0.3)
    ic.shade(ic.poly_mask([(310, 900), (480, 898), (500, 950), (290, 955)]), (40, 34, 30), 0.35, blur=10)

    # ---- pale ore heap, bottom centre-right, and a basket of ore bottom left
    ore_heap(ic, 460, 820, 985, 770, 44, 5)
    glints(ic, [(600, 810), (700, 870)], 6)
    basket_of_ore(ic, 60, 850, 220, 970)
    # pick leaning on the basket
    ic.line([(240, 978), (290, 790)], 18, DARK)
    ic.line([(240, 978), (290, 790)], 10, (140, 100, 62))
    ic.draw.arc((230, 752, 360, 836), 190, 330, fill=DARK + (255,), width=20)
    ic.draw.arc((230, 752, 360, 836), 192, 328, fill=IRON + (255,), width=12)
