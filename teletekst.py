#!/usr/bin/env python3
"""
NOS Teletekst on a Waveshare 2.7" e-Paper HAT (B), black / white / red.

Shows real Teletekst pages in landscape (264 x 176): the 40 x 24 teletext
grid in 6 x 7 pixel cells, with a header row (page number, NOS, date, time).

  * text in the crisp 6x8 pixel font (pixelfont.py), mosaic block graphics
    drawn as real 2x3 "sixels" - no dithering anywhere
  * teletext colours mapped to the panel: red/magenta/yellow become red,
    the other colours black; coloured backgrounds become solid black bars
    with the text cut out in white (or red), like inverse video
  * pages rotate every REFRESH_MINUTES: the news index, a couple of news
    stories, then sport and weather, then round again
  * the four HAT buttons are the coloured "fastext" keys of a teletext
    remote: they jump to the four links shown at the bottom of the page
  * last good copy of each page is cached for when the network is down

Run on a PC without the display:
  python3 teletekst.py --preview 101      # fetch page 101, save PNG
"""
import datetime as dt
import html
import json
import os
import random
import re
import sys
import threading
import time
import urllib.request
from html.parser import HTMLParser
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font (pixelfont.py)

# ---------------------------------------------------------------- settings
REFRESH_MINUTES = 5                  # Waveshare: at least 3 min between refreshes
STORIES_PER_SECTION = 2              # linked pages shown after each index page
SECTIONS = [("nieuws", "101"), ("sport", "601"), ("weer", "702")]   # fallbacks
ROTATE_180 = False                   # flip if the text comes out upside down
BUTTON_PINS = (5, 6, 13, 19)         # KEY1..KEY4 on the 2.7" HAT
FEED = "https://teletekst-data.nos.nl/json/{page}"
CACHE_DIR = os.path.join(HERE, "teletekst_cache")
USER_AGENT = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

W, H = 264, 176                      # landscape canvas; the driver rotates it
COLS, ROWS = 40, 24
CELL_W, CELL_H = 6, 7
LEFT = (W - COLS * CELL_W) // 2      # 12 px margin each side
TOP = 1 + CELL_H                     # row 0 is our header row

# teletext colour -> panel ink. "K" black, "R" red, "W" white (paper)
FG_INK = {"white": "K", "yellow": "R", "cyan": "K", "green": "K",
          "blue": "K", "magenta": "R", "red": "R", "black": "K"}
BG_INK = {"black": "W", "blue": "K", "white": "K", "cyan": "K", "green": "K",
          "yellow": "K", "magenta": "K", "red": "R"}
COLOURS = set(FG_INK)

# ======================================================================
#  FETCH + CACHE
# ======================================================================
def fetch_page(page):
    req = urllib.request.Request(FEED.format(page=page), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, f"{page}.json"), "w") as f:
        json.dump(data, f)
    return data, False

def get_page(page):
    """Return (data, from_cache) or (None, True) if nothing is available."""
    try:
        return fetch_page(page)
    except Exception as e:
        print(f"  page {page}: {e}")
        try:
            with open(os.path.join(CACHE_DIR, f"{page}.json")) as f:
                return json.load(f), True
        except (OSError, ValueError):
            return None, True

# ======================================================================
#  PARSING THE PAGE MARKUP
# ======================================================================
class Cell:
    __slots__ = ("ch", "fg", "bg", "mosaic")
    def __init__(self, ch=" ", fg="white", bg="black", mosaic=None):
        self.ch, self.fg, self.bg, self.mosaic = ch, fg, bg, mosaic

def _colours(cls):
    fg, bg = None, None
    for c in (cls or "").split():
        c = c.strip()
        if c.startswith("bg-") and c[3:] in COLOURS:
            bg = c[3:]
        elif c in COLOURS:
            fg = c
    return fg, bg

