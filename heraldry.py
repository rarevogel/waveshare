#!/usr/bin/env python3
"""
Coats of arms on a Waveshare 2.7" e-Paper HAT (B), black / white / red.

Fetches a random coat of arms from Wikimedia Commons (vector drawings,
rendered to PNG by Commons itself), recognises the heraldic tinctures,
and draws them the way engravers did before colour printing, using the
Petra Sancta hatching system - so no dithering:

    gules   (red)     real red on this panel  (or vertical lines, KEY4)
    azure   (blue)    horizontal lines
    vert    (green)   diagonal lines, top left to bottom right
    purpure (purple)  diagonal lines, top right to bottom left
    or      (gold)    dots
    argent  (silver)  plain white
    sable   (black)   black; large black fields cross-hatched
    tenne   (orange)  diagonal + horizontal lines

The name of the arms is shown on top; the description from Commons (often
the official blazon) underneath, when there is room.

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next coat of arms
  KEY2  next collection (Dutch municipalities -> Dutch arms -> worldwide)
  KEY3  description on / off
  KEY4  gules as red / gules as vertical hatching

Wikimedia asks every program to identify itself: put your e-mail in CONTACT.

Run on a PC:
  python3 heraldry.py --preview              # fetch one, save PNG
  python3 heraldry.py --image arms.png       # convert a local image
"""
import html
import json
import os
import random
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font (pixelfont.py)

# ---------------------------------------------------------------- settings
REFRESH_MINUTES = 30                 # Waveshare: at least 3 min between refreshes
CONTACT = "your-email@example.com"   # Wikimedia's User-Agent policy asks for this
SHOW_DESCRIPTION = True
GULES_AS_RED = True                  # False: traditional vertical hatching
BUTTON_PINS = (5, 6, 13, 19)
CACHE_DIR = os.path.join(HERE, "arms_cache")
CACHE_KEEP = 80

COLLECTIONS = [
    ("Dutch municipalities", ("category", "SVG coats of arms of municipalities of the Netherlands")),
    # Dutch arms on Commons are named "<place> wapen.svg"; searching the title
    # only avoids foreign arms whose pages merely carry a Dutch translation
    ("Dutch arms",           ("search", "intitle:wapen filemime:image/svg+xml")),
    ("Worldwide",            ("search", '"coat of arms" filemime:image/svg+xml')),
]

WIDTH, HEIGHT = 176, 264
API = "https://commons.wikimedia.org/w/api.php"
UA = f"EinkHeraldry/1.0 ({CONTACT}) Python-urllib"

# ======================================================================
#  WIKIMEDIA COMMONS
# ======================================================================
def get_json(params):
    params = dict(params, format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|extmetadata|size",
             "iiurlwidth": "600", "iiextmetadatafilter": "ImageDescription|ObjectName",
             "iiextmetadatalanguage": "nl"}

def candidates_from_category(cat):
    letter = random.choice("ABCDEFGHIJKLMNOPRSTVWZ")
    data = get_json(dict(IMAGEINFO, action="query", generator="categorymembers",
                         gcmtitle=f"Category:{cat}", gcmtype="file", gcmlimit="40",
                         gcmstartsortkeyprefix=letter))
    pages = data.get("query", {}).get("pages", [])
    if not pages:                    # prefix past the end: start from the top
        data = get_json(dict(IMAGEINFO, action="query", generator="categorymembers",
                             gcmtitle=f"Category:{cat}", gcmtype="file", gcmlimit="40"))
        pages = data.get("query", {}).get("pages", [])
    return pages

def candidates_from_search(query):
    """Search File: pages, starting at a random point inside the results."""
    info = get_json({"action": "query", "list": "search", "srsearch": query,
                     "srnamespace": "6", "srlimit": "1", "srinfo": "totalhits"})
    total = info.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
    if total == 0:
        return []
    # the search API stops at 10,000 results
    offset = random.randint(0, max(0, min(total, 10000) - 40))
    data = get_json(dict(IMAGEINFO, action="query", generator="search",
                         gsrsearch=query, gsrnamespace="6", gsrlimit="40",
                         gsroffset=str(offset)))
    return data.get("query", {}).get("pages", [])

def fetch_arms(collection):
    kind, what = COLLECTIONS[collection][1]
    pages = candidates_from_category(what) if kind == "category" else candidates_from_search(what)
    pages = [p for p in pages if p.get("title", "").lower().endswith(".svg")
             and p.get("imageinfo") and p["imageinfo"][0].get("thumburl")]
    if not pages:
        return None
    p = random.choice(pages)
    info = p["imageinfo"][0]
    raw = get_bytes(info["thumburl"])
    meta = {"id": re.sub(r"[^A-Za-z0-9_-]+", "_", p["title"])[:80],
            "title": p["title"],
            "name": arms_name(p["title"], info.get("extmetadata", {})),
            "description": description(info.get("extmetadata", {}), p["title"]),
            "collection": COLLECTIONS[collection][0]}
    save_cache(raw, meta)
    return Image.open(BytesIO(raw)), meta

