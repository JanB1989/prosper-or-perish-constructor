"""Academy of Sciences (advance icon pp_academy_of_sciences_advance): a still life of a learned society. A brass
armillary sphere on a turned walnut stand stands behind a long refractor telescope of red leather and brass; in front
lies the society's open book of memoirs, a Sun-centred system of the planets drawn on one page and the observations
written on the other, the royal charter's red wax seal hanging from it on its ribbons.

Advance icons are still lifes without the building icons' black outline (vanilla efficient_mining, debt_and_loans),
256 px, transparent; the game cuts their lower corners round (``advance_icon_mask``), so the foot stays narrow. The
DDS goes where the game reads advance icons. Run from the constructor:

  uv run python assets/icon_drawings/pp_academy_of_sciences_advance/draw.py [--preview <png>] [--png <png>]

Objects are painted on their own layers, the book flat from above and tipped into view with a perspective warp
(``tip``), and laid together back to front; front objects shade the ones behind (``cast``). The armillary sphere is
the building icon's (true circles in 3D, far halves first); local helpers: ``armillary``, ``turned_wood``,
``telescope``, ``open_book``, ``seal``, ``bevel``, ``text_block``, ``contour``.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from eu5_building_pipeline.dds import encode_dds, fit
from eu5_building_pipeline.iconkit import Icon
from eu5_building_pipeline.iconkit.finalize import grade, rim, soften

SEED = 83
SIDE = 256  # interface_dds.ADVANCE_MAX_SIDE
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "mod/pp/main_menu/gfx/interface/advance/pp_academy_of_sciences_advance.dds"
SERIF = ("/usr/share/fonts/opentype/urw-base35/P052-Roman.otf", "/usr/share/fonts/opentype/urw-base35/C059-Roman.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
SERIF_BOLD = ("/usr/share/fonts/opentype/urw-base35/P052-Bold.otf", "/usr/share/fonts/opentype/urw-base35/C059-Bold.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
ITALIC = ("/usr/share/fonts/opentype/urw-base35/P052-Italic.otf", "/usr/share/fonts/opentype/urw-base35/C059-Italic.otf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf")
INK = (44, 28, 16)
EDGE = (36, 22, 12, 230)
BRASS = ("#f8d88c", "#6a4210")
NOTES = ("Of the spots seen", "on the face of the Sun,", "of the four Moons", "of Jupiter and their", "periods, and of the",
         "Ring of Saturn.")


def font(paths, size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- layers
def layer(seed: int) -> Icon:
    """A fresh canvas for one object, drawn around the canvas centre."""
    return Icon(seed=seed)


def tip(img: Image.Image, src, dst) -> Image.Image:
    """Perspective warp: the quad ``src`` of ``img`` lands on the quad ``dst``."""
    rows = []
    for (xs, ys), (xd, yd) in zip(src, dst):
        rows.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
        rows.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd])
    coeffs = np.linalg.solve(np.array(rows, float), np.array(src, float).reshape(8))
    return img.transform(img.size, Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def turned(img: Image.Image, degrees: float, at) -> Image.Image:
    return img.rotate(degrees, resample=Image.BICUBIC, center=(512, 512), translate=(at[0] - 512, at[1] - 512))


def cast(ic: Icon, placed: Image.Image, dx: float, dy: float, blur: float, alpha: float) -> None:
    """Shadow of an object that is about to be laid on top, falling onto what is already there."""
    m = ImageChops.offset(placed.getchannel("A"), int(dx), int(dy))
    ic.shade(m, (12, 6, 2), alpha, blur=blur)


def bevel(ic: Icon, mask: Image.Image, width: int = 12, lit: float = 0.35, dark: float = 0.45) -> None:
    """Rounded edge on a flat object: light along the upper left rim, shade along the lower right rim."""
    inner = mask.filter(ImageFilter.MinFilter(width | 1))
    ring = ImageChops.subtract(mask, inner)
    up = ImageChops.subtract(ring, ImageChops.offset(ring, -width // 2, -width // 2))
    down = ImageChops.subtract(ring, ImageChops.offset(ring, width // 2, width // 2))
    ic.shade(ic.intersect(up, mask), (255, 238, 206), lit, blur=2)
    ic.shade(ic.intersect(down, mask), (14, 8, 4), dark, blur=2)


def text_block(size, lines, blur: float = 0.6) -> Image.Image:
    """Text on a transparent sheet: ``lines`` = [(x, y, text, font, colour, anchor), ...]."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, text, f, col, anchor in lines:
        d.text((x, y), text, font=f, fill=col, anchor=anchor)
    return img.filter(ImageFilter.GaussianBlur(blur)) if blur else img


