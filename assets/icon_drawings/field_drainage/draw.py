"""Drainage Ditches: raised crop beds between open drains running into a collector ditch, which
leaves the field through a timber sluice; pollard willows along the back, a plank footbridge and a
spade in the spoil.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/field_drainage/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/field_drainage

Identity: blue lines of water cutting the green field slab of the field-management family from
back to front, meeting a cross ditch and pouring out through a sluice gate in the front bank. Unlike
vanilla irrigation (a water wheel lifting water on) and polders (a dyke against the sea), this is
water being led off wet inland ground.

The family helper block is shared with the other field-management drawings (kept identical by
copying); icon helpers: ``ditch``, ``beds``, ``willow``, ``sluice``, ``falling_water``, ``spade``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 41
REFS = ("irrigation_systems", "polders", "farming_village", "terraces")


# ---- family helpers ----------------------------------------------------------------------------
SOIL = ("#5e4430", "#34241a")
GOLD = ("#d8a040", "#8a5c20")
GREEN = ("#6e8e3c", "#34481c")
WOOD = ("#8e6644", "#4e3522")
IRON = ("#8a8a88", "#3e3e40")


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
    ic.shade(ic.intersect(mask, clip) if clip is not None else mask, color, alpha, blur)


def dark(c, f: float):
    return tuple(int(v * f) for v in rgb(c))


def mix(c1, c2, t: float):
    a, b = rgb(c1), rgb(c2)
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


class Field:
    """Field slab top seen from the raised camera: (u, v) in [0, 1]^2, u across, v from back to front."""

    def __init__(self, bl, br, fl, fr, persp: float = 1.25):
        self.bl, self.br, self.fl, self.fr = (np.array(p, float) for p in (bl, br, fl, fr))
        self.persp = persp

    def P(self, u: float, v: float) -> tuple[float, float]:
        v = v ** self.persp
        back = self.bl + (self.br - self.bl) * u
        front = self.fl + (self.fr - self.fl) * u
        p = back + (front - back) * v
        return float(p[0]), float(p[1])

    def band(self, v0: float, v1: float, u0: float = 0.0, u1: float = 1.0, n: int = 24) -> list:
        top = [self.P(u, v0) for u in np.linspace(u0, u1, n)]
        bot = [self.P(u, v1) for u in np.linspace(u1, u0, n)]
        left = [self.P(u0, v) for v in np.linspace(v1, v0, 8)[1:-1]]
        right = [self.P(u1, v) for v in np.linspace(v0, v1, 8)[1:-1]]
        return top + right + bot + left

    def mask(self, ic: Icon, v0=0.0, v1=1.0, u0=0.0, u1=1.0) -> Image.Image:
        return ic.poly_mask(self.band(v0, v1, u0, u1))

    def scale(self, v: float) -> float:
        """Size of things at depth v relative to the front edge."""
        return 0.62 + 0.38 * v


def slab_face(ic: Icon, F: Field, depth: float = 64) -> Image.Image:
    """Cut earth below the front edge: lit lip, dark strata, stones and root ends. Its top runs a
    little inside the field, so the field painted over it leaves no seam (and no stray outline)."""
    rnd = ic.random
    edge = [F.P(u, 1.0) for u in np.linspace(0, 1, 30)]
    edge = [(x, y + rnd.uniform(-3, 3)) for x, y in edge]
    low = [(x + rnd.uniform(-4, 4), y + depth + rnd.uniform(-8, 10)) for x, y in edge[::-1]]
    hidden = [F.P(u, 0.975) for u in np.linspace(0, 1, 30)]
    pts = hidden + low
    m = ic.poly_mask(pts)
    ys = [p[1] for p in edge + low]
    ic.fill(m, "#6a5038", "#34261a", (min(ys), max(ys)), noise=0.3, chroma=0.12)
    lay, d = layer()
    for k in range(3):  # strata
        f = 0.3 + 0.25 * k
        line = [(x, y + depth * f + rnd.uniform(-4, 4)) for x, y in edge[::2]]
        d.line(line, fill=(30, 20, 12, 90), width=4, joint="curve")
    for _ in range(40):  # stones and pebbles
        x = rnd.uniform(edge[0][0], edge[-1][0])
        y = np.interp(x, [p[0] for p in edge], [p[1] for p in edge]) + rnd.uniform(12, depth - 6)
        r = rnd.uniform(4, 10)
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(150, 136, 116, 170))
        d.ellipse((x - r * 0.6, y - r * 0.6, x + r * 0.2, y), fill=(200, 188, 168, 120))
    for _ in range(14):  # root ends
        x = rnd.uniform(edge[0][0], edge[-1][0])
        y = np.interp(x, [p[0] for p in edge], [p[1] for p in edge]) + rnd.uniform(6, 20)
        d.line([(x, y), (x + rnd.uniform(-14, 14), y + rnd.uniform(12, 30))], fill=(40, 28, 16, 150), width=3)
    composite(ic, lay, m)
    tint(ic, ic.poly_mask(edge + [(x, y + 16) for x, y in edge[::-1]]), m, (255, 236, 200), 0.18, 4)
    tint(ic, ic.poly_mask([(x, y + depth * 0.6) for x, y in edge] + low), m, (0, 0, 0), 0.3, 10)
    ic.line(low + [hidden[0]], 3, (40, 28, 16, 150))  # sides and foot only; the top lies under the field
    ic.line([hidden[-1], low[0]], 3, (40, 28, 16, 150))
    return m


def grain(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, h: float = 54, colors=GOLD,
          tufts: bool = True) -> Image.Image:
    """Standing cereal: gold base with a lighter ripening band and darker patches, dense stalk strokes
    with ears of uneven tone, the back row breaking the edge."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, colors[0], colors[1], (min(ys) - 20, max(ys) + 30), noise=0.28, chroma=0.12)
    # uneven ripening: a paler band across the stand, a few darker, laid patches
    vb = rnd.uniform(v0 + (v1 - v0) * 0.3, v0 + (v1 - v0) * 0.6)
    band_m = F.mask(ic, max(v0, vb - (v1 - v0) * 0.12), min(v1, vb + (v1 - v0) * 0.1), u0, u1)
    tint(ic, band_m, m, (255, 236, 170), 0.22, 10)
    for _ in range(3):
        x, y = F.P(rnd.uniform(u0, u1), rnd.uniform(v0, v1))
        r = rnd.uniform(40, 80)
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.35, x + r, y + r * 0.35)), m, (60, 36, 8), 0.25, 12)
    lit = tuple(min(255, int(v * 1.2)) for v in rgb(colors[0]))
    base = tuple(int(c) for c in rgb(colors[0]))
    deep = dark(colors[1], 0.85)
    shd = dark(colors[1], 0.62)
    lay, d = layer()
    rows = max(3, int((v1 - v0) * 26))
    for i in range(rows + 1):
        v = min(v1, v0 + (v1 - v0) * (i + rnd.uniform(-0.3, 0.3)) / rows)
        s = F.scale(v)
        hh = h * s
        u = u0 + rnd.uniform(0, 0.012)
        while u < u1:
            x, y = F.P(u, v)
            y += rnd.uniform(-3, 3)
            top = (x + rnd.uniform(-5, 5), y - hh * rnd.uniform(0.72, 1.08))
            d.line([(x, y), top], fill=shd + (150,), width=4)
            d.line([(x - 2, y - hh * 0.25), (top[0] - 2, top[1] + 4)], fill=lit + (140,), width=3)
            q = rnd.random()
            tone = lit if q < 0.5 else base if q < 0.88 else deep
            d.ellipse((top[0] - 5 * s, top[1] - 11 * s, top[0] + 5 * s, top[1] + 9 * s), fill=tone + (200,))
            u += rnd.uniform(0.007, 0.018) / s
    composite(ic, lay, union(m, F.mask(ic, max(0, v0 - 0.12), v0 + 0.02, u0, u1)) if tufts else m)
    # the stand shades its own foot
    tint(ic, F.mask(ic, v1 - (v1 - v0) * 0.25, v1, u0, u1), m, (30, 20, 6), 0.25, 8)
    return m


