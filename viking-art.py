#!/usr/bin/env python3
"""
Viking art on a Waveshare 2.7" e-Paper HAT (B), black / white / red.

Shows Viking-age animal ornament and runestone drawings from Wikimedia
Commons as crisp 1-bit art, like the kamon program: dragons, serpents,
gripping beasts and runestone snake-bands, with the art style and its
period in the caption.

Collections (KEY2):
  Mixed (all styles)        Borre style       c. 850-950
  Oseberg style c. 775-850  Jelling style     c. 900-975
  Mammen style  c. 950-1000 Ringerike style   c. 990-1050
  Urnes style   c. 1050-1125
  Runestone drawings

Vector drawings are used first. Scanned drawings and engravings are only
accepted when they really are line art (mostly paper and ink, few grey
tones) - museum photographs are skipped automatically.

Styles (KEY3): mixed -> ink -> red -> inverse

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next image
  KEY2  next collection
  KEY3  style
  KEY4  caption on / off

Needs pixelfont.py next to this script. Put your e-mail in CONTACT:
Wikimedia asks programs to identify themselves.

Run on a PC:
  python3 viking-art.py --preview [collection number]
  python3 viking-art.py --test    # how many hits each search finds
"""
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
from PIL import Image, ImageDraw, ImageOps, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font

# ---------------------------------------------------------------- settings
REFRESH_SECONDS = 5                  # pause after each refresh before the next image
# A full refresh of the 3-colour panel takes ~15 s, so ~20 s per image is
# the real minimum. Waveshare recommends >= 180 s between refreshes for the
# life of the panel when it runs all day.
CONTACT = "your-email@example.com"   # Wikimedia's User-Agent policy asks for this
COLLECTION = 0                       # 0 = mixed
SHOW_CAPTION = True
BUTTON_PINS = (5, 6, 13, 19)
CACHE_DIR = os.path.join(HERE, "viking_cache")
CACHE_KEEP = 120
STYLES = ["mixed", "ink", "red", "inverse"]

def style_queries(name):
    """Search variants for one art style, best first: vector drawings in the
    category, vector drawings mentioning the style, then scanned drawings."""
    return [f'incategory:"{name} style" filetype:drawing',
            f'"{name} style" filetype:drawing',
            f'incategory:"{name} style" filetype:bitmap drawing',
            f'"{name} style" drawing filetype:bitmap',
            f'incategory:"{name} style" filetype:bitmap']

ART_STYLES = [("Oseberg", "c. 775-850"), ("Borre", "c. 850-950"),
              ("Jelling", "c. 900-975"), ("Mammen", "c. 950-1000"),
              ("Ringerike", "c. 990-1050"), ("Urnes", "c. 1050-1125")]

COLLECTIONS = [("Mixed (all styles)", None, None)]
COLLECTIONS += [(f"{n} style", p, style_queries(n)) for n, p in ART_STYLES]
COLLECTIONS += [("Runestone drawings", "c. 950-1100", [
    'incategory:"Drawings of runestones"',
    'runestone drawing filetype:drawing',
    'intitle:runestone filetype:drawing',
    'runsten teckning filetype:bitmap',
    'runestone drawing filetype:bitmap',
])]

WIDTH, HEIGHT = 176, 264
API = "https://commons.wikimedia.org/w/api.php"
UA = f"EinkVikingArt/1.0 ({CONTACT}) Python-urllib"

# ======================================================================
#  COMMONS
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

_hits = {}                           # query -> total hits (remembered per run)

def total_hits(query):
    if query not in _hits:
        info = get_json({"action": "query", "list": "search", "srsearch": query,
                         "srnamespace": "6", "srlimit": "1", "srinfo": "totalhits"})
        _hits[query] = info.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
    return _hits[query]

def search_pages(query):
    total = total_hits(query)
    if total == 0:
        return []
    offset = random.randint(0, max(0, min(total, 10000) - 40))
    data = get_json({"action": "query", "generator": "search", "gsrsearch": query,
                     "gsrnamespace": "6", "gsrlimit": "40", "gsroffset": str(offset),
                     "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": "500"})
    return [p for p in data.get("query", {}).get("pages", [])
            if p.get("imageinfo") and p["imageinfo"][0].get("thumburl")]

# ---------------------------------------------------------------- captions
RUNESTONE_ID = re.compile(r"\b(U|S[öo]|[ÖO]g|Vg|Vs|Gs|Sm|N|DR|G|Hs|M|Ög)\s?(\d{1,4})\b")

def ascii_text(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if ord(c) < 128)

