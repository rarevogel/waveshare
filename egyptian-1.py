#!/usr/bin/env python3
"""
Egyptian hieroglyphic texts on a 2.7" e-Paper HAT (B), set in
Noto Sans Egyptian Hieroglyphs.

Three kinds of text, each on the object it belongs to:

  * Book of the Dead papyrus — ruled columns, red rubric for the spell
    title (the origin of the word "rubric"), striped borders, a ragged
    papyrus edge and the odd lacuna.
  * Offering stela — round-topped, winged sun disk in the lunette, the
    offering formula (hetep-di-nesu) in horizontal lines, and the owner
    seated before an offering table.
  * Royal titulary — a temple door-jamb under the sky sign between two
    was-sceptres: King of Upper and Lower Egypt [cartouche], Son of Ra
    [cartouche], given life forever.

The texts are real formulas spelled with the correct Gardiner signs;
names of gods in royal names stand first (honorific transposition), as
on the monuments. Signs are grouped into square blocks (quadrats) the way
scribes arranged them: flat signs stacked, narrow tall signs paired.
"""
import os
import random
import time
import unicodedata
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in7b   # 2.7" e-Paper HAT (B)

WIDTH = 176
HEIGHT = 264
INK = 0
PAPER = 255
SHOW_READING = True     # small English translation at the bottom

HERE = os.path.dirname(os.path.abspath(__file__))
HIERO_FONTS = [
    "/usr/share/fonts/truetype/noto/NotoSansEgyptianHieroglyphs-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansEgyptianHieroglyphs-Regular.ttf",
    os.path.join(HERE, "NotoSansEgyptianHieroglyphs-Regular.ttf"),
]
SMALL_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]

def _first(paths):
    return next((p for p in paths if os.path.exists(p)), None)

HIERO_PATH = _first(HIERO_FONTS)
if not HIERO_PATH:
    raise SystemExit("Noto Sans Egyptian Hieroglyphs not found: sudo apt install fonts-noto-core")
