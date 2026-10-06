"""Shared shield, frames, metal finish and painterly helpers of the PP specialization town right icons.

Vanilla pairs ``<x>_charter`` -> ``royal_<x>_rights`` with ONE emblem per line: a heraldic shield with a
central charge, flanked by props. The charter has a plain steel frame and silver props; the royal rights
version is the same composition with a gold cartouche frame (crest, side volutes, toothed rim) and gilded
props. This module draws that frame for both tiers; ``goods/<good>.py`` draws the line's props and charge.

Composition (1024 px canvas, light from the upper left):

1. metal layer: the good's props plus the frame, painted in any colour (only value matters), then mapped
   to a silver (charter) or gold (rights) ramp,
2. the shield field in the good's tincture, with a parchment hatch and an inner bevel shadow,
3. the charge in natural colours on its own layer, casting a soft shadow onto the field,
4. finish: the kit's colour grade, black silhouette outline and halo, a soft drop shadow, 128 px.

Goods modules call the helpers below through the ``k`` argument (this module).
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from collections.abc import Callable, Iterator, Sequence

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.canvas import SIZE, rgb
from eu5_building_pipeline.iconkit.finalize import grade, outline, rim, soften

Point = tuple[float, float]

# ------------------------------------------------------------------ geometry of the shield
CX = 512
X0, X1, Y0, Y1 = 276, 748, 150, 868  # outer edge of the plain (charter) shield
SHOULDER = 0.48  # share of the height that is straight-sided
RIM = {"charter": 20, "rights": 18}  # field inset from the shield edge
GOLD_OUT = 20  # how far the gold cartouche band reaches outside the shield edge

# charge area inside the field: centre and a comfortable box
CHARGE_CX, CHARGE_CY = 512, 470
CHARGE_BOX = (322, 214, 702, 770)

# crossed props: (base, head); the head shows beside the top corner, the base below the lower corner
CROSS_L = ((808, 994), (80, 104))  # head top left
CROSS_R = ((216, 994), (944, 104))  # head top right
CROSS_LEN = 1100

EDGE = (20, 15, 11, 235)  # interior contour (near black, vanilla separates every element with it)
EDGE_W = 7

SILVER = ((0.0, (26, 29, 36)), (0.30, (88, 94, 104)), (0.62, (164, 170, 178)), (0.86, (222, 226, 230)),
          (1.0, (252, 252, 250)))
GOLD = ((0.0, (64, 34, 0)), (0.28, (162, 106, 4)), (0.56, (232, 180, 22)), (0.80, (254, 222, 70)),
        (1.0, (255, 250, 200)))

FIT = 0.95  # art scale inside the 128 px canvas (vanilla town rights keep ~4-7 px margins)
FIT_RAISE = 6  # px the art sits above centre, room for the drop shadow
GRADE = {"mute": 1.0, "gamma": 0.90, "light": 0.10, "rim": 0.10, "soften": 1.0}


# ------------------------------------------------------------------ small geometry helpers
def bezier(p0: Point, p1: Point, p2: Point, p3: Point, n: int = 24) -> list[Point]:
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def shield_pts(d: float = 0.0, n: int = 36) -> list[Point]:
    """Heater shield outline, inset by ``d`` (negative = outset)."""
    l, r, t = X0 + d, X1 - d, Y0 + d
    b = Y1 - d * 1.55
    mid = Y0 + (Y1 - Y0) * SHOULDER
    right = bezier((r, mid), (r, mid + (b - mid) * 0.52), (CX + (r - CX) * 0.40, b - (b - mid) * 0.12), (CX, b), n)
    left = [(2 * CX - x, y) for x, y in right[::-1]]
    return [(l, t), (r, t)] + right + left[1:] + [(l, mid)]


def along(base: Point, head: Point, pts: Sequence[Point], mirror: bool = False) -> list[Point]:
    """Local prop coordinates (across, along) -> canvas. ``along`` runs from ``base`` towards ``head``."""
    bx, by = base
    dx, dy = head[0] - bx, head[1] - by
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    s = -1 if mirror else 1
    return [(bx + ux * v + px * a * s, by + uy * v + py * a * s) for a, v in pts]


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def subtract(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def offset(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    return ImageChops.offset(mask, dx, dy)


def line_mask(icon: Icon, pts: Sequence[Point], w: float, caps: bool = True) -> Image.Image:
    m = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(m)
    pts = [tuple(p) for p in pts]
    d.line(pts, fill=255, width=int(w), joint="curve")
    if caps:
        for p in (pts[0], pts[-1]):
            d.ellipse((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), fill=255)
    return m


def ell(icon: Icon, cx: float, cy: float, rx: float, ry: float | None = None) -> Image.Image:
    ry = rx if ry is None else ry
    return icon.mask("ellipse", (cx - rx, cy - ry, cx + rx, cy + ry))


# ------------------------------------------------------------------ painting helpers
def _bbox(mask: Image.Image, pad: int = 2):
    b = mask.getbbox()
    if not b:
        return None
    return (max(0, b[0] - pad), max(0, b[1] - pad), min(SIZE, b[2] + pad), min(SIZE, b[3] + pad))


def ramp(t: np.ndarray, stops: Sequence[tuple[float, object]]) -> np.ndarray:
    ts = np.array([s[0] for s in stops], float)
    cols = np.array([rgb(s[1]) for s in stops], float)
    out = np.empty(t.shape + (3,))
    for c in range(3):
        out[..., c] = np.interp(t, ts, cols[:, c])
    return out


def dfill(icon: Icon, mask: Image.Image, origin: Point, direction: Point, length: float,
          stops: Sequence[tuple[float, object]], noise: float = 0.14, chroma: float = 0.06) -> None:
    """Fill ``mask`` with a multi-stop gradient running ``length`` px from ``origin`` along ``direction``."""
    box = _bbox(mask)
    if box is None:
        return
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = direction
    n = math.hypot(dx, dy) or 1
    t = np.clip(((xx - origin[0]) * dx / n + (yy - origin[1]) * dy / n) / length, 0, 1)
    col = ramp(t, stops)
    col *= (1 + noise * icon.noise[y0:y1, x0:x1])[..., None]
    col *= 1 + chroma * icon.chroma[y0:y1, x0:x1]
    lay = Image.fromarray(np.clip(col, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    icon.image.paste(lay, (x0, y0), mask.crop(box))


def rfill(icon: Icon, mask: Image.Image, centre: Point, radius: float, stops, noise: float = 0.14,
          chroma: float = 0.06) -> None:
    """Radial multi-stop fill (spheres, bellies of vessels)."""
    box = _bbox(mask)
    if box is None:
        return
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[y0:y1, x0:x1]
    t = np.clip(np.hypot(xx - centre[0], yy - centre[1]) / radius, 0, 1)
    col = ramp(t, stops)
    col *= (1 + noise * icon.noise[y0:y1, x0:x1])[..., None]
    col *= 1 + chroma * icon.chroma[y0:y1, x0:x1]
    lay = Image.fromarray(np.clip(col, 0, 255).astype("uint8"), "RGB").convert("RGBA")
    icon.image.paste(lay, (x0, y0), mask.crop(box))


def tones(color, lit: float = 1.35, dark: float = 0.42):
    c = rgb(color)
    return tuple(int(min(255, v * lit + 8)) for v in c), tuple(int(v) for v in c), tuple(int(v * dark) for v in c)


def cylinder_stops(color, spec: float = 1.45, dark: float = 0.38):
    c = rgb(color)
    hi = tuple(int(min(255, v * spec + 18)) for v in c)
    return ((0.0, tuple(int(v * 0.62) for v in c)), (0.22, hi), (0.45, tuple(int(v) for v in c)),
            (0.82, tuple(int(v * 0.6) for v in c)), (1.0, tuple(int(v * dark) for v in c)))


def cyl(icon: Icon, mask: Image.Image, p0: Point, p1: Point, w: float, color, spec: float = 1.45,
        dark: float = 0.38, noise: float = 0.12) -> None:
    """Shade ``mask`` as a cylinder of width ``w`` lying along p0 -> p1 (lit on its upper-left side)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    if nx * -1 + ny * -1.2 < 0:  # make n point towards the light (upper left)
        nx, ny = -nx, -ny
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    # project the axis midpoint; t = 0 on the lit edge
    origin = (mx + nx * w / 2, my + ny * w / 2)
    dfill(icon, mask, origin, (-nx, -ny), w, cylinder_stops(color, spec, dark), noise)


