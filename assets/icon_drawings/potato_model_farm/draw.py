"""Potato Model Farm (potato_model_farm): straight drilled ridges running to a brick farm, a built clamp cellar.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/potato_model_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/potato_model_farm

Identity (tier 4 of the potato chain): long straight drills of leafy potatoes run in perspective
towards a planned farm: a two-storey brick farmhouse with a red tiled roof, a brick barn and a
turfed clamp cellar with a dressed stone portal; open crates of potatoes stacked at the bottom
right. Family helpers (shared by all four potato tiers): ``ell``, ``leaflets``, ``potato_plant``,
``ridge``, ``furrow_ground``, ``tubers``, ``potato_heap``, ``potato_basket``, ``hipped``,
``thatch_eave``, ``chimney``, ``spade``; ``union``, ``tint``, ``stones``, ``shingles``, ``thatch``,
``planks`` come from the Tavern, ``jute`` from the Coffee Grove. New here: ``bricks`` (after the
Victualling Yard), ``quoins``, ``drills``, ``cellar``, ``open_crate``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SOIL = ("#86643e", "#3a2a1a")
LEAF = ((94, 132, 48), (144, 180, 82), (26, 40, 12))  # potato leaflet: mid, lit, dark rim
TUBER = ((178, 114, 56), (226, 170, 102), (82, 44, 18))  # warm russet-tan: mid, lit, dark
TUBER_PALE = ((192, 138, 66), (234, 190, 116), (90, 58, 24))  # ochre
TUBER_RED = ((152, 78, 48), (198, 122, 80), (70, 30, 16))  # red-skinned russet
TIMBER = (104, 74, 48)


# ---------------------------------------------------------------- helpers (copied from the Tavern)
def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def tint(ic: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch that stays inside ``clip`` (shade blurs past mask edges otherwise)."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = ic.intersect(mask, clip)
    ic.shade(mask, color, alpha)


def stones(ic: Icon, box, base="#a39889", dark="#756c60", course: float = 38, clip: Image.Image | None = None,
           lit: int = 70, shadow: int = 130, moss: float = 0.06) -> None:
    """Rubble/ashlar wall where every block is a form: tone variation, lit top-left edge, shadowed
    bottom-right edge, no outlines."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, base, dark, (y0, y1), noise=0.2, chroma=0.04)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y = y0 + rnd(-course * 0.5, 0)
    while y < y1:
        h = course * rnd(0.8, 1.15)
        x = x0 - rnd(0, course * 1.4)
        while x < x1:
            w = course * rnd(1.2, 2.5)
            j = lambda: rnd(-3, 3)  # noqa: E731
            q = [(x + 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + 3 + j()), (x + w - 3 + j(), y + h - 3 + j()),
                 (x + 3 + j(), y + h - 3 + j())]
            t = rnd(-1, 1)
            if ic.random.random() < moss:
                d.polygon(q, fill=(96, 104, 60, int(rnd(30, 60))))
            elif t < 0:
                d.polygon(q, fill=(24, 16, 10, int(-t * 55)))
            else:
                d.polygon(q, fill=(255, 240, 215, int(t * 40)))
            d.line([q[3], q[0], q[1]], fill=(255, 244, 225, lit), width=4)
            d.line([q[1], q[2], q[3]], fill=(30, 22, 16, shadow), width=5)
            x += w
        y += h
    clipped = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clipped.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clipped)


def shingles(ic: Icon, pts, c1, c2, course: float = 32, stagger: float = 42, edge: int = 7) -> Image.Image:
    """Roof plane of overlapping tiles: per-tile tone, lit lower lip, course shadow. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, c1, c2, (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.18, chroma=0.05)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
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
        td.line([(0, yl - 4), (ic.size, yl - 4 + rnd(-3, 3))], fill=(255, 232, 205, 55), width=4)
        sd.line([(0, yl + 3), (ic.size, yl + 3 + rnd(-3, 3))], fill=255, width=9)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (18, 8, 4), 0.55, 3)
    ic.outline(pts, edge)
    return m


def thatch(ic: Icon, pts, c1, c2, course: float = 44) -> Image.Image:
    """Thatched roof plane: straw strands running down the slope, layered courses with a dark
    underside, weathered blotches. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    ic.fill(m, c1, c2, (min(ys), max(ys)), noise=0.24, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    shadow = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y = min(ys) + rnd(0, course * 0.4)
    while y < max(ys) + course:
        for _ in range(int((max(xs) - min(xs)) / 3)):
            x = rnd(min(xs), max(xs))
            ln = rnd(course * 0.4, course * 1.2)
            t = rnd(-1, 1)
            col = (255, 236, 196, int(t * 60)) if t > 0 else (30, 18, 8, int(-t * 70))
            y0 = y + rnd(-course * 0.3, course * 0.4)
            d.line([(x, y0), (x + rnd(-4, 4), y0 + ln)], fill=col, width=int(rnd(2, 4)))
        x = min(xs)
        while x < max(xs):
            seg = rnd(40, 130)
            yy = y + course + rnd(-8, 8)
            sd.line([(x, yy), (x + seg, yy + rnd(-6, 6))], fill=int(rnd(90, 200)), width=int(rnd(8, 14)))
            x += seg + rnd(0, 30)
        y += course * rnd(0.85, 1.15)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (30, 16, 6), 0.28, 7)
    for _ in range(12):
        x, yy = rnd(min(xs), max(xs)), rnd(min(ys), max(ys))
        r = rnd(30, 80)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (78, 86, 44), (90, 84, 76)])
        tint(ic, ic.mask("ellipse", (x - r * 1.3, yy - r * 0.6, x + r * 1.3, yy + r * 0.6)), m, col,
             rnd(0.08, 0.2), 18)
    return m