SMALL_PATH = _first(SMALL_FONTS)
_fonts = {}
def hfont(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(HIERO_PATH, size)
    return _fonts[size]

def small(size=7):
    return ImageFont.truetype(SMALL_PATH, size) if SMALL_PATH else ImageFont.load_default()

def G(*codes):
    """Gardiner codes -> hieroglyph characters, e.g. G('R4', 'X8')."""
    out = []
    for c in codes:
        letters = c.rstrip("0123456789")
        num = c[len(letters):]
        out.append(unicodedata.lookup(f"EGYPTIAN HIEROGLYPH {letters.upper()}{int(num):03d}"))
    return out

# =====================================================================
#  VOCABULARY — (signs, English)
# =====================================================================
HTP_DI_NSW = (G("R4", "X8", "M23", "X1", "N35"), "An offering which the king gives")
GODS = [
    (G("Q1", "D4", "A40") + G("V30", "R11", "R11", "O49") + G("R8", "O29"),
     "Osiris, lord of Busiris, the great god"),
    (G("M17", "N35", "Q3", "G43", "E15") + G("D1", "N26", "I9"),
     "Anubis who is upon his mountain"),
]
DI_F = (G("X8", "I9"), "that he may give")
PRT_KHRW = (G("O3"), "an invocation offering of")
OFFERINGS = [
    (G("X2", "W22"), "bread and beer"),
    (G("F1", "H1"), "oxen and fowl"),
    (G("V6", "S28"), "alabaster and linen"),
    (G("M3", "X1", "Z2", "V30", "X1", "F35", "X1", "D60", "X1"),
     "every good and pure thing"),
]
N_KA_N = (G("N35", "D28", "N35"), "for the ka of")
IMAKHU = (G("M17", "F39", "Aa1"), "the revered one")
MAA_KHRW = (G("Aa11", "P8"), "true of voice")

MEN = [(G("M17", "Y5", "N35", "G17", "F4", "X1", "A1"), "Amenemhat"),
       (G("I4", "R4", "X1", "Q3", "A1"), "Sobekhotep"),
       (G("N35", "Aa1", "X1", "D40", "A1"), "Nakht"),
       (G("Q3", "X1", "V28", "R4", "X1", "Q3", "A1"), "Ptahhotep"),
       (G("M17", "N35", "X1", "I9", "A1"), "Intef")]
WOMEN = [(G("F35", "X1", "B1"), "Nefret"),
         (G("U7", "D21", "X1", "B1"), "Meryt"),
         (G("Q1", "X1", "B1"), "Iset")]

RUBRIC = (G("D21", "Z1", "N35", "O1", "D21", "X1", "D54", "G17", "O4", "D21", "G43", "N5"),
          "Spell for going forth by day")
DD_MDW_IN = (G("R11", "D46", "S43", "M17", "N35"), "Words spoken by")
WSIR = (G("Q1", "D4", "A40"), "the Osiris")
HAIL = (G("M17", "N35", "D46", "D2", "V31") + G("Q1", "D4", "A40"), "Hail to you, Osiris")

KINGS = [  # (prenomen, nomen) with gods' names written first
    ((G("N5", "Y5", "L1"), "Menkheperre"), (G("G26", "F31", "S29"), "Thutmose")),
    ((G("N5", "C10", "V30"), "Nebmaatre"), (G("M17", "Y5", "N35", "R4", "X1", "Q3"), "Amenhotep")),
    ((G("N5", "L1", "Z3", "V30"), "Nebkheperure"),
     (G("M17", "Y5", "N35", "X1", "G43", "X1", "S34"), "Tutankhamun")),
    ((G("N5", "F12", "C10", "U21", "N35", "N5"), "Usermaatre-setepenre"),
     (G("N5", "F31", "S29", "M23", "M17", "Y5", "N35", "U7"), "Ramesses-meryamun")),
]
NSWT_BITY = (G("M23", "X1", "L2", "X1"), "King of Upper and Lower Egypt")
NB_TAWY = (G("V30", "N16", "N16"), "Lord of the Two Lands")
SA_RA = (G("G39", "N5"), "Son of Ra")
NB_KHAW = (G("V30", "N28", "Z2"), "Lord of Appearances")
DI_ANKH = (G("X8", "S34", "I10", "X1", "N17"), "given life forever")

# =====================================================================
#  QUADRATS
# =====================================================================
def glyph_box(ch, size):
    x0, y0, x1, y1 = hfont(size).getbbox(ch)
    return x0, y0, x1 - x0, y1 - y0

def make_quadrats(signs, size, S, color="black"):
    """Pack signs into S x S blocks: rows of signs, rows stacked."""
    quads, rows = [], []
    def flush():
        if rows:
            quads.append(rows[:])
            rows.clear()
    gap = max(1, S // 12)
    for ch in signs:
        _, _, w, h = glyph_box(ch, size)
        if rows:
            row = rows[-1]
            rw = sum(it[1] for it in row) + gap * len(row)
            rh = max(it[2] for it in row)
            others = sum(max(it[2] for it in r) + gap for r in rows[:-1])
            if rw + w <= S * 1.08 and others + max(rh, h) <= S * 1.05:
                row.append((ch, w, h, color))
                continue
            total = others + rh + gap
            if total + h <= S * 1.05 and w <= S * 1.1:
                rows.append([(ch, w, h, color)])
                continue
            flush()
        rows.append([(ch, w, h, color)])
    flush()
    return quads

def draw_quadrat(layers, quad, x, y, S, size):
    """Draw one quadrat with its top-left at (x, y)."""
    gap = max(1, S // 12)
    heights = [max(it[2] for it in r) for r in quad]
    total = sum(heights) + gap * (len(quad) - 1)
    cy = y + max(0, (S - total) / 2)
    for r, rh in zip(quad, heights):
        rw = sum(it[1] for it in r) + gap * (len(r) - 1)
        cx = x + (S - rw) / 2
        for ch, w, h, color in r:
            ox, oy, _, _ = glyph_box(ch, size)
            ty = cy + (rh - h)          # signs stand on the row's baseline
            stamp(layers[color], ch, cx - ox, ty - oy, size)
            cx += w + gap
        cy += rh + gap

def stamp(img, ch, x, y, size, stretch=None):
    """Render a sign smoothly, then threshold to 1-bit for crisp e-paper."""
    f = hfont(size)
    x0, y0, x1, y1 = f.getbbox(ch)
    tile = Image.new("L", (x1 + 2, y1 + 2), 0)
    ImageDraw.Draw(tile).text((0, 0), ch, font=f, fill=255)
    if stretch:
        tile = tile.crop((x0, y0, x1, y1)).resize(stretch, Image.LANCZOS)
        x, y = x + x0, y + y0
        x0 = y0 = 0
    mask = tile.point(lambda p: 255 if p > 55 else 0)
    img.paste(INK, (int(round(x)), int(round(y))), mask)

def stamp_fit(img, ch, x, base_y, max_w, max_h):
    """Draw a sign scaled to fit max_w x max_h, standing on base_y."""
    f = hfont(60)
    x0, y0, x1, y1 = f.getbbox(ch)
    k = min(max_w / (x1 - x0), max_h / (y1 - y0))
    w, h = int((x1 - x0) * k), int((y1 - y0) * k)
    tile = Image.new("L", (x1 + 2, y1 + 2), 0)
    ImageDraw.Draw(tile).text((0, 0), ch, font=f, fill=255)
    tile = tile.crop((x0, y0, x1, y1)).resize((w, h), Image.LANCZOS)
    img.paste(INK, (int(x), int(base_y - h)), tile.point(lambda p: 255 if p > 70 else 0))

# =====================================================================
#  TEXT BUILDERS — return list of (signs, english, color) phrases
# =====================================================================
RED = "red"
BLACK = "black"

def owner():
    if random.random() < 0.3:
        return random.choice(WOMEN), True
    return random.choice(MEN), False

def offering_formula():
    (name, name_en), female = owner()
    god = random.choice(GODS)
    offs = random.sample(OFFERINGS, random.randint(2, 4))
    phrases = [HTP_DI_NSW, god, DI_F, PRT_KHRW] + offs + [N_KA_N, IMAKHU, (name, name_en), MAA_KHRW]
    eng = (f"An offering which the king gives to {god[1]}, that he may give an invocation "
           f"offering of {', '.join(o[1] for o in offs)} for the ka of the revered "
           f"{name_en}, true of voice.")
    return [(s, e, BLACK) for s, e in phrases], eng, female, name_en

def book_of_the_dead():
    (name, name_en), female = owner()
    phrases = [(RUBRIC[0], RUBRIC[1], RED),
               (DD_MDW_IN[0], DD_MDW_IN[1], BLACK), (WSIR[0], WSIR[1], BLACK),
               (name, name_en, BLACK), (MAA_KHRW[0], MAA_KHRW[1], BLACK),
               (HAIL[0], HAIL[1], BLACK)]
    # continue with the offerings asked for, as many as fit
    for o in random.sample(OFFERINGS, len(OFFERINGS)):
        phrases.append((o[0], o[1], BLACK))
    phrases += [(N_KA_N[0], N_KA_N[1], BLACK), (WSIR[0], WSIR[1], BLACK),
                (name, name_en, BLACK), (MAA_KHRW[0], MAA_KHRW[1], BLACK)]
    eng = (f"Spell for going forth by day. Words spoken by the Osiris {name_en}, "
           f"true of voice: Hail to you, Osiris...")
    return phrases, eng

# =====================================================================
#  OBJECTS
# =====================================================================
def papyrus_texture(img):
    """Faint fibres and a ragged right and bottom edge."""
    for _ in range(60):
        y = random.randrange(HEIGHT)
        x = random.randrange(WIDTH)
        for k in range(random.randint(6, 20)):
            if random.random() < 0.35:
                img.putpixel(((x + k * 2) % WIDTH, y), INK)

def torn_edges(layers):
    import math
    phase = random.uniform(0, 6)
    for img in layers:
        d = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            depth = 2 + 2 * math.sin(y / 9 + phase) + random.random() * 2
            d.line((WIDTH - depth, y, WIDTH, y), fill=PAPER)
        for x in range(WIDTH):
            depth = 1 + 1.5 * math.sin(x / 7 + phase) + random.random() * 2
            d.line((x, HEIGHT - depth, x, HEIGHT), fill=PAPER)

def lacunae(layers, box, n):
    x0, y0, x1, y1 = box
    for _ in range(n):
        cx, cy = random.uniform(x0, x1), random.uniform(y0, y1)
        r = random.uniform(3, 6)
        pts = []
        import math
        for k in range(10):
            a = 2 * math.pi * k / 10
            rr = r * random.uniform(0.6, 1.2)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        for img in layers:
            ImageDraw.Draw(img).polygon(pts, fill=PAPER)

def border_band(d_black, d_red, y):
    """The black-red-black stripes that frame papyrus texts."""
    d_black.line((4, y, WIDTH - 6, y), fill=INK, width=2)
    d_red.line((4, y + 3, WIDTH - 6, y + 3), fill=INK, width=2)
    d_black.line((4, y + 6, WIDTH - 6, y + 6), fill=INK, width=1)

def render_papyrus(black, red, db, dr):
    phrases, eng = book_of_the_dead()
    layers = {BLACK: black, RED: red}
    S = 26
    size = int(S * 0.8)
    border_band(db, dr, 4)
    reading_h = 20 if SHOW_READING else 0
    bottom = HEIGHT - 14 - reading_h
    border_band(db, dr, bottom + 2)
    top = 16
    col_w = S + 3
    ncols = (WIDTH - 10) // col_w
    left = (WIDTH - ncols * col_w) // 2
    for c in range(ncols + 1):
        db.line((left + c * col_w, top - 2, left + c * col_w, bottom), fill=INK, width=1)
    col, y = 0, top
    for signs, _, color in phrases:
        quads = make_quadrats(signs, size, S, color)
        need = len(quads) * (S + 1)
        if y + need > bottom and col + 1 >= ncols:
            break
        for q in quads:
            if y + S > bottom:
                col += 1
                y = top
                if col >= ncols:
                    break
            draw_quadrat(layers, q, left + col * col_w + 1.5, y, S, size)
            y += S + 1
        if col >= ncols:
            break
    lacunae([black, red], (left, top, WIDTH - 8, bottom), random.randint(0, 2))
    papyrus_texture(black)
    return eng, bottom + 10

def winged_disk(db, dr, cx, cy, span):
    """Winged sun disk (Behdety): red disk, uraei, long feathered wings."""
    r = 6
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK)
    for side in (-1, 1):
        # wing: layered curved feathers
        for k in range(3):
            y = cy - 2 + k * 3
            x_end = cx + side * (span / 2 - k * 6)
            db.line((cx + side * (r + 1), y, x_end, y - 3 + k), fill=INK, width=2)
        db.line((cx + side * (r + 1), cy + 6, cx + side * (span / 2 - 22), cy + 8), fill=INK, width=1)
        # uraeus beside the disk
        ux = cx + side * (r + 3)
        db.arc((ux - 3, cy - 2, ux + 3, cy + 8), 270 if side > 0 else 180, 90 if side > 0 else 360, fill=INK, width=2)
        db.ellipse((ux - 2, cy - 4, ux + 2, cy), fill=INK)

def render_stela(black, red, db, dr):
    phrases, eng, female, _ = offering_formula()
    layers = {BLACK: black, RED: red}
    S = 24
    size = int(S * 0.8)
    x0, x1 = 6, WIDTH - 7
    top, bottom = 6, HEIGHT - 8
    # round-topped stela outline
    db.arc((x0, top, x1, top + (x1 - x0)), 180, 360, fill=INK, width=3)
    arc_mid = top + (x1 - x0) / 2
    db.line((x0, arc_mid, x0, bottom), fill=INK, width=3)
    db.line((x1, arc_mid, x1, bottom), fill=INK, width=3)
    db.line((x0, bottom, x1, bottom), fill=INK, width=3)
    winged_disk(db, dr, WIDTH / 2, top + 30, x1 - x0 - 44)
    # the sky sign as a band under the lunette
    y = top + 48
    db.line((x0 + 6, y, x1 - 6, y), fill=INK, width=2)
    y += 4

    # horizontal lines of text, ruled between registers
    inner_l, inner_r = x0 + 8, x1 - 8
    per_line = int((inner_r - inner_l) // S)
    lm = inner_l + ((inner_r - inner_l) - per_line * S) / 2
    reading_h = 22 if SHOW_READING else 0
    scene_h = 46
    text_bottom = bottom - scene_h - reading_h - 4
    quads = []
    for signs, _, color in phrases:
        quads += make_quadrats(signs, size, S, color)
    lines = [quads[i:i + per_line] for i in range(0, len(quads), per_line)]
    max_lines = int((text_bottom - y) // (S + 3))
    for li, line in enumerate(lines[:max_lines]):
        for qi, q in enumerate(line):
            draw_quadrat(layers, q, lm + qi * S, y, S, size)
        y += S + 1
        db.line((inner_l, y, inner_r, y), fill=INK, width=1)
        y += 2

    # scene: owner seated before an offering table
    sy = bottom - reading_h - scene_h - 2
    db.line((inner_l, sy + scene_h, inner_r, sy + scene_h), fill=INK, width=2)   # ground line
    figure = G("B1")[0] if female else G("A51")[0]
    table = G("R1")[0]
    stamp_fit(red, table, WIDTH / 2 - 46, sy + scene_h, 36, 30)
    stamp_fit(black, figure, WIDTH / 2 + 4, sy + scene_h, 40, 42)
    return eng, bottom - reading_h + 2

def cartouche(dr, x, y0, w, y1):
    """Oval ring with the tie (shen) at the bottom."""
    dr.rounded_rectangle((x, y0, x + w, y1), radius=w // 2, outline=INK, width=2)
    dr.line((x + 3, y1 + 3, x + w - 3, y1 + 3), fill=INK, width=2)
    dr.line((x + w / 2, y1, x + w / 2, y1 + 3), fill=INK, width=2)

def was_sceptre(d, x, top, bottom):
    """Was-sceptre: straight shaft, forked foot, angled animal head."""
    d.line((x, top + 6, x, bottom - 6), fill=INK, width=2)
    d.line((x, bottom - 6, x - 3, bottom), fill=INK, width=2)
    d.line((x, bottom - 6, x + 3, bottom), fill=INK, width=2)
    d.polygon([(x - 1, top + 7), (x - 1, top + 1), (x + 6, top - 1), (x + 6, top + 2),
               (x + 2, top + 3), (x + 1, top + 7)], fill=INK)
    d.line((x - 1, top + 2, x - 3, top - 2), fill=INK, width=1)   # ear

def render_royal(black, red, db, dr):
    (pre, pre_en), (nom, nom_en) = random.choice(KINGS)
    layers = {BLACK: black, RED: red}
    S = 22
    size = int(S * 0.8)
    # sky sign over the door-jamb
    db.line((8, 8, WIDTH - 9, 8), fill=INK, width=4)
    db.line((8, 8, 8, 16), fill=INK, width=3)
    db.line((WIDTH - 9, 8, WIDTH - 9, 16), fill=INK, width=3)
    reading_h = 22 if SHOW_READING else 0
    ground = HEIGHT - 10 - reading_h
    db.line((8, ground, WIDTH - 9, ground), fill=INK, width=3)
    # was-sceptres either side, stretched to the full height
    for x in (17, WIDTH - 18):
        was_sceptre(db, x, 20, ground - 1)

    cols = [
        [(NSWT_BITY, BLACK), (NB_TAWY, BLACK), ((pre, pre_en), "cart")],
        [(SA_RA, BLACK), (NB_KHAW, BLACK), ((nom, nom_en), "cart"), (DI_ANKH, BLACK)],
    ]
    # shrink the sign size until the taller column fits under the sky sign
    for S in range(24, 13, -1):
        size = int(S * 0.8)
        measured = []
        for col in cols:
            blocks = []
            for (signs, _), kind in col:
                blocks.append((make_quadrats(signs, size - (2 if kind == "cart" else 0), S, BLACK), kind))
            total = sum(len(q) * (S + 1) + (12 if k == "cart" else 0) for q, k in blocks)
            measured.append((blocks, total))
        if max(t for _, t in measured) <= ground - 26:
            break
    col_x = [WIDTH / 2 - S - 10, WIDTH / 2 + 10]
    for cx, (blocks, total) in zip(col_x, measured):
        y = 22 + (ground - 22 - total) / 2
        for q, kind in blocks:
            if kind == "cart":
                y0 = y
                y += 3
                for quad in q:
                    draw_quadrat(layers, quad, cx, y, S, size - 2)
                    y += S + 1
                cartouche(dr, cx - 4, y0, S + 8, y + 2)
                y += 9
            else:
                for quad in q:
                    draw_quadrat(layers, quad, cx, y, S, size)
                    y += S + 1
    eng = (f"King of Upper and Lower Egypt, Lord of the Two Lands, {pre_en}; "
           f"Son of Ra, Lord of Appearances, {nom_en}, given life forever.")
    return eng, ground + 4

OBJECTS = [(3, render_papyrus), (2, render_stela), (2, render_royal)]

# =====================================================================
#  RENDER
# =====================================================================
def _wrap(text, f, width, max_lines=2):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines

def render(epd):
    black = Image.new("1", (WIDTH, HEIGHT), PAPER)
    red = Image.new("1", (WIDTH, HEIGHT), PAPER)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)

    weights, objs = zip(*OBJECTS)
    obj = random.choices(objs, weights=weights)[0]
    eng, ry = obj(black, red, db, dr)

    if SHOW_READING:
        f = small(7)
        for i, ln in enumerate(_wrap(eng, f, WIDTH - 16)):
            tw = db.textlength(ln, font=f)
            db.text(((WIDTH - tw) / 2, ry + i * 8), ln, font=f, fill=INK)

    if obj is render_papyrus:
        torn_edges([black, red])
    for img, n in ((black, 150), (red, 80)):
        for _ in range(n):
            img.putpixel((random.randrange(WIDTH), random.randrange(HEIGHT)), PAPER)

    save_preview_png(black, red, f"egypt_{int(time.time())}.png")
    epd.display(epd.getbuffer(black), epd.getbuffer(red))

def save_preview_png(black, red, filename):
    preview = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    preview.paste((0, 0, 0), mask=black.point(lambda p: 255 - p))
    preview.paste((200, 0, 0), mask=red.point(lambda p: 255 - p))
    preview.save(filename)

def main():
    epd = epd2in7b.EPD()
    epd.init()
    try:
        while True:
            render(epd)
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
