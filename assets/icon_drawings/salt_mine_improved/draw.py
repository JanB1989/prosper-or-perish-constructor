"""Improved Salt Mine (salt_mine_improved): a roofed timber gallery, a headframe over a shaft, a cart of salt.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game     uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/salt_mine_improved/draw.py     --out ../ProsperOrPerishConstructor/artifacts/icons/salt_mine_improved

Tier 1 of the salt mine (timbered galleries, drainage, better haulage). Same marl hill with rock-salt
seams and a quarried white face as the Salt Mine, but the plain adit becomes a roofed, planked gallery
portal with a timber track and a loaded mine cart, a timber headframe with a sheave wheel stands over
a shaft, and the pile of cut blocks is larger.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 31
REFS = ("salt_collector", "schwaz_mine", "stone_quarry", "clay_pit")

ROCK, ROCK_DK = "#8e6c4c", "#3a281a"  # marl and clay overburden around the salt body
SALT_TOP = ("#fbf8f0", "#e4dccd")
SALT_FRONT = ("#efe8dc", "#b5a896")
SALT_SIDE = ("#ad9e8c", "#7c6e60")
WOOD, WOOD_DK = "#a86c3a", "#5e3a1e"  # warm orange-brown timber, as vanilla
IRON = (46, 44, 46)
DARK = (28, 20, 14)


# ---- helpers (shared by the salt family) -------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam: lit upper half, darker lower half, a grain highlight, soft rim."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, vertical_boards: bool = True) -> Image.Image:
    """Board panel: per-board tone, grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    lo, hi = (min(xs), max(xs)) if vertical_boards else (min(ys), max(ys))
    v = lo
    while v < hi:
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        col = (255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t))
        if vertical_boards:
            d.rectangle((v, min(ys), v + w, max(ys)), fill=col)
            gx = v + R.uniform(4, max(w - 4, 5))
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        else:
            d.rectangle((min(xs), v, max(xs), v + w), fill=col)
            gy = v + R.uniform(4, max(w - 4, 5))
            d.line([(min(xs), gy), (max(xs), gy + R.uniform(-3, 3))], fill=(40, 24, 12, 60), width=2)
            d.line([(min(xs), v), (max(xs), v)], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def crystal(ic: Icon, m: Image.Image, box, strength: float = 1.0) -> None:
    """Rock-salt texture inside ``m``: faint cleavage strokes, grey specks and a few glints."""
    x0, y0, x1, y1 = box
    R = ic.random
    lay, d = layer()
    area = max((x1 - x0) * (y1 - y0), 1)
    for _ in range(int(area / 900 * strength)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        r = R.uniform(2, 5)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(90, 80, 74, R.randint(40, 90)))
    for _ in range(int(area / 3000 * strength)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        L = R.uniform(10, 26)
        a = math.radians(R.choice((30, 60, 120, 150)) + R.uniform(-8, 8))
        d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=(120, 110, 104, 70), width=3)
    for _ in range(int(area / 5000 * strength)):
        x, y = R.uniform(x0, x1), R.uniform(y0, y1)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 252, 200))
    composite(ic, lay, m)


