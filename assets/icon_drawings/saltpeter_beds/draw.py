"""Niter Beds (saltpeter_beds): a long thatched shed over an earth bed crusted white, with leaching vats.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/saltpeter_beds/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/saltpeter_beds

Identity: the long, low, open-sided thatched shed seen in three-quarter view (hipped end, ragged
eave with a shadow band under it) over a heaped bed of dark manured earth and straw against a warm
grey wattle back wall, a mounded windrow in front with a rake leaning across it; both beds carry a
thin, broken white niter efflorescence along their ridges. On the right, the leaching shed: plank
lean-to with tubs on a stand dripping lye into a trough (the Leaching Vats slot), and a basket of
white crude saltpeter. Vanilla saltpeter buildings (grey heap and brick columns) look nothing like
it. Local helpers: ``union``, ``tint``, ``paste_clipped``, ``timber``, ``planks``, ``thatch``
(copied), new ``crust``, ``earth_texture``, ``earth_bed``, ``windrow``, ``wattle``, ``tub``,
``drip``, ``rake``, ``hip_roof``, ``ragged_eave``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 9
REFS = ("saltpeter_workshop", "putrefaction_works", "farming_village", "tar_kiln")

WOOD, WOOD_DK = "#8a6240", "#4c3422"
EARTH, EARTH_DK = "#7a5838", "#321e0e"
CRUST = (236, 232, 220)
GROUND = 840


# ---------------------------------------------------------------- helpers
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


def paste_clipped(ic: Icon, lay: Image.Image, m: Image.Image) -> None:
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam as a polygon: lit upper half, darker lower half, grain along it (no heavy rim)."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    lower = [(x0, y0), (x1, y1), pts[2], pts[3]]
    ic.shade(ic.intersect(ic.poly_mask(lower), m), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26) -> Image.Image:
    """Vertical board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    v = min(xs)
    while v < max(xs):
        w = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + w, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        for _ in range(2):
            gx = v + R.uniform(4, w - 4)
            d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += w
    paste_clipped(ic, lay, m)
    return m