def planks(ic: Icon, box, c1="#8e7658", c2="#4e3e2c", board: float = 30, clip: Image.Image | None = None) -> None:
    """Vertical weathered boards: per-board tone, grain streaks, dark gap on the right of each board."""
    x0, y0, x1, y1 = box
    m = clip if clip is not None else ic.mask("rectangle", box)
    ic.fill(m, c1, c2, (y0, y1), noise=0.2, chroma=0.05)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    x = x0 - rnd(0, board)
    while x < x1:
        w = board * rnd(0.8, 1.2)
        t = rnd(-1, 1)
        d.rectangle((x, y0, x + w, y1), fill=(24, 14, 8, int(-t * 60)) if t < 0 else (255, 240, 214, int(t * 36)))
        for _ in range(3):
            gx = x + rnd(4, max(w - 4, 5))
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def jute(ic: Icon, cx: float, base: float, w: float, h: float, color) -> None:
    """Filled jute sack (from the Coffee Grove): lumpy body lit from the upper left, tied neck."""
    body = ic.jitter(cx, base - h * 0.42, w * 0.5, h * 0.44, 14, 0.06)
    dark = tuple(int(v * 0.45) for v in rgb(color))
    ic.fill(ic.poly_mask(body), color, dark, radial=(cx - w * 0.35, base - h * 0.8, w * 1.2), noise=0.3)
    ic.outline(body, 3, (40, 28, 16, 150))
    ic.poly([(cx - 10, base - h * 0.84), (cx - 16, base - h), (cx + 14, base - h * 1.02), (cx + 9, base - h * 0.84)],
            color, dark, edge=3)
    ic.line([(cx - 13, base - h * 0.86), (cx + 12, base - h * 0.86)], 5, (60, 44, 26))

    def weave(dr):
        for k in range(8):
            y = base - h * (0.15 + 0.08 * k)
            dr.line([(cx - w * 0.4, y), (cx + w * 0.4, y + 3)], fill=(50, 36, 20, 50), width=2)

    ic.overlay(weave, ic.poly_mask(body))


# ---------------------------------------------------------------- helpers (new for the potato family)
def ell(cx, cy, rx, ry, deg=0.0, n=16, wob=None):
    """Points of a rotated ellipse; ``wob`` is a list of per-point radius factors (lumpy tubers)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        f = wob[k] if wob else 1.0
        x, y = math.cos(a) * rx * f, math.sin(a) * ry * f
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def leaflets(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Small oval leaflets in one blended layer: dark rim, body, lit upper-left half, faint midrib.

    items: (cx, cy, rx, ry, deg, (mid, lit, dark))."""

    def paint(d):
        for cx, cy, rx, ry, deg, (mid, lit, dk) in items:
            d.polygon(ell(cx, cy + 1, rx + 2, ry + 2, deg), fill=tuple(dk) + (235,))
            d.polygon(ell(cx, cy, rx, ry, deg), fill=tuple(mid) + (255,))
            d.polygon(ell(cx + ry * 0.2, cy + ry * 0.3, rx * 0.85, ry * 0.55, deg), fill=tuple(dk) + (45,))
            for f, a in ((0.8, 55), (0.62, 60), (0.44, 70)):
                d.polygon(ell(cx - ry * 0.25, cy - ry * 0.3, rx * f, ry * f * 0.72, deg), fill=tuple(lit) + (a,))
            c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
            d.line([(cx - c * rx * 0.8, cy - s * rx * 0.8), (cx + c * rx * 0.7, cy + s * rx * 0.7)],
                   fill=tuple(dk) + (110,), width=2)

    ic.overlay(paint, clip)