def rod(icon: Icon, p0: Point, p1: Point, w: float, color, edge: bool = True, caps: bool = True,
        spec: float = 1.45) -> Image.Image:
    m = line_mask(icon, [p0, p1], w, caps)
    cyl(icon, m, p0, p1, w, color, spec)
    if edge:
        contour(icon, m)
    return m


def ball(icon: Icon, cx: float, cy: float, r: float, color, edge: bool = True, spec: float = 1.6) -> Image.Image:
    m = ell(icon, cx, cy, r)
    c = rgb(color)
    hi = tuple(int(min(255, v * spec + 30)) for v in c)
    rfill(icon, m, (cx - r * 0.38, cy - r * 0.42), r * 1.55,
          ((0, hi), (0.25, tuple(int(v * 1.1) for v in c)), (0.6, tuple(int(v * 0.72) for v in c)),
           (1, tuple(int(v * 0.3) for v in c))))
    if edge:
        contour(icon, m)
    return m


def contour(icon: Icon, mask: Image.Image, w: int = EDGE_W, color=EDGE) -> None:
    """Dark contour just inside ``mask`` (separates overlapping elements, like vanilla's ink line)."""
    box = _bbox(mask, w + 4)
    if box is None:
        return
    crop = mask.crop(box)
    k = w if w % 2 else w + 1
    ring = ImageChops.subtract(crop, crop.filter(ImageFilter.MinFilter(k)))
    full = Image.new("L", (SIZE, SIZE), 0)
    full.paste(ring, box[:2])
    lay = Image.new("RGBA", (SIZE, SIZE), tuple(color[:3]) + (0,))
    a = np.asarray(full, float) / 255 * (color[3] if len(color) > 3 else 255)
    lay.putalpha(Image.fromarray(a.astype("uint8")))
    icon.image.alpha_composite(lay)


