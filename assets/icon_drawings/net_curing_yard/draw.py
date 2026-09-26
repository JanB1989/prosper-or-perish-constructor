"""Net and Curing Yard (net_curing_yard): a shore yard with a smokehouse, fish flakes and drying nets.

Build: uv run eu5-building icon build --script <this file> --out <out_dir>

Identity: the thatched smokehouse with smoke rising from its ridge louvre and rows of golden smoked
fish in its open front, a drying rack of split fish, nets hung on tall poles behind, and a salting
table with white salt and casks. It stands on a shingle beach inside the fisheries' water band.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import LINE, SIZE

SEED = 37
REFS = ("fishing_village", "salt_collector", "tar_kiln", "dock")

WATER_TOP, WATER_BOTTOM, SAG = 690, 896, 32
WATER_LIGHT, WATER_DEEP = "#74b0c4", "#2c5c70"
BASE = 774  # where the buildings stand on the beach
WOOD = (118, 82, 52)
ROPE = (70, 52, 34)


# ---------------------------------------------------------------- helpers (candidates for the kit)
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


def rim_darken(ic: Icon, width: int = 22, alpha: float = 0.4) -> None:
    """Darken a soft band just inside the silhouette, like the dark rim vanilla icons have."""
    sil = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    inner = sil.filter(ImageFilter.MinFilter(2 * width + 1))
    ring = Image.fromarray(((np.asarray(sil) > 0) & (np.asarray(inner) == 0)).astype("uint8") * 255)
    ic.shade(ring, alpha=alpha, blur=6)


def thatch(ic: Icon, pts, c1, c2, course: float = 44, lean: float = 0.0) -> Image.Image:
    """Thatched roof plane: straw strands down the slope, layered courses, weathered blotches."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    shadow = Image.new("L", (ic.size, ic.size), 0)
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
            d.line([(x, y0), (x + lean * ln + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col, rnd(0.08, 0.2), 18)
    return m


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, w - 4)
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def smoke(ic: Icon, puffs) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, "#e8e4dc", "#8e8a84", radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def cask(ic: Icon, x0, y0, x1, y1, wood=("#b07c4e", "#4a2e18")) -> None:
    """Barrel as a form: bulged staves lit from the left, core shadow right, iron hoops, lit head."""
    w, h = x1 - x0, y1 - y0
    bul = w * 0.09
    ts = np.linspace(0, 1, 32)
    pts = [(x0 - bul * math.sin(math.pi * t), y0 + h * t) for t in ts]
    pts += [(x1 + bul * math.sin(math.pi * t), y0 + h * t) for t in ts[::-1]]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], (x0 + w * 0.15, x1 + bul), vertical=False, noise=0.14)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.55, y0, x1 + bul, y1)), m, (10, 4, 0), 0.35, w * 0.12)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.12, y0, x0 + w * 0.26, y1)), m, (255, 232, 196), 0.22, 6)
    for sx in np.linspace(x0 + w * 0.2, x1 - w * 0.12, 4):
        ic.line([(sx + ic.random.uniform(-3, 3), y0 + 12), (sx, y1 - 6)], 3, (50, 30, 14, 110))
    for f in (0.2, 0.78):
        hy = y0 + h * f
        ic.line([(x0 - bul * 0.7, hy), (x1 + bul * 0.7, hy + 2)], 11, (44, 42, 42))
        ic.line([(x0, hy - 3), (x0 + w * 0.5, hy - 3)], 3, (170, 162, 150, 120))
    head = (x0 - 2, y0 - h * 0.1, x1 + 2, y0 + h * 0.1)
    ic.fill(ic.mask("ellipse", head), "#c89c6c", "#7a5232", radial=(x0 + w * 0.3, y0 - h * 0.08, w * 0.9), noise=0.14)
    ic.overlay(lambda d: d.ellipse(head, outline=(44, 42, 42, 255), width=7))
    ic.outline(pts, 4, (40, 24, 12, 170))


