#!/usr/bin/env python3
"""
Classic Maya Initial Series inscription on a 2.7" e-Paper HAT (B).

Each frame shows a real, internally consistent Maya date laid out the way
a stela or panel inscription is:

    +-----------------------+
    |   Introductory glyph  |   A1-B2  (ISIG, spans both columns)
    +-----------+-----------+
    | Bak'tun   | K'atun    |   A3  B3
    | Tun       | Winal     |   A4  B4
    | K'in      | Tzolk'in  |   A5  B5
    | Glyph G   | Haab      |   A6  B6
    +-----------+-----------+

read in paired columns, left-to-right, top-to-bottom. Coefficients are
bar-and-dot numerals in red, as in the codices; zero is a shell and day 0
of a month is the "seating" sign. The glyphs are simplified line drawings
of the real signs, sized for a 176x264 panel.
"""
import math
import os
import random
import time
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in7b   # 2.7" e-Paper HAT (B)

# --- Display geometry ---
WIDTH = 176
HEIGHT = 264

SHOW_READING = True     # small transliteration + AD year at the bottom

# =====================================================================
#  CALENDAR
# =====================================================================
DAY_NAMES = ["Imix", "Ik'", "Ak'bal", "K'an", "Chikchan", "Kimi", "Manik'",
             "Lamat", "Muluk", "Ok", "Chuwen", "Eb", "Ben", "Ix", "Men",
             "Kib", "Kaban", "Etz'nab", "Kawak", "Ajaw"]
MONTH_NAMES = ["Pop", "Wo", "Sip", "Sotz'", "Sek", "Xul", "Yaxk'in", "Mol",
               "Ch'en", "Yax", "Sak", "Keh", "Mak", "K'ank'in", "Muwan",
               "Pax", "K'ayab", "Kumk'u", "Wayeb"]
GMT_CORRELATION = 584283        # Julian Day Number of 13.0.0.0.0 4 Ajaw 8 Kumk'u