def greens(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, colors=GREEN, r: float = 16,
           rows: int | None = None, soil=SOIL, curve: float = 0.0) -> Image.Image:
    """Leafy crop in rows across the field (peas, beans, roots): soil between, clumps of uneven size,
    spacing and hue, lit top-left and overlapping the row behind. ``curve`` bows the rows back in
    the middle (rows running over a raised bed)."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, soil[0], soil[1], (min(ys), max(ys)), noise=0.3)
    rows = rows or max(3, int((v1 - v0) * 22))
    step = (v1 - v0) / rows
    lay, d = layer()
    for i in range(rows):
        vr = v0 + step * (i + 0.5)
        s = F.scale(vr)
        width = max(1.0, abs(F.P(u1, vr)[0] - F.P(u0, vr)[0]) / (u1 - u0))
        u = u0 + rnd.uniform(0, 0.02)
        while u < u1:
            t = (u - u0) / max(u1 - u0, 1e-6)
            v = vr + rnd.uniform(-0.18, 0.18) * step - curve * math.sin(math.pi * t)
            x, y = F.P(u, v)
            rr = r * s * rnd.uniform(0.62, 1.35)
            if rnd.random() < 0.06:  # a gap in the row
                u += rr * 1.6 / width
                continue
            g = rnd.uniform(0.84, 1.14)
            body = rgb(colors[0]) * g + np.array([rnd.uniform(-14, 16), rnd.uniform(-6, 8), rnd.uniform(-12, 6)])
            body = tuple(int(np.clip(c, 0, 255)) for c in body)
            lit = tuple(min(255, int(c * 1.28)) for c in body)
            sh = tuple(int(c * 0.55) for c in body)
            ox = rnd.uniform(-0.15, 0.15) * rr
            d.ellipse((x - rr * 1.15, y - rr * 0.8, x + rr * 1.25, y + rr * 0.6), fill=sh + (230,))
            d.ellipse((x - rr + ox, y - rr * 1.0, x + rr * 0.9 + ox, y + rr * 0.3), fill=body + (255,))
            if rnd.random() < 0.6:  # a second leaf mass makes the clump irregular
                k = rnd.choice((-1, 1))
                d.ellipse((x + k * rr * 0.5 - rr * 0.6, y - rr * 0.9, x + k * rr * 0.5 + rr * 0.6, y + rr * 0.1),
                          fill=tuple(int(c * 0.92) for c in body) + (255,))
            d.ellipse((x - rr * 0.8 + ox, y - rr * 0.95, x + rr * 0.1 + ox, y - rr * 0.3), fill=lit + (190,))
            u += rr * rnd.uniform(1.15, 1.9) / width
    composite(ic, lay, union(m, F.mask(ic, max(0, v0 - 0.03), v0 + 0.02, u0, u1)))
    return m


def furrows(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, n: int = 7, soil=SOIL) -> Image.Image:
    """Fresh ploughed land: ridges across the field, lit crest and dark trench, clods."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, soil[0], soil[1], (min(ys), max(ys)), noise=0.34, chroma=0.1)
    lay, d = layer()
    for k in range(n):
        va = v0 + (v1 - v0) * k / n
        vb = v0 + (v1 - v0) * (k + 1) / n
        s = F.scale(vb)
        crest = [F.P(u, va + (vb - va) * 0.45) for u in np.linspace(u0, u1, 20)]
        crest = [(x, y + rnd.uniform(-2, 2)) for x, y in crest]
        trench = [F.P(u, vb) for u in np.linspace(u0, u1, 20)]
        d.polygon(crest + [(x, y - 3) for x, y in trench[::-1]], fill=(20, 12, 6, 120))
        d.line(crest, fill=(176, 142, 104, 150), width=int(7 * s), joint="curve")
        d.line([(x, y - 5 * s) for x, y in crest], fill=(210, 180, 140, 90), width=int(3 * s), joint="curve")
        for _ in range(int(26 * (u1 - u0))):
            u = rnd.uniform(u0, u1)
            x, y = F.P(u, va + (vb - va) * rnd.uniform(0.3, 0.7))
            r = rnd.uniform(4, 9) * s
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(30, 20, 10, 140))
            d.ellipse((x - r * 0.8, y - r * 0.9, x + r * 0.4, y), fill=(170, 136, 98, 130))
    composite(ic, lay, m)
    return m


