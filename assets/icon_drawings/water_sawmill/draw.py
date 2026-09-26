"""Water Sawmill (water_sawmill): a board-clad mill house on a stone undercroft in its log pond, an
overshot wheel fed by a wooden flume, a sash saw cutting a log in the open saw floor.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/water_sawmill/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/water_sawmill

Identity: the big overshot waterwheel on the left with water pouring onto it from a flume on a
trestle, the enclosed mill house with a hipped shingle roof, and through its open saw floor a
vertical sash saw with a log on the carriage running out onto the log ramp; logs float in the pond
in front, a stickered stack of fresh boards dries on the landing stage at the right. Unlike the
vanilla sawmill (open gabled frame, wheel on the right) the house is closed and the wheel is fed
from above.

Timber family helpers (shared with Planned Saw Works and Managed Forest Village): ``log`` (log
lying across the picture, bark and sawn end), ``log_end`` (cut end seen head-on, rings),
``board_stack`` (stickered drying stack), ``sash_saw`` (saw frame with toothed blade), ``wheel``
(waterwheel with depth), plus ``planks``/``timber``/``ashlar`` from the Canal Lock Works and
``shingles``/``tint`` from the Tavern.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 31
REFS = ("sawmill", "lumber_mill", "windmill", "forest_village")

W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
WOOD, WOOD_DK = "#86603e", "#4e3522"
STONE, STONE_DK = "#a08a70", "#665646"
IRON = (40, 38, 38)

BAND_TOP, BAND_BOT = 690, 826


# ---- helpers (canal lock works / tavern) -------------------------------------------------------
def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    lay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return lay, ImageDraw.Draw(lay)


def composite(ic: Icon, lay: Image.Image, mask: Image.Image | None = None) -> None:
    if mask is not None:
        clip = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        clip.paste(lay, (0, 0), mask)
        lay = clip
    ic.image.alpha_composite(lay)


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def ashlar(ic: Icon, box, base=STONE, dark=STONE_DK, course=(36, 52), width=(70, 150), moss=True) -> Image.Image:
    """Weathered ashlar face: per-block tint, soft bevels, grime streaks, damp mossy foot."""
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
                d.line([(bx0 + 4, y + 4), (bx0 + 4, yb - 5)], fill=(255, 246, 228, 40), width=3)
                d.line([(bx0 + 3, yb - 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 120), width=4)
                d.line([(bx1 - 2, y + 2), (bx1 - 2, yb - 2)], fill=(30, 22, 15, 95), width=4)
            x = xb
        y = yb
    composite(ic, lay, m)
    for _ in range(int((x1 - x0) / 55)):
        sx = R.uniform(x0, x1)
        ln = R.uniform(0.25, 0.7) * (y1 - y0)
        ic.shade(ic.intersect(m, ic.mask("rectangle", (sx - R.uniform(5, 14), y0, sx + R.uniform(5, 14), y0 + ln))),
                 (35, 30, 22), R.uniform(0.10, 0.2), blur=6)
    ic.shade(ic.intersect(m, ic.mask("rectangle", (x0, y1 - 90, x1, y1 + 40))), (22, 30, 20), 0.42, blur=22)
    if moss:
        for _ in range(int((x1 - x0) / 40)):
            mx = R.uniform(x0, x1)
            my = y1 - R.uniform(10, 70)
            blob = ic.intersect(m, ic.poly_mask(ic.jitter(mx, my, R.uniform(14, 30), R.uniform(8, 16), 8, 0.3)))
            ic.shade(blob, (86, 104, 48), R.uniform(0.25, 0.45), blur=4)
    return m


def planks(ic: Icon, pts, c1=WOOD, c2=WOOD_DK, board: float = 26, vertical_boards: bool = True) -> Image.Image:
    """Board panel: per-board tone, a few grain strokes, soft joints; returns the mask."""
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
            for _ in range(2):
                gx = v + R.uniform(4, w - 4)
                d.line([(gx, min(ys)), (gx + R.uniform(-4, 4), max(ys))], fill=(40, 24, 12, 60), width=2)
            d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        else:
            d.rectangle((min(xs), v, max(xs), v + w), fill=col)
            gy = v + R.uniform(4, w - 4)
            d.line([(min(xs), gy), (max(xs), gy + R.uniform(-3, 3))], fill=(40, 24, 12, 60), width=2)
            d.line([(min(xs), v), (max(xs), v)], fill=(35, 22, 12, 130), width=3)
        v += w
    composite(ic, lay, m)
    return m


def timber(ic: Icon, p0, p1, width: float, c1=WOOD, c2=WOOD_DK) -> None:
    """Squared beam: lit upper half, darker lower half, grain along it."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.32)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping shingles: per-shingle tone, lit lower lip, course shadow."""
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


