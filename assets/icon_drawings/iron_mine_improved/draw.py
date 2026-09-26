"""Iron Mine (iron_mine_improved): a heavy timber windlass over a cribbed shaft beside a rust-veined crag.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/iron_mine_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/iron_mine_improved

Composition: tier 2 of the iron chain. The Iron Ore Pit's rust-veined crag moves to the back left; in
front of it a log-cribbed shaft collar carries a stout windlass frame that rises above the crag (lit
rope drum with iron end hoops, a crank kept inside the silhouette, an ore kibble on the rope against
the planked shaft lining). A muted hematite heap bottom right and a laden mine tub bottom left.
The tiers differ in the headgear: the Deep Iron Mine adds a tall headframe, a pumping wheel and a
stone winding house.
"""

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 11
REFS = ("clay_pit", "schwaz_mine", "stone_quarry", "iron_mill")

ORE = "#ab4a2a"  # hematite, lit
ORE_DARK = "#4a1e14"
HEAP_ORE = ("#9a4a31", "#461f16")  # heap lumps: a touch darker and less red than the lit ore
HEAP_BODY = ("#663023", "#30150f")
ROCK = "#907f70"
ROCK_DARK = "#4a3d35"
TIMBER = (112, 76, 48)
TIMBER_LIT = (146, 102, 64)
IRON = (46, 44, 46)
DARK = (28, 18, 12)


def inside(mask: Image.Image, x: float, y: float) -> bool:
    return 0 <= x < mask.width and 0 <= y < mask.height and mask.getpixel((int(x), int(y))) > 0


def painterly_rock(ic: Icon, pts: list, base: str, dark: str, strokes: int = 9) -> Image.Image:
    """Rock mass shaded by value instead of flat facets: broad light/dark masses, soft blotches and
    broken highlight strokes with a crack under each (helper, not in the kit). Returns the mask."""
    ic.rock(pts, base, dark, facets=0)
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    with ic.clipped(m):
        ic.shade(ic.poly_mask(ic.jitter(x0 + w * 0.32, y0 + h * 0.28, w * 0.34, h * 0.26, 10, 0.3)),
                 (255, 244, 226), 0.16, blur=45)
        ic.shade(ic.poly_mask(ic.jitter(x0 + w * 0.78, y0 + h * 0.72, w * 0.4, h * 0.34, 10, 0.3)),
                 (0, 0, 0), 0.2, blur=55)
        for _ in range(10):
            cx, cy = ic.random.uniform(x0, x1), ic.random.uniform(y0, y1)
            r = ic.random.uniform(30, 70)
            light = ic.random.random() < 0.45
            ic.shade(ic.poly_mask(ic.jitter(cx, cy, r, r * 0.7, 8, 0.3)),
                     (255, 240, 215) if light else (40, 30, 26), ic.random.uniform(0.07, 0.13), blur=18)
        n = 0
        tries = 0
        while n < strokes and tries < 200:
            tries += 1
            sx, sy = ic.random.uniform(x0 + 20, x1 - 20), ic.random.uniform(y0 + 30, y0 + h * 0.8)
            if not inside(m, sx, sy):
                continue
            n += 1
            ang = np.radians(ic.random.uniform(95, 135) if sx < x0 + w * 0.55 else ic.random.uniform(45, 85))
            length = ic.random.uniform(50, 110)
            d = 0.0
            while d < length:
                seg = ic.random.uniform(14, 34)
                a = (sx + np.cos(ang) * d, sy + np.sin(ang) * d)
                b = (sx + np.cos(ang) * (d + seg) + ic.random.uniform(-4, 4), sy + np.sin(ang) * (d + seg))
                ic.line([a, b], int(ic.random.uniform(5, 8)), (222, 208, 186, int(ic.random.uniform(30, 60))))
                ic.line([(a[0] + 6, a[1] + 5), (b[0] + 6, b[1] + 5)], 4, (48, 40, 36, 70))
                d += seg + ic.random.uniform(10, 26)
    return m


