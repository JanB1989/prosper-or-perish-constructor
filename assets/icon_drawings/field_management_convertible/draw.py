"""Convertible Husbandry (up-and-down husbandry): long strips of grain alternating with grass and
clover leys, sheep penned in a wattle fold on the ley, a thatched field shelter at the back.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/field_management_convertible/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/field_management_convertible

Identity: the same field slab as Field Management, but striped front to back in gold grain and
bright green ley, with white sheep inside a hurdle fold (the stock manure the ley where it lies) and
a small thatched shelter. Tier 2 of the field-management chain.

The family helper block is shared with the other field-management drawings (kept identical by
copying); icon helpers: ``ley``, ``hurdle``, ``sheep``, ``thatch``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 5
REFS = ("sheep_farms", "farming_village", "terraces", "fiber_crops_farm")


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
LEY = ("#7a9a44", "#3e5a24")


def ley(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, colors=LEY, flowers: float = 1.0,
        grazed: bool = False) -> Image.Image:
    """Grass and clover ley: fresh green, short blade strokes, clover leaves and a few white and pink heads."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, colors[0], colors[1], (min(ys) - 40, max(ys) + 20), noise=0.3, chroma=0.12)
    lay, d = layer()
    x0, x1 = F.P(u0, v1)[0] - 10, F.P(u1, v1)[0] + 10
    n = int((x1 - x0) * (max(ys) - min(ys)) / (90 if not grazed else 160))
    for _ in range(n):
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        s = F.scale(v)
        L = rnd.uniform(8, 16) * s
        lit = rnd.random() < 0.5
        col = (178, 206, 110, 150) if lit else (34, 58, 18, 140)
        d.line([(x, y), (x + rnd.uniform(-4, 4), y - L)], fill=col, width=3)
    for _ in range(int(n * 0.12)):  # clover trefoils
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        r = 5 * F.scale(v)
        for a in (-90, 30, 150):
            cx, cy = x + math.cos(math.radians(a)) * r, y + math.sin(math.radians(a)) * r * 0.7
            d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(96, 140, 60, 200))
    for _ in range(int(n * 0.025 * flowers)):  # clover heads
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        r = rnd.uniform(4, 6) * F.scale(v)
        col = (236, 232, 214, 230) if rnd.random() < 0.6 else (214, 150, 170, 230)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    composite(ic, lay, m)
    if grazed:  # trodden and dunged inside the fold
        for _ in range(26):
            u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
            x, y = F.P(u, v)
            r = rnd.uniform(10, 26)
            tint(ic, ic.mask("ellipse", (x - r, y - r * 0.5, x + r, y + r * 0.5)), m, (60, 44, 20), 0.35, 6)
    return m


def hurdle(ic: Icon, p0, p1, h: float, shade: float = 0.0) -> None:
    """Wattle hurdle standing on the ground between p0 and p1: stakes, woven withies, ragged top."""
    rnd = ic.random
    (x0, y0), (x1, y1) = p0, p1
    pts = [(x0, y0), (x1, y1), (x1, y1 - h), (x0, y0 - h)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#9a7a4e", "#4e3822", (min(y0, y1) - h, max(y0, y1)), noise=0.3, chroma=0.1)
    L = math.hypot(x1 - x0, y1 - y0)
    lay, d = layer()
    rows = int(h / 11)
    for r in range(rows):
        f = (r + 0.5) / rows
        k = 0
        t = 0.0
        while t < 1:
            t1 = min(1.0, t + rnd.uniform(40, 60) / L)
            a = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - h * f)
            b = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1 - h * f)
            lit = (r + k) % 2 == 0
            d.line([a, b], fill=(214, 180, 128, 150) if lit else (40, 26, 14, 150), width=6)
            d.line([(a[0], a[1] + 5), (b[0], b[1] + 5)], fill=(24, 14, 6, 110), width=3)
            t, k = t1, k + 1
    composite(ic, lay, m)
    if shade:
        tint(ic, m, None, (10, 6, 2), shade, 0)
    ic.shade(ic.poly_mask([(x0, y0 - 12), (x1, y1 - 12), (x1, y1 + 4), (x0, y0 + 4)]), alpha=0.3, blur=6)
    n = max(2, int(L / 70))
    for i in range(n + 1):
        t = i / n
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        timber(ic, (x, y + 6), (x + rnd.uniform(-3, 3), y - h - rnd.uniform(8, 20)), 11, "#8a6640", "#46301c")
    ic.outline(pts, 3, (40, 26, 14, 140))