def random_long_count():
    """A random date inside the Classic period (8.18.0.0.0 to 10.4.0.0.0)."""
    lo = 8 * 144000 + 18 * 7200
    hi = 10 * 144000 + 4 * 7200
    days = random.randint(lo, hi)
    lc = []
    for unit in (144000, 7200, 360, 20, 1):
        lc.append(days // unit)
        days %= unit
    return lc

def calendar_round(lc):
    days = lc[0] * 144000 + lc[1] * 7200 + lc[2] * 360 + lc[3] * 20 + lc[4]
    tz_num = (days + 3) % 13 + 1
    tz_day = (days + 19) % 20
    haab = (days + 348) % 365
    g = days % 9 or 9                       # Lord of the Night, G1-G9
    return days, tz_num, tz_day, haab % 20, haab // 20, g

def julian_year(days):
    """Year (AD/BC) in the proleptic Julian calendar, as historians quote it."""
    jdn = days + GMT_CORRELATION
    c = jdn + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    return d - 4800 + m // 10

# =====================================================================
#  DRAWING PRIMITIVES
# =====================================================================
#  All glyph functions take (d, x, y, w, h): the box of the main sign.
#  Black layer: 0 = ink. Red layer: 0 = ink. 255 = paper on both.

INK = 0
PAPER = 255

def rbox(d, box, r=6, w=2, fill=None):
    d.rounded_rectangle(box, radius=r, outline=INK, width=w, fill=fill)

def dot(d, x, y, r=1.5, fill=INK):
    d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

def ring(d, x, y, r, w=1):
    d.ellipse((x - r, y - r, x + r, y + r), outline=INK, width=w)

def day_cartouche(d, x, y, w, h):
    """The day-sign cartouche: rounded frame on a three-lobed pedestal."""
    ph = max(4, h // 6)
    rbox(d, (x + 2, y, x + w - 2, y + h - ph), r=7, w=2)
    # pedestal: three little scrolls under the frame
    cx = x + w / 2
    by = y + h - ph
    for dx in (-w * 0.28, 0, w * 0.28):
        d.arc((cx + dx - 4, by - 2, cx + dx + 4, by + ph + 2), 0, 180, fill=INK, width=2)
    d.line((x + 6, y + h - 1, x + w - 6, y + h - 1), fill=INK, width=1)
    return (x + 6, y + 4, x + w - 6, y + h - ph - 4)   # inner area

def kin_flower(d, cx, cy, r):
    """K'in: the four-petalled sun flower."""
    for (dx, dy) in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        px, py = cx + dx * r * 0.55, cy + dy * r * 0.55
        rr = r * 0.42
        d.ellipse((px - rr, py - rr, px + rr, py + rr), outline=INK, width=2)
    ring(d, cx, cy, r * 0.22, 1)
    dot(d, cx, cy, 1)

def comb(d, x0, y0, x1, y1, n=4, vertical=True):
    """The 'comb' flange of the Introductory Glyph and the tun superfix."""
    if vertical:
        d.line((x0, y0, x0, y1), fill=INK, width=2)
        for i in range(n):
            y = y0 + (i + 0.5) * (y1 - y0) / n
            d.line((x0, y, x1, y), fill=INK, width=1)
    else:
        d.line((x0, y0, x1, y0), fill=INK, width=2)
        for i in range(n):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            d.line((x, y0, x, y1), fill=INK, width=1)

# =====================================================================
#  DAY SIGNS (Tzolk'in) — schematic versions of the 20 day glyphs
# =====================================================================
def _day_inner(d, idx, x0, y0, x1, y1):
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    name = DAY_NAMES[idx]
    if name == "Imix":          # water lily: row of dots over vertical stripes
        for i in range(4):
            dot(d, x0 + (i + 0.5) * w / 4, y0 + 3, 1.5)
        d.arc((x0, y0 + 4, x1, y1 + h * 0.6), 200, 340, fill=INK, width=2)
        for i in range(3):
            x = x0 + (i + 1) * w / 4
            d.line((x, cy, x, y1), fill=INK, width=1)
    elif name == "Ik'":         # wind: the T-shaped window
        d.line((cx - w * 0.32, y0 + h * 0.25, cx + w * 0.32, y0 + h * 0.25), fill=INK, width=3)
        d.line((cx, y0 + h * 0.25, cx, y1 - 1), fill=INK, width=3)
    elif name == "Ak'bal":      # night: curled scroll with dark crescents
        d.arc((cx - w * 0.35, cy - h * 0.35, cx + w * 0.35, cy + h * 0.35), 180, 360, fill=INK, width=2)
        d.arc((cx - w * 0.2, cy - h * 0.2, cx + w * 0.2, cy + h * 0.25), 180, 360, fill=INK, width=2)
        d.pieslice((cx - 4, cy, cx + 4, cy + 8), 0, 180, fill=INK)
        for i in (-1, 1):
            dot(d, cx + i * w * 0.3, y1 - 2, 1.5)
    elif name == "K'an":        # maize/ripeness: the K'an cross
        s = min(w, h) * 0.32
        d.polygon([(cx - s * 0.35, cy - s), (cx + s * 0.35, cy - s), (cx + s * 0.35, cy - s * 0.35),
                   (cx + s, cy - s * 0.35), (cx + s, cy + s * 0.35), (cx + s * 0.35, cy + s * 0.35),
                   (cx + s * 0.35, cy + s), (cx - s * 0.35, cy + s), (cx - s * 0.35, cy + s * 0.35),
                   (cx - s, cy + s * 0.35), (cx - s, cy - s * 0.35), (cx - s * 0.35, cy - s * 0.35)],
                  outline=INK, width=2)
    elif name == "Chikchan":    # serpent: cross-hatched snakeskin
        for i in range(-2, 3):
            d.line((cx + i * 5 - 4, y0 + 2, cx + i * 5 + 4, y1 - 2), fill=INK, width=1)
            d.line((cx + i * 5 + 4, y0 + 2, cx + i * 5 - 4, y1 - 2), fill=INK, width=1)
        d.arc((x0 - 2, y0, x1 + 2, y1 + h * 0.4), 200, 340, fill=INK, width=2)
    elif name == "Kimi":        # death: skull with the "percent" sign
        d.arc((x0, y0, x1, y1 + h * 0.3), 180, 360, fill=INK, width=2)
        d.line((cx - w * 0.25, y1 - 2, cx + w * 0.25, cy - h * 0.15), fill=INK, width=2)
        dot(d, cx - w * 0.22, cy - h * 0.1, 2)
        dot(d, cx + w * 0.22, y1 - 4, 2)
    elif name == "Manik'":      # deer/hand: a grasping hand
        d.rounded_rectangle((cx - w * 0.3, cy - h * 0.15, cx + w * 0.3, y1), radius=4, outline=INK, width=2)
        for i in range(3):
            x = cx - w * 0.2 + i * w * 0.2
            d.line((x, cy - h * 0.15, x, cy + h * 0.1), fill=INK, width=1)
        d.ellipse((cx - w * 0.38, cy - h * 0.35, cx - w * 0.1, cy - h * 0.05), outline=INK, width=2)
    elif name == "Lamat":       # star/Venus: cross with four dots
        s = min(w, h) * 0.38
        d.line((cx - s, cy - s, cx + s, cy + s), fill=INK, width=2)
        d.line((cx - s, cy + s, cx + s, cy - s), fill=INK, width=2)
        for (sx, sy) in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            dot(d, cx + sx * s * 0.75, cy + sy * s * 0.75, 2)
    elif name == "Muluk":       # water: a jade disk with inner ring
        ring(d, cx, cy, min(w, h) * 0.38, 2)
        ring(d, cx, cy, min(w, h) * 0.16, 1)
        dot(d, cx - w * 0.3, y1 - 1, 1.5); dot(d, cx + w * 0.3, y1 - 1, 1.5)
    elif name == "Ok":          # dog: pendant ear and eye
        d.polygon([(cx - w * 0.3, y0 + 2), (cx + w * 0.2, y0 + 2), (cx + w * 0.35, cy),
                   (cx + w * 0.1, y1)], outline=INK, width=2)
        dot(d, cx - w * 0.05, cy - 2, 2)
    elif name == "Chuwen":      # monkey: curled muzzle
        d.arc((cx - w * 0.35, cy - h * 0.3, cx + w * 0.2, cy + h * 0.4), 300, 220, fill=INK, width=2)
        dot(d, cx - w * 0.05, cy - h * 0.05, 2)
        d.line((cx + w * 0.15, cy + h * 0.2, cx + w * 0.38, cy + h * 0.2), fill=INK, width=2)
    elif name == "Eb":          # face with scattered dots
        d.arc((x0 + 2, y0, x1 + 4, y1 + h * 0.4), 180, 300, fill=INK, width=2)
        for (fx, fy) in ((.3, .35), (.55, .25), (.45, .6), (.7, .55)):
            dot(d, x0 + fx * w, y0 + fy * h, 1.5)
    elif name == "Ben":         # reed: two uprights over a base bar
        for dx in (-w * 0.18, w * 0.18):
            d.line((cx + dx, y0 + 3, cx + dx, cy + h * 0.2), fill=INK, width=2)
            d.arc((cx + dx - 4, y0, cx + dx + 4, y0 + 6), 180, 360, fill=INK, width=2)
        d.line((cx - w * 0.35, cy + h * 0.2, cx + w * 0.35, cy + h * 0.2), fill=INK, width=2)
        d.line((cx - w * 0.25, y1 - 1, cx + w * 0.25, y1 - 1), fill=INK, width=2)
    elif name == "Ix":          # jaguar: three spots in a triangle
        for (fx, fy) in ((.5, .3), (.3, .68), (.7, .68)):
            ring(d, x0 + fx * w, y0 + fy * h, 3, 1)
            dot(d, x0 + fx * w, y0 + fy * h, 1)
    elif name == "Men":         # old one/eagle: spiral eye and wrinkle
        pts = []
        for i in range(20):
            t = i / 19
            a = 4 * math.pi * t
            rr = min(w, h) * 0.38 * (1 - t) + 1
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.line(pts, fill=INK, width=1)
    elif name == "Kib":         # shell/insect: nested curves
        for k in range(3):
            s = (k + 1) * min(w, h) * 0.13
            d.arc((cx - s, cy - s, cx + s, cy + s), 120, 420 - 60, fill=INK, width=1 + (k == 2))
    elif name == "Kaban":       # earth: the curl with a dot
        d.arc((cx - w * 0.3, cy - h * 0.35, cx + w * 0.3, cy + h * 0.35), 60, 360, fill=INK, width=2)
        d.arc((cx - w * 0.12, cy - h * 0.12, cx + w * 0.12, cy + h * 0.12), 0, 300, fill=INK, width=1)
        dot(d, cx + w * 0.3, y1 - 2, 1.5)
    elif name == "Etz'nab":     # flint: crossed blades with hatching
        d.line((x0 + 2, y0 + 2, x1 - 2, y1 - 2), fill=INK, width=2)
        d.line((x0 + 2, y1 - 2, x1 - 2, y0 + 2), fill=INK, width=2)
        d.line((cx, y0 + 2, cx, y1 - 2), fill=INK, width=1)
        d.line((x0 + 2, cy, x1 - 2, cy), fill=INK, width=1)
    elif name == "Kawak":       # storm: grape-cluster markings and a bracket
        for (fx, fy) in ((.3, .3), (.45, .2), (.6, .3)):
            ring(d, x0 + fx * w, y0 + fy * h, 2.5, 1)
        d.arc((cx - w * 0.3, cy - h * 0.05, cx + w * 0.3, y1 + h * 0.2), 180, 360, fill=INK, width=2)
        d.line((x1 - 4, cy, x1 - 4, y1 - 1), fill=INK, width=2)
    elif name == "Ajaw":        # lord: the round face with eyes and mouth
        ring(d, cx, cy, min(w, h) * 0.42, 2)
        dot(d, cx - w * 0.15, cy - h * 0.12, 2)
        dot(d, cx + w * 0.15, cy - h * 0.12, 2)
        ring(d, cx, cy + h * 0.2, min(w, h) * 0.12, 2)

def glyph_day(d, idx, x, y, w, h):
    inner = day_cartouche(d, x, y, w, h)
    _day_inner(d, idx, *inner)

# =====================================================================
#  MONTH SIGNS (Haab) — main sign plus the affixes that tell them apart
# =====================================================================
#  Ch'en, Yax, Sak and Keh share one main sign and differ only in the
#  colour prefix (black, green, white, red) — that is how the real glyphs
#  work. The others use their characteristic main elements.

def _color_prefix(d, kind, x0, y0, x1, y1):
    cx = (x0 + x1) / 2
    if kind == "black":          # ik' darkness: filled crescent
        d.pieslice((cx - 7, y0 - 2, cx + 7, y1 + 6), 180, 360, fill=INK)
    elif kind == "yax":          # yax: oval with inner hook
        d.ellipse((cx - 9, y0, cx + 9, y1), outline=INK, width=2)
        d.line((cx - 2, y0 + 2, cx + 2, y1 - 1), fill=INK, width=1)
    elif kind == "sak":          # sak: flower/bone with a cross line
        d.rounded_rectangle((cx - 9, y0, cx + 9, y1), radius=3, outline=INK, width=2)
        d.line((cx - 6, (y0 + y1) / 2, cx + 6, (y0 + y1) / 2), fill=INK, width=1)
    elif kind == "chak":         # chak: hatched bar (red)
        d.rectangle((cx - 9, y0 + 1, cx + 9, y1 - 1), outline=INK, width=1)
        for i in range(-8, 9, 3):
            d.line((cx + i, y0 + 1, cx + i + 3, y1 - 1), fill=INK, width=1)

def _chen_main(d, x0, y0, x1, y1):
    """The 'moon/cave' main sign shared by Ch'en, Yax, Sak, Keh."""
    rbox(d, (x0, y0, x1, y1), r=6, w=2)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.arc((x0 + 3, cy - 3, x1 - 3, y1 + 6), 180, 360, fill=INK, width=2)
    dot(d, cx - 5, cy + 4, 1.5); dot(d, cx + 5, cy + 4, 1.5)

def glyph_month(d, idx, x, y, w, h):
    name = MONTH_NAMES[idx]
    top = (x + 4, y, x + w - 4, y + h * 0.28)            # superfix area
    main = (x + 2, y + h * 0.3, x + w - 2, y + h - 1)    # main sign area
    mx0, my0, mx1, my1 = main
    mcx, mcy = (mx0 + mx1) / 2, (my0 + my1) / 2
    if name in ("Ch'en", "Yax", "Sak", "Keh"):
        _color_prefix(d, {"Ch'en": "black", "Yax": "yax", "Sak": "sak", "Keh": "chak"}[name], *top)
        _chen_main(d, *main)
        return
    rbox(d, main, r=6, w=2)
    if name == "Pop":            # the woven mat (pop), symbol of kingship
        for i in range(-3, 4):
            d.line((mcx + i * 6 - 8, my0 + 2, mcx + i * 6 + 8, my1 - 2), fill=INK, width=1)
            d.line((mcx + i * 6 + 8, my0 + 2, mcx + i * 6 - 8, my1 - 2), fill=INK, width=1)
        d.rounded_rectangle(main, radius=6, outline=INK, width=2)
        kin_flower(d, (top[0] + top[2]) / 2, (top[1] + top[3]) / 2, 6)
    elif name in ("Wo", "Sip"):  # black / red sky-and-dots signs
        _color_prefix(d, "black" if name == "Wo" else "chak", *top)
        for (fx, fy) in ((.3, .4), (.7, .4), (.5, .7)):
            dot(d, mx0 + fx * (mx1 - mx0), my0 + fy * (my1 - my0), 2)
    elif name == "Sotz'":        # bat head: leaf-nose and ear
        d.polygon([(mcx, my0 + 3), (mcx + 7, mcy), (mcx, my1 - 3), (mcx - 7, mcy)], outline=INK, width=2)
        d.arc((mcx - 12, my0 - 4, mcx + 2, my0 + 8), 180, 360, fill=INK, width=2)
    elif name == "Sek":          # sky-sign over k'in
        comb(d, top[0] + 4, top[3] - 2, top[2] - 4, top[1] + 1, 5, vertical=False)
        kin_flower(d, mcx, mcy, 8)
    elif name == "Xul":          # dog: ear and snout
        d.polygon([(mx0 + 5, my0 + 4), (mcx + 4, my0 + 4), (mx1 - 4, mcy + 2), (mcx, my1 - 3)],
                  outline=INK, width=2)
        dot(d, mcx - 2, mcy - 1, 2)
    elif name == "Yaxk'in":      # yax prefix + k'in
        _color_prefix(d, "yax", *top)
        kin_flower(d, mcx, mcy, 8)
    elif name == "Mol":          # water/cloud: three circles in a bracket
        for i in range(3):
            ring(d, mx0 + (i + 0.5) * (mx1 - mx0) / 3, mcy, 3.5, 1)
        d.line((mx0 + 3, my1 - 4, mx1 - 3, my1 - 4), fill=INK, width=2)
    elif name == "Mak":          # comb-and-crosshatch
        comb(d, mx0 + 4, my0 + 3, mx1 - 4, mcy, 5, vertical=False)
        for i in range(3):
            dot(d, mx0 + (i + 1) * (mx1 - mx0) / 4, my1 - 5, 1.5)
    elif name == "K'ank'in":     # k'an superfix + k'in
        s = 5
        tcx, tcy = (top[0] + top[2]) / 2, (top[1] + top[3]) / 2
        d.rectangle((tcx - s, tcy - s / 2, tcx + s, tcy + s / 2), outline=INK, width=2)
        kin_flower(d, mcx, mcy, 8)
    elif name == "Muwan":        # screech-owl: big eye with feather lines
        ring(d, mcx - 3, mcy, 5, 2); dot(d, mcx - 3, mcy, 1.5)
        for i in range(3):
            d.line((mcx + 5, my0 + 4 + i * 4, mx1 - 3, my0 + 2 + i * 4), fill=INK, width=1)
    elif name == "Pax":          # the drum: vertical bands
        for i in range(1, 4):
            x = mx0 + i * (mx1 - mx0) / 4
            d.line((x, my0 + 3, x, my1 - 3), fill=INK, width=1)
        d.line((mx0 + 3, mcy, mx1 - 3, mcy), fill=INK, width=2)
    elif name == "K'ayab":       # turtle: shell with plates
        d.arc((mx0 + 3, my0 + 2, mx1 - 3, my1 + 8), 180, 360, fill=INK, width=2)
        for i in range(3):
            ring(d, mx0 + (i + 1) * (mx1 - mx0) / 4, mcy + 2, 2.5, 1)
    elif name == "Kumk'u":       # granary/ripe maize: dotted mound
        d.arc((mx0 + 3, mcy - 4, mx1 - 3, my1 + 10), 180, 360, fill=INK, width=2)
        for i in range(4):
            dot(d, mx0 + (i + 0.5) * (mx1 - mx0) / 4, my0 + 5, 1.5)
    elif name == "Wayeb":        # the 5 unlucky days: crossed bands
        d.line((mx0 + 4, my0 + 4, mx1 - 4, my1 - 4), fill=INK, width=2)
        d.line((mx0 + 4, my1 - 4, mx1 - 4, my0 + 4), fill=INK, width=2)

# =====================================================================
#  PERIOD GLYPHS, INTRODUCTORY GLYPH, GLYPH G
# =====================================================================
def _tun(d, x0, y0, x1, y1):
    """Tun ('stone/year'): drum-like sign with cauac markings below."""
    rbox(d, (x0, y0, x1, y1), r=5, w=2)
    cx = (x0 + x1) / 2
    yb = y0 + (y1 - y0) * 0.55
    d.line((x0 + 3, yb, x1 - 3, yb), fill=INK, width=1)
    for i in range(3):
        ring(d, x0 + (i + 0.5) * (x1 - x0) / 3, (yb + y1) / 2, 2.5, 1)
    d.line((x0 + 5, y0 + 4, x0 + 5, yb - 2), fill=INK, width=1)
    d.line((x1 - 5, y0 + 4, x1 - 5, yb - 2), fill=INK, width=1)
    dot(d, cx, (y0 + yb) / 2, 1.5)

def glyph_period(d, which, x, y, w, h):
    if which == "kin":
        kin_flower(d, x + w / 2, y + h / 2, min(w, h) * 0.42)
        return
    if which == "winal":         # the frog-headed winal: U-frame with curls
        x0, y0, x1, y1 = x + 3, y + 4, x + w - 3, y + h - 2
        d.line((x0, y0, x0, y1 - 6), fill=INK, width=2)
        d.arc((x0, y1 - 14, x1, y1), 0, 180, fill=INK, width=2)
        d.line((x1, y0, x1, y1 - 6), fill=INK, width=2)
        d.arc((x0 - 4, y0 - 2, x0 + 8, y0 + 10), 180, 450, fill=INK, width=2)
        d.arc((x1 - 8, y0 - 2, x1 + 4, y0 + 10), 90, 360, fill=INK, width=2)
        dot(d, (x0 + x1) / 2, (y0 + y1) / 2 - 2, 2)
        return
    sup_h = h * 0.3
    _tun(d, x + 2, y + sup_h, x + w - 2, y + h - 1)
    if which == "katun":         # tun with the cauac 'comb' superfix
        comb(d, x + 6, y + sup_h - 2, x + w - 6, y + 2, 5, vertical=False)
    elif which == "baktun":      # tun with doubled superfix (pik)
        comb(d, x + 6, y + sup_h - 2, x + w - 6, y + sup_h * 0.5, 5, vertical=False)
        comb(d, x + 10, y + sup_h * 0.45, x + w - 10, y + 1, 3, vertical=False)

def glyph_isig(d, month_idx, x, y, w, h):
    """Initial Series Introductory Glyph: tun core, comb flanges either
    side, tripartite superfix, and the patron of the month in the middle."""
    cx = x + w / 2
    core_w = w * 0.38
    cy0 = y + h * 0.32
    _tun(d, cx - core_w / 2, cy0, cx + core_w / 2, y + h - 1)
    # comb flanges
    comb(d, cx - core_w / 2 - 3, cy0 + 2, cx - core_w / 2 - 12, y + h - 3, 5)
    comb(d, cx + core_w / 2 + 3, cy0 + 2, cx + core_w / 2 + 12, y + h - 3, 5)
    # tripartite superfix: bowl flanked by two scrolls
    d.arc((cx - 8, y + 2, cx + 8, cy0 + 4), 0, 180, fill=INK, width=2)
    d.line((cx, y + 2, cx, cy0 - 6), fill=INK, width=1)
    d.arc((cx - 22, y + 4, cx - 8, cy0 + 2), 180, 450, fill=INK, width=2)
    d.arc((cx + 8, y + 4, cx + 22, cy0 + 2), 90, 360, fill=INK, width=2)
    # variable element: a small version of the month sign as the patron
    pw = core_w * 0.55
    vx0, vy0 = cx - pw / 2, cy0 + 4
    d.rounded_rectangle((vx0, vy0, vx0 + pw, vy0 + (y + h - 1 - cy0) * 0.42), radius=3,
                        outline=INK, width=1)
    random.seed(month_idx)                    # same patron for the same month
    for _ in range(3):
        dot(d, vx0 + random.uniform(3, pw - 3), vy0 + random.uniform(3, 8), 1)
    random.seed()

def glyph_g(d, g, x, y, w, h):
    """Glyph G: the Lord of the Night (G1-G9) — head in profile with a
    distinguishing headdress element."""
    x0, y0, x1, y1 = x + 3, y + h * 0.28, x + w - 3, y + h - 1
    d.arc((x0, y0, x1 + (x1 - x0) * 0.4, y1 + (y1 - y0) * 0.3), 150, 270, fill=INK, width=2)
    d.line((x0 + 2, y1 - 2, x1 - 2, y1 - 2), fill=INK, width=2)
    dot(d, x0 + (x1 - x0) * 0.4, y0 + (y1 - y0) * 0.45, 2)
    d.line((x0 + (x1 - x0) * 0.3, y0 + (y1 - y0) * 0.75, x0 + (x1 - x0) * 0.6,
            y0 + (y1 - y0) * 0.75), fill=INK, width=1)
    # headdress: G9 carries the k'in sign (as on real inscriptions); the
    # others get a distinct element so each lord looks different
    hx, hy = (x0 + x1) / 2, y + h * 0.14
    if g == 9:
        kin_flower(d, hx, hy, 6)
    else:
        for i in range(g if g <= 4 else g - 4):
            d.line((hx - 8 + i * 5, y + 1, hx - 8 + i * 5, y0 - 1), fill=INK, width=1)
        if g > 4:
            ring(d, hx + 8, hy, 3, 1)

# =====================================================================
#  BAR-AND-DOT NUMERALS (red, drawn as a prefix on the left)
# =====================================================================
def numeral(d, n, x, y, w, h, period=False):
    """Vertical bar-and-dot numeral in the box (x, y, w, h).
    Bars stand upright next to the sign, dots in a column outside them.
    One or two dots get crescent fillers, as scribes did to balance the
    block. Zero is drawn as a shell (Long Count positions)."""
    cy = y + h / 2
    if n == 0:
        # shell: oval with teeth
        d.ellipse((x + 1, cy - h * 0.3, x + w - 1, cy + h * 0.3), outline=INK, width=2)
        for i in range(3):
            yy = cy - h * 0.15 + i * h * 0.15
            d.line((x + w * 0.35, yy, x + w - 3, yy), fill=INK, width=1)
        return
    bars, dots = divmod(n, 5)
    bar_w = 3
    gap = 2
    bx = x + w - bars * (bar_w + gap)
    for i in range(bars):
        xx = bx + i * (bar_w + gap)
        d.rounded_rectangle((xx, y + 2, xx + bar_w, y + h - 2), radius=2, fill=INK)
    if dots:
        dx = bx - 4 if bars else x + w - 4
        # 1 dot: filler-dot-filler, 2 dots: dot-filler-dot, 3-4: just dots
        pattern = {1: "fdf", 2: "dfd"}.get(dots, "d" * dots)
        span = h - 6
        for i, kind in enumerate(pattern):
            yy = y + 3 + (i + 0.5) * span / len(pattern)
            if kind == "f":
                d.arc((dx - 3, yy - 2, dx + 3, yy + 2), 0, 180, fill=INK, width=1)
            else:
                dot(d, dx, yy, 2.5)

def seating(d, x, y, w, h):
    """'Seating of' (day 0 of a month): a cushion with a fringe."""
    cy = y + h / 2
    d.arc((x + 1, cy - h * 0.25, x + w - 1, cy + h * 0.25), 90, 270, fill=INK, width=2)
    for i in range(4):
        yy = cy - h * 0.18 + i * h * 0.12
        d.line((x + w * 0.45, yy, x + w - 1, yy), fill=INK, width=1)

# =====================================================================
#  FRAMES (red layer)
# =====================================================================
#  Each frame returns the inner box available for the inscription.

def frame_sky_band(d):
    """Sky band: the segmented celestial band that tops stelae, lintels and
    the Dresden codex, with k'in, ak'bal, Venus and crossed-band signs."""
    band = 18
    o = 2
    def segments(y0, y1):
        d.rectangle((o, y0, WIDTH - 1 - o, y1), outline=INK, width=2)
        n = 5
        sw = (WIDTH - 2 * o) / n
        for i in range(n):
            x0 = o + i * sw
            if i:
                d.line((x0, y0, x0, y1), fill=INK, width=2)
            cx, cy = x0 + sw / 2, (y0 + y1) / 2
            kind = (i + (y0 > HEIGHT / 2)) % 4
            if kind == 0:                                   # k'in
                kin_flower(d, cx, cy, 6)
            elif kind == 1:                                 # ak'bal (night)
                d.arc((cx - 7, cy - 6, cx + 7, cy + 8), 180, 360, fill=INK, width=2)
                d.pieslice((cx - 3, cy - 1, cx + 3, cy + 5), 0, 180, fill=INK)
            elif kind == 2:                                 # Venus / lamat
                d.line((cx - 6, cy - 5, cx + 6, cy + 5), fill=INK, width=2)
                d.line((cx - 6, cy + 5, cx + 6, cy - 5), fill=INK, width=2)
                for (sx, sy) in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    dot(d, cx + sx * 5, cy + sy * 4, 1.2)
            else:                                           # crossed bands
                d.line((cx - 7, y0 + 3, cx + 7, y1 - 3), fill=INK, width=2)
                d.line((cx - 7, y1 - 3, cx + 7, y0 + 3), fill=INK, width=2)
    segments(o, o + band)
    segments(HEIGHT - 1 - o - band, HEIGHT - 1 - o)
    d.line((o, o + band, o, HEIGHT - 1 - o - band), fill=INK, width=2)
    d.line((WIDTH - 1 - o, o + band, WIDTH - 1 - o, HEIGHT - 1 - o - band), fill=INK, width=2)
    return (8, o + band + 4, WIDTH - 8, HEIGHT - o - band - 4)

def frame_mat(d):
    """Pop: the woven mat border, emblem of the ruler's seat."""
    o, band = 2, 11
    d.rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), outline=INK, width=2)
    i2 = o + band
    d.rectangle((i2, i2, WIDTH - 1 - i2, HEIGHT - 1 - i2), outline=INK, width=2)
    step = 7
    def weave(x0, y0, x1, y1):
        # diagonal strips both ways, clipped to the band by drawing
        # on a temp image and pasting
        tile = Image.new("1", (int(x1 - x0) + 1, int(y1 - y0) + 1), 255)
        td = ImageDraw.Draw(tile)
        L = max(tile.size) * 2
        for k in range(-L, L, step):
            td.line((k, 0, k + tile.size[1], tile.size[1]), fill=0, width=2)
        for k in range(-L, L, step * 2):
            td.line((k + tile.size[1], 0, k, tile.size[1]), fill=0, width=2)
            td.line((k + tile.size[1] + step, 0, k + step, tile.size[1]), fill=255, width=1)
        d._image.paste(0, (int(x0), int(y0)), tile.point(lambda p: 255 if p == 0 else 0))
    weave(o + 2, o + 2, WIDTH - 1 - o - 2, i2 - 2)
    weave(o + 2, HEIGHT - 1 - i2 + 2, WIDTH - 1 - o - 2, HEIGHT - 1 - o - 2)
    weave(o + 2, i2 + 2, i2 - 2, HEIGHT - 1 - i2 - 2)
    weave(WIDTH - 1 - i2 + 2, i2 + 2, WIDTH - 1 - o - 2, HEIGHT - 1 - i2 - 2)
    return (i2 + 3, i2 + 4, WIDTH - i2 - 3, HEIGHT - i2 - 4)