def hanging_fish(ic: Icon, x: float, y: float, length: float, colors=("#d8b068", "#6e4418"), split: bool = False) -> None:
    """A fish hung by the tail: head down, lit left. ``split`` draws a flattened stockfish."""
    w = length * (0.34 if split else 0.24)
    ts = np.linspace(0, 1, 18)
    left = [(x - w / 2 * math.sin(math.pi * min(t * 1.15, 1)) ** 0.7, y + 14 + length * t) for t in ts]
    right = [(x + w / 2 * math.sin(math.pi * min(t * 1.15, 1)) ** 0.7, y + 14 + length * t) for t in ts]
    body = left + right[::-1]
    m = ic.poly_mask(body)
    ic.fill(m, colors[0], colors[1], (x - w / 2, x + w / 2), vertical=False, noise=0.18)
    tail = [(x, y + 18), (x - w * 0.5, y), (x + w * 0.5, y)]
    ic.poly(tail, colors[1], colors[1], edge=3)
    if split:
        ic.line([(x, y + 22), (x, y + length * 0.9)], 4, (120, 90, 60, 160))
    ic.outline(body, 3, (50, 30, 14, 190))


# ---------------------------------------------------------------- stage: water band with a shingle beach
def stage(ic: Icon) -> tuple[Image.Image, Image.Image]:
    band = ic.water_band(top=WATER_TOP, bottom=WATER_BOTTOM, sag=SAG, inset=46)
    ts = np.linspace(0, 1, 40)
    edge = [(1006 - 988 * t, 790 + 22 * math.sin(math.pi * t) + 8 * math.sin(9 * t) + ic.random.uniform(-3, 3))
            for t in ts]
    beach = ic.intersect(ic.poly_mask([(0, WATER_TOP - 10), (SIZE, WATER_TOP - 10)] + edge), band)
    ic.fill(beach, "#c0a476", "#7e6444", (WATER_TOP, 820), noise=0.26)

    def pebbles(d: ImageDraw.ImageDraw) -> None:
        for _ in range(260):
            x, y = ic.random.uniform(20, 1000), ic.random.uniform(WATER_TOP, 830)
            r = ic.random.uniform(4, 10)
            t = ic.random.uniform(-1, 1)
            col = (40, 30, 20, int(90 + 60 * -t)) if t < 0 else (236, 224, 200, int(80 * t + 40))
            d.ellipse((x - r * 1.3, y - r * 0.8, x + r * 1.3, y + r * 0.8), fill=col)

    ic.overlay(pebbles, beach)
    # wet, darker shingle sloping into the sea, then the surf line and a deeper water shelf
    wet = [(x, y - 30) for x, y in edge] + edge[::-1]
    tint(ic, ic.poly_mask(wet), beach, (40, 34, 30), 0.35, 10)
    ic.line(edge, 12, (236, 246, 244, 230))  # surf along the beach
    ic.line([(x, y + 12) for x, y in edge], 6, (30, 60, 70, 120))
    shelf = [(x, y + 36) for x, y in edge] + [(1024, 1024), (0, 1024)]
    tint(ic, ic.poly_mask(shelf), band, (10, 34, 48), 0.3, 18)

    def surf2(d: ImageDraw.ImageDraw) -> None:
        for x, y in edge[2:-2:3]:
            L = ic.random.uniform(30, 60)
            d.line([(x - L / 2, y + 26), (x + L / 2, y + 28)], fill=(232, 244, 245, 150), width=5)

    ic.overlay(surf2, band)
    ic.outline([(64, WATER_TOP), (960, WATER_TOP)], 5)
    return band, beach