def stubble(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0) -> Image.Image:
    """Harvested ground: pale straw-brown with short upright stubble ticks in rows."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, "#b08a4c", "#6e5430", (min(ys), max(ys)), noise=0.3, chroma=0.12)
    lay, d = layer()
    rows = max(4, int((v1 - v0) * 30))
    for i in range(rows):
        v = v0 + (v1 - v0) * (i + 0.5) / rows
        s = F.scale(v)
        u = u0 + rnd.uniform(0, 0.02)
        while u < u1:
            x, y = F.P(u, v)
            h = rnd.uniform(8, 14) * s
            d.line([(x, y), (x + rnd.uniform(-2, 2), y - h)], fill=(70, 52, 28, 150), width=3)
            d.line([(x - 3, y - 1), (x - 3, y - h + 2)], fill=(232, 210, 160, 110), width=2)
            u += rnd.uniform(0.012, 0.02)
    composite(ic, lay, m)
    return m


def stook(ic: Icon, cx: float, base: float, w: float, h: float) -> None:
    """Stook of sheaves leaned together: straw cone lit left, a rounded, tied, slightly flattened cap
    of ears on top. No interior lines; the silhouette carries the edge."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.3, base - 12, cx + w * 1.0, base + 12)), alpha=0.4, blur=6)
    body = [(cx - w * 0.5, base), (cx - w * 0.38, base - h * 0.5), (cx - w * 0.28, base - h * 0.76),
            (cx + w * 0.27, base - h * 0.76), (cx + w * 0.4, base - h * 0.5), (cx + w * 0.52, base + 2)]
    m = ic.poly_mask(body)
    ic.fill(m, "#dcb45a", "#8a6428", (cx - w * 0.5, cx + w * 0.5), vertical=False, noise=0.28)
    lay, d = layer()
    for _ in range(int(w / 3)):
        x = rnd.uniform(cx - w * 0.45, cx + w * 0.45)
        d.line([(x, base), (cx + (x - cx) * 0.55, base - h * 0.76)], fill=(90, 62, 24, 110), width=3)
    composite(ic, lay, m)
    tint(ic, ic.poly_mask([(cx + w * 0.02, base - h * 0.8), (cx + w * 0.6, base - h * 0.8), (cx + w * 0.6, base + 4),
                           (cx + w * 0.06, base + 4)]), m, (40, 22, 6), 0.4, 6)
    # the cap: a flattened dome of ears drooping over the shoulders
    cy = base - h * 0.74
    cap_pts = []
    for a in np.linspace(math.pi, 2 * math.pi, 16):
        rx = w * 0.33 * rnd.uniform(0.97, 1.03)
        ry = h * 0.13 * rnd.uniform(0.94, 1.04)
        cap_pts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry * (0.8 + 0.2 * abs(math.cos(a)))))
    cap_pts += [(cx + w * 0.34, cy + h * 0.06), (cx + w * 0.1, cy + h * 0.09), (cx - w * 0.12, cy + h * 0.09),
                (cx - w * 0.34, cy + h * 0.05)]
    cm = ic.poly_mask(cap_pts)
    ic.fill(cm, "#e6c26a", "#7e5822", radial=(cx - w * 0.2, cy - h * 0.14, w * 0.62), noise=0.24, chroma=0.08)
    lay, d = layer()
    for _ in range(int(w * 0.5)):  # ears hanging down the dome
        a = rnd.uniform(math.pi * 1.02, math.pi * 1.98)
        f = rnd.uniform(0.2, 1.0)
        x = cx + math.cos(a) * w * 0.32 * f
        y = cy + math.sin(a) * h * 0.14 * f
        L = rnd.uniform(8, 16)
        lit = x < cx - w * 0.04
        d.line([(x, y), (x + (x - cx) * 0.08, y + L)], fill=(246, 216, 140, 120) if lit else (96, 64, 22, 120), width=3)
    composite(ic, lay, cm)
    tint(ic, ic.mask("rectangle", (cx + w * 0.04, cy - h * 0.3, cx + w, cy + h * 0.2)), cm, (40, 22, 6), 0.35, 8)
    tint(ic, ic.mask("rectangle", (cx - w, cy + h * 0.02, cx + w, cy + h * 0.2)), cm, (40, 22, 6), 0.3, 5)
    # the tie below the cap
    ic.line([(cx - w * 0.33, cy + h * 0.12), (cx, cy + h * 0.14), (cx + w * 0.35, cy + h * 0.115)], 7, (104, 72, 30))
    ic.line([(cx - w * 0.3, cy + h * 0.11), (cx - w * 0.06, cy + h * 0.125)], 3, (214, 180, 110, 150))


