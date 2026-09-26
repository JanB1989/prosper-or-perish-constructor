"""Engineered Brine Saltworks (engineered_brine_saltworks): graduation tower, wind pump, flume and a stone panhouse.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game     uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/engineered_brine_saltworks/draw.py     --out ../ProsperOrPerishConstructor/artifacts/icons/engineered_brine_saltworks

Tier 1 of the inland saltworks (pumped brine channels, concentration houses, larger panhouses). A long
graduation tower (brushwood wall between timber posts, brine trough and board roof, basin at its foot)
with a small wind pump at its end, a flume on a trestle carrying the concentrated brine into a masonry
panhouse with a tiled roof and two smoking chimneys; the salt loaves of the Inland Saltworks and a cask
stand in front.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 53
REFS = ("salt_collector", "windmill", "mercury_patio", "aqueduct_system")

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


def steam(ic: Icon, paths, alpha=0.5, clip: bool = False) -> None:
    """Soft rising steam: thick blurred wisps along the given polylines."""
    lay = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(lay)
    for pts, w in paths:
        d.line(pts, fill=255, width=w, joint="curve")
    ic.shade(lay, (240, 236, 228), alpha, blur=10, clip=clip)


def salt_cone(ic: Icon, cx: float, base: float, w: float, h: float, tone: float = 0.0) -> None:
    """Conical salt loaf (Fuderstock) drying on its board: smooth white cone, lit left flank, cool
    shadow on the right, a darker damp foot and a few crystal glints."""
    ts = np.linspace(0, 1, 24)
    prof = lambda t: (0.18 + 0.82 * t ** 0.62) * min(1.0, (t / 0.06) ** 0.5)  # noqa: E731  rounded tip, bulging flanks
    left = [(cx - w / 2 * prof(t), base - h + h * t) for t in ts]
    right = [(cx + w / 2 * prof(t), base - h + h * t) for t in ts[::-1]]
    foot = [(cx + w / 2 * math.cos(a), base + w * 0.09 * math.sin(a)) for a in np.linspace(0, math.pi, 16)]
    pts = left + foot[::-1] + right
    m = ic.poly_mask(pts)
    k = np.array([1.0, 0.95, 0.92]) ** (tone * 2) if tone > 0 else np.ones(3)
    c1 = tuple(int(v) for v in rgb("#fbf8f2") * k)
    c2 = tuple(int(v) for v in rgb("#d2c9be") * k)
    ic.fill(m, c1, c2, (cx - w * 0.45, cx + w * 0.55), vertical=False, noise=0.1, chroma=0.04)
    tint(ic, ic.poly_mask([(cx + w * 0.08, base - h), (cx + w * 0.6, base + 20), (cx + w * 0.1, base + 20)]), m,
         (70, 78, 96), 0.2, 14)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.12, cx + w, base + 30)), m, (90, 78, 66), 0.22, 10)
    tint(ic, ic.poly_mask([(cx - w * 0.06, base - h * 0.92), (cx - w * 0.3, base - h * 0.3),
                           (cx - w * 0.18, base - h * 0.3)]), m, (255, 255, 255), 0.45, 5)
    crystal(ic, m, (cx - w / 2, base - h, cx + w / 2, base), 0.35)
    ic.outline(pts, 4, (60, 52, 48, 170))


def ashlar(ic: Icon, box, base="#b8a88e", dark="#7a6a56", course=(30, 42), width=(56, 110), moss: bool = True) -> None:
    """Weathered ashlar face: per-block tint, soft bevels (lit top/left, dark bottom/right), grime
    streaks from the top, darker damp foot."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, base, dark, (x0 - 200, x1 + 200), vertical=False, noise=0.22, chroma=0.14)
    R = ic.random
    lay, d = layer()
    y = y0
    while y < y1:
        yb = min(y + R.randint(*course), y1)
        x = x0 - R.randint(0, width[0])
        while x < x1:
            xb = x + R.randint(*width)
            bx0, bx1 = max(x, x0), min(xb, x1)
            if bx1 - bx0 > 8:
                t = R.uniform(-1, 1)
                d.rectangle((bx0, y, bx1, yb), fill=(255, 240, 215, int(34 * t)) if t > 0 else (30, 22, 14, int(-52 * t)))
                d.line([(bx0 + 4, y + 4), (bx1 - 5, y + 4)], fill=(255, 246, 228, 70), width=4)
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
            x = xb
        y = yb
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 60)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.2, 0.6) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 12), y0, sx + R.uniform(5, 12), y0 + ln))),
                 (35, 30, 22), R.uniform(0.08, 0.16), blur=6)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - 80, x1, y1 + 40))), (30, 30, 20), 0.35, blur=22)