# ---- timber family helpers ---------------------------------------------------------------------
def log(ic: Icon, x0: float, x1: float, y: float, r: float, bark=("#86684a", "#35271a"), cut: str = "right",
        wood=("#e2c496", "#9a7046")) -> Image.Image:
    """Log lying across the picture: bark cylinder lit on top with furrows along it, rounded far end,
    pale sawn end with rings on the ``cut`` side. Returns the log mask."""
    ex = r * 0.42
    body = ic.mask("rectangle", (x0, y - r, x1, y + r))
    far = (x0 - ex, y - r, x0 + ex, y + r) if cut == "right" else (x1 - ex, y - r, x1 + ex, y + r)
    m = union(body, ic.mask("ellipse", far))
    ic.fill(m, bark[0], bark[1], (y - r * 0.9, y + r), noise=0.28, chroma=0.12)
    tint(ic, ic.mask("rectangle", (x0 - ex, y - r * 0.8, x1 + ex, y - r * 0.3)), m, (255, 236, 200), 0.2, r * 0.18)
    tint(ic, ic.mask("rectangle", (x0 - ex, y + r * 0.25, x1 + ex, y + r * 1.2)), m, (0, 0, 0), 0.35, r * 0.25)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * r / 260)):
        yy = y + R.uniform(-0.85, 0.85) * r
        xx = R.uniform(x0 - ex, x1)
        L = R.uniform(20, 70)
        a = int(R.uniform(60, 130))
        d.line([(xx, yy), (xx + L, yy + R.uniform(-2, 2))], fill=(28, 18, 10, a) if R.random() < 0.7 else (220, 196, 160, a // 2),
               width=int(R.uniform(2, 4)))
    composite(ic, lay, m)
    if cut:
        cx = x1 if cut == "right" else x0
        box = (cx - ex, y - r, cx + ex, y + r)
        ic.fill(ic.mask("ellipse", box), "#5a4230", "#2c2016", noise=0.2)
        fb = (cx - ex * 0.8, y - r * 0.86, cx + ex * 0.8, y + r * 0.86)
        fm = ic.mask("ellipse", fb)
        ic.fill(fm, wood[0], wood[1], radial=(cx - ex * 0.4, y - r * 0.6, r * 2.0), noise=0.14)
        for f in (0.62, 0.34):
            b = (cx - ex * 0.8 * f, y - r * 0.86 * f, cx + ex * 0.8 * f, y + r * 0.86 * f)
            ic.overlay(lambda d, b=b: d.ellipse(b, outline=(120, 80, 44, 110), width=3), fm)
        tint(ic, ic.mask("rectangle", (cx, y, cx + ex, y + r)), fm, (40, 22, 8), 0.3, 4)
    ic.outline([(x0, y - r), (x1, y - r)], 3, (40, 26, 16, 140))
    return m


def log_end(ic: Icon, cx: float, cy: float, r: float, mark=None, wood=("#d4b07e", "#8a5e3a")) -> None:
    """Cut log end seen head-on: bark ring, pale face lit upper left, growth rings, a check crack and
    an optional painted forester's mark."""
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), "#5e4430", "#1e140c",
            radial=(cx - r * 0.5, cy - r * 0.5, r * 2.1), noise=0.24)
    ri = r * 0.76
    fm = ic.mask("ellipse", (cx - ri, cy - ri + 1, cx + ri, cy + ri - 1))
    ic.fill(fm, wood[0], wood[1], radial=(cx - ri * 0.55, cy - ri * 0.55, ri * 2.3), noise=0.12)
    pc = (cx + ri * 0.08, cy + ri * 0.06)

    def rings(d):
        for f in (0.28, 0.52, 0.76):
            rr = ri * f
            d.ellipse((pc[0] - rr, pc[1] - rr * 0.96, pc[0] + rr, pc[1] + rr * 0.96), outline=(130, 88, 50, 110),
                      width=max(2, int(r / 14)))
        d.ellipse((pc[0] - 3, pc[1] - 3, pc[0] + 3, pc[1] + 3), fill=(90, 58, 30, 200))
        a = ic.random.uniform(0, 2 * math.pi)
        d.line([pc, (pc[0] + math.cos(a) * ri * 0.85, pc[1] + math.sin(a) * ri * 0.85)], fill=(60, 36, 18, 170),
               width=max(2, int(r / 12)))

    ic.overlay(rings, fm)
    tint(ic, ic.mask("ellipse", (cx - ri * 0.2, cy - ri * 0.1, cx + ri * 1.6, cy + ri * 1.6)), fm, (40, 20, 6), 0.3, r * 0.2)
    if mark:
        ic.overlay(lambda d: d.line([(cx - ri * 0.5, cy - ri * 0.25), (cx + ri * 0.45, cy + ri * 0.2)],
                                    fill=mark + (220,), width=max(5, int(r / 5))), fm)


