"""Village School (pp_village_school): a small rural schoolhouse where the parish cleric teaches the village children.

Build (from eu5-building-pipeline):
  EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game uv run eu5-building icon build \
    --script ../ProsperOrPerishConstructor-locplan/assets/icon_drawings/pp_village_school/draw.py \
    --out ../ProsperOrPerishConstructor-locplan/artifacts/icons/pp_village_school

Identity: a writing slate on an easel with chalk letters in front of a low limewashed schoolhouse; the house has a
row of tall leaded schoolroom windows, a porch over the door, a small open bell-cote with the school bell on the
ridge and a chimney for the schoolroom stove (a house, not a chapel). A firewood lean-to on the right (the children
brought the logs for the stove) and a stack of books with a hornbook at the easel's foot. Helpers ``union``, ``tint``,
``stones``, ``planks``, ``log_end`` are copied from the Cookshop and Tavern; new local helpers: ``slates`` (stone
slate roof with courses that diminish towards the ridge), ``limewash`` (rubble wall under flaking limewash),
``leaded_window``, ``bell``, ``book``, ``hornbook``, ``chalk_board``.
"""

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from eu5_building_pipeline.iconkit import Icon

SEED = 23
REFS = ("local_schools", "parish_church", "farming_village", "scriptorium")

BASE = 900
L, R = 120, 640  # schoolhouse walls
EAVE, RIDGE = 500, 272
SH0, SH1, SHTOP, SHFRONT = 640, 872, 606, 690  # firewood lean-to
IRON = (34, 31, 30)
EDGE = (40, 28, 20, 200)
FONTS = ("/usr/share/fonts/opentype/urw-base35/P052-Bold.otf", "/usr/share/fonts/opentype/urw-base35/C059-Bold.otf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")


def font(size: int) -> ImageFont.ImageFont:
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- helpers (shared with the Cookshop and Tavern)
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
            gx = x + rnd(4, w - 4)
            gy = rnd(y0, y1)
            d.line([(gx, gy), (gx + rnd(-2, 2), gy + rnd(40, 140))], fill=(40, 26, 14, 60), width=2)
        d.line([(x + w - 2, y0), (x + w - 2 + rnd(-2, 2), y1)], fill=(28, 18, 10, 150), width=4)
        d.line([(x + 3, y0), (x + 3, y1)], fill=(255, 238, 210, 40), width=3)
        x += w
    clip2 = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip2.paste(lay, (0, 0), m)
    ic.image.alpha_composite(clip2)


def log_end(ic: Icon, cx, cy, r) -> None:
    """Sawn log end: bark ring, pale end grain lit from the upper left, one growth ring."""
    ic.fill(ic.mask("ellipse", (cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5)), "#6a4a30", "#2e1e12", (cy - r, cy + r))
    k = ic.random.uniform(0.78, 1.05)
    lite, dark = tuple(int(v * k) for v in (216, 178, 124)), tuple(int(v * k) for v in (138, 94, 50))
    ic.fill(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), lite, dark,
            radial=(cx - r * 0.4, cy - r * 0.5, r * 2.0), noise=0.14)
    if ic.random.random() < 0.35:  # weathered grey end
        ic.shade(ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r)), (120, 116, 108), 0.35)
    ic.overlay(lambda d: d.arc((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), 200, 470,
                               fill=(120, 80, 40, 70), width=2))


