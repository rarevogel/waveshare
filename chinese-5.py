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

# Texts for the red seals. Real seals carry short auspicious phrases
# (閒章, "leisure seals") or a name; 2 or 4 characters is the classic size.
SEAL_TEXTS_4 = ["長樂未央", "吉祥如意", "福壽安康", "山高水長", "寧靜致遠",
                "心平氣和", "天長地久", "和氣致祥"]
SEAL_TEXTS_2 = ["吉祥", "長樂", "安康", "福壽", "如意", "平安", "清心", "寧靜",
                "守拙", "知足", "隨緣", "自在"]

# CJK fonts: the first one that exists wins. A bold face cuts the cleanest seal.
CJK_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
CJK_TEXT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

_font_cache = {}
def cjk_font(size, candidates):
    import os
    key = (size, tuple(candidates))
    if key not in _font_cache:
        for path in candidates:
            if os.path.exists(path):
                # index 2 in the Noto CJK .ttc files is the Traditional Chinese face
                try:
                    _font_cache[key] = ImageFont.truetype(path, size, index=2)
                except Exception:
                    _font_cache[key] = ImageFont.truetype(path, size)
                break
        else:
            raise FileNotFoundError("No CJK font found; install fonts-noto-cjk")
    return _font_cache[key]

CHENGYU = [
    "風林火山", "塞翁失馬", "畫龍點睛", "百折不撓", "自強不息",
    "臥虎藏龍", "龍飛鳳舞", "心想事成", "水落石出", "一帆風順",
    "四海一家", "金玉滿堂", "花開富貴", "歲歲平安", "龍馬精神",
    "厚德載物", "海納百川", "天長地久", "吉祥如意", "福壽安康",
    "春暖花開", "萬事如意", "長樂未央", "松柏長青", "鶴壽延年",
    "琴瑟和鳴", "和氣致祥", "福星高照", "蒸蒸日上", "步步高升",
    "龍鳳呈祥", "國泰民安", "花好月圓", "歲月靜好", "山高水長",
    "雲淡風輕", "寧靜致遠", "以和為貴", "天道酬勤", "厚積薄發",
    "精益求精", "開門見山", "一見如故", "相得益彰", "妙筆生花",
    "一心一意", "心平氣和", "大吉大利", "吉慶有餘", "福祿壽喜"]