# ---------------------------------------------------------------- text
def ascii_text(s):
    """The pixel font is ASCII: turn é -> e, ë -> e, ĳ -> ij and so on."""
    s = s.replace("ĳ", "ij").replace("Ĳ", "IJ")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if ord(c) < 128)

def strip_html(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def arms_name(title, ext):
    base = re.sub(r"^File:", "", title)
    base = re.sub(r"\.svg$", "", base, flags=re.I).replace("_", " ")
    m = re.match(r"(.+?)\s+wapen$", base, flags=re.I)
    if m:
        return ascii_text(f"Wapen van {m.group(1)}")
    obj = strip_html((ext.get("ObjectName") or {}).get("value", ""))
    return ascii_text(obj or base)

def description(ext, title):
    d = strip_html((ext.get("ImageDescription") or {}).get("value", ""))
    d = ascii_text(d)
    # prefer the blazon if the description contains one
    m = re.search(r"(Blazoen|Blazon|Beschrijving)\s*:?\s*(.+)", d, flags=re.I)
    if m:
        d = m.group(2)
    if len(d) < 12 or d.lower() in title.lower():
        return ""
    return d

# ---------------------------------------------------------------- cache
def save_cache(raw, meta):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, meta["id"] + ".png"), "wb") as f:
        f.write(raw)
    with open(os.path.join(CACHE_DIR, meta["id"] + ".json"), "w") as f:
        json.dump(meta, f)
    files = sorted((os.path.getmtime(os.path.join(CACHE_DIR, n)), n)
                   for n in os.listdir(CACHE_DIR) if n.endswith(".png"))
    for _, n in files[:-CACHE_KEEP]:
        for ext in (".png", ".json"):
            try:
                os.remove(os.path.join(CACHE_DIR, n[:-4] + ext))
            except OSError:
                pass

def from_cache(exclude=None, collection_name=None):
    """A cached coat of arms, from the given collection if there is one."""
    if not os.path.isdir(CACHE_DIR):
        return None
    entries = []
    for fn in os.listdir(CACHE_DIR):
        if not fn.endswith(".png") or fn[:-4] == exclude:
            continue
        n = fn[:-4]
        try:
            with open(os.path.join(CACHE_DIR, n + ".json")) as f:
                meta = json.load(f)
        except (OSError, ValueError):
            meta = {"id": n, "name": n, "description": ""}
        entries.append((n, meta))
    same = [e for e in entries if e[1].get("collection") == collection_name]
    pool = same or entries
    if not pool:
        return None
    n, meta = random.choice(pool)
    return Image.open(os.path.join(CACHE_DIR, n + ".png")), meta

# ======================================================================
#  TINCTURES AND HATCHING
# ======================================================================
NONE, ARGENT, OR, GULES, AZURE, VERT, PURPURE, SABLE, TENNE = range(9)

def classify(rgba):
    """One tincture per pixel, from hue / saturation / brightness."""
    rgba = rgba.convert("RGBA")
    w, h = rgba.size
    hsv = rgba.convert("RGB").convert("HSV")
    hp, sp, vp = [b.load() for b in hsv.split()]
    ap = rgba.split()[3].load()
    out = Image.new("L", (w, h), NONE)
    op = out.load()
    for y in range(h):
        for x in range(w):
            if ap[x, y] < 128:
                continue
            hh = hp[x, y] * 360 / 255
            s, v = sp[x, y] / 255, vp[x, y]
            if v < 70:
                t = SABLE
            elif s < 0.22:
                t = SABLE if v < 105 else ARGENT
            elif hh < 15 or hh >= 335:
                t = GULES
            elif hh < 40:
                if s < 0.45 and v > 170:
                    t = ARGENT                       # carnation (skin): plain
                elif v > 175 and s > 0.5:
                    t = OR                           # deep gold
                else:
                    t = TENNE                        # orange-brown
            elif hh < 70:
                t = OR
            elif hh < 170:
                t = VERT
            elif hh < 260:
                t = AZURE
            else:
                t = PURPURE
            op[x, y] = t
    # remove anti-aliasing specks: most common tincture in each 3x3 block
    return out.filter(ImageFilter.ModeFilter(3))