def timber(ic: Icon, p0, p1, width: float, c1=WOOD[0], c2=WOOD[1]) -> Image.Image:
    """Squared beam: lit upper half, darker lower half, a thin highlight along it."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    nx, ny = -(y1 - y0) / L, (x1 - x0) / L
    if ny < 0:
        nx, ny = -nx, -ny
    h = width / 2
    pts = [(x0 - nx * h, y0 - ny * h), (x1 - nx * h, y1 - ny * h), (x1 + nx * h, y1 + ny * h), (x0 + nx * h, y0 + ny * h)]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(y0, y1) - h, max(y0, y1) + h), noise=0.18)
    ic.shade(ic.poly_mask([(x0, y0), (x1, y1), pts[2], pts[3]]), (20, 12, 6), 0.3)
    ic.line([(x0 - nx * h * 0.45, y0 - ny * h * 0.45), (x1 - nx * h * 0.45, y1 - ny * h * 0.45)], 3, (255, 225, 180, 70))
    ic.outline(pts, 4, (40, 26, 16, 170))
    return m


def plough(ic: Icon, x: float, g: float, k: float = 1.0, flip: bool = False, iron: bool = False,
           angle: float = 0.0) -> callable:
    """Wooden swing plough side-on, pointing right (left if ``flip``): sole in the furrow, a dark
    twisted mouldboard (weathered wood, or cast iron if ``iron``), iron share and coulter, long beam
    forward, two handles rising back. (x, g) = heel. ``angle`` turns the plough back into depth (the
    point runs up the picture). Returns the local-to-canvas mapping."""
    sx = -1 if flip else 1
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def P(a, b):
        return (x + sx * a * k * ca, g + b * k - a * k * sa)

    def box(a0, b0, a1, b1):
        (x0, y0), (x1, y1) = P(a0, b0), P(a1, b1)
        c = ((x0 + x1) / 2, (y0 + y1) / 2)
        r = abs(b1 - b0) * k / 2
        return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)

    lw, dw = "#bc9060", "#5e4028"  # weathered, sun-bleached ash
    ic.shade(ic.poly_mask([P(-60, -6), P(300, -6), P(320, 18), P(-40, 18)]), alpha=0.55, blur=10 * k)
    timber(ic, P(-4, -20), P(-150, -300), 20 * k, "#86603c", "#44301c")  # far handle, in shade
    timber(ic, P(-20, -10), P(160, -8), 20 * k, "#86603c", "#44301c")  # sole in the furrow
    ic.poly([P(140, -2), P(214, 6), P(132, -30)], "#c4c4bc", IRON[1], edge=3)  # share
    board = [P(20, -14), P(148, -8), P(146, -40), P(92, -88), P(38, -80)]  # twisted mouldboard
    ic.poly(board, *(("#8a9094", "#23272a") if iron else ("#7a5a3a", "#2a1c10")), vertical=False, edge=3)
    ic.shade(ic.poly_mask([P(96, -10), P(148, -8), P(146, -40), P(110, -70)]), (0, 0, 0), 0.4, blur=3)
    ic.shade(ic.poly_mask([P(40, -74), P(58, -84), P(98, -58), P(72, -48)]), (255, 236, 196), 0.28, blur=4)
    ic.line([P(40, -80), P(92, -86), P(144, -42)], max(3, int(5 * k)), (230, 214, 186, 150) if iron else (196, 160, 112, 150))
    timber(ic, P(96, -20), P(106, -132), 14 * k, lw, dw)  # standard
    timber(ic, P(-60, -154), P(300, -104), 24 * k, lw, dw)  # beam
    timber(ic, P(214, -114), P(184, -10), 11 * k, "#b4b4ae", IRON[1])  # coulter
    ic.overlay(lambda d: d.ellipse(box(292, -124, 322, -94), outline=(52, 52, 54, 255), width=max(4, int(8 * k))))
    timber(ic, P(8, -18), P(-120, -306), 22 * k, lw, dw)  # near handle
    timber(ic, P(-88, -236), P(-140, -250), 12 * k, lw, dw)  # rung between the handles
    ic.line([P(-128, -300), P(-112, -306)], max(3, int(8 * k)), (220, 186, 136, 170))  # worn grip
    return P


def manure_heap(ic: Icon, cx: float, base: float, w: float, h: float) -> Image.Image:
    """Dark heap of dung and litter: lumpy mound lit top-left, straw wisps, wet dark foot, steam, fork."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - w * 0.55, base - 16, cx + w * 0.7, base + 18)), alpha=0.5, blur=8)
    pts = [(cx - w * 0.5, base)]
    for t in np.linspace(-0.45, 0.45, 12):
        bump = rnd.uniform(-0.06, 0.06)
        pts.append((cx + t * w, base - h * (math.cos(t * math.pi * 1.05) ** 0.7 + bump)))
    pts.append((cx + w * 0.5, base))
    m = ic.poly_mask(pts)
    ic.fill(m, "#7e5a36", "#24160a", radial=(cx - w * 0.3, base - h, w * 1.0), noise=0.4, chroma=0.12)
    lay, d = layer()
    for _ in range(int(w * h / 500)):
        x, y = rnd.uniform(cx - w * 0.5, cx + w * 0.5), rnd.uniform(base - h, base)
        L = rnd.uniform(10, 24)
        a = rnd.uniform(0, math.pi)
        col = (214, 184, 112, 160) if rnd.random() < 0.55 else (26, 16, 8, 150)
        d.line([(x, y), (x + math.cos(a) * L, y - math.sin(a) * L * 0.5)], fill=col, width=3)
    composite(ic, lay, m)
    tint(ic, ic.mask("rectangle", (cx - w, base - h * 0.28, cx + w, base + 4)), m, (14, 8, 4), 0.35, 10)
    tint(ic, ic.mask("ellipse", (cx - w * 0.4, base - h * 1.05, cx + w * 0.05, base - h * 0.55)), m, (255, 230, 170), 0.18, 12)
    ic.outline(pts, 3, (30, 20, 10, 150))
    return m


