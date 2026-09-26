"""Adit Copper Mine (copper_mine_adit): a timbered adit with a gabled portal, rails and drainage.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/copper_mine_adit/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/copper_mine_adit

Composition: the same malachite-crusted tan rock as the Copper Mine, now a tall face cut by a
proper adit: square timber sets receding into the dark, a gabled plank portal hood, a sleepered
track running out of the mouth to a loaded ore cart (green and copper-red ore), and the drainage
water running out along a plank-lined channel into a small, dull pool bottom left. A broad, low
heap of dressed ore behind and right of the cart. Tier 1: more structure, rails and water where
tier 0 has a windlass over a shaft.
"""

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 23
REFS = ("schwaz_mine", "clay_pit", "stone_quarry", "mercury_patio")

SIZE = 1024
ROCK = "#b89e78"
ROCK_DARK = "#4f3f30"
MAL = "#5ea888"  # malachite, lit
MAL_DARK = "#1c4a3a"
MAL_EDGE = (14, 40, 30)
AZ = "#4f7f9e"  # azurite accent
AZ_DARK = "#1f3a52"
CU = "#c86f3e"  # native copper / cuprite, lit
CU_DARK = "#5a2614"
TIMBER = (118, 80, 50)
TIMBER_LT = (150, 108, 70)
IRON = (46, 44, 46)
IRON_LT = (96, 94, 96)
DARK = (28, 18, 12)
W_LIGHT = "#6a8a8e"  # drainage water: dull grey-teal, it must not outshine the adit
W_DEEP = "#2a4246"


def ore_lumps(ic: Icon, pts, r: float, share_cu: float = 0.3) -> None:
    for x, y in pts:
        rr = r * ic.random.uniform(0.8, 1.15)
        if ic.random.random() < share_cu:
            ic.chunk(x, y, rr, CU, CU_DARK, (255, 200, 150))
        else:
            ic.chunk(x, y, rr, MAL, MAL_DARK, (210, 255, 225))


def board(ic: Icon, pts, c1="#9a6c44", c2="#5a3c24", joints=()) -> None:
    """Plank surface with soft joints (helper, not in the kit)."""
    ic.poly(pts, c1, c2, noise=0.22)
    for a, b in joints:
        ic.line([a, b], 4, (50, 32, 20, 150))


def crust(ic: Icon, path, depth: float, c1=MAL, c2=MAL_DARK, edge=MAL_EDGE, specks: int = 7) -> None:
    """Malachite crust lying on a ledge or facet (helper, not in the kit; same as copper_mine).

    The top edge hugs ``path`` (a stratum line or facet edge), the crust hangs ``depth`` below it with
    a ragged, broken underside, gets a darker lower lip, a lit upper edge, a faint cast line on the
    rock and a few loose specks around it.
    """
    rng = np.random.default_rng(ic.random.randint(0, 2 ** 31))
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    ends = np.concatenate([[0], np.cumsum(seg)])
    n = max(10, int(ends[-1] / 12))
    d = np.linspace(0, ends[-1], n)
    xs, ys = np.interp(d, ends, pts[:, 0]), np.interp(d, ends, pts[:, 1])
    tx, ty = np.gradient(xs), np.gradient(ys)
    ln = np.hypot(tx, ty) + 1e-6
    nx, ny = -ty / ln, tx / ln
    flip = np.where(ny < 0, -1.0, 1.0)
    nx, ny = nx * flip, ny * flip
    prof = np.sin(np.pi * np.linspace(0.04, 0.96, n)) ** 0.5
    wob = np.convolve(rng.uniform(0.2, 1.4, n + 4), np.ones(5) / 5, "valid")[:n]
    th = depth * 1.2 * prof * wob
    top = [(x - a * 4 + rng.uniform(-3, 3), y - b * 4 + rng.uniform(-3, 3)) for x, y, a, b in zip(xs, ys, nx, ny)]
    bot = [(x + a * t + rng.uniform(-7, 7), y + b * t + rng.uniform(-5, 5))
           for x, y, a, b, t in zip(xs, ys, nx, ny, th)]
    m = ic.poly_mask(top + bot[::-1])
    # satellite patches just below and beside the band
    for _ in range(3):
        k = rng.integers(0, n)
        cx, cy = xs[k] + nx[k] * (th[k] + 14), ys[k] + ny[k] * (th[k] + 14)
        r = rng.uniform(8, 16)
        m = ImageChops.lighter(m, ic.poly_mask(ic.jitter(cx, cy, r * 1.4, r, 7, 0.3)))
    # break it into patches with low-frequency holes
    holes = Image.fromarray((rng.random((30, 30)) * 255).astype("uint8")).resize((SIZE, SIZE), Image.BICUBIC)
    holes = holes.point(lambda v: 255 if v > 62 else 0)
    m = ImageChops.multiply(m, holes).filter(ImageFilter.MedianFilter(5))
    lo, hi = float(min(ys.min(), (ys + ny * th).min())), float(max(ys.max(), (ys + ny * th).max()))
    under = ImageChops.subtract(ImageChops.offset(m, 0, 7), m)
    ic.shade(under, (30, 22, 16), 0.35, blur=2)  # the crust stands proud: a thin cast line on the rock
    ic.fill(m, c1, c2, (lo - 6, hi + 10), noise=0.45)
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, 0, -10)), edge, 0.7)  # darker underside
    ic.shade(ImageChops.subtract(m, ImageChops.offset(m, 0, 6)), (205, 245, 220), 0.3)  # lit top edge
    for _ in range(specks):
        k = rng.integers(0, n)
        s = rng.uniform(-0.4, 1.8)
        cx = xs[k] + nx[k] * th[k] * s + rng.uniform(-18, 18)
        cy = ys[k] + ny[k] * th[k] * s + rng.uniform(-10, 14)
        r = rng.uniform(4, 8)
        ic.shade(ic.poly_mask(ic.jitter(cx, cy, r, r * 0.8, 6, 0.25)), (84, 160, 124), 0.8)