def potato_plant(ic: Icon, x: float, base: float, r: float, flowers: int = 0, tone: float = 1.0) -> Image.Image:
    """Leafy potato haulm: a dark rounded mass, compound leaves of paired oval leaflets radiating
    from the ridge, pale star flowers on top. Returns the plant's mask."""
    rnd = ic.random
    body = ic.poly_mask(ic.jitter(x, base - r * 0.42, r * 0.92, r * 0.5, 16, 0.12))
    ic.shade(ic.mask("ellipse", (x - r * 1.05, base - r * 0.2, x + r * 1.15, base + r * 0.16)), (16, 10, 4), 0.5,
             blur=r * 0.12)
    ic.fill(body, "#3c5c20", "#122008", radial=(x - r * 0.6, base - r, r * 1.9), noise=0.3)
    leaves = []
    n = 12
    for i in range(n):
        a = -1.5 + 3.0 * (i + rnd.uniform(-0.35, 0.35)) / (n - 1)  # radians from straight up
        ox, oy = x + rnd.uniform(-r * 0.2, r * 0.2), base - r * rnd.uniform(0.08, 0.3)
        L = r * rnd.uniform(0.72, 1.0) * (1 - 0.15 * abs(a) / 1.5)
        droop = L * 0.35 * abs(math.sin(a))
        leaves.append((abs(a) < 0.7, a, ox, oy, L, droop))
    leaves.sort(key=lambda q: (not q[0], rnd.random()))  # upright (back) leaves first
    items = []
    for upright, a, ox, oy, L, droop in leaves:
        f = tone * (rnd.uniform(0.78, 0.92) if upright else rnd.uniform(0.9, 1.1))
        mid, lit, dk = (tuple(int(min(255, v * f)) for v in c) for c in LEAF)
        dx, dy = math.sin(a), -math.cos(a) * 0.85

        def at(t, ox=ox, oy=oy, L=L, dx=dx, dy=dy, droop=droop):
            return ox + dx * L * t, oy + dy * L * t + droop * t * t

        ic.line([at(t) for t in np.linspace(0, 1, 6)], 4, (54, 76, 30))
        for t in (0.3, 0.5, 0.68, 0.85):
            px, py = at(t)
            qx, qy = at(t + 0.05)
            ang = math.degrees(math.atan2(qy - py, qx - px))
            sz = L * rnd.uniform(0.12, 0.155) * (1.1 - 0.2 * t)
            for sgn in (-1, 1):
                ld = ang + sgn * rnd.uniform(40, 62)
                cx = px + math.cos(math.radians(ld)) * sz * 0.8
                cy = py + math.sin(math.radians(ld)) * sz * 0.8
                items.append((cx, cy, sz, sz * 0.6, ld, (mid, lit, dk)))
        tx, ty = at(1.0)
        items.append((tx, ty, L * 0.16, L * 0.1, math.degrees(math.atan2(dy + 2 * droop / L, dx)), (mid, lit, dk)))
    leaflets(ic, items)
    if flowers:
        fl = []
        for _ in range(flowers):
            fx = x + rnd.uniform(-r * 0.5, r * 0.5)
            fy = base - r * rnd.uniform(0.75, 0.98)
            lilac = rnd.random() < 0.4
            for _ in range(rnd.randint(2, 4)):
                fl.append((fx + rnd.uniform(-10, 10) * r / 75, fy + rnd.uniform(-7, 7) * r / 75, lilac))

        def paint(d):
            k0 = max(0.55, min(1.1, r / 75))  # flowers shrink with the plant towards the back
            for fx, fy, lilac in fl:
                col = (190, 172, 204, 255) if lilac else (222, 216, 202, 255)
                for k in range(5):
                    a = 2 * math.pi * k / 5 - 1.2
                    px, py = fx + math.cos(a) * 5 * k0, fy + math.sin(a) * 4 * k0
                    d.ellipse((px - 5 * k0, py - 4.5 * k0, px + 5 * k0, py + 4.5 * k0), fill=(60, 50, 60, 200))
                for k in range(5):
                    a = 2 * math.pi * k / 5 - 1.2
                    px, py = fx + math.cos(a) * 5 * k0, fy + math.sin(a) * 4 * k0
                    d.ellipse((px - 3.8 * k0, py - 3.4 * k0, px + 3.8 * k0, py + 3.4 * k0), fill=col)
                d.ellipse((fx - 2.5 * k0, fy - 2.5 * k0, fx + 2.5 * k0, fy + 2.5 * k0), fill=(226, 190, 60, 255))

        ic.overlay(paint)
    return body


def ridge(ic: Icon, x0: float, x1: float, base: float, h: float, soil=SOIL, taper: float = 0.08) -> Image.Image:
    """One earthed-up potato ridge running across the view: rounded crest lit from above, darker
    front slope, clods; the furrow in front is left to the next ridge. Returns the mask."""
    rnd = ic.random
    ts = np.linspace(0, 1, 34)
    top = []
    for t in ts:
        e = min(1.0, t / taper, (1 - t) / taper) if taper else 1.0
        top.append((x0 + (x1 - x0) * t, base - h * (math.sin(e * math.pi / 2) ** 0.7) + rnd.uniform(-h * 0.06, h * 0.06)))
    bot = [(x1 - (x1 - x0) * t, base + rnd.uniform(-2, 3)) for t in ts]
    pts = top + bot
    m = ic.poly_mask(pts)
    ic.fill(m, soil[0], soil[1], (base - h, base + 4), noise=0.34, chroma=0.12)
    crest = ic.poly_mask(top + [(p[0], p[1] + h * 0.3) for p in top[::-1]])
    tint(ic, crest, m, (236, 206, 160), 0.22, h * 0.12)
    tint(ic, ic.mask("rectangle", (x0 - 20, base - h * 0.3, x1 + 20, base + 6)), m, (10, 6, 2), 0.35, h * 0.15)

    def clods(d):
        for _ in range(int((x1 - x0) * h / 260)):
            cx, cy = rnd.uniform(x0, x1), rnd.uniform(base - h, base)
            rr = rnd.uniform(3, 8)
            light = rnd.random() < 0.45
            d.ellipse((cx - rr * 1.3, cy - rr, cx + rr * 1.3, cy + rr * 0.7),
                      fill=(232, 204, 160, 70) if light else (20, 12, 6, 80))

    ic.overlay(clods, m)
    return m


