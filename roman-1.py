#!/usr/bin/env python3
"""
Roman inscriptions on a 2.7" e-Paper HAT (B).

Every frame generates a Latin inscription in the formulas the Romans
actually used, and carves it on the matching kind of monument:

    tombstone          -> gable-topped stele, or a tabula ansata
    votive altar       -> altar with bolsters and cornice
    imperial building  -> tabula ansata, or a moulded panel
    milestone          -> milestone column

Letters are red, as the cut letters were painted with minium; words are
divided by triangular interpuncts, numerals that the Romans barred get
an overline, and the first line is set larger, as stonecutters did.

The emperor titles use consulship / tribunician-power combinations that
fall inside each emperor's real ranges, so the dates are plausible.
"""
import os
import random
import time
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in7b   # 2.7" e-Paper HAT (B)

WIDTH = 176
HEIGHT = 264
SHOW_READING = True     # short English reading under the inscription

INK = 0
PAPER = 255

# Fonts: first that exists. Cinzel (free, Google Fonts) looks the most like
# Roman capitals; drop Cinzel-Regular.ttf next to this script to use it.
HERE = os.path.dirname(os.path.abspath(__file__))
CAPITAL_FONTS = [
    os.path.join(HERE, "Cinzel-Regular.ttf"),
    os.path.join(HERE, "Cinzel[wght].ttf"),
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
SMALL_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

def _first(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None

CAPITAL_PATH = _first(CAPITAL_FONTS)
SMALL_PATH = _first(SMALL_FONTS)
_fonts = {}
def capital(size):
    if (CAPITAL_PATH, size) not in _fonts:
        _fonts[(CAPITAL_PATH, size)] = (ImageFont.truetype(CAPITAL_PATH, size)
                                        if CAPITAL_PATH else ImageFont.load_default())
    return _fonts[(CAPITAL_PATH, size)]

def small(size=7):
    return ImageFont.truetype(SMALL_PATH, size) if SMALL_PATH else ImageFont.load_default()

# =====================================================================
#  ROMAN NUMERALS AND NAMES
# =====================================================================
def roman(n):
    out = ""
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                 (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                 (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += s
            n -= v
    # inscriptions mostly wrote 4 as IIII
    return out.replace("IV", "IIII")

PRAENOMINA = {"C": "Gaius", "CN": "Gnaeus", "L": "Lucius", "M": "Marcus",
              "P": "Publius", "Q": "Quintus", "SEX": "Sextus", "T": "Titus",
              "TI": "Tiberius", "A": "Aulus", "D": "Decimus"}
NOMINA = ["IVLIVS", "CLAVDIVS", "VALERIVS", "FLAVIVS", "AVRELIVS", "CORNELIVS",
          "ANTONIVS", "AEMILIVS", "POMPEIVS", "SEMPRONIVS", "ATILIVS", "LICINIVS",
          "PETRONIVS", "CASSIVS", "VIBIVS", "OCTAVIVS", "SVLPICIVS", "CAECILIVS"]
COGNOMINA = [("SECVNDVS", "SECVNDA"), ("FIRMVS", "FIRMA"), ("RVFVS", "RVFA"),
             ("SEVERVS", "SEVERA"), ("MAXIMVS", "MAXIMA"), ("VERVS", "VERA"),
             ("PRISCVS", "PRISCA"), ("PROCVLVS", "PROCVLA"), ("SATVRNINVS", "SATVRNINA"),
             ("MARCELLVS", "MARCELLA"), ("PRIMVS", "PRIMA"), ("IVSTVS", "IVSTA"),
             ("VITALIS", "VITALIS"), ("TERTIVS", "TERTIA"), ("PATERNVS", "PATERNA")]
TRIBES = {"CLA": "Claudia", "FAB": "Fabia", "GAL": "Galeria", "POL": "Pollia",
          "QVI": "Quirina", "SER": "Sergia", "VOL": "Voltinia", "AEM": "Aemilia",
          "ANI": "Aniensis", "ARN": "Arnensis", "POM": "Pomptina"}
LEGIONS = [  # (abbreviation tokens, English)
    (["LEG", "^II", "AVG"], "Legio II Augusta"),
    (["LEG", "^XX", "V", "V"], "Legio XX Valeria Victrix"),
    (["LEG", "^XXX", "VLP", "VIC"], "Legio XXX Ulpia Victrix"),
    (["LEG", "^X", "GEM"], "Legio X Gemina"),
    (["LEG", "^I", "MIN"], "Legio I Minervia"),
    (["LEG", "^VI", "VIC"], "Legio VI Victrix"),
    (["LEG", "^VIII", "AVG"], "Legio VIII Augusta"),
    (["LEG", "^XXII", "PR", "P", "F"], "Legio XXII Primigenia"),
    (["LEG", "^III", "AVG"], "Legio III Augusta"),
    (["LEG", "^IX", "HISP"], "Legio IX Hispana"),
]
RANKS = [("MIL", "soldier"), ("SIGNIFER", "standard-bearer"),
         ("AQVILIFER", "eagle-bearer"), ("OPTIO", "optio"),
         ("CENTVRIO", "centurion"), ("VET", "veteran")]

def person(female=False):
    pr = random.choice(list(PRAENOMINA))
    nomen = random.choice(NOMINA)
    cog = random.choice(COGNOMINA)[1 if female else 0]
    if female:
        nomen = nomen[:-2] + "A"          # Valerius -> Valeria
    father = random.choice(list(PRAENOMINA))
    tribe = random.choice(list(TRIBES))
    full = lambda w: w[0] + w[1:].lower().replace("v", "u")
    if female:
        tokens = [nomen, father, "F", cog]
        english = f"{full(nomen)} {full(cog)}"
    else:
        tokens = [pr, nomen, father, "F", tribe, cog]
        english = f"{PRAENOMINA[pr]} {full(nomen)} {full(cog)}"
    return tokens, english, cog

# =====================================================================
#  INSCRIPTION GENERATORS
#  Each returns (kind, lines, reading). A line is a list of tokens;
#  tokens are separated by interpuncts when drawn. "^" marks a barred
#  numeral.
# =====================================================================
def tombstone():
    female = random.random() < 0.3
    name, english, _ = person(female)
    lines = []
    if random.random() < 0.75:
        lines.append(["D", "M"])                    # Dis Manibus
    # break the name over lines the way stonecutters did
    if female:
        lines += [name[:3], name[3:]]
    else:
        lines += [name[:2], name[2:5], name[5:]]
    role = ""
    if not female and random.random() < 0.6:
        leg, leg_en = random.choice(LEGIONS)
        rank, rank_en = random.choice(RANKS)
        lines.append([rank] + leg)
        role = f", {rank_en} of {leg_en}"
        age = random.randint(22, 48)
        stip = random.randint(max(1, age - 38), age - 17)
        lines.append(["ANN", roman(age), "STIP", roman(stip)])
    else:
        age = random.randint(3, 75)
        lines.append(["VIXIT", "ANNIS", roman(age)] if random.random() < 0.5
                     else ["VIX", "ANN", roman(age)])
    if random.random() < 0.6:
        lines.append(["H", "S", "E"])               # hic situs est
    ending = random.random()
    if ending < 0.4:
        lines.append(["HERES", "F", "C"])           # heres faciendum curavit
        by = "his heir had it made" if not female else "her heir had it made"
    elif ending < 0.7:
        lines.append(["CONIVGI", "B", "M", "P"])    # coniugi bene merenti posuit
        by = "set up by the spouse"
    else:
        lines.append(["S", "T", "T", "L"])          # sit tibi terra levis
        by = "may the earth lie light on you"
    reading = f"Tombstone of {english}{role}, aged {age}; {by}."
    return "tomb", lines, reading

GODS = [(["I", "O", "M"], "Jupiter Best and Greatest"),
        (["DEAE", "NEHALENNIAE"], "the goddess Nehalennia"),
        (["MATRIBVS"], "the Mother goddesses"),
        (["MARTI"], "Mars"), (["MERCVRIO"], "Mercury"),
        (["HERCVLI", "MAGVSANO"], "Hercules Magusanus"),
        (["GENIO", "LOCI"], "the spirit of the place"),
        (["MINERVAE"], "Minerva"), (["FORTVNAE"], "Fortuna"),
        (["APOLLINI"], "Apollo")]

def votive_altar():
    god, god_en = random.choice(GODS)
    female = random.random() < 0.15
    name, english, _ = person(female)
    lines = [god]
    if len(name) > 4:
        lines += [name[:2], name[2:]]
    else:
        lines += [name]
    if not female and random.random() < 0.4:
        leg, leg_en = random.choice(LEGIONS)
        lines.append(["MIL"] + leg)
    if random.random() < 0.35:
        lines.append(["PRO", "SE", "ET", "SVIS"])
    lines.append(["V", "S", "L", "M"])              # votum solvit libens merito
    reading = f"Altar to {god_en}: {english} gladly fulfilled a vow."
    return "altar", lines, reading

# Emperors: (name lines, title builder, English name, year from trib. pot.)
def _augustus():
    tp = random.randint(1, 17)
    lines = [["IMP", "CAESAR", "DIVI", "F"], ["AVGVSTVS"]]
    if tp >= 12:
        lines.append(["PONTIFEX", "MAXIMVS"])
    lines.append(["COS", roman(11), "TRIB", "POT", roman(tp)])
    yr = 24 - tp
    return lines, "Augustus", f"{yr} BC" if yr > 0 else f"AD {1 - yr}"

def _trajan():
    tp = random.randint(8, 21)
    cos = 5 if tp <= 15 else 6
    return ([["IMP", "CAESAR", "NERVA"], ["TRAIANVS", "AVG", "GERM", "DACICVS"],
             ["PONT", "MAX", "TRIB", "POT", roman(tp)], ["COS", roman(cos), "P", "P"]],
            "Trajan", f"AD {96 + tp}")

def _hadrian():
    tp = random.randint(12, 22)
    return ([["IMP", "CAESAR", "TRAIANVS"], ["HADRIANVS", "AVG"],
             ["PONT", "MAX", "TRIB", "POT", roman(tp)], ["COS", "III", "P", "P"]],
            "Hadrian", f"AD {116 + tp}")

def _antoninus():
    tp = random.randint(8, 24)
    return ([["IMP", "CAES", "T", "AELIVS"], ["HADRIANVS", "ANTONINVS"],
             ["AVG", "PIVS", "P", "P"], ["TRIB", "POT", roman(tp), "COS", "IIII"]],
            "Antoninus Pius", f"AD {137 + tp}")

def _marcus():
    tp = random.randint(15, 34)
    return ([["IMP", "CAES", "M", "AVRELIVS"], ["ANTONINVS", "AVG"],
             ["PONT", "MAX", "TRIB", "POT", roman(tp)], ["COS", "III"]],
            "Marcus Aurelius", f"AD {146 + tp}")

def _severus():
    tp = random.randint(10, 19)
    return ([["IMP", "CAES", "L", "SEPTIMIVS"], ["SEVERVS", "PIVS", "PERTINAX", "AVG"],
             ["PONT", "MAX", "TRIB", "POT", roman(tp)], ["COS", "III", "P", "P"]],
            "Septimius Severus", f"AD {192 + tp}")

EMPERORS = [_augustus, _trajan, _hadrian, _antoninus, _marcus, _severus]

WORKS = [(["VIAM", "REFECIT"], "repaired the road"),
         (["PONTEM", "RESTITVIT"], "restored the bridge"),
         (["AQVAEDVCTVM", "FECIT"], "built the aqueduct"),
         (["MVROS", "ET", "PORTAS", "DEDIT"], "gave the walls and gates"),
         (["THERMAS", "RESTITVIT"], "restored the baths"),
         (["HORREA", "FECIT"], "built the granaries"),
         (["TEMPLVM", "RESTITVIT"], "restored the temple")]

def building():
    lines, emp, year = random.choice(EMPERORS)()
    work, work_en = random.choice(WORKS)
    if random.random() < 0.4:
        leg, leg_en = random.choice(LEGIONS)
        lines += [["PER", "VEXILLATIONEM"], leg, work]
        reading = f"Emperor {emp} {work_en}, by a detachment of {leg_en} (c. {year})."
    else:
        lines += [work]
        reading = f"Emperor {emp} {work_en} (c. {year})."
    return "building", lines, reading

TOWNS = [(["COL", "AGRIPP"], "Colonia Agrippina (Cologne)"),
         (["NOVIOMAG"], "Noviomagus (Nijmegen)"),
         (["MOG"], "Mogontiacum (Mainz)"),
         (["AVG", "TREV"], "Augusta Treverorum (Trier)"),
         (["LVGVD"], "Lugdunum (Lyon)"),
         (["LONDIN"], "Londinium (London)"),
         (["EBVR"], "Eboracum (York)"),
         (["VINDOB"], "Vindobona (Vienna)"),
         (["TRAIECT"], "Traiectum (Utrecht)")]

def milestone():
    lines, emp, year = random.choice(EMPERORS)()
    town, town_en = random.choice(TOWNS)
    miles = random.randint(1, 40)
    lines += [["A"] + town, ["M", "P", "^" + roman(miles)]]
    reading = f"Milestone of {emp}: {miles} Roman miles from {town_en} (c. {year})."
    return "milestone", lines, reading

GENERATORS = [(4, tombstone), (2, votive_altar), (2, building), (2, milestone)]

# =====================================================================
#  MONUMENTS (frames). Each draws on the given layer and returns the
#  box available for the text.
# =====================================================================
def _moulding(d, box, outer=3):
    x0, y0, x1, y1 = box
    d.rectangle((x0, y0, x1, y1), outline=INK, width=outer)
    d.rectangle((x0 + outer + 2, y0 + outer + 2, x1 - outer - 2, y1 - outer - 2),
                outline=INK, width=1)

def _rosette(d, cx, cy, r):
    import math
    for k in range(6):
        a = k * math.pi / 3
        px, py = cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a)
        d.ellipse((px - r * 0.45, py - r * 0.45, px + r * 0.45, py + r * 0.45),
                  outline=INK, width=1)
    d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=INK)

def tabula_ansata(d):
    """The rectangular plaque with dovetail 'handles' either side."""
    x0, x1 = 20, WIDTH - 21
    y0, y1 = 8, HEIGHT - 9
    cy = HEIGHT // 2
    for side in (-1, 1):
        bx = x0 if side < 0 else x1
        tip = 3 if side < 0 else WIDTH - 4
        d.polygon([(bx, cy - 26), (tip, cy - 40), (tip, cy + 40), (bx, cy + 26)],
                  outline=INK, width=2)
        hx = (bx + tip) / 2
        d.ellipse((hx - 2, cy - 2, hx + 2, cy + 2), outline=INK, width=1)  # nail hole
    _moulding(d, (x0, y0, x1, y1))
    return (x0 + 9, y0 + 10, x1 - 9, y1 - 9)

def stele(d):
    """Tombstone with a triangular gable, rosette, acroteria and plinth."""
    x0, x1 = 8, WIDTH - 9
    gy0, gy1 = 6, 46
    cx = WIDTH / 2
    d.polygon([(x0, gy1), (cx, gy0), (x1, gy1)], outline=INK, width=3)
    d.line((x0 + 10, gy1 - 4, cx, gy0 + 7, x1 - 10, gy1 - 4), fill=INK, width=1)
    d.line((x0 + 10, gy1 - 4, x1 - 10, gy1 - 4), fill=INK, width=1)
    _rosette(d, cx, gy1 - 15, 8)
    for ax in (x0, x1):                                  # acroteria
        d.polygon([(ax - 2, gy1), (ax, gy1 - 10), (ax + (8 if ax == x0 else -8), gy1)], fill=INK)
    base_y = HEIGHT - 28
    _moulding(d, (x0, gy1 + 2, x1, base_y))
    d.rectangle((x0 - 3, base_y + 3, x1 + 3, HEIGHT - 6), outline=INK, width=2)
    d.line((x0 - 3, base_y + 9, x1 + 3, base_y + 9), fill=INK, width=1)
    return (x0 + 9, gy1 + 11, x1 - 9, base_y - 7)

def altar(d):
    """Altar: bolsters (pulvini) and focus on top, cornice, shaft, base."""
    cx = WIDTH / 2
    # bolsters seen from the front: scroll ends
    for bx in (22, WIDTH - 23):
        d.ellipse((bx - 11, 6, bx + 11, 28), outline=INK, width=2)
        d.ellipse((bx - 5, 12, bx + 5, 22), outline=INK, width=1)
        d.ellipse((bx - 1, 16, bx + 1, 18), fill=INK)
    d.arc((cx - 16, 8, cx + 16, 30), 0, 180, fill=INK, width=2)  # focus (bowl)
    d.line((cx - 16, 19, cx + 16, 19), fill=INK, width=2)
    d.line((33, 28, WIDTH - 34, 28), fill=INK, width=2)
    # cornice: stepped mouldings
    for i, (inset, w) in enumerate(((6, 3), (10, 1), (14, 2))):
        y = 32 + i * 5
        d.line((inset, y, WIDTH - 1 - inset, y), fill=INK, width=w)
    d.line((6, 32, 6, 32), fill=INK)
    sx0, sx1 = 20, WIDTH - 21
    base = HEIGHT - 34
    d.rectangle((sx0, 45, sx1, base), outline=INK, width=2)
    d.rectangle((sx0 + 5, 50, sx1 - 5, base - 5), outline=INK, width=1)
    for i, (inset, w) in enumerate(((14, 2), (10, 1), (6, 3))):
        y = base + 4 + i * 5
        d.line((inset, y, WIDTH - 1 - inset, y), fill=INK, width=w)
    d.rectangle((6, base + 18, WIDTH - 7, HEIGHT - 5), outline=INK, width=2)
    return (sx0 + 8, 56, sx1 - 8, base - 9)

def milestone_column(d):
    """Cylindrical milestone on a square base; edge lines suggest roundness."""
    x0, x1 = 14, WIDTH - 15
    top, bottom = 18, HEIGHT - 36
    d.arc((x0, top - 12, x1, top + 12), 180, 360, fill=INK, width=2)
    d.arc((x0, top - 12, x1, top + 12), 0, 180, fill=INK, width=1)
    d.line((x0, top, x0, bottom), fill=INK, width=2)
    d.line((x1, top, x1, bottom), fill=INK, width=2)
    for k, off in enumerate((4, 9)):                    # curvature lines
        d.line((x0 + off, top + 10, x0 + off, bottom - 2), fill=INK, width=1)
        d.line((x1 - off, top + 10, x1 - off, bottom - 2), fill=INK, width=1)
    d.arc((x0, bottom - 12, x1, bottom + 12), 0, 180, fill=INK, width=2)
    d.rectangle((6, bottom + 6, WIDTH - 7, HEIGHT - 6), outline=INK, width=2)
    return (x0 + 14, top + 16, x1 - 14, bottom - 8)

def moulded_panel(d):
    """Plain building plaque with a stepped (cyma) moulding."""
    d.rectangle((3, 3, WIDTH - 4, HEIGHT - 4), outline=INK, width=4)
    d.rectangle((10, 10, WIDTH - 11, HEIGHT - 11), outline=INK, width=1)
    d.rectangle((14, 14, WIDTH - 15, HEIGHT - 15), outline=INK, width=2)
    return (22, 24, WIDTH - 22, HEIGHT - 22)

MONUMENTS = {
    "tomb":      [stele, stele, tabula_ansata],
    "altar":     [altar],
    "building":  [tabula_ansata, moulded_panel],
    "milestone": [milestone_column],
}

# =====================================================================
#  LETTERING
# =====================================================================
def _line_width(tokens, font, sep):
    w = 0
    for t in tokens:
        w += font.getlength(t.lstrip("^"))
    return w + sep * (len(tokens) - 1)

def _interpunct(d, x, y, s):
    """Triangular word divider, point down, as cut with the chisel."""
    d.polygon([(x - s, y - s * 0.6), (x + s, y - s * 0.6), (x, y + s * 0.8)], fill=INK)

def _hedera(d, x, y, s):
    """Ivy leaf (hedera distinguens), the decorative word divider."""
    d.ellipse((x - s, y - s * 0.6, x, y + s * 0.4), fill=INK)
    d.ellipse((x, y - s * 0.6, x + s, y + s * 0.4), fill=INK)
    d.polygon([(x - s, y), (x + s, y), (x, y + s * 1.2)], fill=INK)
    d.line((x, y - s * 0.4, x + s * 0.6, y - s * 1.4), fill=INK, width=1)

def carve_text(d, lines, box, reading_lines):
    x0, y0, x1, y1 = box
    bw = x1 - x0
    reading_h = 9 * len(reading_lines) + 3 if reading_lines else 0
    bh = y1 - y0 - reading_h

    # Size the lettering like an ordinatio: one size for the body, the
    # first line larger. A line that is far too long is set smaller on
    # its own rather than shrinking the whole inscription.
    def fit(toks, start):
        s = start
        while s > 7 and _line_width(toks, capital(s), s * 0.5) > bw:
            s -= 1
        return s
    def layout(lines):
        for base in range(20, 6, -1):
            fits = [fit(t, base) for t in lines[1:]] or [base]
            body = max(8, min(base, min(fits)))
            sizes = [fit(lines[0], int(body * 1.25))] + [min(body, f) for f in fits]
            total = sum(s * 1.18 for s in sizes)
            if total <= bh:
                return body, sizes, total
        return 7, sizes, total

    # A stonecutter breaks a line when it would otherwise force small
    # letters. Try breaking the widest line, keep the layout with the
    # largest body lettering.
    best_lines = lines
    best = layout(lines)
    cur = lines
    for _ in range(8):
        widths = [(_line_width(t, capital(12), 6), i) for i, t in enumerate(cur) if len(t) > 1]
        if not widths:
            break
        _, i = max(widths)
        t = cur[i]
        cut = len(t) // 2
        cur = cur[:i] + [t[:cut], t[cut:]] + cur[i + 1:]
        trial = layout(cur)
        if trial[0] > best[0] + 1:          # only break if it clearly helps
            best, best_lines = trial, cur
    lines = best_lines
    body, sizes, total = best

    gap = (bh - total) / (len(lines) + 1)
    y = y0 + gap
    hedera_line = 0 if lines[0] == ["D", "M"] and random.random() < 0.5 else -1
    for i, toks in enumerate(lines):
        s = sizes[i]
        font = capital(s)
        sep = s * 0.5
        w = _line_width(toks, font, sep)
        x = x0 + (bw - w) / 2
        cap_top = font.getbbox("H")[1]
        cap_h = font.getbbox("H")[3] - cap_top
        for j, t in enumerate(toks):
            barred = t.startswith("^")
            t = t.lstrip("^")
            d.text((x, y), t, font=font, fill=INK)
            tw = font.getlength(t)
            if barred:                       # numeral bar
                d.line((x - 1, y + cap_top - 3, x + tw + 1, y + cap_top - 3), fill=INK, width=1)
            x += tw
            if j < len(toks) - 1:
                mid_y = y + cap_top + cap_h * 0.5
                if i == hedera_line:
                    _hedera(d, x + sep / 2, mid_y, max(3, s * 0.22))
                else:
                    _interpunct(d, x + sep / 2, mid_y, max(1.2, s * 0.09))
                x += sep
        y += s * 1.18 + gap

    return y1 - reading_h

def _wrap(text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.getlength(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]

# =====================================================================
#  STONE
# =====================================================================
def stone_texture(img, density=0.012):
    for _ in range(int(WIDTH * HEIGHT * density)):
        img.putpixel((random.randrange(WIDTH), random.randrange(HEIGHT)), INK)

def weather(img, amount=200):
    d = ImageDraw.Draw(img)
    for _ in range(amount):
        img.putpixel((random.randrange(WIDTH), random.randrange(HEIGHT)), PAPER)
    for _ in range(random.randint(2, 4)):
        x, y = random.randrange(WIDTH), random.randrange(HEIGHT)
        r = random.randint(1, 3)
        d.ellipse((x - r, y - r, x + r, y + r), fill=PAPER)

# =====================================================================
#  RENDER
# =====================================================================
def render_inscription(epd):
    black = Image.new("1", (WIDTH, HEIGHT), PAPER)
    red = Image.new("1", (WIDTH, HEIGHT), PAPER)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)

    weights, gens = zip(*GENERATORS)
    kind, lines, reading = random.choices(gens, weights=weights)[0]()

    stone_texture(black)
    monument = random.choice(MONUMENTS[kind])
    box = monument(db)
    # clear the speckle inside the text field so the letters read cleanly
    db.rectangle(box, fill=PAPER)

    reading_lines = _wrap(reading, small(), box[2] - box[0]) if SHOW_READING else []
    ry = carve_text(dr, lines, box, reading_lines)
    for i, ln in enumerate(reading_lines):
        tw = db.textlength(ln, font=small())
        db.text((box[0] + (box[2] - box[0] - tw) / 2, ry + 2 + i * 9), ln, font=small(), fill=INK)

    weather(black)
    weather(red, 120)

    timestamp = int(time.time())
    save_preview_png(black, red, f"roman_{timestamp}.png")
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