def hatch(t, x, y, step=3):
    """Is pixel (x, y) inked in the hatching pattern of tincture t?"""
    if t == AZURE:
        return y % step == 0
    if t == VERT:
        return (x - y) % (step + 1) == 0
    if t == PURPURE:
        return (x + y) % (step + 1) == 0
    if t == OR:
        return (y % 2 == 0) and ((x + y // 2) % 3 == 0)    # dense enough for small charges
    if t == TENNE:
        return (x + y) % (step + 1) == 0 or y % (step + 1) == 0
    if t == GULES:
        return x % step == 0
    return False

def render_arms(img, box, gules_red=True):
    """Draw the arms into box on new (black, red) layers."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    img = img.convert("RGBA")
    k = min(bw / img.width, bh / img.height)
    w, h = max(1, int(img.width * k)), max(1, int(img.height * k))
    small = img.resize((w, h), Image.LANCZOS)
    tinct = classify(small)
    tp = tinct.load()
    # large black fields get cross-hatched; thin black lines stay solid
    sable = tinct.point(lambda v: 255 if v == SABLE else 0)
    big_sable = sable.filter(ImageFilter.MinFilter(7)).load()

    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    bp, rp = black.load(), red.load()
    ox, oy = x0 + (bw - w) // 2, y0 + (bh - h) // 2
    for y in range(h):
        for x in range(w):
            t = tp[x, y]
            if t == NONE:
                continue
            X, Y = ox + x, oy + y
            # outline wherever the tincture changes (or the arms end)
            edge = False
            for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                nx, ny = x + dx, y + dy
                nt = tp[nx, ny] if 0 <= nx < w and 0 <= ny < h else NONE
                if nt != t and not (dx < 0 or dy < 0) or nt == NONE:
                    edge = True
                    break
            if edge:
                bp[X, Y] = 0
            elif t == SABLE:
                if big_sable[x, y]:
                    if X % 3 == 0 or Y % 3 == 0:
                        bp[X, Y] = 0
                else:
                    bp[X, Y] = 0
            elif t == GULES and gules_red:
                rp[X, Y] = 0
            elif hatch(t, X, Y):
                bp[X, Y] = 0
    return black, red, (ox, oy, ox + w, oy + h)

# ======================================================================
#  SCREEN
# ======================================================================
def compose(img, meta, show_desc=True, gules_red=True):
    name_lines = pixelfont.wrap(meta.get("name") or "", WIDTH - 6, 2)
    top = pixelfont.LINE_H * len(name_lines) + 3
    desc = meta.get("description", "") if show_desc else ""
    desc_lines = pixelfont.wrap(desc, WIDTH - 6, 9) if desc else []
    bottom = HEIGHT - (pixelfont.LINE_H * len(desc_lines) + 4 if desc_lines else 2)
    black, red, (ax0, ay0, ax1, ay1) = render_arms(img, (4, top + 4, WIDTH - 4, bottom - 3),
                                                   gules_red)
    db = ImageDraw.Draw(black)
    db.rectangle((0, 0, WIDTH - 1, top - 1), fill=0)            # title bar
    y = 2
    for ln in name_lines:
        pixelfont.text_centered(db, WIDTH / 2, y, ln, fill=1)
        y += pixelfont.LINE_H
    y = bottom + 2
    for ln in desc_lines:
        pixelfont.text_centered(db, WIDTH / 2, y, ln, fill=0)
        y += pixelfont.LINE_H
    return black, red

def save_preview(black, red, filename):
    p = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    p.paste((0, 0, 0), mask=black.convert("L").point(lambda v: 255 - v))
    p.paste((200, 0, 0), mask=red.convert("L").point(lambda v: 255 - v))
    p.save(filename)

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
        self.collection = 0
        self.show_desc = SHOW_DESCRIPTION
        self.gules_red = GULES_AS_RED
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
    for pin, act in zip(BUTTON_PINS, ["next", "collection", "desc", "gules"]):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda a=act: ctl.press(a))
            out.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return out

def pick(collection, current_id=None):
    """Fetch from the chosen collection only. If that fails, fall back to a
    cached coat of arms from the same collection - never to another one."""
    name = COLLECTIONS[collection][0]
    for attempt in range(4):
        try:
            got = fetch_arms(collection)
            if got:
                return got
            print(f"  {name}: no usable result, trying again")
        except Exception as e:
            print(f"  {name}: fetch failed: {e}")
        time.sleep(2)
    print(f"  {name}: offline or no result, using the cache")
    return from_cache(exclude=current_id, collection_name=name)

def main():
    if "--image" in sys.argv:
        path = sys.argv[sys.argv.index("--image") + 1]
        b, r = compose(Image.open(path), {"name": os.path.basename(path), "description": ""})
        save_preview(b, r, "arms_preview.png")
        print("arms_preview.png")
        return
    if "--preview" in sys.argv:
        got = pick(0)
        if got:
            b, r = compose(*got)
            save_preview(b, r, "arms_preview.png")
            print("arms_preview.png:", got[1]["name"])
        return

    driver, epd = open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview or --image on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    current = None
    try:
        while True:
            act, ctl.action = ctl.action, None
            ctl.busy = True
            try:
                if act == "collection":
                    ctl.collection = (ctl.collection + 1) % len(COLLECTIONS)
                    print("collection:", COLLECTIONS[ctl.collection][0])
                elif act == "desc":
                    ctl.show_desc = not ctl.show_desc
                elif act == "gules":
                    ctl.gules_red = not ctl.gules_red
                if act in ("next", "collection", None) or current is None:
                    got = pick(ctl.collection, current[1]["id"] if current else None)
                    if got:
                        current = got
                if current:
                    img, meta = current
                    print(f"showing: {meta.get('name')}  [{meta.get('collection', '?')}]")
                    black, red = compose(img, meta, ctl.show_desc, ctl.gules_red)
                    save_preview(black, red, os.path.join(HERE, "last_arms.png"))
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