def frame_step_fret(d):
    """Puuc step-fret (as on the Nunnery Quadrangle at Uxmal):
    a stepped band ending in a hook, repeated along top and bottom."""
    o, band = 2, 16
    def fret_row(y0, flip):
        unit = WIDTH / round(WIDTH / 24)
        n = round(WIDTH / unit)
        for i in range(n):
            x0 = i * unit
            def p(u, v):
                return (x0 + u * unit, y0 + (band - v * band) if flip else y0 + v * band)
            pts = [p(0, 1), p(0, .75), p(.25, .75), p(.25, .5), p(.5, .5),
                   p(.5, .25), p(.75, .25), p(.75, 0)]
            hook = [p(.75, 0), p(1, 0), p(1, .5), p(.75, .5), p(.75, .35)]
            d.line(pts + hook[1:], fill=INK, width=2)
        d.line((0, y0 + (0 if flip else band), WIDTH, y0 + (0 if flip else band)), fill=INK, width=2)
    fret_row(o, False)
    fret_row(HEIGHT - 1 - o - band, True)
    d.line((o, o + band, o, HEIGHT - o - band), fill=INK, width=2)
    d.line((WIDTH - 1 - o, o + band, WIDTH - 1 - o, HEIGHT - o - band), fill=INK, width=2)
    return (8, o + band + 4, WIDTH - 8, HEIGHT - o - band - 4)

