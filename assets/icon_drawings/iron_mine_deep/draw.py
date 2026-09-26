"""Deep Iron Mine (iron_mine_deep): a tall timber headframe over a stone-lined shaft, with a pumping
waterwheel and a stone winding house.

Build:
  cd ~/development/eu5-building-pipeline && EU5_VANILLA_DIR=~/.cache/eu5-vanilla/game \
    uv run eu5-building icon build --script ../ProsperOrPerishConstructor/assets/icon_drawings/iron_mine_deep/draw.py \
    --out ../ProsperOrPerishConstructor/artifacts/icons/iron_mine_deep

Composition: top tier of the iron chain (Iron Ore Pit -> Iron Mine -> Deep Iron Mine). A braced timber
headframe with a big sheave wheel rises over a stone-lined shaft collar; left of it an overshot
waterwheel fed by a launder drives the pump rod into the shaft (drained workings), right of it a stone
winding house with a slate roof takes the hoisting rope. Low rust-veined rock behind, a red hematite
heap bottom right and a laden mine tub in front. Reads through the tall wheel-topped tower, the
waterwheel and the rust colour; the Iron Mine below it has only a windlass and an adit.
"""

import math

import numpy as np
from PIL import ImageChops, ImageFilter

from eu5_building_pipeline.iconkit import Icon

SEED = 23
REFS = ("schwaz_mine", "windmill", "clay_pit", "iron_mill")

ORE = "#ab4a2a"  # hematite, lit
ORE_DARK = "#4a1e14"
ROCK_DARK = "#4a3d35"
TIMBER = (112, 76, 48)
TIMBER_LIT = (146, 102, 64)
POST = (120, 82, 52)
BRACE = (98, 66, 42)
IRON = (46, 44, 46)
DARK = (28, 18, 12)


def tub(ic: Icon, x0: float, x1: float, top: float, bot: float) -> None:
    """Plank mine tub heaped with ore, iron-banded, on two small wheels (helper, not in the kit)."""
    w = x1 - x0
    for x, y, r in ((x0 + w * 0.18, top - 12, 42), (x0 + w * 0.45, top - 30, 52), (x0 + w * 0.75, top - 16, 44),
                    (x0 + w * 0.32, top + 4, 36), (x0 + w * 0.62, top + 2, 38)):
        ic.chunk(x, y, r, ORE, ORE_DARK)
    body = [(x0, top), (x1, top), (x1 - w * 0.07, bot), (x0 + w * 0.07, bot)]
    ic.poly(body, "#9a6a44", "#523620", noise=0.25)
    for f in (0.36, 0.68):
        y = top + (bot - top) * f
        ic.line([(x0 + w * 0.07 * f, y), (x1 - w * 0.07 * f, y)], 4, (58, 38, 22, 200))
    for fx in (0.14, 0.86):
        x = x0 + w * fx
        ic.line([(x, top + 2), (x + (0.5 - fx) * w * 0.07, bot - 2)], 12, IRON)
    ic.shade(ic.poly_mask([body[0], body[1], (x1 - 3, top + 14), (x0 + 3, top + 14)]), (255, 235, 210), 0.25)
    for cx in (x0 + w * 0.24, x1 - w * 0.24):
        ic.ellipse((cx - 34, bot - 22, cx + 34, bot + 44), "#4c4a4c", "#1e1c1e", edge=5)
        ic.ellipse((cx - 9, bot + 2, cx + 9, bot + 20), "#7a7274", "#3a3638", edge=3)


def wheel(ic: Icon, cx: float, cy: float, r: float, rim: float, spokes: int, spoke_w: int,
          paddles: int = 0, turn: float = 0.0) -> None:
    """Timber wheel: spokes behind a shaded rim, optional paddles, iron hub (helper, not in the kit)."""
    for k in range(spokes):
        a = math.radians(turn + 180 * k / spokes)
        dx, dy = math.cos(a) * (r - rim / 2), math.sin(a) * (r - rim / 2)
        ic.beam((cx - dx, cy - dy), (cx + dx, cy + dy), spoke_w, BRACE)
    outer = ic.mask("ellipse", (cx - r, cy - r, cx + r, cy + r))
    inner = ic.mask("ellipse", (cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim))
    ring = ImageChops.subtract(outer, inner)
    ic.fill(ring, TIMBER_LIT, (70, 46, 28), radial=(cx - r * 0.6, cy - r * 0.7, r * 2.2), noise=0.25)
    ic.shade(ImageChops.subtract(ring, ic.mask("ellipse", (cx - r + 6, cy - r + 10, cx + r + 6, cy + r + 10))),
             (255, 235, 205), 0.3)
    for k in range(paddles):
        a = math.radians(turn + 360 * k / paddles)
        pts = ic.rotate([(-rim * 0.2, -8), (rim * 1.3, -8), (rim * 1.3, 8), (-rim * 0.2, 8)],
                        (cx + math.cos(a) * (r - rim * 0.3), cy + math.sin(a) * (r - rim * 0.3)), math.degrees(a))
        ic.poly(pts, "#8a6040", "#4a3220", edge=4)
    ic.overlay(lambda d: d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(40, 28, 20, 200), width=5))
    ic.overlay(lambda d: d.ellipse((cx - r + rim, cy - r + rim, cx + r - rim, cy + r - rim),
                                   outline=(40, 28, 20, 200), width=4))
    hub = r * 0.16
    ic.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), "#5a5658", "#222022", edge=4)


