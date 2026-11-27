"""Academy of Sciences (pp_academy_of_sciences): a learned society of the 17th-18th century in a capital city, where
the academicians observe, measure and publish.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor-locplan/assets/icon_drawings/pp_academy_of_sciences/draw.py \
    --out ../ProsperOrPerishConstructor-locplan/artifacts/icons/pp_academy_of_sciences

Identity: a brass armillary sphere on a stone pedestal in front of a classical academy hall; the hall has a portico
of four Ionic columns under a pediment with a gilt sun, arched windows over a rusticated ground floor, a lead roof;
at its left end an observatory tower with a clock, a drum and a verdigris copper dome, its shutter slit open and a
long refractor telescope reaching out of it over the roof. The pedestal stands where the schools have their easels,
so the three read as one family; dome, telescope and sphere set it apart from the vanilla University and Library.
Helpers ``union``, ``tint``, ``shingles``, ``arch_mask`` are copied from the Cookshop and the Trade School; new local
helpers: ``ashlar``, ``quoins``, ``cornice``, ``column``, ``arched_window``, ``square_window``, ``pediment``,
``clock_face``, ``dome``, ``telescope``, ``pedestal``, ``armillary``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 41
REFS = ("university", "library", "scriptorium", "local_schools")

BASE = 900
HX0, HX1 = 300, 770  # academy hall
CTOP, CBOT = 462, 500  # hall cornice
SY0, SY1 = 688, 706  # string course over the rusticated ground floor
TX0, TX1 = 96, 316  # observatory tower
TTOP = 404  # tower body top (its cornice sits above)
TCX = (TX0 + TX1) / 2
PCX = 545  # portico axis
COLS = (PCX - 122, PCX - 52, PCX + 52, PCX + 122)
AX, AY, AR = 852, 606, 128  # armillary sphere
STONE = ("#e6d0a2", "#a2845a")
RUST = ("#d8bd8e", "#8a704e")
BRASS = ("#f8d88c", "#6a4210")
IRON = (34, 31, 30)
EDGE = (40, 28, 20, 200)


# ---------------------------------------------------------------- helpers (shared with the Cookshop and Trade School)
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


def arch_mask(ic: Icon, x0, x1, top, bottom) -> Image.Image:
    w = x1 - x0
    return union(ic.mask("ellipse", (x0, top, x1, top + w)), ic.mask("rectangle", (x0, top + w / 2, x1, bottom)))


# ---------------------------------------------------------------- helpers (new for the Academy of Sciences)
def ashlar(ic: Icon, mask: Image.Image, box, colors=STONE, course: float = 34, block: float = 72,
           rustic: bool = False) -> None:
    """Dressed stone in regular courses: every block its own tone, fine joints (lit lip under each bed joint). With
    ``rustic`` the bed joints are deep channels, shadowed above and lit below, as on a rusticated ground floor."""
    x0, y0, x1, y1 = box
    ic.fill(mask, colors[0], colors[1], (y0, y1), noise=0.14, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0
    while y < y1:
        x = x0 - rnd(0, block)
        while x < x1:
            w = block * rnd(0.7, 1.35)
            t = rnd(-1, 1)
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2),
                        fill=(30, 20, 10, int(-t * 42)) if t < 0 else (255, 246, 224, int(t * 38)))
            if ic.random.random() < 0.1:  # a darker, weathered block
                d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=(110, 96, 70, 46))
            d.line([(x + w - 1, y + 3), (x + w - 1, y + course - 1)], fill=(70, 54, 38, 150 if rustic else 100),
                   width=4 if rustic else 3)
            x += w
        if rustic:
            d.line([(x0, y + course - 3), (x1, y + course - 3)], fill=(40, 28, 18, 200), width=8)
            d.line([(x0, y + course + 4), (x1, y + course + 4)], fill=(255, 244, 220, 100), width=3)
        else:
            d.line([(x0, y + course), (x1, y + course)], fill=(86, 70, 50, 120), width=3)
            d.line([(x0, y + course + 3), (x1, y + course + 3)], fill=(255, 246, 226, 50), width=2)
        y += course
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), mask)
    ic.image.alpha_composite(clip)


def quoins(ic: Icon, x, y0, y1, side: int, course: float = 34) -> None:
    """Long-and-short corner stones standing a little proud of the wall, lit on top, shadowed below."""
    k = 0
    for y in np.arange(y0, y1 - 4, course):
        w = 54 if k % 2 else 34
        box = (x - 4, y + 2, x + w, y + course - 2) if side < 0 else (x - w, y + 2, x + 4, y + course - 2)
        ic.rect(box, "#f2e4c2", "#b49a70", edge=3)
        ic.line([(box[0] + 3, box[1] + 3), (box[2] - 3, box[1] + 3)], 3, (255, 250, 232, 140))
        k += 1


def cornice(ic: Icon, x0, x1, top, bot, below: Image.Image | None) -> None:
    """A moulded stone cornice: lit top lip, a row of dentils, a deep shadow on the wall beneath."""
    if below is not None:
        tint(ic, ic.mask("rectangle", (x0, bot, x1, bot + 46)), below, (20, 12, 4), 0.5, 10)
    ic.rect((x0, top, x1, bot), STONE[0], STONE[1], edge=4)
    ic.rect((x0 - 8, top, x1 + 8, top + 12), "#f6ead0", "#c8b088", edge=4)
    ic.overlay(lambda d: [d.rectangle((x, bot - 15, x + 8, bot - 5), fill=(70, 52, 34, 150))
                          for x in np.arange(x0 + 6, x1 - 6, 17)])
    ic.line([(x0, bot - 2), (x1, bot - 2)], 4, (60, 44, 30, 160))


def column(ic: Icon, cx, top, bot, r, wall: Image.Image) -> None:
    """An Ionic column: a shaft shaded as a cylinder (lit left of its axis, core shadow right, reflected light at the
    right edge), faint flutes, a moulded base, a capital with two volutes; it casts a shadow on the wall to its right."""
    tint(ic, ic.poly_mask([(cx + r - 6, top + 30), (cx + r + 34, top + 56), (cx + r + 34, bot - 8), (cx + r - 6, bot - 8)]),
         wall, (24, 14, 6), 0.42, 6)
    s0, s1 = top + 30, bot - 26
    shaft = ic.poly_mask([(cx - r + 2, s0), (cx + r - 2, s0), (cx + r, s1), (cx - r, s1)])
    ic.fill(shaft, "#f8ecd0", "#7c6448", (cx - r * 0.45, cx + r * 0.85), vertical=False, noise=0.08)
    tint(ic, ic.mask("rectangle", (cx + r * 0.75, s0, cx + r, s1)), shaft, (200, 170, 130), 0.3, 3)  # reflected light
    tint(ic, ic.mask("rectangle", (cx - r * 0.5, s0, cx - r * 0.12, s1)), shaft, (255, 252, 240), 0.4, 4)
    ic.overlay(lambda d: [d.line([(cx + f * r, s0 + 4), (cx + f * r, s1 - 4)], fill=(96, 76, 54, 70), width=2)
                          for f in (-0.62, -0.2, 0.25, 0.62)], shaft)
    ic.line([(cx - r + 2, s0), (cx - r, s1)], 4, EDGE)
    ic.line([(cx + r - 2, s0), (cx + r, s1)], 4, EDGE)
    ic.rect((cx - r - 6, s1, cx + r + 6, s1 + 12), STONE[0], STONE[1], vertical=False, edge=3)
    ic.rect((cx - r - 12, s1 + 12, cx + r + 12, bot), STONE[0], STONE[1], vertical=False, edge=4)
    ic.rect((cx - r - 4, top + 16, cx + r + 4, s0), "#f0e2c0", "#9c8460", vertical=False, edge=3)  # echinus
    for sx in (-1, 1):
        vx = cx + sx * (r + 2)
        ic.ellipse((vx - 11, top + 12, vx + 11, top + 34), "#f6ead0", "#a08660", edge=3)
        ic.draw.ellipse((vx - 3, top + 20, vx + 3, top + 26), fill=(80, 60, 40, 255))
    ic.rect((cx - r - 14, top, cx + r + 14, top + 14), "#f6ead0", "#b89e74", edge=4)  # abacus


def arched_window(ic: Icon, x0, y0, x1, y1, wall: Image.Image) -> None:
    """A round-headed window: dressed stone surround with a keystone, dark glass with a grey sky sheen and glazing
    bars, a stone sill casting a short shadow."""
    w = x1 - x0
    ring = arch_mask(ic, x0 - 13, x1 + 13, y0 - 13, y1 + 4)
    ic.fill(ring, "#f2e4c2", "#a88e66", (y0, y1), noise=0.12)
    glass = arch_mask(ic, x0, x1, y0, y1)
    ic.fill(glass, "#4a4e56", "#15161a", (y0, y1), noise=0.08, chroma=0.03)
    tint(ic, ic.poly_mask([(x0, y0), (x1, y0), (x1, y0 + w * 0.6), (x0, y0 + w * 1.4)]), glass, (176, 186, 198), 0.22, 5)

    def bars(d):
        d.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill=(214, 200, 172, 200), width=4)
        for y in np.arange(y0 + w * 0.5, y1, 28):
            d.line([(x0, y), (x1, y)], fill=(214, 200, 172, 170), width=3)

    ic.overlay(bars, glass)
    tint(ic, ic.mask("rectangle", (x0, y0, x1, y0 + w * 0.7)), glass, (0, 0, 0), 0.3, 6)
    ic.overlay(lambda d: d.arc((x0, y0, x1, y0 + w), 180, 360, fill=EDGE, width=4))
    ic.line([(x0, y0 + w / 2), (x0, y1)], 4, EDGE)
    ic.line([(x1, y0 + w / 2), (x1, y1)], 4, EDGE)
    xm = (x0 + x1) / 2
    ic.poly([(xm - 8, y0 - 14), (xm + 8, y0 - 14), (xm + 6, y0 + 4), (xm - 6, y0 + 4)], "#f6ead0", "#b49a70", edge=3)
    ic.rect((x0 - 18, y1 + 2, x1 + 18, y1 + 14), "#f0e2c0", "#a88e66", edge=3)
    tint(ic, ic.mask("rectangle", (x0 - 16, y1 + 14, x1 + 22, y1 + 34)), wall, (0, 0, 0), 0.3, 5)


def square_window(ic: Icon, x0, y0, x1, y1, wall: Image.Image) -> None:
    """A ground-floor window: stone frame under a small cornice hood, dark glass, glazing bars."""
    ic.rect((x0 - 11, y0 - 11, x1 + 11, y1 + 9), "#eadcb8", "#a08660", edge=4)
    glass = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(glass, "#46494f", "#141518", (y0, y1), noise=0.08)
    tint(ic, ic.poly_mask([(x0, y0), (x1, y0), (x0, y0 + (y1 - y0) * 0.6)]), glass, (170, 180, 192), 0.18, 4)
    ic.overlay(lambda d: [d.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill=(210, 196, 168, 190), width=4)]
               + [d.line([(x0, y), (x1, y)], fill=(210, 196, 168, 160), width=3) for y in np.arange(y0 + 26, y1, 26)],
               glass)
    tint(ic, ic.mask("rectangle", (x0, y0, x1, y0 + 26)), glass, (0, 0, 0), 0.35, 5)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)
    ic.rect((x0 - 20, y0 - 28, x1 + 20, y0 - 13), "#f4e8ca", "#b0966c", edge=4)
    tint(ic, ic.mask("rectangle", (x0 - 14, y0 - 13, x1 + 24, y0 + 6)), wall, (0, 0, 0), 0.32, 4)


def pediment(ic: Icon, x0, x1, base, apex) -> None:
    """A triangular pediment: raking cornices, a recessed tympanum in their shadow, a gilt sun in its middle, a ball
    on the apex and blocks at the ends."""
    cx = (x0 + x1) / 2
    outer = [(x0 - 16, base + 2), (x1 + 16, base + 2), (cx, apex - 18)]
    ic.poly(outer, "#f0e2c0", "#b49a72", edge=5)
    ic.line([(x0 - 10, base - 4), (cx, apex - 12)], 4, (255, 250, 232, 150))
    inner = [(x0 + 34, base - 6), (x1 - 34, base - 6), (cx, apex + 20)]
    im = ic.poly_mask(inner)
    ic.fill(im, "#d4c098", "#94795a", (apex, base), noise=0.12)
    tint(ic, ic.poly_mask([(x0 + 34, base - 6), (cx, apex + 20), (x1 - 34, base - 6), (x1 - 34, base - 6),
                           (cx, apex + 60), (x0 + 60, base - 6)]), im, (16, 10, 4), 0.42, 9)
    ic.outline(inner, 4)
    # gilt sun
    sx, sy, sr = cx, base - (base - apex) * 0.36, 20
    rays = []
    for k in range(16):
        a = k * math.pi / 8
        L = sr * (2.0 if k % 2 == 0 else 1.55)
        rays.append([(sx + math.cos(a - 0.12) * sr * 0.8, sy + math.sin(a - 0.12) * sr * 0.8),
                     (sx + math.cos(a) * L, sy + math.sin(a) * L),
                     (sx + math.cos(a + 0.12) * sr * 0.8, sy + math.sin(a + 0.12) * sr * 0.8)])
    rm = union(*[ic.poly_mask(r) for r in rays])
    ic.fill(rm, "#f6d27a", "#9a6418", radial=(sx - 14, sy - 14, sr * 2.6), noise=0.08)
    ic.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), "#fbe09a", "#a8701e", edge=3)
    ic.draw.ellipse((sx - sr * 0.6, sy - sr * 0.7, sx - sr * 0.1, sy - sr * 0.2), fill=(255, 246, 214, 255))
    ic.ellipse((cx - 13, apex - 46, cx + 13, apex - 20), "#f4e6c4", "#9c8460", edge=4)
    for x in (x0 - 10, x1 - 14):
        ic.rect((x, base - 22, x + 24, base + 2), "#f4e6c4", "#a88e66", edge=3)


def clock_face(ic: Icon, cx, cy, r) -> None:
    """A tower clock: moulded stone ring, pale dial with hour marks, gilt hands."""
    ic.ellipse((cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12), "#f2e4c2", "#a08660", edge=4)
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), "#f8f0dc", "#b8a684", radial=(cx - r * 0.4, cy - r * 0.4, r * 2),
            noise=0.06)
    ic.overlay(lambda d: [d.line([(cx + math.cos(a) * r * 0.72, cy + math.sin(a) * r * 0.72),
                                  (cx + math.cos(a) * r * 0.92, cy + math.sin(a) * r * 0.92)], fill=(40, 30, 22, 220),
                                 width=3) for a in np.linspace(0, 2 * math.pi, 13)[:-1]])
    ic.line([(cx, cy), (cx + r * 0.38, cy - r * 0.42)], 5, (60, 40, 14))
    ic.line([(cx, cy), (cx - r * 0.1, cy - r * 0.7)], 4, (60, 40, 14))
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=EDGE, width=3))


def dome(ic: Icon, cx, base, w, h, slit=(10, 27)) -> None:
    """An observatory dome of copper gone to verdigris: hemispherical, lit upper left, copper ribs and green drips,
    the shutter slit open over the top (dark inside, the cut edge of the far shutter lit), a dark eave ring."""
    rx = w / 2

    def P(lam, th):
        return (cx + rx * math.sin(math.radians(lam)) * math.cos(math.radians(th)), base - h * math.sin(math.radians(th)))

    m = ic.intersect(ic.mask("ellipse", (cx - rx, base - h, cx + rx, base + h)), ic.mask("rectangle", (0, 0, ic.size, base)))
    ic.fill(m, "#9ccab2", "#22423a", radial=(cx - rx * 0.45, base - h * 0.75, w * 1.0), noise=0.14, chroma=0.06)
    rnd = ic.random.uniform
    drips = Image.new("L", (ic.size, ic.size), 0)
    dd = ImageDraw.Draw(drips)
    for _ in range(18):
        x = rnd(cx - rx * 0.9, cx + rx * 0.9)
        y = rnd(base - h * 0.8, base - 20)
        dd.line([(x, y), (x + rnd(-2, 2), y + rnd(20, 50))], fill=255, width=int(rnd(4, 9)))
    tint(ic, drips, m, (196, 232, 212), 0.22, 3)
    for lam in (-62, -38, -14, 44, 66):  # copper ribs
        pts = [P(lam, th) for th in np.linspace(0, 89, 24)]
        ic.line(pts, 5, (30, 52, 46, 170))
        ic.line([(x - 3, y) for x, y in pts], 2, (210, 240, 222, 90))
    tint(ic, ic.mask("rectangle", (cx + rx * 0.25, base - h, cx + rx + 10, base)), m, (6, 16, 14), 0.38, 26)
    a, b = slit
    gap = [P(a, th) for th in np.linspace(0, 88, 20)] + [P(b, th) for th in np.linspace(88, 0, 20)]
    ic.fill(ic.poly_mask(gap), "#241e18", "#0a0806", (base - h, base), noise=0.06)
    ic.line([P(b, th) for th in np.linspace(0, 86, 20)], 6, (220, 246, 230, 200))  # lit cut edge
    ic.line([P(a, th) for th in np.linspace(0, 86, 20)], 5, (10, 20, 18, 200))
    ic.overlay(lambda d: d.arc((cx - rx, base - h, cx + rx, base + h), 180, 360, fill=EDGE, width=5))
    ic.rect((cx - rx - 8, base - 6, cx + rx + 8, base + 10), "#4a6e62", "#1c3028", edge=4)
    ic.line([(cx - rx - 6, base - 3), (cx + rx + 6, base - 3)], 3, (190, 230, 210, 120))


def telescope(ic: Icon, p0, p1, w0, w1) -> None:
    """A long refractor: a tapering tube of red-brown leather over pasteboard, lit along its upper side, brass bands,
    a brass objective cell with the dark lens at the far end."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    d = (p1 - p0) / np.linalg.norm(p1 - p0)
    n = np.array([d[1], -d[0]])  # points up and to the left of the tube
    if n[1] > 0:
        n = -n

    def band(t0, t1, f0, f1):
        """Quad along the tube between t0..t1 (length fractions) and f0..f1 (width fractions, +1 = upper edge)."""
        q = []
        for t, f in ((t0, f0), (t1, f0), (t1, f1), (t0, f1)):
            hw = (w0 + (w1 - w0) * t) / 2
            q.append(tuple(p0 + (p1 - p0) * t + n * hw * f))
        return q

    tube = band(0, 1, 1, -1)
    tm = ic.poly_mask(tube)
    ic.fill(tm, "#8a4428", "#3a170a", radial=(*(p0 + (p1 - p0) * 0.3 + n * w0), np.linalg.norm(p1 - p0)), noise=0.1)
    tint(ic, ic.poly_mask(band(0, 1, 0.95, 0.35)), tm, (255, 220, 180), 0.35, 3)
    tint(ic, ic.poly_mask(band(0, 1, -0.3, -1)), tm, (10, 4, 0), 0.45, 3)
    ic.overlay(lambda dr: [dr.line([band(t, t, 0.9, 0.9)[0], band(t + 0.05, t + 0.05, 0.9, 0.9)[0]],
                                   fill=(230, 180, 90, 120), width=2) for t in np.arange(0.08, 0.9, 0.12)], tm)
    for t in (0.22, 0.56, 0.86):  # brass bands
        q = band(t, t + 0.035, 1.18, -1.18)
        ic.fill(ic.poly_mask(q), BRASS[0], BRASS[1], radial=(*(p0 + (p1 - p0) * t + n * w0 * 0.6), w1 * 1.4), noise=0.06)
        ic.outline(q, 3, EDGE)
    ic.outline(tube, 4, EDGE)
    # objective cell: a brass ring seen at an angle, the lens dark with a sky glint
    c = p1 + d * 4
    ring = [tuple(c + n * math.cos(s) * w1 * 0.66 + d * math.sin(s) * w1 * 0.24) for s in np.linspace(0, 2 * math.pi, 28)]
    ic.fill(ic.poly_mask(ring), BRASS[0], BRASS[1], radial=(*(c + n * w1 * 0.4), w1 * 1.2), noise=0.06)
    lens = [tuple(c + d * 3 + n * math.cos(s) * w1 * 0.44 + d * math.sin(s) * w1 * 0.15)
            for s in np.linspace(0, 2 * math.pi, 24)]
    ic.fill(ic.poly_mask(lens), "#3c4a5a", "#0c1018", radial=(*(c + n * w1 * 0.3), w1), noise=0.04)
    ic.outline(ring, 3, EDGE)