def salt_block(ic: Icon, x: float, y: float, w: float, h: float, dx: float = 22, dy: float = 30,
               tone: float = 0.0, top: bool = True) -> None:
    """Cut rock-salt block: bottom-left front corner at (x, y + h). Lit top, front face, darker right
    side; crystalline texture, chipped edges and grime low on the front. ``tone`` < 0 greyer,
    > 0 slightly rose (Khewra salt)."""
    def col(c, k=1.0):
        v = rgb(c) * k
        if tone > 0:
            v = v * np.array([1.0, 0.9, 0.86]) ** (tone * 2)
        return tuple(int(min(255, t)) for t in v)

    k = 1 + min(tone, 0) * 0.3
    front = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    side = [(x + w, y), (x + w + dx, y - dy), (x + w + dx, y + h - dy), (x + w, y + h)]
    lid = [(x, y), (x + w, y), (x + w + dx, y - dy), (x + dx, y - dy)]
    fm, sm, tm = ic.poly_mask(front), ic.poly_mask(side), ic.poly_mask(lid)
    ic.fill(sm, col(SALT_SIDE[0], k), col(SALT_SIDE[1], k), (y - dy, y + h), noise=0.2)
    ic.fill(fm, col(SALT_FRONT[0], k), col(SALT_FRONT[1], k), (y - h * 0.3, y + h * 1.1), noise=0.18, chroma=0.06)
    if top:
        ic.fill(tm, col(SALT_TOP[0], k), col(SALT_TOP[1], k), (y - dy, y), noise=0.12)
    crystal(ic, fm, (x, y, x + w, y + h), 0.8)
    crystal(ic, sm, (x + w, y - dy, x + w + dx, y + h), 0.5)
    tint(ic, ic.mask("rectangle", (x - 10, y + h * 0.6, x + w, y + h + 10)), fm, (60, 48, 40), 0.3, 12)
    tint(ic, ic.mask("rectangle", (x - 4, y - 4, x + w * 0.6, y + h * 0.3)), fm, (255, 252, 244), 0.25, 14)
    # chipped corners
    R = ic.random
    for _ in range(2):
        cx, cy = (x + R.uniform(6, w - 6), y + h - R.uniform(3, 8)) if R.random() < 0.5 else (x + w - 4, y + R.uniform(6, h - 6))
        ic.shade(ic.intersect(ic.poly_mask(ic.jitter(cx, cy, R.uniform(6, 12), R.uniform(4, 8), 6, 0.3)), fm), (70, 60, 54), 0.5)
    ic.line([(x + 3, y + 2), (x + w - 3, y + 2)], 4, (255, 255, 250, 150))
    ic.line([(x + w, y), (x + w, y + h)], 3, (60, 50, 44, 150))
    ic.outline(front + [(x + w, y + h), (x + w + dx, y + h - dy), (x + w + dx, y - dy), (x + dx, y - dy), (x, y)], 4,
               (52, 44, 40, 170))


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