def contour(ob: Icon, alpha: float = 0.85) -> None:
    """Thin dark painted edge round everything on the layer."""
    a = ob.alpha().point(lambda v: 255 if v > 40 else 0)
    ob.shade(ImageChops.subtract(a.filter(ImageFilter.MaxFilter(5)), a), EDGE[:3], alpha, clip=False)


def paste_clipped(ob: Icon, sheet: Image.Image, at, clip: Image.Image) -> None:
    lay = Image.new("RGBA", (ob.size, ob.size), (0, 0, 0, 0))
    lay.paste(sheet, (int(at[0]), int(at[1])))
    ob.image.alpha_composite(Image.composite(lay, Image.new("RGBA", lay.size, (0, 0, 0, 0)), clip))


# ---------------------------------------------------------------- the armillary sphere (as in the building icon)
def _rot(v, axis, deg):
    """Rodrigues rotation of vector ``v`` about the unit ``axis``."""
    v, k = np.array(v, float), np.array(axis, float) / np.linalg.norm(axis)
    a = math.radians(deg)
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * np.dot(k, v) * (1 - math.cos(a))


def armillary(ic: Icon, cx, cy, R, widths=1.0, elev: float = 14, yaw: float = 28, tilt: float = 36) -> None:
    """A brass armillary sphere: horizon and meridian rings with their degree marks, the equator, the broad ecliptic
    band with its twelve signs, the colure and the polar circles round a small earth on the polar axis. Every ring is
    a true circle in 3D, projected from slightly above; the far halves are drawn first and darker (in the sphere's
    shade), the near halves over the earth, each band lit by its facing to the upper-left light."""
    e = math.radians(elev)
    up = np.array([0.0, 1.0, 0.0])
    a = np.array([math.sin(math.radians(tilt)), math.cos(math.radians(tilt)), 0.0])
    m = np.array([0.0, 0.0, 1.0])
    a, m = _rot(a, up, yaw), _rot(m, up, yaw)
    c = np.cross(a, m)
    c /= np.linalg.norm(c)
    light = np.array([-0.6, 0.62, 0.5])
    light /= np.linalg.norm(light)

    def proj(p):
        return (cx + p[0], cy - (p[1] * math.cos(e) - p[2] * math.sin(e))), p[2] * math.cos(e) + p[1] * math.sin(e)

    # (normal, radius, centre, width, ticks)
    rings = [(up, 1.13 * R, np.zeros(3), 26 * widths, 72), (m, 1.05 * R, np.zeros(3), 20 * widths, 48),
             (a, R, np.zeros(3), 14 * widths, 0), (_rot(a, c, 23.5), R, np.zeros(3), 30 * widths, 24),
             (c, R * 0.98, np.zeros(3), 10 * widths, 0), (a, 0.4 * R, a * 0.917 * R, 9 * widths, 0),
             (a, 0.4 * R, -a * 0.917 * R, 9 * widths, 0)]
    items = []  # (depth, kind, payload)
    for normal, r, centre, w, ticks in rings:
        normal = normal / np.linalg.norm(normal)
        ref = np.array([0.0, 0.0, 1.0]) if abs(normal[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(normal, ref)
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        ts = np.linspace(0, 2 * math.pi, 361)[:-1]
        pts3 = [centre + r * (u * math.cos(t) + v * math.sin(t)) for t in ts]
        scr, dep = zip(*[proj(p) for p in pts3])
        dep = np.array(dep)
        front = dep >= 0
        # start the walk where the ring turns from back to front, so every run is contiguous
        k0 = next((i for i in range(len(ts)) if front[i] and not front[i - 1]), 0)
        order = [(k0 + i) % len(ts) for i in range(len(ts) + 1)]
        runs, cur = [], [order[0]]
        for i in order[1:]:
            cur.append(i)  # a run ends on the first point of the other side, so the halves join
            if front[i] != front[cur[0]]:
                runs.append(cur)
                cur = [i]
        if len(cur) > 1:
            runs.append(cur)
        for run in runs:
            side = bool(front[run[0]])
            items.append((float(np.mean(dep[run])) + (0.5 if side else -0.5) * R, "ring",
                          (run, scr, pts3, centre, r, w, ticks, side, len(ts))))
    pa, pb = proj(a * 1.34 * R)[0], proj(-a * 1.34 * R)[0]
    items.append((-0.01, "axis", (pa, pb)))
    items.append((0.0, "earth", None))
    items.sort(key=lambda it: it[0])
    dark, lite = np.array((84, 46, 8), float), np.array((246, 200, 100), float)
    for _, kind, payload in items:
        if kind == "ring":
            run, scr, pts3, centre, r, w, ticks, is_front, n = payload
            pts = [scr[i] for i in run]
            ic.line(pts, int(w + 8), (36, 22, 8, 235))
            shine = []
            for j in range(len(run) - 1):
                i = run[j]
                radial = (pts3[i] - centre) / r
                b = float(np.dot(radial if is_front else -radial, light))
                b = 0.3 + 0.7 * max(0.0, min(1.0, 0.5 + 0.6 * b))
                if not is_front:
                    b *= 0.62
                col = tuple(int(v) for v in dark + (lite - dark) * b) + (255,)
                (x, y), (x2, y2) = scr[i], scr[run[j + 1]]
                ic.draw.line([(x, y), (x2, y2)], fill=col, width=int(w))
                if j:  # round joint, so the band has no notches where the segments meet
                    ic.draw.ellipse((x - w / 2 + 1, y - w / 2 + 1, x + w / 2 - 1, y + w / 2 - 1), fill=col)
                shine.append((x, y) if is_front and b > 0.84 else None)
            stretch = []  # a glint along the brightest stretch of the near half
            for p in shine + [None]:
                if p is not None:
                    stretch.append(p)
                elif len(stretch) > 3:
                    ic.line(stretch[1:-1], max(3, int(w * 0.3)), (255, 248, 216, 220))
                    stretch = []
                else:
                    stretch = []
            if ticks:
                step = max(1, n // ticks)

                def marks(d, run=run, pts3=pts3, centre=centre, r=r, w=w, step=step, n=n):
                    for i in run[:-1]:
                        if i % step:
                            continue
                        radial = (pts3[i] - centre) / r
                        major = (i // step) % (2 if ticks > 30 else 1) == 0
                        k = 0.42 if major else 0.2
                        p, q = proj(pts3[i] - radial * w * k)[0], proj(pts3[i] + radial * w * 0.42)[0]
                        d.line([p, q], fill=(70, 40, 10, 190 if major else 140), width=3 if major else 2)

                ic.overlay(marks)
        elif kind == "axis":
            p, q = payload
            ic.line([p, q], int(9 * widths) + 6, (36, 22, 8, 235))
            ic.line([p, q], int(9 * widths), (110, 104, 96))
            ic.line([(x - 2, y - 2) for x, y in (p, q)], max(2, int(3 * widths)), (200, 196, 188, 200))
            for x, y in (p, q):
                rr = 11 * widths
                ic.ellipse((x - rr, y - rr, x + rr, y + rr), BRASS[0], BRASS[1], edge=3)
        else:
            er = 0.21 * R
            em = ic.mask("ellipse", (cx - er, cy - er, cx + er, cy + er))
            ic.fill(em, "#7cb0c4", "#173444", radial=(cx - er * 0.45, cy - er * 0.5, er * 2.1), noise=0.08)
            for dx, dy, s in ((-0.3, -0.2, 0.4), (0.25, 0.2, 0.35), (0.1, -0.45, 0.25)):
                ic.shade(ic.intersect(ic.mask("ellipse", (cx + er * (dx - s), cy + er * (dy - s * 0.7), cx + er * (dx + s),
                                                          cy + er * (dy + s * 0.7))), em), (170, 140, 80), 0.6, blur=2)
            ic.draw.ellipse((cx - er * 0.6, cy - er * 0.66, cx - er * 0.2, cy - er * 0.32), fill=(230, 246, 250, 255))
            ic.overlay(lambda d: d.ellipse((cx - er, cy - er, cx + er, cy + er), outline=(30, 24, 18, 220), width=4))


def turned_wood(ob: Icon, cx, profile, colors=("#a46a3c", "#2e160a"), brass=()) -> None:
    """A piece turned on the lathe, from its profile [(y, half width), ...]: shaded as a body of revolution (lit left
    of the axis, core shadow right, warm reflected light at the right edge), brass collars at the given y ranges."""
    left = [(cx - hw, y) for y, hw in profile]
    right = [(cx + hw, y) for y, hw in profile[::-1]]
    m = ob.poly_mask(left + right)
    wmax = max(hw for _, hw in profile)
    ob.fill(m, colors[0], colors[1], (cx - wmax * 0.5, cx + wmax), vertical=False, noise=0.12, chroma=0.05)
    hi = [(cx - hw * 0.52, y) for y, hw in profile] + [(cx - hw * 0.2, y) for y, hw in profile[::-1]]
    ob.shade(ob.intersect(ob.poly_mask(hi), m), (255, 232, 196), 0.32, blur=5)
    rl = [(cx + hw * 0.78, y) for y, hw in profile] + [(cx + hw, y) for y, hw in profile[::-1]]
    ob.shade(ob.intersect(ob.poly_mask(rl), m), (200, 130, 70), 0.22, blur=4)
    for y0, y1 in brass:
        bm = ob.intersect(m, ob.mask("rectangle", (0, y0, ob.size, y1)))
        ob.fill(bm, BRASS[0], BRASS[1], (cx - wmax * 0.5, cx + wmax), vertical=False, noise=0.06)
        ob.shade(ob.intersect(ob.poly_mask(hi), bm), (255, 250, 220), 0.5, blur=3)
    ob.overlay(lambda d: d.line(left + right + [left[0]], fill=EDGE, width=4))


def stand(ob: Icon, cx, top) -> None:
    """The sphere's stand: a brass cradle on a walnut baluster, a round foot on a stepped base."""
    y = top
    base = [(y + 210, 112), (y + 232, 130), (y + 250, 130)]
    foot = ob.mask("ellipse", (cx - 130, y + 222, cx + 130, y + 278))
    ob.fill(foot, "#7a4a28", "#24100a", (cx - 70, cx + 130), vertical=False, noise=0.1)
    ob.overlay(lambda d: d.ellipse((cx - 130, y + 222, cx + 130, y + 278), outline=EDGE, width=4))
    turned_wood(ob, cx, base)
    top_face = ob.mask("ellipse", (cx - 112, y + 192, cx + 112, y + 230))
    ob.fill(top_face, "#b47a48", "#5a3418", radial=(cx - 50, y + 196, 200), noise=0.1)
    ob.overlay(lambda d: d.ellipse((cx - 112, y + 192, cx + 112, y + 230), outline=EDGE, width=4))
    prof = [(y, 30), (y + 16, 36), (y + 34, 24), (y + 50, 18), (y + 70, 30), (y + 104, 44), (y + 140, 40), (y + 166, 22),
            (y + 186, 28), (y + 204, 60), (y + 214, 60)]
    turned_wood(ob, cx, prof, brass=((y, y + 34), (y + 182, y + 192)))


def telescope(ob: Icon, x0, x1, cy) -> None:
    """A long refractor lying on its side: brass eyepiece and draw tubes at the left, a tapering tube of red leather
    with gilt tooling and brass bands, a brass dew cap at the right with the dark objective lens in its end."""
    def cyl(xa, xb, ra, rb, colors, gilt=False):
        q = [(xa, cy - ra), (xb, cy - rb), (xb, cy + rb), (xa, cy + ra)]
        mk = ob.poly_mask(q)
        r = max(ra, rb)
        ob.fill(mk, colors[0], colors[1], (cy - r * 0.55, cy + r), noise=0.08, chroma=0.04)
        ob.shade(ob.intersect(ob.poly_mask([(xa, cy - ra * 0.72), (xb, cy - rb * 0.72), (xb, cy - rb * 0.38),
                                            (xa, cy - ra * 0.38)]), mk), (255, 246, 220), 0.45, blur=3)
        ob.shade(ob.intersect(ob.poly_mask([(xa, cy + ra * 0.7), (xb, cy + rb * 0.7), (xb, cy + rb), (xa, cy + ra)]), mk),
                 (220, 150, 80), 0.18, blur=3)
        if gilt:
            ob.overlay(lambda d: [d.line([(x, cy - ra * 0.9), (x, cy + ra * 0.9)], fill=(236, 190, 96, 150), width=3)
                                  for x in (xa + 14, xa + 22, xb - 22, xb - 14)], mk)
            ob.overlay(lambda d: [d.line([(x, cy - ra * 0.6), (x + 10, cy - ra * 0.45)], fill=(236, 190, 96, 110), width=2)
                                  for x in np.arange(xa + 40, xb - 40, 24)], mk)
        ob.overlay(lambda d: d.line(q + [q[0]], fill=EDGE, width=4))

    L = x1 - x0
    xs = [x0, x0 + L * 0.04, x0 + L * 0.13, x0 + L * 0.22, x0 + L * 0.245, x0 + L * 0.87, x1]
    cyl(xs[0], xs[1], 17, 17, BRASS)  # eyepiece cap
    cyl(xs[1], xs[2], 20, 20, ("#fae6ac", "#7a5418"))  # second draw tube
    cyl(xs[2], xs[3], 26, 26, ("#f6dc98", "#704a14"))  # first draw tube
    cyl(xs[3], xs[4], 36, 36, BRASS)  # collar
    tube_x = np.linspace(xs[4], xs[5], 4)
    radii = np.linspace(33, 44, 4)
    for k in range(3):
        cyl(tube_x[k], tube_x[k + 1], radii[k], radii[k + 1], ("#b0503a", "#3e140a"), gilt=True)
    for k in (1, 2):
        rr = radii[k] + 5
        cyl(tube_x[k] - 9, tube_x[k] + 9, rr, rr, BRASS)
    cyl(xs[5], xs[6], 50, 50, BRASS)  # dew cap
    ob.overlay(lambda d: [d.line([(x, cy - 46), (x, cy + 46)], fill=(110, 70, 20, 160), width=3)
                          for x in (xs[5] + 14, xs[6] - 14)])
    end = (x1 - 14, cy - 50, x1 + 14, cy + 50)
    ob.fill(ob.mask("ellipse", end), "#f2cf7e", "#7a5014", (cy - 50, cy + 50), noise=0.06)
    ob.fill(ob.mask("ellipse", (x1 - 8, cy - 38, x1 + 8, cy + 38)), "#2c3a4a", "#080a10", (cy - 38, cy + 38), noise=0.04)
    ob.draw.ellipse((x1 - 4, cy - 30, x1 + 2, cy - 14), fill=(190, 210, 226, 255))
    ob.overlay(lambda d: d.ellipse(end, outline=EDGE, width=4))
    contour(ob)


def orbits(size, ink) -> Image.Image:
    """A copperplate of the Sun-centred system: the Sun with its rays, six planets on their circles, the Moon round
    the Earth, a ring of the zodiac's divisions round it all."""
    s = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    c = size / 2
    rz = size * 0.47
    d.ellipse((c - rz, c - rz, c + rz, c + rz), outline=ink + (220,), width=3)
    d.ellipse((c - rz * 0.9, c - rz * 0.9, c + rz * 0.9, c + rz * 0.9), outline=ink + (200,), width=2)
    for k in range(36):
        a = k * math.pi / 18
        r0 = rz * (0.9 if k % 3 == 0 else 0.95)
        d.line([(c + math.cos(a) * r0, c + math.sin(a) * r0), (c + math.cos(a) * rz, c + math.sin(a) * rz)],
               fill=ink + (200,), width=2)
    for k, (f, ang) in enumerate(((0.16, 40), (0.27, 200), (0.4, 310), (0.53, 120), (0.67, 250), (0.8, 20))):
        r = rz * f
        d.ellipse((c - r, c - r, c + r, c + r), outline=ink + (190,), width=2)
        px, py = c + math.cos(math.radians(ang)) * r, c + math.sin(math.radians(ang)) * r
        pr = 6 if k in (3, 4) else 5
        d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=ink + (235,))
        if k == 2:  # the Moon round the Earth
            d.ellipse((px - 14, py - 14, px + 14, py + 14), outline=ink + (170,), width=2)
            d.ellipse((px + 10, py - 4, px + 16, py + 2), fill=ink + (220,))
        if k == 4:  # Saturn's ring
            d.ellipse((px - 13, py - 5, px + 13, py + 5), outline=ink + (220,), width=2)
    for k in range(16):
        a = k * math.pi / 8
        d.line([(c + math.cos(a) * 12, c + math.sin(a) * 12), (c + math.cos(a) * (22 if k % 2 else 28),
                                                               c + math.sin(a) * (22 if k % 2 else 28))],
               fill=(176, 110, 30, 230), width=3)
    d.ellipse((c - 12, c - 12, c + 12, c + 12), fill=(214, 150, 50, 245), outline=ink + (230,), width=2)
    return s


def open_book(ob: Icon) -> None:
    """The society's memoirs open from above: calf boards, the system of the planets on the left page, a heading, the
    observations and a lens diagram on the right, the gutter shadow, a red ribbon."""
    cx, cy = 512, 512
    W, H = 600, 380
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    cover = ob.mask("rounded_rectangle", (x0 - 18, y0 - 12, x1 + 18, y1 + 30), radius=12)
    ob.fill(cover, "#7a4a2c", "#2a1208", radial=(x0, y0, W * 1.1), noise=0.12, chroma=0.06)
    bevel(ob, cover, 10, 0.3, 0.5)
    block = ob.mask("rectangle", (x0 + 4, y1 - 6, x1 - 4, y1 + 18))
    ob.fill(block, "#e6d6b2", "#9a8460", noise=0.06)
    ob.overlay(lambda d: [d.line([(x0 + 6, y), (x1 - 6, y)], fill=(120, 100, 70, 150), width=2)
                          for y in np.arange(y1 - 2, y1 + 18, 5)], block)
    fh, ft, fi = font(SERIF_BOLD, 27), font(SERIF, 22), font(ITALIC, 22)
    for side in (-1, 1):
        ts = np.linspace(0, 1, 30)
        top = [(cx + side * (6 + (W / 2 - 6) * t), y0 + 22 - 28 * t ** 1.4) for t in ts]
        bot = [(cx + side * (6 + (W / 2 - 6) * t), y1 - 2 * t) for t in ts[::-1]]
        page = ob.poly_mask(top + bot)
        ob.fill(page, "#f6ecd0", "#c8b288", radial=(cx + side * W * 0.1 - W * 0.2, y0, W * 0.75), noise=0.06, chroma=0.03)
        for _ in range(5):
            x, y, r = cx + side * ob.random.uniform(40, W / 2 - 40), ob.random.uniform(y0 + 40, y1 - 40), ob.random.uniform(14, 36)
            ob.shade(ob.intersect(ob.mask("ellipse", (x - r, y - r * 0.8, x + r, y + r * 0.8)), page), (160, 120, 70),
                     ob.random.uniform(0.04, 0.1), blur=10)
        pw, ph = int(W / 2 - 36), int(H - 30)
        px = int(cx + 24) if side > 0 else int(cx - 24 - pw)
        if side < 0:
            sheet = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
            plate = orbits(pw - 20, INK)
            sheet.alpha_composite(plate, (10, (ph - plate.height) // 2 + 4))
            sheet = sheet.filter(ImageFilter.GaussianBlur(0.6))
        else:
            lines = [(pw / 2, 8, "OBSERVATIONS", fh, INK + (240,), "ma")]
            lines += [(16, 64 + k * 34, t, fi if k % 2 else ft, INK + (225,), "la") for k, t in enumerate(NOTES)]
            sheet = text_block((pw, ph), lines, blur=0.65)
            dd = ImageDraw.Draw(sheet)
            dd.line([(30, 52), (pw - 30, 52)], fill=INK + (200,), width=2)
            ly = ph - 52  # a lens and its rays meeting in the focus
            dd.ellipse((pw / 2 - 12, ly - 34, pw / 2 + 12, ly + 34), outline=INK + (220,), width=3)
            for dy in (-26, 0, 26):
                dd.line([(36, ly + dy), (pw / 2, ly + dy)], fill=INK + (200,), width=2)
                dd.line([(pw / 2, ly + dy), (pw - 40, ly)], fill=INK + (200,), width=2)
            dd.ellipse((pw - 46, ly - 6, pw - 34, ly + 6), fill=INK + (230,))
        paste_clipped(ob, sheet, (px, y0 + 18), page)
        g = ob.mask("rectangle", (cx - 70, y0 - 20, cx + 70, y1 + 10))
        ob.shade(ob.intersect(g, page), (60, 36, 14), 0.42, blur=26)
        swell = ob.mask("rectangle", (cx + side * 80 - 30, y0, cx + side * 80 + 30, y1))
        ob.shade(ob.intersect(swell, page), (255, 250, 236), 0.16, blur=20)
        ob.overlay(lambda d, p=top + bot: d.line(p + [p[0]], fill=(120, 96, 64, 200), width=3))
    contour(ob)


def seal(ic: Icon, cx, cy, r, top) -> None:
    """The charter's red wax seal on two silk tails that come down from under the book's edge (``top``): an irregular
    blob, an impressed ring with a crown of points, glossy highlights."""
    for dx, col in ((-16, ("#3e5a7a", "#16243a")), (16, ("#d8c088", "#6a5228"))):
        p0, p1 = (cx + dx * 2.2, top), (cx + dx * 0.6, cy)
        n = (14, 0)
        tail = [(p0[0] - n[0], p0[1]), (p0[0] + n[0], p0[1]), (p1[0] + n[0], p1[1]), (p1[0] - n[0], p1[1])]
        tm = ic.poly_mask(tail)
        ic.fill(tm, col[0], col[1], (p0[0] - 14, p0[0] + 14), vertical=False, noise=0.08)
        ic.overlay(lambda d, t=tail: d.line(t + [t[0]], fill=EDGE, width=3))
    ic.shade(ic.mask("ellipse", (cx - r * 0.9, cy - r * 0.6, cx + r * 1.2, cy + r * 1.3)), (10, 4, 2), 0.35, blur=10)
    blob = ic.jitter(cx, cy, r, r * 0.95, 18, 0.06)
    bm = ic.poly_mask(blob).filter(ImageFilter.GaussianBlur(4)).point(lambda v: 255 if v > 120 else 0)
    ic.fill(bm, "#d0402c", "#5a0e08", radial=(cx - r * 0.4, cy - r * 0.4, r * 1.7), noise=0.08, chroma=0.03)
    ring = (cx - r * 0.66, cy - r * 0.66, cx + r * 0.66, cy + r * 0.66)
    ic.overlay(lambda d: d.ellipse(ring, outline=(80, 10, 6, 210), width=5))
    ic.overlay(lambda d: d.ellipse((ring[0] + 3, ring[1] + 3, ring[2] + 3, ring[3] + 3), outline=(255, 150, 120, 120),
                                   width=3))
    crown = [(cx - r * 0.34, cy + r * 0.18), (cx - r * 0.34, cy - r * 0.16), (cx - r * 0.17, cy), (cx, cy - r * 0.3),
             (cx + r * 0.17, cy), (cx + r * 0.34, cy - r * 0.16), (cx + r * 0.34, cy + r * 0.18)]
    ic.overlay(lambda d: d.line(crown + [crown[0]], fill=(90, 12, 8, 210), width=4))
    ic.shade(ic.intersect(ic.mask("ellipse", (cx - r * 0.7, cy - r * 0.8, cx - r * 0.1, cy - r * 0.35)), bm),
             (255, 220, 200), 0.55, blur=5)
    ic.overlay(lambda d: d.line(blob + [blob[0]], fill=(60, 8, 4, 200), width=3))


# ---------------------------------------------------------------- composition
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.92
    ic.grade["gamma"] = 0.9
    ic.grade["light"] = 0.12
    # the armillary sphere on its stand, at the back
    sp = layer(SEED + 1)
    R = 196
    scy = 400
    stand(sp, 512, scy + int(1.05 * R * math.cos(math.radians(14))) - 22)
    armillary(sp, 512, scy, R, widths=1.0)
    simg = turned(rim(sp.image, 0.18, 20), 0, (372, 382))
    ic.image.alpha_composite(simg)
    # the telescope lying across in front of the stand's foot, rising to the right
    tl = layer(SEED + 2)
    telescope(tl, 150, 880, 512)
    timg = turned(rim(tl.image, 0.15, 16), 19, (600, 626))
    cast(ic, timg, 14, 18, 16, 0.5)
    ic.image.alpha_composite(timg)
    # the charter's seal on its tails, which run up under the book; then the open book in front, tipped back
    seal(ic, 676, 952, 42, 860)
    bk = layer(SEED + 3)
    open_book(bk)
    bimg = tip(rim(bk.image, 0.18, 16), [(194, 314), (830, 314), (830, 760), (194, 760)],
               [(276, 436), (756, 436), (834, 664), (196, 664)])
    bimg = turned(bimg, -4, (592, 758))
    cast(ic, bimg, 14, 16, 16, 0.55)
    ic.image.alpha_composite(bimg)


def finished(ic: Icon) -> Image.Image:
    """Colour grade and soften as the building icons get them, no outline, fitted into the vanilla frame."""
    art = soften(grade(ic.image, ic.grade["mute"], ic.grade["gamma"], ic.grade["light"]), ic.grade["soften"])
    art = art.crop(art.getbbox())
    inner = SIDE - 16
    scale = inner / max(art.size)
    art = fit(art, (max(1, round(art.width * scale)), max(1, round(art.height * scale))))
    canvas = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    canvas.alpha_composite(art, ((SIDE - art.width) // 2, (SIDE - art.height) // 2))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", type=Path, help="write a preview sheet here instead of the DDS")
    ap.add_argument("--png", type=Path, help="write the finished 256 px PNG here instead of the DDS")
    args = ap.parse_args()
    ic = Icon(seed=SEED)
    draw(ic)
    image = finished(ic)
    if args.png:
        args.png.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.png)
    if args.preview:
        sheet = Image.new("RGBA", (SIDE + 90, SIDE + 12), (60, 60, 70, 255))
        sheet.alpha_composite(image, (6, 6))
        sheet.alpha_composite(image.resize((64, 64), Image.LANCZOS), (SIDE + 16, 6))
        sheet.save(args.preview)
    if args.png or args.preview:
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(encode_dds(image, "DXT5"))
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
