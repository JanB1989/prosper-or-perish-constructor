"""Managed Forest Village (managed_forest_village): a log-built woodland cottage between coppiced
hazel stools, a cordwood stack, a hide shed and straw bee skeps.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/managed_forest_village/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/managed_forest_village

Identity: the managed wood itself. A coppice stool at the left sends up a fan of straight poles
with leafy tops (the regrowth of a worked wood, unlike the vanilla forest village's wild pines);
in the middle a round-log cottage with notched corners, a shingle roof and a stone chimney; at the
right a lean-to shed with hides stretched on a frame (hides, fur and game); in front a long stack
of cordwood between stakes and straw bee skeps on a bench (forest wax). Helpers are shared with the
Water Sawmill and Planned Saw Works.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE

SEED = 53
REFS = ("forest_village", "peasants_hunting_grounds", "charcoal_maker", "eng_royal_forest")

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


def board_stack(ic: Icon, x0: float, x1: float, base: float, layers: int, t: float = 20, gap: float = 9,
                top_depth: float = 26, wood=("#dcbb88", "#a47c50")) -> Image.Image:
    """Stickered drying stack of sawn boards seen side-on from the raised camera: layers of pale board
    edges with dark air gaps and sticker ends between them, the top boards' faces visible."""
    R = ic.random
    h = layers * (t + gap)
    top = base - h
    m = ic.mask("rectangle", (x0, top - top_depth, x1, base))
    for i in range(layers):
        yb = base - i * (t + gap)
        # air gap with sticker ends
        g = ic.mask("rectangle", (x0 + 6, yb - gap, x1 - 6, yb))
        ic.fill(g, "#2a1e14", "#1a120c", noise=0.1)
        for sx in np.linspace(x0 + 24, x1 - 30, max(2, int((x1 - x0) / 80))):
            ic.rect((sx - 7, yb - gap - 1, sx + 7, yb + 1), "#6a4e32", "#4a3420", edge=0)
        # board edges in this layer
        yt = yb - gap - t
        x = x0 + R.uniform(-20, 6)
        while x < x1 - 10:
            w = R.uniform(70, 150)
            bx1 = min(x + w, x1 + R.uniform(-14, 18))
            f = R.uniform(0.9, 1.08)
            c1 = tuple(int(min(255, int(wood[0][i:i + 2], 16) * f)) for i in (1, 3, 5))
            c2 = tuple(int(min(255, int(wood[1][i:i + 2], 16) * f)) for i in (1, 3, 5))
            ic.rect((x, yt, bx1, yb - gap), c1, c2, noise=0.14, edge=0)
            ic.line([(bx1, yt), (bx1, yb - gap)], 3, (70, 46, 24, 150))
            x = bx1 + 2
        ic.line([(x0, yt + 2), (x1, yt + 2)], 3, (255, 240, 210, 90))
    # top faces of the uppermost boards
    tf = [(x0 + 10, top - top_depth), (x1 - 4, top - top_depth), (x1, top), (x0, top)]
    ic.fill(ic.poly_mask(tf), "#e8d0a4", "#c8a676", (top - top_depth, top), noise=0.14)
    for x in np.linspace(x0 + 40, x1 - 20, max(2, int((x1 - x0) / 60))):
        ic.line([(x + R.uniform(-6, 6), top - top_depth + 2), (x + R.uniform(-4, 4), top)], 3, (120, 84, 50, 120))
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.25, top, x1 + 20, base)), m, (20, 10, 4), 0.22, 18)
    ic.outline([(x0, top - top_depth), (x1, top - top_depth), (x1, base), (x0, base)], 4, (40, 26, 14, 150))
    return m


