"""Copper Mine (copper_mine): a hand windlass over an open shaft below a malachite-stained outcrop.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/copper_mine/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/copper_mine

Composition: a low, weathered tan outcrop with patchy green malachite crusts lying on its ledges and
a few copper-red veins (the exposed lode), a dark shaft mouth in front of it behind a collar of
stacked logs, a hand windlass (A-frame posts, rope drum, crank) lowering a kibble of ore into the
shaft, a basket of ore and a pick bottom left and a rounded heap of green and copper-red ore bottom
right. Tier 0 of the copper chain: shallow workings, no adit (the adit tier adds the timbered
entrance, rails and drainage).
"""

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("schwaz_mine", "clay_pit", "stone_quarry", "sand_pit")

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
COLLAR = (164, 122, 80)
IRON = (46, 44, 46)
DARK = (28, 18, 12)


def log(ic: Icon, p0, p1, w: float, color=TIMBER) -> None:
    """Round log: dark rim, body, lit upper stripe (helper, not in the kit)."""
    ic.line([p0, p1], int(w + 6), (40, 28, 20, 230))
    ic.line([p0, p1], int(w), color)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    n = np.hypot(dx, dy)
    ox, oy = -dy / n * w * 0.22, dx / n * w * 0.22
    if oy > 0:
        ox, oy = -ox, -oy
    lit = tuple(min(255, int(c * 1.3)) for c in color)
    ic.line([(p0[0] + ox, p0[1] + oy), (p1[0] + ox, p1[1] + oy)], max(3, int(w * 0.25)), lit + (170,))


def ore_lumps(ic: Icon, pts, r: float, share_cu: float = 0.3) -> None:
    for x, y in pts:
        rr = r * ic.random.uniform(0.8, 1.15)
        if ic.random.random() < share_cu:
            ic.chunk(x, y, rr, CU, CU_DARK, (255, 200, 150))
        else:
            ic.chunk(x, y, rr, MAL, MAL_DARK, (210, 255, 225))