def pedestal(ic: Icon, cx, top, bot) -> None:
    """A stone pedestal turned like a baluster: a cap slab, a neck, a round shaft and a moulded base on a plinth, each
    part shaded as a cylinder; it throws its shadow to the right on the ground."""
    tint(ic, ic.mask("ellipse", (cx - 90, bot - 22, cx + 170, bot + 40)), None, (0, 0, 0), 0.45, 14)
    parts = ((cx - 60, bot - 30, cx + 60, bot), (cx - 50, bot - 46, cx + 50, bot - 30),
             (cx - 40, top + 36, cx + 40, bot - 46), (cx - 30, top + 22, cx + 30, top + 36), (cx - 62, top, cx + 62, top + 22))
    for x0, y0, x1, y1 in parts:
        m = ic.mask("rectangle", (x0, y0, x1, y1))
        ic.fill(m, "#f4e6c4", "#7e6648", (x0 + (x1 - x0) * 0.25, x1), vertical=False, noise=0.12)
        tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.22, y0, x0 + (x1 - x0) * 0.4, y1)), m, (255, 252, 240), 0.35, 3)
        ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)
    tint(ic, ic.mask("rectangle", (cx - 40, top + 36, cx + 40, top + 60)), None, (0, 0, 0), 0.3, 6)


