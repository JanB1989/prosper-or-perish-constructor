"""Land Clearance: a woodland assart being opened, forest edge behind, fresh stumps with their roots,
felled trunks stacked in front and a brush pile burning with a tall plume of smoke.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/land_clearance/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/land_clearance

Identity: the same ground slab as the field-management family, but raw: dark forest standing at
the back, pale-topped stumps across grubbed earth, an axe left in one, a stack of felled trunks with
their sawn ends in front, and orange fire in a heap of brushwood sending grey smoke up the right
side. Unlike vanilla lumber mills there is no building and no sawn timber; the fire and the stumps
say "clearing for fields".

The family helper block is shared with the other field-management drawings (kept identical by
copying); icon helpers: ``rough_ground``, ``conifer``, ``canopy``, ``stump``, ``log``, ``log_end``,
``brush``, ``flame``, ``smoke``, ``axe``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SEED = 29
REFS = ("forest_village", "lumber_mill", "charcoal_maker", "farming_village")


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
BARK = ("#8a6a4a", "#35271a")
FRESH = ("#e2c48e", "#9a7042")


def rough_ground(ic: Icon, F: Field, v0: float, v1: float, u0=0.0, u1=1.0, grass: float = 1.0) -> Image.Image:
    """Grubbed woodland soil: warm humus with lighter trodden patches, clods, torn roots, stones, wood
    chips and tufts of surviving grass."""
    rnd = ic.random
    m = F.mask(ic, v0, v1, u0, u1)
    ys = [p[1] for p in F.band(v0, v1, u0, u1)]
    ic.fill(m, "#8a6440", "#4e3620", (min(ys), max(ys)), noise=0.4, chroma=0.14)
    for _ in range(10):  # warmer, drier patches and darker damp ones
        x, y = F.P(rnd.uniform(u0, u1), rnd.uniform(v0, v1))
        r = rnd.uniform(50, 110)
        warm = rnd.random() < 0.6
        tint(ic, ic.mask("ellipse", (x - r, y - r * 0.4, x + r, y + r * 0.4)), m,
             (214, 160, 96) if warm else (40, 24, 12), 0.2, 16)
    lay, d = layer()
    for _ in range(380):
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        s = F.scale(v)
        r = rnd.uniform(4, 11) * s
        d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(30, 18, 8, 130))
        d.ellipse((x - r * 0.8, y - r * 0.8, x + r * 0.3, y), fill=(170, 128, 86, 120))
    for _ in range(22):  # torn roots snaking over the ground
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        s = F.scale(v)
        a = rnd.uniform(-0.5, 0.5) + (0 if rnd.random() < 0.5 else math.pi)
        pts = [(x, y)]
        for _ in range(4):
            a += rnd.uniform(-0.5, 0.5)
            L = rnd.uniform(12, 22) * s
            x, y = x + math.cos(a) * L, y + math.sin(a) * L * 0.4
            pts.append((x, y))
        d.line(pts, fill=(52, 34, 20, 210), width=int(7 * s), joint="curve")
        d.line([(px, py - 2 * s) for px, py in pts], fill=(160, 120, 80, 150), width=max(2, int(3 * s)), joint="curve")
    for _ in range(26):  # stones
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        r = rnd.uniform(6, 13) * F.scale(v)
        d.ellipse((x - r, y - r * 0.4, x + r * 1.3, y + r * 0.7), fill=(30, 22, 14, 120))
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.5), fill=(150, 142, 128, 235))
        d.ellipse((x - r * 0.7, y - r * 0.65, x + r * 0.2, y - r * 0.05), fill=(206, 198, 180, 170))
    for _ in range(int(160 * grass)):  # grass tufts
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        s = F.scale(v)
        for _ in range(5):
            L = rnd.uniform(10, 22) * s
            d.line([(x, y), (x + rnd.uniform(-9, 9) * s, y - L)], fill=(128, 146, 60, 200) if rnd.random() < 0.6
                   else (66, 84, 30, 200), width=3)
    for _ in range(110):  # wood chips
        u, v = rnd.uniform(u0, u1), rnd.uniform(v0, v1)
        x, y = F.P(u, v)
        a = rnd.uniform(0, math.pi)
        L = rnd.uniform(6, 14)
        d.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L * 0.4)], fill=(232, 204, 150, 210), width=4)
    composite(ic, lay, m)
    return m


def conifer(ic: Icon, cx: float, base: float, h: float, w: float) -> None:
    """Spruce: stacked drooping tiers, lit on the left, darker core, bare stem foot."""
    rnd = ic.random
    timber(ic, (cx, base), (cx, base - h * 0.3), max(10, w * 0.1), "#5e4a38", "#2a2018")
    tiers = 6
    for k in range(tiers):
        t = k / (tiers - 1)
        top = base - h + h * 0.78 * t * 0.92
        bot = top + h * (0.26 + 0.06 * t)
        hw = w * (0.22 + 0.78 * t) / 2
        pts = [(cx + rnd.uniform(-4, 4), top)]
        for s in np.linspace(-1, 1, 9):
            pts.append((cx + s * hw + rnd.uniform(-6, 6), bot - (1 - abs(s)) * h * 0.05 + rnd.uniform(-5, 5)))
        m = ic.poly_mask(pts)
        ic.fill(m, "#4e6e3a", "#142410", radial=(cx - hw, top, h * 0.5), noise=0.26, chroma=0.12)
        tint(ic, ic.poly_mask([(cx, top), (cx + hw + 10, bot + 6), (cx + 4, bot + 6)]), m, (6, 14, 4), 0.35, 6)
        tint(ic, ic.mask("rectangle", (cx - hw, bot - 16, cx + hw, bot + 4)), m, (6, 12, 4), 0.35, 5)


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


def stump(ic: Icon, cx: float, base: float, r: float, h: float, roots: int = 4) -> None:
    """Fresh stump: roots spreading over the ground, bark sides lit left, pale sawn top with rings."""
    rnd = ic.random
    ic.shade(ic.mask("ellipse", (cx - r * 1.6, base - r * 0.3, cx + r * 2.2, base + r * 0.45)), alpha=0.5, blur=8)
    for k in range(roots):  # roots: tapered, crawling out and down into the soil
        side = -1 if k % 2 == 0 else 1
        a = side * rnd.uniform(0.2, 1.0)
        L = r * rnd.uniform(1.1, 1.8)
        x0, y0 = cx + side * r * rnd.uniform(0.3, 0.8), base - r * 0.1
        x1, y1 = x0 + side * L * math.cos(abs(a) * 0.6), base + r * 0.25 * rnd.uniform(0.2, 1.0)
        pts = [(x0, y0 - r * 0.35), (x1, y1 - 3), (x1, y1 + 3), (x0, y0 + r * 0.2)]
        ic.poly(pts, BARK[0], BARK[1], vertical=False, edge=3)
    top = base - h
    body = [(cx - r, top), (cx + r, top), (cx + r * 1.08, base - r * 0.1), (cx + r * 1.2, base + r * 0.12),
            (cx - r * 1.2, base + r * 0.12), (cx - r * 1.08, base - r * 0.1)]
    m = ic.poly_mask(body)
    ic.fill(m, BARK[0], BARK[1], (cx - r, cx + r), vertical=False, noise=0.3)
    lay, d = layer()
    for x in np.linspace(cx - r * 0.9, cx + r * 0.9, int(r / 6)):
        d.line([(x + rnd.uniform(-2, 2), top + 4), (x + rnd.uniform(-4, 4), base)], fill=(24, 16, 10, 120), width=3)
    composite(ic, lay, m)
    ic.outline(body, 3, (30, 20, 12, 150))
    face = (cx - r, top - r * 0.36, cx + r, top + r * 0.36)
    fm = ic.mask("ellipse", face)
    ic.fill(fm, FRESH[0], FRESH[1], radial=(cx - r * 0.5, top - r * 0.3, r * 2.2), noise=0.14)

    def rings(dr):
        for f in (0.3, 0.55, 0.8):
            dr.ellipse((cx - r * f, top - r * 0.36 * f, cx + r * f, top + r * 0.36 * f), outline=(140, 96, 54, 130), width=3)

    ic.overlay(rings, fm)
    ic.overlay(lambda dr: dr.ellipse(face, outline=(60, 40, 22, 220), width=5))


def log(ic: Icon, x0: float, x1: float, y: float, r: float, bark=BARK, cut: str = "right") -> Image.Image:
    """Log lying across the picture: bark lit on top with furrows, pale sawn end on the ``cut`` side."""
    ex = r * 0.6
    body = ic.mask("rectangle", (x0, y - r, x1, y + r))
    far = (x0 - ex, y - r, x0 + ex, y + r) if cut == "right" else (x1 - ex, y - r, x1 + ex, y + r)
    m = union(body, ic.mask("ellipse", far))
    ic.fill(m, bark[0], bark[1], (y - r * 0.9, y + r), noise=0.28, chroma=0.12)
    tint(ic, ic.mask("rectangle", (x0 - ex, y - r * 0.8, x1 + ex, y - r * 0.3)), m, (255, 226, 180), 0.24, r * 0.18)
    tint(ic, ic.mask("rectangle", (x0 - ex, y + r * 0.25, x1 + ex, y + r * 1.2)), m, (0, 0, 0), 0.35, r * 0.25)
    R = ic.random
    lay, d = layer()
    for _ in range(int((x1 - x0) * r / 260)):
        yy = y + R.uniform(-0.85, 0.85) * r
        xx = R.uniform(x0 - ex, x1)
        L = R.uniform(20, 70)
        d.line([(xx, yy), (xx + L, yy + R.uniform(-2, 2))], fill=(28, 18, 10, int(R.uniform(60, 130))), width=int(R.uniform(2, 4)))
    composite(ic, lay, m)
    if cut:
        cx = x1 if cut == "right" else x0
        log_end(ic, cx, y, r, ex)
    ic.outline([(x0, y - r), (x1, y - r)], 3, (40, 26, 16, 140))
    return m


def log_end(ic: Icon, cx: float, cy: float, r: float, ex: float) -> None:
    """Sawn log end seen from the side: a proper ellipse with a dark bark ring, pale face lit upper
    left, growth rings, a dark heart and a drying crack."""
    ic.fill(ic.mask("ellipse", (cx - ex, cy - r, cx + ex, cy + r)), "#5a4230", "#2c2016", noise=0.2)
    fb = (cx - ex * 0.84, cy - r * 0.88, cx + ex * 0.84, cy + r * 0.88)
    fm = ic.mask("ellipse", fb)
    ic.fill(fm, "#ecd09a", "#a67a48", radial=(cx - ex * 0.4, cy - r * 0.6, r * 2.0), noise=0.14)

    def rings(d):
        for f in (0.8, 0.62, 0.45, 0.28):
            b = (cx - ex * 0.84 * f, cy - r * 0.88 * f, cx + ex * 0.84 * f, cy + r * 0.88 * f)
            d.ellipse(b, outline=(128, 84, 44, 150), width=3)
        d.ellipse((cx - ex * 0.08, cy - r * 0.09, cx + ex * 0.08, cy + r * 0.09), fill=(110, 70, 36, 220))
        d.line([(cx + ex * 0.05, cy - r * 0.05), (cx + ex * 0.5, cy - r * 0.55)], fill=(70, 44, 22, 170), width=3)

    ic.overlay(rings, fm)
    tint(ic, ic.mask("rectangle", (cx, cy, cx + ex, cy + r)), fm, (40, 22, 8), 0.3, 4)


def brush(ic: Icon, cx: float, base: float, w: float, h: float) -> Image.Image:
    """Heap of lopped branches and brushwood: dark tangle of sticks, a few withered leaves, charred foot."""
    rnd = ic.random
    pts = [(cx - w / 2, base)] + [(cx + t * w, base - h * math.cos(t * math.pi) ** 0.8 * rnd.uniform(0.85, 1.1))
                                   for t in np.linspace(-0.45, 0.45, 10)] + [(cx + w / 2, base)]
    m = ic.poly_mask(pts)
    ic.fill(m, "#4a3a2a", "#1a120c", radial=(cx - w * 0.3, base - h, w), noise=0.4)
    lay, d = layer()
    for _ in range(int(w * h / 200)):
        x, y = rnd.uniform(cx - w / 2, cx + w / 2), rnd.uniform(base - h, base)
        a = rnd.uniform(-0.6, 0.6) + (0 if rnd.random() < 0.6 else math.pi / 2)
        L = rnd.uniform(30, 80)
        col = (150, 118, 84, 200) if rnd.random() < 0.4 else (30, 20, 12, 210)
        d.line([(x - math.cos(a) * L / 2, y - math.sin(a) * L / 2), (x + math.cos(a) * L / 2, y + math.sin(a) * L / 2)],
               fill=col, width=rnd.choice((3, 4, 6)))
        if rnd.random() < 0.3:
            k = rnd.uniform(5, 9)
            d.ellipse((x - k, y - k * 0.6, x + k, y + k * 0.6), fill=(128, 96, 44, 200))
    composite(ic, lay, union(m, m.filter(ImageFilter.MaxFilter(15))))
    return m


def flame(ic: Icon, cx, base, w, h, lean=0.0, outer=("#f08a2c", "#a82c10"), mid=("#ffbe50", "#e0641c"),
          inner=("#fff0b8", "#ffb040")) -> None:
    """Tongue of flame: red-orange outside, brighter tongues nested low inside it. No edge lines."""
    for (c1, c2), sw, sh in ((outer, 1.0, 1.0), (mid, 0.66, 0.74), (inner, 0.36, 0.46)):
        ts = np.linspace(0, 1, 24)
        g = np.sin(np.pi * (ts * 0.8 + 0.2))
        left = [(cx - w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        right = [(cx + w * sw / 2 * gi + lean * sh * t * t, base - h * sh * t) for t, gi in zip(ts, g)]
        ic.fill(ic.poly_mask(left + right[::-1]), c1, c2, (base, base - h * sh), noise=0.08, chroma=0.04)


def smoke(ic: Icon, puffs, colors=("#d8d4cc", "#7e7a74")) -> None:
    """Rolling smoke: puffs drawn far to near, each lit top-left and greyer underneath."""
    for x, y, r in puffs:
        ph = [ic.random.uniform(0, 2 * math.pi) for _ in range(3)]
        pts = [(x + math.cos(a) * r * k, y + math.sin(a) * r * 0.84 * k)
               for a in np.linspace(0, 2 * math.pi, 72, endpoint=False)
               for k in [1 + 0.07 * math.sin(3 * a + ph[0]) + 0.05 * math.sin(5 * a + ph[1])]]
        m = ic.poly_mask(pts)
        ic.fill(m, colors[0], colors[1], radial=(x - r * 0.45, y - r * 0.55, r * 1.7), noise=0.08, chroma=0.03)
        tint(ic, ic.mask("ellipse", (x - r * 0.2, y + r * 0.1, x + r * 1.2, y + r * 1.3)), m, (40, 36, 34), 0.22, 8)


def axe(ic: Icon, x: float, y: float, k: float = 1.0) -> None:
    """Felling axe bitten into a stump top at (x, y), helve slanting up to the right."""
    timber(ic, (x, y - 4 * k), (x + 110 * k, y - 120 * k), 13 * k, "#b88c5a", "#5e4028")
    head = [(x - 30 * k, y + 8 * k), (x + 6 * k, y - 26 * k), (x + 22 * k, y - 10 * k), (x - 4 * k, y + 22 * k)]
    ic.poly(head, "#b8bab6", "#4a4c4e", vertical=False, edge=4)


# ---- drawing -----------------------------------------------------------------------------------
def draw(ic: Icon) -> None:
    rnd = ic.random
    ic.grade["gamma"] = 0.74
    ic.grade["mute"] = 0.84
    F = Field((170, 440), (860, 428), (30, 890), (995, 902))

    # forest edge behind the clearing
    for x, h, w in ((196, 360, 150), (300, 420, 170), (560, 300, 130)):
        conifer(ic, x, F.P(0, 0)[1] + 20, h, w)
    timber(ic, (420, 470), (426, 300), 26, "#6e5a44", "#342618")
    timber(ic, (424, 350), (370, 290), 12, "#6e5a44", "#342618")
    crown(ic, 432, 250, 150, 112, light="#86a04a", dark="#1c2c14")
    conifer(ic, 250, F.P(0, 0)[1] + 40, 300, 140)

    slab_face(ic, F, 70)
    rough_ground(ic, F, 0.0, 1.0)
    # the side already grubbed and broken up: darker turned soil at the left front
    furrows(ic, F, 0.55, 1.0, 0.0, 0.4, n=4, soil=("#6e4e34", "#3a281a"))

    # the fire and its smoke, right, behind the stumps
    bx, by = F.P(0.72, 0.46)
    smoke(ic, [(bx + 160, by - 500, 64), (bx + 120, by - 430, 72), (bx + 80, by - 350, 78), (bx + 40, by - 270, 76)])
    smoke(ic, [(bx - 20, by - 170, 128), (bx + 70, by - 200, 104)], ("#8e8680", "#3a3432"))  # smoke billowing up behind the flames
    tint(ic, ic.mask("ellipse", (bx - 170, by - 150, bx + 190, by + 10)), None, (255, 120, 40), 0.22, 30)
    ic.shade(ic.mask("ellipse", (bx - 260, by - 100, bx + 240, by + 80)), (255, 150, 60), 0.25, blur=40)
    brush(ic, bx, by - 10, 280, 170)
    for dx, h, lean in ((-100, 110, -14), (-58, 180, -10), (-5, 250, 8), (52, 190, 20), (100, 120, 12)):
        flame(ic, bx + dx, by - 60, 84, h, lean)
    brush(ic, bx + 10, by + 16, 310, 70)
    # firelight on the brush, the smoke and the ground around it
    ic.shade(ic.mask("ellipse", (bx - 200, by - 60, bx + 200, by + 60)), (255, 160, 60), 0.2, blur=30)
    ic.shade(ic.mask("ellipse", (bx - 110, by - 50, bx + 120, by + 10)), (255, 200, 100), 0.3, blur=16)

    # stumps across the clearing, back to front; the axe left in one
    for u, v, r in ((0.52, 0.18, 42), (0.28, 0.32, 50), (0.58, 0.62, 56), (0.42, 0.86, 64)):
        x, y = F.P(u, v)
        stump(ic, x, y, r, r * 1.1)
    x, y = F.P(0.42, 0.86)
    axe(ic, x + 10, y - 64 * 1.1 - 4, 1.35)

    # stack of felled trunks at the front right
    lx0, lx1, ly = 620, 920, 874
    ic.shade(ic.mask("ellipse", (lx0 - 20, ly + 20, lx1 + 80, ly + 70)), alpha=0.5, blur=10)
    log(ic, lx0 + 70, lx1 - 20, ly - 96, 54, bark=("#a07448", "#402a18"))
    log(ic, lx0, lx1 - 50, ly - 12, 60, bark=("#a07448", "#402a18"))
    log(ic, lx0 + 90, lx1 + 22, ly + 10, 62, bark=("#a07448", "#402a18"))