def mound(ic: Icon, x0, x1, base, top, r, rows, cu_share=0.4, body=("#3f5a48", "#1d2b22"), power=0.65) -> None:
    """Rounded ore heap: a domed body with rows of lumps and a soft lit crown (helper, not in the kit)."""
    ts = np.linspace(0, 1, 28)
    outline = [(x0 + (x1 - x0) * t, base - (base - top) * np.sin(np.pi * t) ** power) for t in ts]
    ic.poly(outline, body[0], body[1], noise=0.3)
    # lumps may bulge a little above the body, but no stray facet lines past a clean domed crown
    crown = [(x0 + (x1 - x0) * t, base - (base - top + r * 0.5) * np.sin(np.pi * t) ** power) for t in ts]
    with ic.clipped(ic.poly_mask(crown + [(x1 + r, base + r), (x0 - r, base + r)])):
        _mound_lumps(ic, x0, x1, base, top, r, rows, cu_share, power)
    m = ic.poly_mask(outline)
    ic.shade(ic.poly_mask([(x0 + (x1 - x0) * 0.55, top), (x1 + 20, top), (x1 + 20, base), (x0 + (x1 - x0) * 0.62, base)]),
             alpha=0.28, blur=24)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (x0 + (x1 - x0) * 0.15, top - 20, x0 + (x1 - x0) * 0.6, top + (base - top) * 0.5))),
             (255, 240, 220), 0.12, blur=20)


def _mound_lumps(ic: Icon, x0, x1, base, top, r, rows, cu_share, power) -> None:
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.55 + (base - top - r * 0.9) * t
        h = np.clip((base - y) / (base - top), 0, 1)
        tt = np.arcsin(h ** (1 / power)) / np.pi
        half = (x1 - x0) * (0.5 - tt) - r * 0.35
        n = max(1, int(2 * half / (r * 1.25)) + 1)
        cx = (x0 + x1) / 2
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + ic.random.uniform(-10, 10)
            rr = r * ic.random.uniform(0.8, 1.1)
            if ic.random.random() < cu_share:
                ic.chunk(x, y, rr, CU, CU_DARK, (255, 200, 150))
            else:
                ic.chunk(x, y, rr, MAL, MAL_DARK, (210, 255, 225))