def tint(icon: Icon, mask: Image.Image, clip: Image.Image | None, color, alpha: float, blur: float = 0) -> None:
    """Blurred colour patch kept inside ``clip``."""
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    if clip is not None:
        mask = Icon.intersect(mask, clip)
    icon.shade(mask, color, alpha)


def strokes(icon: Icon, mask: Image.Image, color, alpha: int, angle: float, spacing: float, width: int = 3,
            jitter: float = 0.4, length: tuple[float, float] = (30, 90)) -> None:
    """Short parallel brush strokes inside ``mask`` (parchment hatch, wood grain, fibres)."""
    box = _bbox(mask)
    if box is None:
        return
    x0, y0, x1, y1 = box
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    rnd = icon.random

    def paint(d: ImageDraw.ImageDraw) -> None:
        y = y0 - (x1 - x0)
        while y < y1 + (x1 - x0):
            x = x0 - 40
            while x < x1:
                L = rnd.uniform(*length)
                if rnd.random() > jitter:
                    px, py = x, y + (x - x0) * uy / max(ux, 1e-3)
                    d.line([(px, py), (px + ux * L, py + uy * L)], fill=tuple(rgb(color).astype(int)) + (alpha,),
                           width=width)
                x += L + rnd.uniform(10, 50)
            y += spacing * rnd.uniform(0.7, 1.3)

    icon.overlay(paint, mask)