def board_stack(ic: Icon, x0: float, x1: float, base: float, layers: int, t: float = 18, gap: float = 11,
                top_depth: float = 30, wood=("#dcbb88", "#a47c50"), face=("#a07448", "#6e4c2e")) -> Image.Image:
    """Stickered drying stack of sawn boards seen end-on from the raised camera: each layer a row of
    pale board ends (end grain lighter than the faces) with thin dark slits between the boards, a dark
    air gap with sticker ends between the layers, the board faces of the top layer running back."""
    R = ic.random
    h = layers * (t + gap)
    top = base - h
    m = ic.mask("rectangle", (x0, top - top_depth, x1, base))
    ic.fill(m, "#241810", "#140c08", noise=0.08)  # the dark air inside the stack
    for i in range(layers):
        yb = base - i * (t + gap)
        # sticker ends in the air gap (darker squared battens)
        for sx in np.linspace(x0 + 16, x1 - 18, max(2, int((x1 - x0) / 56))):
            sx += R.uniform(-5, 5)
            ic.rect((sx - 7, yb - gap, sx + 7, yb), "#7a5a3a", "#4a3420", noise=0.1, edge=0)
        # board ends in this layer, staggered
        yt = yb - gap - t
        x = x0 + (R.uniform(-6, 10) if i % 2 else R.uniform(-2, 4))
        while x < x1 - 14:
            w = R.uniform(30, 46)
            bx1 = min(x + w, x1 + R.uniform(-3, 5))
            f = R.uniform(0.9, 1.1)
            c1 = tuple(int(min(255, int(wood[0][j:j + 2], 16) * f)) for j in (1, 3, 5))
            c2 = tuple(int(min(255, int(wood[1][j:j + 2], 16) * f)) for j in (1, 3, 5))
            ic.rect((x, yt + R.uniform(-1, 2), bx1, yb - gap), c1, c2, noise=0.12, edge=0)
            ic.line([(x + 3, yt + 3), (bx1 - 3, yt + 3)], 3, (255, 246, 222, 110))
            x = bx1 + R.uniform(4, 7)
    # top faces of the uppermost boards, running back into the stack
    tf = [(x0 + 14, top - top_depth), (x1 - 6, top - top_depth), (x1, top), (x0, top)]
    ic.fill(ic.poly_mask(tf), face[0], face[1], (top - top_depth, top), noise=0.16)
    for x in np.linspace(x0 + 36, x1 - 24, max(2, int((x1 - x0) / 40))):
        ic.line([(x + R.uniform(-5, 5) + 8, top - top_depth + 2), (x + R.uniform(-3, 3), top)], 3, (40, 24, 12, 150))
    ic.line([(x0 + 2, top - 2), (x1 - 2, top - 2)], 3, (255, 236, 200, 90))
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.22, top, x1 + 20, base)), m, (20, 10, 4), 0.25, 14)
    return m