def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands running down the slope, layered courses with a dark
    underside and a lit combed lip, weathered blotches. Returns the mask."""
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
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):  # course edge: short irregular segments
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
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def crust(ic: Icon, m: Image.Image, ridge, depth: float, density: float = 1.0) -> None:
    """Niter efflorescence along a ridge line: a greyish-white film fading down into the earth, broken
    into thin crystalline flakes right on the ridge, with small bright specks. ``ridge`` = points."""
    R = ic.random
    xs = [p[0] for p in ridge]
    # soft greyish film hugging the ridge and fading downwards
    band = ic.poly_mask(list(ridge) + [(x, y + depth) for x, y in ridge[::-1]])
    tint(ic, ic.poly_mask(list(ridge) + [(x, y + depth * 0.4) for x, y in ridge[::-1]]), m, (222, 220, 210), 0.6, depth * 0.18)
    film = Image.new("L", (ic.size, ic.size), 0)
    fd = ImageDraw.Draw(film)
    for _ in range(int((max(xs) - min(xs)) / 2 * density)):  # broken thin flakes on the ridge and top face
        i = R.randrange(len(ridge))
        x, y = ridge[i]
        x += R.uniform(-12, 12)
        y += R.uniform(0, depth * 0.4) ** 2 / (depth * 0.4)
        ln = R.uniform(8, 26)
        fd.line([(x, y), (x + ln, y + R.uniform(-3, 3))], fill=R.randint(120, 255), width=R.choice((2, 3, 4)))
    ic.shade(ic.intersect(film.filter(ImageFilter.GaussianBlur(1.2)), band, m), (244, 242, 236), 0.95)

    def specks(d: ImageDraw.ImageDraw) -> None:
        for _ in range(int((max(xs) - min(xs)) / 5 * density)):
            i = R.randrange(len(ridge))
            x, y = ridge[i]
            x += R.uniform(-10, 10)
            y += R.uniform(0, depth * 0.6) ** 2 / (depth * 0.6)
            r = R.uniform(1.2, 2.4)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 250, R.randint(140, 240)))
        for _ in range(int(4 * density)):  # a few glinting crystals
            i = R.randrange(len(ridge))
            x, y = ridge[i]
            y += R.uniform(2, depth * 0.15)
            d.line([(x - 5, y), (x + 5, y)], fill=(255, 255, 255, 170), width=2)
            d.line([(x, y - 4), (x, y + 4)], fill=(255, 255, 255, 170), width=2)

    ic.overlay(specks, m)


def earth_texture(ic: Icon, m: Image.Image, x0: float, x1: float, top: float, base: float) -> None:
    """Clods and straw bedding mixed into the dark earth."""
    R = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for _ in range(int((x1 - x0) * (base - top) / 600)):
            x, y = R.uniform(x0, x1), R.uniform(top, base)
            r = R.uniform(5, 12)
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(24, 16, 10, 120))
            d.arc((x - r, y - r * 0.7, x + r, y + r * 0.7), 190, 320, fill=(170, 130, 90, 90), width=3)
        for _ in range(int((x1 - x0) / 9)):  # straw streaks
            x, y = R.uniform(x0, x1), R.uniform(top, base)
            a = R.uniform(-0.6, 0.6)
            ln = R.uniform(12, 30)
            d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln)], fill=(200, 172, 108, R.randint(70, 150)), width=3)

    ic.overlay(paint, m)


def earth_bed(ic: Icon, x0: float, x1: float, base: float, top: float, lit: float = 1.0) -> Image.Image:
    """Long heaped bed of manured earth and straw under the roof: rounded ridge, crust on the ridge."""
    R = ic.random
    top_pts = []
    for t in np.linspace(0, 1, 40):
        x = x0 + (x1 - x0) * t
        y = base - (base - top) * (math.sin(t * math.pi) ** 0.35) * (1 - 0.05 * math.sin(t * 9)) + R.uniform(-3, 3)
        top_pts.append((x, y))
    pts = [(x0, base)] + top_pts + [(x1, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, EARTH, EARTH_DK, (top, base), noise=0.3, chroma=0.12)
    tint(ic, ic.poly_mask(top_pts + [(x, y + (base - top) * 0.3) for x, y in top_pts[::-1]]), m, (255, 226, 186), 0.2 * lit, 8)
    tint(ic, ic.mask("rectangle", (x0 - 20, base - (base - top) * 0.4, x1 + 20, base + 10)), m, (14, 8, 4), 0.35, 16)
    earth_texture(ic, m, x0, x1, top, base)
    crust(ic, m, top_pts[3:-3], (base - top) * 0.45, 0.8)
    ic.outline(pts, 4, (40, 26, 16, 160))
    return m


def windrow(ic: Icon, x0: float, x1: float, base: float, top: float) -> Image.Image:
    """Open niter bed in front: a mounded windrow seen from the raised camera. Rounded ridge, the near
    side slopes down to a soft, irregular foot on the ground, rounded ends; crust along the ridge."""
    R = ic.random
    H = base - top
    ph = R.uniform(0, 6)
    ridge, foot = [], []
    for t in np.linspace(0, 1, 50):
        x = x0 + (x1 - x0) * t
        end = min(t, 1 - t) / 0.12
        rise = min(1.0, end) ** 0.6
        ridge.append((x, base - H * rise * (0.94 + 0.06 * math.sin(t * 11 + ph)) - R.uniform(0, 3)))
        foot.append((x + R.uniform(-2, 2), base + 10 * math.sin(t * 7 + ph) * min(1.0, end) + R.uniform(-3, 3)))
    pts = smooth(ridge + foot[::-1], 1, closed=True)
    m = ic.poly_mask(pts)
    ic.fill(m, "#86603c", EARTH_DK, (top, base + 10), noise=0.3, chroma=0.12)
    # lit rounded ridge and top face, near slope darkening to the foot, far end in shadow
    tint(ic, ic.poly_mask(ridge + [(x, y + H * 0.35) for x, y in ridge[::-1]]), m, (255, 226, 186), 0.24, 10)
    tint(ic, ic.poly_mask([(x, y + H * 0.55) for x, y in ridge] + [(x, y + 20) for x, y in foot[::-1]]), m, (14, 8, 4), 0.4, 16)
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.1, top - 10, x1 + 10, base + 20)), m, (14, 8, 4), 0.3, 20)
    earth_texture(ic, m, x0, x1, top, base)
    crust(ic, m, ridge[4:-4], H * 0.5, 1.1)
    # soft irregular edge on the ground: darker rim fading up, crumbs spilling out
    tint(ic, ic.poly_mask([(x, y - 16) for x, y in foot] + [(x, y + 20) for x, y in foot[::-1]]), m, (20, 12, 6), 0.45, 6)

    def crumbs(d: ImageDraw.ImageDraw) -> None:
        for _ in range(40):
            x, y = foot[R.randrange(len(foot))]
            y += R.uniform(0, 8)
            r = R.uniform(3, 7)
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(R.randint(60, 100), R.randint(40, 64), R.randint(22, 36), 255))

    ic.overlay(crumbs)
    ic.outline(pts, 3, (40, 26, 16, 130))
    return m


def smooth(pts, n: int = 2, closed: bool = True):
    """Chaikin corner cutting on a closed polygon."""
    pts = [tuple(p) for p in pts]
    for _ in range(n):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out += [(p[0] * 0.75 + q[0] * 0.25, p[1] * 0.75 + q[1] * 0.25), (p[0] * 0.25 + q[0] * 0.75, p[1] * 0.25 + q[1] * 0.75)]
        pts = out
    return pts


def wattle(ic: Icon, pts, c1="#7c6a54", c2="#4a3e30") -> Image.Image:
    """Warm grey wattle panel: stakes and woven horizontal withies, clay daub showing in patches."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.25, chroma=0.06)
    R = ic.random

    def weave(d: ImageDraw.ImageDraw) -> None:
        y, k = min(ys) + 6, 0
        while y < max(ys):
            x = min(xs)
            while x < max(xs):
                seg = R.uniform(30, 50)
                off = 4 if (k + int(x / 40)) % 2 else -4
                d.line([(x, y + off), (x + seg, y - off)], fill=(150, 132, 104, 80), width=7)
                d.line([(x, y + off + 5), (x + seg, y - off + 5)], fill=(40, 30, 20, 90), width=3)
                x += seg
            y += 17
            k += 1
        for x in np.arange(min(xs) + 20, max(xs), 44):
            d.line([(x, min(ys)), (x + R.uniform(-3, 3), max(ys))], fill=(60, 44, 30, 130), width=6)

    ic.overlay(weave, m)
    return m


