"""Potato Field (potato_farm): spade-dug lazy beds of leafy potatoes beside a whitewashed cabin.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor/assets/icon_drawings/potato_farm/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/potato_farm

Identity (tier 1 of the potato chain): three earthed-up ridges of dark leafy potato haulms with
pale flowers fill the view in front of a small whitewashed, thatched cabin; the end of the front
ridge is dug open with a spade still in it, fresh potatoes on the earth and a basket of them at the
bottom right. Family helpers (shared by all four potato tiers): ``ell``, ``leaflets``,
``potato_plant``, ``ridge``, ``furrow_ground``, ``tubers``, ``potato_heap``, ``potato_basket``,
``spade``; ``union``, ``tint``, ``stones``, ``thatch``, ``planks`` come from the Tavern, ``jute``
from the Coffee Grove.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb

SOIL = ("#86643e", "#3a2a1a")
LEAF = ((94, 132, 48), (144, 180, 82), (26, 40, 12))  # potato leaflet: mid, lit, dark rim
TUBER = ((160, 118, 70), (200, 164, 108), (72, 48, 26))  # mid, lit, dark
TUBER_PALE = ((178, 140, 88), (214, 184, 128), (84, 60, 34))
TUBER_RED = ((140, 76, 58), (180, 112, 86), (64, 30, 22))
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
        for _ in range(rnd.randint(1, 3)):
            px, py = cx + rnd.uniform(-0.6, 0.6) * rx, cy + rnd.uniform(-0.45, 0.45) * ry
            fd.ellipse((px - 2.4, py - 1.6, px + 2.4, py + 1.6), fill=tuple(dk) + (200,))
        form = form.filter(ImageFilter.GaussianBlur(max(r * 0.12, 1.2)))
        form.putalpha(ImageChops.multiply(form.getchannel("A"), body))
        tile.alpha_composite(form)
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
    """Dome of potatoes, drawn back to front."""
    rnd = ic.random
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

SEED = 11
REFS = ("farming_village", "fiber_crops_farm", "free_village", "terraces")


def cabin(ic: Icon) -> None:
    L, R, TOP, BASE = 130, 520, 470, 650
    # chimney at the right gable end
    cx0, cx1 = 420, 476
    cm = ic.mask("rectangle", (cx0, 262, cx1, 420))
    stones(ic, (cx0, 262, cx1, 420), "#b4aa98", "#6e6456", course=26, clip=cm)
    tint(ic, ic.mask("rectangle", (cx0 + 30, 262, cx1 + 10, 420)), cm, (0, 0, 0), 0.3, 10)
    ic.outline([(cx0, 262), (cx1, 262), (cx1, 420), (cx0, 420)], 4)
    ic.rect((cx0 - 8, 252, cx1 + 8, 270), "#aaa08e", "#6e6658", edge=4)
    # walls: whitewashed rubble, grimy at the foot
    wm = ic.mask("rectangle", (L, TOP, R, BASE))
    stones(ic, (L, TOP, R, BASE), "#e0d8c4", "#b0a48c", course=34, clip=wm, lit=40, shadow=70, moss=0.02)
    tint(ic, ic.mask("rectangle", (L, BASE - 60, R, BASE)), wm, (70, 60, 36), 0.35, 18)
    tint(ic, ic.mask("rectangle", (L + 240, TOP, R, BASE)), wm, (40, 30, 20), 0.18, 40)
    for _ in range(6):
        x, y = ic.random.uniform(L, R), ic.random.uniform(TOP + 40, BASE)
        tint(ic, ic.mask("ellipse", (x - 30, y - 40, x + 30, y + 40)), wm, (110, 96, 70), 0.14, 16)
    ic.outline([(L, TOP), (R, TOP), (R, BASE), (L, BASE)], 5)
    # half door (lower leaf shut, upper open onto the dark room) and two small windows
    dx0, dx1 = 268, 330
    ic.rect((dx0 - 10, 536, dx1 + 10, BASE), "#b8ac94", "#8a7e6a", edge=0)
    ic.rect((dx0, 546, dx1, BASE), "#1e1610", "#0c0806", noise=0.1, edge=0)
    planks(ic, (dx0, 596, dx1, BASE - 2), "#8a5a34", "#4a2e18", board=16)
    ic.outline([(dx0, 596), (dx1, 596), (dx1, BASE - 2), (dx0, BASE - 2)], 4)
    ic.outline([(dx0, 546), (dx1, 546), (dx1, BASE), (dx0, BASE)], 4)
    for x0, x1 in ((170, 214), (398, 440)):
        ic.window(x0, 556, x1, 596)
        tint(ic, ic.mask("rectangle", (x0 - 10, 606, x1 + 14, 624)), wm, (0, 0, 0), 0.25, 6)
    # thatch: hipped, rounded shoulders, heavy eave shading the wall
    ridge_y, eave_y = 330, 500
    lside = [(96 + 110 * (1 - math.cos(t * math.pi / 2)) + 24 * math.sin(t * math.pi),
              eave_y - (eave_y - ridge_y) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    rside = [(556 - 104 * (1 - math.cos(t * math.pi / 2)) - 24 * math.sin(t * math.pi),
              eave_y - (eave_y - ridge_y - 6) * math.sin(t * math.pi / 2)) for t in np.linspace(0, 1, 14)]
    roof = lside + [(330, ridge_y + 6)] + rside[::-1]
    rm = thatch(ic, roof, "#b89656", "#5a4020", course=40)
    tint(ic, ic.poly_mask([(90, ridge_y), (300, ridge_y), (260, eave_y), (90, eave_y)]), rm, (255, 230, 180), 0.14, 40)
    tint(ic, ic.poly_mask([(420, ridge_y), (580, ridge_y), (580, eave_y), (450, eave_y)]), rm, (0, 0, 0), 0.22, 36)
    tint(ic, ic.poly_mask([(cx0 - 10, 350), (cx0 - 50, 390), (cx0 - 40, 440), (cx0, 420)]), rm, (0, 0, 0), 0.3, 12)
    # weighted ropes across the thatch
    for x in (190, 260, 330, 400):
        ic.line([(x + 8, ridge_y + 12), (x - 6, eave_y - 6)], 4, (60, 44, 24, 150))
    ic.outline(roof, 6)
    ic.line([(206, ridge_y + 4), (452, ridge_y + 8)], 18, (122, 98, 58))
    ic.line([(206, ridge_y), (452, ridge_y + 4)], 6, (190, 162, 110, 150))
    eave = [(100, eave_y - 4), (552, eave_y - 4), (550, eave_y + 24)]
    for x in np.arange(544, 100, -14):
        eave.append((x, eave_y + 28 + ic.random.uniform(-5, 6)))
    eave.append((102, eave_y + 24))
    em = ic.poly_mask(eave)
    ic.fill(em, "#94764a", "#3a2a16", (eave_y - 4, eave_y + 32), noise=0.22)
    ic.overlay(lambda d: [d.line([(x, eave_y), (x + ic.random.uniform(-3, 3), eave_y + 28)],
                                 fill=(30, 18, 8, int(ic.random.uniform(40, 130))), width=3)
                          for x in np.arange(104, 548, 7)], em)
    ic.outline(eave, 4)
    tint(ic, ic.mask("rectangle", (L, eave_y + 20, R, eave_y + 70)), wm, (0, 0, 0), 0.45, 12)


def draw(ic: Icon) -> None:
    ic.grade["gamma"] = 0.63
    ic.grade["mute"] = 0.84
    rnd = ic.random
    cabin(ic)

    # dark furrow earth under the whole hillside bed, ragged edge
    edge = [(548, 520)] + [(x, 488 + rnd.uniform(-8, 8)) for x in np.linspace(590, 960, 7)] + [(1000, 520)]
    furrow_ground(ic, edge + [(1004, 850), (960, 960), (700, 968), (40, 950), (24, 790), (60, 750), (300, 730),
                              (520, 700), (530, 600)])

    rows = (  # x0, x1, base, ridge height, plant radius, tone -- lazy beds climbing the slope behind
        (566, 990, 530, 34, 50, 0.78),
        (548, 1000, 620, 40, 58, 0.84),
        (530, 1004, 712, 46, 66, 0.9),
        (44, 990, 818, 54, 74, 0.95),
        (24, 700, 930, 62, 84, 1.0),
    )
    for x0, x1, base, h, r, tone in rows:
        ridge(ic, x0, x1, base, h)
        n = max(2, int((x1 - x0) / (r * 1.3)))
        xs = np.linspace(x0 + r * 0.9, x1 - r * 0.9, n)
        for k, x in enumerate(xs):
            potato_plant(ic, x + rnd.uniform(-10, 10), base - h * 0.7, r * rnd.uniform(0.9, 1.08),
                         flowers=rnd.choice((0, 1, 2)), tone=tone)
        tint(ic, ic.mask("rectangle", (x0 - 40, base - 10, x1 + 40, base + 30)), None, (10, 6, 2), 0.3, 10)

    # the dug end of the front ridge: opened earth, fresh potatoes, spade in the soil
    dug = ic.poly_mask([(600, 936), (626, 884), (690, 862), (760, 872), (790, 924), (750, 966), (630, 968)])
    ic.fill(dug, "#7a5a38", "#3e2c1a", (860, 968), noise=0.35)
    spade(ic, (744, 700), (720, 872), 54, 66)
    items = [(640, 912, 22, -20, TUBER), (676, 928, 24, 15, TUBER_PALE), (714, 904, 20, 30, TUBER),
             (660, 952, 22, -10, TUBER_RED), (704, 950, 22, 5, TUBER), (742, 936, 20, 40, TUBER_PALE)]
    tubers(ic, sorted(items, key=lambda it: it[1]))

    # basket of the day's lifting, bottom right
    potato_basket(ic, 778, 884, 1006, 992, r=24, heap=0.7)
