"""Iron (Hammer Privileges): a stone blast furnace with flames at its throat and a glowing tap arch, rust-red ore
at its left foot and red-hot pig bars at its right, on a slate field; a miner's pick and hammer (Schlaegel und
Eisen) crossed behind the shield. Rights tier only: the iron right has no charter."""

FIELD = "#4a5662"
SEED = 41


def _pick(icon, loc, k):
    """Miner's pick: long spike outwards, short blunt poll inwards, handle end showing above the eye."""
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 0), (0, L - 40)]), 38, (118, 118, 118))
    head = (k.bezier((-210, L - 156), (-150, L - 98), (-70, L - 70), (30, L - 68), 16)
            + [(96, L - 76), (102, L - 146)]
            + k.bezier((40, L - 144), (-40, L - 140), (-130, L - 140), (-210, L - 156), 12))
    m = icon.poly_mask(loc(head))
    a, b = loc([(0, L - 66), (0, L - 146)])
    k.cyl(icon, m, a, b, 80, (186, 186, 186), spec=1.5)
    k.tint(icon, icon.poly_mask(loc([(-210, L - 156), (-120, L - 104), (-110, L - 124)])), m, (255, 255, 255), 0.3)
    k.contour(icon, m)
    k.rod(icon, *loc([(0, L - 168), (0, L - 140)]), 50, (150, 150, 150))  # wedge collar below the eye


def _hammer(icon, loc, k):
    """Miner's hammer (Schlaegel): a short squared head with chamfered faces."""
    L = k.CROSS_LEN
    k.rod(icon, *loc([(0, 0), (0, L - 70)]), 40, (118, 118, 118))
    k.rod(icon, *loc([(0, L - 216), (0, L - 184)]), 52, (150, 150, 150))
    head = loc([(-128, L - 186), (-110, L - 204), (88, L - 204), (106, L - 186), (106, L - 92), (88, L - 74),
                (-110, L - 74), (-128, L - 92)])
    m = icon.poly_mask(head)
    a, b = loc([(0, L - 204), (0, L - 74)])
    k.cyl(icon, m, a, b, 130, (176, 176, 176), spec=1.5)
    for s, col in ((-1, (255, 255, 255)), (1, (0, 0, 0))):  # struck faces at both ends
        f = loc([(s * 108, L - 196), (s * 128, L - 180), (s * 128, L - 96), (s * 108, L - 80)])
        k.tint(icon, icon.poly_mask(f), m, col, 0.3)
    k.contour(icon, m)


def props(icon, k):
    k.crossed(icon, lambda ic, loc, mirror: (_hammer if mirror else _pick)(ic, loc, k))


def _flame(icon, k):
    def T(x, y):  # flame drawn on a 138 px tall template, placed on the throat and stretched upwards
        return (512 + (x - 512) * 1.12, 432 - (332 - y) * 1.2)

    def B(*pts, n=12):
        return k.bezier(*(T(*p) for p in pts), n)

    outer = (B((466, 332), (450, 298), (450, 262), (472, 236))
             + B((472, 236), (474, 260), (484, 276), (494, 282), n=8)[1:]
             + B((494, 282), (486, 248), (496, 220), (514, 194))[1:]
             + B((514, 194), (532, 226), (538, 254), (530, 278), n=10)[1:]
             + B((530, 278), (542, 266), (552, 250), (556, 228), n=8)[1:]
             + B((556, 228), (578, 262), (572, 300), (558, 332))[1:])
    m = icon.poly_mask(outer)
    k.dfill(icon, m, (512, 432), (0, -1), 166,
            ((0, (255, 246, 196)), (0.3, (255, 204, 84)), (0.65, (244, 124, 34)), (1, (176, 46, 16))), noise=0.08)
    core = B((488, 334), (480, 300), (496, 274), (512, 246)) + B((512, 246), (528, 274), (544, 300), (536, 334))[1:]
    k.dfill(icon, icon.poly_mask(core), (512, 434), (0, -1), 108,
            ((0, (255, 255, 236)), (0.5, (255, 236, 150)), (1, (255, 190, 70))), noise=0.05)
    k.contour(icon, m, 5, (96, 30, 8, 220))
    for x, y, r in ((446, 300, 8), (584, 286, 7), (548, 240, 6), (474, 252, 6), (528, 214, 5)):  # sparks
        k.ball(icon, x, y, r, (255, 214, 110), edge=False)


def charge(icon, k):
    stone = ((0, (226, 210, 180)), (0.4, (180, 160, 128)), (0.75, (126, 108, 86)), (1, (80, 66, 52)))
    # squat blast furnace: a truncated stone pyramid, wide hearth at the foot, throat at the top
    stack_pts = [(448, 444), (576, 444), (634, 716), (390, 716)]
    stack = icon.poly_mask(stack_pts)
    k.dfill(icon, stack, (390, 444), (1, 0.3), 250, stone, noise=0.16)

    def courses(d):
        for r, y in enumerate(range(480, 716, 40)):
            d.line([(380, y), (644, y)], fill=(54, 40, 30, 190), width=5)
            for x in range(384 + (r % 2) * 32, 644, 64):
                d.line([(x, y - 40), (x, y)], fill=(54, 40, 30, 150), width=4)

    icon.overlay(courses, stack)
    # big hearth arch with the glow of the fire, lighting the stone around it
    k.tint(icon, k.ell(icon, 512, 650, 130, 100), stack, (255, 140, 40), 0.5, blur=28)
    arch = k.union(k.ell(icon, 512, 616, 48, 50), icon.mask("rectangle", (464, 616, 560, 716)))
    k.rfill(icon, arch, (512, 712), 124, ((0, (255, 246, 190)), (0.4, (252, 158, 46)), (1, (110, 26, 10))))
    k.contour(icon, arch, 6, (60, 20, 8, 230))
    k.tint(icon, k.ell(icon, 512, 450, 90, 36), stack, (255, 170, 60), 0.5, blur=14)
    k.contour(icon, stack)
    # stone collar at the throat and a plinth at the foot
    k.block(icon, [(432, 424), (592, 424), (598, 452), (426, 452)], (196, 176, 146))
    k.block(icon, [(380, 712), (644, 712), (650, 744), (374, 744)], (156, 138, 112))
    _flame(icon, k)
    # rust-red ore heaped at the left foot (hematite, one dark specular lump)
    for x, y, r, col in ((372, 628, 26, (184, 84, 46)), (350, 664, 24, (106, 84, 82)), (386, 664, 32, (190, 88, 48)),
                         (416, 696, 28, (172, 76, 42))):
        lump = icon.poly_mask(icon.jitter(x, y, r, r * 0.82, 9, 0.12))
        k.rfill(icon, lump, (x - r * 0.4, y - r * 0.45), r * 1.7,
                ((0, tuple(min(255, int(v * 1.45 + 20)) for v in col)), (0.35, col),
                 (1, tuple(int(v * 0.32) for v in col))), noise=0.25)
        k.contour(icon, lump, 5)
    # red-hot pig bars at the right foot
    for x0, y0, x1, y1 in ((606, 646, 662, 672), (598, 672, 670, 700)):
        bar = icon.mask("rounded_rectangle", (x0, y0, x1, y1), radius=7)
        k.dfill(icon, bar, (x0, y0), (0.3, 1), y1 - y0 + 8,
                ((0, (255, 226, 140)), (0.45, (238, 106, 34)), (1, (120, 30, 12))), noise=0.08)
        k.contour(icon, bar, 5, (60, 18, 6, 230))