def sash_saw(ic: Icon, x: float, y0: float, y1: float, w: float = 70, bw: float = 10) -> None:
    """Reciprocating sash saw: a timber sash (two stiles, top rail) holding a long steel blade of
    half-width ``bw`` with teeth facing left, between two guide posts."""
    timber(ic, (x - w * 0.5, y0 + 10), (x - w * 0.5, y1), 18, "#9a7050", "#553a24")
    timber(ic, (x + w * 0.5, y0 + 10), (x + w * 0.5, y1), 18, "#8a6442", "#4e3522")
    timber(ic, (x - w * 0.66, y0 + 18), (x + w * 0.66, y0 + 18), 20, "#a07854", "#5a3e26")
    blade = [(x - bw, y0 + 28), (x + bw, y0 + 28), (x + bw, y1 - 10), (x - bw, y1 - 10)]
    teeth = []
    for yy in np.arange(y0 + 32, y1 - 14, bw * 1.5):
        teeth += [(x - bw, yy), (x - bw * 1.9, yy + bw * 0.6), (x - bw, yy + bw * 1.2)]
    ic.overlay(lambda d: d.polygon([(x - bw, y0 + 28)] + teeth + [(x - bw, y1 - 10)], fill=(170, 176, 180, 255)))
    ic.fill(ic.poly_mask(blade), "#eceeee", "#8a9094", (x - bw, x + bw), vertical=False, noise=0.06, chroma=0.02)
    ic.line([(x - bw * 0.4, y0 + 32), (x - bw * 0.4, y1 - 14)], 3, (255, 255, 255, 170))
    ic.outline(blade, 3, (30, 30, 32, 180))
    for yy in (y0 + 28, y1 - 10):  # blade buckles
        ic.rect((x - bw - 6, yy - 7, x + bw + 6, yy + 7), "#5a5654", "#2e2c2a", edge=3)


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


# ---- helpers (managed forest village) ----------------------------------------------------------
def canopy(ic: Icon, cx: float, cy: float, rx: float, ry: float, light=(146, 168, 76), dark=(34, 54, 20),
           n: int | None = None) -> Image.Image:
    """Loose leafy crown built from many small irregular leaf clusters: each cluster lit on its upper
    left, clusters towards the top left of the crown warmer and lighter, a shaded underside, dark
    pockets inside and a ragged, uneven edge. Returns the mask."""
    R = ic.random
    n = n or max(10, int(rx * ry / 55))
    clusters = []
    for _ in range(n):
        a = R.uniform(0, 2 * math.pi)
        d = R.random() ** 0.7
        bx, by = cx + math.cos(a) * rx * d, cy + math.sin(a) * ry * d * (0.8 if math.sin(a) > 0 else 1.0)
        r = R.uniform(16, 30) * (1.1 - 0.3 * d)
        clusters.append((bx, by, r, ic.jitter(bx, by, r, r * 0.78, 9, 0.38)))
    m = ic.poly_mask(ic.jitter(cx, cy + ry * 0.05, rx * 0.8, ry * 0.72, 14, 0.12))  # solid core, no holes
    for *_, pts in clusters:
        m = ImageChops.lighter(m, ic.poly_mask(pts))
    ic.fill(m, "#34481e", "#141e0a", radial=(cx - rx * 0.5, cy - ry * 0.6, max(rx, ry) * 2), noise=0.3, chroma=0.14)

    def lit_of(c):
        return max(0.0, min(1.0, 0.62 - 0.32 * (c[0] - cx) / rx - 0.55 * (c[1] - cy) / ry + R.uniform(-0.15, 0.15)))

    for c in sorted(clusters, key=lambda c: c[1] + R.uniform(-20, 20)):
        bx, by, r, pts = c
        lit = lit_of(c)
        if R.random() < 0.07 and abs(bx - cx) < rx * 0.6 and abs(by - cy) < ry * 0.5:  # a dark pocket where the crown is open
            ic.fill(ic.poly_mask(pts), "#1e2a10", "#0e1608", noise=0.2)
            continue
        c1 = tuple(int(dark[i] + (light[i] - dark[i]) * lit + R.uniform(-10, 10)) for i in range(3))
        c2 = tuple(int(v * 0.5) for v in c1)
        cm = ic.poly_mask(pts)
        ic.fill(cm, c1, c2, radial=(bx - r * 0.55, by - r * 0.6, r * 1.9), noise=0.34, chroma=0.16)
        if lit > 0.55:
            tint(ic, ic.mask("ellipse", (bx - r * 0.6, by - r * 0.6, bx + r * 0.1, by - r * 0.1)), cm, (232, 236, 160), 0.3, 3)
    tint(ic, ic.mask("ellipse", (cx - rx * 1.1, cy + ry * 0.15, cx + rx * 1.1, cy + ry * 1.4)), m, (6, 14, 4), 0.42, ry * 0.25)
    return m