def furrow_ground(ic: Icon, pts, soil=("#5e4630", "#2e2216")) -> Image.Image:
    """Dark earth of the furrows under a bed of ridges."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ic.fill(m, soil[0], soil[1], (min(p[1] for p in pts), max(p[1] for p in pts)), noise=0.3)
    ic.outline(pts, 4, (40, 28, 16, 160))
    return m


def tubers(ic: Icon, items, clip: Image.Image | None = None) -> None:
    """Potatoes, each painted on a small tile: lumpy oval with a thin dark rim, a soft (blurred)
    core shadow low right and light upper left, eyes and soil flecks. items: (x, y, r, deg, palette)."""
    rnd = ic.random
    for x, y, r, deg, (mid, lit, dk) in items:
        wob = [rnd.uniform(0.9, 1.1) for _ in range(14)]
        pad = int(r * 1.8) + 8
        ox, oy = max(0, int(x) - pad), max(0, int(y) - pad)
        size = 2 * pad
        cx, cy = x - ox, y - oy
        rx, ry = r, r * 0.74
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(tile).polygon(ell(cx + 1, cy + 2, rx + 2.5, ry + 2.5, deg, 14, wob), fill=tuple(dk) + (255,))
        body = Image.new("L", (size, size), 0)
        ImageDraw.Draw(body).polygon(ell(cx, cy, rx, ry, deg, 14, wob), fill=255)
        tile.paste(tuple(mid) + (255,), (0, 0), body)
        form = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        fd = ImageDraw.Draw(form)
        fd.polygon(ell(cx + rx * 0.22, cy + ry * 0.5, rx * 0.95, ry * 0.62, deg, 14), fill=tuple(dk) + (170,))
        fd.polygon(ell(cx - rx * 0.26, cy - ry * 0.32, rx * 0.55, ry * 0.42, deg, 14), fill=tuple(lit) + (200,))
        for _ in range(int(r * 0.6)):
            px, py = cx + rnd.uniform(-rx, rx) * 0.8, cy + rnd.uniform(-ry, ry) * 0.8
            s = rnd.uniform(1, 2.2)
            fd.ellipse((px - s, py - s, px + s, py + s), fill=(40, 26, 12, 90) if rnd.random() < 0.6 else (240, 220, 180, 70))
        form = form.filter(ImageFilter.GaussianBlur(max(r * 0.12, 1.2)))
        form.putalpha(ImageChops.multiply(form.getchannel("A"), body))
        tile.alpha_composite(form)
        ed = ImageDraw.Draw(tile)  # eyes stay crisp: small dark pits with a lit lower lip
        for _ in range(rnd.randint(2, 4)):
            px, py = cx + rnd.uniform(-0.6, 0.6) * rx, cy + rnd.uniform(-0.45, 0.45) * ry
            e = max(2.0, r * 0.1)
            ed.ellipse((px - e, py - e * 0.7, px + e, py + e * 0.7), fill=tuple(dk) + (230,))
            ed.arc((px - e, py - e * 0.4, px + e, py + e * 1.1), 20, 160, fill=tuple(lit) + (150,), width=2)
        g = max(r * 0.1, 1.8)
        gx, gy = cx - rx * 0.36, cy - ry * 0.42
        glint = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(glint).ellipse((gx - g, gy - g * 0.7, gx + g, gy + g * 0.7), fill=(250, 238, 210, 110))
        tile.alpha_composite(glint.filter(ImageFilter.GaussianBlur(1)))
        if clip is not None:
            tile.putalpha(ImageChops.multiply(tile.getchannel("A"), clip.crop((ox, oy, ox + size, oy + size))))
        ic.image.alpha_composite(tile, (ox, oy))


def potato_heap(ic: Icon, cx: float, base: float, w: float, h: float, r: float, n: int,
                pals=((TUBER, 0.6), (TUBER_PALE, 0.28), (TUBER_RED, 0.12))) -> None:
    """Dome of potatoes, drawn back to front over a dark earthy backing mound, so the heap reads as
    one mass (the finalize outline wraps the heap, not every single potato)."""
    rnd = ic.random
    dome = [(cx + u * w / 2 * 1.04, base - h * math.sqrt(max(0.0, 1 - u * u)) * 0.96 + r * 0.1 + rnd.uniform(-3, 3))
            for u in np.linspace(-1, 1, 24)] + [(cx + w / 2 * 1.04, base + r * 0.3), (cx - w / 2 * 1.04, base + r * 0.3)]
    ic.fill(ic.poly_mask(dome), "#6a4020", "#2e1a0a", (base - h, base + r * 0.3), noise=0.2)
    items = []
    for _ in range(n):
        u = rnd.uniform(-1, 1)
        top = base - h * math.sqrt(max(0.0, 1 - u * u))
        y = rnd.uniform(top + r * 0.4, base)
        p = rnd.random()
        pal = pals[-1][0]
        for pl, wt in pals:
            p -= wt
            if p <= 0:
                pal = pl
                break
        items.append((cx + u * w / 2, y, r * rnd.uniform(0.8, 1.15), rnd.uniform(-40, 40), pal))
    items.sort(key=lambda it: it[1])
    tubers(ic, items)


def potato_basket(ic: Icon, x0: float, y0: float, x1: float, y1: float, r: float = 17, heap: float = 0.5) -> None:
    """Wicker basket heaped with potatoes, contact shadow underneath."""
    w = x1 - x0
    ic.shade(ic.mask("ellipse", (x0 - w * 0.08, y1 - 18, x1 + w * 0.12, y1 + 18)), (10, 6, 2), 0.5, blur=8)
    ic.fill(ic.mask("ellipse", (x0 + 4, y0 - 16, x1 - 4, y0 + 16)), "#2e2012", "#1a120a")
    potato_heap(ic, (x0 + x1) / 2, y0 + 8, w * 0.86, w * heap * 0.5, r, int(w * w * 0.9 / (r * r * 5)) + 8)
    ic.basket(x0, y0, x1, y1, ("#b28a54", "#5e4226"))
    ic.line([(x0 + 4, y0 + 3), (x1 - 4, y0 + 3)], 10, (138, 104, 62))
    ic.line([(x0 + 4, y0), (x1 - 4, y0)], 4, (196, 160, 110, 150))


def hipped(cx0, cx1, eave_y, ridge_y, inset, bulge=24):
    """Outline of a hipped thatch roof with rounded shoulders between eave x0..x1."""
    lside = [(cx0 + inset * (1 - math.cos(t * math.pi / 2)) + bulge * math.sin(t * math.pi),
              eave_y - (eave_y - ridge_y) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    rside = [(cx1 - inset * (1 - math.cos(t * math.pi / 2)) - bulge * math.sin(t * math.pi),
              eave_y - (eave_y - ridge_y - 4) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    return lside + [((cx0 + cx1) / 2, ridge_y + 6)] + rside[::-1]


def thatch_eave(ic: Icon, x0, x1, y) -> None:
    eave = [(x0, y - 4), (x1, y - 4), (x1 - 2, y + 22)]
    for x in np.arange(x1 - 8, x0, -14):
        eave.append((x, y + 26 + ic.random.uniform(-5, 6)))
    eave.append((x0 + 2, y + 22))
    em = ic.poly_mask(eave)
    ic.fill(em, "#94764a", "#3a2a16", (y - 4, y + 30), noise=0.22)
    ic.overlay(lambda d: [d.line([(x, y), (x + ic.random.uniform(-3, 3), y + 26)],
                                 fill=(30, 18, 8, int(ic.random.uniform(40, 130))), width=3)
                          for x in np.arange(x0 + 4, x1 - 4, 7)], em)
    ic.outline(eave, 4)


def chimney(ic: Icon, x0, x1, top, bottom) -> None:
    cm = ic.mask("rectangle", (x0, top, x1, bottom))
    stones(ic, (x0, top, x1, bottom), "#aea290", "#6a6054", course=26, clip=cm)
    tint(ic, ic.mask("rectangle", (x0 + (x1 - x0) * 0.55, top, x1 + 10, bottom)), cm, (0, 0, 0), 0.3, 10)
    ic.outline([(x0, top), (x1, top), (x1, bottom), (x0, bottom)], 4)
    ic.rect((x0 - 8, top - 10, x1 + 8, top + 8), "#aaa08e", "#6e6658", edge=4)


def spade(ic: Icon, grip, foot, blade_w: float = 44, blade_h: float = 70) -> None:
    """Spade driven into the ground: ash shaft with a T grip, iron-shod blade at ``foot`` (blade top)."""
    gx, gy = grip
    fx, fy = foot
    ang = math.atan2(fy - gy, fx - gx)
    nx, ny = -math.sin(ang), math.cos(ang)
    ic.line([(gx, gy), (fx, fy)], 22, (46, 30, 18))
    ic.line([(gx, gy), (fx, fy)], 15, (150, 112, 70))
    ic.line([(gx - 3, gy + 2), (fx - 3, fy)], 4, (214, 180, 132, 150))
    ic.line([(gx - nx * 30, gy - ny * 30), (gx + nx * 30, gy + ny * 30)], 20, (46, 30, 18))
    ic.line([(gx - nx * 28, gy - ny * 28), (gx + nx * 28, gy + ny * 28)], 13, (140, 104, 64))
    dx, dy = math.cos(ang), math.sin(ang)
    hw = blade_w / 2
    blade = [(fx - nx * hw, fy - ny * hw), (fx + nx * hw, fy + ny * hw),
             (fx + nx * hw * 0.92 + dx * blade_h, fy + ny * hw * 0.92 + dy * blade_h),
             (fx - nx * hw * 0.92 + dx * blade_h, fy - ny * hw * 0.92 + dy * blade_h)]
    ic.poly(blade, "#8e8a84", "#46423e", (fx - hw, fx + hw), vertical=False, edge=4)
    ic.line([blade[0], blade[1]], 8, (70, 50, 30))
    ic.line([(fx - nx * hw * 0.6 + dx * 6, fy - ny * hw * 0.6 + dy * 6),
             (fx - nx * hw * 0.5 + dx * blade_h * 0.8, fy - ny * hw * 0.5 + dy * blade_h * 0.8)], 4, (220, 216, 206, 120))

SEED = 29
REFS = ("farming_village", "granary", "fiber_crops_farm", "grain_house")

BRICK = ("#bc7c52", "#744630")  # lighter, warm orange brick walls
TILE = ("#a23a2a", "#4a1410")  # deeper, saturated terracotta roof


def bricks(ic: Icon, m: Image.Image, box, base=BRICK[0], dark=BRICK[1], course: float = 17, length: float = 40) -> None:
    """Brick face: per-brick tone, pale mortar joints, a lit top and a shadowed bottom per course."""
    x0, y0, x1, y1 = box
    ic.fill(m, base, dark, (y0, y1), noise=0.22, chroma=0.08)
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rnd = ic.random.uniform
    y, k = y0, 0
    while y < y1:
        x = x0 - (k % 2) * length / 2 - rnd(0, 6)
        while x < x1:
            w = length * rnd(0.9, 1.1)
            t = rnd(-1, 1)
            col = (255, 214, 176, int(t * 40)) if t > 0 else (30, 12, 6, int(-t * 64))
            d.rectangle((x + 2, y + 2, x + w - 2, y + course - 2), fill=col)
            d.line([(x + w - 1, y + 1), (x + w - 1, y + course - 1)], fill=(196, 176, 150, 38), width=3)
            x += w
        d.line([(x0, y + course - 1), (x1, y + course - 1)], fill=(196, 176, 150, 46), width=3)
        d.line([(x0, y + course + 2), (x1, y + course + 2)], fill=(24, 12, 8, 50), width=2)
        y += course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip)


def pantiles(ic: Icon, pts, c1, c2, course: float = 30, edge: int = 7) -> Image.Image:
    """Roof plane of horizontal overlapping tile courses (no vertical joints): soft tone drifts along
    each course, a lit lip and a dark shadow line under every course, a scalloped pantile eaves edge.
    Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys = [p[1] for p in pts]
    xs = [p[0] for p in pts]
    top, bot, xa, xb = min(ys), max(ys), min(xs), max(xs)
    ic.fill(m, c1, c2, (top, bot), noise=0.16, chroma=0.05)
    rnd = ic.random.uniform
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    y = top + course * 0.6
    while y < bot - 4:
        x = xa - 20
        while x < xb:  # long, soft tone drifts along the course, not individual tiles
            w = rnd(60, 160)
            t = rnd(-1, 1)
            td.rectangle((x, y - course + 4, x + w, y - 2),
                         fill=(24, 6, 2, int(-t * 44)) if t < 0 else (255, 214, 180, int(t * 30)))
            x += w
        # pantile rolls: a faint lit and dark wave along the lip of every course
        for xx in np.arange(xa - 10, xb, 26):
            td.arc((xx, y - 14, xx + 26, y + 4), 200, 340, fill=(255, 210, 176, 50), width=3)
        td.line([(xa, y - 5), (xb, y - 5 + rnd(-2, 2))], fill=(255, 216, 186, 70), width=4)
        sd.line([(xa, y + 2), (xb, y + 2 + rnd(-2, 2))], fill=255, width=8)
        y += course * rnd(0.94, 1.06)
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (20, 2, 0), 0.62, 2.5)
    ic.outline(pts, edge)
    return m