def draw(ic: Icon) -> None:
    # ---- the rock face: broad and taller than the tier-0 outcrop
    face = [(30, 900), (40, 720), (70, 610), (100, 520), (150, 450), (182, 372), (228, 332), (258, 262),
            (300, 226), (334, 250), (372, 206), (420, 236), (466, 300), (516, 288), (572, 330), (636, 344),
            (700, 414), (742, 500), (772, 600), (796, 900)]
    ic.rock(face, ROCK, ROCK_DARK, facets=6)
    fm = ic.poly_mask(face)
    with ic.clipped(fm):
        ic.shade(fm, (204, 152, 90), 0.24)  # warm the stone towards tan
        for y in (420, 560, 700, 820):
            ic.line([(0, y + 60), (300, y + 10), (560, y - 20), (900, y + 30)], 5, (60, 48, 38, 130))
        for cx, cy, rx, ry in ((230, 340, 60, 30), (660, 420, 70, 30), (150, 600, 50, 30), (700, 570, 40, 40)):
            ic.shade(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), (70, 150, 110), 0.25, blur=18)
        # malachite crusts on the ledges and facets, a small azurite patch
        crust(ic, [(186, 376), (226, 340), (258, 300), (300, 262)], 54)
        crust(ic, [(100, 470), (176, 454), (250, 442)], 56)
        crust(ic, [(56, 614), (150, 598), (244, 584)], 58)
        crust(ic, [(76, 752), (160, 738), (244, 724)], 40, specks=5)
        crust(ic, [(596, 410), (660, 418), (716, 434)], 58)
        crust(ic, [(636, 552), (700, 558), (756, 572)], 56)
        crust(ic, [(548, 322), (600, 334), (636, 348)], 36, specks=4)
        crust(ic, [(712, 474), (748, 496)], 30, AZ, AZ_DARK, (16, 28, 42), specks=3)
        ic.vein([(400, 250), (380, 330)], 14, CU, CU_DARK, (60, 26, 14))
        ic.vein([(720, 620), (760, 700)], 14, CU, CU_DARK, (60, 26, 14))
        ic.vein([(120, 660), (150, 700), (140, 730)], 12, CU, CU_DARK, (60, 26, 14))
        for _ in range(22):
            x, y = ic.random.uniform(50, 840), ic.random.uniform(260, 860)
            r = ic.random.uniform(4, 9)
            ic.shade(ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), (90, 170, 130), 0.5)
        ic.shade(ic.mask("rectangle", (0, 760, 1024, 1024)), alpha=0.35, blur=40)
        # the portal's cast shadow on the rock
        ic.shade(ic.poly_mask([(560, 420), (620, 460), (640, 900), (570, 900)]), alpha=0.35, blur=18)
        rim = ImageChops.subtract(fm, fm.filter(ImageFilter.MinFilter(31)))
        ic.shade(rim, alpha=0.25, blur=8)
    ic.outline(face)

    # ---- ground in front: packed spoil
    apron = [(20, 972), (60, 896), (320, 884), (760, 884), (960, 900), (1004, 972)]
    ic.poly(apron, "#8e7656", "#56452f", noise=0.3)
    with ic.clipped(ic.poly_mask(apron)):
        for _ in range(24):
            x, y = ic.random.uniform(60, 960), ic.random.uniform(900, 962)
            col = (80, 160, 120) if ic.random.random() < 0.55 else (196, 104, 58)
            ic.shade(ic.mask("ellipse", (x - 9, y - 6, x + 9, y + 6)), col, 0.7)

    # ---- adit mouth: dark, with square timber sets receding
    mouth = [(318, 902), (322, 586), (538, 586), (542, 902)]
    ic.poly(mouth, "#2a201a", "#0b0806", edge=0, noise=0.1)
    for k, (inset, top) in enumerate(((42, 632), (74, 676), (98, 710))):
        col = tuple(int(c * (0.62 - 0.15 * k)) for c in TIMBER)
        w = 20 - 5 * k
        ic.beam((318 + inset, 900), (322 + inset, top), w, col)
        ic.beam((542 - inset, 900), (538 - inset, top), w, col)
        ic.beam((318 + inset - 8, top), (542 - inset + 8, top), w, col)
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.3, blur=20)

    # track running out of the mouth and curving right: spaced sleepers, two lit rails
    def rail(x0, x1, y1, t):
        return x0 + (x1 - x0) * t ** 1.6, 880 + (y1 - 880) * t

    ts = np.linspace(0, 1, 24)
    r1 = [rail(410, 690, 980, t) for t in ts]
    r2 = [rail(500, 840, 962, t) for t in ts]
    for t in (0.12, 0.38, 0.64, 0.9):
        (ax, ay), (bx, by) = rail(410, 690, 980, t), rail(500, 840, 962, t)
        ic.line([(ax - 30, ay + 6), (bx + 30, by + 4)], 30, (36, 24, 16))
        ic.line([(ax - 28, ay + 3), (bx + 28, by + 1)], 20, (104, 70, 44))
        ic.line([(ax - 26, ay - 3), (bx + 26, by - 5)], 6, (160, 118, 78))
    for r in (r1, r2):
        ic.line(r, 22, DARK)
        ic.line(r, 14, (104, 100, 96))
        ic.line([(x, y - 4) for x, y in r], 5, (200, 194, 182))

    # drainage water: out of the mouth along a plank-lined channel into a small pool bottom left
    chan = [(326, 884), (392, 884), (300, 972), (212, 972)]
    ic.poly([(314, 880), (404, 880), (318, 984), (192, 984)], "#8a5e3a", "#4e331e", noise=0.22)
    ic.ellipse((84, 956, 322, 1006), "#5e7c80", W_DEEP, edge=5)
    ic.poly(chan, W_LIGHT, "#3e5a5e", edge=0, noise=0.1)
    ic.shade(ic.poly_mask([(326, 884), (392, 884), (386, 904), (322, 904)]), (10, 16, 18), 0.55)
    ic.line([(354, 912), (322, 944)], 4, (170, 186, 186, 120))
    ic.line([(150, 974), (184, 974)], 5, (214, 226, 226, 200))  # a single small glint on the pool
    ic.line([(156, 982), (178, 982)], 4, (20, 40, 44, 110))

    # ---- portal: square posts, heavy cap and a gabled plank hood
    ic.beam((314, 906), (318, 580), 42, TIMBER)
    ic.beam((546, 906), (542, 580), 42, TIMBER)
    ic.shade(ic.poly_mask([(304, 580), (330, 580), (326, 906), (302, 906)]), (255, 240, 220), 0.2)
    ic.shade(ic.poly_mask([(338, 590), (522, 590), (522, 640), (338, 640)]), alpha=0.5, blur=10)
    ic.rect((278, 546, 582, 594), "#8e603c", "#5a3c24")
    for x in (302, 558):
        ic.ellipse((x - 10, 560, x + 10, 580), "#4a4648", "#2c2a2c", edge=3)
    gable = [(300, 548), (430, 420), (560, 548)]
    board(ic, gable, "#a07048", "#6a4628",
          joints=[((365, 486), (365, 548)), ((430, 424), (430, 548)), ((495, 486), (495, 548))])
    ic.shade(ic.poly_mask([(300, 548), (560, 548), (548, 536), (312, 536)]), alpha=0.35)
    # barge boards / roof edges, the shingled slopes seen edge-on
    for p0, p1 in (((250, 580), (436, 396)), ((610, 580), (424, 396))):
        ic.line([p0, p1], 44, (40, 28, 20, 230))
        ic.line([p0, p1], 36, (96, 72, 58))
        ic.line([(p0[0], p0[1] - 10), (p1[0], p1[1] - 10)], 12, (140, 112, 92))
    ic.ellipse((418, 384, 442, 408), "#6a4a30", "#3e2a18", edge=3)

    # ---- broad, low heap of dressed ore spreading behind and right of the cart
    mound(ic, 668, 1016, 950, 712, 38, 5, cu_share=0.36, power=0.5)
    for x, y, r in ((884, 760, 30), (954, 806, 30), (930, 880, 28), (984, 910, 26)):
        ic.chunk(x, y, r, CU, CU_DARK, (255, 200, 150))

    # ---- ore cart on the rails, loaded
    cx0, cx1, cy0, cy1 = 580, 872, 758, 906
    ic.shade(ic.mask("ellipse", (570, 900, 890, 956)), alpha=0.5, blur=8)
    ore_lumps(ic, [(612, 758), (660, 738), (712, 726), (766, 730), (818, 742), (850, 760), (640, 770),
                   (690, 758), (744, 756), (798, 764)], 32, 0.36)
    box = [(cx0, cy0), (cx1, cy0), (cx1 - 16, cy1), (cx0 + 16, cy1)]
    board(ic, box, "#9a6c44", "#553a22", joints=[((cx0 + 6, 814), (cx1 - 6, 814)), ((cx0 + 12, 858), (cx1 - 12, 858))])
    ic.shade(ic.poly_mask([(cx0, cy0), (cx1, cy0), (cx1 - 2, cy0 + 14), (cx0 + 2, cy0 + 14)]), (255, 240, 220), 0.25)
    for x in (cx0 + 30, cx1 - 30):
        ic.line([(x, cy0 + 2), (x + (4 if x < 700 else -4), cy1 - 2)], 12, IRON)
    ic.line([(cx0 + 4, cy0 + 6), (cx1 - 4, cy0 + 6)], 10, IRON)
    for x in (cx0 + 62, cx1 - 62):
        ic.ellipse((x - 38, 874, x + 38, 950), "#56504c", "#26221f", edge=6)
        ic.ellipse((x - 11, 901, x + 11, 923), IRON_LT, IRON, edge=3)
    for x in (cx0 + 30, cx1 - 30):
        ic.ellipse((x - 7, cy0 + 16, x + 7, cy0 + 30), IRON_LT, IRON, edge=0)