def brushwood(ic: Icon, box) -> Image.Image:
    """Blackthorn brushwood wall of a graduation tower: warm grey-brown mass of short vertical and
    diagonal twig strokes, dry and light at the top, dark and wet at the bottom with brine-drip
    streaks, a few white salt-crust highlights."""
    x0, y0, x1, y1 = box
    m = ic.mask("rectangle", box)
    ic.fill(m, "#9a8466", "#3e3226", (y0, y1), noise=0.22, chroma=0.08)
    R = ic.random
    lay, d = layer()
    n = int((x1 - x0) * (y1 - y0) / 110)
    for _ in range(n):
        x, y = R.uniform(x0 - 4, x1 + 4), R.uniform(y0 - 4, y1 + 4)
        up = (y - y0) / (y1 - y0)  # 0 top .. 1 bottom
        a = math.radians(R.choice((90, 90, 90, 62, 118, 45, 135)) + R.uniform(-12, 12))
        L = R.uniform(10, 24)
        dx, dy = math.cos(a) * L / 2, math.sin(a) * L / 2
        if R.random() < 0.5:
            col = (int(196 - 70 * up), int(174 - 66 * up), int(136 - 56 * up), R.randint(110, 190))
        else:
            col = (int(52 - 20 * up), int(40 - 16 * up), int(30 - 12 * up), R.randint(110, 190))
        d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=col, width=R.choice((3, 3, 4)))
    composite(ic, lay, m)
    # wet, darker lower part
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y0 + (y1 - y0) * 0.5, x1, y1 + 40))), (18, 22, 24), 0.4, blur=30)
    # brine-drip streaks: dark wet runs with a glint, mostly in the lower two thirds
    lay, d = layer()
    for _ in range(int((x1 - x0) / 22)):
        x = R.uniform(x0 + 6, x1 - 6)
        ys = R.uniform(y0 + (y1 - y0) * 0.25, y0 + (y1 - y0) * 0.6)
        ye = y1 - R.uniform(0, 40)
        d.line([(x, ys), (x + R.uniform(-3, 3), ye)], fill=(20, 22, 22, 90), width=R.randint(5, 8))
        d.line([(x - 1, ys + 10), (x - 1 + R.uniform(-3, 3), ye - 10)], fill=(200, 216, 218, R.randint(60, 110)), width=2)
    composite(ic, lay.filter(ImageFilter.GaussianBlur(1)), m)
    # salt crust: white bloom along the top under the trough and a few highlights on twigs
    lay, d = layer()
    for _ in range(int((x1 - x0) / 26)):
        x = R.uniform(x0, x1)
        y = y0 + abs(R.gauss(0, 1)) * (y1 - y0) * 0.12
        r = R.uniform(2.5, 5)
        d.ellipse((x - r * 1.6, y - r * 0.6, x + r * 1.6, y + r * 0.6), fill=(244, 242, 236, R.randint(120, 210)))
    for _ in range(int((x1 - x0) / 30)):
        x, y = R.uniform(x0, x1), R.uniform(y0 + 40, y1 - 40)
        d.line([(x, y), (x + R.uniform(-4, 4), y + R.uniform(6, 14))], fill=(240, 240, 234, 170), width=3)
    composite(ic, lay, m)
    return m


