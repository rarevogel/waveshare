#!/usr/bin/env python3
import random
import time
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in7b   # 2.7" e-Paper HAT (B)

# --- Display geometry ---
WIDTH = 176
HEIGHT = 264
MARGIN = 10

# Red symbol
SYMBOL_SIZE = 60
SYMBOL_THICKNESS = 5

# Fonts
FONT_RUNES = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoSansRunic-Regular.ttf", 26
)

# --- Futhark rune sets ---
ELDER = [
    0x16A0, 0x16A2, 0x16A6, 0x16A8, 0x16B1, 0x16B2, 0x16B7, 0x16B9,
    0x16BA, 0x16BE, 0x16C1, 0x16C3, 0x16C7, 0x16C8, 0x16C9, 0x16CB,
    0x16CF, 0x16D2, 0x16D6, 0x16D7, 0x16DA, 0x16DC, 0x16DE, 0x16DF
]

YOUNGER = [
    0x16A0, 0x16A2, 0x16A6, 0x16A8, 0x16B1, 0x16B2, 0x16B7, 0x16B9,
    0x16BA, 0x16BE, 0x16C1, 0x16C3, 0x16C7, 0x16C8, 0x16C9, 0x16CB
]

FUTHORC = [
    0x16A0, 0x16A2, 0x16A6, 0x16A8, 0x16B1, 0x16B2, 0x16B7, 0x16B9,
    0x16BA, 0x16BE, 0x16C1, 0x16C3, 0x16C7, 0x16C8, 0x16C9, 0x16CB,
    0x16CC, 0x16CD, 0x16CE, 0x16D0, 0x16D1, 0x16D3, 0x16D4, 0x16D5,
    0x16D6, 0x16D7, 0x16DA, 0x16DB, 0x16DC, 0x16DD, 0x16DE, 0x16DF, 0x16E0
]

# --- Helpers ---
def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def pick_futhark():
    name, runes = random.choice([
        ("Elder Futhark", ELDER),
        ("Younger Futhark", YOUNGER),
        ("Anglo-Saxon Futhorc", FUTHORC),
    ])
    return name, [chr(c) for c in runes]

def generate_rows_for_futhark(rune_set):
    return [
        "".join(random.choice(rune_set) for _ in range(random.randint(5, 8)))
        for _ in range(5)
    ]

# --- Stone texture ---
def draw_stone_texture(draw):
    density = 0.03
    for _ in range(int(WIDTH * HEIGHT * density)):
        x = random.randint(3, WIDTH - 3)
        y = random.randint(3, HEIGHT - 3)
        if random.random() < 0.6:
            draw.point((x, y), fill=0)

# =====================================================================
#  BORDERS — ornament bands after real Viking-age carving and metalwork
# =====================================================================
#
#  Each band is drawn once into a strip (outer edge at y=0), then pasted
#  at the top and rotated 180 degrees at the bottom, so the two ends of
#  the stone mirror each other. Repeats are fitted to the width so the
#  pattern never breaks off halfway at the right edge.

import math

BAND_H = 18

def _fit(period):
    """Nearest period that divides the width evenly."""
    n = max(1, round(WIDTH / period))
    return WIDTH / n, n

def _band_line(d, pts, w=5):
    """A carved strand: solid band with a fine groove down the middle."""
    d.line(pts, fill=0, width=w, joint="curve")
    d.line(pts, fill=1, width=1)

def _frame_lines(d, y_top, y_bot):
    d.line((0, y_top, WIDTH, y_top), fill=0, width=2)
    d.line((0, y_bot, WIDTH, y_bot), fill=0, width=1)