# ---------------------------------------------------------------- helpers (new for the Village School)
def slates(ic: Icon, pts, c1, c2, bottom_course: float = 40, top_course: float = 22, edge: int = 7) -> Image.Image:
    """Stone-slate roof: courses diminish towards the ridge, every slate its own tone and a ragged butt, each course
    shades the one below. Returns the mask."""
    pts = [tuple(p) for p in pts]
    m = ic.poly_mask(pts)
    ys, xs = [p[1] for p in pts], [p[0] for p in pts]
    top, bot = min(ys), max(ys)
    ic.fill(m, c1, c2, (top, bot), noise=0.2, chroma=0.06)
    tone = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    shadow = Image.new("L", (ic.size, ic.size), 0)
    td, sd = ImageDraw.Draw(tone), ImageDraw.Draw(shadow)
    rnd = ic.random.uniform
    y, k = bot, 0
    while y > top - 4:
        f = (y - top) / max(bot - top, 1)
        course = top_course + (bottom_course - top_course) * f
        y0 = y - course
        x = min(xs) - rnd(0, 50)
        while x < max(xs):
            w = course * rnd(0.8, 2.3)
            drop = rnd(-5, 6)  # every slate hangs a little differently
            bl, br = y + drop + rnd(-3, 3), y + drop + rnd(-3, 3)
            q = [(x + 2, y0 + 2), (x + w - 2, y0 + 2), (x + w - 2, br), (x + w * 0.5, max(bl, br) + rnd(0, 3)), (x + 2, bl)]
            t = rnd(-1, 1)
            if ic.random.random() < 0.08:
                td.polygon(q, fill=(118, 120, 66, int(rnd(50, 90))))  # lichen
            elif t < 0:
                td.polygon(q, fill=(16, 12, 10, int(-t * 85)))
            else:
                td.polygon(q, fill=(255, 244, 226, int(t * 55)))
            td.line([(x + w - 2, y0 + 4), (x + w - 2, br - 2)], fill=(30, 22, 18, 130), width=3)
            td.line([(x + 4, bl - 3), (x + w - 4, br - 3)], fill=(255, 240, 220, 70), width=3)  # lit butt
            sd.line([(x + 2, bl + 4), (x + w * 0.5, max(bl, br) + 5), (x + w - 2, br + 4)], fill=255,
                    width=int(max(5, course * 0.3)))
            x += w
        y -= course
        k += 1
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(tone, (0, 0), m)
    ic.image.alpha_composite(clip)
    tint(ic, shadow, m, (14, 10, 8), 0.5, 3)
    ic.outline(pts, edge)
    return m


def limewash(ic: Icon, box, clip: Image.Image, wash=("#e2c898", "#a6845a"), stone=("#a08464", "#5a4632"),
             flakes: int = 3) -> None:
    """Rubble wall under old limewash: the wash has flaked off in places and shows the stones, its edges cast a thin
    shadow; the stone courses still read faintly through it."""
    x0, y0, x1, y1 = box
    stones(ic, box, stone[0], stone[1], course=32, clip=clip, moss=0.03)
    rnd = ic.random.uniform
    holes = Image.new("L", (ic.size, ic.size), 0)
    hd = ImageDraw.Draw(holes)
    for _ in range(flakes):
        cx, cy = rnd(x0 + 20, x1 - 20), rnd(y0 + 80, y1 - 20)
        r = rnd(16, 38)
        hd.polygon(ic.jitter(cx, cy, r * 1.4, r * 0.8, 11, 0.35), fill=255)
    holes = holes.filter(ImageFilter.GaussianBlur(4)).point(lambda v: 255 if v > 120 else 0)
    coat = ImageChops.subtract(clip, holes)
    ic.fill(coat, wash[0], wash[1], (y0, y1), noise=0.12, chroma=0.03)
    # faint courses through the wash
    lay = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = y0 + rnd(0, 20)
    while y < y1:
        h = rnd(28, 38)
        x = x0 - rnd(0, 40)
        while x < x1:
            w = rnd(40, 80)
            d.line([(x, y + h), (x + w, y + h + rnd(-2, 2))], fill=(90, 80, 66, 34), width=3)
            d.line([(x + w, y + 3), (x + w + rnd(-3, 3), y + h)], fill=(90, 80, 66, 26), width=3)
            x += w
        y += h
    c = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    c.paste(lay, (0, 0), coat)
    ic.image.alpha_composite(c)
    # the wash's broken edge: dark on the lower right of each hole, lit lip on the upper left
    ring = ImageChops.subtract(holes.filter(ImageFilter.MaxFilter(9)), holes)
    lower = ImageChops.offset(ring, 3, 4)
    tint(ic, ImageChops.subtract(lower, holes), clip, (40, 32, 24), 0.35, 1)
    tint(ic, ImageChops.subtract(ImageChops.offset(holes, 4, 5), holes), clip, (30, 22, 16), 0.45, 2)