@contextmanager
def layer(icon: Icon) -> Iterator[dict]:
    """Draw into a fresh transparent layer; the result is in ``holder['image']`` after the block."""
    saved, saved_draw = icon.image, icon.draw
    icon.image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.draw = ImageDraw.Draw(icon.image)
    holder: dict = {}
    try:
        yield holder
    finally:
        holder["image"] = icon.image
        icon.image, icon.draw = saved, saved_draw


def tone_map(img: Image.Image, stops, contrast: float = 1.15, lift: float = 0.0) -> Image.Image:
    """Map an image's value onto a metal ramp (silver or gold); alpha is kept."""
    a = np.asarray(img, float)
    lum = (a[..., :3] @ np.array([0.299, 0.587, 0.114])) / 255
    lum = np.clip((lum - 0.5) * contrast + 0.5 + lift, 0, 1)
    col = ramp(lum, stops)
    out = np.dstack([col, a[..., 3]])
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8"), "RGBA")


def alpha_mask(img: Image.Image, threshold: int = 40) -> Image.Image:
    return img.getchannel("A").point(lambda v: 255 if v > threshold else 0)


# ------------------------------------------------------------------ frames (painted in grey, mapped to metal)
GREY = "#a8a8a8"


def _bevel_band(icon: Icon, outer: Image.Image, inner: Image.Image, w: float) -> None:
    """A metal band between two masks, rounded like a moulding: bright outer lip, dark inner groove."""
    band = subtract(outer, inner)
    icon.fill(band, (226, 226, 226), (96, 96, 96), radial=(X0 - 60, Y0 - 80, 1250), noise=0.10, chroma=0)
    # lit upper-left lip and shadowed lower-right half of the moulding
    tint(icon, offset(inner, -6, -6), band, (255, 255, 255), 0.35, blur=4)
    shadow_half = icon.poly_mask([(CX + 40, 0), (SIZE, 0), (SIZE, SIZE), (0, SIZE), (0, 700)])
    tint(icon, Icon.intersect(band, shadow_half), band, (0, 0, 0), 0.30, blur=10)
    contour(icon, outer, 6)


def charter_frame(icon: Icon) -> None:
    """Plain steel rim with three rivets (charter)."""
    outer = icon.poly_mask(shield_pts(0))
    inner = icon.poly_mask(shield_pts(RIM["charter"]))
    _bevel_band(icon, outer, inner, RIM["charter"])
    # a groove line in the middle of the rim
    icon.outline(shield_pts(RIM["charter"] * 0.5), 3, (60, 60, 60, 110))
    for x, y in ((X0 + 10, Y0 + 10), (X1 - 10, Y0 + 10), (CX, Y1 - 15), (CX, Y0 + 10)):
        ball(icon, x, y, 9, (180, 180, 180), edge=False)


def _volute(icon: Icon, edge_x: float, cy: float, r: float, side: int) -> Image.Image:
    """C-scroll on the side of the cartouche: a band leaving the frame, curling down into a round eye."""
    o = side
    pts = bezier((edge_x, cy - r * 0.9), (edge_x + o * r * 1.5, cy - r * 1.6), (edge_x + o * r * 2.1, cy + r * 0.2),
                 (edge_x + o * r * 1.2, cy + r * 0.45), 24)
    pts += bezier(pts[-1], (edge_x + o * r * 0.7, cy + r * 0.6), (edge_x + o * r * 0.75, cy), (edge_x + o * r * 1.15, cy), 10)[1:]
    m = union(line_mask(icon, pts, r * 0.42), ell(icon, pts[-1][0], pts[-1][1], r * 0.32),
              line_mask(icon, [(edge_x, cy - r * 0.9), (edge_x, cy + r * 0.9)], r * 0.5))
    return m


