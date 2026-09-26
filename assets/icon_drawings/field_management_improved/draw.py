"""Improved Husbandry: hedged enclosures in a four-course rotation, a hedgerow oak, a field gate and
a wheeled plough with an iron mouldboard drilling the front field.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/field_management_improved/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/field_management_improved

Identity: the same field slab as Field Management, now divided by dark quickset hedges into four
closes (wheat, turnips, clover, fresh drills) with an oak standing in the hedge and a five-bar gate;
in the front close a heavier wheeled plough with an iron mouldboard. Tier 3 of the chain: more
structure (hedges, gate, tree) and better equipment than the open field and the wattle fold.

The family helper block is shared with the other field-management drawings (kept identical by
copying); icon helpers: ``ley``, ``hedge``, ``canopy``, ``oak``, ``wheel``, ``gate``, ``drills``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 17
REFS = ("farming_village", "fiber_crops_farm", "royal_garden", "terraces")


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
HEDGE = ("#5a7a36", "#18280e")


def ley(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, colors=LEY, flowers: float = 1.0) -> Image.Image:
    """Grass and clover ley: fresh green, short blade strokes, clover leaves and white and pink heads."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, colors[0], colors[1], (min(ys) - 40, max(ys) + 20), noise=0.3, chroma=0.12)
    lay, d = layer()
    x0, x1 = F.P(u0, v1)[0] - 10, F.P(u1, v1)[0] + 10
    n = int((x1 - x0) * (max(ys) - min(ys)) / 90)
    for _ in range(n):
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        L = rnd.uniform(8, 16) * F.scale(v)
        col = (178, 206, 110, 150) if rnd.random() < 0.5 else (34, 58, 18, 140)
        d.line([(x, y), (x + rnd.uniform(-4, 4), y - L)], fill=col, width=3)
    for _ in range(int(n * 0.12)):  # clover trefoils
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        r = 5 * F.scale(v)
        for a in (-90, 30, 150):
            cx, cy = x + math.cos(math.radians(a)) * r, y + math.sin(math.radians(a)) * r * 0.7
            d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(96, 140, 60, 200))
    for _ in range(int(n * 0.03 * flowers)):  # clover heads
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        r = rnd.uniform(4, 6) * F.scale(v)
        col = (236, 232, 214, 230) if rnd.random() < 0.4 else (214, 150, 170, 230)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    composite(ic, lay, m)
    return m


def hedge(ic: Icon, pts, h: float, r: float, colors=HEDGE) -> None:
    """Quickset hedge along a ground polyline (back to front): contact shadow, then dense clumps of
    dark foliage lit along the top edge, darkest at the foot."""
    rnd = ic.random
    P = np.array(pts, float)
    seg = np.hypot(*np.diff(P, axis=0).T)
    ends = np.cumsum(seg)
    total = ends[-1]
    ic.shade(ic.poly_mask([tuple(p + (0, -8)) for p in P] + [tuple(p + (30, 18)) for p in P[::-1]]), alpha=0.55, blur=10)
    d = 0.0
    while d <= total:
        i = min(int(np.searchsorted(ends, d)), len(seg) - 1)
        t = (d - (ends[i] - seg[i])) / seg[i]
        x, y = P[i] + (P[i + 1] - P[i]) * t
        s = 0.7 + 0.3 * (y - P[:, 1].min()) / max(1.0, float(np.ptp(P[:, 1])))
        rr = r * s * rnd.uniform(0.85, 1.15)
        hh = h * s * rnd.uniform(0.88, 1.1)
        blob = ic.poly_mask(ic.jitter(x, y - hh * 0.5, rr, hh * 0.55, 14, 0.1))
        ic.fill(blob, colors[0], colors[1], (y - hh * 1.05, y + 4), noise=0.3, chroma=0.14)
        lay, dr = layer()
        for _ in range(int(rr * hh / 80)):
            px, py = x + rnd.uniform(-rr, rr), y - hh * rnd.uniform(0.05, 1.05)
            k = rnd.uniform(3, 6)
            col = (150, 178, 92, 110) if py < y - hh * 0.6 and px < x + rr * 0.3 else (8, 16, 4, 120)
            dr.ellipse((px - k, py - k * 0.7, px + k, py + k * 0.7), fill=col)
        composite(ic, lay, blob)
        # light catching the clipped top
        tint(ic, ic.poly_mask(ic.jitter(x - rr * 0.15, y - hh * 0.92, rr * 0.8, hh * 0.18, 10, 0.12)), blob,
             (214, 230, 150), 0.4, 3)
        tint(ic, ic.mask("rectangle", (x - rr * 1.2, y - hh * 0.3, x + rr * 1.2, y + 8)), blob, (4, 8, 2), 0.35, 6)
        d += rr * 0.75


