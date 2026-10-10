#!/usr/bin/env python3
"""
Kanji with stroke order on a Waveshare 2.7" e-Paper HAT (B).

Uses KanjiVG (stroke-by-stroke vector data for kanji, by Ulrich Apel and
contributors, CC BY-SA 3.0, https://kanjivg.tagaini.net). Each kanji file
holds every stroke as a path in the correct writing order, plus where the
stroke numbers go. This program draws them itself - no SVG library needed.

Study layout (default):
    +--------------------------+
    |  water          4 strokes|
    |                          |
    |      big kanji, with     |
    |    red stroke numbers    |
    |                          |
    |  on SUI   kun mizu       |
    | [1][2][3][4]             |   stroke by stroke, newest stroke in red
    +--------------------------+
Big layout (KEY3): only the kanji, as large as possible, with its numbers.

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next kanji
  KEY2  random order <-> list order (first-grade kanji first)
  KEY3  study layout <-> big layout
  KEY4  stroke numbers on / off

KanjiVG files are downloaded one by one from GitHub and cached in
kanji_cache/. If you have cloned the whole KanjiVG repository, point
KANJIVG_DIR at its "kanji" folder and it works fully offline.

Run on a PC:  python3 kanji.py --preview 水
"""
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.request
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font (with ō, ū macrons)

# ---------------------------------------------------------------- settings
REFRESH_SECONDS = 5                  # pause after each refresh before the next kanji
# A full refresh of the 3-colour panel takes ~15 s, so ~20 s per kanji is
# the real minimum. Waveshare recommends >= 180 s between refreshes for the
# life of the panel when it runs all day.
ORDER = "random"                     # random / list
LAYOUT = "study"                     # study / big
SHOW_NUMBERS = True
BUTTON_PINS = (5, 6, 13, 19)
KANJIVG_DIR = os.path.expanduser("~/kanjivg/kanji")   # optional local copy
KANJIVG_URL = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{:05x}.svg"
CACHE_DIR = os.path.join(HERE, "kanji_cache")

WIDTH, HEIGHT = 176, 264
SUPER = 4                            # draw 4x larger, then reduce: smooth strokes