# ---------------------------------------------------------------- tarred nets draped over one pole behind
def nets(ic: Icon) -> None:
    px0, px1, py = 596, 1000, 424
    for x in (px0 + 14, px1 - 18):
        ic.beam((x, py - 20), (x, BASE - 20), 18, WOOD)
    # swags: hold points on the pole, the net sagging into deep loops between them
    holds = (px0 + 4, 700, 812, 910, px1 + 8)
    hem = []
    for i, (a, b) in enumerate(zip(holds[:-1], holds[1:])):
        depth = (150, 118, 140, 104)[i]
        for t in np.linspace(0, 1, 12)[(1 if i else 0):]:
            hem.append((a + (b - a) * t, py + 50 + depth * math.sin(math.pi * t) ** 0.9 + ic.random.uniform(-3, 3)))
    top = [(px1 + 8, py - 2), (px0 + 4, py - 2)]
    ic.net(hem + top, back="#6a4c30", back_dark="#2e2014", cord=(18, 12, 6, 200), mesh=26)
    # the fold over the pole: a lit roll along the top, dark gaps where the swags turn
    for a, b in zip(holds[:-1], holds[1:]):
        m = (a + b) / 2
        tint(ic, ic.mask("ellipse", (m - 40, py + 20, m + 40, py + 120)), None, (10, 6, 2), 0.25, 18)
    ic.beam((px0 - 18, py), (px1 + 26, py + 4), 20, WOOD)
    ic.line([(px0, py - 12), (px1 + 10, py - 8)], 10, (86, 62, 40))
    ic.line([(px0, py - 16), (px1 + 10, py - 12)], 4, (190, 150, 104, 170))
    # cork floats along the hem
    for x, y in hem[3::5]:
        ic.ellipse((x - 14, y - 9, x + 14, y + 9), "#d0955a", "#7a4822", edge=4)
    for x in (px0 + 14, px1 - 18):
        ic.ellipse((x - 12, py - 28, x + 12, py - 12), "#a07650", "#6a4a30", edge=4)