# ---- parts -------------------------------------------------------------------------------------
def wind_pump(ic: Icon, cx: float, hub_y: float, foot: float) -> None:
    """Wind pump at the tower's left end: a tapering lattice trestle down to the basin, four lattice
    sails, the pump rod running down into the brine."""
    top = hub_y + 34
    lx0, lx1 = cx - 66, cx + 66
    tx0, tx1 = cx - 18, cx + 18
    ic.shade(ic.mask("ellipse", (lx0 - 20, foot - 14, lx1 + 20, foot + 18)), alpha=0.4, blur=10)
    # back legs, then the pump rod, then the lit front legs and lattice
    timber(ic, (lx0 + 34, foot - 6), (tx0 + 8, top), 16, "#6e4626", "#3e2612")
    timber(ic, (lx1 - 34, foot - 6), (tx1 - 8, top), 16, "#6e4626", "#3e2612")
    ic.line([(cx + 2, hub_y + 20), (cx + 2, foot - 8)], 8, (58, 54, 52))
    ic.line([(cx, hub_y + 20), (cx, foot - 8)], 3, (160, 156, 150, 180))
    timber(ic, (lx0, foot), (tx0, top), 22, "#b27842", "#643e1e")
    timber(ic, (lx1, foot), (tx1, top), 22, "#b27842", "#643e1e")
    levels = [0.0, 0.27, 0.52, 0.74, 0.92]
    pos = lambda t: (lx0 + (tx0 - lx0) * t, lx1 + (tx1 - lx1) * t, foot + (top - foot) * t)  # noqa: E731
    for i, t in enumerate(levels[1:], 1):
        a0, a1, y = pos(t)
        timber(ic, (a0 - 4, y), (a1 + 4, y), 12, "#a46e3c", "#5e3c1e")
        b0, b1, yb = pos(levels[i - 1])
        timber(ic, (b0 + 6, yb - 4), (a1 - 6, y + 4), 10, "#945e32", "#54361a")
        timber(ic, (b1 - 6, yb - 4), (a0 + 6, y + 4), 10, "#945e32", "#54361a")
    # head: a short tail vane and the sails
    timber(ic, (cx + 6, hub_y + 6), (cx + 120, hub_y + 16), 12, "#8e5e32", "#4e3218")
    ic.poly([(cx + 92, hub_y - 26), (cx + 132, hub_y - 20), (cx + 132, hub_y + 42), (cx + 92, hub_y + 30)], "#c8b89c",
            "#8a7a62", edge=4)
    hub = (cx - 8, hub_y)
    for k, a in enumerate((24, 114, 204, 294)):
        r = math.radians(a)
        ux, uy = math.cos(r), math.sin(r)
        px, py = -uy, ux
        L, W0, W1 = 176, 12, 56
        sail = [(hub[0] + ux * 40 + px * W0, hub[1] + uy * 40 + py * W0), (hub[0] + ux * L + px * W0, hub[1] + uy * L + py * W0),
                (hub[0] + ux * L + px * W1, hub[1] + uy * L + py * W1), (hub[0] + ux * 40 + px * W1, hub[1] + uy * 40 + py * W1)]
        ic.poly(sail, "#dccfb6" if k % 2 == 0 else "#bcae94", "#8e806a", edge=4)
        for f in (0.42, 0.62, 0.82):
            ic.line([(hub[0] + ux * L * f + px * W0, hub[1] + uy * L * f + py * W0),
                     (hub[0] + ux * L * f + px * W1, hub[1] + uy * L * f + py * W1)], 5, (70, 50, 32, 210))
        ic.line([(hub[0] + ux * 44 + px * (W0 + W1) / 2, hub[1] + uy * 44 + py * (W0 + W1) / 2),
                 (hub[0] + ux * (L - 4) + px * (W0 + W1) / 2, hub[1] + uy * (L - 4) + py * (W0 + W1) / 2)], 4,
                (70, 50, 32, 180))
        timber(ic, hub, (hub[0] + ux * (L + 10), hub[1] + uy * (L + 10)), 16, "#a06a38", "#58381c")
    ic.ellipse((hub[0] - 20, hub[1] - 20, hub[0] + 20, hub[1] + 20), "#7a706a", "#2e2826", edge=4)