# Fonts
FONT_RUNES = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoSansRunic-Regular.ttf", 26
)
FONT_BINDRUNES = ImageFont.truetype(
    "/usr/share/fonts/truetype/noto/NotoSansRunic-Regular.ttf", 44
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

def draw_vertical_chinese(draw, text, start_y):
    """Stack the characters top to bottom; returns the y below the last one."""
    font = cjk_font(32, CJK_TEXT_CANDIDATES)
    step = 34
    x = WIDTH // 2
    for i, ch in enumerate(text):
        draw.text((x, start_y + i * step + step // 2), ch, font=font, fill=0, anchor="mm")
    return start_y + len(text) * step


# =====================================================================
#  RED FRAMES — after real Chinese borders
# =====================================================================
#  All frames draw on the red layer (0 = red). Each one is a function
#  taking the ImageDraw; one is picked at random per frame.

import math

def _corner(pts, corner):
    """Mirror points drawn for the top-left corner into any corner."""
    out = []
    for (x, y) in pts:
        if corner in ("tr", "br"):
            x = WIDTH - 1 - x
        if corner in ("bl", "br"):
            y = HEIGHT - 1 - y
        out.append((x, y))
    return out

CORNERS = ("tl", "tr", "bl", "br")


# 1. 回紋 Huiwen — the "回" key-fret band of bronzes, porcelain and
#    lattice work, running all the way round.
def frame_huiwen(d):
    inset, band = 3, 14
    # outer and inner lines of the band
    d.rectangle((inset, inset, WIDTH - 1 - inset, HEIGHT - 1 - inset), outline=0, width=2)
    i2 = inset + band
    d.rectangle((i2, i2, WIDTH - 1 - i2, HEIGHT - 1 - i2), outline=0, width=1)

    # one 回 spiral in a unit square; rotated per side so it always turns inward
    spiral = [(0.12, 0.88), (0.12, 0.12), (0.88, 0.12), (0.88, 0.88),
              (0.38, 0.88), (0.38, 0.38), (0.64, 0.38), (0.64, 0.64)]

    def unit(x0, y0, sx, sy, rot):
        pts = []
        for (u, v) in spiral:
            for _ in range(rot):
                u, v = 1 - v, u
            pts.append((x0 + u * sx, y0 + v * sy))
        d.line(pts, fill=0, width=2)

    pad = inset + 2
    inner = band - 4
    # horizontal sides
    span = WIDTH - 2 * pad
    n = max(1, round(span / inner))
    sx = span / n
    for i in range(n):
        unit(pad + i * sx, pad, sx, inner, 0)
        unit(pad + i * sx, HEIGHT - pad - inner, sx, inner, 2)
    # vertical sides (between the corner units)
    span = HEIGHT - 2 * pad - 2 * inner
    n = max(1, round(span / inner))
    sy = span / n
    for i in range(n):
        unit(pad, pad + inner + i * sy, inner, sy, 3)
        unit(WIDTH - pad - inner, pad + inner + i * sy, inner, sy, 1)


# 2. 文武線 "civil-and-military lines" — a thick outer rule with a thin
#    inner rule, the standard frame of woodblock-printed books, with the
#    inner corners stepped in.
def frame_wenwu(d):
    o = 4
    d.rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), outline=0, width=4)
    i = 11
    c = 7   # size of the stepped corner
    pts = [(i + c, i), (WIDTH - 1 - i - c, i), (WIDTH - 1 - i - c, i + c),
           (WIDTH - 1 - i, i + c), (WIDTH - 1 - i, HEIGHT - 1 - i - c),
           (WIDTH - 1 - i - c, HEIGHT - 1 - i - c), (WIDTH - 1 - i - c, HEIGHT - 1 - i),
           (i + c, HEIGHT - 1 - i), (i + c, HEIGHT - 1 - i - c), (i, HEIGHT - 1 - i - c),
           (i, i + c), (i + c, i + c), (i + c, i)]
    d.line(pts, fill=0, width=1)


# 3. 朱絲欄 "vermilion silk ruling" — red-ruled paper used for fine
#    calligraphy: a frame divided into vertical columns.
def frame_zhusilan(d):
    o = 6
    d.rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), outline=0, width=3)
    d.rectangle((o + 4, o + 4, WIDTH - 1 - o - 4, HEIGHT - 1 - o - 4), outline=0, width=1)
    col = 38                           # column width, text column centred
    x = WIDTH // 2 - col // 2
    while x - col > o + 4:
        x -= col
    while x < WIDTH - o - 4:
        if x > o + 6:
            d.line((x, o + 4, x, HEIGHT - 1 - o - 4), fill=0, width=1)
        x += col


# 4. 如意雲紋 Ruyi cloud-head corners joined by a double line.
def _ruyi(d, corner):
    cx, cy = 17, 17
    # three-lobed cloud head: a big lobe pointing into the corner, two side lobes
    lobes = [(cx - 4, cy - 4, 7), (cx + 6, cy - 7, 5), (cx - 7, cy + 6, 5)]
    for (x, y, r) in lobes:
        (x0, y0), (x1, y1) = _corner([(x - r, y - r), (x + r, y + r)], corner)
        d.ellipse((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), fill=0)
    # cut a curl into the main lobe, as on carved ruyi
    for (x, y, r) in [(cx - 4, cy - 4, 4)]:
        (x0, y0), (x1, y1) = _corner([(x - r, y - r), (x + r, y + r)], corner)
        d.ellipse((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), fill=255)
    (x0, y0), (x1, y1) = _corner([(cx - 5, cy - 5), (cx - 3, cy - 3)], corner)
    d.ellipse((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), fill=0)
    # tail of the cloud trailing back into the frame lines
    d.line(_corner([(cx + 3, cy + 3), (cx + 9, cy + 5), (cx + 12, cy + 12)], corner),
           fill=0, width=2)

def frame_ruyi(d):
    a, b = 8, 12
    for off, w in ((a, 2), (b, 1)):
        d.line((26, off, WIDTH - 27, off), fill=0, width=w)
        d.line((26, HEIGHT - 1 - off, WIDTH - 27, HEIGHT - 1 - off), fill=0, width=w)
        d.line((off, 26, off, HEIGHT - 27), fill=0, width=w)
        d.line((WIDTH - 1 - off, 26, WIDTH - 1 - off, HEIGHT - 27), fill=0, width=w)
    for c in CORNERS:
        _ruyi(d, c)