# ---------------------------------------------------------------- the smokehouse
def smokehouse(ic: Icon) -> None:
    x0, x1, wall_top = 70, 440, 490
    dx, dy, rise = 118, -38, 176  # depth of the hut (back and to the right) and height of the ridge
    F = (x1, wall_top)
    B = (x1 + dx, wall_top + dy)
    A = (x1 + dx / 2, wall_top + dy / 2 - rise)
    ridge_y = A[1]
    # smoke from the ridge louvre, behind the roof
    smoke(ic, [(210, 88, 56), (252, 142, 62), (292, 196, 58)])
    # narrow side wall and the triangular gable above it, in shade
    side = [F, B, (B[0], BASE + dy), (x1, BASE)]
    end = [F, A, B, (B[0], BASE + dy), (x1, BASE)]
    planks(ic, (x1, A[1], B[0], BASE), "#7a6448", "#4a3a28", 24, clip=ic.poly_mask(end))
    ic.shade(ic.poly_mask(side), alpha=0.34)
    ic.shade(ic.poly_mask([F, A, B]), alpha=0.42)
    tint(ic, ic.poly_mask([F, A, B, (B[0], B[1] + 40), (x1, wall_top + 40)]), None, (0, 0, 0), 0.3, 10)
    ic.rect((x1 + 34, 560, x1 + 76, 610), "#2a1e16", "#141010", edge=4)  # small dark vent in the side wall
    ic.outline(end)
    # front wall: boards with a wide open front showing the smoked fish inside
    planks(ic, (x0, wall_top, x1, BASE), "#9a7650", "#54402a", 30)
    tint(ic, ic.mask("rectangle", (x0, BASE - 60, x1 + dx, BASE)), None, (30, 40, 20), 0.3, 16)
    ox0, ox1, oy0 = 138, 378, 548
    ic.rect((ox0, oy0, ox1, BASE - 6), "#3a2a20", "#161010", noise=0.1, edge=0)
    # firelight from the smoulder bed on the floor
    tint(ic, ic.mask("ellipse", (ox0 - 20, BASE - 110, ox1 + 20, BASE + 40)), ic.mask("rectangle", (ox0, oy0, ox1, BASE - 6)),
         (255, 128, 30), 0.55, 30)
    tint(ic, ic.mask("rectangle", (ox0, oy0, ox1, oy0 + 120)), None, (170, 90, 40), 0.2, 30)
    for row, y in enumerate((oy0 + 16, oy0 + 96)):
        ic.line([(ox0, y), (ox1, y)], 8, (90, 62, 38))
        x = ox0 + 16 + row * 10
        while x < ox1 - 12:
            warm = row == 1
            hanging_fish(ic, x, y + 2 + ic.random.uniform(0, 12), 62 + ic.random.uniform(-12, 12),
                         ("#e6a444", "#7a3a10") if warm else ("#cc9a4c", "#5e3612"))
            x += ic.random.choice((20, 24, 34, 46)) + ic.random.uniform(-3, 3)
    # smoulder bed: a low dark heap of coals with a few glowing embers
    bed = [(ox0 + 14, BASE - 6), (ox0 + 40, BASE - 22), (ox1 - 60, BASE - 26), (ox1 - 14, BASE - 6)]
    ic.poly(bed, "#3a2418", "#1a0e08", edge=0)
    for _ in range(14):
        ex, ey = ic.random.uniform(ox0 + 34, ox1 - 30), BASE - ic.random.uniform(10, 22)
        r = ic.random.uniform(3, 7)
        ic.ellipse((ex - r * 1.4, ey - r * 0.8, ex + r * 1.4, ey + r * 0.8), "#ffc050", "#d04a10", edge=0)
    tint(ic, ic.mask("rectangle", (ox0, oy0, ox1, oy0 + 40)), None, (0, 0, 0), 0.4, 12)
    for x in (ox0 - 12, ox1 + 12):
        ic.beam((x, wall_top), (x, BASE), 24, WOOD)
    ic.beam((x0, wall_top + 14), (x1, wall_top + 14), 22, WOOD)
    ic.beam((x0 + 10, wall_top), (x0 + 10, BASE), 22, WOOD)
    ic.beam((x1 - 8, wall_top), (x1 - 8, BASE), 20, WOOD)
    ic.outline([(x0, wall_top), (x1, wall_top), (x1, BASE), (x0, BASE)])
    # shadow band under the eave overhang on the front and side walls
    ic.shade(ic.poly_mask([(x0, wall_top), (x1, wall_top), (x1, wall_top + 58), (x0, wall_top + 58)]), alpha=0.5, blur=10)
    ic.shade(ic.poly_mask([F, B, (B[0], B[1] + 40), (x1, wall_top + 40)]), alpha=0.35, blur=8)
    # far slope: only its thick verge shows beyond the gable, in shade
    ov = 30
    far = [(A[0] - 4, A[1] - 14), (B[0] + ov, B[1] + 20), (B[0] + ov - 10, B[1] + 34), (A[0] + 6, A[1] + 8)]
    thatch(ic, far, "#7a5c32", "#3e2a14", 24, lean=0.6)
    ic.outline(far, 6)
    # near slope, lit: eave overhanging the front wall, ridge running back to the gable apex
    ex0, ex1, ey = x0 - 40, x1 + 26, wall_top + 26
    near = [(ex0, ey), (ex0 + dx / 2 + 8, ridge_y), (A[0] + 8, ridge_y), (ex1, ey)]
    lean = -(dx / 2 + 8) / (ey - ridge_y)
    thatch(ic, near, "#d0aa62", "#7a5428", 34, lean=lean)
    tint(ic, ic.poly_mask([(ex0, ey), (ex0 + dx / 2 + 8, ridge_y), (ex0 + 160, ridge_y), (ex0 + 90, ey)]),
         None, (255, 230, 170), 0.12, 30)
    tint(ic, ic.poly_mask([(ex0, ey - 30), (ex1, ey - 30), (ex1, ey), (ex0, ey)]), None, (40, 22, 8), 0.3, 8)
    ic.line([(ex0 + 4, ey - 6), (ex1 - 4, ey - 6)], 8, (110, 80, 42))  # trimmed thatch edge at the eave
    ic.outline(near, 7)
    # ridge cap
    ic.line([(ex0 + dx / 2 + 6, ridge_y + 4), (A[0] + 6, ridge_y + 4)], 20, (98, 72, 40))
    ic.line([(ex0 + dx / 2 + 6, ridge_y - 2), (A[0] + 6, ridge_y - 2)], 6, (196, 160, 100))
    ic.line([(ex0 + dx / 2 + 2, ridge_y + 14), (A[0] + 2, ridge_y + 14)], 4, LINE)
    # the smoke louvre sitting on the ridge
    lx = 250
    lv = [(lx - 32, ridge_y + 8), (lx - 26, ridge_y - 40), (lx + 36, ridge_y - 42), (lx + 42, ridge_y + 8)]
    ic.poly(lv, "#6e5236", "#3e2c1c", edge=5)
    ic.rect((lx - 16, ridge_y - 30, lx + 26, ridge_y - 4), "#2a1e16", "#141010", edge=0)
    lvr = [(lx - 46, ridge_y - 34), (lx + 6, ridge_y - 70), (lx + 58, ridge_y - 36)]
    ic.poly(lvr, "#b08c54", "#5a4428", edge=5)
    tint(ic, ic.poly_mask([(lx + 6, ridge_y - 70), (lx + 58, ridge_y - 36), (lx + 20, ridge_y - 36)]), None,
         (0, 0, 0), 0.3, 4)