def tower(ic: Icon, x0: float, x1: float, top: float, foot: float) -> None:
    """Graduation tower seen along its length: brushwood wall between irregular timber posts, a brine
    trough, a pitched board roof with an overhang, braces at the end, a brine basin at its foot."""
    brushwood(ic, (x0 + 10, top + 40, x1 - 10, foot - 30))
    # posts and rails in front of the brushwood, spacing slightly irregular
    fr = [0.0, 0.19, 0.37, 0.6, 0.79, 1.0]
    for f in fr:
        x = x0 + 14 + (x1 - x0 - 28) * f
        timber(ic, (x, top + 20), (x + ic.random.uniform(-3, 3), foot), 18, "#a0683a", "#5a3a1e")
    timber(ic, (x0, foot - 150), (x1, foot - 146), 14, "#94603a", "#56361c")  # low rail
    # brace at the right end
    timber(ic, (x1 - 14, foot - 10), (x1 + 50, foot), 18, "#9a6436", "#583818")
    timber(ic, (x1 - 14, top + 120), (x1 + 48, foot - 4), 18, "#a46c3a", "#5e3c20")
    # trough under the eave
    timber(ic, (x0 - 10, top + 30), (x1 + 10, top + 30), 26, "#a0683a", "#5a3a1e")
    ic.shade(ic.mask("rectangle", (x0, top + 44, x1, top + 76)), alpha=0.4, blur=10)
    # pitched roof plane with overhang and a slightly sagging ridge
    ridge = [(x0 + 18, top - 58), ((x0 + x1) / 2, top - 52), (x1 - 18, top - 58)]
    roof = [(x0 - 50, top + 26), (x1 + 50, top + 26)] + ridge[::-1]
    shingles(ic, roof, "#a8704a", "#643e26", course=22, stagger=34, edge=6)
    ic.line(ridge, 8, (70, 44, 28, 220))
    ic.line([(x0 - 50, top + 24), (x1 + 50, top + 24)], 5, (250, 214, 170, 120))
    # brine basin at the foot (kerbed, grey-blue brine)
    bm = ic.poly_mask([(x0 - 20, foot - 26), (x1 + 20, foot - 26), (x1 + 34, foot + 28), (x0 - 34, foot + 28)])
    ic.fill(bm, "#b4a48a", "#7a6a56", (foot - 26, foot + 28), noise=0.2)
    wm = ic.poly_mask([(x0 - 6, foot - 16), (x1 + 6, foot - 16), (x1 + 16, foot + 14), (x0 - 16, foot + 14)])
    ic.fill(wm, "#a8b6b8", "#5a6c74", (foot - 16, foot + 14), noise=0.08)
    ic.shade(ic.intersect(wm, ic.mask("rectangle", (0, foot - 16, SIZE, foot - 4))), (30, 40, 34), 0.4, blur=4)
    for _ in range(10):
        x = ic.random.uniform(x0, x1 - 40)
        y = ic.random.uniform(foot - 6, foot + 8)
        ic.line([(x, y), (x + ic.random.uniform(20, 40), y)], 3, (230, 238, 238, 160))
    ic.outline([(x0 - 20, foot - 26), (x1 + 20, foot - 26), (x1 + 34, foot + 28), (x0 - 34, foot + 28)], 5)