# 5. 拐子紋 Guaizi "walking-stick" fret — the squared hook corners of
#    Ming and Qing furniture and window lattices.
def frame_guaizi(d):
    o = 5
    pts = [  # outer line, stepping into a hook at the corner
        (40, o), (o, o), (o, 40)]
    hook = [(o + 6, 40), (o + 6, o + 6), (40, o + 6), (40, o + 14),
            (o + 14, o + 14), (o + 14, o + 24), (o + 22, o + 24), (o + 22, o + 20)]
    for c in CORNERS:
        d.line(_corner(pts, c), fill=0, width=2)
        d.line(_corner(hook, c), fill=0, width=2)
    # straight runs between the corner hooks
    d.line((40, o, WIDTH - 41, o), fill=0, width=2)
    d.line((40, HEIGHT - 1 - o, WIDTH - 41, HEIGHT - 1 - o), fill=0, width=2)
    d.line((o, 40, o, HEIGHT - 41), fill=0, width=2)
    d.line((WIDTH - 1 - o, 40, WIDTH - 1 - o, HEIGHT - 41), fill=0, width=2)
    d.line((40, o + 6, WIDTH - 41, o + 6), fill=0, width=1)
    d.line((40, HEIGHT - 1 - o - 6, WIDTH - 41, HEIGHT - 1 - o - 6), fill=0, width=1)
    d.line((o + 6, 40, o + 6, HEIGHT - 41), fill=0, width=1)
    d.line((WIDTH - 1 - o - 6, 40, WIDTH - 1 - o - 6, HEIGHT - 41), fill=0, width=1)


# 6. 冰裂紋 Cracked-ice lattice — the irregular window-lattice pattern,
#    filling the corners of a plain frame.
def _split_convex(poly):
    """Cut a convex polygon in two along a random line between two edges."""
    n = len(poly)
    i, j = sorted(random.sample(range(n), 2))
    def on_edge(k):
        (x0, y0), (x1, y1) = poly[k], poly[(k + 1) % n]
        t = random.uniform(0.3, 0.7)
        return (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
    p, q = on_edge(i), on_edge(j)
    a = [p] + poly[i + 1:j + 1] + [q]
    b = [q] + poly[j + 1:] + poly[:i + 1] + [p]
    return a, b

def _area(poly):
    return abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1]
                   - poly[(k + 1) % len(poly)][0] * poly[k][1]
                   for k in range(len(poly)))) / 2

def frame_ice(d):
    o = 5
    d.rectangle((o, o, WIDTH - 1 - o, HEIGHT - 1 - o), outline=0, width=3)
    leg = 46
    for c in CORNERS:
        pieces = [[(o, o), (o + leg, o), (o, o + leg)]]
        for _ in range(6):
            pieces.sort(key=_area)
            pieces += _split_convex(pieces.pop())
        for poly in pieces:
            d.line(_corner(poly + [poly[0]], c), fill=0, width=2)


FRAMES = [frame_huiwen, frame_wenwu, frame_zhusilan,
          frame_ruyi, frame_guaizi, frame_ice]

def weather_frame(img):
    """Woodblock/ink look: a few lost pixels and small breaks in the lines."""
    d = ImageDraw.Draw(img)
    for _ in range(400):
        img.putpixel((random.randrange(WIDTH), random.randrange(HEIGHT)), 255)
    for _ in range(random.randint(2, 5)):
        x, y = random.randrange(WIDTH), random.randrange(HEIGHT)
        d.rectangle((x, y, x + random.randint(1, 3), y + random.randint(1, 3)), fill=255)


# =====================================================================
#  THE SEAL (印章)
# =====================================================================
#  Two classic kinds, picked at random:
#    白文 baiwen — solid red block, characters cut out in white
#    朱文 zhuwen — red border, characters in red on white
#  Four characters sit in a 2x2 grid read right column first, top to
#  bottom, as on real seals; two characters stack vertically. The seal
#  is pressed slightly crooked and with uneven ink.

