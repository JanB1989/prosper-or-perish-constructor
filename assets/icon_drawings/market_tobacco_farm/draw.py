"""Market Tobacco Farm: a tall curing barn hung with cured leaf, a packing lean-to with marked
hogsheads, pressed bales of leaf ready for market, broad-leaved tobacco in front.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/market_tobacco_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/market_tobacco_farm

Identity: the Tobacco Farm's barn of hanging brown leaf, now taller with a tiled roof and louvred
vent, plus a packing lean-to of branded hogsheads and a stack of corded leaf bales at the bottom
right: tier 1 of the tobacco chain, the same leaf and palette with more structure and goods.

Local helpers: ``leaf``, ``plant``, ``bundle`` (from tobacco_farm), ``tint``, ``shingles`` (from
cookshop), ``bale`` (pressed leaf bale with a burlap top and cords), ``hogshead`` (standing cask
with a branded head).
"""

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 41
REFS = ("tobacco_plantation", "fiber_crops_farm", "market_village", "farming_village")

L, R = 150, 650  # barn walls
EAVE, RIDGE = 350, 176
BASE = 842
BAY = 96
LEAF_EDGE = (26, 38, 14)

GREEN = ("#5c7e22", "#122604")
CURED = (("#c47e3a", "#6c3818"), ("#b06430", "#5e2e14"), ("#c89444", "#7a4c20"), ("#a45a2a", "#542a12"))


def leaf(ic: Icon, base, ang_deg: float, length: float, width: float, droop: float = 0.25,
         colors=GREEN, flip_shade: bool = False, rib=(92, 114, 44), vein=(26, 42, 12),
         edge=LEAF_EDGE) -> None:
    """Broad pointed tobacco leaf from ``base`` towards ``ang_deg`` (0 = right, 90 = down), tip droops."""
    a = math.radians(ang_deg)
    d = np.array([math.cos(a), math.sin(a)])
    n = np.array([-d[1], d[0]])
    b = np.array(base, float)
    ts = np.linspace(0, 1, 28)
    spine = [b + d * length * t + np.array([0, droop * length * t * t]) for t in ts]
    hw = [width / 2 * math.sin(math.pi * t ** 0.75) for t in ts]
    side1 = [tuple(p + n * w) for p, w in zip(spine, hw)]
    side2 = [tuple(p - n * w) for p, w in zip(spine, hw)]
    pts = side1 + side2[::-1]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(ic.poly_mask(pts), colors[0], colors[1],
            radial=(min(xs) + 0.2 * (max(xs) - min(xs)), min(ys), max(length, 1) * 1.1), noise=0.22)
    half = [tuple(p) for p in spine] + (side1 if flip_shade else side2)[::-1]
    ic.shade(ic.poly_mask(half), (10, 20, 5), 0.36)
    ic.line([tuple(p) for p in spine[:-3]], 4, rib)
    for k in (8, 14, 20):
        p = spine[k]
        for sgn in (1, -1):
            q = p + n * sgn * hw[k] * 0.8 + d * length * 0.08
            ic.line([tuple(p), tuple(q)], 3, vein)
    ic.outline(pts, 4, edge)


def plant(ic: Icon, x: float, base: float, h: float, flowers: bool = False) -> None:
    """Tobacco plant: stalk with pairs of long pointed leaves, large and spreading at the bottom."""
    ic.line([(x, base), (x + 4, base - h)], 12, (44, 62, 24))
    ic.line([(x, base), (x + 4, base - h)], 6, (96, 120, 56))
    if flowers:
        for dx, dy in ((-16, -14), (0, -26), (16, -14), (-6, -4), (10, -2)):
            ic.line([(x + 4, base - h + 6), (x + 4 + dx, base - h + dy)], 3, (70, 90, 40))
            ic.ellipse((x + 4 + dx - 8, base - h + dy - 9, x + 4 + dx + 8, base - h + dy + 7), "#dcaaa4", "#a8706c",
                       edge=3)
    levels = 4
    for i in reversed(range(levels)):
        t = i / (levels - 1)
        y = base - h * (0.10 + 0.66 * t)
        ln = h * (0.60 - 0.30 * t)
        w = ln * 0.48
        spread = 10 + 40 * t
        leaf(ic, (x, y), 180 + spread, ln, w, droop=0.40 - 0.25 * t)
        leaf(ic, (x + 4, y - 8), -spread, ln, w, droop=0.40 - 0.25 * t, flip_shade=True)
    leaf(ic, (x + 2, base - h * 0.34), 96, h * 0.30, h * 0.15, droop=0.05)