def coppice(ic: Icon, cx: float, base: float, spread: float, h: float, poles: int = 7) -> None:
    """Coppice stool: a low gnarled stump with a few living stems of different thickness and lean,
    grey-brown and olive bark, gathering into a loose leafy crown."""
    R = ic.random
    barks = [(80, 70, 50), (76, 76, 46), (90, 78, 58), (66, 58, 42), (84, 76, 50)]
    stems = []
    for k in range(poles):
        t = (k + R.uniform(-0.3, 0.3)) / (poles - 1) - 0.5
        bx = cx + t * spread * 0.32 + R.uniform(-6, 6)
        tx = cx + t * spread * 1.25 + R.uniform(-26, 26)
        ty = base - h * R.uniform(0.7, 1.0) * (1 - 0.2 * abs(t))
        w = R.uniform(8, 19)
        stems.append((tx, ty, w, bx, R.choice(barks), R.uniform(-40, 40)))
    mx_ = sum(p[0] for p in stems) / len(stems)
    my_ = sum(p[1] for p in stems) / len(stems)
    canopy(ic, mx_, my_ + 70, spread * 1.0, h * 0.2)
    for tx, ty, w, bx, col, bend in stems:
        p0 = (bx, base - 50)
        p1 = (bx + (tx - bx) * 0.45 + bend, base - 36 + (ty + 80 - base + 36) * 0.45)
        p2 = (tx, ty + 80)
        ic.line([p0, p1, p2], int(w + 5), (40, 32, 22, 220))
        ic.line([p0, p1, p2], int(w), col)
        ic.line([(p0[0] - w * 0.25, p0[1]), (p1[0] - w * 0.25, p1[1]), (p2[0] - w * 0.2, p2[1])], max(2, int(w * 0.28)),
                (200, 190, 150, 60))
        ic.line([(p0[0] + w * 0.28, p0[1]), (p1[0] + w * 0.28, p1[1])], max(2, int(w * 0.25)), (30, 24, 14, 90))
        if w > 13 and R.random() < 0.7:  # a side twig
            fx, fy = p1[0] + (p2[0] - p1[0]) * 0.5, p1[1] + (p2[1] - p1[1]) * 0.5
            sgn = 1 if tx > cx else -1
            ic.line([(fx, fy), (fx + sgn * R.uniform(30, 50), fy - R.uniform(30, 50))], 5, col)
    # leaf clusters over the stem tips, so the stems vanish into the crown
    for tx, ty, w, bx, col, bend in stems[::2]:
        canopy(ic, tx * 0.7 + mx_ * 0.3, ty + 96, 54, 38, n=14)
    # the gnarled stool with knobs, moss and two small cut stubs
    stool = ic.jitter(cx, base - 34, spread * 0.44, 42, 16, 0.2)
    ic.rock(stool, "#6e5a44", "#2e2216", facets=3)
    sm = ic.poly_mask(stool)
    for _ in range(6):
        kx, ky = cx + R.uniform(-spread * 0.34, spread * 0.34), base - R.uniform(34, 66)
        kr = R.uniform(8, 15)
        ic.fill(ic.mask("ellipse", (kx - kr, ky - kr * 0.8, kx + kr, ky + kr * 0.8)), "#86705a", "#3a2c1e",
                radial=(kx - kr * 0.4, ky - kr * 0.4, kr * 2), noise=0.2)
    tint(ic, ic.mask("rectangle", (cx - spread * 0.4, base - 60, cx + spread * 0.4, base - 30)), sm, (96, 124, 46), 0.4, 6)
    for k in (-1, 1):
        sx = cx + k * spread * 0.2 + R.uniform(-6, 6)
        ic.rect((sx - 9, base - 58, sx + 9, base - 32), "#6e5c46", "#3e3224", edge=3)
        ic.ellipse((sx - 10, base - 64, sx + 10, base - 52), "#b89c70", "#806440", edge=3)


def split_log(ic: Icon, cx: float, cy: float, r: float, span: float, rot: float, wood) -> None:
    """Split firewood seen end-on: a half-round (span 180) or quarter (span 90), pale split faces,
    bark along the round edge."""
    arc = [(cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r)
           for a in np.linspace(rot, rot + span, 14)]
    pts = arc + [(cx, cy)]
    m = ic.poly_mask(pts)
    ic.fill(m, wood[0], wood[1], radial=(cx - r * 0.6, cy - r * 0.6, r * 2.2), noise=0.16)
    ic.overlay(lambda d: d.line(arc, fill=(58, 42, 28, 255), width=max(5, int(r * 0.24)), joint="curve"), m)
    mid = math.radians(rot + span / 2)
    ic.line([(cx, cy), (cx + math.cos(mid) * r * 0.7, cy + math.sin(mid) * r * 0.7)], 2, (110, 74, 40, 140))
    ic.outline(pts, 3, (36, 24, 12, 180))


