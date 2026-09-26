"""Inland Saltworks (inland_saltworks): a timber boiling house, shallow brine pans, white salt loaves.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game     uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/inland_saltworks/draw.py     --out ../ProsperOrPerishConstructor/artifacts/icons/inland_saltworks

Identity: salt won from brine, not rock. A plank boiling house with a steep board roof and a smoking
louvre; its open middle bay shows the shallow iron pan over the fire, steam rising. In front a row of
clay-rimmed evaporation pans with white crust, on the right conical salt loaves drying on a board and a
salt rake. The Engineered Brine Saltworks adds a graduation tower, a flume and a masonry panhouse.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("salt_collector", "mercury_patio", "charcoal_maker", "polders")

ROCK, ROCK_DK = "#8e6c4c", "#3a281a"  # marl and clay overburden around the salt body
SALT_TOP = ("#fbf8f0", "#e4dccd")
SALT_FRONT = ("#efe8dc", "#b5a896")
SALT_SIDE = ("#ad9e8c", "#7c6e60")
WOOD, WOOD_DK = "#8a623e", "#4e3522"
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
            td.polygon(q, fill=(20, 10, 6, int(-t * 95)) if t < 0 else (255, 236, 210, int(t * 60)))
            if rnd(0, 1) < 0.12:  # an odd weathered, silvery board
                td.polygon(q, fill=(170, 166, 150, 70))
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


def pan_bed(ic: Icon, x0: float, x1: float, y0: float, y1: float, n: int, crust=(0.0, 0.6, 0.3)) -> None:
    """Row of shallow clay-rimmed evaporation pans seen from the raised camera: brine that shows
    the sky and white crust at the edges, crystallised patches where it is nearly dry."""
    w = (x1 - x0) / n
    bed = [(x0 - 10, y0 - 8), (x1 + 10, y0 - 8), (x1 + 24, y1 + 10), (x0 - 24, y1 + 10)]
    ic.poly(bed, "#b08a5e", "#6e4c30", noise=0.22)
    # bevel of the clay bank: lit top edge, shadowed front lip
    ic.line([bed[0], bed[1]], 6, (250, 214, 160, 150))
    ic.line([bed[3], bed[2]], 8, (50, 30, 16, 170))
    R = ic.random
    for i in range(n):
        a = x0 + i * w
        sk = lambda x, y: (x + (x - (x0 + x1) / 2) * (y - y0) / (y1 - y0) * 0.06, y)  # noqa: E731
        q = [sk(a + 14, y0 + 7), sk(a + w - 14, y0 + 7), sk(a + w - 14, y1 - 5), sk(a + 14, y1 - 5)]
        m = ic.poly_mask(q)
        # grey-blue brine, lighter towards the far edge, with a soft sky sheen
        ic.fill(m, "#aab4b4", "#627078", (y0, y1), noise=0.07, chroma=0.03)
        tint(ic, ic.poly_mask([(a + w * 0.2, y0 + 8), (a + w * 0.55, y0 + 8), (a + w * 0.4, y1 - 6), (a + w * 0.12, y1 - 6)]),
             m, (226, 232, 230), 0.3, 10)
        # clay rim bevel: shadow cast by the far bank, light on the near bank's inner slope
        ic.shade(ic.intersect(m, ic.mask("rectangle", (0, y0, SIZE, y0 + 20))), (46, 34, 26), 0.5, blur=4)
        tint(ic, ic.poly_mask([(q[0][0], q[0][1]), (q[0][0] + 12, q[0][1]), (q[3][0] + 12, q[3][1]), (q[3][0], q[3][1])]),
             m, (46, 34, 26), 0.35, 3)
        c = crust[i % len(crust)]
        # white crust along the pan edges (thicker where drier) and a few thin drifts
        lay, d = layer()
        cw = int(8 + 16 * c)
        d.line([q[3], q[2], q[1]], fill=(246, 244, 238, 235), width=cw, joint="curve")
        d.line([q[0], q[3]], fill=(246, 244, 238, 200), width=cw // 2 + 4)
        for _ in range(int(1 + 3 * c)):
            x, y = R.uniform(a + 24, a + w - 90), R.uniform(y0 + 18, y1 - 14)
            L = R.uniform(40, 90)
            d.line([(x, y), (x + L * 0.5, y + R.uniform(-3, 3)), (x + L, y + R.uniform(-4, 4))],
                   fill=(248, 247, 242, 170), width=int(R.uniform(6, 10)), joint="curve")
        composite(ic, lay.filter(ImageFilter.GaussianBlur(2.5)), m)
        ic.outline(q, 4, (60, 40, 24, 200))
        ic.line([(q[3][0], q[3][1] + 8), (q[2][0], q[2][1] + 8)], 4, (250, 216, 160, 150))  # lit near lip of the rim


def rake(ic: Icon, p0, p1) -> None:
    """Long wooden salt rake with a board head."""
    timber(ic, p0, p1, 20, "#b8844e", "#6a4424")
    x, y = p1
    timber(ic, (x - 40, y + 4), (x + 40, y - 4), 22, "#a0703e", "#5a3a1e")


def log_end(ic: Icon, cx: float, cy: float, r: float) -> None:
    """Sawn log end: pale wood with growth rings, dark bark rim, lit upper left."""
    ic.ellipse((cx - r, cy - r, cx + r, cy + r), "#4a3020", "#2a1a10", edge=0)
    ic.fill(ic.mask("ellipse", (cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5)), "#d8aa6e", "#94622e",
            radial=(cx - r * 0.4, cy - r * 0.4, r * 1.8), noise=0.2)
    ic.overlay(lambda d: d.ellipse((cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5), outline=(120, 80, 40, 150),
                                   width=3))
    ic.overlay(lambda d: d.ellipse((cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1), outline=(28, 18, 10, 200), width=4))


def woodshed(ic: Icon, x0: float, x1: float, top: float, low: float, foot: float) -> None:
    """Lean-to firewood store against the left gable: board pent roof, two posts, stacked logs."""
    ic.rect((x0, top + 10, x1, foot), "#3a2a1c", "#1c140c", edge=0)
    R = ic.random
    r = 17
    y = foot - r
    row = 0
    while y > low + 30:
        x = x0 + r + 4 + (row % 2) * r
        while x < x1 - r:
            log_end(ic, x + R.uniform(-2, 2), y + R.uniform(-2, 2), r * R.uniform(0.85, 1.05))
            x += 2 * r
        y -= 2 * r - 4
        row += 1
    ic.shade(ic.mask("rectangle", (x0, low, x1, low + 50)), alpha=0.5, blur=10)
    timber(ic, (x0 + 10, foot + 4), (x0 + 10, low + 4), 20)
    shingles(ic, [(x0 - 20, low + 8), (x1 + 4, top - 2), (x1 + 4, top - 26), (x0 - 20, low - 22)], "#9a6e46", "#5e3e24",
             course=26, stagger=30, edge=6)


def plank_door(ic: Icon, x0: float, y0: float, x1: float, y1: float) -> None:
    """Ledged plank door with iron strap hinges, in its frame."""
    ic.rect((x0 - 10, y0 - 10, x1 + 10, y1), "#7a5030", "#44301c", edge=4)
    planks(ic, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "#8a5c34", "#4c3018", board=20)
    for yy in (y0 + 30, y1 - 40):
        ic.line([(x0 + 4, yy), (x1 - 12, yy)], 8, (54, 50, 50))
        ic.line([(x0 + 4, yy - 3), (x1 - 12, yy - 3)], 2, (150, 146, 140, 150))
    ic.ellipse((x1 - 22, (y0 + y1) / 2 - 6, x1 - 10, (y0 + y1) / 2 + 6), "#6a6666", "#2e2c2c", edge=2)
    ic.shade(ic.mask("rectangle", (x0, y0, x1, y0 + 30)), alpha=0.35, blur=8)


# ---- parts -------------------------------------------------------------------------------------
def boiling_house(ic: Icon) -> None:
    """Timber boiling house with a steep board roof and a steam louvre; the open middle bay shows
    the shallow iron pan over its fire."""
    x0, x1, eave, ridge, foot = 110, 620, 590, 412, 790
    # louvre on the ridge, off centre (behind the roof plane)
    lx = 444
    planks(ic, [(lx - 62, ridge + 30), (lx + 62, ridge + 30), (lx + 62, ridge - 56), (lx - 62, ridge - 56)],
           "#6e5036", "#3e2a1a", board=16)
    for x in (lx - 36, lx, lx + 36):
        ic.rect((x - 10, ridge - 40, x + 10, ridge + 4), "#1e1712", "#120d0a", edge=0)
    shingles(ic, [(lx - 92, ridge - 46), (lx + 92, ridge - 46), (lx + 58, ridge - 100), (lx - 58, ridge - 100)],
             "#8e6444", "#5a3c26", course=22, stagger=30, edge=6)
    # walls: planked end bays, open middle bay
    wall = [(x0, eave), (x1, eave), (x1, foot), (x0, foot)]
    planks(ic, wall, "#a2703f", "#5e3c20", board=26)
    bay0, bay1 = 240, 490
    # dark interior of the open bay
    ic.poly([(bay0, eave + 20), (bay1, eave + 20), (bay1, foot), (bay0, foot)], "#1e1812", "#0a0706", edge=0, noise=0.08)
    # low stone hearth cheeks and the fire glow under the pan, with ember specks
    for hx in (bay0 + 18, bay1 - 58):
        ic.rect((hx, 742, hx + 40, foot), "#6e6258", "#3a322c", edge=4)
    ic.shade(ic.mask("ellipse", (bay0 + 40, 726, bay1 - 40, 812)), (255, 110, 30), 0.55, blur=16)
    fire = ic.mask("ellipse", (bay0 + 70, 752, bay1 - 70, 800))
    ic.fill(fire, "#f08a34", "#8e2a10", radial=(365, 790, 110), noise=0.3)
    R = ic.random
    lay, d = layer()
    for _ in range(9):
        x, y = R.uniform(bay0 + 80, bay1 - 80), R.uniform(768, 796)
        r = R.uniform(2, 3.5)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, R.randint(190, 230), 110, 230))
    composite(ic, lay)
    # the pan: wide, flat iron trough in slight perspective, dark rim, lighter grey brine
    pan_top = [(bay0 + 22, 700), (bay1 - 22, 700), (bay1 + 2, 724), (bay0 - 2, 724)]
    ic.poly([(bay0 - 2, 724), (bay1 + 2, 724), (bay1 - 2, 748), (bay0 + 2, 748)], "#46403c", "#1c1816", noise=0.1, edge=4)
    ic.shade(ic.mask("rectangle", (bay0 + 2, 736, bay1 - 2, 750)), (255, 120, 40), 0.35, blur=4)  # fire on its belly
    ic.poly(pan_top, "#2e2a28", "#1a1716", noise=0.08, edge=0)
    brine = [(bay0 + 34, 704), (bay1 - 34, 704), (bay1 - 12, 720), (bay0 + 12, 720)]
    ic.poly(brine, "#b6b8b4", "#8a8e8c", noise=0.08, edge=0)
    ic.line([brine[0], brine[1]], 3, (240, 240, 236, 170))
    ic.line([(bay0 - 2, 724), (bay1 + 2, 724)], 4, (150, 140, 130, 200))  # lit front rim
    ic.outline(pan_top, 5, (16, 12, 10, 230))
    # frame: posts, sill, wall plate, one brace (the right bay has the door)
    for x in (x0 + 8, bay0, bay1, x1 - 8):
        timber(ic, (x, eave + 6), (x, foot + 4), 28)
    timber(ic, (x0 - 6, eave + 16), (x1 + 6, eave + 16), 30, "#a46c3a", "#5e3c20")
    timber(ic, (x0 + 14, eave + 110), (bay0 - 10, eave + 30), 16)
    ic.window(150, 670, 194, 714)
    plank_door(ic, 516, 646, 594, foot)
    # front roof plane with a deep shadow under the eave, per-board tone, grime streaks and moss
    roof = shingles(ic, [(x0 - 60, eave + 10), (x1 + 60, eave + 10), (x1 - 30, ridge), (x0 + 30, ridge)], "#a8784c",
                    "#664226", course=30, stagger=40)
    for _ in range(9):
        sx = R.uniform(x0 - 30, x1 + 30)
        tint(ic, ic.mask("rectangle", (sx, ridge + R.uniform(20, 90), sx + R.uniform(8, 18), eave)), roof,
             (40, 26, 16), 0.22, 4)
    for cx_, cy_, rx, ry in ((120, 570, 70, 22), (230, 590, 60, 14), (560, 560, 50, 26), (650, 590, 44, 14),
                             (500, 440, 34, 14), (190, 470, 30, 12)):
        blob = ic.poly_mask(ic.jitter(cx_, cy_, rx, ry, 9, 0.35))
        tint(ic, blob, roof, (92, 112, 46), 0.55, 5)
        tint(ic, ic.poly_mask(ic.jitter(cx_ - rx * 0.2, cy_ - ry * 0.3, rx * 0.5, ry * 0.4, 7, 0.3)), roof,
             (150, 168, 80), 0.35, 3)
    ic.shade(ic.mask("rectangle", (x0, eave + 22, x1, eave + 70)), alpha=0.5, blur=12)
    ic.shade(ic.mask("rectangle", (x0, foot - 40, x1, foot + 4)), (30, 26, 18), 0.3, blur=10)
    # white steam rising off the pan and rolling out of the top of the bay under the eave
    lay = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(lay)
    for pts, w in (([(300, 704), (290, 672), (318, 640)], 44), ([(400, 704), (416, 668), (392, 636)], 48), ([(350, 700), (340, 670), (356, 646)], 30),
                   ([(456, 700), (464, 676), (452, 650)], 26),
                   ([(236, 630), (300, 614), (380, 608), (470, 616), (520, 628)], 46)):
        d.line(pts, fill=255, width=w, joint="curve")
    for x, y, r in ((270, 626, 34), (340, 616, 38), (420, 618, 36), (486, 628, 30)):
        d.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8), fill=255)
    lay = ic.intersect(lay.filter(ImageFilter.GaussianBlur(14)), ic.mask("rectangle", (bay0 - 30, eave + 24, bay1 + 30, 704)))
    ic.shade(lay, (246, 244, 240), 0.64)
    # smoke and steam out of the louvre
    smoke(ic, [(lx + 70, ridge - 214, 50), (lx + 20, ridge - 166, 56), (lx - 6, ridge - 116, 44)])


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.78
    ic.grade["mute"] = 0.85
    # yard ground under everything
    ic.poly([(26, 966), (60, 790), (660, 780), (1000, 800), (1012, 966)], "#a8967a", "#6c5c46", noise=0.28)
    woodshed(ic, 12, 112, 626, 668, 792)
    boiling_house(ic)
    pan_bed(ic, 70, 700, 812, 872, 3, crust=(0.7, 0.3, 0.9))
    pan_bed(ic, 50, 720, 890, 960, 3, crust=(0.2, 0.85, 0.45))
    # drying board with salt loaves, right
    ic.shade(ic.poly_mask([(700, 890), (1010, 884), (1010, 930), (700, 930)]), alpha=0.45, blur=10)
    timber(ic, (720, 900), (1004, 894), 26, "#94704a", "#5a3e26")
    for cx, w, h, t in ((790, 138, 250, 0.0), (906, 130, 214, 0.25)):
        salt_cone(ic, cx, 884, w, h, t)
    salt_cone(ic, 860, 956, 124, 170, 0.1)
    salt_cone(ic, 970, 950, 88, 128, 0.0)
    rake(ic, (640, 640), (700, 906))