# 1. Two-strand plait (Borre / Jelling style interlace) ----------------
def band_plait(d):
    P, n = _fit(24)
    y_hi, y_lo, w = 4, 14, 2
    def strand(phase):
        # zig-zag strand with rounded turns; phase 0 starts high, 1 starts low
        pts = []
        for i in range(2 * n + 3):
            x = (i - 1) * P / 2
            hi = (i + phase) % 2 == 0
            pts.append((x, y_hi if hi else y_lo))
        return pts
    a, b = strand(0), strand(1)
    d.line(a, fill=0, width=w, joint="curve")
    d.line(b, fill=0, width=w, joint="curve")
    # crossings sit halfway along every diagonal; the strand on top alternates
    for i in range(len(a) - 1):
        top = a if i % 2 == 0 else b
        (x0, y0), (x1, y1) = top[i], top[i + 1]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ux, uy = (x1 - x0), (y1 - y0)
        L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
        seg = [(mx - ux * 3, my - uy * 3), (mx + ux * 3, my + uy * 3)]
        d.line(seg, fill=1, width=w + 3)
        d.line([(mx - ux * 6, my - uy * 6), (mx + ux * 6, my + uy * 6)], fill=0, width=w)
    d.line((0, 1, WIDTH, 1), fill=0, width=2)
    d.line((0, BAND_H - 1, WIDTH, BAND_H - 1), fill=0, width=1)

# 2. Borre ring-chain (Gokstad finds, Gosforth cross) -------------------
def band_ring_chain(d):
    P, n = _fit(14)
    cy, r = 9, 6
    centres = [i * P for i in range(n + 1)]
    for x in centres:
        d.ellipse((x - r, cy - r, x + r, cy + r), outline=0, width=2)
    # interlace each pair of neighbouring rings: one crossing over, one under
    for i, x in enumerate(centres[:-1]):
        mx = x + P / 2
        h = math.sqrt(max(r * r - (P / 2) ** 2, 0))
        for j, yy in enumerate((cy - h, cy + h)):
            d.ellipse((mx - 2, yy - 2, mx + 2, yy + 2), fill=1)
            over_right = (i + j) % 2 == 0
            ox = x + P if over_right else x
            ang = math.degrees(math.atan2(yy - cy, mx - ox))
            d.arc((ox - r, cy - r, ox + r, cy + r), ang - 25, ang + 25, fill=0, width=2)
        # the lozenge where the chain's centre line passes through
        d.polygon([(mx, cy - 2), (mx + 2, cy), (mx, cy + 2), (mx - 2, cy)], fill=0)
    d.line((0, 1, WIDTH, 1), fill=0, width=2)
    d.line((0, BAND_H - 1, WIDTH, BAND_H - 1), fill=0, width=1)

# 3. Runestone serpent band — the text-band animal of Uppland stones ----
def band_serpent(d):
    mid, half = 8, 4
    yc = lambda x: mid + 1.5 * math.sin(x / 9)
    xs = list(range(16, WIDTH - 9, 2))
    d.line([(x, yc(x) - half) for x in xs], fill=0, width=2, joint="curve")
    d.line([(x, yc(x) + half) for x in xs], fill=0, width=2, joint="curve")
    # paired cross-ties, like the bands that bind a runestone serpent
    step, n = _fit(22)
    for i in range(1, n):
        x = i * step
        for dx in (-2, 2):
            d.line((x + dx, yc(x) - half, x + dx, yc(x) + half), fill=0, width=1)
    # head at the left: almond with an eye, snout pointing outward
    hx, hy = 15, yc(15)
    d.polygon([(hx + 3, hy - 6), (hx - 5, hy - 4), (hx - 11, hy),
               (hx - 5, hy + 4), (hx + 3, hy + 6)], fill=0)
    d.ellipse((hx - 4, hy - 2, hx - 1, hy + 1), fill=1)
    # tail at the right: tapers to a point and curls
    tx = xs[-1]
    ty = yc(tx)
    d.polygon([(tx, ty - half - 1), (tx + 7, ty + 1), (tx, ty + half + 1)], fill=0)
    d.line([(tx + 6, ty + 1), (tx + 8, ty + 5), (tx + 5, ty + 7)], fill=0, width=1)
    d.line((0, BAND_H - 1, WIDTH, BAND_H - 1), fill=0, width=1)


# 4. Wolf-tooth band — the sawtooth framing of Gotland picture stones ---
def band_wolf_tooth(d):
    P, n = _fit(12)
    _frame_lines(d, 1, 14)
    for i in range(n):
        x = i * P
        d.polygon([(x, 2), (x + P, 2), (x + P / 2, 11)], fill=0)
        # punched pellet in each gap, as on brooches and the picture stones
        d.ellipse((x + P / 2 + P / 2 - 1.5, 9, x + P + 1.5, 12), fill=0)
        # groove inside each tooth
        d.line((x + P / 2, 3, x + P / 2, 7), fill=1, width=1)

