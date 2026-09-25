"""Iron Ore Pit (iron_mine): a timber-framed adit in a rust-veined rock face.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/iron_mine/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/iron_mine

Composition: a craggy outcrop with red hematite veins and an ochre streak, a short timber-set adit
cut into it (dark mouth with receding sets), a heap of red-brown ore bottom right and a wheelbarrow
of ore bottom left. Vanilla pits (clay/sand/stone) are a treadwheel crane over a heap; this one is
read through the rock face, the adit and the rust colour instead.
"""

from contextlib import contextmanager

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 7
REFS = ("clay_pit", "schwaz_mine", "stone_quarry", "sand_pit")

ORE = "#ab4a2a"  # hematite, lit
ORE_DARK = "#4a1e14"
ROCK = "#907f70"
ROCK_DARK = "#4a3d35"
TIMBER = (112, 76, 48)
IRON = (46, 44, 46)
DARK = (28, 18, 12)


@contextmanager
def clipped(ic: Icon, mask: Image.Image):
    """Everything drawn inside the block only lands where ``mask`` is set (helper, not in the kit)."""
    before = ic.image.copy()
    yield
    ic.image.paste(Image.composite(ic.image, before, mask), (0, 0))


def jitter(ic: Icon, cx: float, cy: float, rx: float, ry: float, n: int, j: float = 0.2) -> list:
    angles = np.sort([ic.random.uniform(0, 2 * np.pi) for _ in range(n)])
    return [(cx + np.cos(a) * rx * ic.random.uniform(1 - j, 1 + j), cy + np.sin(a) * ry * ic.random.uniform(1 - j, 1 + j))
            for a in angles]


def chunk(ic: Icon, cx: float, cy: float, r: float, base: str = ORE, dark: str = ORE_DARK) -> None:
    """One ore lump: an irregular rock with a lit top-left facet (helper, not in the kit)."""
    pts = jitter(ic, cx, cy, r, r * 0.75, ic.random.randint(6, 8), 0.15)
    ic.rock(pts, base, dark, facets=2)
    top = [(cx - r * 0.6, cy - r * 0.1), (cx - r * 0.15, cy - r * 0.6), (cx + r * 0.35, cy - r * 0.45),
           (cx - r * 0.05, cy - r * 0.05)]
    ic.shade(ic.poly_mask(top), (255, 190, 150), 0.25)