def caption_name(title, collection_name):
    base = re.sub(r"^File:|\.(svg|png|jpe?g|gif|tiff?)$", "", title, flags=re.I).replace("_", " ")
    base = re.sub(r"\s*\(.*?\)\s*$", "", base).strip()
    m = RUNESTONE_ID.search(base)
    if collection_name.startswith("Runestone") and m:
        return ascii_text(f"Runestone {m.group(1)} {m.group(2)}")
    return ascii_text(base) or "Viking art"

# ======================================================================
#  LINE-ART CHECK AND CONVERSION
# ======================================================================
def flatten(img):
    """RGBA -> RGB on white paper."""
    img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, img).convert("RGB")

def is_line_art(img):
    """Mostly paper and ink, few grey tones? Measured at the downloaded size
    (shrinking first would blur fine hatching into grey)."""
    g = ImageOps.grayscale(flatten(img))
    if max(g.size) > 600:
        g.thumbnail((600, 600))
    g = ImageOps.autocontrast(g, cutoff=(1, 2))
    hist = g.histogram()
    mid = sum(hist[60:200]) / max(1, sum(hist))
    return mid < 0.25

def otsu(gray):
    hist = gray.histogram()
    total = sum(hist)
    sum_all = sum(i * c for i, c in enumerate(hist))
    wb = sb = 0
    best, t_best = 0, 128
    for t in range(256):
        wb += hist[t]
        if wb == 0:
            continue
        wf = total - wb
        if wf == 0:
            break
        sb += t * hist[t]
        mb, mf = sb / wb, (sum_all - sb) / wf
        v = wb * wf * (mb - mf) ** 2
        if v > best:
            best, t_best = v, t
    return t_best

def to_masks(img, box):
    """Fit img into box; return (ink_mask, red_mask, offset). Ink = dark
    lines; red = clearly red areas (e.g. painted runestone reconstructions)."""
    x0, y0, x1, y1 = box
    rgb = flatten(img)
    gray = ImageOps.grayscale(rgb)
    # crop to the drawing itself
    bbox = ImageOps.invert(gray).point(lambda v: 255 if v > 40 else 0).getbbox()
    if bbox:
        rgb, gray = rgb.crop(bbox), gray.crop(bbox)
    k = min((x1 - x0) / rgb.width, (y1 - y0) / rgb.height)
    w, h = max(1, round(rgb.width * k)), max(1, round(rgb.height * k))
    rgb = rgb.resize((w, h), Image.LANCZOS)
    gray = ImageOps.autocontrast(ImageOps.grayscale(rgb), cutoff=(1, 2))
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=2))
    t = min(otsu(gray), 170)
    ink = gray.point(lambda v: 255 if v <= t else 0)
    px = rgb.load()
    red = Image.new("L", (w, h), 0)
    rp, ip = red.load(), ink.load()
    for yy in range(h):
        for xx in range(w):
            r, g, b = px[xx, yy]
            if r > 130 and r > 1.6 * g and r > 1.6 * b:
                rp[xx, yy] = 255
                ip[xx, yy] = 0
    ox, oy = x0 + ((x1 - x0) - w) // 2, y0 + ((y1 - y0) - h) // 2
    return ink, red, (ox, oy)

# ======================================================================
#  FETCH / CACHE / PICK
# ======================================================================
def fetch(collection):
    if collection == 0:
        collection = random.randrange(1, len(COLLECTIONS))
    name, period, queries = COLLECTIONS[collection]
    for q in queries:
        try:
            pages = search_pages(q)
        except Exception as e:
            print(f"  search '{q}': {e}")
            continue
        random.shuffle(pages)
        for p in pages[:6]:
            info = p["imageinfo"][0]
            vector = (info.get("mime") or "").endswith("svg+xml") or p["title"].lower().endswith(".svg")
            try:
                raw = get_bytes(info["thumburl"])
                img = Image.open(BytesIO(raw))
                img.load()
            except Exception as e:
                print(f"  {p['title']}: {e}")
                continue
            if not vector and not is_line_art(img):
                print(f"  skipping (photo, not line art): {p['title'][:50]}")
                continue
            meta = {"id": re.sub(r"[^A-Za-z0-9_-]+", "_", p["title"])[:80],
                    "name": caption_name(p["title"], name),
                    "style": name, "period": period or "",
                    "collection": name}
            save_cache(raw, meta)
            return img, meta
    return None

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

def from_cache(collection):
    if not os.path.isdir(CACHE_DIR):
        return None
    want = None if collection == 0 else COLLECTIONS[collection][0]
    entries = []
    for fn in os.listdir(CACHE_DIR):
        if fn.endswith(".png"):
            try:
                with open(os.path.join(CACHE_DIR, fn[:-4] + ".json")) as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                continue
            if want is None or meta.get("collection") == want:
                entries.append((fn, meta))
    if not entries:
        return None
    fn, meta = random.choice(entries)
    return Image.open(os.path.join(CACHE_DIR, fn)), meta