def fill_slivers(ic: Icon, box, size: int = 19) -> None:
    """Paint the slivers of sky between crossing rings as the dim inside of the sphere. The finalize outline would
    fill every gap narrower than its own width with solid black (stray dark specks at 128 px); larger gaps stay open."""
    a = ic.alpha().point(lambda v: 255 if v > 30 else 0)
    closed = a.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    holes = ic.intersect(ImageChops.subtract(closed, a), ic.mask("rectangle", box))
    x0, y0, x1, y1 = box
    ic.fill(holes, "#5a4024", "#21160a", radial=(x0 + (x1 - x0) * 0.35, y0 + (y1 - y0) * 0.35, max(x1 - x0, y1 - y0)),
            noise=0.08)


def _rot(v, axis, deg):
    """Rodrigues rotation of vector ``v`` about the unit ``axis``."""
    v, k = np.array(v, float), np.array(axis, float) / np.linalg.norm(axis)
    a = math.radians(deg)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * np.dot(k, v) * (1 - math.cos(a))


def armillary(ic: Icon, cx, cy, R, widths=1.0, full: bool = True, elev: float = 14, yaw: float = 28,
              tilt: float = 36) -> None:
    """A brass armillary sphere: horizon and meridian rings, the equator, the broad ecliptic band with its divisions,
    the colure and the polar circles round a small earth on the polar axis. Every ring is a true circle in 3D,
    projected from slightly above; the far halves are drawn first and darker (in the sphere's shade), the near halves
    over the earth, each band lit by its facing to the upper-left light."""
    e = math.radians(elev)
    up = np.array([0.0, 1.0, 0.0])
    a = np.array([math.sin(math.radians(tilt)), math.cos(math.radians(tilt)), 0.0])
    m = np.array([0.0, 0.0, 1.0])
    a, m = _rot(a, up, yaw), _rot(m, up, yaw)
    c = np.cross(a, m)
    c /= np.linalg.norm(c)
    light = np.array([-0.6, 0.62, 0.5])
    light /= np.linalg.norm(light)

    def proj(p):
        return (cx + p[0], cy - (p[1] * math.cos(e) - p[2] * math.sin(e))), p[2] * math.cos(e) + p[1] * math.sin(e)

    # (normal, radius, centre, width, ticks)
    rings = [(up, 1.13 * R, np.zeros(3), 24 * widths, 0), (m, 1.05 * R, np.zeros(3), 20 * widths, 0),
             (a, R, np.zeros(3), 15 * widths, 0), (_rot(a, c, 23.5), R, np.zeros(3), 28 * widths, 12)]
    if full:
        rings += [(c, R * 0.98, np.zeros(3), 10 * widths, 0), (a, 0.4 * R, a * 0.917 * R, 9 * widths, 0),
                  (a, 0.4 * R, -a * 0.917 * R, 9 * widths, 0)]
    items = []  # (depth, kind, payload)
    for normal, r, centre, w, ticks in rings:
        normal = normal / np.linalg.norm(normal)
        ref = np.array([0.0, 0.0, 1.0]) if abs(normal[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(normal, ref)
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        ts = np.linspace(0, 2 * math.pi, 241)[:-1]
        pts3 = [centre + r * (u * math.cos(t) + v * math.sin(t)) for t in ts]
        scr, dep = zip(*[proj(p) for p in pts3])
        dep = np.array(dep)
        front = dep >= 0
        # start the walk where the ring turns from back to front, so every run is contiguous
        k0 = next((i for i in range(len(ts)) if front[i] and not front[i - 1]), 0)
        order = [(k0 + i) % len(ts) for i in range(len(ts) + 1)]
        runs, cur = [], [order[0]]
        for i in order[1:]:
            cur.append(i)  # a run ends on the first point of the other side, so the halves join
            if front[i] != front[cur[0]]:
                runs.append(cur)
                cur = [i]
        if len(cur) > 1:
            runs.append(cur)
        for run in runs:
            side = bool(front[run[0]])
            items.append((float(np.mean(dep[run])) + (0.5 if side else -0.5) * R, "ring",
                          (run, scr, pts3, centre, r, w, ticks, side)))
    pa, pb = proj(a * 1.34 * R)[0], proj(-a * 1.34 * R)[0]
    items.append((-0.01, "axis", (pa, pb)))
    items.append((0.0, "earth", None))
    items.sort(key=lambda it: it[0])
    dark, lite = np.array((84, 46, 8), float), np.array((246, 200, 100), float)
    for _, kind, payload in items:
        if kind == "ring":
            run, scr, pts3, centre, r, w, ticks, is_front = payload
            pts = [scr[i] for i in run]
            ic.line(pts, int(w + 8), (36, 22, 8, 235))
            shine = []
            for j in range(len(run) - 1):
                i = run[j]
                radial = (pts3[i] - centre) / r
                b = float(np.dot(radial if is_front else -radial, light))
                b = 0.3 + 0.7 * max(0.0, min(1.0, 0.5 + 0.6 * b))
                if not is_front:
                    b *= 0.62
                col = tuple(int(v) for v in dark + (lite - dark) * b) + (255,)
                (x, y), (x2, y2) = scr[i], scr[run[j + 1]]
                ic.draw.line([(x, y), (x2, y2)], fill=col, width=int(w))
                if j:  # round joint, so the band has no notches where the segments meet
                    ic.draw.ellipse((x - w / 2 + 1, y - w / 2 + 1, x + w / 2 - 1, y + w / 2 - 1), fill=col)
                shine.append((x, y) if is_front and b > 0.84 else None)
            # a glint along the brightest stretch of the near half
            stretch = []
            for p in shine + [None]:
                if p is not None:
                    stretch.append(p)
                elif len(stretch) > 3:
                    ic.line(stretch[1:-1], max(3, int(w * 0.3)), (255, 248, 216, 220))
                    stretch = []
                else:
                    stretch = []
            if ticks:
                step = max(1, 240 // ticks)

                def marks(d, run=run, pts3=pts3, centre=centre, r=r, w=w, step=step):
                    for i in run[:-1]:
                        if i % step:
                            continue
                        radial = (pts3[i] - centre) / r
                        p, q = proj(pts3[i] - radial * w * 0.42)[0], proj(pts3[i] + radial * w * 0.42)[0]
                        d.line([p, q], fill=(70, 40, 10, 190), width=3)

                ic.overlay(marks)
        elif kind == "axis":
            p, q = payload
            ic.line([p, q], int(9 * widths) + 6, (36, 22, 8, 235))
            ic.line([p, q], int(9 * widths), (110, 104, 96))
            for x, y in (p, q):
                rr = 11 * widths
                ic.ellipse((x - rr, y - rr, x + rr, y + rr), BRASS[0], BRASS[1], edge=3)
        else:
            er = 0.21 * R
            em = ic.mask("ellipse", (cx - er, cy - er, cx + er, cy + er))
            ic.fill(em, "#7cb0c4", "#173444", radial=(cx - er * 0.45, cy - er * 0.5, er * 2.1), noise=0.08)
            for dx, dy, s in ((-0.3, -0.2, 0.4), (0.25, 0.2, 0.35), (0.1, -0.45, 0.25)):
                tint(ic, ic.mask("ellipse", (cx + er * (dx - s), cy + er * (dy - s * 0.7), cx + er * (dx + s),
                                             cy + er * (dy + s * 0.7))), em, (170, 140, 80), 0.6, 2)
            ic.draw.ellipse((cx - er * 0.6, cy - er * 0.66, cx - er * 0.2, cy - er * 0.32), fill=(230, 246, 250, 255))
            ic.overlay(lambda d: d.ellipse((cx - er, cy - er, cx + er, cy + er), outline=(30, 24, 18, 220), width=4))


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.95
    ic.grade["gamma"] = 0.74

    # ---- hall roof: lead-grey slates, hipped, behind the cornice
    roof = [(HX0 + 4, CTOP + 6), (HX1 + 6, CTOP + 6), (HX1 - 60, 404), (HX0 + 70, 404)]
    rm = shingles(ic, roof, "#868a92", "#383c44", course=22, stagger=34)
    tint(ic, ic.poly_mask([(HX1 - 200, 404), (HX1, 404), (HX1 + 20, CTOP + 10), (HX1 - 160, CTOP + 10)]), rm, (0, 0, 0), 0.22, 30)
    for x in (430, 680):  # chimneys
        ic.rect((x, 372, x + 34, 424), "#c8b694", "#7e6a50", edge=4)
        ic.rect((x - 6, 364, x + 40, 376), "#d8c8a6", "#8e7a5c", edge=3)

    # ---- hall walls: dressed stone above, rustication below
    wall = ic.mask("rectangle", (HX0, CBOT, HX1, BASE))
    upper = ic.mask("rectangle", (HX0, CBOT, HX1, SY0))
    lower = ic.mask("rectangle", (HX0, SY1, HX1, BASE))
    ashlar(ic, upper, (HX0, CBOT, HX1, SY0), STONE, course=31, block=74)
    ashlar(ic, lower, (HX0, SY1, HX1, BASE), RUST, course=36, block=90, rustic=True)
    tint(ic, ic.mask("rectangle", (HX0, BASE - 90, HX1, BASE)), wall, (64, 60, 36), 0.25, 24)  # damp and dirt low
    tint(ic, ic.mask("rectangle", (HX1 - 150, CBOT, HX1 + 30, BASE)), wall, (20, 10, 0), 0.2, 50)
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(16):
        x = ic.random.uniform(HX0 + 10, HX1 - 10)
        y = ic.random.choice((CBOT + 4, SY1 + 2))
        sd.line([(x, y), (x + ic.random.uniform(-3, 3), y + ic.random.uniform(40, 120))], fill=255,
                width=int(ic.random.uniform(4, 9)))
    tint(ic, streaks, wall, (70, 58, 40), 0.16, 4)
    ic.rect((HX0 - 4, SY0, HX1 + 4, SY1), "#f0e2c0", "#a88e66", edge=4)  # string course
    tint(ic, ic.mask("rectangle", (HX0, SY1, HX1, SY1 + 26)), wall, (0, 0, 0), 0.3, 6)

    # ---- wing windows and the portico bay
    for x0 in (346, 700):
        arched_window(ic, x0, 548, x0 + 48, 652, wall)
        square_window(ic, x0, 772, x0 + 48, 856, wall)
    tint(ic, ic.mask("rectangle", (COLS[0] - 30, CBOT, COLS[3] + 30, BASE)), wall, (30, 20, 8), 0.12, 20)  # bay in shade
    arched_window(ic, PCX - 24, 560, PCX + 24, 652, wall)
    dx0, dx1 = PCX - 28, PCX + 28
    ring = arch_mask(ic, dx0 - 16, dx1 + 16, 760 - 16, BASE)
    ic.fill(ring, "#f2e4c2", "#a88e66", (744, BASE), noise=0.12)
    ic.door(dx0, 760, dx1, BASE - 6, arched=True, surround=None)
    tint(ic, ic.mask("rectangle", (dx0, 760, dx1, 810)), None, (0, 0, 0), 0.3, 8)
    for x0 in (COLS[0] + 26, COLS[2] + 26):  # oval niches between the outer column pairs
        nm = ic.mask("ellipse", (x0, 600, x0 + 18, 640))
        ic.fill(nm, "#7a6650", "#3a2c1e", noise=0.06)
    for cxl in COLS:
        column(ic, cxl, CBOT + 6, BASE - 2, 19, wall)
    cornice(ic, HX0 - 6, HX1 + 6, CTOP, CBOT, wall)
    pediment(ic, COLS[0] - 30, COLS[3] + 30, CTOP + 2, 372)

    # ---- steps before the portico
    for k in range(3):
        x0, x1 = COLS[0] - 44 - k * 14, COLS[3] + 44 + k * 14
        y0 = BASE - 6 + k * 15
        ic.rect((x0, y0, x1, y0 + 15), "#e0d0aa", "#9a8260", edge=4)
        ic.line([(x0 + 4, y0 + 3), (x1 - 4, y0 + 3)], 3, (255, 248, 228, 140))

    # ---- observatory tower, in front of the hall's left end
    tint(ic, ic.mask("rectangle", (TX1, CBOT - 40, TX1 + 60, BASE)), None, (20, 10, 0), 0.4, 14)  # its shadow on the hall
    tw_up = ic.mask("rectangle", (TX0, TTOP, TX1, SY0))
    tw_lo = ic.mask("rectangle", (TX0, SY1, TX1, BASE))
    tower = ic.mask("rectangle", (TX0, TTOP, TX1, BASE))
    ashlar(ic, tw_up, (TX0, TTOP, TX1, SY0), STONE, course=31, block=70)
    ashlar(ic, tw_lo, (TX0, SY1, TX1, BASE), RUST, course=36, block=86, rustic=True)
    tint(ic, ic.mask("rectangle", (TX0 - 20, TTOP, TX0 + 70, BASE)), tower, (255, 240, 210), 0.12, 30)
    tint(ic, ic.mask("rectangle", (TX1 - 60, TTOP, TX1 + 10, BASE)), tower, (20, 10, 0), 0.2, 30)
    tint(ic, ic.mask("rectangle", (TX0, BASE - 90, TX1, BASE)), tower, (64, 60, 36), 0.25, 24)
    quoins(ic, TX0, TTOP + 30, SY0, -1, 31)
    quoins(ic, TX1, TTOP + 30, SY0, 1, 31)
    ic.rect((TX0 - 6, SY0, TX1 + 6, SY1), "#f0e2c0", "#a88e66", edge=4)
    tint(ic, ic.mask("rectangle", (TX0, SY1, TX1, SY1 + 26)), tower, (0, 0, 0), 0.3, 6)
    ic.rect((TX0 - 6, CTOP + 14, TX1 + 6, CBOT - 6), "#f0e2c0", "#a88e66", edge=4)  # band in line with the hall cornice
    tint(ic, ic.mask("rectangle", (TX0, CBOT - 6, TX1, CBOT + 18)), tower, (0, 0, 0), 0.3, 6)
    clock_face(ic, TCX, 438, 26)
    arched_window(ic, TCX - 28, 540, TCX + 28, 662, tower)
    arched_window(ic, TCX - 26, 760, TCX + 26, 862, tower)
    ic.outline([(TX0, TTOP), (TX1, TTOP), (TX1, BASE), (TX0, BASE)], 5)
    cornice(ic, TX0 - 8, TX1 + 8, TTOP - 26, TTOP, tower)

    # ---- drum and dome on the tower, the telescope out of the slit
    DR0, DR1, DTOP = TCX - 84, TCX + 84, 312
    drum = ic.mask("rectangle", (DR0, DTOP, DR1, TTOP - 26))
    ashlar(ic, drum, (DR0, DTOP, DR1, TTOP - 26), STONE, course=22, block=48)
    tint(ic, ic.mask("rectangle", (TCX + 20, DTOP, DR1 + 10, TTOP)), drum, (20, 10, 0), 0.32, 18)
    tint(ic, ic.mask("rectangle", (DR0, DTOP, DR1, DTOP + 22)), drum, (0, 0, 0), 0.4, 8)
    for x in (TCX - 52, TCX - 6, TCX + 40):
        ic.rect((x, DTOP + 22, x + 14, TTOP - 38), "#3a3c40", "#141518", edge=3)
    ic.outline([(DR0, DTOP), (DR1, DTOP), (DR1, TTOP - 26), (DR0, TTOP - 26)], 4)
    dome(ic, TCX, DTOP, 196, 150)
    lam, th = math.radians(18.5), math.radians(42)
    sx, sy = TCX + 98 * math.sin(lam) * math.cos(th), DTOP - 150 * math.sin(th)
    telescope(ic, (sx - 8, sy + 10), (sx + 196, sy - 122), 34, 46)

    # ---- plinth
    ic.rect((HX0 - 10, BASE - 14, HX1 + 10, BASE + 8), "#bcae92", "#7c6e58", edge=4)
    ic.rect((TX0 - 10, BASE - 14, TX1 + 10, BASE + 8), "#bcae92", "#7c6e58", edge=4)
    ic.line([(TX0 - 8, BASE - 11), (HX1 + 8, BASE - 11)], 3, (255, 246, 226, 110))

    # ---- the armillary sphere on its pedestal
    ptop = AY + int(AR * 1.12) + 26
    pedestal(ic, AX, ptop, BASE + 44)
    ic.line([(AX, AY + AR * 1.0), (AX, ptop + 2)], 20, (36, 22, 8, 235))
    ic.line([(AX, AY + AR * 1.0), (AX, ptop + 2)], 13, (176, 128, 48))
    ic.ellipse((AX - 15, ptop - 30, AX + 15, ptop - 6), BRASS[0], BRASS[1], edge=3)
    ic.ellipse((AX - 30, ptop - 8, AX + 30, ptop + 6), BRASS[0], BRASS[1], edge=3)
    armillary(ic, AX, AY, AR, widths=1.15, full=False)
    fill_slivers(ic, (AX - AR * 1.3, AY - AR * 1.4, AX + AR * 1.3, AY + AR * 1.25))