# ---------------------------------------------------------------- drying flake and salting table
def flake(ic: Icon) -> None:
    posts = (600, 760, 930)
    for x in posts:
        ic.beam((x, 500), (x, BASE + 4), 20, WOOD)
    for y in (512, 626):
        ic.beam((posts[0] - 30, y), (posts[-1] + 30, y + 4), 16, WOOD)
        for x in np.arange(posts[0] - 6, posts[-1] + 24, 34):
            hanging_fish(ic, x + ic.random.uniform(-4, 4), y + 8, 84 + ic.random.uniform(-8, 8),
                         ("#ead6a6", "#8e7450"), split=True)
    for x in posts:
        ic.ellipse((x - 11, 492, x + 11, 508), "#a07650", "#6a4a30", edge=4)


def salting(ic: Icon, beach: Image.Image) -> None:
    # contact shadows on the beach
    tint(ic, ic.mask("ellipse", (40, BASE - 20, 560, BASE + 30)), beach, (20, 14, 8), 0.45, 12)
    tint(ic, ic.mask("ellipse", (540, BASE - 16, 1000, BASE + 26)), beach, (20, 14, 8), 0.4, 12)
    # salting table: plank top seen from above, trestle legs, a heap of white salt and fish
    tx0, tx1, ty = 470, 700, 700
    for x in (tx0 + 20, tx1 - 20):
        ic.beam((x, ty + 20), (x - 6, BASE + 14), 16, WOOD)
    top = [(tx0 + 12, ty - 20), (tx1 - 8, ty - 20), (tx1, ty + 10), (tx0, ty + 10)]
    ic.poly(top, "#b08458", "#8a6440")
    ic.rect((tx0, ty + 10, tx1, ty + 30), "#7a5436", "#4e3320")
    salt = [(tx0 + 110, ty - 6), (tx0 + 126, ty - 40), (tx0 + 150, ty - 58), (tx0 + 178, ty - 44), (tx0 + 206, ty - 6)]
    ic.fill(ic.poly_mask(salt), "#fbf8f0", "#a8a8a8", radial=(tx0 + 136, ty - 50, 110), noise=0.08)
    ic.outline(salt, 4, (90, 90, 96, 180))
    for cx, cy, a in ((tx0 + 50, ty - 6, -8), (tx0 + 80, ty + 2, 12)):
        ic.fish(cx, cy, 80, a)
    # casks of cured fish, one open with salt
    cask(ic, 846, 660, 930, 790)
    cask(ic, 922, 690, 996, 800)
    ic.fill(ic.mask("ellipse", (848, 646, 928, 674)), "#f4f0e6", "#b0aca4", (646, 674), noise=0.08)
    ic.basket(724, 716, 832, 790)
    ic.ellipse((720, 702, 836, 730), "#5a4128", "#3a2818", edge=4)
    for cx, cy, a in ((752, 712, -14), (792, 708, 16), (772, 722, -30)):
        ic.fish(cx, cy, 62, a)


def draw(ic: Icon) -> None:
    band, beach = stage(ic)
    nets(ic)
    smokehouse(ic)
    flake(ic)
    salting(ic, beach)
    rim_darken(ic)