# ---- icon helpers ------------------------------------------------------------------------------
W_LIGHT, W_DEEP = "#94cad8", "#2e6678"


def ditch(ic: Icon, pts, w0: float, w1: float, light=None, water: float = 0.3) -> Image.Image:
    """Open drain along a ground polyline (back to front), ``w0``..``w1`` wide: cut banks of wet
    earth, the far bank lit, water with a pale sky sheen and a few ripples. Returns the water mask."""
    rnd = ic.random
    P = np.array(pts, float)
    n = len(P)
    ws = np.linspace(w0, w1, n)
    d = np.gradient(P, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], axis=1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    outer = [tuple(p + q * w / 2) for p, q, w in zip(P, nrm, ws)] + [tuple(p - q * w / 2) for p, q, w in zip(P[::-1], nrm[::-1], ws[::-1])]
    inner = [tuple(p + q * w * water) for p, q, w in zip(P, nrm, ws)] + [tuple(p - q * w * water) for p, q, w in zip(P[::-1], nrm[::-1], ws[::-1])]
    om = ic.poly_mask(outer)
    ys = [p[1] for p in outer]
    ic.fill(om, "#5a442e", "#2e2016", (min(ys), max(ys)), noise=0.35)
    # the bank facing the light
    lit = [tuple(p + q * w / 2) for p, q, w in zip(P, nrm, ws)] + [tuple(p + q * w * 0.28) for p, q, w in zip(P[::-1], nrm[::-1], ws[::-1])]
    tint(ic, ic.poly_mask(lit), om, (220, 190, 140), 0.25, 3)
    wm = ic.poly_mask(inner)
    ic.fill(wm, light or W_LIGHT, W_DEEP, (min(ys) - 60, max(ys) + 40), noise=0.08, chroma=0.06)
    lay, dr = layer()
    for _ in range(int(len(P) * 2)):
        i = rnd.randrange(n - 1)
        t = rnd.random()
        p = P[i] + (P[i + 1] - P[i]) * t
        w = ws[i] * 0.25
        L = max(8.0, w * rnd.uniform(0.8, 1.6))
        dr.line([(p[0] - L / 2, p[1]), (p[0] + L / 2, p[1])], fill=(230, 244, 246, 150), width=4)
    composite(ic, lay, wm)
    tint(ic, ic.poly_mask([tuple(p - q * w * water) for p, q, w in zip(P, nrm, ws)] +
                          [tuple(p - q * w * 0.1) for p, q, w in zip(P[::-1], nrm[::-1], ws[::-1])]), wm, (10, 24, 30), 0.35, 3)
    return wm