# ======================================================================
#  KANJI: (kanji, meaning, on-reading, kun-reading)
#  On-readings in capitals, kun-readings lowercase; okurigana in brackets.
# ======================================================================
KANJI = [
    # the 80 first-grade kanji
    ("一", "one", "ICHI, ITSU", "hito(tsu)"), ("右", "right", "U, YŪ", "migi"),
    ("雨", "rain", "U", "ame"), ("円", "circle, yen", "EN", "maru(i)"),
    ("王", "king", "Ō", ""), ("音", "sound", "ON, IN", "oto, ne"),
    ("下", "below", "KA, GE", "shita"), ("火", "fire", "KA", "hi"),
    ("花", "flower", "KA", "hana"), ("貝", "shellfish", "", "kai"),
    ("学", "study", "GAKU", "mana(bu)"), ("気", "spirit, air", "KI, KE", ""),
    ("九", "nine", "KYŪ, KU", "kokono(tsu)"), ("休", "rest", "KYŪ", "yasu(mu)"),
    ("玉", "jewel, ball", "GYOKU", "tama"), ("金", "gold, money", "KIN, KON", "kane"),
    ("空", "sky, empty", "KŪ", "sora"), ("月", "moon, month", "GETSU, GATSU", "tsuki"),
    ("犬", "dog", "KEN", "inu"), ("見", "see", "KEN", "mi(ru)"),
    ("五", "five", "GO", "itsu(tsu)"), ("口", "mouth", "KŌ, KU", "kuchi"),
    ("校", "school", "KŌ", ""), ("左", "left", "SA", "hidari"),
    ("三", "three", "SAN", "mi(ttsu)"), ("山", "mountain", "SAN", "yama"),
    ("子", "child", "SHI, SU", "ko"), ("四", "four", "SHI", "yo(ttsu), yon"),
    ("糸", "thread", "SHI", "ito"), ("字", "character", "JI", "aza"),
    ("耳", "ear", "JI", "mimi"), ("七", "seven", "SHICHI", "nana(tsu)"),
    ("車", "vehicle", "SHA", "kuruma"), ("手", "hand", "SHU", "te"),
    ("十", "ten", "JŪ", "tō"), ("出", "go out", "SHUTSU", "de(ru)"),
    ("女", "woman", "JO, NYO", "onna"), ("小", "small", "SHŌ", "chii(sai), ko"),
    ("上", "above", "JŌ", "ue"), ("森", "forest", "SHIN", "mori"),
    ("人", "person", "JIN, NIN", "hito"), ("水", "water", "SUI", "mizu"),
    ("正", "correct", "SEI, SHŌ", "tada(shii)"), ("生", "life, birth", "SEI, SHŌ", "i(kiru)"),
    ("青", "blue", "SEI", "ao"), ("夕", "evening", "SEKI", "yū"),
    ("石", "stone", "SEKI", "ishi"), ("赤", "red", "SEKI", "aka"),
    ("千", "thousand", "SEN", "chi"), ("川", "river", "SEN", "kawa"),
    ("先", "ahead", "SEN", "saki"), ("早", "early", "SŌ", "haya(i)"),
    ("草", "grass", "SŌ", "kusa"), ("足", "foot, enough", "SOKU", "ashi"),
    ("村", "village", "SON", "mura"), ("大", "big", "DAI, TAI", "ō(kii)"),
    ("男", "man", "DAN, NAN", "otoko"), ("竹", "bamboo", "CHIKU", "take"),
    ("中", "middle", "CHŪ", "naka"), ("虫", "insect", "CHŪ", "mushi"),
    ("町", "town", "CHŌ", "machi"), ("天", "heaven", "TEN", "ame"),
    ("田", "rice field", "DEN", "ta"), ("土", "earth, soil", "DO, TO", "tsuchi"),
    ("二", "two", "NI", "futa(tsu)"), ("日", "sun, day", "NICHI, JITSU", "hi, ka"),
    ("入", "enter", "NYŪ", "i(ru), hai(ru)"), ("年", "year", "NEN", "toshi"),
    ("白", "white", "HAKU", "shiro"), ("八", "eight", "HACHI", "ya(ttsu)"),
    ("百", "hundred", "HYAKU", ""), ("文", "writing", "BUN, MON", "fumi"),
    ("木", "tree", "BOKU, MOKU", "ki"), ("本", "book, origin", "HON", "moto"),
    ("名", "name", "MEI, MYŌ", "na"), ("目", "eye", "MOKU", "me"),
    ("立", "stand", "RITSU", "ta(tsu)"), ("力", "power", "RYOKU, RIKI", "chikara"),
    ("林", "grove", "RIN", "hayashi"), ("六", "six", "ROKU", "mu(ttsu)"),
    # some well-loved others
    ("夢", "dream", "MU", "yume"), ("愛", "love", "AI", ""),
    ("龍", "dragon", "RYŪ", "tatsu"), ("道", "way, road", "DŌ", "michi"),
    ("心", "heart", "SHIN", "kokoro"), ("風", "wind", "FŪ", "kaze"),
    ("光", "light", "KŌ", "hikari"), ("海", "sea", "KAI", "umi"),
    ("春", "spring", "SHUN", "haru"), ("夏", "summer", "KA", "natsu"),
    ("秋", "autumn", "SHŪ", "aki"), ("冬", "winter", "TŌ", "fuyu"),
    ("雪", "snow", "SETSU", "yuki"), ("星", "star", "SEI", "hoshi"),
    ("鳥", "bird", "CHŌ", "tori"), ("魚", "fish", "GYO", "sakana"),
    ("馬", "horse", "BA", "uma"), ("和", "harmony", "WA", ""),
    ("美", "beauty", "BI", "utsuku(shii)"), ("武", "martial", "BU, MU", ""),
    ("刀", "sword", "TŌ", "katana"), ("城", "castle", "JŌ", "shiro"),
    ("寺", "temple", "JI", "tera"), ("侍", "samurai", "JI", "samurai"),
    ("禅", "zen", "ZEN", ""), ("茶", "tea", "CHA, SA", ""),
    ("書", "write", "SHO", "ka(ku)"), ("言", "say, word", "GEN, GON", "i(u)"),
    ("花", "flower", "KA", "hana"), ("桜", "cherry tree", "Ō", "sakura"),
    ("松", "pine", "SHŌ", "matsu"), ("竜", "dragon", "RYŪ", "tatsu"),
]
# drop the duplicate 花 kept above for readability of the list
_seen = set()
KANJI = [k for k in KANJI if not (k[0] in _seen or _seen.add(k[0]))]