def sheep(ic: Icon, cx: float, base: float, s: float = 1.0, facing: int = 1, grazing: bool = False,
          front: bool = False, wool=("#f6eedc", "#7a7262")) -> None:
    """Sheep: soft cast shadow to the lower right, short legs with hooves, a fleece lit on top and
    darker underneath, a brown face (side-on, down in the grass when ``grazing``, or turned to the
    viewer when ``front``)."""
    rnd = ic.random
    w, h = 150 * s, 84 * s
    by = base - 30 * s - h / 2
    ic.shade(ic.mask("ellipse", (cx - w * 0.5, base - 12 * s, cx + w * 0.75, base + 14 * s)), alpha=0.5, blur=8 * s)
    for dx in (-0.3, -0.16, 0.2, 0.33):  # legs, the far pair darker
        far = dx in (-0.16, 0.33)
        x = cx + dx * w * facing
        ic.line([(x, by + h * 0.25), (x + rnd.uniform(-2, 2), base - 3 * s)], int(12 * s), (44, 36, 30) if far else (92, 78, 64))
        ic.line([(x - 5 * s, base - 3 * s), (x + 6 * s, base - 3 * s)], int(6 * s), (26, 20, 16))
    m = Image.new("L", (SIZE, SIZE), 0)
    for _ in range(11):
        a = rnd.uniform(0, 2 * math.pi)
        rx, ry = w * 0.5 * rnd.uniform(0.5, 0.8), h * 0.5 * rnd.uniform(0.5, 0.8)
        bx, by2 = cx + math.cos(a) * (w * 0.5 - rx), by + math.sin(a) * (h * 0.5 - ry)
        m = union(m, ic.poly_mask(ic.jitter(bx, by2, rx, ry, 16, 0.08)))
    ic.fill(m, wool[0], wool[1], (by - h * 0.45, by + h * 0.6), noise=0.14, chroma=0.05)
    lay, d = layer()
    for _ in range(int(34 * s)):  # curls
        x, y = rnd.uniform(cx - w / 2, cx + w / 2), rnd.uniform(by - h / 2, by + h / 2)
        r = rnd.uniform(5, 9) * s
        d.arc((x - r, y - r, x + r, y + r), 200, 340, fill=(96, 88, 72, 90), width=3)
        d.arc((x - r, y - r - 3, x + r, y + r - 3), 200, 300, fill=(255, 252, 240, 110), width=2)
    composite(ic, lay, m)
    tint(ic, ic.mask("ellipse", (cx - w * 0.45, by - h * 0.6, cx + w * 0.2, by + h * 0.05)), m, (255, 250, 236), 0.4, 12 * s)
    tint(ic, ic.mask("rectangle", (cx - w, by + h * 0.18, cx + w, by + h)), m, (36, 30, 22), 0.4, 10 * s)
    face1, face2 = "#7e6a58", "#2e241c"
    if front:  # head turned to the viewer: ears out to the sides, a wool topknot
        hx, hy = cx + facing * w * 0.36, by - h * 0.02
        for sx in (-1, 1):
            ear = ic.rotate([(0, -5 * s), (22 * s, -3 * s), (26 * s, 3 * s), (0, 6 * s)], (hx + sx * 10 * s, hy - 12 * s),
                            180 + 10 if sx < 0 else -10)
            ic.poly(ear, face1, face2, edge=0)
        fm = ic.poly_mask(ic.jitter(hx, hy + 4 * s, 17 * s, 27 * s, 18, 0.04))
        ic.fill(fm, face1, face2, radial=(hx - 8 * s, hy - 12 * s, 40 * s), noise=0.12)
        tint(ic, ic.mask("ellipse", (hx - 11 * s, hy + 12 * s, hx + 11 * s, hy + 30 * s)), fm, (220, 200, 180), 0.22, 3)
        for sx in (-1, 1):
            ic.ellipse((hx + sx * 8 * s - 3 * s, hy - 4 * s, hx + sx * 8 * s + 3 * s, hy + 2 * s), (16, 12, 10), edge=0)
        ic.poly(ic.jitter(hx, hy - 20 * s, 18 * s, 10 * s, 12, 0.12), wool[0], wool[1], edge=0)
        return
    # side-on head: a rounded wedge pointing forward (down to the grass when grazing), ear behind it
    hx = cx + facing * w * 0.42
    hy = by + h * 0.05 if grazing else by - h * 0.18
    ang = 62 if grazing else 28
    deg = ang if facing > 0 else 180 - ang
    L, W = 56 * s, 32 * s
    half = [(L * t, W / 2 * math.sin(math.pi * (0.15 + 0.85 * t)) ** 0.6 * (1 - 0.45 * t)) for t in np.linspace(0, 1, 12)]
    head = ic.rotate(half + [(x, -y) for x, y in half[::-1]], (hx, hy), deg)
    ic.fill(ic.poly_mask(head), face1, face2, radial=(hx - 10 * s, hy - 14 * s, L * 1.1), noise=0.12)
    nose = ic.rotate([(L * 0.74, -W * 0.14), (L * 0.98, 0), (L * 0.74, W * 0.14)], (hx, hy), deg)
    ic.shade(ic.poly_mask(nose), (230, 210, 190), 0.25, blur=2)
    ear = ic.rotate([(4 * s, -W * 0.3), (-6 * s, -W * 1.0), (14 * s, -W * 0.45)], (hx, hy), deg)
    ic.poly(ear, "#6a5848", "#2a2019", edge=0)
    # the fleece hides where the neck joins
    ic.poly(ic.jitter(cx + facing * w * 0.36, by - h * 0.05, 18 * s, 22 * s, 12, 0.1), wool[0], "#d8d0bc", edge=0)