def eaves(ic: Icon, x0: float, x1: float, y: float, color=TILE) -> None:
    """Scalloped pantile eaves edge over a dark eaves shadow line."""
    ic.overlay(lambda d: d.rectangle((x0 + 4, y - 2, x1 - 4, y + 12), fill=(20, 8, 4, 150)))
    pts = [(x0, y - 16)] + [(x1, y - 16)]
    for x in np.arange(x1, x0 - 1, -22):
        pts += [(x, y + 2), (x - 11, y + 10), (x - 22, y + 2)]
    pts = [(p[0], p[1]) for p in pts if x0 - 1 <= p[0] <= x1 + 1]
    pts.append((x0, y + 2))
    ic.poly(pts, color[0], color[1], (y - 16, y + 10), edge=4)
    ic.overlay(lambda d: [d.arc((x - 22, y - 6, x, y + 10), 20, 160, fill=(255, 208, 172, 90), width=3)
                          for x in np.arange(x1, x0, -22)])


def ridge_tiles(ic: Icon, x0: float, x1: float, y: float, h: float = 20) -> None:
    """Rounded ridge capping: a darker half-round roll with a lit top and a joint every tile."""
    ic.rect((x0, y - h / 2, x1, y + h / 2), "#8e3022", "#3e100a", edge=4)
    ic.line([(x0 + 6, y - h / 2 + 5), (x1 - 6, y - h / 2 + 5)], 4, (236, 150, 120, 120))
    ic.overlay(lambda d: [d.line([(x, y - h / 2 + 2), (x, y + h / 2 - 2)], fill=(30, 8, 4, 120), width=3)
                          for x in np.arange(x0 + 36, x1 - 10, 36)])