def float_log(ic: Icon, cx: float, cy: float, length: float, r: float, deg: float, cut: str = "right") -> None:
    """Log floating in the pond at a slight angle: rounded bark with a lit top edge and dark underside,
    pale end-grain disc(s), the lower third sunk behind a water tint and a waterline shadow."""
    a = math.radians(deg)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux  # points down for small angles
    h = length / 2

    def P(s, t):  # s along the log, t across it (in radii)
        return (cx + ux * s + nx * t * r, cy + uy * s + ny * t * r)

    def ell(s, rx, n=24):
        return [P(s + math.cos(k * 2 * math.pi / n) * rx, math.sin(k * 2 * math.pi / n)) for k in range(n)]

    def strip(t0, t1, s0=-h, s1=h):
        return [P(s0, t0), P(s1, t0), P(s1, t1), P(s0, t1)]

    ex = r * 0.4
    body = union(ic.poly_mask(strip(-1, 1)), ic.poly_mask(ell(-h if cut == "right" else h, ex)))
    # waterline shadow and ripples under it
    ic.shade(ic.poly_mask([P(-h - 10, 0.55), P(h + 10, 0.55), P(h + 22, 1.5), P(-h - 22, 1.5)]), (10, 30, 40), 0.55, blur=6)
    ic.fill(body, "#8a6a48", "#2e2014", (cy - r, cy + r), noise=0.26, chroma=0.12)
    tint(ic, ic.poly_mask(strip(-0.95, -0.45)), body, (255, 230, 186), 0.42, r * 0.15)
    tint(ic, ic.poly_mask(strip(0.2, 1.1)), body, (0, 0, 0), 0.45, r * 0.2)
    R = ic.random
    lay, d = layer()
    for _ in range(int(length * r / 300)):
        s, t = R.uniform(-h, h - 30), R.uniform(-0.8, 0.5)
        L = R.uniform(20, 60)
        d.line([P(s, t), P(s + L, t + R.uniform(-0.05, 0.05))], fill=(26, 16, 8, int(R.uniform(70, 140))), width=3)
    composite(ic, lay, body)
    # end-grain discs: the sawn end bright, the far end a smaller paler stub
    for s, big in ((h if cut == "right" else -h, True), (-h if cut == "right" else h, False)):
        rx = ex if big else ex * 0.7
        em = ic.poly_mask(ell(s, rx))
        ic.fill(em, "#5a4230", "#2a1e14", noise=0.2)
        fm = ic.poly_mask([P(s + math.cos(k * math.pi / 12) * rx * 0.78, math.sin(k * math.pi / 12) * 0.84) for k in range(24)])
        ic.fill(fm, "#ecd2a2" if big else "#c8a878", "#a07a4c", (cy - r, cy + r), noise=0.12)
        if big:
            ic.overlay(lambda d, s=s: d.polygon([P(s + math.cos(k * math.pi / 12) * rx * 0.4, math.sin(k * math.pi / 12) * 0.45)
                                                  for k in range(24)], outline=(130, 88, 50, 150)), fm)
    # lower third under water
    sub = ic.intersect(body, ic.poly_mask(strip(0.45, 1.4, -h - ex, h + ex)))
    ic.shade(sub, (60, 120, 140), 0.55, blur=2)
    lay, d = layer()
    d.line([P(-h - 12, 0.45), P(h + 12, 0.45)], fill=(22, 46, 56, 200), width=5)
    d.line([P(-h + 8, 0.62), P(-h + length * 0.45, 0.62)], fill=(226, 242, 244, 170), width=4)
    d.line([P(h - length * 0.25, 0.7), P(h + 16, 0.7)], fill=(226, 242, 244, 130), width=3)
    composite(ic, lay)


def sash_saw(ic: Icon, x: float, y0: float, y1: float, w: float = 70, bw: float = 10) -> None:
    """Reciprocating sash saw: a dark timber sash (two stiles, heavy top and bottom rails) holding a long
    bright steel blade of half-width ``bw`` with teeth facing right, towards the incoming log."""
    dk1, dk2 = "#5a3e28", "#2c1c10"
    timber(ic, (x - w * 0.5, y0), (x - w * 0.5, y1), 20, dk1, dk2)
    timber(ic, (x + w * 0.5, y0), (x + w * 0.5, y1), 20, dk1, dk2)
    top_r, bot_r = y0 + 16, y1 - 14
    # blade: tooth edge on the right, steel body, bright lit strip
    teeth = []
    for yy in np.arange(top_r + 22, bot_r - 24, 17):
        teeth += [(x + bw, yy), (x + bw + 11, yy + 5), (x + bw, yy + 15)]
    ic.overlay(lambda d: d.polygon([(x + bw, top_r + 18)] + teeth + [(x + bw, bot_r - 18)], fill=(176, 184, 188, 255)))
    ic.overlay(lambda d: d.line([(x + bw, top_r + 18)] + teeth + [(x + bw, bot_r - 18)], fill=(40, 42, 46, 200), width=2))
    blade = [(x - bw, top_r), (x + bw, top_r), (x + bw, bot_r), (x - bw, bot_r)]
    ic.fill(ic.poly_mask(blade), "#ffffff", "#aab2b6", (x - bw, x + bw), vertical=False, noise=0.05, chroma=0.02)
    ic.line([(x - bw * 0.35, top_r + 6), (x - bw * 0.35, bot_r - 6)], 4, (255, 255, 255, 220))
    ic.line([(x - bw, top_r), (x - bw, bot_r)], 3, (30, 32, 36, 200))
    # heavy dark rails above and below, iron buckles holding the blade
    for yy in (y0 + 6, y1 - 6):
        timber(ic, (x - w * 0.62, yy), (x + w * 0.62, yy), 26, dk1, dk2)
    for yy in (top_r + 10, bot_r - 10):
        ic.rect((x - bw - 7, yy - 9, x + bw + 7, yy + 9), "#4a4644", "#1e1c1a", edge=3)