def leaded_window(ic: Icon, x0, y0, x1, y1, panes=(3, 4)) -> None:
    """Tall schoolroom window: timber frame, dark glass with a grey sky sheen at the top, a grid of lead cames, a stone
    sill casting a short shadow."""
    ic.rect((x0 - 12, y0 - 12, x1 + 12, y1 + 8), "#6c5038", "#45301e", edge=4)
    glass = ic.mask("rectangle", (x0, y0, x1, y1))
    ic.fill(glass, "#4a4c52", "#17171a", (y0, y1), noise=0.08, chroma=0.03)
    tint(ic, ic.poly_mask([(x0, y0), (x1, y0), (x1, y0 + (y1 - y0) * 0.18), (x0, y0 + (y1 - y0) * 0.5)]), glass,
         (170, 180, 192), 0.2, 6)
    nx, ny = panes

    def lead(d):
        for i in range(1, nx):
            x = x0 + (x1 - x0) * i / nx
            d.line([(x, y0), (x, y1)], fill=(70, 66, 62, 220), width=4)
        for j in range(1, ny):
            y = y0 + (y1 - y0) * j / ny
            d.line([(x0, y), (x1, y)], fill=(70, 66, 62, 220), width=4)

    ic.overlay(lead, glass)
    ic.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], 8, (96, 70, 46))  # mullion
    ic.outline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], 4)
    ic.rect((x0 - 18, y1 + 8, x1 + 18, y1 + 24), "#c2b8a4", "#8a806e", edge=4)  # sill


def bell(ic: Icon, cx, top, w, h) -> None:
    """Bronze bell: crown, waist, flared lip; lit left, core shadow right, dark mouth and the clapper."""
    knots = [(0.0, 0.26), (0.1, 0.34), (0.35, 0.36), (0.62, 0.40), (0.84, 0.47), (1.0, 0.56)]
    ss = np.linspace(0, 1, 30)
    hw = np.interp(ss, [k[0] for k in knots], [k[1] for k in knots]) * w
    pts = [(cx - v, top + h * s) for s, v in zip(ss, hw)] + [(cx + v, top + h * s) for s, v in zip(ss[::-1], hw[::-1])]
    m = ic.poly_mask(pts)
    ic.fill(m, "#e0b874", "#5e3a16", (cx - w * 0.4, cx + w * 0.56), vertical=False, noise=0.1)
    tint(ic, ic.mask("rectangle", (cx + w * 0.08, top, cx + w, top + h)), m, (20, 10, 2), 0.4, w * 0.12)
    tint(ic, ic.mask("rectangle", (cx - w * 0.3, top + h * 0.1, cx - w * 0.16, top + h * 0.9)), m, (255, 240, 200), 0.45, 5)
    ic.line([(cx - w * 0.5, top + h * 0.88), (cx + w * 0.5, top + h * 0.9)], 4, (70, 44, 18, 160))
    mouth = (cx - w * 0.56, top + h - h * 0.08, cx + w * 0.56, top + h + h * 0.08)
    ic.fill(ic.mask("ellipse", mouth), "#2a1a0c", "#100804", noise=0.06)
    ic.draw.ellipse((cx - w * 0.1, top + h + h * 0.02, cx + w * 0.1, top + h + h * 0.2), fill=(46, 34, 22, 255))
    ic.outline(pts, 4, (40, 24, 10, 210))


def book(ic: Icon, x0, y0, x1, y1, cover, pages=("#e8dcc0", "#a8946e"), spine_left=True) -> None:
    """A closed book lying flat, seen from the front and slightly above: a cover top, a block of pages, a spine."""
    t = (y1 - y0) * 0.34  # cover thickness band at the top
    top = [(x0 + 10, y0), (x1 - 4, y0), (x1, y0 + t), (x0, y0 + t)]
    ic.fill(ic.poly_mask(top), cover[0], cover[1], radial=(x0 + (x1 - x0) * 0.2, y0, (x1 - x0) * 1.1), noise=0.14)
    block = ic.mask("rectangle", (x0 + (14 if spine_left else 0), y0 + t, x1 - (0 if spine_left else 14), y1 - 6))
    ic.fill(block, pages[0], pages[1], (y0 + t, y1), noise=0.08)
    ic.overlay(lambda d: [d.line([(x0 + 16, yy), (x1 - 2, yy)], fill=(120, 100, 70, 90), width=2)
                          for yy in np.arange(y0 + t + 6, y1 - 6, 6)], block)
    sx = x0 if spine_left else x1 - 18
    ic.fill(ic.mask("rectangle", (sx, y0 + t - 2, sx + 18, y1)), cover[0], cover[1], (y0, y1), noise=0.12)
    ic.fill(ic.mask("rectangle", (x0, y1 - 8, x1, y1)), cover[1], cover[1], noise=0.1)
    ic.outline([(x0 + 10, y0), (x1 - 4, y0), (x1, y0 + t), (x1, y1), (x0, y1), (x0, y0 + t)], 4, (36, 22, 12, 200))