def quoins(ic: Icon, x: float, y0: float, y1: float, w: float = 34, h: float = 30) -> None:
    """Dressed pale stone blocks up a corner, alternating long and short."""
    y, k = y0, 0
    while y < y1 - 4:
        ww = w if k % 2 else w * 0.62
        ic.rect((x - ww / 2, y, x + ww / 2, min(y + h, y1)), "#d0c4ac", "#948670", noise=0.14, edge=3)
        y += h + 2
        k += 1


def house(ic: Icon) -> None:
    L, R, TOP, BASE = 60, 440, 290, 610
    for x0 in (100, 360):  # end chimneys
        cm = ic.mask("rectangle", (x0, 110, x0 + 50, 240))
        bricks(ic, cm, (x0, 110, x0 + 50, 240), course=15, length=26)
        tint(ic, ic.mask("rectangle", (x0 + 28, 110, x0 + 60, 240)), cm, (0, 0, 0), 0.3, 8)
        ic.outline([(x0, 110), (x0 + 50, 110), (x0 + 50, 240), (x0, 240)], 4)
        ic.rect((x0 - 8, 100, x0 + 58, 116), "#8a5a44", "#4e3024", edge=4)
    roof = [(L - 34, TOP + 14), (R + 34, TOP + 14), (R - 60, 160), (L + 60, 160)]
    rm = pantiles(ic, roof, TILE[0], TILE[1], course=30)
    tint(ic, ic.poly_mask([(20, 150), (220, 150), (180, 320), (20, 320)]), rm, (255, 210, 180), 0.12, 40)
    tint(ic, ic.poly_mask([(330, 150), (500, 150), (500, 320), (360, 320)]), rm, (0, 0, 0), 0.22, 36)
    eaves(ic, L - 34, R + 34, TOP + 12)
    ridge_tiles(ic, L + 54, R - 54, 160)
    wm = ic.mask("rectangle", (L, TOP + 14, R, BASE))
    bricks(ic, wm, (L, TOP + 14, R, BASE))
    tint(ic, ic.mask("rectangle", (L, TOP, R, TOP + 70)), wm, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (300, TOP, R, BASE)), wm, (20, 10, 4), 0.18, 40)
    tint(ic, ic.mask("rectangle", (L, BASE - 50, R, BASE)), wm, (40, 36, 20), 0.3, 14)
    ic.rect((L, 452, R, 466), "#cabea6", "#8e826c", edge=3)  # string course
    quoins(ic, L + 14, TOP + 16, BASE)
    quoins(ic, R - 14, TOP + 16, BASE)
    for x0 in (104, 206, 294, 372):
        if x0 in (104, 372):
            ic.window(x0 - 14, 352, x0 + 22, 420, frame="#d4cab6")
        ic.window(x0 - 14, 498, x0 + 22, 566, frame="#d4cab6")
    ic.window(236, 352, 272, 420, frame="#d4cab6")
    ic.door(226, 500, 284, BASE - 4, arched=True, surround="#cabea6")
    ic.outline([(L, TOP + 14), (R, TOP + 14), (R, BASE), (L, BASE)], 5)