def wheel(ic: Icon, cx: float, cy: float, R: float, spokes: int = 8, paddles: int = 22, depth=(20, -10)) -> Image.Image:
    """Waterwheel seen side-on with a little depth: back rim offset, buckets between the rims, front
    rim, spokes, iron-banded hub. Returns the wheel mask."""
    dx, dy = depth
    rim = R * 0.13
    ring = lambda ox, oy, r0, r1: ImageChops.subtract(  # noqa: E731
        ic.mask("ellipse", (cx + ox - r1, cy + oy - r1, cx + ox + r1, cy + oy + r1)),
        ic.mask("ellipse", (cx + ox - r0, cy + oy - r0, cx + ox + r0, cy + oy + r0)))
    # back rim and back spokes
    back = ring(dx, dy, R - rim, R)
    ic.fill(back, "#5e4430", "#2e2016", radial=(cx - R, cy - R, R * 2.6), noise=0.2)
    for k in range(spokes):
        a = 2 * math.pi * (k + 0.5) / spokes + 0.2
        ic.line([(cx + dx, cy + dy), (cx + dx + math.cos(a) * (R - rim), cy + dy + math.sin(a) * (R - rim))], 14,
                (54, 38, 26))
    # buckets bridging the rims
    for k in range(paddles):
        a = 2 * math.pi * k / paddles + 0.08
        c, s = math.cos(a), math.sin(a)
        p_in, p_out = R - rim * 1.6, R + rim * 0.7
        quad = [(cx + c * p_in, cy + s * p_in), (cx + c * p_out, cy + s * p_out),
                (cx + dx + c * p_out, cy + dy + s * p_out), (cx + dx + c * p_in, cy + dy + s * p_in)]
        lit = 0.5 + 0.5 * math.cos(a - math.radians(225))
        col1 = tuple(int(v * (0.65 + 0.5 * lit)) for v in (150, 110, 72))
        ic.poly(quad, col1, tuple(int(v * 0.55) for v in col1), edge=3)
        ic.line([(cx + c * p_out, cy + s * p_out), (cx + dx + c * p_out, cy + dy + s * p_out)], 4, (40, 26, 16, 170))
    # front rim
    front = ring(0, 0, R - rim, R)
    ic.fill(front, "#b08058", "#4e3420", radial=(cx - R * 0.7, cy - R * 0.7, R * 2.2), noise=0.22, chroma=0.1)
    ic.overlay(lambda d: d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(40, 26, 16, 170), width=4))
    ic.overlay(lambda d: d.ellipse((cx - R + rim, cy - R + rim, cx + R - rim, cy + R - rim), outline=(40, 26, 16, 150), width=4))
    ic.overlay(lambda d: d.arc((cx - R + 8, cy - R + 8, cx + R - 8, cy + R - 8), 190, 290, fill=(255, 230, 190, 90), width=5))
    # front spokes
    for k in range(spokes):
        a = 2 * math.pi * k / spokes + 0.2
        timber(ic, (cx + math.cos(a) * R * 0.14, cy + math.sin(a) * R * 0.14),
               (cx + math.cos(a) * (R - rim * 0.6), cy + math.sin(a) * (R - rim * 0.6)), 18, "#9a7050", "#553a24")
    hr = R * 0.16
    ic.fill(ic.mask("ellipse", (cx - hr, cy - hr, cx + hr, cy + hr)), "#8a6444", "#3a2818",
            radial=(cx - hr * 0.5, cy - hr * 0.5, hr * 2), noise=0.2)
    ic.overlay(lambda d: d.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), outline=IRON + (255,), width=8))
    ic.fill(ic.mask("ellipse", (cx - hr * 0.35, cy - hr * 0.35, cx + hr * 0.35, cy + hr * 0.35)), "#5a5450", "#2a2624")
    return union(ic.mask("ellipse", (cx - R - rim, cy - R - rim, cx + R + rim, cy + R + rim)),
                 ic.mask("ellipse", (cx + dx - R - rim, cy + dy - R - rim, cx + dx + R + rim, cy + dy + R + rim)))


def falling_water(ic: Icon, path, w: float) -> None:
    """Sheet of water falling along ``path``: pale body, white core streaks."""
    lay, d = layer()
    d.line(path, fill=(150, 200, 214, 235), width=int(w + 10), joint="curve")
    d.line(path, fill=(222, 240, 244, 240), width=int(w), joint="curve")
    for off in (-w * 0.25, w * 0.2):
        d.line([(x + off, y) for x, y in path[1:]], fill=(255, 255, 255, 170), width=4)
    composite(ic, lay)


def splash(ic: Icon, x: float, y: float, w: float, clip=None) -> None:
    lay, d = layer()
    for _ in range(14):
        r = ic.random.uniform(6, 13)
        sx, sy = x + ic.random.uniform(-w, w), y + ic.random.uniform(-14, 12)
        d.ellipse((sx - r * 1.6, sy - r * 0.6, sx + r * 1.6, sy + r * 0.6), fill=(240, 248, 248, 220))
    composite(ic, lay, clip)


