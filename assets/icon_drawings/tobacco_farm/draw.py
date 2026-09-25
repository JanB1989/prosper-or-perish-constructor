"""Tobacco Farm: an open curing barn with hands of cured leaves, broad-leaved tobacco in front.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/tobacco_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/tobacco_farm

Identity: the brown of cured leaf bundles hanging in tiers inside a tall timber barn against the
deep green of broad tobacco plants in the foreground; a packing hogshead at the bottom right.
Helpers ``leaf``, ``plant`` and ``bundle`` are local to this script.
"""

import math

import numpy as np

from eu5_building_pipeline.iconkit import Icon

SEED = 7
REFS = ("fiber_crops_farm", "farming_village", "fruit_orchard", "tobacco_plantation")

L, R = 210, 850  # barn walls
EAVE, RIDGE = 380, 226
BASE = 850
BAY = 120  # width of the boarded end bays
LEAF_EDGE = (26, 38, 14)

GREEN = ("#5c7e22", "#122604")
CURED = (("#c47e3a", "#6c3818"), ("#b06430", "#5e2e14"), ("#c89444", "#7a4c20"), ("#a45a2a", "#542a12"))


def _rot(pts, origin, ang):
    """Rotate local points (x across, y along) by ``ang`` radians and move them to ``origin``."""
    ox, oy = origin
    c, s = math.cos(ang), math.sin(ang)
    return [(ox + x * c - y * s, oy + x * s + y * c) for x, y in pts]


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
    # the half facing down/away is in shade: a fold along the midrib
    half = [tuple(p) for p in spine] + (side1 if flip_shade else side2)[::-1]
    ic.shade(ic.poly_mask(half), (10, 20, 5), 0.36)
    ic.line([tuple(p) for p in spine[:-3]], 4, rib)
    for k in (8, 14, 20):  # side veins
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
    for i in reversed(range(levels)):  # top leaves first, big lower leaves in front
        t = i / (levels - 1)
        y = base - h * (0.10 + 0.66 * t)
        ln = h * (0.60 - 0.30 * t)
        w = ln * 0.48
        spread = 10 + 40 * t
        leaf(ic, (x, y), 180 + spread, ln, w, droop=0.40 - 0.25 * t)
        leaf(ic, (x + 4, y - 8), -spread, ln, w, droop=0.40 - 0.25 * t, flip_shade=True)
    # one leaf turned towards the viewer, hanging down in front of the stalk
    leaf(ic, (x + 2, base - h * 0.34), 96, h * 0.30, h * 0.15, droop=0.05)


def bundle(ic: Icon, top, w: float, h: float, colors, ang_deg: float = 0) -> None:
    """A hand of cured leaves: three long leaves fanning down from a tied stem end at ``top``.

    ``ang_deg`` rotates the whole hand (0 = hanging straight down, 90 = lying pointing left).
    """
    cured = dict(colors=colors, rib=(70, 40, 18), vein=(78, 46, 20), edge=(40, 24, 12), droop=0)
    for off, f, fl in ((-11, 0.92, False), (11, 0.95, True), (0, 1.0, False)):
        leaf(ic, top, 90 + off + ang_deg, h * f, w * 0.70, flip_shade=fl, **cured)
    c, s = math.cos(math.radians(ang_deg)), math.sin(math.radians(ang_deg))
    tx, ty = top[0] - s * 6, top[1] + c * 6
    ic.ellipse((tx - 10, ty - 8, tx + 10, ty + 8), "#6a5236", "#3e2e1c", edge=3)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84
    mid = (L + R) / 2
    # louvred ridge vent, behind the roof
    vl, vr = mid - 100, mid + 100
    ic.rect((vl, RIDGE - 62, vr, RIDGE), "#3a2819", "#1f150e", edge=0)
    for x in np.arange(vl + 10, vr, 26):
        ic.line([(x, RIDGE - 58), (x, RIDGE)], 12, (120, 88, 58))
    ic.outline([(vl, RIDGE - 62), (vr, RIDGE - 62), (vr, RIDGE), (vl, RIDGE)])
    ic.poly([(vl - 20, RIDGE - 56), (vr + 20, RIDGE - 56), (vr - 5, RIDGE - 96), (vl + 5, RIDGE - 96)],
            "#94806a", "#5f4d3e")

    # main roof plane (weathered shingles) + ridge
    ic.tiles([(L - 36, EAVE + 12), (R + 36, EAVE + 12), (R - 4, RIDGE), (L + 4, RIDGE)], "#94745a", "#4e3a28",
             course=30, stagger=38)
    ic.rect((L, RIDGE - 14, R, RIDGE + 6), "#86705a", "#5a4838")
    # light from the upper left: the right end of the roof falls off
    ic.shade(ic.poly_mask([(mid + 120, RIDGE - 20), (R + 60, RIDGE - 20), (R + 60, EAVE + 20), (mid + 160, EAVE + 20)]),
             alpha=0.18, blur=60)

    # walls: dark interior, boarded end bays, open middle bay with tiers of curing leaves
    top = EAVE + 12
    ic.rect((L, top, R, BASE), "#3a2819", "#1c130c", edge=0)
    for x0, x1 in ((L, L + BAY), (R - BAY, R)):
        x = x0 + 8
        while x < x1 - 8:
            ic.rect((x, top, min(x + 26, x1), BASE), "#8e603c", "#4e321e", noise=0.2, edge=4)
            x += 36
    open_l, open_r = L + BAY, R - BAY
    for k, y in enumerate((top + 34, top + 180, top + 326)):
        ic.beam((open_l, y), (open_r, y), 14, (96, 66, 42))
        xs = np.linspace(open_l + 30, open_r - 30, 9)
        for j, x in enumerate(xs):
            c = CURED[(j + k * 2) % len(CURED)]
            bundle(ic, (x + ic.random.uniform(-3, 3), y + 2), 56, 124 + ic.random.uniform(-8, 8), c)
    # bundles also hang outside on poles along the boarded bays
    for x0 in (L, R - BAY):
        ic.beam((x0 + 4, top + 34), (x0 + BAY - 4, top + 34), 12, (96, 66, 42))
        for j, x in enumerate(np.linspace(x0 + 32, x0 + BAY - 32, 2)):
            bundle(ic, (x, top + 36), 52, 118, CURED[(j + 1) % len(CURED)])
    ic.shade(ic.mask("rectangle", (L, top, R, top + 60)), alpha=0.45, blur=12)
    for x in (L + 10, open_l, open_r, R - 10):
        ic.beam((x, top), (x, BASE), 24)
    ic.rect((L - 12, BASE - 18, R + 12, BASE + 8), "#6b4a31", "#4a3120")
    ic.outline([(L, top), (R, top), (R, BASE), (L, BASE)])

    # packing prop, bottom right: a tobacco hogshead with cured hands lying on and before it
    ic.barrel(862, 790, 992, 972)
    bundle(ic, (990, 770), 46, 110, CURED[1], ang_deg=78)
    bundle(ic, (1010, 950), 50, 124, CURED[2], ang_deg=84)

    # tobacco field in the foreground: soil strip, back row, front row
    ic.ground([(40, 920), (640, 920), (660, 990), (20, 990)], "#6e5436", "#4f3c27")
    for x in (240, 440):
        plant(ic, x, 920, 250, flowers=True)
    for x in (150, 340, 540):
        plant(ic, x, 988, 300)
    # ground shadow among the lower leaves
    ic.shade(ic.mask("rectangle", (0, 905, 700, 1024)), (10, 18, 4), alpha=0.35, blur=24)