def pick(collection):
    """Only the chosen collection (Mixed draws from all styles); offline:
    cached images of that collection."""
    for _ in range(3):
        try:
            got = fetch(collection)
            if got:
                return got
        except Exception as e:
            print(f"  fetch failed: {e}")
        time.sleep(2)
    print(f"  {COLLECTIONS[collection][0]}: nothing new, using the cache")
    return from_cache(collection)

# ======================================================================
#  SCREEN
# ======================================================================
def compose(img, meta, style="mixed", caption=True):
    if style == "mixed":
        style = random.choices(["ink", "red", "inverse"], [3, 1, 1])[0]
    name_lines = pixelfont.wrap(meta.get("name", ""), WIDTH - 8, 2) if caption else []
    top = pixelfont.LINE_H * len(name_lines) + 6 if name_lines else 4
    bottom = HEIGHT - (pixelfont.LINE_H * 2 + 4 if caption else 4)
    ink, redm, (ox, oy) = to_masks(img, (6, top + 2, WIDTH - 6, bottom - 4))

    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)
    if style == "inverse":
        db.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=0)
        black.paste(1, (ox, oy), ink)
        red.paste(0, (ox, oy), redm)
        black.paste(1, (ox, oy), redm)
        tl, tf = db, 1
    elif style == "red":
        red.paste(0, (ox, oy), ink)
        red.paste(0, (ox, oy), redm)
        tl, tf = db, 0
    else:
        black.paste(0, (ox, oy), ink)
        red.paste(0, (ox, oy), redm)
        tl, tf = db, 0

    if caption:
        y = 3
        for ln in name_lines:
            pixelfont.text_centered(tl, WIDTH / 2, y, ln, fill=tf)
            y += pixelfont.LINE_H
        y = bottom + 2
        line1 = meta.get("style", "")
        if meta.get("period"):
            line1 += ", " + meta["period"]
        pixelfont.text_centered(dr if style != "inverse" else tl, WIDTH / 2, y,
                                pixelfont.wrap(line1, WIDTH - 6, 1)[0],
                                fill=0 if style != "inverse" else tf)
        pixelfont.text_centered(tl, WIDTH / 2, y + pixelfont.LINE_H, "Wikimedia Commons", fill=tf)
    return black, red, style

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
        self.collection = COLLECTION
        self.style = "mixed"
        self.caption = SHOW_CAPTION
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
    for pin, act in zip(BUTTON_PINS, ["next", "collection", "style", "caption"]):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda a=act: ctl.press(a))
            out.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return out

def main():
    if "--test" in sys.argv:
        for name, period, queries in COLLECTIONS[1:]:
            print(name)
            for q in queries:
                try:
                    print(f"  {total_hits(q):6d}  {q}")
                except Exception as e:
                    print(f"  error   {q}: {e}")
        return
    if "--preview" in sys.argv:
        i = sys.argv.index("--preview")
        col = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 0
        got = pick(col)
        if got:
            for st in ("ink", "red", "inverse"):
                b, r, _ = compose(*got, style=st)
                save_preview(b, r, f"viking_{st}.png")
            print("viking_*.png:", got[1]["name"], "|", got[1]["style"])
        return

    driver, epd = open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    current = None
    prefetched = {}

    def prefetch(collection):
        got = pick(collection)
        if got:
            got[0].load()
            prefetched.update(item=got, collection=collection)

    try:
        while True:
            act, ctl.action = ctl.action, None
            ctl.busy = True
            try:
                if act == "collection":
                    ctl.collection = (ctl.collection + 1) % len(COLLECTIONS)
                    print("collection:", COLLECTIONS[ctl.collection][0])
                elif act == "style":
                    ctl.style = STYLES[(STYLES.index(ctl.style) + 1) % len(STYLES)]
                    print("style:", ctl.style)
                elif act == "caption":
                    ctl.caption = not ctl.caption
                if act in ("next", "collection", None) or current is None:
                    got = None
                    if act != "collection" and prefetched.get("item") \
                            and prefetched.get("collection") == ctl.collection:
                        got = prefetched["item"]
                    prefetched.clear()
                    current = got or pick(ctl.collection) or current
                if current:
                    threading.Thread(target=prefetch, args=(ctl.collection,), daemon=True).start()
                    img, meta = current
                    black, red, used = compose(img, meta, ctl.style, ctl.caption)
                    print(f"showing: {meta.get('name')} | {meta.get('style')} [{used}]")
                    save_preview(black, red, os.path.join(HERE, "last_viking.png"))
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