# 5. Pellet band — beaded/punched border of oval brooches and mounts ---
def band_pellets(d):
    P, n = _fit(8)
    _frame_lines(d, 1, 14)
    d.line((0, 4, WIDTH, 4), fill=0, width=1)
    for i in range(n):
        x = i * P + P / 2
        d.ellipse((x - 2.5, 6.5, x + 2.5, 11.5), fill=0)
        d.ellipse((x - 0.5, 8.5, x + 0.5, 9.5), fill=1)   # the punch mark

# 6. Ringerike tendril scroll — running vine with curled offshoots -----
def band_tendrils(d):
    P, n = _fit(24)
    cy, a = 10, 4
    stem = [(x, cy + a * math.sin(2 * math.pi * x / P)) for x in range(-2, WIDTH + 3)]
    d.line(stem, fill=0, width=2, joint="curve")
    # a spiral tendril curls into the hollow under every crest
    for i in range(2 * n + 1):
        xc = i * P / 2 + P / 4
        top = (i % 2 == 1)                      # sin crest pointing up or down
        crest_y = cy - a if top else cy + a
        s = 1 if top else -1                    # curl grows into the hollow
        C = (xc + 1, crest_y + s * 4)
        pts = []
        for k in range(16):
            t = k / 15
            ang = -s * math.pi / 2 + s * 2 * math.pi * 1.1 * t
            rr = 4 * (1 - t) + 0.6
            pts.append((C[0] + rr * math.cos(ang), C[1] + rr * math.sin(ang)))
        d.line(pts, fill=0, width=1)
    d.line((0, 1, WIDTH, 1), fill=0, width=2)


BORDERS = [band_plait, band_ring_chain, band_serpent,
           band_wolf_tooth, band_pellets, band_tendrils]

def draw_knotwork_border(img):
    """Draw a matching ornament band at the top and bottom of the stone."""
    strip = Image.new("1", (WIDTH, BAND_H), 1)
    d = ImageDraw.Draw(strip)
    random.choice(BORDERS)(d)
    # weather the carving a little: lost pixels and a few chipped spots
    for _ in range(WIDTH // 2):
        strip.putpixel((random.randrange(WIDTH), random.randrange(BAND_H)), 1)
    for _ in range(random.randint(1, 3)):
        x, y = random.randrange(WIDTH), random.randrange(BAND_H)
        d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=1)

    # clear the stone texture under the bands, then stamp the ornament
    ImageDraw.Draw(img).rectangle((0, 0, WIDTH, BAND_H), fill=255)
    ImageDraw.Draw(img).rectangle((0, HEIGHT - BAND_H, WIDTH, HEIGHT), fill=255)
    mask = strip.point(lambda p: 255 if p == 0 else 0)
    img.paste(0, (0, 0), mask)
    img.paste(0, (0, HEIGHT - BAND_H), mask.rotate(180))

# =====================================================================
#  RED SYMBOLS — drawn as geometry, modelled on real Viking-age finds
# =====================================================================
#
#  Every symbol is drawn into a SYMBOL_SIZE x SYMBOL_SIZE box with lines
#  that look cut (uniform stroke, round ends), never with a font, so the
#  bind-runes share a real stave instead of two glyphs pasted on top of
#  each other.
#
#  On the red layer 0 = red ink and 1 = no ink, so "erasing" with fill=1
#  is used to cut the double contour that runestone bands have.

INK = 0
CUT = 1
STROKE = 4          # main carving width in pixels

def _line(d, pts, w=STROKE):
    """Polyline with round joints/ends, like a chisel groove."""
    d.line(pts, fill=INK, width=w, joint="curve")
    r = w / 2
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK)