def turnips(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, rows: int = 7) -> Image.Image:
    """Turnips in rows: tufts of broad, irregular leaves of mixed greens, jittered in size and spacing,
    the purple-white shoulders of the roots showing in the soil here and there."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, "#6a4c34", "#3e2a1c", (min(ys), max(ys)), noise=0.32)
    step = (v1 - v0) / rows
    lay, d = layer()
    leaf_cols = [(108, 150, 74), (88, 132, 66), (124, 158, 70), (80, 120, 62), (102, 140, 86)]
    for i in range(rows):
        vr = v0 + step * (i + 0.5)
        s = F.scale(vr)
        width = max(1.0, abs(F.P(u1, vr)[0] - F.P(u0, vr)[0]) / (u1 - u0))
        u = u0 + rnd.uniform(0.005, 0.03)
        while u < u1 - 0.01:
            v = vr + rnd.uniform(-0.2, 0.2) * step
            x, y = F.P(u, v)
            k = s * rnd.uniform(0.7, 1.3)
            if rnd.random() < 0.3:  # root shoulder: purple top, white below
                rr = 11 * k
                d.ellipse((x - rr, y - rr * 0.6, x + rr, y + rr * 0.9), fill=(232, 222, 206, 255))
                d.pieslice((x - rr, y - rr * 0.6, x + rr, y + rr * 0.9), 180, 360, fill=(150, 70, 118, 255))
                d.ellipse((x - rr * 0.6, y - rr * 0.5, x - rr * 0.1, y - rr * 0.1), fill=(214, 150, 190, 200))
            base = leaf_cols[rnd.randrange(len(leaf_cols))]
            for j in range(rnd.randint(4, 7)):  # broad leaves splaying up and out
                a = math.radians(rnd.uniform(-160, -20))
                L = rnd.uniform(24, 38) * k
                W = L * rnd.uniform(0.5, 0.7)
                g = rnd.uniform(0.85, 1.15)
                col = tuple(int(min(255, c * g)) for c in base)
                half = [(L * t, W / 2 * math.sin(math.pi * t ** 0.8) * rnd.uniform(0.85, 1.1)) for t in np.linspace(0, 1, 9)]
                pts = ic.rotate(half + [(q[0], -q[1]) for q in half[::-1]], (x, y - 4 * k), math.degrees(a))
                d.polygon(pts, fill=col + (255,))
                lit = math.cos(a) < 0.2
                tip = ic.rotate([(L * 0.2, 0), (L * 0.85, 0)], (x, y - 4 * k), math.degrees(a))
                d.line(tip, fill=(196, 214, 150, 140) if lit else (30, 50, 22, 140), width=max(2, int(3 * k)))
                if not lit:
                    shadow = ic.rotate(half[2:] + [(q[0], 0) for q in half[::-1][:-2]], (x, y - 4 * k), math.degrees(a))
                    d.polygon(shadow, fill=(20, 36, 14, 90))
            u += 30 * k * rnd.uniform(0.8, 1.3) / width
    composite(ic, lay, union(m, F.mask(ic, max(0, v0 - 0.04), v0 + 0.02, u0, u1)))
    return m


def cow(ic: Icon, cx: float, base: float, s: float = 1.0, facing: int = 1) -> None:
    """Small red-brown cow grazing side-on: cast shadow, legs, barrel body lit on the back, head down."""
    rnd = ic.random
    w, h = 170 * s, 74 * s
    top = base - 44 * s - h
    ic.shade(ic.mask("ellipse", (cx - w * 0.5, base - 12 * s, cx + w * 0.72, base + 14 * s)), alpha=0.5, blur=8 * s)
    for dx, far in ((-0.36, True), (-0.26, False), (0.26, True), (0.36, False)):
        x = cx + dx * w * facing
        ic.line([(x, top + h * 0.6), (x + rnd.uniform(-2, 2), base - 3 * s)], int(15 * s), (52, 30, 18) if far else (104, 62, 36))
        ic.line([(x - 5 * s, base - 3 * s), (x + 6 * s, base - 3 * s)], int(6 * s), (24, 16, 10))
    body = [(cx - w * 0.5, top + h * 0.2), (cx - w * 0.3, top), (cx + w * 0.34, top + 4 * s), (cx + w * 0.5, top + h * 0.2),
            (cx + w * 0.48, top + h * 0.85), (cx + w * 0.2, top + h), (cx - w * 0.3, top + h * 0.98), (cx - w * 0.5, top + h * 0.8)]
    body = [(cx + (x - cx) * facing, y) for x, y in body]
    bm = ic.poly_mask(body)
    ic.fill(bm, "#a2643a", "#3e2214", (top, top + h), noise=0.2)
    tint(ic, ic.mask("ellipse", (cx - w * 0.45, top - h * 0.2, cx + w * 0.3, top + h * 0.35)), bm, (255, 226, 180), 0.3, 8)
    tint(ic, ic.mask("ellipse", (cx - w * 0.05, top + h * 0.45, cx + w * 0.22, top + h * 0.95)), bm, (230, 214, 190), 0.3, 6)
    tint(ic, ic.mask("rectangle", (cx - w, top + h * 0.7, cx + w, top + h * 1.1)), bm, (20, 10, 4), 0.35, 6)
    # head down to the grass
    hx, hy = cx + facing * w * 0.46, top + h * 0.3
    head = [(0, -12 * s), (58 * s, -2 * s), (66 * s, 14 * s), (54 * s, 22 * s), (0, 16 * s)]
    head = ic.rotate(head, (hx, hy), 58 if facing > 0 else 180 - 58)
    ic.poly(head, "#8e5432", "#34200f", edge=0)
    horn = ic.rotate([(4 * s, -12 * s), (-4 * s, -26 * s), (10 * s, -14 * s)], (hx, hy), 58 if facing > 0 else 180 - 58)
    ic.poly(horn, "#e8dcc0", "#8a7c60", edge=0)
    ic.line([(cx - facing * w * 0.5, top + h * 0.22), (cx - facing * w * 0.56, top + h * 0.8)], max(3, int(5 * s)), (60, 34, 20))


def crown(ic: Icon, cx: float, cy: float, rx: float, ry: float, light="#8aa64c", dark="#1a2a12", n: int = 14,
          clusters: int = 9) -> Image.Image:
    """Broadleaf crown built from overlapping lobes, back to front: each lobe lit on its upper left with
    a dark underside and a soft shadow cast on the lobes behind; small leaf clusters break the outline."""
    R = ic.random
    mid = mix(light, dark, 0.5)
    lobes = []
    for _ in range(n):
        a = R.uniform(0, 2 * math.pi)
        dd = math.sqrt(R.uniform(0, 1)) * 0.52
        lobes.append((cx + math.cos(a) * rx * dd, cy + math.sin(a) * ry * dd, min(rx, ry) * R.uniform(0.44, 0.58)))
    for k in range(clusters):  # small clusters around the rim, mostly on the top and sides
        a = math.pi * (0.95 + 1.1 * k / max(clusters - 1, 1)) + R.uniform(-0.12, 0.12)
        lobes.append((cx + math.cos(a) * rx * 0.74, cy + math.sin(a) * ry * 0.72, min(rx, ry) * R.uniform(0.27, 0.34)))
    lobes.sort(key=lambda l: l[1] - l[2] * 0.3)
    m = ic.mask("ellipse", (cx - rx * 0.74, cy - ry * 0.7, cx + rx * 0.74, cy + ry * 0.74))  # dense core, no holes
    ic.fill(m, mid, dark, radial=(cx - rx * 0.4, cy - ry * 0.5, rx * 1.6), noise=0.3)
    for bx, by, br in lobes:
        lm = ic.poly_mask(ic.jitter(bx, by, br, br * 0.84, 18, 0.07))
        ic.shade(ic.mask("ellipse", (bx - br * 0.9, by - br * 0.5, bx + br * 1.1, by + br * 1.0)), (6, 12, 4), 0.35,
                 blur=br * 0.25)  # the lobe shades what lies behind it
        t = float(np.clip(0.5 + 0.55 * (by - cy) / ry + 0.3 * (bx - cx) / rx, 0, 1))
        c1, c2 = mix(light, mid, t * 0.8), mix(mid, dark, 0.35 + t * 0.65)
        ic.fill(lm, c1, c2, radial=(bx - br * 0.45, by - br * 0.55, br * 1.9), noise=0.26, chroma=0.14)

        def dabs(d, bx=bx, by=by, br=br):  # leaf texture: pale on the lit side, dark below
            for _ in range(int(br * br / 40)):
                x, y = R.uniform(bx - br, bx + br), R.uniform(by - br, by + br)
                v = (y - by) / br + (x - bx) / br * 0.5
                k = R.uniform(3, 6)
                col = (190, 208, 120, 90) if R.random() < 0.45 - 0.5 * v else (14, 24, 8, 90)
                d.ellipse((x - k, y - k * 0.6, x + k, y + k * 0.6), fill=col)

        ic.overlay(dabs, lm)
        tint(ic, ic.mask("ellipse", (bx - br * 0.8, by + br * 0.2, bx + br * 1.1, by + br * 1.1)), lm, (6, 12, 4), 0.35, br * 0.2)
        m = union(m, lm)
    tint(ic, ic.mask("ellipse", (cx - rx * 1.2, cy + ry * 0.2, cx + rx * 1.3, cy + ry * 1.4)), m, (6, 14, 4), 0.3, 18)
    return m


def oak(ic: Icon, x: float, base: float, h: float, r: float) -> None:
    """Hedgerow oak: stout trunk with two limbs, a broad crown of lit and shaded lobes."""
    ic.shade(ic.mask("ellipse", (x - r * 0.6, base - 14, x + r * 0.9, base + 16)), alpha=0.45, blur=10)
    timber(ic, (x, base), (x + 4, base - h * 0.6), max(18, r * 0.2), "#6e5a44", "#342618")
    timber(ic, (x + 3, base - h * 0.5), (x - r * 0.45, base - h * 0.8), max(10, r * 0.1), "#6e5a44", "#342618")
    timber(ic, (x + 4, base - h * 0.52), (x + r * 0.5, base - h * 0.78), max(9, r * 0.09), "#6e5a44", "#342618")
    crown(ic, x, base - h * 0.84, r, r * 0.74)


def wheel(ic: Icon, cx: float, cy: float, r: float, tone: float = 1.0) -> None:
    """Spoked cart wheel side-on: iron tyre, wooden felloes, spokes, hub; ``tone`` < 1 for the far wheel."""
    def c(col):
        return tuple(int(v * tone) for v in rgb(col))

    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c("#2e2e30") + (255,), width=int(r * 0.12)))
    ic.overlay(lambda d: d.ellipse((cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9),
                                   outline=c("#8a6440") + (255,), width=int(r * 0.14)))
    for k in range(10):
        a = math.radians(k * 36 + 8)
        ic.line([(cx + math.cos(a) * r * 0.16, cy + math.sin(a) * r * 0.16),
                 (cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82)], max(4, int(r * 0.07)), c("#9a7248"))
    ic.ellipse((cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2), c("#a07a50"), c("#4a3420"), edge=3)
    ic.overlay(lambda d: d.arc((cx - r * 0.95, cy - r * 0.95, cx + r * 0.95, cy + r * 0.95), 190, 280,
                               fill=(255, 236, 200, 90), width=4))


def gate(ic: Icon, p0, p1, h: float) -> None:
    """Five-bar field gate between two posts standing at ground points p0 and p1, with a brace."""
    (x0, y0), (x1, y1) = p0, p1
    for k in range(5):
        f = 0.12 + 0.2 * k
        timber(ic, (x0, y0 - h * f), (x1, y1 - h * f), 10, "#b89468", "#6a4c30")
    timber(ic, (x0, y0 - h * 0.1), (x1, y1 - h * 0.9), 9, "#b89468", "#6a4c30")
    for x, y in ((x0, y0), (x1, y1)):
        timber(ic, (x, y + 6), (x, y - h - 18), 20, "#8a6a48", "#44301e")


def drills(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, n: int = 7) -> Image.Image:
    """Seed drilled in straight rows: fine ridges with a line of fresh green shoots along each crest."""
    rnd = ic.random
    m = furrows(ic, F, v0, v1, u0, u1, n=n)
    lay, d = layer()
    for k in range(n):
        v = v0 + (v1 - v0) * (k + 0.45) / n
        s = F.scale(v)
        u = u0 + 0.02
        while u < u1 - 0.01:
            x, y = F.P(u, v)
            hh = rnd.uniform(9, 14) * s
            d.line([(x, y), (x - 5 * s, y - hh)], fill=(126, 170, 70, 230), width=int(4 * s) + 1)
            d.line([(x, y), (x + 5 * s, y - hh * 0.9)], fill=(84, 124, 46, 230), width=int(4 * s) + 1)
            u += rnd.uniform(0.018, 0.026)
    composite(ic, lay, union(m, F.mask(ic, max(0.0, v0 - 0.03), v1, u0, u1)))
    return m


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.84
    ic.grade["mute"] = 0.8
    F = Field((170, 370), (860, 358), (30, 890), (995, 902))
    slab_face(ic, F, 70)
    UH, VH = 0.5, 0.44  # the hedges' lines
    # four closes: wheat | turnips (back), clover ley | fresh drills (front)
    grain(ic, F, 0.0, VH, 0.0, UH, h=60)
    turnips(ic, F, 0.0, VH, UH, 1.0, rows=7)
    lm = ley(ic, F, VH, 1.0, 0.0, UH)
    for _ in range(9):  # the clover grows in patches, some grazed short
        x, y = F.P(rnd.uniform(0.02, UH - 0.02), rnd.uniform(VH + 0.05, 0.98))
        r = rnd.uniform(40, 80)
        light = rnd.random() < 0.5
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.4, x + r, y + r * 0.4)), lm,
             (220, 236, 150) if light else (20, 40, 10), 0.18 if light else 0.25, 12)

    def blooms(d):
        for _ in range(8):
            cx, cy = F.P(rnd.uniform(0.04, UH - 0.05), rnd.uniform(VH + 0.08, 0.96))
            pink = rnd.random() < 0.55
            for _ in range(rnd.randint(5, 9)):
                x, y = cx + rnd.gauss(0, 16), cy + rnd.gauss(0, 7)
                r = rnd.uniform(5, 7)
                col = (222, 144, 170, 235) if pink else (240, 236, 220, 235)
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
                d.ellipse((x - r * 0.7, y - r * 0.8, x, y - r * 0.1), fill=(255, 240, 244, 150))

    ic.overlay(blooms, lm)
    drills(ic, F, VH, 1.0, UH, 1.0, n=6)

    # hedges, back to front, with an oak standing at the back corner
    ox, oy = F.P(0.035, 0.0)
    oak(ic, ox, oy + 6, 190, 138)
    hedge(ic, [F.P(UH, v) for v in np.linspace(0.0, VH - 0.02, 6)], 74, 38)
    # a small cow grazing the clover close
    cx, cy = F.P(0.24, 0.74)
    cow(ic, cx, cy, 0.78, facing=1)
    # the cross hedge, broken by a five-bar gate into the clover close
    G0, G1 = 0.06, 0.22
    hedge(ic, [F.P(u, VH) for u in np.linspace(0.0, G0 - 0.02, 3)], 84, 42)
    hedge(ic, [F.P(u, VH) for u in np.linspace(G1 + 0.02, 1.0, 10)], 84, 42)
    gate(ic, F.P(G0, VH), F.P(G1, VH), 70)
    hedge(ic, [F.P(UH, v) for v in np.linspace(VH + 0.02, 1.0, 6)], 90, 44)

    # wheeled plough with a cast-iron mouldboard in the drilled close, running along the rows
    px, py = F.P(0.64, 0.9)
    k, ang = 0.84, 12
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def P(a, b):
        return (px + a * k * ca, py + b * k - a * k * sa)

    wheel(ic, *P(268, -58), 64 * k, tone=0.62)
    plough(ic, px, py, k, iron=True, angle=ang)
    wheel(ic, *P(300, -70), 76 * k)