def frame_codex(d):
    """Codex page: thin red border and red register lines, like the pages
    of the Dresden Codex. The register lines are added by the layout."""
    o = 4
    d.rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), outline=INK, width=2)
    return (o + 4, o + 6, WIDTH - o - 4, HEIGHT - o - 6)

def frame_stela(d):
    """Carved stela edge: a raised rounded border with an inner groove."""
    o = 3
    d.rounded_rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), radius=14, outline=INK, width=4)
    d.rounded_rectangle((o + 7, o + 7, WIDTH - 1 - o - 7, HEIGHT - 1 - o - 7), radius=9,
                        outline=INK, width=1)
    return (o + 10, o + 12, WIDTH - o - 10, HEIGHT - o - 12)

FRAMES = [frame_sky_band, frame_mat, frame_step_fret, frame_codex, frame_stela]

# =====================================================================
#  LAYOUT
# =====================================================================
def weather(img, amount):
    d = ImageDraw.Draw(img)
    for _ in range(amount):
        img.putpixel((random.randrange(WIDTH), random.randrange(HEIGHT)), PAPER)
    for _ in range(random.randint(2, 5)):
        x, y = random.randrange(WIDTH), random.randrange(HEIGHT)
        r = random.randint(1, 3)
        d.ellipse((x - r, y - r, x + r, y + r), fill=PAPER)