def bundle(ic: Icon, top, w: float, h: float, colors, ang_deg: float = 0) -> None:
    """A hand of cured leaves: three long leaves fanning down from a tied stem end at ``top``."""
    cured = dict(colors=colors, rib=(70, 40, 18), vein=(78, 46, 20), edge=(40, 24, 12), droop=0)
    for off, f, fl in ((-11, 0.92, False), (11, 0.95, True), (0, 1.0, False)):
        leaf(ic, top, 90 + off + ang_deg, h * f, w * 0.70, flip_shade=fl, **cured)
    c, s = math.cos(math.radians(ang_deg)), math.sin(math.radians(ang_deg))
    tx, ty = top[0] - s * 6, top[1] + c * 6
    ic.ellipse((tx - 10, ty - 8, tx + 10, ty + 8), "#6a5236", "#3e2e1c", edge=3)


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles, each with its own tone, courses shading the one below (from cookshop)."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
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
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def bale(ic: Icon, x0: float, y0: float, x1: float, y1: float, color=("#a8845a", "#4a3420")) -> None:
    """Pressed bale of cured leaf sewn into burlap: a bulging pillow lit on its top, corded twice,
    brown leaf tips poking out of the open left end."""
    rnd = ic.random
    w, h = x1 - x0, y1 - y0
    ts = np.linspace(0, 1, 16)
    top = [(x0 + w * t, y0 - 10 * math.sin(math.pi * t)) for t in ts]
    right = [(x1 + 12 * math.sin(math.pi * t), y0 + h * t) for t in ts]
    bot = [(x1 - w * t, y1 + 4 * math.sin(math.pi * t)) for t in ts]
    left = [(x0 - 10 * math.sin(math.pi * t), y1 - h * t) for t in ts]
    pts = top + right + bot + left
    m = ic.poly_mask(pts)
    for k, (dx, ang) in enumerate(((-4, 196), (4, 170), (0, 184))):  # leaf tips out of the left end
        leaf(ic, (x0 + 18, y0 + h * (0.3 + 0.2 * k)), ang, 76, 34, droop=0.1, colors=CURED[k],
             rib=(70, 40, 18), vein=(78, 46, 20), edge=(40, 24, 12))
    ic.fill(m, color[0], color[1], radial=(x0 + w * 0.2, y0 - 10, w * 1.05), noise=0.28, chroma=0.1)
    tint(ic, ic.mask("ellipse", (x0 + 6, y0 - 12, x1 - 6, y0 + h * 0.34)), m, (255, 244, 214), 0.22, 8)
    tint(ic, ic.mask("rectangle", (x0 - 20, y1 - h * 0.3, x1 + 20, y1 + 10)), m, (30, 18, 8), 0.35, 10)

    def weave(dr):
        for y in np.arange(y0 - 10, y1 + 6, 9):
            dr.line([(x0 - 12, y), (x1 + 12, y + rnd.uniform(-2, 2))], fill=(60, 44, 24, 30), width=2)
        for x in np.arange(x0 - 10, x1 + 12, 11):
            dr.line([(x, y0 - 12), (x + rnd.uniform(-2, 2), y1 + 6)], fill=(250, 230, 190, 16), width=2)

    ic.overlay(weave, m)
    ic.line([tuple(p) for p in top[2:-2]], 3, (90, 66, 40, 150))  # seam along the top
    for f in (0.3, 0.7):
        cx = x0 + w * f
        ic.line([(cx, y0 - 10 * math.sin(math.pi * f) + 2), (cx - 3, y0 + h * 0.5), (cx, y1 + 2)], 9, (58, 42, 24))
        ic.line([(cx - 2, y0 - 10 * math.sin(math.pi * f) + 4), (cx - 5, y0 + h * 0.5)], 3, (196, 166, 110, 150))
    ic.outline(pts, 4, (40, 28, 16, 190))


