"""Topography icons for the three river channel topographies, drawn in the vanilla style.

Vanilla topography icons (main_menu/gfx/interface/topography/*.dds) are 64x64 sepia landscape vignettes cut into a
bowl: a flat horizon on top, a round bottom, a black outline; the location view puts them into the climate frame.
This script paints each scene at 4x, reduces it and writes `<topography>.png` next to itself; the constructor
(navigation.write_topographies) converts them into the mod's DDS files.

    uv run python assets/icons/topography/draw.py
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 256                      # working size (4x the 64 px icon)
OUT = 64
CX, CY, R = 124, 120, 104    # the bowl: a circle below a horizon (vanilla silhouettes: x 5..57, y 20..56)
HORIZON = 80
BOTTOM = CY + R
HERE = Path(__file__).resolve().parent

# sepia ramp measured on the vanilla icons (dark rim .. bright highlight)
DARK = np.array([40, 34, 26], float)
MID = np.array([140, 126, 100], float)
LIGHT = np.array([212, 202, 176], float)
BRIGHT = np.array([250, 246, 230], float)

Y, X = np.mgrid[0:S, 0:S].astype(float)


def at(f: float) -> float:
    """Screen y a fraction of the way from the horizon (0) to the bottom of the bowl (1)."""
    return HORIZON + f * (BOTTOM - HORIZON)


def ramp(t: np.ndarray) -> np.ndarray:
    """0 = dark, 0.5 = mid, 0.8 = light, 1 = bright."""
    t = np.clip(t, 0, 1)[..., None]
    a = np.where(t < 0.5, DARK + (MID - DARK) * (t / 0.5), 0)
    b = np.where((t >= 0.5) & (t < 0.8), MID + (LIGHT - MID) * ((t - 0.5) / 0.3), 0)
    c = np.where(t >= 0.8, LIGHT + (BRIGHT - LIGHT) * ((t - 0.8) / 0.2), 0)
    return a + b + c


def noise(seed: int, sx: float, sy: float) -> np.ndarray:
    """Smooth noise with features sx by sy pixels (horizontal striations when sx > sy), roughly -1..1."""
    rng = np.random.default_rng(seed)
    img = Image.fromarray((rng.random((S, S)) * 255).astype(np.uint8))
    img = img.resize((max(2, int(S / sx)), max(2, int(S / sy))), Image.BILINEAR).resize((S, S), Image.BICUBIC)
    a = np.asarray(img, float) / 127.5 - 1
    return a / max(1e-6, np.abs(a).max())


def mask(draw_fn) -> np.ndarray:
    im = Image.new("L", (S, S), 0)
    draw_fn(ImageDraw.Draw(im))
    return np.asarray(im, float) / 255


def soft(m: np.ndarray, r: float) -> np.ndarray:
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), float) / 255


def depth() -> np.ndarray:
    return np.clip((Y - HORIZON) / (BOTTOM - HORIZON), 0, 1)


def bowl(horizon: np.ndarray) -> np.ndarray:
    """The icon silhouette: inside the circle and below the horizon line (one y per column)."""
    inside = (X - CX) ** 2 + (Y - CY) ** 2 <= R * R
    return (inside & (Y >= horizon[None, :])).astype(float)


def horizon_line(seed: int, amp: float) -> np.ndarray:
    return HORIZON + amp * noise(seed, 36, 36)[S // 2] + 0.5 * amp * noise(seed + 1, 12, 12)[S // 2]


def land(seed: int) -> np.ndarray:
    """Banks: light towards the horizon, dark in the foreground, horizontal field striations and grain."""
    d = depth()
    return (0.66 - 0.44 * d ** 1.2 + 0.09 * noise(seed, 20, 3) + 0.06 * noise(seed + 1, 6, 2)
            + 0.07 * noise(seed + 2, 3, 1.2) + 0.04 * noise(seed + 3, 1.2, 1.2))


def water(seed: int, fade: float = 0.2) -> np.ndarray:
    """Calm water: bright, horizontal glints, a little darker towards the viewer."""
    return 0.88 - fade * depth() + 0.07 * noise(seed, 30, 1.5) + 0.05 * noise(seed + 7, 8, 1.2)


def river(center, width, y0: float, y1: float, steps: int = 60) -> np.ndarray:
    left, right = [], []
    for i in range(steps + 1):
        y = y0 + (y1 - y0) * i / steps
        c, w = center(y), width(y)
        left.append((c - w / 2, y))
        right.append((c + w / 2, y))
    return soft(mask(lambda d: d.polygon(left + right[::-1], fill=255)), 1.2)


def banks(tone: np.ndarray, water_mask: np.ndarray, strength: float = 0.3) -> np.ndarray:
    """Dark wet edge where land meets water."""
    return tone - strength * np.clip(soft(water_mask, 3) - water_mask, 0, 1) * 1.6


def finish(tone: np.ndarray, alpha: np.ndarray, name: str) -> Path:
    rgba = np.dstack([ramp(tone), alpha * 255]).clip(0, 255).astype(np.uint8)
    small = Image.fromarray(rgba, "RGBA").resize((OUT, OUT), Image.LANCZOS)
    solid = np.asarray(small.getchannel("A"), float) > 110
    as_img = Image.fromarray((solid * 255).astype(np.uint8))
    grown = np.asarray(as_img.filter(ImageFilter.MaxFilter(3)), float) > 0
    shrunk = np.asarray(as_img.filter(ImageFilter.MinFilter(3)), float) > 0
    px = np.asarray(small, float).copy()
    px[..., 3] = np.where(solid, 255, 0)
    px[solid & ~shrunk, :3] *= 0.7          # slight bevel just inside the outline
    px[grown & ~solid] = [14, 11, 8, 255]   # the black outline around the silhouette, as on the vanilla icons
    out = HERE / f"{name}.png"
    Image.fromarray(px.clip(0, 255).astype(np.uint8), "RGBA").save(out)
    return out


# --- Navigable River: a broad calm river winding through flat banks, a sail on it -------------------------------

def navigable() -> Path:
    alpha = bowl(horizon_line(3, 7))
    center = lambda y: CX + 30 * math.sin((y - HORIZON) / (BOTTOM - HORIZON) * math.pi * 1.3 + 0.2)
    width = lambda y: 8 + 0.62 * (y - HORIZON)
    riv = river(center, width, HORIZON, S)
    tone = banks(land(10) * (1 - riv) + water(20) * riv, riv)
    # a boat with a square sail mid-river
    y = at(0.5)
    c = center(y) + 4
    sail = mask(lambda d: d.polygon([(c - 2, y - 34), (c + 18, y - 30), (c + 16, y - 5), (c - 2, y - 5)], fill=255))
    hull = mask(lambda d: d.polygon([(c - 17, y - 5), (c + 22, y - 5), (c + 14, y + 5), (c - 10, y + 5)], fill=255))
    mast = mask(lambda d: d.line([(c - 3, y - 42), (c - 3, y)], fill=255, width=4))
    tone = np.where(sail > 0.5, 0.97 - 0.3 * np.clip((X - c) / 18, 0, 1), tone)
    tone = np.where(np.maximum(hull, mast) > 0.5, 0.1, tone)
    shadow = soft(mask(lambda d: d.rectangle([c - 12, y + 6, c + 16, y + 13], fill=255)), 2.5)
    tone -= 0.3 * shadow * riv
    return finish(tone, alpha, "pp_river_channel")


# --- Shallows: the river breaks over gravel bars and a weir ----------------------------------------------------

def shallows() -> Path:
    alpha = bowl(horizon_line(5, 7))
    center = lambda y: CX - 14 + 24 * math.sin((y - HORIZON) / (BOTTOM - HORIZON) * math.pi + 0.7)
    width = lambda y: 12 + 0.72 * (y - HORIZON)
    riv = river(center, width, HORIZON, S)
    # shallow water: short, busy ripples
    wet = 0.62 - 0.14 * depth() + 0.1 * noise(40, 5, 1.3) + 0.05 * noise(41, 2.5, 1)
    wet = np.where(noise(42, 4, 1.1) > 0.35, 0.95, wet)   # white ripples breaking over the shoals
    tone = banks(land(30) * (1 - riv) + wet * riv, riv)
    # gravel bars: pale islands, lit on top and shaded along their lower edge, with pebble grain
    for off, f, w, h in ((-0.22, 0.2, 30, 8), (0.25, 0.44, 44, 11), (-0.18, 0.8, 64, 15)):
        y = at(f)
        c = center(y) + off * width(y)
        bar = soft(mask(lambda d: d.ellipse([c - w / 2, y - h / 2, c + w / 2, y + h / 2], fill=255)), 1.4) * riv
        lit = 0.9 - 0.25 * np.clip((Y - (y - h / 2)) / h, 0, 1) + 0.05 * noise(50 + int(f * 100), 1.6, 1.6)
        lit = np.where(noise(70 + int(f * 100), 1.4, 1.4) > 0.45, 0.35, lit)   # pebbles
        tone = tone * (1 - bar) + lit * bar
        tone -= 0.25 * np.clip(soft(bar, 2.5) - bar, 0, 1) * 1.5 * (Y > y)
    # a weir across the river: dark crest with white water spilling below it
    y = at(0.62)
    x0, x1 = center(y) - width(y) / 2, center(y) + width(y) / 2
    foam = soft(mask(lambda d: d.line([(x0, y + 12), (x1, y)], fill=255, width=10)), 2.5)
    tone = tone * (1 - foam * riv) + 1.0 * foam * riv
    crest = mask(lambda d: d.line([(x0, y + 5), (x1, y - 7)], fill=255, width=5))
    tone = np.where(crest * riv > 0.5, 0.16, tone)
    return finish(tone, alpha, "pp_river_shallows")


# --- Falls: the river drops over a rock ledge into a spray-filled pool ------------------------------------------

def falls() -> Path:
    alpha = bowl(horizon_line(9, 6))
    ledge_y = lambda x: at(0.36) + 6 * math.sin(x / 30) - 0.1 * (x - CX)
    face_h = 0.3 * (BOTTOM - HORIZON)
    top = np.array([ledge_y(x) for x in range(S)])[None, :]
    # upper river on the plateau, narrowing to the lip of the falls
    center = lambda y: CX + 4 + 0.12 * (y - HORIZON)
    width = lambda y: 8 + 0.5 * (y - HORIZON)
    upper = river(center, width, HORIZON, ledge_y(CX) + 2)
    plateau = land(60) + 0.14 * (Y < top)   # the plateau above the ledge is lit, the valley below lies in shade
    tone = banks(plateau * (1 - upper) + water(61, 0.05) * upper, upper)
    # the rock face: dark, with vertical cracks and a lit top edge
    face = ((Y >= top) & (Y < top + face_h)).astype(float)
    rock = 0.1 + 0.1 * noise(62, 1.5, 14) + 0.05 * noise(63, 3, 3) + 0.45 * np.clip(1 - (Y - top) / 7, 0, 1)
    tone = tone * (1 - face) + rock * face
    # the falling water: bright vertical streaks as wide as the river at the lip, flaring slightly as it falls
    lip = ledge_y(CX)
    c, w = center(lip), width(lip)
    spread = np.clip((Y - top) / face_h, 0, 1)
    sheet = (np.abs(X - c) < w / 2 + 6 * spread) & (Y >= top - 2) & (Y < top + face_h + 4)
    tone = np.where(sheet, 0.86 + 0.13 * noise(64, 0.8, 16), tone)
    # plunge pool and a cloud of spray at the foot
    foot = lip + face_h
    pool = soft(mask(lambda d: d.ellipse([c - w - 14, foot - 6, c + w + 18, foot + 34], fill=255)), 2)
    tone = tone * (1 - pool) + (water(65, 0.3) - 0.08) * pool
    tone = banks(tone, pool, 0.25)
    spray = soft(mask(lambda d: d.ellipse([c - w / 2 - 12, foot - 14, c + w / 2 + 14, foot + 10], fill=255)), 6)
    tone = tone * (1 - spray) + 1.0 * spray
    return finish(tone, alpha, "pp_river_falls")


def main() -> None:
    for fn in (navigable, shallows, falls):
        print(fn())


if __name__ == "__main__":
    main()