def log(ic: Icon, x0: float, x1: float, y: float, h: float, tone: float = 1.0) -> None:
    """Horizontal round log: lit upper half, dark underside, grain streaks (helper, not in the kit)."""
    c = tuple(int(v * tone) for v in TIMBER_LIT)
    d = tuple(int(v * tone * 0.45) for v in TIMBER_LIT)
    ic.poly([(x0, y), (x1, y), (x1, y + h), (x0, y + h)], c, d, edge=0, noise=0.25)
    for k in range(3):
        yy = y + h * ic.random.uniform(0.25, 0.7)
        xa = ic.random.uniform(x0, x1 - 60)
        ic.line([(xa, yy), (xa + ic.random.uniform(40, 110), yy + ic.random.uniform(-2, 2))], 3, (60, 38, 22, 150))
    ic.line([(x0, y + h), (x1, y + h)], 4)


def log_end(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Sawn log end with rings (helper, not in the kit)."""
    ic.ellipse((cx - r, cy - r * 0.95, cx + r, cy + r * 0.95), "#b88c5c", "#6a4a2c", edge=4)
    ic.overlay(lambda d: d.ellipse((cx - r * 0.5, cy - r * 0.45, cx + r * 0.5, cy + r * 0.45),
                                   outline=(90, 60, 34, 170), width=3))


def tub(ic: Icon, x0: float, x1: float, top: float, bot: float) -> None:
    """Plank mine tub heaped with ore, iron-banded, on two small wheels (helper, not in the kit)."""
    w = x1 - x0
    for x, y, r in ((x0 + w * 0.18, top - 12, 42), (x0 + w * 0.45, top - 30, 52), (x0 + w * 0.75, top - 16, 44),
                    (x0 + w * 0.32, top + 4, 36), (x0 + w * 0.62, top + 2, 38)):
        ic.chunk(x, y, r, ORE, ORE_DARK)
    body = [(x0, top), (x1, top), (x1 - w * 0.07, bot), (x0 + w * 0.07, bot)]
    ic.poly(body, "#9a6a44", "#523620", noise=0.25)
    for f in (0.36, 0.68):
        y = top + (bot - top) * f
        ic.line([(x0 + w * 0.07 * f, y), (x1 - w * 0.07 * f, y)], 4, (58, 38, 22, 200))
    for fx in (0.14, 0.86):
        x = x0 + w * fx
        ic.line([(x, top + 2), (x + (0.5 - fx) * w * 0.07, bot - 2)], 12, IRON)
    ic.shade(ic.poly_mask([body[0], body[1], (x1 - 3, top + 14), (x0 + 3, top + 14)]), (255, 235, 210), 0.25)
    for cx in (x0 + w * 0.24, x1 - w * 0.24):
        ic.ellipse((cx - 34, bot - 22, cx + 34, bot + 44), "#4c4a4c", "#1e1c1e", edge=5)
        ic.ellipse((cx - 9, bot + 2, cx + 9, bot + 20), "#7a7274", "#3a3638", edge=3)


def drum(ic: Icon, d0: float, d1: float, y0: float, y1: float) -> None:
    """Horizontal rope drum: a lit round log with rope turns and dark iron end hoops (helper)."""
    h = y1 - y0
    body = ic.mask("rectangle", (d0, y0, d1, y1))
    ic.fill(body, (176, 128, 84), (92, 60, 36), (y0, y1), noise=0.22)
    # cylinder: bright band a third down, core shadow low, reflected light at the very bottom
    ic.shade(ic.mask("rectangle", (d0, y0 + h * 0.14, d1, y0 + h * 0.36)), (255, 236, 200), 0.45, blur=5)
    ic.shade(ic.mask("rectangle", (d0, y0 + h * 0.66, d1, y1 - h * 0.1)), alpha=0.45, blur=5)
    # rope turns over the middle, lit on top
    for x in np.arange(d0 + 40, d1 - 40, 16):
        ic.line([(x, y0 + 4), (x + 7, y1 - 4)], 6, (74, 54, 32, 120))
        ic.line([(x + 3, y0 + 8), (x + 5, y0 + h * 0.4)], 5, (214, 186, 134, 130))
    for x in (d0 + 14, d1 - 14):  # iron end hoops
        ic.line([(x, y0 - 2), (x, y1 + 2)], 16, (30, 26, 26))
        ic.line([(x - 3, y0 + h * 0.18), (x - 3, y0 + h * 0.34)], 5, (120, 112, 110))
    ic.outline([(d0, y0), (d1, y0), (d1, y1), (d0, y1)], 5)


def windlass(ic: Icon, x0: float, x1: float, top: float) -> None:
    """Log-cribbed shaft collar with a stout timber windlass frame, drum, crank and ore kibble (helper)."""
    cx = (x0 + x1) / 2
    pl, pr = x0 + 64, x1 - 64  # posts
    # boarded back of the frame in shadow, so the frame reads as one solid headgear and the lit drum
    # stands out against it
    ic.poly([(pl, top + 40), (pr, top + 40), (pr, 530), (pl, 530)], "#5e4430", "#3a291c", noise=0.25, edge=0)
    for x in np.arange(pl + 30, pr - 10, 34):
        ic.line([(x + ic.random.uniform(-3, 3), top + 60), (x + ic.random.uniform(-3, 3), 528)], 4, (30, 20, 14, 140))
    # planked shaft lining behind the kibble (the far crib wall, lit)
    lin = [(pl + 20, 520), (pr - 20, 520), (pr - 20, 690), (pl + 20, 690)]
    ic.poly(lin, "#a88a66", "#6e5438", noise=0.25, edge=0)
    for x in np.arange(pl + 44, pr - 26, 30):
        ic.line([(x + ic.random.uniform(-3, 3), 522), (x + ic.random.uniform(-3, 3), 688)], 4, (70, 50, 32, 150))
    ic.shade(ic.mask("rectangle", (pl + 20, 520, pr - 20, 560)), alpha=0.35, blur=12)  # under the drum
    # collar top and the dark shaft mouth, now a low sliver
    ic.poly([(x0 - 10, 712), (x1 + 10, 712), (x1 - 16, 672), (x0 + 16, 672)], "#9a6c44", "#6a4428", noise=0.25)
    ic.poly([(x0 + 52, 706), (x1 - 52, 706), (x1 - 64, 684), (x0 + 64, 684)], "#1c140e", "#060403", edge=0,
            noise=0.05)
    BR = (104, 70, 44)
    # outer raking struts, posts, knee braces: 1.5x the old sections, same warm timber as the adit
    ic.beam((x0 - 26, 712), (pl + 4, 470), 34, BR)
    ic.beam((x1 + 26, 712), (pr - 4, 470), 34, BR)
    for x, lean in ((pl, 3), (pr, -3)):
        ic.beam((x, 712), (x + lean, top + 50), 58, TIMBER)
        ic.shade(ic.poly_mask([(x - 26, top + 60), (x - 10, top + 60), (x - 10, 712), (x - 26, 712)]),
                 (255, 236, 205), 0.28)
        ic.shade(ic.poly_mask([(x + 12, top + 60), (x + 28, top + 60), (x + 28, 712), (x + 12, 712)]), alpha=0.3)
    ic.beam((pl + 26, top + 130), (pl + 64, top + 62), 26, BR)
    ic.beam((pr - 26, top + 130), (pr - 64, top + 62), 26, BR)
    # heavy cap beam with a lit top face and pegs
    ic.rect((x0 + 4, top, x1 - 4, top + 60), "#8e603c", "#5a3c24")
    ic.shade(ic.mask("rectangle", (x0 + 6, top + 2, x1 - 6, top + 16)), (255, 240, 215), 0.35)
    for x in (pl, pr):
        ic.ellipse((x - 10, top + 22, x + 10, top + 42), "#4a4648", "#2c2a2c", edge=3)
    ic.shade(ic.mask("rectangle", (pl + 28, top + 60, pr - 28, top + 110)), alpha=0.35, blur=12)
    # drum with its axle bosses on the posts
    d0, d1 = pl + 26, pr - 26
    drum(ic, d0, d1, 436, 512)
    for x in (pl, pr):
        ic.ellipse((x - 16, 456, x + 16, 492), "#5c585a", "#1e1c1e", edge=4)
    # short crank on the right post, bent down so it stays inside the silhouette
    ax = pr + 26
    for p, q in (((ax, 474), (ax + 34, 474)), ((ax + 34, 474), (ax + 40, 540))):
        ic.line([p, q], 18, DARK)
        ic.line([p, q], 10, (84, 80, 84))
    ic.beam((ax + 40, 540), (ax + 74, 546), 16, TIMBER_LIT)
    # rope down to an ore kibble, seen against the lit lining
    ic.line([(cx + 20, 512), (cx + 16, 598)], 10, DARK)
    ic.line([(cx + 20, 512), (cx + 16, 598)], 5, (196, 164, 112))
    ic.line([(cx - 20, 622), (cx + 16, 596), (cx + 52, 622)], 6, (50, 46, 48))
    for dx, y, r in ((-12, 620, 24), (16, 612, 28), (44, 622, 22)):
        ic.chunk(cx + dx, y, r, ORE, ORE_DARK)
    ic.poly([(cx - 30, 622), (cx + 62, 622), (cx + 52, 680), (cx - 20, 680)], "#6e4e32", "#34221a")
    ic.line([(cx - 28, 640), (cx + 60, 640)], 8, IRON)
    ic.line([(cx - 22, 668), (cx + 54, 668)], 8, IRON)
    ic.shade(ic.poly_mask([(cx - 30, 622), (cx - 16, 622), (cx - 8, 680), (cx - 20, 680)]), (255, 236, 205), 0.2)
    ic.shade(ic.poly_mask([(cx - 24, 684), (cx + 70, 684), (cx + 76, 700), (cx - 18, 700)]), alpha=0.35, blur=8)
    # collar front: stacked logs with crib corners
    for i, y in enumerate(range(712, 880, 42)):
        log(ic, x0 - 6, x1 + 6, y, 42, 1.0 - 0.07 * i)
    ic.shade(ic.mask("rectangle", (x0, 712, x1, 740)), alpha=0.25, blur=6)
    for y in range(733, 880, 42):
        log_end(ic, x0 - 14, y, 22)
        log_end(ic, x1 + 14, y + 4, 22)
    ic.shade(ic.mask("rectangle", (x0 - 40, 840, x1 + 40, 900)), alpha=0.3, blur=14)


def draw(ic: Icon) -> None:
    # ---- rock shoulder behind the shaft; broad on the right so the crank sits inside it
    shoulder = [(420, 905), (450, 640), (520, 580), (590, 560), (640, 520), (700, 535), (770, 500), (850, 462),
                (912, 498), (955, 565), (980, 650), (994, 740), (996, 905)]
    sm = painterly_rock(ic, shoulder, "#8a786a", ROCK_DARK, strokes=3)
    with ic.clipped(sm):
        ic.shade(ic.mask("rectangle", (0, 640, 1024, 1024)), (150, 60, 35), 0.22, blur=50)
        ic.vein([(770, 510), (790, 580), (815, 660), (812, 720), (840, 800)], 24, ORE, ORE_DARK)
        ic.shade(ic.poly_mask(ic.jitter(950, 720, 26, 90, 9, 0.35)), (176, 136, 70), 0.3, blur=16)  # ochre stain
        ic.shade(ic.mask("rectangle", (0, 760, 1024, 1024)), alpha=0.35, blur=30)
    ic.outline(shoulder)

    # ---- rust-veined crag, left: the Iron Ore Pit rock with its adit, now one part of the works
    crag = [(30, 905), (40, 730), (70, 650), (95, 600), (120, 530), (160, 490), (180, 440), (225, 415), (250, 370),
            (285, 336), (318, 362), (345, 350), (380, 310), (410, 350), (440, 372), (470, 430), (500, 470),
            (530, 540), (548, 600), (575, 660), (590, 740), (600, 905)]
    cm = painterly_rock(ic, crag, "#9c8d7f", ROCK_DARK, strokes=7)
    with ic.clipped(cm):
        ic.shade(ic.mask("rectangle", (0, 620, 1024, 1024)), (150, 60, 35), 0.25, blur=50)
        # main vein: wandering, thick and thin in turn, with a side branch
        ic.vein([(388, 322), (420, 400), (432, 450)], 30, ORE, ORE_DARK)
        ic.vein([(432, 450), (462, 540), (468, 600)], 20, ORE, ORE_DARK)
        ic.vein([(468, 600), (490, 690), (484, 760), (515, 905)], 36, ORE, ORE_DARK)
        ic.vein([(440, 470), (492, 500), (520, 540)], 12, ORE, ORE_DARK)
        # second vein: short and broken
        ic.vein([(282, 348), (262, 410), (256, 450)], 20, ORE, ORE_DARK)
        ic.vein([(248, 492), (236, 540)], 11, ORE, ORE_DARK)
        # muted ochre staining on the left flank, soft, not a stripe
        ic.shade(ic.poly_mask(ic.jitter(110, 700, 34, 140, 10, 0.35)), (176, 136, 70), 0.3, blur=18)
        ic.shade(ic.mask("rectangle", (0, 820, 1024, 1024)), alpha=0.3, blur=30)
        rim = ImageChops.subtract(cm, cm.filter(ImageFilter.MinFilter(31)))
        ic.shade(rim, alpha=0.25, blur=8)
    ic.outline(crag)

    # ---- adit with receding timber sets
    mouth = [(212, 905), (230, 610), (378, 610), (396, 905)]
    ic.poly(mouth, "#2a201a", "#0c0907", edge=0, noise=0.1)
    for k, (inset, top) in enumerate(((40, 670), (70, 720), (92, 755))):
        col = tuple(int(c * (0.6 - 0.15 * k)) for c in TIMBER)
        w = 18 - 5 * k
        ic.beam((212 + inset, 905), (222 + inset, top), w, col)
        ic.beam((396 - inset, 905), (386 - inset, top), w, col)
        ic.beam((212 + inset - 8, top), (396 - inset + 8, top), w, col)
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.3, blur=20)
    ic.beam((202, 910), (230, 600), 36, TIMBER)
    ic.beam((406, 910), (378, 600), 36, TIMBER)
    ic.shade(ic.poly_mask([(230, 604), (378, 604), (378, 660), (230, 660)]), (0, 0, 0), 0.5, blur=10)
    ic.rect((180, 556, 428, 606), "#8e603c", "#5a3c24")
    for x in (200, 408):
        ic.ellipse((x - 9, 572, x + 9, 590), "#4a4648", "#2c2a2c", edge=3)
    ic.shade(ic.poly_mask([(202, 606), (218, 606), (204, 910), (186, 910)]), (255, 240, 220), 0.18)

    # ---- ground apron in red and ochre spoil
    apron = [(15, 970), (50, 900), (300, 885), (700, 885), (960, 900), (1010, 970)]
    ic.poly(apron, "#8e5634", "#553020", noise=0.3)
    ic.shade(ic.poly_mask([(240, 905), (380, 900), (400, 955), (220, 958)]), (170, 60, 35), 0.45, blur=8)
    ic.shade(ic.poly_mask([(430, 900), (560, 898), (580, 950), (420, 952)]), (190, 145, 70), 0.3, blur=8)

    # ---- windlass shaft, right of the crag; its frame rises above the crag peak
    windlass(ic, 560, 880, 244)

    # ---- hematite heap (muted, flatter top), bottom right, and a laden tub bottom left
    ic.heap(720, 1020, 982, 700, 46, 6, body=HEAP_BODY, lump=HEAP_ORE, odd_share=0.08)
    tub(ic, 22, 252, 836, 918)