def hornbook(ic: Icon, cx, cy, h, degrees) -> None:
    """A hornbook: an oak paddle with a printed alphabet sheet under clear horn, held by a brass strip and nails."""
    w = h * 0.6
    paddle = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h * 0.22), (w * 0.16, h * 0.3), (w * 0.14, h / 2),
              (-w * 0.14, h / 2), (-w * 0.16, h * 0.3), (-w / 2, h * 0.22)]
    pm = ic.poly_mask(ic.rotate(paddle, (cx, cy), degrees))
    ic.fill(pm, "#b48656", "#4e3018", radial=(cx - w * 0.4, cy - h * 0.4, h * 1.1), noise=0.18)
    sheet = [(-w * 0.38, -h * 0.4), (w * 0.38, -h * 0.4), (w * 0.38, h * 0.14), (-w * 0.38, h * 0.14)]
    sp = ic.rotate(sheet, (cx, cy), degrees)
    sm = ic.poly_mask(sp)
    ic.fill(sm, "#efe4c8", "#bfae88", radial=(cx - w * 0.3, cy - h * 0.4, h * 0.9), noise=0.08)

    def rows(d):
        for k in range(5):
            yy = -h * 0.32 + k * h * 0.09
            a, b = ic.rotate([(-w * 0.3, yy), (w * (0.3 if k else 0.2), yy)], (cx, cy), degrees)
            d.line([a, b], fill=(60, 40, 24, 200), width=4)

    ic.overlay(rows, sm)
    ic.outline(sp, 4, (150, 112, 50, 230))  # brass strip
    ic.outline(ic.rotate(paddle, (cx, cy), degrees), 4, EDGE)


def chalk_board(ic: Icon) -> None:
    """A slate in a wooden frame on an easel, chalk letters and a sum on it, a chalk ledge with a stick of chalk."""
    # back leg and the easel's shadow on the ground
    ic.beam((836, 560), (870, 944), 18, (80, 56, 36))
    tint(ic, ic.mask("ellipse", (660, BASE + 4, 1000, BASE + 60)), None, (0, 0, 0), 0.4, 14)
    frame = [(676, 556), (948, 540), (966, 812), (688, 828)]
    fm = ic.poly_mask(frame)
    ic.fill(fm, "#a87a4a", "#5a3a20", (676, 966), vertical=False, noise=0.18)
    tint(ic, ic.poly_mask([(676, 556), (948, 540), (948, 560), (680, 576)]), fm, (255, 236, 200), 0.3, 3)
    inner = [(700, 578), (926, 565), (941, 790), (711, 804)]
    im = ic.poly_mask(inner)
    ic.fill(im, "#424a4c", "#1a2022", radial=(730, 590, 300), noise=0.14, chroma=0.04)
    # rubbed-out chalk haze
    for _ in range(6):
        x, y = ic.random.uniform(730, 910), ic.random.uniform(600, 780)
        tint(ic, ic.mask("ellipse", (x - 60, y - 20, x + 60, y + 20)), im, (200, 204, 200), 0.09, 12)
    chalk = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    d = ImageDraw.Draw(chalk)
    d.text((722, 576), "A b c", font=font(70), fill=(240, 238, 228, 240))
    d.text((726, 650), "d e f", font=font(58), fill=(234, 232, 222, 220))
    d.text((728, 714), "1 + 2", font=font(58), fill=(234, 232, 222, 220))
    chalk = chalk.rotate(3.2, resample=Image.BICUBIC, center=(820, 680)).filter(ImageFilter.GaussianBlur(1.3))
    clip = Image.new("RGBA", (ic.size, ic.size), (0, 0, 0, 0))
    clip.paste(chalk, (0, 0), im)
    ic.image.alpha_composite(clip)
    tint(ic, ic.poly_mask([(700, 578), (926, 565), (928, 610), (702, 624)]), im, (0, 0, 0), 0.25, 10)
    ic.outline(inner, 5, (30, 20, 12, 210))
    ic.outline(frame, 5)
    # chalk ledge and front legs
    ic.beam((670, 830), (976, 814), 20, (126, 90, 56))
    ic.fill(ic.mask("rectangle", (780, 806, 836, 818)), "#f4f2e8", "#c8c4b8", noise=0.05)
    ic.beam((700, 818), (664, 948), 20, (116, 82, 52))
    ic.beam((946, 806), (984, 944), 20, (100, 70, 44))
    tint(ic, ic.mask("rectangle", (946, 600, 984, 944)), None, (0, 0, 0), 0.2, 8)


