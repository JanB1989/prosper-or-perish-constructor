"""Llama Caravan Post (pp_llama_caravan_post): Andean tambo-style caravan post with llama trains.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/pp_llama_caravan_post/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/pp_llama_caravan_post

Identity: two round dry-stone qullqa storehouses under conical ichu-grass thatch, each with a
trapezoidal Inca doorway, a snow-capped peak rising behind, and two woolly pack llamas with
striped costal bags and red ear tassels on the puna grass. Round storehouses, the peak and the
llamas keep it apart from vanilla's rectangular tambo.
Caravan-family helpers copied from pp_caravanserai (see there); local: ``llama``, ``fieldstones``, ``qullqa``,
``thatch_cone``, ``peak``, ``puna``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 67
REFS = ("tambo", "caravan_stop", "caravanserai", "market_village")

BASE = 890
GROUND = 946
FIELDSTONE = ("#aaa08e", "#645a4c")
ICHU = ("#d2b46e", "#6e5428")


# ---------------------------------------------------------------- caravan-family helpers
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tone(c, f: float) -> tuple[int, int, int]:
    return tuple(int(min(255, max(0, v * f))) for v in rgb(c))


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


def rim(ic: Icon, m: Image.Image, width: int = 4, color=(40, 24, 12), alpha: float = 0.75) -> None:
    """Soft dark edge just inside a mask (a form's contour without a hard outline)."""
    ring = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(2 * width + 1)))
    ic.shade(ring, color, alpha, blur=1)


def smooth(m: Image.Image, r: float = 10) -> Image.Image:
    """Round the corners of a union of shapes (blur, then threshold)."""
    return m.filter(ImageFilter.GaussianBlur(r)).point(lambda v: 255 if v > 127 else 0)