def thatch(ic: Icon, ridge, eave, c=("#b49a64", "#6a5430")) -> Image.Image:
    """Thatched roof plane: straw strokes down the slope, ragged courses, a cut eave with a dark lip."""
    rnd = ic.random
    pts = [tuple(p) for p in ridge] + [tuple(p) for p in eave[::-1]]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    ic.fill(m, c[0], c[1], (min(ys), max(ys)), noise=0.3, chroma=0.12)
    lay, d = layer()
    xs = [p[0] for p in pts]
    for _ in range(900):
        x, y = rnd.uniform(min(xs), max(xs)), rnd.uniform(min(ys), max(ys))
        L = rnd.uniform(12, 26)
        col = (232, 212, 150, 80) if rnd.random() < 0.55 else (60, 44, 22, 90)
        d.line([(x, y), (x + rnd.uniform(-3, 3), y + L)], fill=col, width=3)
    for f in (0.35, 0.68):
        y = min(ys) + (max(ys) - min(ys)) * f
        d.line([(min(xs), y + rnd.uniform(-3, 3)), (max(xs), y + rnd.uniform(-3, 3))], fill=(40, 28, 12, 90), width=6)
    composite(ic, lay, m)
    lip = [tuple(p) for p in eave] + [(p[0], p[1] + 20 + rnd.uniform(-2, 4)) for p in eave[::-1]]
    ic.fill(ic.poly_mask(lip), "#86683a", "#4a381c", (min(p[1] for p in eave), max(p[1] for p in eave) + 24), noise=0.35)
    ic.line([tuple(p) for p in ridge], 18, (104, 84, 50))
    ic.line([tuple(p) for p in ridge], 7, (160, 136, 88, 170))
    ic.outline(pts, 3, (40, 28, 12, 150))
    return m