def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping boards/tiles with per-tile tone, lit lips and course shadows."""
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


def seam(ic: Icon, path, r: float, light, dark, edge=(70, 50, 38)) -> None:
    """Smooth bedding band along a gently curved path: thickness swells and thins, a lit upper lip
    and a soft shadow under the lower edge; low noise so it stays a clean band at 64 px."""
    R = ic.random
    p = np.array(path, float)
    t = np.linspace(0, 1, len(p))
    tt = np.linspace(0, 1, 160)
    xs, ys = np.interp(tt, t, p[:, 0]), np.interp(tt, t, p[:, 1])
    k = 21
    ys = np.convolve(np.pad(ys, k // 2, mode="edge"), np.ones(k) / k, "valid")
    ph1, ph2, f = R.uniform(0, 6.3), R.uniform(0, 6.3), R.uniform(2.2, 3.4)
    w = r * (0.62 + 0.28 * np.sin(tt * math.pi * f + ph1) + 0.12 * np.sin(tt * math.pi * 7.3 + ph2))
    top = [(x, y - wi * 0.55) for x, y, wi in zip(xs, ys, w)]
    bot = [(x, y + wi * 0.45) for x, y, wi in zip(xs, ys, w)]
    m = ic.poly_mask(top + bot[::-1])
    ic.shade(ic.poly_mask([(x, y + 6) for x, y in bot] + [(x, y + 16) for x, y in bot[::-1]]), edge, 0.45, blur=4)
    ic.fill(m, light, dark, (float(ys.min() - r), float(ys.max() + r)), noise=0.07, chroma=0.03)
    ic.shade(ic.poly_mask([(x, y + 1) for x, y in bot] + [(x, y - wi * 0.35) for (x, y), wi in zip(bot[::-1], w[::-1])]),
             (60, 44, 34), 0.28, blur=3)
    ic.line(top, 4, (255, 250, 240, 150))


# ---- parts -------------------------------------------------------------------------------------
def crest(ic: Icon, m: Image.Image, depth: int = 44, light="#8c8a4a", dark="#4c4a26") -> None:
    """Grassy crest along the top of a hill mask: a ragged olive band with lit tufts."""
    shifted = Image.new("L", (SIZE, SIZE), 0)
    shifted.paste(m, (0, depth))
    band = ImageChops.subtract(m, shifted).filter(ImageFilter.GaussianBlur(3)).point(lambda v: 255 if v > 110 else 0)
    ys, xs = np.nonzero(np.asarray(band))
    R = ic.random
    for _ in range(int(len(xs) / 900)):
        i = R.randrange(len(xs))
        band = ImageChops.lighter(band, ic.intersect(ic.poly_mask(ic.jitter(xs[i], ys[i] + 18, R.uniform(14, 30),
                                                                            R.uniform(12, 22), 7, 0.3)), m))
    ic.fill(band, light, dark, radial=(200, 250, 700), noise=0.3, chroma=0.12)
    lay, d = layer()
    for _ in range(int(len(xs) / 500)):
        i = R.randrange(len(xs))
        x, y = xs[i], ys[i]
        d.line([(x, y + 8), (x + R.uniform(-8, 8), y - R.uniform(8, 20))], fill=(170, 170, 96, 200), width=4)
    composite(ic, lay, band.filter(ImageFilter.MaxFilter(9)))


def hill(ic: Icon) -> Image.Image:
    """Hill of marl and clay with rock-salt seams and a quarried white salt face on its shoulder."""
    pts = [(40, 905), (50, 770), (80, 640), (118, 520), (160, 424), (206, 350), (250, 300), (298, 284),
           (340, 306), (392, 346), (446, 360), (500, 352), (552, 384), (600, 430), (640, 492), (668, 570),
           (684, 680), (692, 905)]
    ic.rock(pts, ROCK, ROCK_DK, facets=4)
    m = ic.poly_mask(pts)
    with ic.clipped(m):
        # same bedding finish as the Salt Mine: clean white and rose seams, gently folded
        seam(ic, [(0, 552), (120, 506), (250, 474), (380, 470), (520, 486), (700, 452), (900, 420)], 36,
             "#f4ede2", "#c8b8a6")
        seam(ic, [(0, 690), (140, 640), (260, 608), (400, 616), (560, 600), (720, 566), (900, 560)], 46,
             "#ecd2c4", "#b08c7c")
        seam(ic, [(0, 808), (150, 770), (300, 744), (440, 752), (620, 730), (900, 700)], 32,
             "#f2ebe0", "#c0ae9c")
        seam(ic, [(60, 590), (220, 552), (360, 548)], 10, "#e8dccc", "#b8a694")
        for part, wd in (([(0, 626), (180, 578), (330, 566), (520, 570), (900, 520)], 6),
                         ([(0, 752), (200, 700), (360, 690), (560, 676), (900, 646)], 5)):
            ic.line(part, wd, (58, 40, 28, 120))
        ic.shade(ic.mask("rectangle", (0, 810, SIZE, SIZE)), (40, 30, 22), 0.35, blur=30)
        rim = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(31)))
        ic.shade(rim, alpha=0.25, blur=8)
    crest(ic, m)
    ic.outline(pts)
    return m


def headframe(ic: Icon, cx: float, top: float, foot: float) -> None:
    """Timber headframe over the shaft: raking legs, cross-ties and braces, a sheave wheel under a
    little board roof, the hoisting rope running down into the shaft collar."""
    lx0, lx1 = cx - 200, cx + 190  # leg feet: a wide, squat trapezoid
    tx0, tx1 = cx - 52, cx + 52   # leg heads
    # diagonal back-stay from the head down to the ground on the right
    timber(ic, (tx1 - 6, top + 14), (cx + 290, foot + 4), 34, "#9a6436", "#583818")
    # far (back) legs, darker
    for a, b in (((lx0 + 50, foot - 10), (tx0 + 14, top + 20)), ((lx1 - 50, foot - 10), (tx1 - 14, top + 20))):
        timber(ic, a, b, 22, "#6a4426", "#3e2814")
    # rope and shaft collar
    ic.line([(cx + 4, top - 10), (cx + 4, foot - 40)], 9, (70, 56, 40))
    ic.line([(cx + 2, top - 10), (cx + 2, foot - 40)], 4, (170, 140, 96, 210))
    # near legs, ties and braces (thick enough to survive at 64 px)
    timber(ic, (lx0, foot), (tx0, top + 10), 46, "#b27842", "#643e1e")
    timber(ic, (lx1, foot), (tx1, top + 10), 46, "#b27842", "#643e1e")
    for t in (0.3, 0.64):
        y = foot + (top - foot) * t
        xa = lx0 + (tx0 - lx0) * t
        xb = lx1 + (tx1 - lx1) * t
        timber(ic, (xa - 10, y), (xb + 10, y), 36, "#a46e3c", "#5e3c1e")
    y0, y1 = foot + (top - foot) * 0.3, foot + (top - foot) * 0.64
    timber(ic, (lx0 + (tx0 - lx0) * 0.3 + 16, y0 - 12), (lx1 + (tx1 - lx1) * 0.64 - 16, y1 + 12), 30, "#9a6438",
           "#583a1c")
    timber(ic, (tx0 - 40, top + 6), (tx1 + 40, top + 6), 36, "#b0743e", "#643e20")  # head beam
    # small pent roof on two short posts behind the wheel, sloping down to the left
    r = 82
    wc = (cx + 4, top - r + 6)
    rt = wc[1] - r - 22
    # one king post behind the wheel carries the roof, with a short raking strut
    timber(ic, (cx + 30, top - 6), (cx + 30, rt + 20), 24, "#7a4e2a", "#442a14")
    timber(ic, (cx + 36, top - 70), (cx + 96, rt + 16), 16, "#6e4626", "#3e2612")
    # sheave wheel on top, bigger and in the open
    ic.shade(ic.mask("ellipse", (wc[0] - r + 12, wc[1] - r + 16, wc[0] + r + 16, wc[1] + r + 18)), alpha=0.35, blur=8)
    ic.overlay(lambda d: d.ellipse((wc[0] - r, wc[1] - r, wc[0] + r, wc[1] + r), outline=(38, 26, 16, 255), width=26))
    ic.overlay(lambda d: d.ellipse((wc[0] - r + 4, wc[1] - r + 4, wc[0] + r - 4, wc[1] + r - 4),
                                   outline=(170, 112, 62, 255), width=15))
    ic.overlay(lambda d: d.arc((wc[0] - r + 6, wc[1] - r + 6, wc[0] + r - 6, wc[1] + r - 6), 190, 280,
                               fill=(236, 186, 128, 170), width=5))
    for a in np.linspace(0, math.pi, 3, endpoint=False):
        ca, sa = math.cos(a) * (r - 10), math.sin(a) * (r - 10)
        timber(ic, (wc[0] - ca, wc[1] - sa), (wc[0] + ca, wc[1] + sa), 12, "#8e5e32", "#4e3218")
    ic.ellipse((wc[0] - 16, wc[1] - 16, wc[0] + 16, wc[1] + 16), "#7a7674", "#3a3838", edge=4)
    # pent roof over the wheel, its eave shading the wheel's top
    ic.shade(ic.poly_mask([(cx - 100, rt + 40), (cx + 110, rt + 14), (cx + 110, rt + 64), (cx - 100, rt + 84)]),
             alpha=0.45, blur=12)
    shingles(ic, [(cx - 126, rt + 48), (cx + 128, rt + 12), (cx + 112, rt - 30), (cx - 112, rt + 8)],
             "#a47a50", "#664428", course=22, stagger=32, edge=6)
    ic.line([(cx - 126, rt + 48), (cx + 128, rt + 12)], 10, (80, 52, 30, 230))


def portal(ic: Icon, x0: float, x1: float, eave: float, foot: float) -> None:
    """Roofed timber gallery portal projecting from the hill: planked cheeks, heavy frame, dark
    gallery with receding timber sets, gable of boards."""
    w = x1 - x0
    mouth = [(x0 + 44, foot), (x0 + 44, eave + 70), (x1 - 44, eave + 70), (x1 - 44, foot)]
    ic.poly(mouth, "#2a221c", "#0c0907", edge=0, noise=0.1)
    for k, inset in enumerate((0.26, 0.33, 0.38)):
        c = tuple(int(v * (0.5 - 0.12 * k)) for v in (138, 98, 62))
        t = eave + 110 + 50 * k
        ic.beam((x0 + w * inset, foot), (x0 + w * inset, t), 14 - 3 * k, c)
        ic.beam((x1 - w * inset, foot), (x1 - w * inset, t), 14 - 3 * k, c)
        ic.beam((x0 + w * inset - 6, t), (x1 - w * inset + 6, t), 14 - 3 * k, c)
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.25, blur=20)
    # planked cheeks either side of the mouth
    planks(ic, [(x0, eave + 30), (x0 + 44, eave + 30), (x0 + 44, foot), (x0, foot)], "#8a643e", "#4e3522", board=18)
    planks(ic, [(x1 - 44, eave + 30), (x1, eave + 30), (x1, foot), (x1 - 44, foot)], "#7a5636", "#442e1c", board=18)
    timber(ic, (x0 + 40, foot + 4), (x0 + 40, eave + 40), 30)
    timber(ic, (x1 - 40, foot + 4), (x1 - 40, eave + 40), 30)
    timber(ic, (x0 + 10, eave + 58), (x1 - 10, eave + 58), 32, "#94693f", "#5a3c24")
    ic.shade(ic.mask("rectangle", (x0 + 50, eave + 74, x1 - 50, eave + 120)), alpha=0.45, blur=10)
    # gable roof of boards
    ridge = eave - 120
    cx = (x0 + x1) / 2
    gable = [(x0 + 10, eave + 40), (cx, ridge + 10), (x1 - 10, eave + 40)]
    planks(ic, gable, "#8e6a46", "#5a3e28", board=20)
    ic.shade(ic.poly_mask(gable), alpha=0.25, blur=6)
    shingles(ic, [(x0 - 34, eave + 46), (cx - 6, ridge - 6), (cx + 10, ridge + 10), (x0 - 12, eave + 62)],
             "#9a7450", "#62442c", course=24, stagger=34, edge=6)
    shingles(ic, [(x1 + 34, eave + 46), (cx + 6, ridge - 6), (cx - 10, ridge + 10), (x1 + 12, eave + 62)],
             "#7a5a3e", "#4a3220", course=24, stagger=34, edge=6)


def rails(ic: Icon, x0: float, x1: float, y: float) -> None:
    """Timber track: sleepers and two wooden rails running out of the gallery."""
    for x in np.arange(x0, x1, 46):
        timber(ic, (x, y - 10), (x + 16, y + 16), 12, "#6a4a2e", "#3e2a1a")
    timber(ic, (x0 - 10, y - 6), (x1, y - 6), 12, "#8a6a4a", "#4e3a28")
    timber(ic, (x0 - 10, y + 10), (x1, y + 12), 12, "#8a6a4a", "#4e3a28")


def cart(ic: Icon, x0: float, x1: float, top: float, bottom: float) -> None:
    """Mine cart (hund) on the track: iron-bound wooden box, small wheels, piled salt blocks."""
    # dark gap behind the load and the cart's right end, so they stand off the big stack
    ic.shade(ic.poly_mask([(x1 - 60, top - 150), (x1 + 34, top - 140), (x1 + 34, bottom + 20), (x1 - 60, bottom + 20)]),
             (22, 14, 10), 0.75, blur=14)
    salt_block(ic, x0 + 18, top - 76, 104, 80, dx=20, dy=26, tone=0.5)
    salt_block(ic, x0 + 126, top - 58, 90, 62, dx=18, dy=22, tone=0.0)
    salt_block(ic, x0 + 60, top - 132, 92, 64, dx=18, dy=22, tone=0.2)
    box = [(x0, top), (x1, top), (x1 - 16, bottom), (x0 + 16, bottom)]
    planks(ic, box, "#96704a", "#553a24", board=20, vertical_boards=False)
    ic.shade(ic.poly_mask([(x0, top), (x1, top), (x1, top + 12), (x0, top + 12)]), (255, 240, 220), 0.25)
    for fx in (0.08, 0.92):
        x = x0 + (x1 - x0) * fx
        ic.line([(x, top), (x + (6 if fx < 0.5 else -6), bottom)], 10, (50, 48, 50))
    ic.line([(x0, top + 4), (x1, top + 4)], 9, (50, 48, 50))
    for wx in (x0 + 46, x1 - 46):
        ic.ellipse((wx - 32, bottom - 22, wx + 32, bottom + 42), "#5e5a58", "#262322", edge=5)
        ic.ellipse((wx - 10, bottom, wx + 10, bottom + 20), "#9a948e", "#4a4644", edge=3)
    ic.shade(ic.poly_mask([(x1 - 40, top), (x1, top), (x1 - 14, bottom), (x1 - 50, bottom)]), alpha=0.25, blur=8)


def block_stack(ic: Icon) -> None:
    """Large stack of cut salt blocks bottom right, with its contact shadow."""
    base = 968
    ic.shade(ic.poly_mask([(640, base - 24), (1014, base - 30), (1014, base + 8), (640, base + 8)]), alpha=0.45, blur=12)
    rows = [  # (x, width, height, tone) per block, bottom row first
        [(672, 116, 92, 0.1), (792, 102, 92, 0.6), (898, 110, 88, 0.0)],
        [(700, 112, 84, 0.55), (816, 104, 84, 0.05), (924, 80, 78, 0.4)],
        [(746, 110, 78, 0.1), (858, 90, 74, 0.7)],
    ]
    y = base
    for row in rows:
        h = row[0][2]
        for x, w, hh, tone in row:
            salt_block(ic, x + ic.random.uniform(-4, 4), y - hh, w, hh, dx=18, dy=26, tone=tone)
        y -= h + 10


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.80
    ic.grade["mute"] = 0.9
    hill(ic)
    headframe(ic, 790, 540, 900)
    # shaft collar at the headframe foot
    ic.poly([(700, 900), (840, 900), (830, 870), (710, 870)], "#6e5036", "#3e2a1a", noise=0.2)
    apron = [(20, 968), (60, 905), (300, 894), (660, 896), (900, 904), (1010, 968)]
    ic.poly(apron, "#b0a28e", "#766856", noise=0.28)
    for _ in range(40):
        x, y = ic.random.uniform(80, 940), ic.random.uniform(904, 956)
        r = ic.random.uniform(4, 11)
        ic.shade(ic.mask("ellipse", (x - r, y - r * 0.6, x + r, y + r * 0.6)), (248, 246, 240), 0.55)
    portal(ic, 176, 436, 520, 905)
    rails(ic, 200, 680, 930)
    block_stack(ic)
    cart(ic, 356, 628, 800, 906)