# ---------------------------------------------------------------- drawing
def draw(ic: Icon) -> None:
    ic.grade["mute"] = 0.96
    ic.grade["gamma"] = 0.78

    # ---- chimney at the right end of the ridge (the schoolroom stove), a thin wisp of smoke drifting right
    cx0, cx1, ctop = 520, 586, 176
    cm = ic.mask("rectangle", (cx0, ctop, cx1, RIDGE + 60))
    stones(ic, (cx0, ctop, cx1, RIDGE + 60), "#a89a86", "#6a5e50", course=26)
    tint(ic, ic.mask("rectangle", (cx0 + 40, ctop, cx1 + 10, RIDGE + 60)), cm, (0, 0, 0), 0.32, 12)
    tint(ic, ic.mask("rectangle", (cx0, ctop, cx1, ctop + 36)), cm, (20, 14, 10), 0.32, 10)
    ic.outline([(cx0, ctop), (cx1, ctop), (cx1, RIDGE + 60), (cx0, RIDGE + 60)], 4)
    ic.poly([(cx0 - 10, ctop - 12), (cx1 + 10, ctop - 12), (cx1 + 10, ctop + 8), (cx0 - 10, ctop + 8)],
            "#b4a894", "#7c7264", edge=4)

    # ---- firewood lean-to against the right gable (drawn first, the house roof overlaps it)
    back = ic.mask("rectangle", (SH0, SHTOP, SH1, BASE))
    planks(ic, (SH0, SHTOP, SH1, BASE), "#6a5644", "#3a2e24", board=30)
    tint(ic, ic.mask("rectangle", (SH0, SHTOP, SH1, SHTOP + 200)), back, (8, 4, 2), 0.5, 26)
    stack = ic.mask("rectangle", (SH0 + 10, 716, SH1 - 26, BASE))
    ic.fill(stack, "#4a3220", "#24160c", noise=0.1)
    for row, y in enumerate(np.arange(BASE - 24, 720, -40)):
        for x in np.arange(SH0 + 34 + (row % 2) * 20, SH1 - 40, 40):
            log_end(ic, x + ic.random.uniform(-4, 4), y + ic.random.uniform(-4, 4), ic.random.uniform(16, 22))
    tint(ic, ic.mask("rectangle", (SH0, 700, SH1, 760)), stack, (0, 0, 0), 0.35, 14)
    roof_s = [(SH0 - 6, SHTOP - 10), (SH1 + 8, SHTOP), (SH1 + 34, SHFRONT + 8), (SH0 - 6, SHFRONT + 8)]
    slates(ic, roof_s, "#94806a", "#4e4236", bottom_course=26, top_course=20, edge=6)
    ic.beam((SH1 - 10, SHFRONT + 10), (SH1 - 12, BASE), 24, (98, 70, 46))
    ic.beam((SH0, SHFRONT + 14), (SH1 + 20, SHFRONT + 14), 18, (98, 70, 46))
    tint(ic, ic.mask("rectangle", (SH0, SHFRONT + 22, SH1, SHFRONT + 70)), None, (0, 0, 0), 0.4, 12)

    # ---- the house roof: stone slates, slightly sagging ridge
    roof = [(90, EAVE + 14), (672, EAVE + 14), (630, RIDGE), (380, RIDGE + 7), (132, RIDGE)]
    rmask = slates(ic, roof, "#947a5a", "#40342a", bottom_course=36, top_course=18)
    for _ in range(16):  # weathering: lichen, damp and sun-bleached patches
        x, y = ic.random.uniform(120, 640), ic.random.uniform(RIDGE + 10, EAVE)
        r = ic.random.uniform(24, 64)
        col = ic.random.choice([(0, 0, 0), (255, 236, 200), (130, 120, 50), (90, 96, 50)])
        tint(ic, ic.mask("ellipse", (x - r * 1.5, y - r * 0.6, x + r * 1.5, y + r * 0.6)), rmask, col,
             ic.random.uniform(0.08, 0.2), 14)
    tint(ic, ic.poly_mask([(132, RIDGE), (330, RIDGE), (280, EAVE + 14), (90, EAVE + 14)]), rmask, (255, 240, 214), 0.12, 50)
    tint(ic, ic.poly_mask([(470, RIDGE), (700, RIDGE), (700, EAVE + 14), (520, EAVE + 14)]), rmask, (0, 0, 0), 0.18, 50)
    tint(ic, ic.poly_mask([(cx1, RIDGE + 40), (cx1 + 50, RIDGE + 70), (cx1 + 50, RIDGE + 130), (cx1, RIDGE + 100)]),
         rmask, (0, 0, 0), 0.35, 12)  # chimney shadow
    ridge = [(130, RIDGE - 12), (380, RIDGE - 5), (632, RIDGE - 12), (632, RIDGE + 8), (380, RIDGE + 14), (130, RIDGE + 8)]
    ic.poly(ridge, "#8e7258", "#5a4636", edge=4)
    stones(ic, (cx0, RIDGE + 40, cx1, RIDGE + 70), "#a89a86", "#6a5e50", course=26)  # chimney foot over the ridge
    ic.outline([(cx0, RIDGE + 40), (cx1, RIDGE + 40), (cx1, RIDGE + 70), (cx0, RIDGE + 70)], 4)

    # ---- bell-cote on the ridge at the left end: two posts, the school bell, a small slate cap, a ball finial
    bx = 232
    tint(ic, ic.poly_mask([(bx + 40, RIDGE + 6), (bx + 110, RIDGE + 40), (bx + 110, RIDGE + 90), (bx + 40, RIDGE + 50)]),
         rmask, (0, 0, 0), 0.3, 12)
    ic.rect((bx - 62, RIDGE - 22, bx + 62, RIDGE + 10), "#7a5a3c", "#4a3422", edge=4)  # sole plate on the ridge
    bell(ic, bx, 186, 66, 62)
    ic.beam((bx - 36, 180), (bx + 36, 180), 14, (90, 62, 40))  # headstock
    for x in (bx - 48, bx + 48):
        ic.beam((x, RIDGE - 16), (x, 150), 20, (104, 74, 48))
    ic.beam((bx - 52, 168), (bx + 52, 168), 12, (96, 68, 44))
    cap = [(bx - 76, 160), (bx + 76, 160), (bx + 4, 82), (bx - 4, 82)]
    cmk = ic.poly_mask(cap)
    ic.fill(cmk, "#8e877c", "#4e4840", (82, 160), noise=0.2)
    tint(ic, ic.poly_mask([(bx, 82), (bx + 80, 160), (bx, 160)]), cmk, (0, 0, 0), 0.3, 4)
    ic.overlay(lambda d: [d.line([(bx - 66 + 6 * k, 150 - 14 * k), (bx + 66 - 6 * k, 150 - 14 * k)],
                                 fill=(30, 26, 22, 120), width=3) for k in range(5)], cmk)
    ic.outline(cap, 5)
    ic.line([(bx, 82), (bx, 60)], 6, IRON)
    ic.ellipse((bx - 11, 44, bx + 11, 66), "#8a8478", "#3a3630", edge=4)

    # ---- walls: limewashed rubble
    wall = ic.mask("rectangle", (L, EAVE + 14, R, BASE))
    limewash(ic, (L, EAVE + 14, R, BASE), wall)
    tint(ic, ic.mask("rectangle", (L, BASE - 100, R, BASE)), wall, (54, 58, 30), 0.25, 26)  # damp and moss low
    tint(ic, ic.mask("rectangle", (L, EAVE + 14, R, EAVE + 64)), wall, (0, 0, 0), 0.5, 12)  # eave shadow
    tint(ic, ic.mask("rectangle", (R - 160, EAVE, R + 40, BASE)), wall, (20, 10, 0), 0.22, 50)
    tint(ic, ic.mask("rectangle", (L - 40, EAVE, L + 120, BASE)), wall, (255, 236, 200), 0.1, 40)
    streaks = Image.new("L", (ic.size, ic.size), 0)
    sd = ImageDraw.Draw(streaks)
    for _ in range(14):
        x = ic.random.uniform(L + 10, R - 10)
        sd.line([(x, EAVE + 20), (x + ic.random.uniform(-4, 4), EAVE + ic.random.uniform(60, 150))], fill=255,
                width=int(ic.random.uniform(4, 9)))
    tint(ic, streaks, wall, (60, 50, 36), 0.18, 4)
    ic.outline([(L, EAVE + 14), (R, EAVE + 14), (R, BASE), (L, BASE)], 5)

    # ---- three tall schoolroom windows and the porch door
    for x0 in (160, 280, 540):
        leaded_window(ic, x0, 600, x0 + 66, 738)
        tint(ic, ic.mask("rectangle", (x0 - 18, 762, x0 + 92, 820)), wall, (50, 40, 28), 0.16, 10)  # weather streak
    dx0, dx1, dtop = 404, 488, 690
    ic.rect((dx0 - 14, dtop - 14, dx1 + 14, BASE), "#7a5a3c", "#4a3422", edge=4)
    ic.door(dx0, dtop, dx1, BASE - 4, arched=False, surround=None)
    tint(ic, ic.mask("rectangle", (dx0, dtop, dx1, dtop + 50)), None, (0, 0, 0), 0.35, 10)
    # porch hood on two brackets
    for x in (dx0 - 26, dx1 + 26):
        ic.beam((x, dtop - 8), (x + (14 if x < dx0 else -14), dtop + 60), 12, (92, 64, 42))
    hood = [(dx0 - 56, dtop - 6), (dx1 + 56, dtop - 6), (dx1 + 36, dtop - 66), (dx0 - 36, dtop - 66)]
    hm = slates(ic, hood, "#a08a6c", "#54463a", bottom_course=20, top_course=16, edge=5)
    tint(ic, ic.mask("rectangle", (dx0 - 40, dtop - 4, dx1 + 40, dtop + 30)), wall, (0, 0, 0), 0.4, 10)
    tint(ic, ic.poly_mask([(dx0 - 36, dtop - 66), (dx0 + 10, dtop - 66), (dx0 - 20, dtop - 6), (dx0 - 56, dtop - 6)]), hm,
         (255, 244, 220), 0.12, 6)
    # bench by the door
    ic.beam((290, 840), (380, 840), 16, (120, 86, 54))
    for x in (300, 370):
        ic.beam((x, 846), (x, BASE - 4), 10, (84, 58, 36))
    tint(ic, ic.mask("rectangle", (280, 850, 392, BASE)), wall, (0, 0, 0), 0.3, 8)

    # ---- plinth
    stones(ic, (L - 8, BASE - 14, SH1 + 10, BASE + 12), "#867a6a", "#5a5046", course=26, moss=0.0)
    ic.outline([(L - 8, BASE - 14), (SH1 + 10, BASE - 14), (SH1 + 10, BASE + 12), (L - 8, BASE + 12)], 4)

    # ---- the slate on its easel, books and a hornbook at its foot
    chalk_board(ic)
    tint(ic, ic.mask("ellipse", (880, BASE, 1024, BASE + 50)), None, (0, 0, 0), 0.45, 10)
    book(ic, 900, 892, 1016, 948, ("#8a3e2a", "#3a160e"))
    book(ic, 910, 852, 1004, 896, ("#3e5a70", "#1a2632"), spine_left=False)
    hornbook(ic, 892, 860, 136, -12)