def tube(path, widths, n: int = 40):
    """Tapering band along a polyline: returns (outline points, left side, right side)."""
    pts = np.array(path, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    xs, ys = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    ws = np.interp(s / cum[-1], np.linspace(0, 1, len(widths)), widths)
    dx, dy = np.gradient(xs), np.gradient(ys)
    ln = np.hypot(dx, dy) + 1e-6
    nx, ny = -dy / ln, dx / ln
    a = [(x + nx_ * w / 2, y + ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    b = [(x - nx_ * w / 2, y - ny_ * w / 2) for x, y, nx_, ny_, w in zip(xs, ys, nx, ny, ws)]
    return a + b[::-1], a, b


def hair(ic: Icon, mask: Image.Image, box, n: int, length: float = 14, light=(255, 236, 206), dark=(30, 16, 8),
         alpha: int = 60) -> None:
    """Short coat strokes (hair lying back and down) clipped to ``mask``."""
    rnd = ic.random
    x0, y0, x1, y1 = box

    def paint(d):
        for _ in range(n):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            t = rnd.uniform(-1, 1)
            col = light + (int(t * alpha),) if t > 0 else dark + (int(-t * alpha),)
            d.line([(x, y), (x + rnd.uniform(-4, 4), y + length * rnd.uniform(0.6, 1.2))], fill=col, width=3)

    ic.overlay(paint, mask)


def modelled(ic: Icon, m: Image.Image, s: float, light=(255, 222, 170), lit: float = 0.4, dark: float = 0.5) -> None:
    """Round an animal's flat mask: warm light along every upper-left edge, dark underside."""
    edge = ImageChops.subtract(m, ImageChops.offset(m, int(12 * s) + 1, int(26 * s) + 1))
    tint(ic, edge, m, light, lit, 7 * s)
    under = ImageChops.subtract(m, ImageChops.offset(m, -int(6 * s), -int(30 * s) - 1))
    tint(ic, under, m, (12, 6, 2), dark, 10 * s)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.0, long: float = 1.0) -> None:
    """Coursed stone where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.85, 1.12)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.4, 2.4) * long
            j = lambda: rnd(-2, 2)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(70, 60, 44, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 50)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(40, 26, 14, shadow), width=5)
            x += w
        y += h
    paste_clipped(ic, lay, m)


def pointed(x0: float, x1: float, spring: float, bottom: float, k: float = 0.82, n: int = 18) -> list:
    """Two-centred pointed arch opening from ``bottom`` up to the springing line and the apex."""
    w = x1 - x0
    r = w * k
    mid = (x0 + x1) / 2
    th_mid = math.acos((mid - x0 - r) / r)
    left = [(x0 + r + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, th_mid, n)]
    right = [(x1 - (px - x0), py) for px, py in left[::-1]]
    return [(x0, bottom)] + left + right[1:] + [(x1, bottom)]


def sack(ic: Icon, cx, base, w, h, c=("#d8cdb4", "#7e735e"), lean: float = 0) -> None:
    """Filled sack: slumped round body lit from the upper left, gathered neck tied with twine."""
    pts = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        s, co = math.sin(a), math.cos(a)
        rx = w / 2 * (1 + 0.1 * math.sin(3 * a + 1))
        y = base - h * 0.42 + s * h * 0.42
        if s > 0.6:
            y = min(y, base)
        pts.append((cx + co * rx + lean * (base - y) * 0.2, y))
    body = ic.poly_mask(pts)
    ic.fill(body, c[0], c[1], radial=(cx - w * 0.25, base - h * 0.7, w * 1.1), noise=0.16)
    tint(ic, ic.mask("ellipse", (cx - w * 0.1, base - h * 0.6, cx + w * 0.8, base + 10)), body, (20, 14, 8), 0.28, 12)
    nx = cx + lean * h * 0.2
    neck = [(nx - w * 0.14, base - h * 0.8), (nx - w * 0.1, base - h * 1.02), (nx - w * 0.2, base - h * 1.12),
            (nx + w * 0.02, base - h * 1.08), (nx + w * 0.2, base - h * 1.14), (nx + w * 0.12, base - h * 1.0),
            (nx + w * 0.15, base - h * 0.8)]
    ic.fill(ic.poly_mask(neck), c[0], c[1], radial=(nx - w * 0.1, base - h * 1.1, w * 0.5), noise=0.14)
    ic.outline(neck, 3, (60, 48, 32, 150))
    ic.line([(nx - w * 0.13, base - h * 0.96), (nx + w * 0.13, base - h * 0.95)], 6, (96, 72, 44))
    ic.outline(pts, 4, (56, 44, 30, 160))


def rope(ic: Icon, pts, width: int = 6, color=(176, 146, 100)) -> None:
    ic.line(pts, width + 4, (50, 38, 24, 220))
    ic.line(pts, width, color)


def road(ic: Icon, top: float, bot: float, c=("#c9a878", "#8e7048"), x0: float = 16, x1: float = 1008,
         ruts: bool = False) -> Image.Image:
    """Dusty ground band with pebbles, hoof marks and a shaded far edge; returns its mask."""
    pts = [(x0 + 8, top), (x1 - 8, top), (x1, bot - 20), (x1 - 26, bot), (x0 + 26, bot), (x0, bot - 20)]
    m = ic.poly_mask(pts)
    ic.fill(m, c[0], c[1], (top, bot), noise=0.3)
    rnd = ic.random.uniform

    def marks(d: ImageDraw.ImageDraw) -> None:
        if ruts:
            for y in (top + (bot - top) * 0.45, top + (bot - top) * 0.78):
                x = x0 + 10
                while x < x1 - 10:
                    ln = rnd(60, 160)
                    d.line([(x, y + rnd(-3, 3)), (x + ln, y + rnd(-3, 3))], fill=(50, 36, 20, 110), width=int(rnd(6, 9)))
                    x += ln + rnd(10, 50)
        for _ in range(70):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 8, bot - 8)
            r = rnd(3, 8)
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(236, 220, 186, 130))
            d.line([(x - r, y + r * 0.6), (x + r, y + r * 0.6)], fill=(50, 36, 20, 110), width=2)
        for _ in range(26):
            x, y = rnd(x0 + 20, x1 - 20), rnd(top + 10, bot - 10)
            d.arc((x - 9, y - 5, x + 9, y + 5), 0, 180, fill=(60, 44, 24, 100), width=3)

    ic.overlay(marks, m)
    tint(ic, ic.mask("rectangle", (0, top, SIZE, top + 24)), m, (0, 0, 0), 0.32, 10)
    ic.outline(pts, 5)
    return m


# ---------------------------------------------------------------- llama
def llama(ic: Icon, X: float, G: float, s: float = 0.6, coat=("#e2d2b8", "#6e5c46"), bags=("#b83a2c", "#f0e6d0"),
          dim: float = 0.0) -> Image.Image:
    """Pack llama in profile facing left: woolly body, tall upright neck, banana ears with red
    tassels, thin legs, a striped costal bag slung on the flank. Local units, y up."""

    def P(pts):
        return [(X + x * s, G - y * s) for x, y in pts]

    def box(x0, y0, x1, y1):
        (ax, ay), (bx, by) = P([(x0, y0), (x1, y1)])
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    for hx in (60, 100, 250, 290):
        cx = X + hx * s
        tint(ic, ic.mask("ellipse", (cx - 30 * s, G - 8 * s, cx + 30 * s, G + 12 * s)), None, (10, 6, 2), 0.5, 5)
    near_fore = [(46, 250), (102, 250), (90, 130), (86, 110), (84, 12), (94, 0), (58, 0), (60, 12), (58, 110), (52, 130)]
    near_hind = [(230, 260), (292, 260), (286, 150), (274, 110), (276, 12), (286, 0), (250, 0), (252, 12), (246, 110),
                 (242, 150)]
    far = union(ic.poly_mask(P([(x + 34, y) for x, y in near_fore])), ic.poly_mask(P([(x - 28, y) for x, y in near_hind])))
    ic.fill(far, tone(coat[0], 0.5), tone(coat[1], 0.5), (G - 240 * s, G), noise=0.16)
    rim(ic, far, 3, (20, 12, 6), 0.6)
    # woolly body: a jittered, lumpy outline
    body = ic.poly_mask(P(ic.jitter(172, 312, 160, 100, 40, 0.05)))
    neck, _, _ = tube(P([(64, 330), (54, 420), (52, 490), (60, 546)]), [124 * s, 84 * s, 68 * s, 62 * s])
    head = [(92, 590), (40, 596), (0, 584), (-40, 566), (-60, 548), (-58, 530), (-34, 522), (10, 526), (50, 532),
            (86, 540)]
    tail, _, _ = tube(P([(310, 310), (336, 330), (344, 350)]), [40 * s, 34 * s, 24 * s])
    legs = union(ic.poly_mask(P(near_fore)), ic.poly_mask(P(near_hind)))
    mass = smooth(union(body, ic.poly_mask(neck), ic.poly_mask(P(head)), ic.poly_mask(tail), legs), 5 * s)
    xs = [p[0] for p in P(head)]
    ic.fill(mass, coat[0], coat[1], radial=(min(xs), G - 620 * s, 700 * s), noise=0.2, chroma=0.06)
    modelled(ic, mass, s, (255, 244, 220), 0.35, 0.45)
    tint(ic, ic.mask("ellipse", box(20, 200, 330, 280)), mass, (20, 12, 4), 0.35, 14 * s)
    tint(ic, ic.mask("rectangle", (0, G - 120 * s, SIZE, G)), legs, (40, 28, 16), 0.3, 6 * s)
    # wool: short curly strokes on the body and neck
    rnd = ic.random.uniform

    def wool(d):
        for _ in range(int(900 * s * s)):
            x, y = rnd(X - 60 * s, X + 340 * s), rnd(G - 600 * s, G - 200 * s)
            r = rnd(5, 9) * s * 1.4
            t = rnd(-1, 1)
            col = (255, 248, 230, int(t * 90)) if t > 0 else (40, 28, 16, int(-t * 70))
            d.arc((x - r, y - r, x + r, y + r), rnd(0, 180), rnd(200, 360), fill=col, width=3)

    ic.overlay(wool, ic.intersect(mass, ImageChops.invert(ic.poly_mask(P(head)))))
    # ears, eye, split lip
    for ex_, lean in ((58, 8), (80, 14)):
        ear, _, _ = tube(P([(ex_, 586), (ex_ + lean * 0.3, 630), (ex_ + lean, 668), (ex_ - 4, 690)]),
                         [22 * s, 24 * s, 18 * s, 6 * s])
        ic.fill(ic.poly_mask(ear), tone(coat[0], 0.95), tone(coat[1], 0.95), noise=0.14)
        ic.outline(ear, 3, (40, 26, 14, 180))
        tx, ty = P([(ex_ + lean * 0.3, 628)])[0]
        ic.fill(ic.mask("ellipse", (tx - 10 * s, ty - 8 * s, tx + 14 * s, ty + 16 * s)), "#e0405a", "#7a1020", noise=0.1)
    ex, ey = P([(24, 568)])[0]
    ic.draw.ellipse((ex - 9 * s, ey - 7 * s, ex + 9 * s, ey + 7 * s), fill=(18, 12, 10, 255))
    ic.draw.ellipse((ex - 5 * s, ey - 5 * s, ex - 1, ey - 1), fill=(200, 190, 180, 255))
    ic.line(P([(-56, 540), (-40, 536)]), 3, (40, 24, 14, 200))
    nx, ny = P([(-48, 556)])[0]
    ic.line([(nx, ny), (nx + 8 * s, ny - 4 * s)], 3, (30, 18, 10, 220))
    tint(ic, ic.poly_mask(P([(-58, 530), (-34, 522), (40, 530), (-20, 546)])), mass, (30, 16, 6), 0.3, 4 * s)
    ic.line(P([(-10, 530), (-20, 584), (40, 594), (60, 540)]), max(3, int(8 * s)), bags[0])  # woven halter
    rim(ic, mass, 3, (40, 26, 12), 0.6)
    # costal bag over the back: striped wool, bulging, tied across
    bag = P([(124, 404), (228, 406), (240, 360), (238, 290), (220, 262), (140, 260), (122, 290), (116, 360)])
    bm = smooth(ic.poly_mask(bag), 5 * s)
    ic.fill(bm, bags[1], tone(bags[1], 0.5), radial=(bag[0][0], bag[0][1], 260 * s), noise=0.18)
    ic.overlay(lambda d: [d.line(P([(88, y), (262, y + 4)]), fill=tuple(int(v) for v in rgb(c)) + (220,),
                                 width=max(4, int(13 * s)))
                          for y, c in ((384, bags[0]), (358, "#2a2a32"), (332, bags[0]), (306, "#2a2a32"), (280, bags[0]))],
               bm)
    tint(ic, ic.mask("rectangle", box(206, 250, 260, 420)), bm, (20, 10, 4), 0.3, 12 * s)
    rim(ic, bm, 3, (40, 20, 10), 0.8)
    rope(ic, P([(128, 404), (178, 420), (232, 408)]), max(3, int(6 * s)), (190, 170, 130))
    if dim:
        tint(ic, union(mass, bm), None, (30, 30, 40), dim)
    return mass


# ---------------------------------------------------------------- storehouses, peak, ground
def thatch_cone(ic: Icon, cx, apex, eave, rx) -> Image.Image:
    """Conical ichu-grass roof: straw strokes running from the peak, ragged lower edge, a binding ring."""
    rnd = ic.random.uniform
    pts = [(cx, apex)]
    for t in np.linspace(0, 1, 30):
        a = math.pi * t
        pts.append((cx + rx * math.cos(a) * 1.0, eave + rx * 0.22 * math.sin(a) + rnd(-6, 10)))
    pts = [(cx, apex)] + pts[1:][::-1]
    m = ic.poly_mask(pts)
    ic.fill(m, ICHU[0], ICHU[1], radial=(cx - rx * 0.6, apex, (eave - apex) * 1.4), noise=0.25)

    def straw(d):
        for _ in range(700):
            t = rnd(0.05, 1)
            a = rnd(0.05, math.pi - 0.05)
            bx, by = cx + rx * math.cos(a) * t, apex + (eave - apex + rx * 0.22 * math.sin(a)) * t
            ln = rnd(20, 50)
            dx, dy = bx - cx, by - apex
            L = math.hypot(dx, dy) or 1
            col = (255, 236, 180, int(rnd(40, 110))) if rnd(0, 1) < 0.5 else (60, 40, 14, int(rnd(40, 110)))
            d.line([(bx, by), (bx + dx / L * ln, by + dy / L * ln)], fill=col, width=3)

    ic.overlay(straw, m)
    tint(ic, ic.poly_mask([(cx, apex), (cx + rx * 1.1, eave + 40), (cx + rx * 0.1, eave + 40)]), m, (30, 16, 4), 0.35, 20)
    ring_y = apex + (eave - apex) * 0.3
    ic.line([(cx - rx * 0.3, ring_y), (cx, ring_y + 8), (cx + rx * 0.3, ring_y)], 8, (90, 66, 30))
    ic.outline(pts, 5)
    ic.line([(cx, apex + 4), (cx + 4, apex - 34)], 10, (100, 76, 40))  # tuft
    return m


def fieldstones(ic: Icon, box, clip: Image.Image, course: float = 34) -> None:
    """Dry-stone walling: irregular rounded fieldstones of mixed size in rough courses, each lit on
    its upper left and shadowed below, with dark gaps between (no mortar)."""
    x0, y0, x1, y1 = box
    ic.fill(clip, "#3e362c", "#1e1a14", (y0, y1), noise=0.2)
    rnd = ic.random.uniform
    y = y0 - course * 0.3
    while y < y1 + course:
        h = course * rnd(0.75, 1.2)
        x = x0 - rnd(0, course)
        while x < x1 + course:
            w = course * rnd(0.9, 2.0)
            pts = ic.jitter(x + w / 2, y + h / 2, w / 2 + 1, h / 2 + 1, 10, 0.07)
            m = ic.intersect(ic.poly_mask(pts), clip)
            base = tone(FIELDSTONE[0], rnd(0.82, 1.12))
            ic.fill(m, base, tone(FIELDSTONE[1], rnd(0.85, 1.1)), radial=(x + w * 0.2, y, max(w, h) * 1.1), noise=0.18)
            x += w
        y += h


def qullqa(ic: Icon, x0, x1, top, apex) -> None:
    """Round dry-stone storehouse with a trapezoidal doorway and a conical thatch roof."""
    w = x1 - x0
    cx = (x0 + x1) / 2
    body = union(ic.mask("rectangle", (x0, top, x1, BASE)), ic.mask("ellipse", (x0, BASE - w * 0.14, x1, BASE + w * 0.14)))
    fieldstones(ic, (x0, top, x1, BASE + w * 0.14), body, course=w * 0.15)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.6, top, x1 + 20, BASE + 60)), body, (20, 16, 10), 0.45, w * 0.16)
    tint(ic, ic.mask("rectangle", (x0 + w * 0.15, top, x0 + w * 0.35, BASE)), body, (255, 246, 226), 0.16, w * 0.08)
    # trapezoidal doorway with a stone lintel
    dh = (BASE - top) * 0.55
    dw = w * 0.22
    door = [(cx - dw * 0.62, BASE + 4), (cx - dw * 0.42, BASE - dh), (cx + dw * 0.42, BASE - dh), (cx + dw * 0.62, BASE + 4)]
    ic.poly(door, "#2a2018", "#0e0a06", edge=0)
    ic.rect((cx - dw * 0.62, BASE - dh - 20, cx + dw * 0.62, BASE - dh + 2), "#b8ae9a", "#7a705e", edge=4)
    ic.outline(door, 4)
    ic.overlay(lambda d: d.line([(x0, top), (x0, BASE)], fill=(40, 30, 20, 200), width=5))
    ic.overlay(lambda d: d.line([(x1, top), (x1, BASE)], fill=(40, 30, 20, 200), width=5))
    thatch_cone(ic, cx, apex, top + 10, w * 0.62)
    tint(ic, ic.mask("rectangle", (x0, top + 20, x1, top + 70)), body, (10, 6, 2), 0.45, 12)


def peak(ic: Icon) -> None:
    """Snow-capped Andean peak behind the post: blue-grey rock planes, snow in the gullies."""
    pts = [(330, 760), (480, 520), (570, 440), (650, 330), (712, 262), (770, 320), (840, 380), (910, 420), (1000, 580),
           (1000, 760)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#9aa6b2", "#56606e", radial=(600, 260, 600), noise=0.16)
    # lit and shaded rock planes either side of the ridges
    tint(ic, ic.poly_mask([(712, 262), (770, 320), (840, 380), (910, 420), (1000, 580), (1000, 760), (740, 760),
                           (716, 460)]), m, (20, 26, 50), 0.35)
    tint(ic, ic.poly_mask([(570, 440), (650, 330), (712, 262), (690, 420), (620, 560)]), m, (255, 250, 240), 0.14, 10)
    snow = [(590, 420), (650, 330), (712, 262), (770, 320), (840, 380), (806, 392), (780, 366), (752, 404),
            (724, 360), (700, 410), (672, 372), (630, 428)]
    sm = ic.poly_mask(snow)
    ic.fill(sm, "#f4f6fa", "#b4c0d2", (262, 430), noise=0.08)
    tint(ic, ic.poly_mask([(712, 262), (770, 320), (840, 380), (806, 392), (780, 366), (752, 404), (724, 360)]), sm,
         (60, 80, 130), 0.3)
    tint(ic, ic.mask("rectangle", (0, 560, SIZE, 780)), m, (190, 196, 186), 0.35, 50)  # haze at the foot
    ic.outline(pts, 5)


def puna(ic: Icon) -> Image.Image:
    """Puna grassland band with tussocks of ichu breaking the far edge."""
    m = road(ic, BASE - 10, 978, c=("#b0a070", "#6a5c38"))
    rnd = ic.random.uniform

    def grass(d):
        for _ in range(360):
            x, y = rnd(24, 1000), rnd(BASE, 970)
            ln = rnd(10, 22)
            t = rnd(-1, 1)
            col = (236, 220, 160, int(t * 150)) if t > 0 else (50, 44, 20, int(-t * 150))
            d.line([(x, y), (x + rnd(-6, 6), y - ln)], fill=col, width=3)

    ic.overlay(grass, m)
    return m


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.86
    ic.grade["gamma"] = 0.76
    peak(ic)
    qullqa(ic, 430, 610, 690, 500)
    qullqa(ic, 90, 390, 580, 300)
    puna(ic)
    llama(ic, 800, GROUND - 24, 0.66, coat=("#8a6446", "#2e1c10"), bags=("#2e6a8a", "#e8dcc0"), dim=0.08)
    llama(ic, 640, GROUND, 0.76)