def beds(ic: Icon, F: Field, u0: float, u1: float, v0: float, v1: float) -> None:
    """Raised cultivation bed: crop rows of uneven plants bowing over the crown of the bed, the crown
    lit, the flanks falling off into a dark, damp edge along the ditches."""
    m = greens(ic, F, v0, v1, u0, u1, colors=("#74983e", "#34501c"), r=13, soil=("#5e4630", "#34241a"),
               curve=0.012)
    for uu, a in ((u0, 0.4), (u1, 0.5)):
        edge = ic.poly_mask(F.band(v0, v1, max(u0, uu - 0.035), min(u1, uu + 0.035)))
        tint(ic, edge, m, (14, 10, 4), a, 8)
        wet = ic.poly_mask(F.band(v0, v1, max(u0, uu - 0.012), min(u1, uu + 0.012)))
        tint(ic, wet, m, (18, 22, 20), 0.55, 3)  # the damp foot of the bank
    crown = ic.poly_mask(F.band(v0, v1, u0 + (u1 - u0) * 0.35, u0 + (u1 - u0) * 0.6))
    tint(ic, crown, m, (255, 240, 190), 0.12, 14)


def willow(ic: Icon, x: float, base: float, h: float, r: float) -> None:
    """Pollard willow: a short, fat, gnarled trunk with a knobbly head, and on it a dense rounded crown
    of thin upright shoots in grey-green. One closed silhouette."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (x - r * 0.5, base - 12, x + r * 0.9, base + 16)), alpha=0.5, blur=8)
    tw = r * 0.42  # half width of the trunk
    hy = base - h  # top of the head
    trunk = [(x - tw * 1.25, base + 4), (x - tw * 0.95, base - h * 0.2), (x - tw * 1.05, base - h * 0.5),
             (x - tw * 0.9, base - h * 0.75), (x - tw * 1.2, hy + 10), (x + tw * 1.2, hy + 6),
             (x + tw * 0.95, base - h * 0.72), (x + tw * 1.05, base - h * 0.45), (x + tw * 0.9, base - h * 0.2),
             (x + tw * 1.3, base + 4)]
    tm = ic.poly_mask(trunk)
    ic.fill(tm, "#8a7e68", "#2e2a24", (x - tw * 1.2, x + tw * 1.2), vertical=False, noise=0.34, chroma=0.1)
    lay, d = layer()
    for _ in range(12):  # deep furrows in the bark, twisting a little
        x0 = x + rnd.uniform(-tw, tw)
        y0 = rnd.uniform(hy + 20, base - 10)
        d.line([(x0, y0), (x0 + rnd.uniform(-8, 8), y0 + rnd.uniform(20, 50))], fill=(24, 20, 14, 150), width=4)
        d.line([(x0 - 4, y0), (x0 - 4 + rnd.uniform(-6, 6), y0 + rnd.uniform(14, 36))], fill=(190, 178, 150, 70), width=2)
    composite(ic, lay, tm)
    tint(ic, ic.mask("rectangle", (x + tw * 0.2, hy, x + tw * 2, base + 10)), tm, (10, 8, 4), 0.35, 10)
    ic.fill(ic.mask("ellipse", (x - tw * 1.15, hy - tw * 0.5, x + tw * 1.15, hy + tw * 0.5)), "#6e6452", "#2e2a22",
            (hy - tw * 0.5, hy + tw * 0.5), noise=0.3)  # the swollen head
    # the crown of shoots: rounded, a little taller than wide, ragged upright top edge
    cx, cy = x, hy - r * 0.5
    rx, ry = r * 0.82, r * 0.64
    pts = []
    for a in np.linspace(0, 2 * math.pi, 64, endpoint=False):
        k = 1.0
        if math.sin(a) < -0.1:  # upper half: tufts of shoots make small irregular points
            k = rnd.uniform(0.95, 1.07)
        px, py = cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k
        if math.sin(a) > 0.3:  # the base narrows into the head
            px = cx + (px - cx) * (1 - 0.2 * math.sin(a))
        pts.append((px, py))
    cm = ic.poly_mask(pts)
    ic.fill(cm, "#b8c496", "#3a4630", radial=(cx - rx * 0.5, cy - ry * 0.7, r * 1.7), noise=0.26, chroma=0.1)
    lay, d = layer()
    for _ in range(int(r * 4.5)):  # thin upright shoots with narrow leaves, fanning slightly
        px = rnd.uniform(cx - rx, cx + rx)
        py = rnd.uniform(cy - ry * 1.05, cy + ry * 0.9)
        fan = (px - cx) / rx * 0.35
        L = rnd.uniform(16, 32)
        lit = px < cx + rx * 0.1 and py < cy + ry * 0.2
        col = (218, 226, 186, 130) if lit and rnd.random() < 0.7 else (34, 44, 26, 130)
        d.line([(px, py), (px + math.sin(fan) * L, py - math.cos(fan) * L)], fill=col, width=3)
    for _ in range(8):  # a few bare withies showing through
        px = rnd.uniform(cx - rx * 0.6, cx + rx * 0.6)
        d.line([(x + (px - x) * 0.2, hy + 4), (px, cy - ry * rnd.uniform(0.2, 0.8))], fill=(110, 86, 54, 150), width=4)
    composite(ic, lay, cm)
    tint(ic, ic.mask("ellipse", (cx - rx * 0.4, cy - ry * 0.1, cx + rx * 1.4, cy + ry * 1.3)), cm, (8, 14, 6), 0.35, 18)
    # the knobbly head where the shoots spring from, over the foot of the crown
    for dx, dy, kr in ((-0.85, 0.2, 0.36), (0.8, 0.15, 0.34), (-0.2, 0.3, 0.3)):
        bx, by = x + dx * tw, hy + dy * tw
        rr = tw * kr
        ic.fill(ic.poly_mask(ic.jitter(bx, by, rr, rr * 0.8, 10, 0.12)), "#847862", "#2e2a22",
                radial=(bx - rr * 0.4, by - rr * 0.5, rr * 1.8), noise=0.25)


def falling_water(ic: Icon, x0: float, x1: float, y0: float, y1: float) -> None:
    """Sheet of water tipping over a lip at y0 and falling to y1, streaked, with foam at the foot."""
    rnd = ic.random
    lay, d = layer()
    ic.fill(ic.poly_mask([(x0, y0), (x1, y0), (x1 + 8, y1), (x0 - 8, y1)]), "#a8d4e0", "#6aa6b8", (y0, y1), noise=0.06)
    for x in np.arange(x0 + 4, x1, 9):
        d.line([(x, y0 + 2), (x + rnd.uniform(-3, 3), y1)], fill=(236, 248, 250, rnd.randint(110, 200)), width=4)
    d.line([(x0, y0 + 3), (x1, y0 + 3)], fill=(255, 255, 255, 220), width=6)
    d.ellipse((x0 - 40, y1 - 14, x1 + 40, y1 + 12), fill=(226, 240, 244, 240))  # one body of foam, no gaps
    for _ in range(18):
        r = rnd.uniform(8, 16)
        sx, sy = rnd.uniform(x0 - 30, x1 + 30), y1 + rnd.uniform(-12, 10)
        d.ellipse((sx - r * 1.4, sy - r * 0.6, sx + r * 1.4, sy + r * 0.6), fill=(236, 246, 248, 225))
    ic.image.alpha_composite(lay)


def sluice(ic: Icon, x0: float, x1: float, sill: float, top: float) -> None:
    """Timber sluice: two posts with a head beam, a guide rack and the gate board raised on it."""
    for x in (x0, x1):
        timber(ic, (x, sill + 20), (x, top), 26, "#8a6a48", "#44301e")
    timber(ic, (x0 - 20, top + 14), (x1 + 20, top + 14), 22, "#9a7650", "#4e3824")
    board = [(x0 + 14, sill - 70), (x1 - 14, sill - 70), (x1 - 14, top + 50), (x0 + 14, top + 50)]
    planks(ic, board)
    timber(ic, ((x0 + x1) / 2, top + 60), ((x0 + x1) / 2, top - 40), 12, "#6f6860", "#3e3a36")  # rack stem
    ic.ellipse(((x0 + x1) / 2 - 18, top - 58, (x0 + x1) / 2 + 18, top - 24), "#7a7068", "#403a36", edge=4)
    ic.shade(ic.mask("rectangle", (x0, sill - 70, x1, sill - 40)), alpha=0.4, blur=6)


def planks(ic: Icon, pts, c1="#9a7650", c2="#4e3824", board: float = 22) -> Image.Image:
    """Board panel: vertical boards with per-board tone and soft joints; returns the mask."""
    m = ic.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.2)
    R = ic.random
    lay, d = layer()
    v = min(xs)
    while v < max(xs):
        bw = board * R.uniform(0.8, 1.2)
        t = R.uniform(-1, 1)
        d.rectangle((v, min(ys), v + bw, max(ys)), fill=(255, 225, 180, int(28 * t)) if t > 0 else (20, 12, 6, int(-40 * t)))
        d.line([(v, min(ys)), (v, max(ys))], fill=(35, 22, 12, 130), width=3)
        v += bw
    composite(ic, lay, m)
    ic.outline(pts, 3, (40, 26, 16, 170))
    return m


def spade(ic: Icon, x: float, y: float, k: float = 1.0) -> None:
    """Spade stuck upright in the spoil at (x, y): iron-shod blade, long handle with a T grip."""
    timber(ic, (x, y - 30 * k), (x - 22 * k, y - 230 * k), 12 * k, "#b88c5a", "#5e4028")
    timber(ic, (x - 38 * k, y - 232 * k), (x - 6 * k, y - 228 * k), 10 * k, "#b88c5a", "#5e4028")
    blade = [(x - 22 * k, y - 36 * k), (x + 22 * k, y - 34 * k), (x + 18 * k, y + 16 * k), (x - 18 * k, y + 14 * k)]
    ic.poly(blade, "#9a7a54", "#5a4028", vertical=False, edge=3)
    ic.line([(x - 18 * k, y + 12 * k), (x + 18 * k, y + 14 * k)], int(7 * k), (120, 122, 124))


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.8
    ic.grade["mute"] = 0.84
    F = Field((170, 400), (860, 388), (30, 850), (995, 862))
    slab_face(ic, F, 70)

    # pollard willows standing along the back ditch
    for u, h, r in ((0.1, 140, 132), (0.64, 104, 104)):
        x, y = F.P(u, 0.0)
        willow(ic, x, y + 10, h, r)

    # raised beds between the drains, the drains, then the collector ditch across the front
    DU = (0.25, 0.5, 0.75)
    VC = 0.84
    edges = [0.0] + [u for u in DU for _ in (0, 1)] + [1.0]
    for k in range(4):
        beds(ic, F, edges[2 * k] + (0.03 if k else 0), edges[2 * k + 1] - (0.03 if k < 3 else 0), 0.0, VC - 0.04)
    ic.fill(F.mask(ic, VC - 0.04, 1.0), "#5e4a30", "#3a2a1a", (F.P(0, VC)[1] - 20, F.P(0, 1)[1]), noise=0.35)
    for u in DU:
        ditch(ic, [F.P(u, v) for v in np.linspace(0.0, VC - 0.02, 10)], 54, 104)
    ditch(ic, [F.P(u, VC + 0.05) for u in np.linspace(0.0, 0.8, 12)] + [F.P(0.8, 0.995)], 92, 108, light="#aedbe6", water=0.36)

    # footbridge of planks over the collector
    bx, by = F.P(0.33, VC + 0.05)
    ic.shade(ic.mask("rectangle", (bx - 44, by - 10, bx + 50, by + 36)), alpha=0.4, blur=6)
    planks(ic, [(bx - 50, by - 34), (bx + 44, by - 32), (bx + 50, by + 26), (bx - 44, by + 24)], "#a88660", "#5a4028", 18)

    # the sluice where the collector leaves through the front bank, water falling down the face
    sx, sy = F.P(0.8, 1.0)
    falling_water(ic, sx - 50, sx + 50, sy + 2, sy + 104)
    sluice(ic, sx - 58, sx + 58, sy + 8, sy - 190)

    # spade and a spoil heap on the right bank
    hx, hy = F.P(0.92, 0.9)
    ic.poly(ic.jitter(hx, hy - 10, 70, 30, 10, 0.15), "#6e5436", "#3a2a1a", edge=3)
    spade(ic, hx + 10, hy - 20, 1.1)