# ---- drawing -----------------------------------------------------------------------------------
HX0, HX1 = 452, 832          # mill house walls
EAVE, RIDGE = 300, 150
SILL = 592                   # saw floor sill beam (top of the stone undercroft)
BASE = 742                   # undercroft foot in the pond
BX0 = 572                    # open saw bay
WX, WY, WR = 250, 512, 212   # wheel
FY = 250                     # flume
WALL_TOP = 452               # weathered top of the low wheel-pit wall


def pit_wall(ic: Icon) -> Image.Image:
    """Low wheel-pit wall behind the wheel: ashlar body, an uneven top of loose weathered stones with
    moss, stepping down towards the outer end so the wheel rim breaks the silhouette."""
    rnd = ic.random
    pit = ashlar(ic, (70, WALL_TOP, HX0 + 4, BASE), "#8e887c", "#524c44", course=(30, 44), width=(60, 120))
    x = 70
    while x < HX0:
        w = rnd.uniform(42, 70)
        x1 = min(x + w, HX0 + 4)
        rise = rnd.uniform(4, 16) + 26 * (x - 70) / (HX0 - 70)
        pts = ic.jitter((x + x1) / 2, WALL_TOP - rise / 2, (x1 - x) / 2, rise / 2 + 12, 8, 0.14)
        m = ic.poly_mask(pts)
        ic.fill(m, "#a09888", "#5a544a", (WALL_TOP - rise - 12, WALL_TOP + 12), noise=0.24, chroma=0.1)
        tint(ic, ic.mask("rectangle", (x, WALL_TOP - rise - 20, x1, WALL_TOP - rise + 4)), m, (255, 246, 224), 0.25, 4)
        if rnd.random() < 0.7:
            tint(ic, ic.poly_mask(ic.jitter((x + x1) / 2 + rnd.uniform(-8, 8), WALL_TOP - rise - 4,
                                             (x1 - x) * 0.4, 9, 8, 0.3)), m, (92, 112, 50), 0.6, 3)
        ic.outline(pts, 3, (40, 34, 28, 150))
        x = x1 + rnd.uniform(-2, 3)
    return pit


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.96
    band = ic.water_band(top=BAND_TOP, bottom=BAND_BOT, x0=24, x1=1000, inset=36, sag=30,
                         light=W_LIGHT, deep=W_DEEP)

    # ---- dark wheel pit seen through the spokes, low wall behind the wheel, trestle posts for the flume
    disk = ic.mask("ellipse", (WX + 12 - WR + 6, WY - 6 - WR + 6, WX + 12 + WR - 6, WY - 6 + WR - 6))
    ic.fill(disk, "#3e342a", "#16120e", radial=(WX - WR * 0.4, WY - WR * 0.6, WR * 2.0), noise=0.18)
    for x in (126, 214):
        timber(ic, (x, FY + 20), (x + 3, WALL_TOP - 10), 14, "#6e4e32", "#40291a")
    pit = pit_wall(ic)
    tint(ic, ic.mask("ellipse", (WX - WR + 40, WY - WR + 10, WX + WR + 80, WY + WR + 60)), pit, (0, 0, 0), 0.45, 30)

    # ---- mill house: roof, board-clad saw floor, stone undercroft
    roof = [(410, EAVE + 6), (872, EAVE + 6), (800, RIDGE), (482, RIDGE)]
    rm = shingles(ic, roof, "#9c7a5c", "#4a3222", course=26, stagger=32, edge=6)
    tint(ic, ic.poly_mask([(400, RIDGE), (600, RIDGE), (560, EAVE + 10), (400, EAVE + 10)]), rm, (255, 232, 190), 0.14, 40)
    tint(ic, ic.poly_mask([(720, RIDGE), (880, RIDGE), (880, EAVE + 10), (780, EAVE + 10)]), rm, (0, 0, 0), 0.2, 30)
    for _ in range(6):  # moss and weathering on the shingles
        x, y = rnd.uniform(470, 820), rnd.uniform(RIDGE + 40, EAVE - 10)
        tint(ic, ic.mask("ellipse", (x - 50, y - 16, x + 50, y + 16)), rm, (70, 84, 40), 0.18, 12)
    ic.line([(482, RIDGE), (800, RIDGE)], 16, (86, 64, 44))
    ic.line([(482, RIDGE - 4), (800, RIDGE - 4)], 4, (180, 150, 112, 150))
    # louvred vent on the ridge
    ic.rect((612, RIDGE - 40, 676, RIDGE + 4), "#7a5e42", "#4a3624", edge=4)
    for yy in (RIDGE - 28, RIDGE - 16, RIDGE - 4):
        ic.line([(616, yy), (672, yy)], 4, (40, 28, 18, 180))
    ic.poly([(600, RIDGE - 34), (644, RIDGE - 70), (688, RIDGE - 34)], "#8a6a50", "#4a3624", edge=4)

    wall = [(HX0, EAVE + 6), (HX1, EAVE + 6), (HX1, SILL), (HX0, SILL)]
    wm = planks(ic, wall, "#a08060", "#5a4430", board=30)
    bay = ic.mask("rectangle", (BX0, EAVE + 30, HX1 + 2, SILL))
    ic.fill(bay, "#261a12", "#0e0a06", noise=0.1)
    ic.overlay(lambda d: [d.line([(x, EAVE + 30), (x + rnd.uniform(-3, 3), SILL)], fill=(80, 60, 40, 40), width=4)
                          for x in np.arange(BX0 + 30, HX1, 34)], bay)
    tint(ic, ic.mask("rectangle", (BX0, EAVE, HX1, EAVE + 90)), bay, (0, 0, 0), 0.5, 14)
    for x in (HX0 + 10, BX0, HX1 - 8):
        timber(ic, (x, EAVE + 8), (x, SILL), 22, "#8a6442", "#4e3522")
    timber(ic, (HX0 - 6, EAVE + 24), (HX1 + 6, EAVE + 24), 20, "#8a6442", "#4e3522")
    timber(ic, (HX0 + 18, SILL - 14), (BX0 - 8, EAVE + 44), 14, "#7c5838", "#4a321f")
    ic.window(490, 380, 536, 446)
    tint(ic, ic.mask("rectangle", (HX0, EAVE + 6, HX1, EAVE + 64)), wm, (0, 0, 0), 0.5, 12)

    # carriage rail out of the bay onto a trestle; the log being cut and the big sash saw
    SX = 700
    LY, LR = SILL - 92, 38
    timber(ic, (BX0 + 14, LY + LR + 12), (962, LY + LR + 12), 22, "#7a5638", "#48301e")
    for x in (890, 952):
        timber(ic, (x, LY + LR + 20), (x + 4, 700), 16, "#6e4e32", "#40291a")
    log(ic, SX + 14, 962, LY, LR)
    # the sawn part left of the blade: boards split by dark kerfs, fresh wood a warm mid tone
    ic.fill(ic.mask("rectangle", (622, LY - LR + 4, SX - 18, LY + LR)), "#c49a68", "#7a5634", noise=0.16)
    for yy in (LY - 12, LY + 12):
        ic.line([(622, yy), (SX - 18, yy)], 5, (26, 16, 8, 230))
    ic.line([(622, LY - LR + 7), (SX - 18, LY - LR + 7)], 3, (255, 236, 200, 110))
    # kerf: dark slot where the blade enters the log
    ic.rect((SX - 20, LY - LR - 4, SX + 26, LY + LR), "#140c06", "#0a0604", noise=0.05, edge=0)
    ic.shade(ic.mask("ellipse", (SX - 80, EAVE + 50, SX + 90, SILL - 10)), (0, 0, 0), 0.35, blur=20)
    sash_saw(ic, SX, EAVE + 34, SILL - 2, 168, 12)
    # sawdust heap on the carriage where the log meets the blade, and dust falling from the cut
    ic.fill(ic.poly_mask(ic.jitter(SX + 8, LY + LR + 2, 46, 13, 12, 0.22)), "#f0d8a8", "#b08c5a", noise=0.24)
    lay, d = layer()
    for _ in range(26):
        sx, sy = SX + rnd.uniform(-22, 34), LY + LR - rnd.uniform(0, 30)
        d.ellipse((sx - 2.5, sy - 2.5, sx + 2.5, sy + 2.5), fill=(240, 220, 180, 200))
    composite(ic, lay)

    # stone undercroft with the tailrace arch
    ashlar(ic, (HX0 - 6, SILL, HX1 + 4, BASE))
    ic.rect((HX0 - 16, SILL - 10, HX1 + 14, SILL + 12), "#7a5838", "#48301e", edge=4)
    tint(ic, ic.mask("rectangle", (HX0, SILL + 12, HX1, SILL + 46)), None, (0, 0, 0), 0.35, 10)
    ax0, ax1 = 560, 680
    ic.fill(ic.mask("ellipse", (ax0, 626, ax1, 716)), "#1e1a16", "#100e0c", noise=0.05)
    ic.fill(ic.mask("rectangle", (ax0, 670, ax1, BASE)), "#1e1a16", "#100e0c", noise=0.05)
    mx = (ax0 + ax1) / 2
    for a in range(190, 355, 24):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        ic.line([(mx + 60 * ca, 670 + 44 * sa), (mx + 82 * ca, 670 + 62 * sa)], 4, (50, 40, 30, 150))
    lay, d = layer()
    d.polygon([(ax0 + 4, 706), (ax1 - 4, 706), (ax1 + 16, BASE + 6), (ax0 - 16, BASE + 6)], fill=(200, 226, 232, 220))
    for x in np.arange(ax0 + 10, ax1, 14):
        d.line([(x, 710), (x + (x - mx) * 0.3, BASE)], fill=(255, 255, 255, 160), width=4)
    composite(ic, lay)
    ic.shade(ic.mask("rectangle", (HX1 - 90, SILL, HX1 + 4, BASE)), alpha=0.25, blur=20)

    # ---- landing stage with the stickered board stack, raised on bearers clear of the house wall
    ic.shade(ic.mask("rectangle", (HX1, 640, 1004, 720)), alpha=0.3, blur=14)
    for x in (846, 920, 990):
        timber(ic, (x, 694), (x + 2, 772), 18, "#6a4a30", "#3a281a")
    deck = [(826, 692), (1004, 692), (1004, 714), (826, 714)]
    planks(ic, deck, "#8e6c48", "#5a4028", board=10, vertical_boards=False)
    ic.outline(deck, 4, (40, 26, 16, 170))
    for x in (868, 930, 988):  # bearers
        ic.rect((x - 12, 676, x + 12, 694), "#5a3e28", "#2e2014", edge=3)
    ic.shade(ic.mask("rectangle", (856, 684, 1004, 700)), alpha=0.4, blur=6)
    board_stack(ic, 856, 1004, 678, 3, t=18, gap=11, top_depth=26, wood=("#ecd0a0", "#b48c5c"))

    # ---- the wheel, fed from the flume on its trestle
    wmk = wheel(ic, WX, WY, WR, spokes=8, paddles=24, depth=(24, -12))
    timber(ic, (WX + 10, WY), (HX0 + 30, WY - 4), 28, "#6e5a4a", "#34281e")
    FX0 = 100
    trough = [(FX0, FY - 24), (WX + 30, FY - 20), (WX + 30, FY + 26), (FX0, FY + 28)]
    planks(ic, trough, "#94704a", "#553c24", board=14, vertical_boards=False)
    ic.fill(ic.poly_mask([(FX0 + 8, FY - 34), (WX + 24, FY - 30), (WX + 30, FY - 20), (FX0, FY - 24)]), W_LIGHT, "#4e8a9c", noise=0.08)
    ic.outline(trough, 4, (40, 26, 16, 170))
    ic.line([(FX0, FY - 24), (WX + 30, FY - 20)], 6, (170, 134, 92))
    ic.rect((FX0 - 4, FY - 26, FX0 + 14, FY + 30), "#5a3e28", "#2e2014", edge=3)  # end board of the trough
    falling_water(ic, [(WX + 28, FY - 14), (WX + 48, FY + 4), (WX + 64, FY + 30), (WX + 76, FY + 56)], 22)
    # water spilling off the buckets: broken, translucent streaks and droplets, the wood showing through
    lay, d = layer()
    for a in np.arange(-66, 64, 9):
        a += rnd.uniform(-3, 3)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        bx, by = WX + ca * (WR + 12), WY + sa * (WR + 12)
        if rnd.random() < 0.8:
            L = rnd.uniform(16, 44)
            d.line([(bx, by), (bx + rnd.uniform(2, 8), by + L)], fill=(236, 246, 250, int(rnd.uniform(90, 160))),
                   width=int(rnd.uniform(3, 6)))
        for _ in range(rnd.randint(1, 3)):
            dx, dy = bx + rnd.uniform(0, 18), by + rnd.uniform(20, 70)
            rr = rnd.uniform(2.5, 5)
            d.ellipse((dx - rr, dy - rr * 1.4, dx + rr, dy + rr * 1.4), fill=(240, 250, 252, int(rnd.uniform(110, 190))))
    composite(ic, lay)

    # ---- the pond: waterline over wheel, walls and posts; floating logs; foam
    ic.waterline(union(wmk, ic.mask("rectangle", (0, 700, SIZE, SIZE))), 718)
    ic.foam(40, 1000, 718)
    splash(ic, WX + 180, 720, 70, band)
    float_log(ic, 196, 782, 250, 27, -5, "right")
    float_log(ic, 526, 804, 230, 29, 6, "left")
    float_log(ic, 790, 776, 130, 22, -10, "right")