def hogshead(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Standing tobacco hogshead with a branded head: a dark burnt mark on the staves."""
    ic.barrel(x0, y0, x1, y1)
    cx, cy = (x0 + x1) / 2, y0 + (y1 - y0) * 0.5
    ic.overlay(lambda dr: (dr.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=(40, 20, 8, 170), width=6),
                           dr.line([(cx - 12, cy), (cx + 12, cy)], fill=(40, 20, 8, 170), width=6),
                           dr.line([(cx, cy - 12), (cx, cy + 12)], fill=(40, 20, 8, 170), width=6)))


def barn(ic: Icon) -> None:
    mid = (L + R) / 2
    # louvred ridge vent
    vl, vr = mid - 80, mid + 80
    ic.rect((vl, RIDGE - 58, vr, RIDGE), "#3a2819", "#1f150e", edge=0)
    for x in np.arange(vl + 10, vr, 24):
        ic.line([(x, RIDGE - 54), (x, RIDGE)], 11, (120, 88, 58))
    ic.outline([(vl, RIDGE - 58), (vr, RIDGE - 58), (vr, RIDGE), (vl, RIDGE)])
    shingles(ic, [(vl - 20, RIDGE - 52), (vr + 20, RIDGE - 52), (vr - 5, RIDGE - 92), (vl + 5, RIDGE - 92)],
             "#b06a4a", "#6a3422", course=20, stagger=30, edge=5)
    # tiled main roof
    shingles(ic, [(L - 34, EAVE + 12), (R + 34, EAVE + 12), (R - 4, RIDGE), (L + 4, RIDGE)], "#c0704a", "#62301e",
             course=30, stagger=40)
    ic.rect((L, RIDGE - 14, R, RIDGE + 6), "#9a5e42", "#5a3020")
    # walls: dark interior, boarded end bays, open middle with tiers of curing leaves
    top = EAVE + 12
    ic.rect((L, top, R, BASE), "#3a2819", "#1c130c", edge=0)
    for x0, x1 in ((L, L + BAY), (R - BAY, R)):
        x = x0 + 8
        while x < x1 - 8:
            ic.rect((x, top, min(x + 26, x1), BASE), "#8e603c", "#4e321e", noise=0.2, edge=4)
            x += 36
    open_l, open_r = L + BAY, R - BAY
    for k, y in enumerate((top + 30, top + 176, top + 322)):
        ic.beam((open_l, y), (open_r, y), 14, (96, 66, 42))
        for j, x in enumerate(np.linspace(open_l + 28, open_r - 28, 7)):
            c = CURED[(j + k * 2) % len(CURED)]
            bundle(ic, (x + ic.random.uniform(-3, 3), y + 2), 54, 122 + ic.random.uniform(-8, 8), c)
    for x0 in (L, R - BAY):
        ic.beam((x0 + 4, top + 30), (x0 + BAY - 4, top + 30), 12, (96, 66, 42))
        bundle(ic, (x0 + BAY / 2, top + 32), 52, 116, CURED[1])
    ic.shade(ic.mask("rectangle", (L, top, R, top + 60)), alpha=0.45, blur=12)
    for x in (L + 10, open_l, open_r, R - 10):
        ic.beam((x, top), (x, BASE), 24)
    ic.rect((L - 12, BASE - 18, R + 12, BASE + 8), "#6b4a31", "#4a3120")
    ic.outline([(L, top), (R, top), (R, BASE), (L, BASE)])


def lean_to(ic: Icon) -> None:
    """Packing lean-to against the barn's right wall: shingled roof on posts, hogsheads and a
    sorting table with hands of leaf inside."""
    x0, x1 = R, 980
    ytop, ylow = 470, 560
    ic.rect((x0, ytop, x1, BASE), "#35281c", "#17110b", edge=0)

    def slats(dr):
        for x in np.arange(x0 + 10, x1, 30):
            dr.line([(x + ic.random.uniform(-3, 3), ytop), (x, BASE)], fill=(90, 70, 50, 60), width=4)

    ic.overlay(slats)
    # sorting table with leaf hands laid out
    ic.rect((x0 + 20, 700, x0 + 200, 718), "#a07850", "#5e4028", edge=4)
    for lx in (x0 + 34, x0 + 186):
        ic.rect((lx - 7, 718, lx + 7, 800), "#6a4a2e", "#38261a", vertical=False, edge=3)
    for k, x in enumerate((x0 + 40, x0 + 92, x0 + 144)):
        bundle(ic, (x, 694), 40, 76, CURED[k % 4], ang_deg=86)
    hogshead(ic, 872, 616, 968, 790)
    ic.shade(ic.mask("rectangle", (x0, ytop, x1, ytop + 90)), alpha=0.45, blur=14)
    for x in (x1 - 12,):
        ic.beam((x, ylow), (x, BASE), 22)
    ic.outline([(x0, ytop), (x1, ytop), (x1, BASE), (x0, BASE)])
    shingles(ic, [(x0 - 6, ytop - 30), (x1 + 26, ylow - 34), (x1 + 34, ylow + 4), (x0 - 6, ytop + 14)], "#a4684a",
             "#5e3020", course=24, stagger=36, edge=6)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84

    lean_to(ic)
    barn(ic)
    # yard strip
    top = [(20, 926)] + [(x, 900 + rnd.uniform(-8, 8)) for x in np.linspace(80, 960, 12)] + [(1008, 924)]
    ic.poly(top + [(1010, 994), (520, 1004), (16, 996)], "#76583a", "#4c3824", noise=0.32, edge=3)

    # hogsheads rolled out for carting, a stack of bales, bottom right
    ic.shade(ic.mask("ellipse", (560, 950, 1016, 1004)), alpha=0.45, blur=10)
    hogshead(ic, 560, 790, 680, 972)
    bale(ic, 704, 874, 844, 976)
    bale(ic, 862, 880, 996, 980, ("#9c7c54", "#443220"))
    bale(ic, 780, 780, 924, 874, ("#b08c60", "#4e3822"))
    bundle(ic, (918, 770), 44, 96, CURED[2], ang_deg=80)

    # tobacco rows in front, left
    ic.ground([(30, 918), (520, 918), (540, 990), (20, 990)], "#6e5436", "#4f3c27")
    for x in (200, 400):
        plant(ic, x, 918, 240, flowers=True)
    for x in (110, 300, 490):
        plant(ic, x, 988, 290)
    ic.shade(ic.mask("rectangle", (0, 905, 560, 1024)), (10, 18, 4), alpha=0.35, blur=24)