# ======================================================================
#  KANJIVG FILES
# ======================================================================
def kanjivg_svg(ch):
    """The KanjiVG SVG text for ch: local copy, cache, or GitHub."""
    name = f"{ord(ch):05x}.svg"
    for folder in (KANJIVG_DIR, CACHE_DIR):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
    req = urllib.request.Request(KANJIVG_URL.format(ord(ch)),
                                 headers={"User-Agent": "eink-kanji/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8")
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, name), "w", encoding="utf-8") as f:
        f.write(text)
    return text

def parse_kanjivg(svg):
    """Strokes (list of path 'd' strings, in order) and number positions."""
    strokes = re.findall(r'<path[^>]*\sd="([^"]+)"', svg)
    numbers = [(float(x), float(y), int(n)) for x, y, n in
               re.findall(r'matrix\(1 0 0 1 ([\d.]+) ([\d.]+)\)">(\d+)<', svg)]
    return strokes, numbers

# ---------------------------------------------------------------- SVG paths
def path_points(d, steps=12):
    """Flatten an SVG path (M L H V C S Q T Z, absolute and relative) into
    a list of polylines in the 109 x 109 KanjiVG coordinate space."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtZz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    lines, cur = [], []
    x = y = sx = sy = 0.0
    last_ctrl = None
    cmd = None
    i = 0

    def num():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    def cubic(p0, p1, p2, p3):
        return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
                for t in [k / steps for k in range(1, steps + 1)]]

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                cur.append((sx, sy))
                x, y = sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            if cur:
                lines.append(cur)
            cur = [(x, y)]
            sx, sy = x, y
            cmd = "l" if rel else "L"          # extra pairs are line-tos
            last_ctrl = None
        elif c == "L":
            nx, ny = num(), num()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            cur.append((x, y))
            last_ctrl = None
        elif c == "H":
            nx = num()
            x = x + nx if rel else nx
            cur.append((x, y))
            last_ctrl = None
        elif c == "V":
            ny = num()
            y = y + ny if rel else ny
            cur.append((x, y))
            last_ctrl = None
        elif c in "CS":
            if c == "C":
                x1, y1 = num(), num()
                if rel:
                    x1, y1 = x + x1, y + y1
            else:                                   # reflect the previous control point
                x1, y1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
            x2, y2, nx, ny = num(), num(), num(), num()
            if rel:
                x2, y2, nx, ny = x + x2, y + y2, x + nx, y + ny
            cur += cubic((x, y), (x1, y1), (x2, y2), (nx, ny))
            last_ctrl = (x2, y2)
            x, y = nx, ny
        elif c in "QT":
            if c == "Q":
                qx, qy = num(), num()
                if rel:
                    qx, qy = x + qx, y + qy
            else:
                qx, qy = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
            nx, ny = num(), num()
            if rel:
                nx, ny = x + nx, y + ny
            # quadratic as cubic
            c1 = (x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y))
            c2 = (nx + 2 / 3 * (qx - nx), ny + 2 / 3 * (qy - ny))
            cur += cubic((x, y), c1, c2, (nx, ny))
            last_ctrl = (qx, qy)
            x, y = nx, ny
        else:
            i += 1                                  # unknown token: skip
    if cur:
        lines.append(cur)
    return lines

# ======================================================================
#  DRAWING
# ======================================================================
def draw_kanji(strokes, size, width_units=4.0, highlight=None, upto=None):
    """Render strokes into (black, red) masks of size x size.
    highlight: index of a stroke drawn in red; upto: draw strokes [0..upto]."""
    S = size * SUPER
    k = S / 109.0
    canvas = Image.new("L", (S, S), 0)        # 0 paper, 1 black, 2 red
    d = ImageDraw.Draw(canvas)
    w = max(1, int(width_units * k))
    last = len(strokes) - 1 if upto is None else upto
    for n, sd in enumerate(strokes[:last + 1]):
        ink = 2 if n == highlight else 1
        for line in path_points(sd):
            pts = [(px * k, py * k) for px, py in line]
            if len(pts) > 1:
                d.line(pts, fill=ink, width=w, joint="curve")
            for px, py in (pts[0], pts[-1]):           # round caps
                d.ellipse((px - w / 2, py - w / 2, px + w / 2, py + w / 2), fill=ink)
    def layer(v):
        m = canvas.point(lambda p: 255 if p == v else 0).resize((size, size), Image.BOX)
        return m.point(lambda p: 255 if p > 100 else 0)
    return layer(1), layer(2)

def frame_box(draw, x, y, size):
    """Practice-square guide: thin frame with dotted centre lines."""
    draw.rectangle((x, y, x + size - 1, y + size - 1), outline=0)
    for t in range(0, size, 3):
        draw.point((x + size // 2, y + t), fill=0)
        draw.point((x + t, y + size // 2), fill=0)

def compose(entry, strokes, numbers, layout="study", show_numbers=True):
    ch, meaning, on, kun = entry
    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)
    n = len(strokes)

    # title bar: meaning and stroke count
    db.rectangle((0, 0, WIDTH - 1, 11), fill=0)
    pixelfont.text(db, 3, 2, pixelfont.wrap(meaning, 110, 1)[0], fill=1)
    count = f"{n} stroke{'s' if n != 1 else ''}"
    pixelfont.text(db, WIDTH - 3 - pixelfont.width(count), 2, count, fill=1)

    big = 140 if layout == "study" else 168
    bx = (WIDTH - big) // 2
    by = 15 if layout == "study" else 22
    frame_box(db, bx, by, big)
    kb, kr = draw_kanji(strokes, big, width_units=4.2)
    black.paste(0, (bx, by), kb)
    if show_numbers:
        k = big / 109.0
        for x, y, num in numbers:
            s = str(num)
            tx = int(bx + x * k)
            ty = int(by + y * k) - 7
            tx = max(bx + 1, min(bx + big - pixelfont.width(s) - 1, tx))
            ty = max(by + 1, min(by + big - 9, ty))
            pixelfont.text(dr, tx, ty, s, fill=0)
        # where a red digit crosses a stroke, the digit wins (only its own pixels)
        black.paste(1, (0, 0), red.convert("L").point(lambda v: 255 if v == 0 else 0))

    y = by + big + 3
    readings = []
    if on:
        readings.append(f"on {on}")
    if kun:
        readings.append(f"kun {kun}")
    for ln in pixelfont.wrap("   ".join(readings), WIDTH - 6, 2):
        pixelfont.text_centered(db, WIDTH / 2, y, ln)
        y += pixelfont.LINE_H

    if layout == "study":
        # stroke by stroke: each square adds one stroke, newest in red
        y += 2
        cell = 40
        per_row = WIDTH // (cell + 2)
        rows = max(1, (HEIGHT - y) // (cell + 2))
        slots = per_row * rows
        steps = list(range(n))
        if n > slots:                       # too many strokes: sample, keep the last
            steps = [round(i * (n - 1) / (slots - 1)) for i in range(slots)]
        x0 = (WIDTH - per_row * (cell + 2) + 2) // 2
        for j, s in enumerate(steps):
            cx = x0 + (j % per_row) * (cell + 2)
            cy = y + (j // per_row) * (cell + 2)
            frame_box(db, cx, cy, cell)
            mb, mr = draw_kanji(strokes, cell, width_units=6.0, highlight=s, upto=s)
            black.paste(0, (cx, cy), mb)
            red.paste(0, (cx, cy), mr)
            black.paste(1, (cx, cy), mr)
    return black, red

def save_preview(black, red, filename):
    p = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    p.paste((0, 0, 0), mask=black.convert("L").point(lambda v: 255 - v))
    p.paste((200, 0, 0), mask=red.convert("L").point(lambda v: 255 - v))
    p.save(filename)

# ======================================================================
#  CHOOSING
# ======================================================================
def next_entry(order):
    if order == "list":
        path = os.path.join(CACHE_DIR, "position.json")
        try:
            with open(path) as f:
                i = json.load(f).get("index", -1) + 1
        except (OSError, ValueError):
            i = 0
        i %= len(KANJI)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"index": i}, f)
        return KANJI[i]
    return random.choice(KANJI)

def pick(order):
    for _ in range(6):
        entry = next_entry(order)
        try:
            strokes, numbers = parse_kanjivg(kanjivg_svg(entry[0]))
            if strokes:
                return entry, strokes, numbers
        except Exception as e:
            print(f"  {entry[0]}: {e}")
    # offline: anything already in the cache
    cached = [k for k in KANJI if os.path.exists(os.path.join(CACHE_DIR, f"{ord(k[0]):05x}.svg"))]
    if cached:
        entry = random.choice(cached)
        return (entry,) + parse_kanjivg(kanjivg_svg(entry[0]))
    return None

# ======================================================================
#  HARDWARE
# ======================================================================
def open_display():
    try:
        from waveshare_epd import epd2in7b as driver
    except ImportError:
        try:
            from waveshare_epd import epd2in7b_V2 as driver
        except ImportError:
            return None, None
    return driver, driver.EPD()

def show(epd, black, red):
    epd.init()
    epd.display(epd.getbuffer(black), epd.getbuffer(red))
    epd.sleep()

class Controller:
    def __init__(self):
        self.order = ORDER
        self.layout = LAYOUT
        self.numbers = SHOW_NUMBERS
        self.action = "next"
        self.wake = threading.Event()
        self.busy = False

    def press(self, action):
        if not self.busy:
            self.action = action
            self.wake.set()

def setup_buttons(ctl):
    try:
        from gpiozero import Button
    except ImportError:
        print("gpiozero not available: buttons disabled")
        return []
    out = []
    for pin, act in zip(BUTTON_PINS, ["next", "order", "layout", "numbers"]):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda a=act: ctl.press(a))
            out.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return out

def main():
    if "--preview" in sys.argv:
        arg = sys.argv[sys.argv.index("--preview") + 1] if len(sys.argv) > 2 else None
        entry = next((k for k in KANJI if k[0] == arg), None) or random.choice(KANJI)
        strokes, numbers = parse_kanjivg(kanjivg_svg(entry[0]))
        for lay in ("study", "big"):
            b, r = compose(entry, strokes, numbers, lay)
            save_preview(b, r, f"kanji_{lay}.png")
        print("kanji_study.png, kanji_big.png:", entry)
        return

    driver, epd = open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    current = None
    prefetched = {}

    def prefetch(order):
        got = pick(order)
        if got:
            prefetched.update(item=got, order=order)

    try:
        while True:
            act, ctl.action = ctl.action, None
            ctl.busy = True
            try:
                if act == "order":
                    ctl.order = "list" if ctl.order == "random" else "random"
                    print("order:", ctl.order)
                elif act == "layout":
                    ctl.layout = "big" if ctl.layout == "study" else "study"
                elif act == "numbers":
                    ctl.numbers = not ctl.numbers
                if act in ("next", "order", None) or current is None:
                    got = None
                    if act != "order" and prefetched.get("item") and prefetched.get("order") == ctl.order:
                        got = prefetched["item"]
                    prefetched.clear()
                    current = got or pick(ctl.order) or current
                if current:
                    threading.Thread(target=prefetch, args=(ctl.order,), daemon=True).start()
                    entry, strokes, numbers = current
                    print(f"showing: {entry[0]} {entry[1]} ({len(strokes)} strokes)")
                    black, red = compose(entry, strokes, numbers, ctl.layout, ctl.numbers)
                    save_preview(black, red, os.path.join(HERE, "last_kanji.png"))
                    show(epd, black, red)
            except Exception as e:
                print(f"error: {e}")
            finally:
                ctl.busy = False
                ctl.wake.clear()
            ctl.wake.wait(timeout=REFRESH_SECONDS)
    except KeyboardInterrupt:
        print("Exiting cleanly...")
        epd.init()
        epd.Clear()
        epd.sleep()
    finally:
        driver.epdconfig.module_exit()

if __name__ == "__main__":
    main()