def rock_back(ic: Icon) -> None:
    """Low rust-veined rock ridge behind the works (the pit's crag, now only a backdrop)."""
    ridge = [(40, 905), (50, 700), (80, 600), (130, 540), (190, 515), (260, 470), (320, 430), (380, 395),
             (430, 380), (480, 350), (540, 372), (600, 400), (650, 440), (700, 470), (760, 530), (840, 580),
             (910, 630), (960, 700), (985, 905)]
    ic.rock(ridge, "#7e6e62", ROCK_DARK, facets=2)
    with ic.clipped(ic.poly_mask(ridge)):
        for y in (500, 640, 780):
            ic.line([(0, y + 30), (500, y - 10), (1024, y + 20)], 5, (55, 45, 40, 140))
        ic.shade(ic.mask("rectangle", (0, 600, 1024, 1024)), (150, 60, 35), 0.25, blur=50)
        ic.vein([(330, 430), (300, 560), (290, 700), (270, 880)], 30, ORE, ORE_DARK)
        ic.vein([(600, 400), (640, 480), (660, 560)], 24, ORE, ORE_DARK)
        ic.vein([(860, 590), (900, 720), (890, 880)], 26, ORE, ORE_DARK)
        ic.vein([(200, 520), (150, 700), (120, 880)], 26, "#c89a48", "#8a6226")
        ic.shade(ic.mask("rectangle", (0, 760, 1024, 1024)), alpha=0.35, blur=30)
    ic.outline(ridge)


def winding_house(ic: Icon) -> None:
    """Stone winding house with a slate roof, a door and a small dark window."""
    ic.stonewall((650, 580, 965, 890), "#988a78", "#6c6154", course=38)
    ic.shade(ic.mask("rectangle", (650, 800, 965, 890)), (60, 40, 30), 0.3, blur=20)  # grime low
    ic.door(740, 720, 812, 890, arched=True, surround="#b3a894")
    ic.window(880, 660, 918, 716)
    roof = [(690, 470), (925, 470), (990, 590), (625, 590)]
    ic.tiles(roof, "#6f6a6c", "#343032", course=26, stagger=34)
    ic.rect((676, 458, 940, 478), "#5a5456", "#2e2a2c")  # ridge
    ic.shade(ic.poly_mask([(690, 470), (790, 470), (700, 590), (625, 590)]), (255, 245, 230), 0.12)
    ic.shade(ic.mask("rectangle", (650, 590, 965, 640)), alpha=0.4, blur=12)  # under the eaves


