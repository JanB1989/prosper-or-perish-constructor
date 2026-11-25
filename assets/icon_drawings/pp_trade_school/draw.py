"""Trade School (pp_trade_school): a reckoning school in a merchant town, where a master teaches merchants' sons
arithmetic and bookkeeping (scuola d'abaco, Rechenschule).

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor-locplan/assets/icon_drawings/pp_trade_school/draw.py \
    --out ../ProsperOrPerishConstructor-locplan/artifacts/icons/pp_trade_school

Identity: a big teaching counting frame (abacus) on an easel stand in front, with an open ledger and a quill on its
tray; behind it a brick merchant house with a stepped gable and a loft door under its hoist beam, and a lower
stuccoed schoolroom wing with an arcade. A brass balance hangs as the house sign from an iron bracket. The easel
repeats the Village School's slate, so the two schools read as one family. Helpers ``union``, ``tint``, ``stones``,
``shingles`` are copied from the Cookshop; new local helpers: ``bricks``, ``coping``, ``arch_mask``,
``stone_window``, ``abacus``, ``ledger``, ``hanging_balance``, ``quill``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 31
REFS = ("counting_house", "library", "marketplace", "university")

BASE = 900
X0, X1 = 176, 520  # merchant house front
GCX = (X0 + X1) / 2
WX1 = 872  # schoolroom wing right wall
WEAVE, WRIDGE = 584, 440
IRON = (34, 31, 30)
EDGE = (40, 28, 20, 200)
STONE = ("#d6c8a6", "#94866a")
BEADS = [3, 7, 1, 5, 9, 2]  # beads counted out to the left on each rod


# ---------------------------------------------------------------- helpers (shared with the Cookshop)
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
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
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
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


# ---------------------------------------------------------------- helpers (new for the Trade School)
def bricks(ic: Icon, mask: Image.Image, box, colors=("#b46a44", "#5e2e1e"), course: float = 18,
           brick: float = 46) -> None:
    """Brick facade: per-brick tone, thin pale mortar, a few dark burnt headers, soft weathering."""
    x0, y0, x1, y1 = box
    ic.fill(mask, colors[0], colors[1], (y0, y1), noise=0.18, chroma=0.06)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    for k, y in enumerate(np.arange(y0, y1, course)):
        off = (k % 2) * brick / 2
        for x in np.arange(x0 - brick + off, x1, brick):
            t = rnd(-1, 1)
            if ic.random.random() < 0.12:
                d.rectangle((x + 2, y + 2, x + brick - 2, y + course - 2), fill=(40, 16, 10, 90))
            else:
                d.rectangle((x + 2, y + 2, x + brick - 2, y + course - 2),
                            fill=(20, 8, 4, int(-t * 50)) if t < 0 else (255, 214, 180, int(t * 40)))
            d.line([(x, y), (x, y + course)], fill=(206, 186, 160, 100), width=3)
        d.line([(x0, y), (x1, y)], fill=(206, 186, 160, 110), width=3)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def coping(ic: Icon, x0, x1, y, h=22) -> None:
    """Stone coping slab on a gable step: lit top, overhang shadow below."""
    ic.rect((x0 - 10, y - h, x1 + 10, y), STONE[0], STONE[1], edge=4)
    ic.line([(x0 - 8, y - h + 4), (x1 + 8, y - h + 4)], 3, (255, 248, 228, 120))


def arch_mask(ic: Icon, x0, x1, top, bottom) -> Image.Image:
    w = x1 - x0
    return union(ic.mask("ellipse", (x0, top, x1, top + w)), ic.mask("rectangle", (x0, top + w / 2, x1, bottom)))


def stone_window(ic: Icon, x0, y0, x1, y1, clip, cross: bool = True) -> None:
    """Window in a dressed stone frame with a stone cross mullion, dark leaded glass, a shadow under the sill."""
    ic.rect((x0 - 16, y0 - 16, x1 + 16, y1 + 20), STONE[0], STONE[1], edge=4)
    glass = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(glass, "#46484e", "#16161a", (y0, y1), noise=0.08)
    tint(ic, ic.poly_mask([(x0, y0), (x1, y0), (x0, y0 + (y1 - y0) * 0.45)]), glass, (170, 180, 192), 0.18, 4)
    ic.overlay(lambda d: [d.line([(x0, y), (x1, y)], fill=(70, 66, 62, 200), width=3)
                          for y in np.arange(y0 + 18, y1, 18)], glass)
    if cross:
        xm, ym = (x0 + x1) / 2, y0 + (y1 - y0) * 0.38
        ic.line([(xm, y0), (xm, y1)], 12, STONE[1])
        ic.line([(x0, ym), (x1, ym)], 12, STONE[1])
        ic.line([(xm - 3, y0), (xm - 3, y1)], 4, (240, 230, 206, 150))
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)
    tint(ic, ic.mask("rectangle", (x0 - 16, y1 + 20, x1 + 22, y1 + 44)), clip, (0, 0, 0), 0.3, 6)


def abacus(ic: Icon, x0, y0, x1, y1) -> None:
    """A teaching counting frame: a stout wooden frame, six iron rods, ten beads on each in two colours by fives,
    some counted out to the left."""
    w, h = x1 - x0, y1 - y0
    bar = 22
    outer = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(outer, "#b8844e", "#4e3018", radial=(x0 + w * 0.15, y0, w * 1.3), noise=0.16)
    inner = ic.mask("rectangle", (x0 + bar, y0 + bar, x1 - bar, y1 - bar))
    ic.fill(inner, "#3a2a1c", "#160e08", (y0, y1), noise=0.1)
    tint(ic, ic.mask("rectangle", (x0 + bar, y0 + bar, x1 - bar, y0 + bar + 30)), inner, (0, 0, 0), 0.45, 8)
    rods = len(BEADS)
    pitch = (h - 2 * bar) / rods
    bh = pitch * 0.44  # bead half-height
    bwid = min(pitch * 0.36, (w - 2 * bar - 40) / 20)  # bead half-width
    for i, left in enumerate(BEADS):
        y = y0 + bar + pitch * (i + 0.5)
        ic.line([(x0 + bar, y + 3), (x1 - bar, y + 3)], 3, (10, 6, 4, 160))
        ic.line([(x0 + bar, y), (x1 - bar, y)], 4, (168, 160, 150))
        xs = [x0 + bar + bwid + 3 + k * (bwid * 2 + 1) for k in range(left)]
        xs += [x1 - bar - bwid - 3 - k * (bwid * 2 + 1) for k in range(10 - left)][::-1]
        for k, x in enumerate(xs):
            red = k < 5
            col = ("#dc6a40", "#701e0e") if red else ("#f2e6c4", "#8a7650")
            box = (x - bwid, y - bh, x + bwid, y + bh)
            ic.fill(ic.mask("ellipse", box), col[0], col[1], radial=(x - bwid * 0.5, y - bh * 0.6, bh * 1.9), noise=0.08)
            ic.overlay(lambda d, box=box: d.ellipse(box, outline=(30, 14, 8, 140), width=2))
            ic.draw.ellipse((x - bwid * 0.6, y - bh * 0.7, x - bwid * 0.05, y - bh * 0.3), fill=(255, 248, 230, 255))
    tint(ic, ic.mask("rectangle", (x0, y0, x0 + bar, y1)), outer, (255, 236, 200), 0.2, 4)
    tint(ic, ic.mask("rectangle", (x1 - bar, y0, x1, y1)), outer, (0, 0, 0), 0.3, 4)
    for xx, yy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):  # iron corner plates
        ic.rect((xx - 12, yy - 12, xx + 12, yy + 12), "#6a6460", "#2a2624", edge=3)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 5)
    ic.outline([(x0 + bar, y0 + bar), (x1 - bar, y0 + bar), (x1 - bar, y1 - bar), (x0 + bar, y1 - bar)], 4)


def ledger(ic: Icon, cx, cy, w, h, degrees=0.0) -> None:
    """An open ledger: two pages of ruled columns with figures, a red rule down each page, a ribbon, a dark cover."""
    def P(pts):
        return ic.rotate(pts, (cx, cy), degrees)

    cover = P([(-w / 2 - 10, -h / 2 + 8), (w / 2 + 10, -h / 2 + 8), (w / 2 + 14, h / 2 + 12), (-w / 2 - 14, h / 2 + 12)])
    ic.fill(ic.poly_mask(cover), "#6a3422", "#2c120a", noise=0.12)
    ic.outline(cover, 4, EDGE)
    for side in (-1, 1):
        ts = np.linspace(0, 1, 16)
        top = [(side * w / 2 * t, -h / 2 + 6 * math.sin(math.pi * t) - (1 - t) * 8) for t in ts]
        bot = [(side * w / 2 * t, h / 2 - (1 - t) * 4) for t in ts[::-1]]
        page = P(top + bot)
        pm = ic.poly_mask(page)
        ic.fill(pm, "#f4eacc", "#c2b08a", radial=(cx - w * 0.3, cy - h * 0.5, w * 0.9), noise=0.06, chroma=0.03)
        tint(ic, ic.poly_mask(P([(0, -h / 2 - 10), (side * w * 0.14, -h / 2), (side * w * 0.14, h / 2), (0, h / 2 + 4)])),
             pm, (60, 40, 20), 0.35, 8)  # gutter shadow

        def rows(d, side=side):
            for k in range(6):
                yy = -h / 2 + 18 + k * (h - 30) / 5.5
                a, b = P([(side * w * 0.08, yy), (side * w * 0.46, yy)])
                d.line([a, b], fill=(110, 96, 74, 120), width=2)
                for j in range(3):
                    x = side * (w * 0.12 + j * w * 0.1)
                    p, q = P([(x, yy - 8), (x + side * w * 0.06, yy - 8)])
                    d.line([p, q], fill=(52, 36, 22, 210), width=4)
            a, b = P([(side * w * 0.36, -h / 2 + 8), (side * w * 0.36, h / 2 - 6)])
            d.line([a, b], fill=(170, 50, 36, 200), width=3)

        ic.overlay(rows, pm)
        ic.outline(page, 3, (90, 70, 46, 200))


def quill(ic: Icon, nib, tip, width=26) -> None:
    """A goose quill: a pale vane along the shaft, lit on one side, the nib dark with ink."""
    nib, tip = np.array(nib, float), np.array(tip, float)
    d = (tip - nib) / np.linalg.norm(tip - nib)
    n = np.array([-d[1], d[0]])
    L = np.linalg.norm(tip - nib)
    vane = [tuple(nib + d * L * 0.22)] + [tuple(nib + d * L * t + n * width * math.sin(math.pi * (t - 0.22) / 0.78) ** 0.7)
                                          for t in np.linspace(0.25, 1, 10)]
    vane += [tuple(nib + d * L * t - n * width * 0.45 * math.sin(math.pi * (t - 0.22) / 0.78) ** 0.7)
             for t in np.linspace(1, 0.25, 10)]
    vm = ic.poly_mask(vane)
    ic.fill(vm, "#f6f0e2", "#b4aa94", radial=(nib[0] + d[0] * L * 0.5, nib[1] + d[1] * L * 0.5, L * 0.6), noise=0.06)
    ic.overlay(lambda dr: [dr.line([tuple(nib + d * L * t), tuple(nib + d * L * (t + 0.06) + n * width * 0.9)],
                                   fill=(150, 140, 120, 110), width=2) for t in np.linspace(0.3, 0.9, 9)], vm)
    ic.line([tuple(nib), tuple(tip)], 4, (120, 108, 90))
    ic.line([tuple(nib), tuple(nib + d * L * 0.12)], 5, (30, 24, 20))
    ic.outline(vane, 3, (90, 80, 66, 200))


def hanging_balance(ic: Icon, cx, top, span, drop) -> None:
    """A brass balance hung as the house sign: a ring, a beam with a pointer, two dished pans on three chains."""
    brass = ("#f6d488", "#8a5c1e")
    ic.overlay(lambda d: d.ellipse((cx - 14, top - 14, cx + 14, top + 14), outline=(196, 150, 70, 255), width=8))
    beam_y = top + 34
    ic.line([(cx - span, beam_y + 4), (cx + span, beam_y - 4)], 18, (150, 104, 40))
    ic.line([(cx - span, beam_y - 1), (cx + span, beam_y - 9)], 6, (255, 236, 180, 230))
    ic.poly([(cx - 10, beam_y - 4), (cx + 10, beam_y - 4), (cx, beam_y + 46)], brass[0], brass[1], edge=3)
    ic.ellipse((cx - 17, beam_y - 17, cx + 17, beam_y + 17), brass[0], brass[1], edge=3)
    for side, dy in ((-1, 4), (1, -4)):
        px = cx + side * span
        py = beam_y + dy
        pan_y = py + drop
        for dx in (-span * 0.5, 0, span * 0.5):
            ic.line([(px, py), (px + dx, pan_y)], 5, (176, 136, 70, 255))
        ic.ellipse((px - 9, py - 9, px + 9, py + 9), brass[0], brass[1], edge=3)
        pan = (px - span * 0.62, pan_y - 16, px + span * 0.62, pan_y + 40)
        pm = ic.intersect(ic.mask("ellipse", pan), ic.mask("rectangle", (0, pan_y, ic.size, ic.size)))
        ic.fill(pm, brass[0], brass[1], radial=(px - span * 0.3, pan_y, span * 0.8), noise=0.08)
        tint(ic, ic.mask("ellipse", (px, pan_y, px + span * 0.7, pan_y + 40)), pm, (40, 20, 0), 0.35, 6)
        ic.line([(px - span * 0.62, pan_y + 1), (px + span * 0.62, pan_y + 1)], 8, (255, 230, 160))
        ic.overlay(lambda d, pan=pan: d.chord(pan, 0, 180, outline=EDGE, width=4))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.9

    # ---- schoolroom wing: tiled roof seen from the eaves side, stucco walls, an arcade
    roof = [(X1 - 20, WEAVE + 14), (WX1 + 30, WEAVE + 14), (WX1 - 6, WRIDGE), (X1, WRIDGE)]
    rm = shingles(ic, roof, "#7e584a", "#33221c", course=28, stagger=38)
    for _ in range(10):
        x, y = ic.random.uniform(X1, WX1), ic.random.uniform(WRIDGE, WEAVE)
        r = ic.random.uniform(20, 50)
        tint(ic, ic.mask("ellipse", (x - r * 1.4, y - r * 0.6, x + r * 1.4, y + r * 0.6)), rm,
             ic.random.choice([(0, 0, 0), (255, 230, 196), (96, 92, 50)]), ic.random.uniform(0.08, 0.18), 12)
    tint(ic, ic.poly_mask([(X1 + 200, WRIDGE), (WX1 + 40, WRIDGE), (WX1 + 40, WEAVE + 20), (X1 + 240, WEAVE + 20)]), rm,
         (0, 0, 0), 0.18, 40)
    ic.poly([(X1, WRIDGE - 10), (WX1 - 4, WRIDGE - 10), (WX1 - 4, WRIDGE + 6), (X1, WRIDGE + 6)], "#6e4a3c", "#3a241a",
            edge=4)
    # a dormer with a small window lights the attic
    wall = ic.mask("rectangle", (X1, WEAVE + 14, WX1, BASE))
    ic.fill(wall, "#dcc49a", "#a88a62", (WEAVE, BASE), noise=0.16, chroma=0.04)
    for _ in range(10):
        x, y = ic.random.uniform(X1, WX1), ic.random.uniform(WEAVE + 40, BASE)
        r = ic.random.uniform(20, 60)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.7, x + r, y + r * 0.7)), wall,
             ic.random.choice([(80, 60, 40), (255, 240, 210)]), ic.random.uniform(0.06, 0.14), 14)
    tint(ic, ic.mask("rectangle", (X1, WEAVE + 14, WX1, WEAVE + 70)), wall, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (X1, BASE - 90, WX1, BASE)), wall, (60, 50, 30), 0.25, 20)
    for x0 in (580, 718):
        stone_window(ic, x0, 626, x0 + 64, 690, wall, cross=False)
    ic.rect((X1 + 4, 718, WX1 - 4, 740), STONE[0], STONE[1], edge=4)  # string course
    for ax0 in (566, 714):
        ring = arch_mask(ic, ax0 - 22, ax0 + 112 + 22, 760 - 22, BASE)
        ic.fill(ring, STONE[0], STONE[1], (740, BASE), noise=0.16)
        hole = arch_mask(ic, ax0, ax0 + 112, 760, BASE)
        ic.fill(hole, "#2a1e16", "#0e0a08", (760, BASE), noise=0.1)
        tint(ic, ic.mask("rectangle", (ax0, 760, ax0 + 112, 820)), hole, (0, 0, 0), 0.5, 14)
        cx, cy = ax0 + 56, 760 + 56
        ic.overlay(lambda d, cx=cx, cy=cy: [d.line([(cx + math.cos(a) * 56, cy + math.sin(a) * 56),
                                                    (cx + math.cos(a) * 78, cy + math.sin(a) * 78)],
                                                   fill=(70, 58, 44, 170), width=4)
                                            for a in np.linspace(math.pi, 2 * math.pi, 7)[1:-1]])
        ic.overlay(lambda d, ax0=ax0: d.arc((ax0, 760, ax0 + 112, 872), 180, 360, fill=EDGE, width=5))
        ic.line([(ax0, 816), (ax0, BASE)], 5, EDGE)
        ic.line([(ax0 + 112, 816), (ax0 + 112, BASE)], 5, EDGE)
    # a bench and a pupil's slate in the left arch
    ic.beam((578, 862), (666, 862), 12, (110, 78, 50))
    ic.outline([(X1, WEAVE + 14), (WX1, WEAVE + 14), (WX1, BASE), (X1, BASE)], 5)

    # ---- the merchant house: brick, stepped gable
    st = 44
    steps = [(X0, 470), (X0, 400), (X0 + st, 400), (X0 + st, 326), (X0 + 2 * st, 326), (X0 + 2 * st, 252),
             (X0 + 3 * st, 252), (X0 + 3 * st, 178), (X1 - 3 * st, 178), (X1 - 3 * st, 252), (X1 - 2 * st, 252),
             (X1 - 2 * st, 326), (X1 - st, 326), (X1 - st, 400), (X1, 400), (X1, 470)]
    front = steps + [(X1, BASE), (X0, BASE)]
    fm = ic.poly_mask(front)
    bricks(ic, fm, (X0, 170, X1, BASE))
    tint(ic, ic.mask("rectangle", (X1 - 110, 170, X1 + 20, BASE)), fm, (0, 0, 0), 0.18, 40)
    tint(ic, ic.mask("rectangle", (X0, 170, X0 + 90, BASE)), fm, (255, 230, 200), 0.08, 30)
    tint(ic, ic.mask("rectangle", (X0, BASE - 110, X1, BASE)), fm, (40, 36, 20), 0.25, 26)
    for x0, x1, y in ((X0, X0 + st, 400), (X0 + st, X0 + 2 * st, 326), (X0 + 2 * st, X0 + 3 * st, 252),
                      (X1 - st, X1, 400), (X1 - 2 * st, X1 - st, 326), (X1 - 3 * st, X1 - 2 * st, 252)):
        tint(ic, ic.mask("rectangle", (x0, y, x1, y + 34)), fm, (0, 0, 0), 0.35, 8)
        coping(ic, x0, x1, y)
    coping(ic, X0 + 3 * st, X1 - 3 * st, 178, 26)
    ic.rect((GCX - 16, 122, GCX + 16, 154), STONE[0], STONE[1], edge=4)  # finial
    ic.ellipse((GCX - 22, 86, GCX + 22, 128), "#d8cbac", "#8a7c60", edge=4)
    for y in (470, 690):  # string courses
        ic.rect((X0 - 8, y - 10, X1 + 8, y + 12), STONE[0], STONE[1], edge=4)
        tint(ic, ic.mask("rectangle", (X0, y + 12, X1, y + 40)), fm, (0, 0, 0), 0.3, 8)
    # loft door and hoist beam in the gable
    ic.rect((GCX - 40, 282, GCX + 40, 396), "#6a4a30", "#3e2a1a", edge=4)
    ic.rect((GCX - 30, 292, GCX + 30, 390), "#7c5a3a", "#4a3220", edge=3)
    ic.line([(GCX, 294), (GCX, 388)], 4, (40, 26, 14, 170))
    tint(ic, ic.mask("rectangle", (GCX - 46, 396, GCX + 50, 420)), fm, (0, 0, 0), 0.35, 6)
    # the hoist beam points at us: its squared end, an iron pulley and the rope down past the loft door
    ic.rect((GCX - 20, 214, GCX + 20, 250), "#8a6040", "#4a3220", edge=4)
    ic.line([(GCX - 14, 218), (GCX + 12, 218)], 3, (190, 150, 110, 160))
    ic.line([(GCX, 250), (GCX, 262)], 5, (50, 46, 44))
    ic.ellipse((GCX - 12, 260, GCX + 12, 284), "#6a6460", "#2a2624", edge=3)
    ic.line([(GCX + 10, 274), (GCX + 12, 300)], 3, (120, 96, 60))
    ic.line([(GCX - 10, 274), (GCX - 12, 300)], 3, (120, 96, 60))
    # first floor: the schoolroom windows
    for x0 in (222, 412):
        stone_window(ic, x0, 516, x0 + 62, 640, fm)
    # ground floor: the arched door and two windows
    dx0, dx1 = 300, 396
    ring = arch_mask(ic, dx0 - 26, dx1 + 26, 734 - 26, BASE)
    ic.fill(ring, STONE[0], STONE[1], (708, BASE), noise=0.16)
    ic.door(dx0, 734, dx1, BASE - 4, arched=True, surround=None)
    tint(ic, ic.mask("rectangle", (dx0, 734, dx1, 784)), None, (0, 0, 0), 0.25, 10)
    dcx, dcy = (dx0 + dx1) / 2, 734 + (dx1 - dx0) / 2
    ic.overlay(lambda d: [d.line([(dcx + math.cos(a) * 48, dcy + math.sin(a) * 48),
                                  (dcx + math.cos(a) * 74, dcy + math.sin(a) * 74)], fill=(70, 58, 44, 170), width=4)
                          for a in np.linspace(math.pi, 2 * math.pi, 7)[1:-1]])
    stone_window(ic, 212, 752, 256, 830, fm, cross=False)
    stone_window(ic, 438, 752, 482, 830, fm, cross=False)
    ic.outline(front, 6)

    # ---- plinth
    stones(ic, (X0 - 8, BASE - 14, WX1 + 10, BASE + 12), "#8a7c6a", "#5a5046", course=26, moss=0.0)
    ic.outline([(X0 - 8, BASE - 14), (WX1 + 10, BASE - 14), (WX1 + 10, BASE + 12), (X0 - 8, BASE + 12)], 4)

    # ---- the counting frame on its easel stand, ledger and quill on the tray
    ic.beam((800, 548), (830, 944), 18, (80, 56, 36))  # back leg
    tint(ic, ic.mask("ellipse", (600, BASE + 4, 1000, BASE + 60)), None, (0, 0, 0), 0.42, 14)
    abacus(ic, 618, 536, 964, 800)
    ic.beam((604, 818), (984, 818), 22, (126, 90, 56))  # tray
    tint(ic, ic.mask("rectangle", (618, 800, 964, 816)), None, (0, 0, 0), 0.35, 6)
    ic.beam((650, 800), (618, 948), 22, (116, 82, 52))
    ic.beam((934, 800), (972, 944), 22, (100, 70, 44))
    ledger(ic, 760, 806, 196, 74, degrees=-2)
    quill(ic, (878, 812), (996, 690), width=24)
    ic.fill(ic.mask("ellipse", (858, 790, 902, 822)), "#3a3a42", "#101014", radial=(866, 796, 46), noise=0.06)
    ic.fill(ic.mask("ellipse", (864, 786, 896, 798)), "#24242a", "#08080a", noise=0.06)