def tub(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Coopered leaching tub, open top with dark lye, iron hoops, a spigot at the foot."""
    w = x1 - x0
    body = [(x0, y0), (x1, y0), (x1 - w * 0.06, y1), (x0 + w * 0.06, y1)]
    m = ic.poly_mask(body)
    ic.fill(m, "#a4764c", "#4c3120", (x0, x1), vertical=False, noise=0.2)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for sx in np.linspace(x0 + w / 6, x1 - w / 6, 5):
        d.line([(sx, y0), (sx + (sx - (x0 + x1) / 2) * -0.06, y1)], fill=(50, 30, 16, 120), width=3)
    paste_clipped(ic, lay, m)
    for f in (0.22, 0.78):
        hy = y0 + (y1 - y0) * f
        ic.line([(x0 + w * 0.06 * f, hy), (x1 - w * 0.06 * f, hy)], 9, (48, 46, 46))
    ic.outline(body, 4, (40, 26, 16, 180))
    ry = w * 0.16
    ic.fill(ic.mask("ellipse", (x0 - 2, y0 - ry, x1 + 2, y0 + ry)), "#b88a5e", "#7a5434", noise=0.2)
    inner = ic.mask("ellipse", (x0 + 10, y0 - ry + 7, x1 - 10, y0 + ry - 7))
    ic.fill(inner, "#4a3a28", "#241a10", noise=0.12)
    crust(ic, inner, [(x, y0 - ry * 0.3) for x in np.linspace(x0 + 16, x1 - 16, 12)], ry * 0.8, 0.6)
    ic.overlay(lambda d: d.ellipse((x0 - 2, y0 - ry, x1 + 2, y0 + ry), outline=(40, 26, 16, 190), width=4))
    sx = x0 + w * 0.5
    ic.line([(sx, y1 - 4), (sx + 4, y1 + 14)], 9, (86, 60, 38))  # spigot


def drip(ic: Icon, x: float, y0: float, y1: float) -> None:
    """Short bright drip streak of lye with drops, readable at game size."""
    ic.line([(x, y0), (x, y1 - 14)], 6, (236, 232, 206, 235))
    ic.line([(x - 1, y0), (x - 1, y1 - 20)], 2, (255, 255, 255, 200))
    for yy, r in ((y1 - 6, 5), (y1 + 4, 4)):
        ic.draw.ellipse((x - r, yy - r, x + r, yy + r), fill=(240, 236, 214, 255))


def rake(ic: Icon, head, end, n: int = 6) -> None:
    """Long wooden rake leaning across the bed: thick light handle, crossbar with ``n`` tines."""
    hx, hy = head
    timber(ic, head, end, 18, "#c8a06a", "#7a5634")
    bar0, bar1 = (hx - 70, hy + 8), (hx + 70, hy - 6)
    for k in range(n):
        t = k / (n - 1)
        x, y = bar0[0] + (bar1[0] - bar0[0]) * t, bar0[1] + (bar1[1] - bar0[1]) * t
        timber(ic, (x, y), (x - 3, y + 32), 8, "#c0986a", "#6e4c2c")
    timber(ic, bar0, bar1, 16, "#d0aa74", "#7e5a36")


def hip_roof(ic: Icon, front, end) -> Image.Image:
    """Thatched hipped roof in three-quarter view: the long front plane and the lit hip end on the left,
    a darker hip line between them, a ragged eave edge. Returns the union mask."""
    em = thatch(ic, end, "#d2b474", "#806438", course=36)
    tint(ic, em, None, (255, 236, 196), 0.12, 0)
    fm = thatch(ic, front, "#bc9c60", "#5a4222", course=40)
    ic.line([front[3], front[0]], 6, (60, 40, 20, 170))  # hip line
    return union(em, fm)


def ragged_eave(ic: Icon, pts, depth: float = 18) -> None:
    """Ragged straw ends hanging below an eave line (list of points left to right)."""
    R = ic.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
            L = math.hypot(xb - xa, yb - ya)
            for _ in range(int(L / 4)):
                t = R.random()
                x, y = xa + (xb - xa) * t, ya + (yb - ya) * t
                ln = R.uniform(depth * 0.3, depth)
                c = R.choice([(196, 168, 106), (150, 122, 72), (110, 86, 50), (214, 190, 130)])
                d.line([(x, y - 6), (x + R.uniform(-3, 3), y + ln)], fill=c + (230,), width=R.choice((3, 4)))

    ic.overlay(paint)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86

    # ---- leaching shed on the right: plank lean-to
    lx0, lx1 = 720, 1004
    planks(ic, [(lx0 + 10, 390), (lx1 - 14, 390), (lx1 - 14, GROUND - 10), (lx0 + 10, GROUND - 10)], "#8e7056", "#4c3a2a", 30)
    ic.rect((770, 470, 870, GROUND - 10), "#241a12", "#100a06", edge=4)  # open door
    ic.shade(ic.mask("rectangle", (lx0, 390, lx1, 450)), alpha=0.5, blur=12)
    thatch(ic, [(lx0 - 16, 420), (lx1 + 10, 420), (lx1 - 6, 300), (lx0 + 6, 300)], "#a8905c", "#5e4a2a", course=36)
    ragged_eave(ic, [(lx0 - 16, 418), (lx1 + 10, 418)], 16)
    ic.outline([(lx0 - 16, 420), (lx1 + 10, 420), (lx1 - 6, 300), (lx0 + 6, 300)], 5)

    # ---- long bed shed in three-quarter view: lit wattle end wall on the left, warm grey back wall
    eave = 430
    back = [(96, 380), (716, 380), (716, GROUND - 110), (96, GROUND - 110)]
    wattle(ic, back)
    # dappled light falling between the posts onto the back wall
    for cx, cy, r in ((170, 520, 60), (380, 500, 70), (590, 540, 60), (290, 610, 40), (500, 620, 44)):
        tint(ic, ic.mask("ellipse", (cx - r, cy - r * 0.7, cx + r, cy + r * 0.7)), None, (255, 232, 186), 0.2, 18)
    end_wall = [(14, 372), (96, 424), (96, GROUND - 80), (14, GROUND - 130)]
    wattle(ic, end_wall, "#9a8468", "#62543e")
    tint(ic, ic.poly_mask(end_wall), None, (255, 236, 200), 0.1, 0)
    bed = earth_bed(ic, 110, 704, GROUND - 90, 600, lit=0.8)
    # shadow band under the eave overhang on the wall and the back of the bed
    ic.shade(ic.mask("rectangle", (0, eave - 20, 730, eave + 70)), (20, 10, 4), 0.5, blur=18)
    for x in (98, 300, 500, 700):
        timber(ic, (x, eave - 10), (x + 3, GROUND - 60), 28)
    timber(ic, (90, eave - 8), (716, eave - 8), 22)  # wall plate
    front = [(80, eave + 22), (726, eave + 14), (664, 240), (236, 246)]
    end = [(8, 378), (80, eave + 22), (236, 246)]
    rm = hip_roof(ic, front, end)
    tint(ic, ic.mask("rectangle", (0, eave - 30, 740, eave + 40)), rm, (30, 18, 6), 0.3, 14)  # weathered eave
    ragged_eave(ic, [(8, 378), (80, eave + 22), (400, eave + 22), (726, eave + 14)], 20)
    ic.outline([end[0], front[0], front[1], front[2], front[3]], 6)

    # ---- open bed in front: a mounded windrow crusted white, a rake leaning across it
    windrow(ic, 34, 610, GROUND + 26, 704)
    rake(ic, (206, 690), (590, 900))

    # ---- leaching vats on a stand, dripping into a trough
    timber(ic, (590, 700), (1000, 700), 20)
    for x in (610, 790, 980):
        timber(ic, (x, 700), (x, 800), 18)
    for x0 in (604, 742, 872):
        tub(ic, x0, 580, x0 + 120, 696)
    ic.rect((600, 786, 1004, 836), "#7e5a3a", "#44301e", edge=5)  # collecting trough
    ic.fill(ic.mask("rectangle", (612, 790, 992, 804)), "#d6d2b4", "#9e9a80", noise=0.08)  # lye line
    ic.line([(612, 791), (992, 791)], 3, (255, 255, 240, 180))
    for x in (668, 806, 936):
        drip(ic, x, 716, 790)
    # basket of crude saltpeter in front of the stand
    ic.basket(836, 846, 1016, 950)
    ic.fill(ic.poly_mask(ic.jitter(926, 846, 88, 28, 16, 0.12)), "#f0ece0", "#a8a292", noise=0.2)
    top = ic.poly_mask(ic.jitter(926, 846, 88, 28, 16, 0.05))
    crust(ic, top, [(x, 836) for x in np.linspace(850, 1000, 14)], 22, 0.8)