def barn(ic: Icon) -> None:
    L, R, TOP, BASE = 440, 800, 400, 610
    roof = [(L - 20, TOP + 14), (R + 30, TOP + 14), (R - 10, 262), (L + 10, 262)]
    rm = pantiles(ic, roof, "#9c3828", "#461410", course=30)
    tint(ic, ic.poly_mask([(600, 250), (860, 250), (860, 420), (640, 420)]), rm, (0, 0, 0), 0.22, 40)
    eaves(ic, L - 20, R + 30, TOP + 12)
    ridge_tiles(ic, L + 4, R - 4, 260)
    wm = ic.mask("rectangle", (L, TOP + 14, R, BASE))
    bricks(ic, wm, (L, TOP + 14, R, BASE), base="#b4744c", dark="#6c402a")
    tint(ic, ic.mask("rectangle", (L, TOP, R, TOP + 60)), wm, (0, 0, 0), 0.45, 12)
    tint(ic, ic.mask("rectangle", (L, TOP, L + 60, BASE)), wm, (0, 0, 0), 0.35, 20)  # the house shades it
    # arched cart entrance
    ax0, ax1 = 560, 680
    arch = union(ic.mask("ellipse", (ax0, 470, ax1, 590)), ic.mask("rectangle", (ax0, 530, ax1, BASE)))
    ring = union(ic.mask("ellipse", (ax0 - 16, 454, ax1 + 16, 606)), ic.mask("rectangle", (ax0 - 16, 530, ax1 + 16, BASE)))
    ic.fill(ring, "#cabea6", "#8e826c", (454, BASE), noise=0.14)
    ic.fill(arch, "#281c12", "#0e0a06", noise=0.1)
    # slatted vents
    for x in (500, 740):
        ic.rect((x - 10, 450, x + 10, 530), "#2a1e16", "#140c08", edge=3)
    quoins(ic, R - 14, TOP + 16, BASE, 30, 28)
    ic.outline([(L, TOP + 14), (R, TOP + 14), (R, BASE), (L, BASE)], 5)