def stamp_seal(red_img, text, x0, y0, size, tall=False):
    w = size
    h = size * 2 if tall else size
    pad = 8                                       # room for rotation
    tile = Image.new("1", (w + 2 * pad, h + 2 * pad), 1)
    d = ImageDraw.Draw(tile)
    box = (pad, pad, pad + w - 1, pad + h - 1)
    baiwen = random.random() < 0.6

    if baiwen:
        d.rectangle(box, fill=0)
        ink, bg = 1, 0
    else:
        d.rectangle(box, outline=0, width=max(2, size // 12))
        ink, bg = 0, 1

    # character cells
    n = len(text)
    if n == 4:
        cells = [(1, 0), (1, 1), (0, 0), (0, 1)]  # right column first
        cols, rows = 2, 2
    else:
        cells = [(0, i) for i in range(n)]
        cols, rows = 1, n
    margin = max(2, size // 12)
    cw = (w - 2 * margin) / cols
    ch = (h - 2 * margin) / rows
    font = cjk_font(int(min(cw, ch) * 1.0), CJK_FONT_CANDIDATES)
    stroke = 0
    for char, (cx, cy) in zip(text, cells):
        px = pad + margin + (cx + 0.5) * cw
        py = pad + margin + (cy + 0.5) * ch
        d.text((px, py), char, font=font, fill=ink, anchor="mm",
               stroke_width=stroke, stroke_fill=ink)

    # uneven ink: nibble the edges and leave a few pale specks
    for _ in range(w * h // 10):
        x = random.randrange(pad, pad + w)
        y = random.randrange(pad, pad + h)
        edge = min(x - pad, pad + w - 1 - x, y - pad, pad + h - 1 - y)
        if edge < 1 or (edge < 2 and random.random() < 0.4) or random.random() < 0.02:
            tile.putpixel((x, y), 1)

    angle = random.uniform(-3, 3)
    tile = tile.rotate(angle, resample=Image.NEAREST, fillcolor=1)
    # clear the seal's footprint first so frame lines never show through it
    footprint = Image.new("1", tile.size, 1)
    ImageDraw.Draw(footprint).rectangle(box, fill=0)
    footprint = footprint.rotate(angle, resample=Image.NEAREST, fillcolor=1)
    pos = (x0 - pad, y0 - pad)
    red_img.paste(255, pos, footprint.point(lambda p: 255 if p == 0 else 0))
    red_img.paste(0, pos, tile.point(lambda p: 255 if p == 0 else 0))

# --- 5 Border Styles (all edge-hugging) ---
def draw_knotwork_border(draw):
    style = random.choice(["tight", "loose", "angular", "serpentine", "dots"])
    step = 12

    # --- 1. Tight diagonal knotwork ---
    if style == "tight":
        for x in range(0, WIDTH, step):
            draw.line((x, 0, x + 8, 8), fill=0, width=3)
            draw.line((x, HEIGHT - 1, x + 8, HEIGHT - 9), fill=0, width=3)

    # --- 2. Loose arc border (perfect half-circles) ---
    elif style == "loose":
        radius = 12
        for x in range(0, WIDTH, radius * 2):
            draw.arc((x, 0, x + radius * 2, radius * 2), 180, 360, fill=0, width=3)
            draw.arc((x, HEIGHT - radius * 2, x + radius * 2, HEIGHT), 0, 180, fill=0, width=3)

    # --- 3. Angular zig-zag (fixed left-side gap) ---
    elif style == "angular":
        start = -(step * 2)
        for x in range(start, WIDTH, step):
            draw.line((x, 0, x + 12, 12), fill=0, width=4)
            draw.line((x + 12, 12, x + 24, 0), fill=0, width=4)
            draw.line((x, HEIGHT - 1, x + 12, HEIGHT - 13), fill=0, width=4)
            draw.line((x + 12, HEIGHT - 13, x + 24, HEIGHT - 1), fill=0, width=4)

    # --- 4. Serpentine wave border ---
    elif style == "serpentine":
        for x in range(0, WIDTH, 8):
            y = random.choice([6, 10])
            draw.line((x, 0, x + 8, y), fill=0, width=3)
            draw.line((x, HEIGHT - 1, x + 8, HEIGHT - 1 - y), fill=0, width=3)

    # --- 5. Dot-chain / crosses border (fixed tiling) ---
    elif style == "dots":
        for x in range(0, WIDTH, 10):
            draw.line((x, 0, x + 6, 6), fill=0, width=3)
            draw.line((x + 6, 0, x, 6), fill=0, width=3)
            draw.line((x, HEIGHT - 1, x + 6, HEIGHT - 7), fill=0, width=3)
            draw.line((x + 6, HEIGHT - 7, x, HEIGHT - 1), fill=0, width=3)

# --- Procedural bind-rune (full size, font 44) ---
def draw_bindrune(draw_red, cx, cy, r, rune_set):
    # Pick exactly 2 runes
    base = random.choice(rune_set)
    branch = random.choice(rune_set)

    # Temporary canvas
    temp = Image.new("1", (SYMBOL_SIZE, SYMBOL_SIZE), 1)
    d = ImageDraw.Draw(temp)

    # Fonts: base rune large, branch slightly smaller
    base_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoSansRunic-Regular.ttf", 44
    )
    branch_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoSansRunic-Regular.ttf", 36
    )

    # --- Draw base rune (centered) ---
    bw, bh = d.textbbox((0, 0), base, font=base_font)[2:]
    bx = (SYMBOL_SIZE - bw) // 2
    by = (SYMBOL_SIZE - bh) // 2
    d.text((bx, by), base, font=base_font, fill=0)

    # --- Draw branch rune (historical placement) ---
    # 50% kans links, 50% kans rechts
    side = random.choice(["left", "right"])
    offset_x = -12 if side == "left" else 12

    bw2, bh2 = d.textbbox((0, 0), branch, font=branch_font)[2:]
    bx2 = (SYMBOL_SIZE - bw2) // 2 + offset_x
    by2 = (SYMBOL_SIZE - bh2) // 2

    d.text((bx2, by2), branch, font=branch_font, fill=0)

    # --- Copy to red layer ---
    x0 = cx - SYMBOL_SIZE // 2
    y0 = cy - SYMBOL_SIZE // 2

    for y in range(SYMBOL_SIZE):
        for x in range(SYMBOL_SIZE):
            if temp.getpixel((x, y)) == 0:
                draw_red.point((x0 + x, y0 + y), fill=0)

# --- Red symbol ---
def draw_red_symbol(draw_red, corner, rune_bboxes, rune_set):
    pad = 12

    if corner == "tl":
        x0 = pad
        y0 = pad
    elif corner == "tr":
        x0 = WIDTH - SYMBOL_SIZE - pad
        y0 = pad
    elif corner == "bl":
        x0 = pad
        y0 = HEIGHT - SYMBOL_SIZE - pad
    else:
        x0 = WIDTH - SYMBOL_SIZE - pad
        y0 = HEIGHT - SYMBOL_SIZE - pad

    x1 = x0 + SYMBOL_SIZE
    y1 = y0 + SYMBOL_SIZE

    for (rx0, ry0, rx1, ry1) in rune_bboxes:
        if not (x1 < rx0 or x0 > rx1 or y1 < ry0 or y0 > ry1):
            return False

    # Weighted symbol selection (bindrune appears more often)
    styles = [
        "bindrune", "bindrune", "bindrune", "bindrune",
        "valknut", "sunwheel", "hammer", "serpent", "suncross",
        "shield", "axe", "helm", "diamond", "triangles"
    ]

    style = random.choice(styles)

    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    r = SYMBOL_SIZE // 3

    if style == "hammer":
        draw_red.rectangle((cx - r, cy - r, cx + r, cy), outline=0, width=SYMBOL_THICKNESS)
        draw_red.rectangle((cx - r//2, cy, cx + r//2, cy + r), outline=0, width=SYMBOL_THICKNESS)

    elif style == "serpent":
        draw_red.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=SYMBOL_THICKNESS)
        draw_red.arc((cx - r, cy - r, cx + r, cy + r), 40, 320, fill=0, width=SYMBOL_THICKNESS)

    elif style == "suncross":
        draw_red.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=SYMBOL_THICKNESS)
        draw_red.line((cx - r, cy, cx + r, cy), fill=0, width=SYMBOL_THICKNESS)
        draw_red.line((cx, cy - r, cx, cy + r), fill=0, width=SYMBOL_THICKNESS)

    elif style == "valknut":
        pts1 = [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)]
        pts2 = [(cx, cy + r), (cx - r, cy - r), (cx + r, cy - r)]
        draw_red.polygon(pts1, outline=0, width=SYMBOL_THICKNESS)
        draw_red.polygon(pts2, outline=0, width=SYMBOL_THICKNESS)

    elif style == "shield":
        draw_red.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=SYMBOL_THICKNESS)
        draw_red.line((cx - r, cy, cx + r, cy), fill=0, width=SYMBOL_THICKNESS)
        draw_red.line((cx, cy - r, cx, cy + r), fill=0, width=SYMBOL_THICKNESS)

    elif style == "axe":
        draw_red.line((cx - r, cy + r, cx + r, cy - r), fill=0, width=SYMBOL_THICKNESS)
        draw_red.rectangle((cx + r//2, cy - r, cx + r, cy - r//2),
                           outline=0, width=SYMBOL_THICKNESS)

    elif style == "helm":
        for angle in range(0, 360, 45):
            x2 = cx + int(r * 0.9 * (1 if angle in [0, 45, 315] else -1 if angle in [135, 180, 225] else 0))
            y2 = cy + int(r * 0.9 * (1 if angle in [90, 135, 180] else -1 if angle in [0, 315, 270] else 0))
            draw_red.line((cx, cy, x2, y2), fill=0, width=SYMBOL_THICKNESS)

    elif style == "diamond":
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        draw_red.polygon(pts, outline=0, width=SYMBOL_THICKNESS)

    elif style == "triangles":
        pts1 = [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)]
        pts2 = [(cx, cy - r//2), (cx - r//2, cy + r//2), (cx + r//2, cy + r//2)]
        draw_red.polygon(pts1, outline=0, width=SYMBOL_THICKNESS)
        draw_red.polygon(pts2, outline=0, width=SYMBOL_THICKNESS)

    elif style == "bindrune":
        draw_bindrune(draw_red, cx, cy, r, rune_set)

    return True

# --- PNG export ---
def save_preview_png(black, red, filename):
    preview = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    black_mask = black.point(lambda p: 255 - p)
    red_mask = red.point(lambda p: 255 - p)
    preview.paste((0, 0, 0), mask=black_mask)
    preview.paste((255, 0, 0), mask=red_mask)
    preview.save(filename)

def render_chinese_poem(epd, poem_text):
    black = Image.new("1", (WIDTH, HEIGHT), 255)
    red = Image.new("1", (WIDTH, HEIGHT), 255)
    draw_black = ImageDraw.Draw(black)
    draw_red = ImageDraw.Draw(red)

    random.choice(FRAMES)(draw_red)
    weather_frame(red)

    # Text column starts a little high so the seal fits under it
    start_y = 34
    bottom = draw_vertical_chinese(draw_black, poem_text, start_y)

    # Main seal under the last character, slightly off-centre
    seal_text = random.choice(SEAL_TEXTS_4 if random.random() < 0.6 else SEAL_TEXTS_2)
    size = 40
    sx = WIDTH // 2 - size // 2 + random.choice([-5, -2, 0, 3])
    stamp_seal(red, seal_text, sx, bottom + 12, size)

    # Small leisure seal (引首章) beside the first character, half the time
    if random.random() < 0.5:
        stamp_seal(red, random.choice(SEAL_TEXTS_2), WIDTH // 2 + 24, start_y + 4,
                   17, tall=True)

    timestamp = int(time.time())
    save_preview_png(black, red, f"chinese_{timestamp}.png")

    epd.display(epd.getbuffer(black), epd.getbuffer(red))

# --- Render one frame ---
def render_frame(epd):
    black = Image.new("1", (WIDTH, HEIGHT), 255)
    red = Image.new("1", (WIDTH, HEIGHT), 255)
    draw_black = ImageDraw.Draw(black)
    draw_red = ImageDraw.Draw(red)

    draw_stone_texture(draw_black)
    draw_knotwork_border(draw_black)

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
        if draw_red_symbol(draw_red, c, rune_bboxes, rune_set):
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
            poem_text = random.choice(CHENGYU)
            render_chinese_poem(epd, poem_text)
            #render_frame(epd)
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