def headframe(ic: Icon) -> None:
    """Braced timber headframe with a sheave wheel on top; rope into the shaft and to the house."""
    L0, R0, L1, R1, TOP, BASE = 318, 612, 400, 530, 250, 800

    def lx(y: float) -> float:
        return L0 + (L1 - L0) * (BASE - y) / (BASE - TOP)

    def rx(y: float) -> float:
        return R0 + (R1 - R0) * (BASE - y) / (BASE - TOP)

    girts = (660, 520, 385)
    # X-braces between girts (behind the legs)
    ys = (BASE,) + girts
    for ya, yb in zip(ys[:-1], ys[1:]):
        ic.beam((lx(ya) + 10, ya), (rx(yb) - 10, yb), 16, BRACE)
        ic.beam((rx(ya) - 10, ya), (lx(yb) + 10, yb), 16, BRACE)
    # boarded upper stage under the sheave
    y0 = girts[-1]
    clad = [(lx(y0), y0), (rx(y0), y0), (rx(TOP), TOP), (lx(TOP), TOP)]
    ic.poly(clad, "#8e6644", "#5a3c24", vertical=False, noise=0.3)
    for x in np.arange(lx(y0) + 20, rx(y0), 22):
        xt = lx(TOP) + (x - lx(y0)) * (rx(TOP) - lx(TOP)) / (rx(y0) - lx(y0))
        ic.line([(x, y0), (xt, TOP)], 4, (58, 38, 22, 170))
    ic.shade(ic.poly_mask(clad), (255, 240, 215), 0.0)
    ic.rect((445, 300, 488, 350), "#2a201a", "#0c0907", edge=4)  # hatch
    ic.shade(ic.poly_mask([(rx(y0) - 60, y0), (rx(y0), y0), (rx(TOP), TOP), (rx(TOP) - 40, TOP)]), alpha=0.3, blur=12)
    for y in girts:
        ic.beam((lx(y) - 6, y), (rx(y) + 6, y), 24, POST)
    ic.beam((L0, BASE + 10), (L1, TOP), 40, POST)
    ic.beam((R0, BASE + 10), (R1, TOP), 40, POST)
    for x0, x1 in ((L0 - 14, L1 - 14), (R0 - 14, R1 - 14)):
        ic.shade(ic.poly_mask([(x0 - 4, BASE), (x0 + 6, BASE), (x1 + 6, TOP), (x1 - 4, TOP)]), (255, 240, 220), 0.25)
    # cap and sheave
    ic.rect((370, TOP - 24, 560, TOP + 10), "#9a6c44", "#5a3c24")
    ic.shade(ic.mask("rectangle", (370, TOP - 24, 560, TOP - 14)), (255, 240, 215), 0.3)
    ic.beam((420, TOP - 20), (465, 160), 18, BRACE)  # bearing trestle
    ic.beam((510, TOP - 20), (465, 160), 18, BRACE)
    wheel(ic, 465, 160, 92, 18, 4, 12, turn=20)
    # hoisting ropes: down the shaft, and off the sheave to the winding house
    ic.line([(375, 170), (375, 600)], 9, DARK)
    ic.line([(375, 170), (375, 600)], 4, (170, 140, 96))
    ic.line([(555, 168), (705, 470)], 9, DARK)
    ic.line([(555, 168), (705, 470)], 4, (170, 140, 96))
    ic.beam((560, 262), (700, 470), 22, BRACE)  # back-stay onto the house
    # ore kibble on the shaft rope
    for dx, y, r in ((-24, 616, 22), (2, 608, 26), (26, 618, 20)):
        ic.chunk(375 + dx, y, r, ORE, ORE_DARK)
    ic.poly([(338, 618), (412, 618), (404, 670), (346, 670)], "#8a6a4a", "#3e2a1a")
    ic.line([(340, 634), (410, 634)], 7, IRON)
    ic.line([(345, 660), (405, 660)], 7, IRON)


def draw(ic: Icon) -> None:
    rock_back(ic)

    # ---- ground apron in red and ochre spoil
    apron = [(15, 972), (50, 900), (300, 885), (700, 885), (960, 900), (1012, 972)]
    ic.poly(apron, "#8e5634", "#553020", noise=0.3)
    ic.shade(ic.poly_mask([(430, 905), (600, 900), (620, 955), (410, 958)]), (170, 60, 35), 0.45, blur=8)

    # ---- launder on posts feeding an overshot pumping wheel, left
    ic.beam((60, 900), (64, 470), 24, BRACE)
    ic.beam((236, 900), (232, 470), 24, BRACE)
    wheel(ic, 170, 660, 158, 30, 4, 18, paddles=16, turn=8)
    ic.rect((20, 440, 262, 492), "#9a6c44", "#553820")  # launder trough
    ic.poly([(24, 440), (258, 440), (250, 452), (30, 452)], "#6f9fb0", "#2f5566", edge=0, noise=0.1)
    for x in (258, 272, 286):  # water spilling onto the wheel
        ic.line([(x - 10, 470), (x + 4, 520), (x + 6, 560)], 10, (120, 170, 190, 220))
    ic.line([(262, 470), (284, 560)], 4, (225, 240, 245, 200))
    # pump rod from the wheel crank to the shaft
    ic.beam((170, 660), (360, 700), 18, TIMBER)
    ic.ellipse((150, 640, 190, 680), "#5a5658", "#222022", edge=4)
    # tail race along the foot of the wheel
    race = [(20, 918), (290, 900), (305, 924), (24, 948)]
    ic.poly(race, "#74a8ba", "#2c5c70", noise=0.1)
    for x in (60, 150, 230):
        ic.line([(x, 925), (x + 40, 922)], 5, (225, 240, 245, 190))

    # ---- stone winding house, right
    winding_house(ic)

    # ---- stone-lined shaft collar and the headframe over it
    ic.poly([(292, 812), (640, 812), (618, 770), (314, 770)], "#a39684", "#6e6458", noise=0.25)
    ic.poly([(336, 804), (596, 804), (582, 780), (350, 780)], "#1c140e", "#060403", edge=0, noise=0.05)
    headframe(ic)
    ic.stonewall((296, 812, 636, 895), "#a39684", "#766b5e", course=40)
    ic.shade(ic.mask("rectangle", (296, 812, 636, 836)), alpha=0.3, blur=6)

    # ---- hematite heap and a laden tub
    ic.heap(745, 1022, 985, 690, 48, 5, odd_share=0.08)
    tub(ic, 420, 640, 868, 940)