# ---------------------------------------------------------------------
#  Bind-runes: real ones (e.g. Sigtuna, Kylver) hang several runes on
#  ONE shared vertical stave. Each rune below is described as the
#  branches it adds to a stave running from y=0 (top) to y=1 (bottom);
#  x is in stave heights, negative = left.
# ---------------------------------------------------------------------
STAVE_BRANCHES = {
    "ᚠ": [[(0, .32), (.38, .06)], [(0, .58), (.38, .32)]],               # fehu
    "ᚦ": [[(0, .25), (.34, .50), (0, .75)]],                             # thurisaz
    "ᚨ": [[(0, .06), (.36, .28)], [(0, .32), (.36, .54)]],               # ansuz
    "ᚱ": [[(0, 0), (.34, .22), (0, .44), (.36, 1)]],                     # raidho
    "ᚹ": [[(0, 0), (.34, .20), (0, .40)]],                               # wunjo
    "ᚾ": [[(-.26, .34), (.26, .60)]],                                    # naudiz
    "ᛁ": [],                                                             # isa
    "ᛇ": [[(0, 0), (.30, .16)], [(0, 1), (-.30, .84)]],                  # eihwaz
    "ᛉ": [[(0, .42), (-.34, .08)], [(0, .42), (.34, .08)]],              # algiz
    "ᛏ": [[(0, 0), (-.34, .30)], [(0, 0), (.34, .30)]],                  # tiwaz
    "ᛒ": [[(0, 0), (.34, .25), (0, .50), (.34, .75), (0, 1)]],           # berkano
    "ᛚ": [[(0, 0), (.36, .30)]],                                         # laguz
    "ᚷ": [[(-.38, .18), (.38, .82)], [(.38, .18), (-.38, .82)]],         # gebo
    "ᛦ": [[(0, .58), (-.34, .92)], [(0, .58), (.34, .92)]],              # yr (younger)
    "ᚬ": [[(-.30, .30), (.30, .55)]],                                    # óss (younger, short-twig style)
}

# Which stave-runes belong to which row of the stone
BIND_SETS = {
    "Elder Futhark":       "ᚠᚦᚨᚱᚹᚾᛁᛇᛉᛏᛒᛚᚷ",
    "Younger Futhark":     "ᚠᚦᚱᚾᛁᛏᛒᛚᛦᚬ",
    "Anglo-Saxon Futhorc": "ᚠᚦᚱᚹᚾᛁᛇᛉᛏᛒᛚᚷ",
}

def draw_bindrune(d, cx, cy, futhark_name):
    pool = list(BIND_SETS.get(futhark_name, BIND_SETS["Elder Futhark"]))
    pool.remove("ᛁ")                       # isa alone adds nothing
    runes = random.sample(pool, random.choice([2, 3, 3]))

    h = SYMBOL_SIZE - 10
    top = cy - h / 2
    branches = []
    for i, rune in enumerate(runes):
        mirror = -1 if (i == 1 and random.random() < 0.5) else 1   # mirrored twigs are common
        for br in STAVE_BRANCHES[rune]:
            branches.append([(cx + mirror * x * h, top + y * h) for (x, y) in br])

    _line(d, [(cx, top), (cx, top + h)], STROKE + 1)   # the shared stave
    for br in branches:
        _line(d, br)

# ---------------------------------------------------------------------
#  Valknut — three interlaced triangles (Stora Hammars I, Gotland;
#  Tängelgårda stone). Drawn as Borromean triangles with over/under gaps.
# ---------------------------------------------------------------------
def draw_valknut(d, cx, cy):
    import math
    s = SYMBOL_SIZE * 0.66            # triangle side
    off = s * 0.17                    # how far each triangle is shifted
    tris = []
    for k in range(3):
        a = math.radians(90 + 120 * k)
        ox, oy = cx + off * math.cos(a), cy + off * math.sin(a) + 3
        R = s / math.sqrt(3)
        tris.append([(ox + R * math.cos(math.radians(-90 + 120 * j)),
                      oy + R * math.sin(math.radians(-90 + 120 * j))) for j in range(3)])
    for t in tris:
        _line(d, t + [t[0]], STROKE)
    # interlace: where triangle k crosses triangle k+1, cut a small gap in k+1
    for k in range(3):
        a, b = tris[k], tris[(k + 1) % 3]
        for i in range(3):
            p1, p2 = a[i], a[(i + 1) % 3]
            for j in range(3):
                q1, q2 = b[j], b[(j + 1) % 3]
                hit = _seg_intersect(p1, p2, q1, q2)
                if hit:
                    # redraw the over-strand on top with a cut border
                    _gap(d, hit, p1, p2)

def _seg_intersect(p1, p2, q1, q2):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = p1, p2, q1, q2
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / den
    if 0.02 < t < 0.98 and 0.02 < u < 0.98:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None