class TeletextParser(HTMLParser):
    """Walks the span/anchor markup and fills a 40 x 24 grid of cells."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.rows = [[]]
        self.stack = []              # (fg, bg) of open span / a elements
        self.links = []

    def style(self):
        fg, bg = "white", "black"
        for f, b in self.stack:
            fg = f or fg
            bg = b or bg
        return fg, bg

    def handle_starttag(self, tag, attrs):
        if tag in ("span", "a"):
            a = dict(attrs)
            fg, bg = _colours(a.get("class"))
            self.stack.append((fg, bg))
            href = a.get("href") or ""
            m = re.match(r"#(\d{3}(?:-\d+)?)$", href)
            if tag == "a" and m:
                self.links.append(m.group(1))

    def handle_endtag(self, tag):
        if tag in ("span", "a") and self.stack:
            self.stack.pop()

    def put(self, ch, mosaic=None):
        fg, bg = self.style()
        self.rows[-1].append(Cell(ch, fg, bg, mosaic))

    def handle_data(self, data):
        for ch in data:
            if ch == "\n":
                self.rows.append([])
            elif ch != "\r":
                self.put(ch)

    def handle_charref(self, name):
        code = int(name[1:], 16) if name[:1] in "xX" else int(name)
        if 0xF020 <= code <= 0xF07F:
            c = code - 0xF000
            if 0x40 <= c <= 0x5F:            # capital letters "blast through"
                self.put(chr(c))
            else:                            # 2x3 mosaic block
                self.put(" ", mosaic=(c & 0x1F) | ((c & 0x40) >> 1))
        else:
            self.put(chr(code))

    def handle_entityref(self, name):
        self.put(html.unescape(f"&{name};"))

def parse(content):
    p = TeletextParser()
    p.feed(content)
    rows = [r for r in p.rows]
    # drop a leading empty line produced by a newline at the very start
    while rows and not rows[0]:
        rows.pop(0)
    return rows[:ROWS], p.links

# ======================================================================
#  DRAWING
# ======================================================================
class Canvas:
    def __init__(self):
        self.black = Image.new("1", (W, H), 1)
        self.red = Image.new("1", (W, H), 1)
        self.db = ImageDraw.Draw(self.black)
        self.dr = ImageDraw.Draw(self.red)

    def rect(self, box, ink):
        if ink == "K":
            self.db.rectangle(box, fill=0)
            self.dr.rectangle(box, fill=1)
        elif ink == "R":
            self.dr.rectangle(box, fill=0)
            self.db.rectangle(box, fill=1)
        else:
            self.db.rectangle(box, fill=1)
            self.dr.rectangle(box, fill=1)

    def text(self, x, y, s, ink):
        layers = {"K": (self.db, self.dr), "R": (self.dr, self.db), "W": (None, None)}
        on, off = layers[ink]
        if ink == "W":
            pixelfont.text(self.db, x, y, s, fill=1)
            pixelfont.text(self.dr, x, y, s, fill=1)
        else:
            pixelfont.text(off, x, y, s, fill=1)
            pixelfont.text(on, x, y, s, fill=0)

def cell_inks(cell):
    bg = BG_INK.get(cell.bg, "W")
    fg = FG_INK.get(cell.fg, "K")
    if bg == "K" and fg == "K":
        fg = "W"                     # text on a coloured bar: cut out in white
    if bg == "R" and fg == "R":
        fg = "W"
    return fg, bg

def draw_mosaic(cv, x, y, bits, ink):
    # 2 columns x 3 rows of sixels; rows split 7 px as 2/3/2
    ys = [(0, 2), (2, 5), (5, 7)]
    for i in range(6):
        if bits & (1 << i):
            col, row = i % 2, i // 2
            y0, y1 = ys[row]
            cv.rect((x + col * 3, y + y0, x + col * 3 + 2, y + y1 - 1), ink)

def draw_page(rows, page, from_cache=False):
    cv = Canvas()
    # header row: page number, NOS, Dutch date and time
    now = dt.datetime.now()
    days = ["ma", "di", "wo", "do", "vr", "za", "zo"]
    months = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    left = f"P{page}"
    right = f"{days[now.weekday()]} {now.day:2d} {months[now.month - 1]} {now:%H:%M}"
    mid = "NOS" + (" *" if from_cache else "")
    cv.text(LEFT, 1, left, "R")
    cv.text(LEFT + 9 * CELL_W, 1, mid, "K")
    cv.text(LEFT + COLS * CELL_W - pixelfont.width(right), 1, right, "K")

    for r, row in enumerate(rows):
        y = TOP + r * CELL_H
        for c, cell in enumerate(row[:COLS]):
            x = LEFT + c * CELL_W
            fg, bg = cell_inks(cell)
            if bg != "W":
                cv.rect((x, y, x + CELL_W - 1, y + CELL_H - 1), bg)
            if cell.mosaic:
                draw_mosaic(cv, x, y, cell.mosaic, fg)
            elif cell.ch.strip():
                cv.text(x, y, cell.ch, fg)
        # a coloured bar runs on to the right edge if the row ends inside it
        if row and BG_INK.get(row[-1].bg, "W") != "W" and len(row) < COLS:
            bg = BG_INK[row[-1].bg]
            x0 = LEFT + len(row) * CELL_W
            cv.rect((x0, y, LEFT + COLS * CELL_W - 1, y + CELL_H - 1), bg)

    black, red = cv.black, cv.red
    if ROTATE_180:
        black, red = black.rotate(180), red.rotate(180)
    return black, red

def error_page(page):
    cv = Canvas()
    cv.text(LEFT, 1, f"P{page}", "R")
    cv.rect((LEFT, TOP + 9 * CELL_H, LEFT + COLS * CELL_W - 1, TOP + 12 * CELL_H), "K")
    msg = "Pagina niet beschikbaar"
    cv.text((W - pixelfont.width(msg)) / 2, TOP + 10 * CELL_H, msg, "W")
    return cv.black, cv.red

def save_preview(black, red, filename):
    p = Image.new("RGB", black.size, (255, 255, 255))
    p.paste((0, 0, 0), mask=black.convert("L").point(lambda v: 255 - v))
    p.paste((200, 0, 0), mask=red.convert("L").point(lambda v: 255 - v))
    p.save(filename)

# ======================================================================
#  WHAT TO SHOW NEXT
# ======================================================================
def news_links(links, section_page):
    """Links on an index page that lead to stories (not the fastext/menu)."""
    base = int(section_page[:1])
    out = []
    for l in links:
        p = l.split("-")[0]
        if p != section_page and p[:1] == str(base) and p not in out:
            out.append(p)
    return out

def build_queue():
    sections = list(SECTIONS)
    data, _ = get_page("100")
    if data:
        found = {f.get("title", "").lower(): f.get("page") for f in data.get("fastTextLinks", [])}
        sections = [(name, found.get(name) or page) for name, page in SECTIONS]
    queue = []
    for name, page in sections:
        queue.append(page)
        idx, _ = get_page(page)
        if idx:
            _, links = parse(idx.get("content", ""))
            stories = news_links(links, page)
            queue += random.sample(stories, min(STORIES_PER_SECTION, len(stories)))
    return queue

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
    epd.display(epd.getbuffer(black), epd.getbuffer(red))   # landscape is rotated by getbuffer
    epd.sleep()

class Controller:
    def __init__(self):
        self.wake = threading.Event()
        self.jump = None
        self.busy = False
        self.fastext = []

    def press(self, i):
        if self.busy or i >= len(self.fastext):
            return
        self.jump = self.fastext[i]
        self.wake.set()

def setup_buttons(ctl):
    try:
        from gpiozero import Button
    except ImportError:
        print("gpiozero not available: buttons disabled")
        return []
    buttons = []
    for i, pin in enumerate(BUTTON_PINS):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda k=i: ctl.press(k))
            buttons.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return buttons

def render(page):
    data, cached = get_page(page)
    if not data:
        return error_page(page), []
    rows, _ = parse(data.get("content", ""))
    fast = [f.get("page") for f in data.get("fastTextLinks", []) if f.get("page")]
    return draw_page(rows, page, cached), fast

def main():
    if "--preview" in sys.argv:
        page = sys.argv[sys.argv.index("--preview") + 1] if len(sys.argv) > 2 else "101"
        (black, red), fast = render(page)
        save_preview(black, red, f"teletekst_{page}.png")
        print(f"teletekst_{page}.png  fastext: {fast}")
        return

    driver, epd = open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    queue = []
    try:
        while True:
            ctl.busy = True
            try:
                if ctl.jump:
                    page, ctl.jump = ctl.jump, None
                else:
                    if not queue:
                        queue = build_queue()
                    page = queue.pop(0) if queue else "101"
                print(f"showing page {page}")
                (black, red), ctl.fastext = render(page)
                save_preview(black, red, os.path.join(HERE, "last_teletekst.png"))
                show(epd, black, red)
            except Exception as e:
                print(f"error: {e}")
            finally:
                ctl.busy = False
                ctl.wake.clear()
            ctl.wake.wait(timeout=max(180, REFRESH_MINUTES * 60))
    except KeyboardInterrupt:
        print("Exiting cleanly...")
        epd.init()
        epd.Clear()
        epd.sleep()
    finally:
        driver.epdconfig.module_exit()

if __name__ == "__main__":
    main()
