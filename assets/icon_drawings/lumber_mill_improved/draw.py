"""Planned Saw Works (lumber_mill_improved): a long saw hall with three sash saws working side by side
over a stone race, a log landing with a jib crane and forester-marked logs, stacked plank yards.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/lumber_mill_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/lumber_mill_improved

Identity: the upgrade of the Water Sawmill. Where the sawmill has one saw and one big wheel, the
planned works has a long hall under a red tile roof whose open saw floor shows three blades in a
row, each cutting a log; the water drives two undershot wheels in the arches of the stone ground
floor. At the left a timber jib crane lifts logs off a stacked landing whose ends carry the
forester's red ordinance marks, beside a painted survey stake; at the right two tall stickered
plank stacks fill the yard. Helpers are shared with the Water Sawmill.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 41
REFS = ("lumber_mill", "sawmill", "furniture_mill", "eng_royal_forest")

W_LIGHT, W_DEEP = "#7cb6c6", "#285a6c"
WOOD, WOOD_DK = "#86603e", "#4e3522"
STONE, STONE_DK = "#a08a70", "#665646"
IRON = (40, 38, 38)


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
HX0, HX1 = 250, 800          # saw hall walls
EAVE, RIDGE = 318, 120
SILL = 566                   # saw floor sill (top of the stone ground floor)
BASE = 740                   # ground floor foot in the race
BAYS = (250, 433, 616, 800)  # posts of the three saw bays


def ground_strip(ic: Icon, x0: float, x1: float, top: float, bottom: float) -> Image.Image:
    """Trodden yard ground with a ragged top edge, clods and sawdust."""
    rnd = ic.random
    pts = [(x0, bottom)] + [(x, top + rnd.uniform(-6, 6)) for x in np.linspace(x0, x1, 10)] + [(x1, bottom)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#7a6444", "#4a3a26", (top, bottom), noise=0.3)
    for _ in range(int((x1 - x0) / 14)):
        x, y = rnd.uniform(x0, x1), rnd.uniform(top, bottom)
        col = (236, 212, 160) if rnd.random() < 0.4 else (0, 0, 0)
        tint(ic, ic.mask("ellipse", (x - 12, y - 5, x + 12, y + 5)), m, col, 0.2, 2)
    return m


def conifer(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Planted spruce painted as layered bough tiers: each tier a drooping skirt with a soft ragged hem,
    warm lit bough tips on the left, a cool shaded right side and underside, needle texture."""
    rnd = ic.random
    tiers = 6
    ic.line([(cx, base - h * 0.2), (cx + rnd.uniform(-3, 3), base)], 12, (70, 50, 34))
    for k in range(tiers):
        t = k / (tiers - 1)
        top = base - h + h * 0.8 * t * 0.9
        bot = top + h * (0.24 + 0.05 * t)
        hw = w * (0.3 + 0.7 * t) / 2
        pts = [(cx + rnd.uniform(-5, 5), top - rnd.uniform(0, 6))]
        n = 7 + k
        for j, s in enumerate(np.linspace(-1, 1, n)):
            droop = bot - (1 - abs(s)) * h * 0.035
            if j % 2:  # bough tip hanging a little lower
                droop += rnd.uniform(6, 14)
            pts.append((cx + s * hw + rnd.uniform(-7, 7), droop + rnd.uniform(-5, 5)))
        pts[1] = (pts[1][0] - rnd.uniform(0, 8), pts[1][1] - rnd.uniform(8, 20))
        pts[-1] = (pts[-1][0] + rnd.uniform(0, 8), pts[-1][1] - rnd.uniform(8, 20))
        m = ic.poly_mask(pts)
        ic.fill(m, "#64843e", "#22341c", radial=(cx - hw * 0.8, top, h * 0.5), noise=0.3, chroma=0.14)
        # warm lit tips along the hem on the left, cool shade on the right and under the tier above
        lay, d = layer()
        for s in np.linspace(-1, 0.4, 5 + k):
            bx = cx + s * hw * 0.92 + rnd.uniform(-6, 6)
            by = bot - (1 - abs(s)) * h * 0.035 - rnd.uniform(4, 16)
            rx, ry = rnd.uniform(10, 18), rnd.uniform(5, 8)
            a = int(150 * (0.4 + 0.6 * (0.4 - s) / 1.4))
            d.ellipse((bx - rx, by - ry, bx + rx, by + ry), fill=(148, 160, 84, a))
        composite(ic, lay.filter(ImageFilter.GaussianBlur(3)), m)
        tint(ic, ic.poly_mask([(cx + 6, top), (cx + hw + 14, bot + 16), (cx + hw * 0.1, bot + 16)]), m, (8, 20, 18), 0.4, 8)
        tint(ic, ic.mask("rectangle", (cx - hw, top - 4, cx + hw, top + (bot - top) * 0.3)), m, (4, 10, 6), 0.3, 6)
        lay, d = layer()
        for _ in range(int(hw * (bot - top) / 90)):
            x, y = cx + rnd.uniform(-hw, hw), rnd.uniform(top + 10, bot)
            L = rnd.uniform(6, 14)
            col = (170, 176, 98, 90) if x < cx and rnd.random() < 0.6 else (10, 22, 10, 90)
            d.line([(x, y), (x + L * (1 if x > cx else -1) * 0.7, y + L * 0.6)], fill=col, width=2)
        composite(ic, lay, m)


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.96
    band = ic.water_band(top=690, bottom=832, x0=150, x1=880, inset=30, sag=24, light=W_LIGHT, deep=W_DEEP)

    # ---- the managed stand behind the works: a planted row of spruce of one age
    for cx, h, w in ((708, 360, 190), (796, 430, 220), (884, 388, 200), (960, 300, 160)):
        conifer(ic, cx + rnd.uniform(-8, 8), 590, h, w)

    # ---- roof: red clay tiles, hoist dormer
    roof = [(206, EAVE + 6), (846, EAVE + 6), (770, RIDGE), (290, RIDGE)]
    rm = shingles(ic, roof, "#b06a4a", "#5e3222", course=26, stagger=34, edge=6)
    tint(ic, ic.poly_mask([(200, RIDGE), (430, RIDGE), (380, EAVE + 10), (200, EAVE + 10)]), rm, (255, 226, 190), 0.14, 40)
    tint(ic, ic.poly_mask([(700, RIDGE), (860, RIDGE), (860, EAVE + 10), (760, EAVE + 10)]), rm, (0, 0, 0), 0.22, 30)
    for _ in range(7):
        x, y = rnd.uniform(300, 780), rnd.uniform(RIDGE + 30, EAVE - 10)
        tint(ic, ic.mask("ellipse", (x - 50, y - 14, x + 50, y + 14)), rm, rnd.choice([(80, 84, 50), (40, 20, 10)]), 0.16, 12)
    ic.line([(290, RIDGE), (770, RIDGE)], 18, (110, 60, 42))
    ic.line([(290, RIDGE - 5), (770, RIDGE - 5)], 4, (200, 140, 110, 150))
    # hoist dormer with a gable over the left bay
    dx0, dx1, dtop = 300, 400, 196
    planks(ic, [(dx0, dtop + 40), (dx1, dtop + 40), (dx1, EAVE + 8), (dx0, EAVE + 8)], "#9a7858", "#5a4430", board=20)
    ic.fill(ic.mask("rectangle", (dx0 + 22, dtop + 70, dx1 - 22, EAVE)), "#241a12", "#100a06", noise=0.1)
    shingles(ic, [(dx0 - 22, dtop + 48), (dx0 + 50, dtop - 10), (dx0 + 50, dtop + 20), (dx0 - 4, dtop + 60)], "#b06a4a",
             "#6e3a28", course=16, stagger=20, edge=5)
    shingles(ic, [(dx1 + 22, dtop + 48), (dx1 - 50, dtop - 10), (dx1 - 50, dtop + 20), (dx1 + 4, dtop + 60)], "#8a4e36",
             "#4e2a1c", course=16, stagger=20, edge=5)
    timber(ic, (350, dtop + 6), (350, dtop + 52), 16, "#8a6442", "#4e3522")

    # ---- saw floor: three open bays, a saw and a log in each
    floor = ic.mask("rectangle", (HX0, EAVE + 6, HX1, SILL))
    ic.fill(floor, "#2c2016", "#140e0a", noise=0.12)
    ic.overlay(lambda d: [d.line([(x, EAVE + 10), (x + rnd.uniform(-3, 3), SILL)], fill=(84, 62, 42, 60), width=4)
                          for x in np.arange(HX0 + 20, HX1, 32)], floor)
    tint(ic, ic.mask("rectangle", (HX0, EAVE, HX1, EAVE + 80)), floor, (0, 0, 0), 0.55, 14)
    LR = 32
    for i in range(3):
        b0, b1 = BAYS[i], BAYS[i + 1]
        sx = b0 + 64 + rnd.uniform(-6, 6)
        ly = SILL - 70 - i * 4
        log(ic, sx + 14, b1 - 14, ly, LR, bark=("#6a4e34", "#241810"), cut=None)
        ic.fill(ic.mask("rectangle", (b0 + 18, ly - LR + 4, sx - 16, ly + LR)), "#c49a68", "#7a5634", noise=0.16)
        for yy in (ly - 10, ly + 10):
            ic.line([(b0 + 18, yy), (sx - 16, yy)], 5, (26, 16, 8, 230))
        ic.line([(b0 + 18, ly - LR + 7), (sx - 16, ly - LR + 7)], 3, (255, 236, 200, 110))
        ic.rect((sx - 18, ly - LR - 4, sx + 22, ly + LR), "#140c06", "#0a0604", noise=0.05, edge=0)
        sash_saw(ic, sx, EAVE + 30 + i * 6, SILL - 4, 104, 11)
        ic.fill(ic.poly_mask(ic.jitter(sx + 8, ly + LR + 2, 38, 11, 10, 0.22)), "#f0d8a8", "#b08c5a", noise=0.24)
    timber(ic, (HX0 - 4, SILL - 26), (HX1 + 4, SILL - 26), 16, "#7a5638", "#48301e")  # carriage rail
    for x in BAYS:
        timber(ic, (x, EAVE + 8), (x, SILL), 24, "#8e6644", "#4e3522")
    timber(ic, (HX0 - 8, EAVE + 22), (HX1 + 8, EAVE + 22), 22, "#8e6644", "#4e3522")
    for i in range(3):  # knee braces
        b0, b1 = BAYS[i], BAYS[i + 1]
        timber(ic, (b0 + 10, EAVE + 70), (b0 + 50, EAVE + 30), 12, "#7c5838", "#4a321f")
        timber(ic, (b1 - 10, EAVE + 70), (b1 - 50, EAVE + 30), 12, "#7c5838", "#4a321f")

    # ---- stone ground floor over the race, two undershot wheels in the arches
    gm = ashlar(ic, (HX0 - 8, SILL, HX1 + 8, BASE), "#aa9478", "#6a5a48")
    ic.rect((HX0 - 18, SILL - 8, HX1 + 18, SILL + 14), "#7a5838", "#48301e", edge=4)
    tint(ic, ic.mask("rectangle", (HX0, SILL + 14, HX1, SILL + 50)), gm, (0, 0, 0), 0.35, 10)
    for ax0, ax1 in ((300, 480), (570, 750)):
        mx = (ax0 + ax1) / 2
        arch = union(ic.mask("ellipse", (ax0, 606, ax1, 740)), ic.mask("rectangle", (ax0, 673, ax1, BASE)))
        ic.fill(arch, "#221c16", "#100c0a", noise=0.06)
        with ic.clipped(arch):
            wheel(ic, mx, 736, 96, spokes=6, paddles=14, depth=(14, -8))
            tint(ic, ic.mask("rectangle", (ax0, 600, ax1, 680)), arch, (0, 0, 0), 0.45, 16)
        for a in range(186, 360, 20):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            ic.line([(mx + (ax1 - ax0) / 2 * ca, 673 + 67 * sa), (mx + ((ax1 - ax0) / 2 + 26) * ca, 673 + 88 * sa)], 4,
                    (50, 40, 30, 150))
    ic.shade(ic.mask("rectangle", (HX1 - 90, SILL, HX1 + 8, BASE)), alpha=0.25, blur=20)
    ic.waterline(ic.mask("rectangle", (0, 700, SIZE, SIZE)), 712)
    tint(ic, ic.mask("rectangle", (150, 706, 880, 760)), band, (6, 22, 30), 0.55, 18)
    for ax0, ax1 in ((300, 480), (570, 750)):
        tint(ic, ic.mask("ellipse", (ax0 - 10, 690, ax1 + 10, 790)), band, (4, 14, 20), 0.45, 20)
    lay, d = layer()
    for x in (390, 660):
        for _ in range(16):
            y = rnd.uniform(718, 790)
            spread = 40 + (y - 718) * 1.2
            x0 = x + rnd.uniform(-spread, spread)
            L = rnd.uniform(20, 56)
            d.line([(x0, y), (x0 + L, y + rnd.uniform(-2, 2))], fill=(236, 246, 248, int(rnd.uniform(110, 200))),
                   width=int(rnd.uniform(3, 5)))
    composite(ic, lay, band)
    ic.line([(300, 714), (480, 714)], 4, (230, 244, 246, 170))
    ic.line([(570, 714), (750, 714)], 4, (230, 244, 246, 170))

    # ---- timber yard on the right: two stickered plank stacks
    ground_strip(ic, 770, 1012, 736, 830)
    ic.shade(ic.mask("rectangle", (780, 690, 1012, 760)), alpha=0.35, blur=16)
    board_stack(ic, 836, 1008, 742, 5, t=18, gap=11, top_depth=24, wood=("#d0aa78", "#94704a"))
    tint(ic, ic.mask("rectangle", (836, 540, 1010, 742)), None, (0, 0, 0), 0.18, 10)
    ic.shade(ic.mask("rectangle", (760, 776, 990, 824)), alpha=0.35, blur=10)
    board_stack(ic, 770, 952, 812, 3, t=18, gap=11, top_depth=24, wood=("#ecd0a0", "#b48c5c"))

    # ---- log landing on the left: stacked marked logs under a jib crane
    ground_strip(ic, 8, 330, 752, 830)
    ic.shade(ic.mask("rectangle", (20, 770, 330, 820)), alpha=0.4, blur=10)
    # crane: mast, jib, rope, a log in the sling
    timber(ic, (208, 770), (208, 280), 28, "#8a6442", "#4a3220")
    timber(ic, (208, 300), (112, 266), 22, "#8a6442", "#4a3220")
    timber(ic, (208, 440), (150, 290), 14, "#7c5838", "#4a321f")
    ic.ellipse((196, 420, 236, 460), "#6a5a4c", "#2e2620", edge=4)  # windlass drum
    ic.line([(126, 276), (126, 530)], 5, (150, 126, 88))
    ic.line([(126, 530), (80, 560)], 4, (150, 126, 88))
    ic.line([(126, 530), (172, 560)], 4, (150, 126, 88))
    mark = (150, 36, 24)
    R0 = 44
    rows = ((4, 776), (3, 704), (2, 632))
    for n, y in rows:
        w = n * R0 * 1.9
        for k in range(n):
            cx = 170 - w / 2 + R0 * 0.95 + k * R0 * 1.9 + rnd.uniform(-4, 4)
            log_end(ic, cx, y + rnd.uniform(-3, 3), R0 * rnd.uniform(0.92, 1.04), mark if rnd.random() < 0.55 else None,
                    wood=("#c49c6a", "#7a5232"))
    ic.shade(ic.mask("ellipse", (60, 590, 200, 616)), alpha=0.35, blur=8)
    log(ic, 70, 186, 576, 25, bark=("#7a5a3c", "#2a1c12"), cut="right")
    # survey stake with a painted head
    timber(ic, (318, 820), (322, 690), 12, "#b09070", "#6a5238")
    ic.rect((312, 690, 330, 716), "#c05038", "#7a2a1c", edge=3)