def _gap(d, c, p1, p2):
    """Cut around a crossing, then lay the over-strand back in."""
    import math
    x, y = c
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    r = STROKE * 1.9
    d.ellipse((x - r, y - r, x + r, y + r), fill=CUT)
    d.line((x - ux * (r + 1), y - uy * (r + 1), x + ux * (r + 1), y + uy * (r + 1)),
           fill=INK, width=STROKE)

# ---------------------------------------------------------------------
#  Mjölnir pendant — after the Skåne / Erikstorp / Rømersdal finds:
#  suspension loop, short shaft, flaring head, punched dot ornament.
# ---------------------------------------------------------------------
def draw_mjolnir(d, cx, cy):
    S = SYMBOL_SIZE
    top = cy - S * 0.47
    d.ellipse((cx - 5, top, cx + 5, top + 10), outline=INK, width=3)   # suspension ring
    shaft_top = top + 9
    head_top = cy - S * 0.08
    bottom = cy + S * 0.44
    ws = 5
    body = [
        (cx - ws, shaft_top), (cx + ws, shaft_top),
        (cx + ws + 2, head_top),
        (cx + S * 0.20, head_top + 6),
        (cx + S * 0.36, bottom - 8),                 # right cheek flares down
        (cx + S * 0.42, bottom),
        (cx + S * 0.15, bottom - 5),
        (cx, bottom - 7),                            # gently curved lower edge
        (cx - S * 0.15, bottom - 5),
        (cx - S * 0.42, bottom),
        (cx - S * 0.36, bottom - 8),
        (cx - S * 0.20, head_top + 6),
        (cx - ws - 2, head_top),
    ]
    d.polygon(body, fill=INK)
    # punched ornament: dots down the shaft, a ring-and-dot on the head
    for y in range(int(shaft_top + 4), int(head_top), 5):
        d.ellipse((cx - 1, y - 1, cx + 1, y + 1), fill=CUT)
    hy = head_top + 12
    d.ellipse((cx - 5, hy - 5, cx + 5, hy + 5), outline=CUT, width=1)
    d.ellipse((cx - 1, hy - 1, cx + 1, hy + 1), fill=CUT)
    for sx in (-1, 1):
        for (dx, dy) in [(11, 12), (17, 18)]:
            x, y = cx + sx * dx, head_top + dy
            d.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=CUT)

# ---------------------------------------------------------------------
#  Triskele of drinking horns — Snoldelev stone (Denmark, 9th c.).
# ---------------------------------------------------------------------
def draw_horn_triskele(d, cx, cy):
    import math
    R = SYMBOL_SIZE * 0.46
    for k in range(3):
        a = math.radians(-90 + 120 * k)
        centre, left, right = [], [], []
        N = 16
        for i in range(N + 1):
            t = i / N
            ang = a + 2.3 * t                      # sweep, so the horns hook round each other
            rho = R * (0.12 + 0.86 * t)
            centre.append((cx + rho * math.cos(ang), cy + rho * math.sin(ang)))
        for i, (x, y) in enumerate(centre):
            t = i / N
            px, py = centre[max(i - 1, 0)]
            nx2, ny2 = centre[min(i + 1, N)]
            tx, ty = nx2 - px, ny2 - py
            L = math.hypot(tx, ty) or 1
            nx, ny = -ty / L, tx / L
            w = 1 + 3.8 * t                         # tip thin, mouth wide
            left.append((x + nx * w, y + ny * w))
            right.append((x - nx * w, y - ny * w))
        d.polygon(left + right[::-1], fill=INK)
        # rim band near the mouth, cut across the horn
        i = N - 2
        (lx, ly), (rx, ry) = left[i], right[i]
        d.line((lx, ly, rx, ry), fill=CUT, width=1)