def rights_frame(icon: Icon) -> Image.Image:
    """Gold cartouche: thick moulded band, crest on top, side volutes, toothed lower rim, pendant drop.

    Returns the ornament mask (outside the plain shield) so the caller can shadow props with it."""
    band_outer = icon.poly_mask(shield_pts(-GOLD_OUT))
    inner = icon.poly_mask(shield_pts(RIM["rights"]))
    pts = shield_pts(-GOLD_OUT - 6)
    # teeth along the lower curve (cog rim like vanilla royal rights)
    lower = [p for p in pts if p[1] > Y0 + (Y1 - Y0) * SHOULDER + 40]
    teeth = Image.new("L", (SIZE, SIZE), 0)
    acc = 0.0
    for a, b in zip(lower, lower[1:]):
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
        if acc > 50:
            acc = 0
            teeth = union(teeth, ell(icon, b[0], b[1], 21))
    # side volutes at the upper sides and small ones lower down
    vol = union(_volute(icon, X0 - GOLD_OUT + 6, Y0 + 150, 58, -1), _volute(icon, X1 + GOLD_OUT - 6, Y0 + 150, 58, 1),
                _volute(icon, X0 - GOLD_OUT + 8, Y0 + 420, 40, -1), _volute(icon, X1 + GOLD_OUT - 8, Y0 + 420, 40, 1))
    # crest: a bar with rolled ends and a central knob
    ct = Y0 - GOLD_OUT
    crest = union(icon.mask("rounded_rectangle", (CX - 150, ct - 40, CX + 150, ct + 6), radius=16),
                  ell(icon, CX - 150, ct - 26, 26), ell(icon, CX + 150, ct - 26, 26),
                  icon.mask("rounded_rectangle", (CX - 52, ct - 84, CX + 52, ct - 20), radius=20),
                  ell(icon, CX, ct - 92, 22))
    drop = union(ell(icon, CX, Y1 + 34, 26), icon.poly_mask([(CX - 30, Y1 - 10), (CX + 30, Y1 - 10), (CX, Y1 + 30)]))
    orn = union(teeth, vol, crest, drop)
    icon.fill(orn, (232, 232, 232), (92, 92, 92), radial=(X0 - 80, Y0 - 120, 1300), noise=0.12, chroma=0)
    # model the ornaments: a lit top-left edge and a dark bottom-right edge on every piece
    tint(icon, subtract(orn, offset(orn, 8, 8)), orn, (255, 255, 255), 0.45, blur=3)
    tint(icon, subtract(orn, offset(orn, -9, -9)), orn, (0, 0, 0), 0.45, blur=3)
    contour(icon, orn, 6)
    _bevel_band(icon, band_outer, inner, GOLD_OUT + RIM["rights"])
    icon.outline(shield_pts(RIM["rights"] * 0.2 - GOLD_OUT * 0.45), 4, (50, 50, 50, 120))
    for x, y in ((X0 - 2, Y0 - 2), (X1 + 2, Y0 - 2)):
        ball(icon, x, y, 14, (200, 200, 200), edge=True)
    return union(orn, band_outer)


# ------------------------------------------------------------------ field
def paint_field(icon: Icon, tincture) -> Image.Image:
    """Shield field in the good's tincture with parchment hatch and an inner bevel shadow."""
    inset = icon._pp_rim
    m = icon.poly_mask(shield_pts(inset))
    c = rgb(tincture)
    lum = float(c @ np.array([0.299, 0.587, 0.114]))
    light = tuple(int(min(255, v * 1.28 + 16)) for v in c)
    dark = tuple(int(v * 0.72) for v in c)
    icon.fill(m, light, dark, radial=(X0 + 40, Y0 + 30, 980), noise=0.10, chroma=0.05)
    # diagonal hatch (vanilla parchment fields carry fine diagonal strokes)
    hatch = (255, 250, 236) if lum < 150 else (120, 104, 84)
    strokes(icon, m, hatch, 20 if lum < 150 else 30, -32, 8, 2, 0.35, (30, 110))
    strokes(icon, m, (0, 0, 0), 14, -32, 15, 2, 0.55, (20, 70))
    # inner bevel: shadow below the rim, lighter lip at the bottom right
    ring = subtract(m, icon.poly_mask(shield_pts(inset + 34)))
    tint(icon, ring, m, (0, 0, 0), 0.40, blur=16)
    tint(icon, offset(subtract(m, offset(m, 10, 12)), 0, 0), m, (0, 0, 0), 0.35, blur=4)
    contour(icon, m, 6)
    return m