def log_wall(ic: Icon, x0: float, x1: float, y0: float, y1: float, r: float) -> None:
    """Round-log wall: courses laid top to bottom with dark chinking, notched corners where the log
    ends stick out on both sides."""
    y = y0 + r
    k = 0
    while y - r < y1:
        log(ic, x0, x1, y, r, bark=("#8a6a4a", "#3a2a1c"), cut=None)
        ic.line([(x0, y + r - 2), (x1, y + r - 2)], 6, (30, 20, 12, 170))
        for ex, off in ((x0, -r * 0.35), (x1, r * 0.35)):
            log_end(ic, ex + off + (4 if k % 2 else -4), y, r * 1.02, wood=("#caa272", "#7e5634"))
        y += r * 1.86
        k += 1


def skep(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Straw bee skep: coiled dome lit upper left, dark entrance at the foot."""
    ts = np.linspace(0, math.pi, 30)
    pts = [(cx - w / 2 * math.cos(t), base - h * math.sin(t) ** 0.8) for t in ts]
    m = ic.poly_mask(pts)
    ic.fill(m, "#d8b460", "#6e5020", radial=(cx - w * 0.3, base - h * 0.9, h * 1.4), noise=0.2)
    for k in range(1, 7):
        yy = base - h * k / 7
        ic.overlay(lambda d, yy=yy: d.line([(cx - w, yy), (cx + w, yy - 2)], fill=(90, 62, 20, 150), width=4), m)
        ic.overlay(lambda d, yy=yy: d.line([(cx - w, yy - 5), (cx + w, yy - 7)], fill=(255, 236, 170, 70), width=3), m)
    for k in range(1, 7, 2):
        yy = base - h * k / 7
        tint(ic, ic.mask("rectangle", (cx - w, yy - h / 14, cx + w, yy + 2)), m, (70, 44, 10), 0.22, 2)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.24, cx + w, base + 6)), m, (40, 24, 6), 0.5, 6)
    tint(ic, ic.mask("rectangle", (cx + w * 0.1, base - h, cx + w, base)), m, (30, 18, 4), 0.25, 12)
    ic.fill(ic.mask("ellipse", (cx - 12, base - 22, cx + 12, base + 2)), "#1e140a", "#100a04")
    ic.outline(pts, 4, (40, 26, 10, 170))


def hide(ic: Icon, cx: float, cy: float, w: float, h: float, color=("#b88a5c", "#5e3e22")) -> None:
    """Hide stretched in a pole frame: lobed pelt lit upper left, lacing to the poles."""
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
    for p0, p1 in (((x0, y0 - 10), (x0 + 6, y1 + 30)), ((x1, y0 - 14), (x1 - 4, y1 + 30)),
                   ((x0 - 16, y0), (x1 + 16, y0 - 6)), ((x0 - 16, y1), (x1 + 16, y1 + 4))):
        timber(ic, p0, p1, 13, "#8a6a4a", "#4a3624")
    pelt = [(cx - w * 0.36, cy - h * 0.38), (cx - w * 0.1, cy - h * 0.32), (cx, cy - h * 0.42), (cx + w * 0.1, cy - h * 0.32),
            (cx + w * 0.36, cy - h * 0.38), (cx + w * 0.3, cy - h * 0.1), (cx + w * 0.4, cy + h * 0.2),
            (cx + w * 0.26, cy + h * 0.38), (cx, cy + h * 0.3), (cx - w * 0.26, cy + h * 0.38), (cx - w * 0.4, cy + h * 0.2),
            (cx - w * 0.3, cy - h * 0.1)]
    ic.poly(pelt, color[0], color[1], edge=4)
    tint(ic, ic.mask("ellipse", (cx - w * 0.3, cy - h * 0.3, cx + w * 0.05, cy + h * 0.05)), ic.poly_mask(pelt),
         (255, 230, 190), 0.25, 14)
    for px, py in pelt[::2]:
        tx = x0 if px < cx else x1
        ic.line([(px, py), (tx, py + (6 if py > cy else -4))], 3, (60, 44, 28, 200))


# ---- drawing -----------------------------------------------------------------------------------
CX0, CX1 = 300, 700          # cottage walls
EAVE, RIDGE = 470, 260
BASE = 812


def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["mute"] = 0.9

    # ---- second coppice stool behind the cottage on the right, then the big one on the left
    coppice(ic, 812, 600, 150, 450, poles=6)

    # ---- lean-to shed on the right with furs hanging inside
    sx0, sx1 = 700, 990
    ic.fill(ic.mask("rectangle", (sx0, 540, sx1, BASE)), "#2e2218", "#140e0a", noise=0.12)
    for fx, fl in ((760, 120), (820, 150), (900, 110)):
        fur = ic.jitter(fx, 600 + fl / 2, 26, fl / 2, 10, 0.12)
        ic.poly(fur, "#6e5038", "#2a1c12", edge=3)
    tint(ic, ic.mask("rectangle", (sx0, 540, sx1, 620)), None, (0, 0, 0), 0.4, 12)
    for x in (sx0 + 14, 850, sx1 - 12):
        timber(ic, (x, 540), (x, BASE), 20, "#8a6442", "#4a3220")
    lean = [(sx0 - 10, 506), (sx1 + 24, 552), (sx1 + 24, 584), (sx0 - 10, 540)]
    shingles(ic, lean, "#8c7a64", "#4e4232", course=18, stagger=26, edge=5)
    hide(ic, 916, 700, 140, 150)

    # ---- the cottage: shingle roof, chimney, round-log walls, door and window
    ch0, ch1 = 590, 650
    ic.rect((ch0, 212, ch1, 330), "#9a8e7c", "#5e564a", vertical=False, edge=4)
    ic.rect((ch0 - 8, 200, ch1 + 8, 216), "#8a7e6c", "#5a5046", edge=4)
    roof = [(CX0 - 44, EAVE + 8), (CX1 + 40, EAVE + 8), (CX1 - 60, RIDGE), (CX0 + 60, RIDGE)]
    rm = shingles(ic, roof, "#967656", "#4a3624", course=24, stagger=30, edge=6)
    tint(ic, ic.poly_mask([(CX0 - 50, RIDGE), (CX0 + 160, RIDGE), (CX0 + 100, EAVE + 10), (CX0 - 50, EAVE + 10)]), rm,
         (255, 232, 190), 0.14, 40)
    for _ in range(8):  # moss patches on the shingles
        x, y = rnd.uniform(CX0, CX1), rnd.uniform(RIDGE + 30, EAVE - 10)
        tint(ic, ic.mask("ellipse", (x - 46, y - 14, x + 46, y + 14)), rm, (74, 96, 40), 0.3, 10)
    ic.line([(CX0 + 60, RIDGE), (CX1 - 60, RIDGE)], 16, (86, 66, 46))
    ic.line([(CX0 + 60, RIDGE - 4), (CX1 - 60, RIDGE - 4)], 4, (180, 150, 112, 150))
    ic.shade(ic.poly_mask([(ch1, RIDGE + 60), (ch1 + 50, RIDGE + 90), (ch1 + 40, RIDGE + 150), (ch1, RIDGE + 120)]),
             alpha=0.3, blur=10)
    walls = ic.mask("rectangle", (CX0 - 20, EAVE + 8, CX1 + 20, BASE))
    log_wall(ic, CX0, CX1, EAVE + 8, BASE - 10, 24)
    tint(ic, ic.mask("rectangle", (CX0 - 20, EAVE + 8, CX1 + 20, EAVE + 70)), walls, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (CX0 - 20, BASE - 70, CX1 + 20, BASE)), walls, (30, 40, 16), 0.3, 16)
    ic.door(446, 610, 526, BASE - 4, arched=False, surround=None)
    ic.rect((436, 596, 536, 614), "#6e4e32", "#42301e", edge=4)
    ic.window(344, 590, 394, 640)
    ic.rect((330, 646, 408, 660), "#6e4e32", "#42301e", edge=3)
    # antlers over the door
    for sgn in (-1, 1):
        ic.line([(486, 572), (486 + sgn * 30, 546), (486 + sgn * 44, 516)], 7, (214, 196, 160))
        ic.line([(486 + sgn * 26, 550), (486 + sgn * 12, 522)], 6, (214, 196, 160))
    ic.fill(ic.mask("ellipse", (474, 562, 498, 584)), "#6a5038", "#3a2a1c")

    # ---- coppice at the left, in front of the cottage's corner
    coppice(ic, 150, 812, 176, 650, poles=7)

    # ---- ground: uneven strip with a worn path, grass tufts, leaf litter and moss; contact shadows
    top = [(x, 800 + rnd.uniform(-8, 8)) for x in np.linspace(20, 1004, 14)]
    bot = [(x, 884 + rnd.uniform(-12, 14)) for x in np.linspace(1004, 20, 12)]
    gm = ic.poly_mask([(10, 850)] + top + [(1014, 846)] + bot)
    ic.fill(gm, "#6c6c3a", "#3e3a22", (790, 900), noise=0.34, chroma=0.14)
    for _ in range(10):  # patches of bare earth and darker grass
        x, y = rnd.uniform(20, 1000), rnd.uniform(810, 880)
        col = rnd.choice([(128, 100, 64), (40, 58, 22), (96, 120, 50)])
        tint(ic, ic.poly_mask(ic.jitter(x, y, rnd.uniform(30, 70), rnd.uniform(8, 16), 8, 0.3)), gm, col, 0.35, 8)
    tint(ic, ic.poly_mask([(450, 806), (522, 806), (600, 900), (390, 900)]), gm, (150, 122, 84), 0.55, 10)  # path
    ic.shade(ic.mask("rectangle", (CX0 - 30, 796, CX1 + 30, 824)), alpha=0.45, blur=8)
    ic.shade(ic.mask("rectangle", (220, 850, 430, 880)), alpha=0.4, blur=8)
    ic.shade(ic.mask("rectangle", (530, 848, 860, 884)), alpha=0.45, blur=8)
    lay, d = layer()
    for _ in range(60):  # leaf litter
        x, y = rnd.uniform(20, 1000), rnd.uniform(810, 884)
        c = rnd.choice([(176, 116, 52), (140, 90, 40), (196, 150, 70), (110, 70, 34)])
        d.ellipse((x - 5, y - 3, x + 5, y + 3), fill=c + (int(rnd.uniform(140, 220)),))
    for _ in range(26):  # grass tufts
        x, y = rnd.uniform(20, 1000), rnd.uniform(812, 884)
        if 380 < x < 600 and y > 820:
            continue
        for k in range(5):
            dx = rnd.uniform(-12, 12)
            d.line([(x + dx * 0.3, y), (x + dx, y - rnd.uniform(12, 24))],
                   fill=rnd.choice([(44, 62, 22, 230), (70, 92, 34, 230), (120, 138, 60, 200)]), width=3)
    composite(ic, lay, gm)

    # ---- cordwood stack between stakes: rounds and split pieces of different sizes and ages
    for x in (534, 846):
        timber(ic, (x, 868), (x + rnd.uniform(-4, 4), 690), 18, "#8a6a4a", "#4a3624")
    ic.fill(ic.mask("rectangle", (552, 726, 830, 868)), "#1e140c", "#0e0a06", noise=0.1)
    tones = [("#d2a872", "#7e5634"), ("#c49a66", "#704a2c"), ("#aa9c86", "#5c544a"), ("#a07a52", "#4e3622")]
    rows = [846, 806, 766, 728]
    for row, y in enumerate(rows[::-1]):
        x = 552 + (row % 2) * 14 + rnd.uniform(0, 6)
        while x < 812:
            r = rnd.uniform(15, 27)
            cx = x + r
            if cx + r > 836:
                r = max(12, (836 - x) / 2)
                cx = x + r
            wood = rnd.choices(tones, weights=[4, 3, 2, 2])[0]
            cy = y + rnd.uniform(-4, 4)
            kind = rnd.choices(["round", "half", "quarter"], weights=[5, 3, 2])[0]
            if kind == "round":
                log_end(ic, cx, cy, r, wood=wood)
            else:
                split_log(ic, cx, cy, r * 1.1, 180 if kind == "half" else 90, rnd.uniform(0, 360), wood)
            x = cx + r + rnd.uniform(1, 5)
    ic.fill(ic.poly_mask([(544, 712), (840, 712), (832, 694), (556, 692)]), "#8a7458", "#5a4a36", noise=0.2)  # bark cap

    # bench with skeps
    ic.rect((226, 812, 420, 830), "#8a6a4a", "#4a3624", edge=4)
    for x in (244, 400):
        timber(ic, (x, 826), (x, 880), 14, "#6e5038", "#3a2a1c")
    skep(ic, 280, 814, 96, 104)
    skep(ic, 372, 814, 84, 90)
    lay, d = layer()  # a few bees
    for _ in range(9):
        x, y = rnd.uniform(250, 440), rnd.uniform(680, 780)
        d.ellipse((x - 4, y - 3, x + 4, y + 3), fill=(40, 30, 10, 220))
    composite(ic, lay)