def cellar(ic: Icon, x0: float, x1: float, base: float, top: float) -> None:
    """Clamp cellar: a turfed mound over a vault, dressed stone portal with a plank door, a vent."""
    rnd = ic.random
    cx = (x0 + x1) / 2
    prof = [(x0 + (x1 - x0) * t, base - (base - top) * math.sin(math.pi * t) ** 0.6) for t in np.linspace(0, 1, 30)]
    ic.shade(ic.mask("ellipse", (x0 - 20, base - 30, x1 + 40, base + 30)), (10, 6, 2), 0.5, blur=12)
    mm = ic.poly_mask(prof)
    ic.fill(mm, "#7c9448", "#2e3e18", radial=(x0 + (x1 - x0) * 0.25, top - 40, (x1 - x0) * 0.9), noise=0.3, chroma=0.12)

    def grass(d):
        for _ in range(900):
            x, y = rnd.uniform(x0, x1), rnd.uniform(top - 10, base)
            L = rnd.uniform(6, 14)
            col = (178, 196, 110, 110) if rnd.random() < 0.45 else (24, 36, 12, 110)
            d.line([(x, y), (x + rnd.uniform(-3, 3), y - L)], fill=col, width=2)

    ic.overlay(grass, mm)
    ic.outline(prof, 5, (30, 40, 14, 170))
    # vent chimney on the crown
    vx = cx + (x1 - x0) * 0.18
    vy = np.interp(vx, [p[0] for p in prof], [p[1] for p in prof]) + 14
    vm = ic.mask("rectangle", (vx - 20, vy - 56, vx + 20, vy))
    stones(ic, (vx - 20, vy - 56, vx + 20, vy), "#c0b49c", "#7e7262", course=18, clip=vm)
    ic.outline([(vx - 20, vy - 56), (vx + 20, vy - 56), (vx + 20, vy), (vx - 20, vy)], 4)
    ic.rect((vx - 28, vy - 66, vx + 28, vy - 52), "#b4a890", "#766a58", edge=4)
    # portal: ashlar face, arched door
    px0, px1 = cx - 96, cx + 70
    pt = base - (base - top) * 0.72
    face = [(px0, base), (px0 + 6, pt + 30), (cx - 13, pt), (px1 - 6, pt + 30), (px1, base)]
    fm = ic.poly_mask(face)
    stones(ic, (px0, pt, px1, base), "#c6baa2", "#8a7e6a", course=28, clip=fm)
    tint(ic, ic.mask("rectangle", (px0, pt, px1, pt + 40)), fm, (0, 0, 0), 0.2, 10)
    ic.outline(face, 5)
    ic.door(cx - 50, pt + 44, cx + 24, base - 4, arched=True, surround="#d4c8ae")
    ic.rect((px0 - 10, pt + 22, px1 + 10, pt + 38), "#b4a890", "#766a58", edge=4)  # coping stone


def drills(ic: Icon, back_y, front_y, back_x, front_x, n, wb, wf) -> list:
    """Straight ridges running from the front towards the farm; returns plant positions (x, y, r)."""
    rnd = ic.random
    bxs = np.linspace(back_x[0], back_x[1], n)
    fxs = np.linspace(front_x[0], front_x[1], n)
    field = [(back_x[0] - wb * 1.6, back_y - 6), (back_x[1] + wb * 1.6, back_y - 6), (front_x[1] + wf * 1.3, front_y + 6),
             (front_x[0] - wf * 1.3, front_y + 6)]
    furrow_ground(ic, field)
    plants = []
    for bx, fx in zip(bxs, fxs):
        pts = [(bx - wb, back_y), (bx + wb, back_y), (fx + wf, front_y), (fx - wf, front_y)]
        m = ic.poly_mask(pts)
        ic.fill(m, SOIL[0], SOIL[1], (back_y, front_y), noise=0.3, chroma=0.1)
        tint(ic, ic.poly_mask([(bx, back_y), (bx + wb, back_y), (fx + wf, front_y), (fx, front_y)]), m, (10, 6, 2),
             0.4, 6)
        tint(ic, ic.poly_mask([(bx - wb, back_y), (bx, back_y), (fx, front_y), (fx - wf, front_y)]), m,
             (236, 206, 160), 0.14, 6)
        t = 0.03
        while t < 1.0:
            r = 24 + 40 * t
            plants.append((bx + (fx - bx) * t + rnd.uniform(-4, 4), back_y + (front_y - back_y) * t, r))
            t += r * 0.62 / (front_y - back_y)
    return plants


def open_crate(ic: Icon, x0, y0, x1, y1, heap: float = 34) -> None:
    """Slatted field crate heaped with potatoes: load first, then the front boards over it."""
    ic.shade(ic.mask("ellipse", (x0 - 10, y1 - 16, x1 + 20, y1 + 16)), (10, 6, 2), 0.45, blur=8)
    ic.fill(ic.mask("rectangle", (x0 + 6, y0 - 18, x1 - 6, y0 + 10)), "#2a1c10", "#140c06")
    potato_heap(ic, (x0 + x1) / 2, y0 + 10, x1 - x0 - 6, heap, 27, 12, pals=((TUBER, 0.5), (TUBER_RED, 0.35), (TUBER_PALE, 0.15)))
    fm = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(fm, "#a07a50", "#5a3e24", (y0, y1), noise=0.2)
    for k, y in enumerate(np.linspace(y0, y1, 4)[:-1]):
        ic.rect((x0, y + 3, x1, y + (y1 - y0) / 3 - 5), "#a88258" if k % 2 else "#98724a", "#5e4026", noise=0.2, edge=3)
    for bx in (x0 + 8, x1 - 8):
        ic.line([(bx, y0 - 4), (bx, y1)], 14, (78, 54, 32))
    tint(ic, ic.mask("rectangle", (x1 - (x1 - x0) * 0.3, y0, x1 + 20, y1)), fm, (0, 0, 0), 0.25, 10)
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 5)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.66
    ic.grade["mute"] = 0.84
    rnd = ic.random
    barn(ic)
    house(ic)
    cellar(ic, 770, 1006, 640, 430)

    # the drilled field
    plants = drills(ic, 640, 972, (200, 840), (50, 980), 7, 20, 50)
    for x, y, r in sorted(plants, key=lambda p: p[1]):
        potato_plant(ic, x, y, r * rnd.uniform(0.92, 1.08), flowers=rnd.choice((0, 0, 0, 1)), tone=0.82 + 0.2 * (y - 640) / 330)

    # crates of the lifted crop, bottom right
    open_crate(ic, 740, 890, 890, 992, heap=66)
    open_crate(ic, 872, 910, 1014, 1004, heap=60)