# ------------------------------------------------------------------ composition
def compose(good, tier: str, seed: int = 7) -> Icon:
    """Draw one icon: ``good`` is a module with FIELD, props(icon, k) and charge(icon, k)."""
    icon = Icon(seed=getattr(good, "SEED", seed))
    icon._pp_rim = RIM[tier]
    icon._pp_tier = tier
    # 1. metal layer: props, then the frame
    with layer(icon) as metal:
        good.props(icon, _K)
        shield_outer = icon.poly_mask(shield_pts(-GOLD_OUT if tier == "rights" else 0))
        # the shield casts a soft shadow onto the props behind it
        tint(icon, offset(shield_outer, 16, 22), None, (0, 0, 0), 0.55, blur=18)
        if tier == "rights":
            rights_frame(icon)
        else:
            charter_frame(icon)
    metal_img = tone_map(metal["image"], GOLD if tier == "rights" else SILVER,
                         contrast=1.2, lift=0.04 if tier == "rights" else 0.05)
    icon.image.alpha_composite(metal_img)
    # 2. field
    field = paint_field(icon, good.FIELD)
    # 3. charge
    with layer(icon) as ch:
        good.charge(icon, _K)
    cimg = ch["image"]
    cm = cimg.getchannel("A")
    tint(icon, offset(cm, 14, 20), field, (0, 0, 0), 0.5, blur=14)
    icon.image.alpha_composite(cimg)
    return icon


class _Kit:
    """Namespace handed to goods modules (``k``): this module's helpers and constants."""

    def __getattr__(self, name):
        return globals()[name]


_K = _Kit()