# ---------------------------------------------------------------------
#  Runestone serpent — Urnes/Ringerike style band with double contour,
#  head seen from above with an eye, tail tucked under (Uppland stones).
# ---------------------------------------------------------------------
def draw_serpent(d, cx, cy):
    import math
    rx, ry = SYMBOL_SIZE * 0.36, SYMBOL_SIZE * 0.38
    a0, a1 = 230, 230 + 330                    # tail start -> head
    pts, widths = [], []
    for a in range(a0, a1 + 1, 5):
        t = (a - a0) / (a1 - a0)
        pts.append((cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a))))
        widths.append(2 + 7 * min(1, t * 3))  # tail tapers, body full width
    for i in range(len(pts) - 1):
        d.line((pts[i], pts[i + 1]), fill=INK, width=int(widths[i]))
        r = widths[i] / 2
        x, y = pts[i]
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK)
    # double contour: cut a thin line down the full-width part of the body
    body = [p for p, w in zip(pts, widths) if w >= 8]
    d.line(body[1:-1], fill=CUT, width=1, joint="curve")
    # head: almond along the direction of travel, with an eye and a curled lappet
    hx, hy = pts[-1]
    px, py = pts[-2]
    ux, uy = hx - px, hy - py
    L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
    nx, ny = -uy, ux
    head = [(hx - ux * 2 + nx * 5, hy - uy * 2 + ny * 5),
            (hx + ux * 7 + nx * 6, hy + uy * 7 + ny * 6),
            (hx + ux * 14, hy + uy * 14),
            (hx + ux * 7 - nx * 6, hy + uy * 7 - ny * 6),
            (hx - ux * 2 - nx * 5, hy - uy * 2 - ny * 5)]
    d.polygon(head, fill=INK)
    ex, ey = hx + ux * 6 + nx * 2, hy + uy * 6 + ny * 2
    d.ellipse((ex - 1.5, ey - 1.5, ex + 1.5, ey + 1.5), fill=CUT)
    lap = [(hx + nx * 5, hy + ny * 5), (hx - ux * 6 + nx * 10, hy - uy * 6 + ny * 10),
           (hx - ux * 11 + nx * 7, hy - uy * 11 + ny * 7)]
    d.line(lap, fill=INK, width=2, joint="curve")

# ---------------------------------------------------------------------
#  Triquetra — on Swedish runestones (Funbo U 1034) and Viking coins.
# ---------------------------------------------------------------------
def draw_triquetra(d, cx, cy):
    import math
    R = SYMBOL_SIZE * 0.30
    centres = [(cx + R * math.cos(math.radians(-90 + 120 * k)) * 0.58,
                cy + R * math.sin(math.radians(-90 + 120 * k)) * 0.58 + 3) for k in range(3)]
    # each petal = the lens between two neighbouring circles
    for i in range(3):
        for j in (i + 1) % 3, (i + 2) % 3:
            ax, ay = centres[i]
            bx, by = centres[j]
            # arc on circle i that lies inside circle j
            mid = math.degrees(math.atan2(by - ay, bx - ax))
            dist = math.hypot(bx - ax, by - ay)
            half = math.degrees(math.acos(dist / (2 * R)))
            d.arc((ax - R, ay - R, ax + R, ay + R), mid - half, mid + half,
                  fill=INK, width=STROKE)
    d.ellipse((cx - R * 0.42, cy - R * 0.42 + 3, cx + R * 0.42, cy + R * 0.42 + 3),
              outline=INK, width=2)

# ---------------------------------------------------------------------
#  Whirl disc — the great sun/whirl wheels of Gotlandic picture stones
#  (Sanda, Hablingbo). Curved rays inside a rope-like rim.
# ---------------------------------------------------------------------
def draw_whirl_disc(d, cx, cy):
    import math
    R = SYMBOL_SIZE * 0.44
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=INK, width=STROKE)
    d.ellipse((cx - R + 6, cy - R + 6, cx + R - 6, cy + R - 6), outline=INK, width=1)
    arms = random.choice([5, 6, 8])
    turn = random.choice([-1, 1])
    for k in range(arms):
        a0 = 2 * math.pi * k / arms
        pts = []
        for i in range(10):
            t = i / 9
            rr = 3 + (R - 8) * t
            ang = a0 + turn * 1.3 * t
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        d.line(pts, fill=INK, width=3, joint="curve")
    d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=INK)

# ---------------------------------------------------------------------
#  Sun cross / ring cross — Bronze-age rock carvings and Gotland stones.
# ---------------------------------------------------------------------
def draw_sun_cross(d, cx, cy):
    R = SYMBOL_SIZE * 0.36
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=INK, width=STROKE)
    _line(d, [(cx - R - 4, cy), (cx + R + 4, cy)])
    _line(d, [(cx, cy - R - 4), (cx, cy + R + 4)])
    # cup marks between the arms, as on the rock carvings
    for (sx, sy) in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
        x, y = cx + sx * R * 0.42, cy + sy * R * 0.42
        d.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=INK)