def panhouse(ic: Icon, x0: float, x1: float, eave: float, ridge: float, foot: float) -> None:
    """Masonry panhouse: tiled roof, two stout chimneys with smoke, arched door, dark windows, a
    fire glow at the stoke hole."""
    cx = (x0 + x1) / 2
    for chx in (x0 + 110, x1 - 90):
        ic.rect((chx - 30, ridge - 90, chx + 30, eave - 40), "#a89682", "#6a5a4a", vertical=False, edge=4)
        ic.rect((chx - 38, ridge - 104, chx + 38, ridge - 84), "#8e7e6c", "#5c5044", edge=4)
    ashlar(ic, (x0, eave, x1, foot), "#a88e70", "#6a5640")
    ic.rect((x0 - 6, eave - 4, x1 + 6, eave + 14), "#a8987e", "#7a6a56", edge=4)
    ic.door(cx - 44, foot - 150, cx + 44, foot, arched=True)
    for wx in (x0 + 50, x1 - 94):
        ic.window(wx, eave + 60, wx + 44, eave + 110)
    # stoke hole with fire glow
    ic.rect((x0 + 60, foot - 60, x0 + 120, foot - 6), "#2a1c14", "#140c08", edge=4)
    ic.fill(ic.mask("rectangle", (x0 + 68, foot - 40, x0 + 112, foot - 10)), "#ffc860", "#c04c18", (foot - 40, foot - 10),
            noise=0.3)
    ic.shade(ic.mask("ellipse", (x0 + 30, foot - 90, x0 + 150, foot + 20)), (255, 150, 60), 0.3, blur=16)
    shingles(ic, [(x0 - 40, eave + 6), (x1 + 40, eave + 6), (x1 - 30, ridge), (x0 + 30, ridge)], "#b06a4a", "#6c3a26",
             course=28, stagger=36)
    ic.shade(ic.mask("rectangle", (x0, eave + 14, x1, eave + 60)), alpha=0.5, blur=12)
    for chx in (x0 + 110, x1 - 90):  # chimney stacks above the roof
        ic.rect((chx - 30, ridge - 90, chx + 30, ridge + 40), "#b09e88", "#6e5e4e", vertical=False, edge=4)
        ic.rect((chx - 38, ridge - 104, chx + 38, ridge - 84), "#8e7e6c", "#5c5044", edge=4)
        ic.shade(ic.mask("rectangle", (chx + 6, ridge - 84, chx + 30, ridge + 40)), alpha=0.3, blur=4)
    smoke(ic, [(x0 + 170, ridge - 250, 50), (x0 + 130, ridge - 196, 46), (x0 + 110, ridge - 140, 38)])
    smoke(ic, [(x1 - 40, ridge - 236, 44), (x1 - 70, ridge - 184, 42), (x1 - 88, ridge - 136, 34)])


def flume(ic: Icon, p0, p1, legs) -> None:
    """Wooden brine flume on a trestle from the tower head down to a spout in the panhouse wall."""
    y_at = lambda x: p0[1] + (p1[1] - p0[1]) * (x - p0[0]) / (p1[0] - p0[0])  # noqa: E731
    for x, y in legs:
        timber(ic, (x - 30, y), (x, y_at(x) + 20), 16, "#8a5a32", "#4e3218")
        timber(ic, (x + 30, y), (x, y_at(x) + 20), 16, "#8a5a32", "#4e3218")
    # spout collar in the panhouse wall where the flume enters
    ex, ey = p1
    ic.rect((ex - 14, ey - 34, ex + 30, ey + 24), "#bcae96", "#7e6e5a", edge=4)
    ic.rect((ex - 4, ey - 24, ex + 20, ey + 12), "#1e1814", "#0c0a08", edge=0)
    ic.shade(ic.poly_mask([(p0[0], p0[1] + 22), (p1[0], p1[1] + 22), (p1[0], p1[1] + 50), (p0[0], p0[1] + 50)]),
             alpha=0.35, blur=10)
    timber(ic, p0, p1, 34, "#b07a46", "#603c1e")
    # lit top edge and the brine running in the trough
    ic.line([(p0[0] + 2, p0[1] - 18), (p1[0], p1[1] - 18)], 5, (250, 214, 160, 200))
    ic.line([(p0[0] + 6, p0[1] - 12), (p1[0] - 4, p1[1] - 12)], 7, (150, 176, 184, 230))
    ic.line([(p0[0] + 6, p0[1] - 14), (p1[0] - 4, p1[1] - 14)], 2, (236, 244, 244, 200))


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.85
    ic.poly([(26, 966), (50, 860), (660, 850), (1000, 860), (1012, 966)], "#a8967a", "#6c5c46", noise=0.28)
    tower(ic, 40, 560, 470, 860)
    wind_pump(ic, 214, 262, 862)
    panhouse(ic, 680, 990, 600, 450, 900)
    flume(ic, (534, 506), (700, 634), [(624, 866)])
    # three salt loaves on a board in front of the tower basin; the door and cask stay clear
    ic.shade(ic.poly_mask([(320, 930), (620, 926), (620, 966), (320, 966)]), alpha=0.45, blur=10)
    timber(ic, (340, 938), (600, 934), 24, "#a0703e", "#5a3a1e")
    for cx, w, h, t in ((398, 124, 206, 0.0), (514, 116, 178, 0.2)):
        salt_cone(ic, cx, 924, w, h, t)
    salt_cone(ic, 458, 962, 108, 146, 0.1)
    ic.barrel(904, 856, 978, 956)