def shelter(ic: Icon, sc: float, foot: float, W: float = 216, f: float = 0.84) -> None:
    """Two-bay thatched field shelter standing on the ley: soft contact shadow, dark open front, hay
    rack along the back wall, three posts, thatched roof."""
    sx0, sx1 = sc - W / 2, sc + W / 2

    def Y(o):
        return foot + o * f

    ic.shade(ic.mask("ellipse", (sx0 - 30 * f, foot - 26 * f, sx1 + 60 * f, foot + 24 * f)), alpha=0.6, blur=10)
    ic.shade(ic.mask("ellipse", (sx0 - 8, foot - 10 * f, sx1 + 16, foot + 10 * f)), alpha=0.4, blur=4)
    ic.rect((sx0 + 14 * f, Y(-130), sx1 - 14 * f, foot), "#2e241a", "#140e0a", edge=0)
    for x in np.arange(sx0 + 44 * f, sx1 - 36 * f, 18 * f):  # hay rack along the back wall
        ic.line([(x, Y(-94)), (x + 8 * f, Y(-40))], max(3, int(6 * f)), (120, 92, 58))
    ic.poly([(sx0 + 40 * f, Y(-86)), (sx0 + 80 * f, Y(-112)), (sx1 - 76 * f, Y(-114)), (sx1 - 36 * f, Y(-86))],
            "#c0a05a", "#6e5428", edge=3)
    ic.line([(sx0 + 36 * f, Y(-36)), (sx1 - 36 * f, Y(-36))], max(4, int(10 * f)), (110, 84, 52))
    # ground at the open front: trodden, a little hay
    ic.shade(ic.mask("rectangle", (sx0 + 14 * f, Y(-20), sx1 - 14 * f, foot)), (200, 170, 110), 0.25, blur=4)
    for x in (sx0 + 20 * f, (sx0 + sx1) / 2, sx1 - 20 * f):
        timber(ic, (x, foot + 4), (x, Y(-134)), 18 * f)
    ic.shade(ic.mask("rectangle", (sx0, Y(-134), sx1, Y(-80))), alpha=0.55, blur=8)
    thatch(ic, [(sx0 + 40 * f, Y(-254)), (sx1 - 40 * f, Y(-260))],
           [(sx0 - 22 * f, Y(-112)), ((sx0 + sx1) / 2, Y(-106)), (sx1 + 22 * f, Y(-116))])


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.86
    ic.grade["mute"] = 0.78
    F = Field((170, 214), (860, 202), (30, 800), (995, 812))
    slab_face(ic, F, 70)
    # long strips front to back: ley | grain | ley | grain | wide ley with the shelter
    cuts = [0.0, 0.18, 0.36, 0.52, 0.68, 1.0]
    for k in range(5):
        u0, u1 = cuts[k], cuts[k + 1]
        if k % 2:
            m = grain(ic, F, 0.0, 1.0, u0, u1, h=58, colors=("#c8963c", "#7e5420"))
            for j in range(1, 12):  # drill rows showing through the stand
                v = j / 12 + ic.random.uniform(-0.01, 0.01)
                tint(ic, F.mask(ic, v - 0.012, v + 0.006, u0, u1), m, (58, 34, 8), 0.3, 3)
            for uu, a in ((u0, 0.45), (u1, 0.35)):  # darker, trodden edges against the clover
                tint(ic, F.mask(ic, 0.0, 1.0, max(u0, uu - 0.014), min(u1, uu + 0.014)), m, (40, 26, 6), a, 5)
        else:
            ley(ic, F, 0.0, 1.0, u0, u1)
    for u in cuts[1:-1]:  # balks between strips
        ic.line([F.P(u, v) for v in np.linspace(0, 1, 12)], 8, (70, 52, 30, 150))

    # thatched field shelter standing on the wide ley, right
    sx, sy = F.P(0.8, 0.42)
    shelter(ic, sx, sy)

    # wattle fold on the ley at the front left, sheep inside
    fu0, fu1, fv0, fv1 = 0.03, 0.46, 0.5, 0.96
    ley(ic, F, fv0, fv1, fu0, fu1, grazed=True, flowers=0.3)
    hurdle(ic, F.P(fu0, fv0), F.P(fu1, fv0), 56, shade=0.15)
    hurdle(ic, F.P(fu1, fv0), F.P(fu1, fv1), 70, shade=0.3)
    for u, v, s, fa, kw in ((0.18, 0.69, 0.88, 1, {"grazing": True}), (0.375, 0.75, 0.94, -1, {"front": True}),
                            (0.145, 0.87, 1.04, 1, {"front": True}), (0.35, 0.965, 1.08, 1, {"grazing": True})):
        x, y = F.P(u, v)
        sheep(ic, x, y, s, facing=fa, **kw)
    hurdle(ic, F.P(fu0, fv0), F.P(fu0, fv1), 70)
    hurdle(ic, F.P(fu0, fv1), F.P(fu1, fv1), 76)
    # one sheep grazing free on the wide ley, well clear of the fold
    ox, oy = F.P(0.84, 0.8)
    sheep(ic, ox, oy, 1.16, facing=-1, grazing=True)