# ---------------------------------------------------------------------
#  Picking and placing the symbol
# ---------------------------------------------------------------------
SYMBOLS = [
    # (weight, function)
    (5, "bindrune"),
    (2, draw_valknut),
    (2, draw_mjolnir),
    (2, draw_serpent),
    (1, draw_horn_triskele),
    (1, draw_triquetra),
    (1, draw_whirl_disc),
    (1, draw_sun_cross),
]

def draw_red_symbol(red_img, corner, rune_bboxes, futhark_name):
    pad = 12

    if corner == "tl":
        x0, y0 = pad, pad
    elif corner == "tr":
        x0, y0 = WIDTH - SYMBOL_SIZE - pad, pad
    elif corner == "bl":
        x0, y0 = pad, HEIGHT - SYMBOL_SIZE - pad
    else:
        x0, y0 = WIDTH - SYMBOL_SIZE - pad, HEIGHT - SYMBOL_SIZE - pad

    x1, y1 = x0 + SYMBOL_SIZE, y0 + SYMBOL_SIZE
    for (rx0, ry0, rx1, ry1) in rune_bboxes:
        if not (x1 < rx0 or x0 > rx1 or y1 < ry0 or y0 > ry1):
            return False

    # Draw on a private canvas so "cut" pixels never erase anything else,
    # then stamp the inked pixels onto the red layer.
    tile = Image.new("1", (SYMBOL_SIZE, SYMBOL_SIZE), 1)
    d = ImageDraw.Draw(tile)
    c = SYMBOL_SIZE // 2

    weights, choices = zip(*SYMBOLS)
    choice = random.choices(choices, weights=weights)[0]
    if choice == "bindrune":
        draw_bindrune(d, c, c, futhark_name)
    else:
        choice(d, c, c)

    # slight weathering: knock out a few pixels so it reads as paint on stone
    for _ in range(SYMBOL_SIZE * 3):
        tile.putpixel((random.randrange(SYMBOL_SIZE), random.randrange(SYMBOL_SIZE)), 1)

    mask = tile.point(lambda p: 255 if p == 0 else 0)
    red_img.paste(0, (x0, y0), mask)
    return True

# --- PNG export ---
def save_preview_png(black, red, filename):
    preview = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    black_mask = black.point(lambda p: 255 - p)
    red_mask = red.point(lambda p: 255 - p)
    preview.paste((0, 0, 0), mask=black_mask)
    preview.paste((255, 0, 0), mask=red_mask)
    preview.save(filename)

# --- Render one frame ---
def render_frame(epd):
    black = Image.new("1", (WIDTH, HEIGHT), 255)
    red = Image.new("1", (WIDTH, HEIGHT), 255)
    draw_black = ImageDraw.Draw(black)
    draw_red = ImageDraw.Draw(red)

    draw_stone_texture(draw_black)
    draw_knotwork_border(black)

    futhark_name, rune_set = pick_futhark()
    rows = generate_rows_for_futhark(rune_set)

    rune_bboxes = []
    row_height = 32
    start_y = MARGIN + 20

    for i, row in enumerate(rows):
        y = start_y + i * row_height
        w, h = text_size(draw_black, row, FONT_RUNES)
        x = (WIDTH - w) // 2
        draw_black.text((x, y), row, font=FONT_RUNES, fill=0)
        rune_bboxes.append((x, y, x + w, y + h))

    corners = ["tl", "tr", "bl", "br"]
    random.shuffle(corners)
    for c in corners:
        if draw_red_symbol(red, c, rune_bboxes, futhark_name):
            break

    timestamp = int(time.time())
    save_preview_png(black, red, f"frame_{timestamp}.png")

    epd.display(epd.getbuffer(black), epd.getbuffer(red))

# --- Main loop ---
def main():
    epd = epd2in7b.EPD()
    epd.init()
    try:
        while True:
            render_frame(epd)
            time.sleep(15)

    except KeyboardInterrupt:
        print("Exiting cleanly...")
        epd.init()      # re-init to ensure clean state
        epd.Clear()     # optional: clear display
        epd.sleep()     # put panel to sleep

    finally:
        # ALWAYS release GPIO
        epd2in7b.epdconfig.module_exit()

if __name__ == "__main__":
    main()