def vein(ic: Icon, path: list, r: float, c1: str = ORE, c2: str = ORE_DARK) -> None:
    """Ore vein: irregular blobs along a polyline, thickest in the middle (helper, not in the kit)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    ends = np.cumsum(seg)
    total = ends[-1]
    m = Image.new("L", (ic.size, ic.size), 0)
    for d in np.arange(0, total, r * 0.3):
        i = min(int(np.searchsorted(ends, d)), len(seg) - 1)
        t = (d - (ends[i] - seg[i])) / seg[i]
        x, y = pts[i] + (pts[i + 1] - pts[i]) * t
        rr = r * (0.45 + 0.55 * np.sin(np.pi * d / total)) * ic.random.uniform(0.8, 1.1)
        blob = jitter(ic, x + ic.random.uniform(-0.2, 0.2) * r, y, rr, rr * 0.8, 7, 0.15)
        m = ImageChops.lighter(m, ic.poly_mask(blob))
    ic.fill(m, c1, c2, (pts[:, 1].min(), pts[:, 1].max()), noise=0.4)
    edge = ImageChops.subtract(m.filter(ImageFilter.MaxFilter(7)), m)
    ic.shade(edge, (60, 22, 14), 0.6)


def heap(ic: Icon, x0: float, x1: float, base: float, top: float, r: float, rows: int) -> None:
    """Mound of ore lumps: a dark body, then lumps laid back to front (helper, not in the kit)."""
    cx = (x0 + x1) / 2
    body = [(x0, base), (x0 + (cx - x0) * 0.4, base - (base - top) * 0.6), (cx - r * 0.8, top + r * 0.3),
            (cx + r * 0.6, top + r * 0.2), (x1 - (x1 - cx) * 0.35, base - (base - top) * 0.55), (x1, base)]
    ic.poly(body, "#6e3222", "#34160f", noise=0.3)
    for i in range(rows):
        t = i / max(rows - 1, 1)
        y = top + r * 0.55 + (base - top - r * 1.0) * t
        half = (x1 - x0) / 2 * (0.22 + 0.72 * t)
        n = max(1, int(2 * half / (r * 1.3)))
        for j in range(n):
            x = cx - half + (j + 0.5) * 2 * half / n + ic.random.uniform(-10, 10)
            rr = r * ic.random.uniform(0.8, 1.1)
            if ic.random.random() < 0.12:
                chunk(ic, x, y, rr, "#6a5452", "#2e2322")  # dark specular hematite
            else:
                chunk(ic, x, y, rr)


def draw(ic: Icon) -> None:
    # ---- craggy outcrop (main structure): tall crag left, broad face centre, lower shoulder right
    crag = [(40, 900), (55, 640), (95, 540), (110, 470), (150, 400), (175, 330), (215, 300), (250, 255),
            (300, 262), (330, 235), (370, 270), (395, 290), (410, 360), (430, 420), (440, 900)]
    face = [(210, 900), (240, 560), (300, 430), (350, 410), (400, 350), (455, 338), (500, 300), (555, 322),
            (600, 318), (650, 370), (690, 400), (720, 470), (760, 520), (775, 600), (805, 700), (820, 900)]
    ic.rock(crag, "#9c8d7f", ROCK_DARK, facets=3)
    ic.rock(face, ROCK, ROCK_DARK, facets=4)
    outcrop = Image.composite(ic.poly_mask(crag), ic.poly_mask(face), ic.poly_mask(crag))

    with clipped(ic, outcrop):
        # strata
        for y in (470, 610, 750):
            ic.line([(0, y + 40), (300, y), (560, y - 30), (900, y + 20)], 5, (55, 45, 40, 140))
        # red hematite veins and ochre patches, as blob clusters
        ic.shade(ic.mask("rectangle", (0, 600, 1024, 1024)), (150, 60, 35), 0.22, blur=60)  # iron staining
        vein(ic, [(560, 320), (600, 470), (650, 640), (660, 900)], 40)
        vein(ic, [(215, 290), (190, 470), (205, 650), (150, 900)], 34)
        vein(ic, [(410, 355), (490, 330)], 24)
        vein(ic, [(735, 480), (775, 640), (790, 860)], 42, "#c89a48", "#8a6226")
        # shadow of the crag on the face, and dark lower edge
        ic.shade(ic.poly_mask([(430, 420), (470, 400), (480, 900), (440, 900)]), alpha=0.35, blur=16)
        ic.shade(ic.mask("rectangle", (0, 820, 1024, 1024)), alpha=0.3, blur=30)
        rim = ImageChops.subtract(outcrop, outcrop.filter(ImageFilter.MinFilter(31)))
        ic.shade(rim, alpha=0.25, blur=8)  # darker rim so the halo ring stays dark
    ic.outline(crag)
    ic.outline(face)

    # ---- adit: dark mouth, receding timber sets, front set
    mouth = [(378, 905), (400, 520), (592, 520), (614, 905)]
    ic.poly(mouth, "#2a201a", "#0c0907", edge=0, noise=0.1)
    for k, (inset, top) in enumerate(((50, 590), (88, 650), (116, 695))):
        col = tuple(int(c * (0.6 - 0.15 * k)) for c in TIMBER)
        w = 20 - 5 * k
        ic.beam((378 + inset, 905), (390 + inset, top), w, col)
        ic.beam((614 - inset, 905), (602 - inset, top), w, col)
        ic.beam((378 + inset - 10, top), (614 - inset + 10, top), w, col)
    ic.shade(ic.poly_mask(mouth), (0, 0, 0), 0.3, blur=20)
    # front set: two leaning posts, a heavy cap and a lintel shadow
    ic.beam((368, 910), (400, 510), 40, TIMBER)
    ic.beam((624, 910), (592, 510), 40, TIMBER)
    ic.shade(ic.poly_mask([(400, 515), (592, 515), (592, 575), (400, 575)]), (0, 0, 0), 0.5, blur=10)
    ic.rect((336, 462, 656, 516), "#8e603c", "#5a3c24")
    for x in (360, 632):
        ic.ellipse((x - 10, 479, x + 10, 499), "#4a4648", "#2c2a2c", edge=3)  # peg heads
    ic.shade(ic.poly_mask([(368, 516), (386, 516), (372, 910), (352, 910)]), (255, 240, 220), 0.18)

    # ---- red and ochre spoil apron
    apron = [(20, 965), (70, 905), (300, 890), (660, 892), (900, 905), (1000, 965)]
    ic.poly(apron, "#8e5634", "#553020", noise=0.3)
    ic.shade(ic.poly_mask([(110, 905), (330, 898), (350, 950), (90, 955)]), (205, 150, 60), 0.5, blur=8)
    ic.shade(ic.poly_mask([(420, 900), (600, 898), (620, 955), (400, 955)]), (170, 60, 35), 0.45, blur=8)

    # pick leaning on the right post
    ic.line([(650, 912), (690, 700)], 18, DARK)
    ic.line([(650, 912), (690, 700)], 10, (140, 100, 62))
    ic.draw.arc((630, 668, 760, 752), 190, 330, fill=DARK + (255,), width=20)
    ic.draw.arc((630, 668, 760, 752), 192, 328, fill=IRON + (255,), width=12)

    # ---- hematite heap, bottom right
    heap(ic, 650, 1015, 980, 640, 58, 5)

    # ---- wheelbarrow of ore, bottom left
    ic.line([(170, 875), (345, 930)], 20, DARK)  # handle
    ic.line([(170, 875), (345, 930)], 12, TIMBER)
    ic.line([(255, 870), (268, 955)], 18, DARK)  # leg
    ic.line([(255, 870), (268, 955)], 10, (90, 62, 40))
    for x, y, r in ((115, 768, 50), (192, 745, 60), (268, 770, 48), (155, 792, 42), (232, 792, 44)):
        chunk(ic, x, y, r)
    tray = [(65, 785), (310, 785), (278, 885), (108, 885)]
    ic.poly(tray, "#a2704a", "#5e3e24", noise=0.2)
    for y in (820, 853):
        ic.line([(72 + (y - 785) * 0.42, y), (305 - (y - 785) * 0.3, y)], 4, (60, 40, 24))
    ic.shade(ic.poly_mask([(65, 785), (310, 785), (307, 797), (68, 797)]), (255, 240, 220), 0.25)
    ic.ellipse((28, 858, 132, 962), "#8a6040", "#4f3420", edge=8)  # wheel, in front of the tray
    for a in np.linspace(0, np.pi, 4, endpoint=False):
        ic.line([(80 + np.cos(a) * 46, 910 + np.sin(a) * 46), (80 - np.cos(a) * 46, 910 - np.sin(a) * 46)], 5,
                (60, 40, 24))
    ic.ellipse((68, 898, 92, 922), "#4a4648", "#2c2a2c", edge=3)