def render_inscription(epd):
    black = Image.new("1", (WIDTH, HEIGHT), PAPER)
    red = Image.new("1", (WIDTH, HEIGHT), PAPER)
    db = ImageDraw.Draw(black)
    dr = ImageDraw.Draw(red)

    frame = random.choice(FRAMES)
    ix0, iy0, ix1, iy1 = frame(dr)

    lc = random_long_count()
    days, tz_num, tz_day, h_day, h_month, g = calendar_round(lc)

    footer = 11 if SHOW_READING else 0
    rows = 4
    isig_h = 42
    avail = (iy1 - iy0) - isig_h - footer
    row_h = min(44, avail // rows)
    top = iy0 + max(0, (avail - rows * row_h) // 2)

    col_w = (ix1 - ix0 - 6) // 2
    colx = [ix0, ix0 + col_w + 6]
    num_w = 19

    # A1-B2: Introductory Glyph across both columns
    glyph_isig(db, h_month, ix0 + 8, top, ix1 - ix0 - 16, isig_h - 4)
    y = top + isig_h

    # A3..B6: the glyph blocks, in reading order
    blocks = [
        ("num", lc[0], "baktun"), ("num", lc[1], "katun"),
        ("num", lc[2], "tun"),    ("num", lc[3], "winal"),
        ("num", lc[4], "kin"),    ("day", tz_num, tz_day),
        ("g", None, g),           ("month", h_day, h_month),
    ]
    for i, (kind, n, what) in enumerate(blocks):
        col, row = i % 2, i // 2
        bx = colx[col]
        by = y + row * row_h
        sx, sy, sw, sh = bx + num_w + 2, by + 2, col_w - num_w - 2, row_h - 5
        if kind == "num":
            glyph_period(db, what, sx, sy, sw, sh)
            numeral(dr, n, bx, by + 4, num_w, row_h - 9, period=True)
        elif kind == "day":
            glyph_day(db, what, sx, sy, sw, sh)
            numeral(dr, n, bx, by + 4, num_w, row_h - 9)
        elif kind == "month":
            glyph_month(db, what, sx, sy, sw, sh)
            if n == 0:
                seating(dr, bx, by + 4, num_w, row_h - 9)
            else:
                numeral(dr, n, bx, by + 4, num_w, row_h - 9)
        else:
            glyph_g(db, what, bx + 4, sy, col_w - 8, sh)

    if frame is frame_codex:      # red register lines between the rows
        for r in range(rows + 1):
            yy = y + r * row_h - 2
            dr.line((ix0 - 2, yy, ix1 + 2, yy), fill=INK, width=1)
        dr.line((ix0 - 2, top - 2, ix1 + 2, top - 2), fill=INK, width=1)

    if SHOW_READING:
        year = julian_year(days)
        era = f"AD {year}" if year > 0 else f"{1 - year} BC"
        text = (f"{'.'.join(map(str, lc))}  {tz_num} {DAY_NAMES[tz_day]} "
                f"{h_day if h_day else 'Seating of'} {MONTH_NAMES[h_month]} · {era}")
        font = _small_font(len(text))
        tw = db.textlength(text, font=font)
        db.text(((WIDTH - tw) / 2, iy1 - footer + 1), text, font=font, fill=INK)

    weather(black, 250)
    weather(red, 150)

    timestamp = int(time.time())
    save_preview_png(black, red, f"maya_{timestamp}.png")
    epd.display(epd.getbuffer(black), epd.getbuffer(red))

def _small_font(n_chars):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(path):
            size = 8 if n_chars < 42 else 7
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# --- PNG export ---
def save_preview_png(black, red, filename):
    preview = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    preview.paste((0, 0, 0), mask=black.point(lambda p: 255 - p))
    preview.paste((200, 0, 0), mask=red.point(lambda p: 255 - p))
    preview.save(filename)

# --- Main loop ---
def main():
    epd = epd2in7b.EPD()
    epd.init()
    try:
        while True:
            render_inscription(epd)
            time.sleep(15)
    except KeyboardInterrupt:
        print("Exiting cleanly...")
        epd.init()
        epd.Clear()
        epd.sleep()
    finally:
        epd2in7b.epdconfig.module_exit()

if __name__ == "__main__":
    main()