def finish(icon: Icon) -> dict[int, Image.Image]:
    """Grade, outline and downscale (no re-placement: every icon of the family keeps the same frame size)."""
    g = GRADE
    art = grade(icon.image, g["mute"], g["gamma"], g["light"])
    art = rim(soften(art, g["soften"]), g["rim"])
    # one fixed scale for the whole family, so every icon keeps the same frame size and a margin like vanilla
    small_art = art.resize((round(SIZE * FIT), round(SIZE * FIT)), Image.LANCZOS)
    art = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    art.alpha_composite(small_art, ((SIZE - small_art.width) // 2, (SIZE - small_art.height) // 2 - FIT_RAISE))
    full = outline(art)
    # soft drop shadow down-right, like vanilla town right icons
    sil = full.getchannel("A").filter(ImageFilter.GaussianBlur(10))
    sh = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    sh.putalpha(offset(sil, 10, 14).point(lambda v: int(v * 0.55)))
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.alpha_composite(sh)
    out.alpha_composite(full)
    small = out.resize((128, 128), Image.LANCZOS).filter(ImageFilter.UnsharpMask(0.8, 60, 2))
    return {1024: out, 128: small}


# ------------------------------------------------------------------ prop layouts
def crossed(icon: Icon, draw_one: Callable) -> None:
    """Draw one prop twice as a saltire behind the shield: draw_one(icon, loc, mirror) where
    loc(points) maps local (across, along) points, along 0 = butt at the bottom, CROSS_LEN = tip at the top."""
    for (base, head), mirror in ((CROSS_L, False), (CROSS_R, True)):
        draw_one(icon, lambda pts, b=base, h=head, m=mirror: along(b, h, pts, m), mirror)


def flank(icon: Icon, draw_one: Callable) -> None:
    """Draw one prop on each side of the shield: draw_one(icon, sx, mirror) with sx(x) mapping an x of the
    left-hand prop to the right-hand side when mirrored."""
    for mirror in (False, True):
        draw_one(icon, (lambda x: 2 * CX - x) if mirror else (lambda x: x), mirror)


def block(icon: Icon, pts: Sequence[Point], color, edge: bool = True, light: float = 1.35, dark: float = 0.45,
          noise: float = 0.14) -> Image.Image:
    """Polygon lit from the upper left (lighter top-left corner, darker bottom-right)."""
    m = icon.poly_mask(pts)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    c = rgb(color)
    L = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    dfill(icon, m, (min(xs), min(ys)), (1, 1.2), L * 0.9,
          ((0, tuple(int(min(255, v * light + 10)) for v in c)), (0.45, tuple(int(v) for v in c)),
           (1, tuple(int(v * dark) for v in c))), noise)
    if edge:
        contour(icon, m)
    return m


def fade(icon: Icon, mask: Image.Image, factor: float) -> None:
    """Multiply the alpha inside mask (transparent glass on a charge layer)."""
    a = np.asarray(icon.image.getchannel("A"), float)
    m = np.asarray(mask, float) / 255
    a = a * (1 - m * (1 - factor))
    icon.image.putalpha(Image.fromarray(np.clip(a, 0, 255).astype("uint8")))


def path_points(pts: Sequence[Point], step: float) -> list[tuple[Point, Point]]:
    """Evenly spaced (point, unit tangent) samples along a polyline."""
    p = np.array(pts, float)
    seg = np.hypot(*np.diff(p, axis=0).T)
    ends = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for d in np.arange(0, ends[-1] + 1e-6, step):
        i = min(int(np.searchsorted(ends, d, side="right")) - 1, len(seg) - 1)
        if seg[i] == 0:
            continue
        t = (d - ends[i]) / seg[i]
        q = p[i] + (p[i + 1] - p[i]) * t
        u = (p[i + 1] - p[i]) / seg[i]
        out.append(((float(q[0]), float(q[1])), (float(u[0]), float(u[1]))))
    return out


def rope(icon: Icon, pts: Sequence[Point], w: float, color=(176, 140, 92)) -> Image.Image:
    """Twisted rope along a polyline: a shaded band with diagonal strand grooves."""
    m = line_mask(icon, pts, w)
    c = rgb(color)
    icon.fill(m, tuple(int(min(255, v * 1.2)) for v in c), tuple(int(v * 0.6) for v in c),
              (min(p[1] for p in pts) - w, max(p[1] for p in pts) + w), noise=0.2)

    def grooves(d: ImageDraw.ImageDraw) -> None:
        for (x, y), (ux, uy) in path_points(pts, w * 0.45):
            px, py = -uy, ux
            a = (x + px * w * 0.55 - ux * w * 0.25, y + py * w * 0.55 - uy * w * 0.25)
            b = (x - px * w * 0.55 + ux * w * 0.25, y - py * w * 0.55 + uy * w * 0.25)
            d.line([a, b], fill=(40, 26, 12, 170), width=max(3, int(w * 0.13)))
            d.line([(a[0] + ux * 5, a[1] + uy * 5), (b[0] + ux * 5, b[1] + uy * 5)], fill=(255, 240, 210, 70),
                   width=max(2, int(w * 0.08)))

    icon.overlay(grooves, m)
    contour(icon, m, 5)
    return m


def pearls(icon: Icon, pts: Sequence[Point], r: float, color=(200, 200, 200), gap: float = 1.9) -> None:
    for (x, y), _ in path_points(pts, r * gap):
        ball(icon, x, y, r, color)


def rotated(pts: Sequence[Point], origin: Point, degrees: float) -> list[Point]:
    """Local points (x along, y across) rotated by degrees and moved to origin."""
    return Icon.rotate(pts, origin, degrees)