def crust(ic: Icon, path, depth: float, c1=MAL, c2=MAL_DARK, edge=MAL_EDGE, specks: int = 7) -> None:
    """Malachite crust lying on a ledge or facet (helper, not in the kit).

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


def mound(ic: Icon, x0, x1, base, top, r, rows, cu_share=0.4, body=("#3f5a48", "#1d2b22")) -> None:
    """Rounded ore heap: a domed body with rows of lumps and a soft lit crown (helper, not in the kit)."""
    ts = np.linspace(0, 1, 28)
    prof = lambda t: np.sin(np.pi * t) ** 0.65  # noqa: E731
    outline = [(x0 + (x1 - x0) * t, base - (base - top) * prof(t)) for t in ts]
    ic.poly(outline, body[0], body[1], noise=0.3)
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.55 + (base - top - r * 0.9) * t
        h = np.clip((base - y) / (base - top), 0, 1)
        tt = np.arcsin(h ** (1 / 0.65)) / np.pi
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
    m = ic.poly_mask(outline)
    ic.shade(ic.poly_mask([(x0 + (x1 - x0) * 0.55, top), (x1 + 20, top), (x1 + 20, base), (x0 + (x1 - x0) * 0.62, base)]),
             alpha=0.28, blur=24)
    ic.shade(ic.intersect(m, ic.mask("ellipse", (x0 + (x1 - x0) * 0.15, top - 20, x0 + (x1 - x0) * 0.6, top + (base - top) * 0.5))),
             (255, 240, 220), 0.12, blur=20)


def draw(ic: Icon) -> None:
    # ---- the outcrop: a jagged crag on the left, a lower broken ledge to the right
    crag = [(40, 890), (50, 730), (80, 640), (110, 560), (150, 500), (175, 430), (215, 380), (250, 300),
            (290, 268), (322, 290), (350, 262), (392, 318), (420, 380), (440, 470), (452, 890)]
    ledge = [(330, 890), (360, 560), (410, 500), (470, 470), (530, 438), (585, 452), (640, 430), (690, 470),
             (725, 520), (750, 600), (770, 700), (790, 890)]
    ic.rock(ledge, "#ab9270", ROCK_DARK, facets=4)
    ic.rock(crag, ROCK, ROCK_DARK, facets=4)
    om = ImageChops.lighter(ic.poly_mask(crag), ic.poly_mask(ledge))
    with ic.clipped(om):
        ic.shade(om, (204, 152, 90), 0.24)  # warm the stone towards tan
        for y in (470, 600, 740):
            ic.line([(0, y + 60), (260, y + 15), (520, y - 20), (800, y + 25)], 5, (60, 48, 38, 130))
        # the worked face behind the pit: a shadowed cut into the lode
        cut = [(450, 890), (470, 600), (520, 560), (610, 556), (660, 600), (680, 890)]
        ic.shade(ic.poly_mask(cut), (30, 24, 18), 0.45, blur=10)
        # a faint green bloom where the crusts sit, not everywhere
        for cx, cy, rx, ry in ((280, 330, 60, 30), (560, 470, 70, 26), (190, 520, 50, 30), (690, 610, 40, 30),
                               (160, 650, 60, 30)):
            ic.shade(ic.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry)), (70, 150, 110), 0.25, blur=18)
        # malachite crusts on the ledges and facets, a small azurite patch
        crust(ic, [(232, 336), (262, 300), (292, 290), (322, 312)], 58)
        crust(ic, [(392, 330), (412, 380), (428, 440)], 40, specks=4)
        crust(ic, [(128, 520), (200, 494), (290, 480)], 58)
        crust(ic, [(488, 456), (560, 446), (640, 456)], 66)
        crust(ic, [(70, 652), (160, 634), (262, 614)], 56)
        crust(ic, [(640, 604), (700, 612), (748, 628)], 46, specks=5)
        crust(ic, [(90, 782), (170, 770), (250, 758)], 36, specks=5)
        crust(ic, [(360, 604), (420, 596)], 34, specks=3)
        crust(ic, [(648, 470), (700, 486), (724, 520)], 34, AZ, AZ_DARK, (16, 28, 42), specks=3)
        # thin copper-red veins, two of them low on the face
        ic.vein([(340, 290), (370, 380), (360, 470)], 13, CU, CU_DARK, (60, 26, 14))
        ic.vein([(470, 500), (520, 520), (540, 580)], 12, CU, CU_DARK, (60, 26, 14))
        ic.vein([(96, 700), (126, 740), (118, 800)], 13, CU, CU_DARK, (60, 26, 14))
        ic.vein([(700, 660), (736, 720), (744, 790)], 13, CU, CU_DARK, (60, 26, 14))
        # a few loose green specks across the face
        for _ in range(22):
            x, y = ic.random.uniform(60, 780), ic.random.uniform(300, 860)
            r = ic.random.uniform(4, 9)
            ic.shade(ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), (90, 170, 130), 0.5)
        # darker, grimier foot and an edge rim so the halo ring stays dark
        ic.shade(ic.mask("rectangle", (0, 760, 1024, 1024)), alpha=0.35, blur=40)
        ic.shade(ic.poly_mask([(452, 500), (480, 500), (500, 890), (452, 890)]), alpha=0.3, blur=16)
        rim = ImageChops.subtract(om, om.filter(ImageFilter.MinFilter(31)))
        ic.shade(rim, alpha=0.25, blur=8)
    ic.outline(ledge)
    ic.outline(crag)

    # ---- spoil apron in front
    apron = [(20, 968), (70, 900), (300, 884), (700, 884), (900, 900), (1000, 968)]
    ic.poly(apron, "#8e7656", "#56452f", noise=0.3)
    am = ic.poly_mask(apron)
    with ic.clipped(am):
        for _ in range(26):
            x, y = ic.random.uniform(60, 960), ic.random.uniform(900, 960)
            col = (80, 160, 120) if ic.random.random() < 0.55 else (196, 104, 58)
            ic.shade(ic.mask("ellipse", (x - 9, y - 6, x + 9, y + 6)), col, 0.7)

    # ---- the shaft mouth: a dark elliptical hole under the drum
    ic.shade(ic.mask("ellipse", (344, 752, 632, 900)), alpha=0.45, blur=10)
    ic.ellipse((360, 764, 616, 890), "#1c1510", "#050403", edge=0, noise=0.1)
    ic.shade(ic.mask("ellipse", (374, 764, 602, 800)), (84, 68, 52), 0.3, blur=6)  # lit far lip of the shaft
    ic.shade(ic.mask("ellipse", (400, 800, 576, 884)), alpha=0.55, blur=14)

    # ---- hand windlass: A-frame posts either side, drum, crank, rope and kibble
    for p0, p1 in (((300, 915), (372, 612)), ((426, 900), (372, 612)), ((550, 900), (604, 612)),
                   ((672, 915), (604, 612))):
        log(ic, p0, p1, 30)
    for x in (300, 672):  # contact shadows of the outer legs
        ic.shade(ic.mask("ellipse", (x - 34, 900, x + 34, 930)), alpha=0.45, blur=6)
    # rope and kibble hanging down into the shaft
    ic.line([(488, 650), (488, 796)], 9, (60, 44, 28))
    ic.line([(488, 650), (488, 796)], 4, (170, 140, 96))
    kib = [(452, 806), (524, 806), (516, 866), (460, 866)]
    ic.poly(kib, "#9a6c44", "#553a22", (452, 524), vertical=False, noise=0.2)
    for y in (820, 852):
        ic.line([(454 + (y - 806) * 0.13, y), (522 - (y - 806) * 0.13, y)], 7, IRON)
    ic.shade(ic.poly_mask([(452, 806), (474, 806), (478, 866), (460, 866)]), (255, 240, 220), 0.18)
    ic.shade(ic.poly_mask([(494, 806), (524, 806), (516, 866), (500, 866)]), alpha=0.25)
    ic.shade(ic.poly_mask([(456, 840), (522, 840), (516, 866), (460, 866)]), alpha=0.45, blur=6)  # shaft gloom
    ic.overlay(lambda d: d.arc((458, 758, 518, 836), 200, 340, fill=IRON + (255,), width=7))  # bail
    ic.chunk(468, 802, 18, MAL, MAL_DARK, (210, 255, 225))
    ic.chunk(510, 802, 17, MAL, MAL_DARK, (210, 255, 225))
    ic.chunk(488, 792, 22, CU, CU_DARK, (255, 200, 150))

    # ---- log collar in front of the shaft: stacked horizontal logs, lighter than the frame
    for (x0, x1, y, w, col) in ((350, 628, 916, 22, (150, 110, 72)), (362, 616, 892, 22, COLLAR)):
        log(ic, (x0, y), (x1, y), w, col)
        for x in (x0, x1):
            ic.ellipse((x - w * 0.55, y - w * 0.55, x + w * 0.55, y + w * 0.55), "#c9a276", "#7a5634", edge=3)
    ic.shade(ic.mask("rectangle", (340, 926, 640, 940)), alpha=0.4, blur=6)

    # drum: a rounded log with rope turns
    ic.rect((360, 604, 616, 660), "#8e6040", "#4e331e", noise=0.2)
    ic.shade(ic.mask("rectangle", (360, 612, 616, 626)), (255, 235, 200), 0.25)
    ic.shade(ic.mask("rectangle", (360, 644, 616, 660)), alpha=0.35)
    for x in range(456, 526, 12):
        ic.line([(x, 606), (x + 8, 658)], 5, (176, 146, 100))
    for x in (372, 604):  # post heads over the drum axle
        ic.ellipse((x - 20, 612, x + 20, 652), "#a2744c", "#5e3e24", edge=4)
        ic.ellipse((x - 7, 625, x + 7, 639), "#4a4648", "#2c2a2c", edge=3)
    # crank on the right end
    ic.line([(604, 632), (660, 690)], 16, DARK)
    ic.line([(604, 632), (660, 690)], 9, IRON)
    ic.line([(652, 690), (712, 682)], 18, DARK)
    ic.line([(652, 690), (712, 682)], 11, TIMBER_LT)

    # ---- basket of ore and a pick, bottom left
    ic.line([(250, 945), (150, 700)], 18, DARK)  # pick handle leaning on the rock
    ic.line([(250, 945), (150, 700)], 10, (140, 100, 62))
    ic.overlay(lambda d: d.arc((90, 650, 230, 740), 190, 340, fill=DARK + (255,), width=20))
    ic.overlay(lambda d: d.arc((90, 650, 230, 740), 192, 338, fill=(96, 94, 96, 255), width=12))
    ic.shade(ic.mask("ellipse", (40, 940, 250, 985)), alpha=0.45, blur=8)
    ic.basket(58, 830, 232, 968)
    ore_lumps(ic, [(88, 826), (196, 826), (150, 842)], 28, 0.0)
    for x, y, r in ((118, 812, 30), (178, 806, 28), (140, 790, 26)):
        ic.chunk(x, y, r, CU, CU_DARK, (255, 200, 150))
    ic.shade(ic.mask("rectangle", (58, 846, 232, 868)), alpha=0.3, blur=6)

    # ---- rounded heap of green and copper-red ore, bottom right
    mound(ic, 690, 1016, 982, 740, 40, 5, cu_share=0.34)
    for x, y, r in ((812, 768, 32), (900, 800, 30), (760, 860, 30), (944, 900, 28)):
        ic.chunk(x, y, r, CU, CU_DARK, (255, 200, 150))
