#!/usr/bin/env python3
"""
Japanese family crests (kamon) on a Waveshare 2.7" e-Paper HAT (B).

Fetches a random kamon from Wikimedia Commons (vector drawings, rendered
to PNG by Commons), turns it into crisp 1-bit art - kamon are black and
white by nature, so nothing is dithered - and shows it large with its
romanised name and an English gloss of that name:

    "Maru ni hitotsuhiki"   ->  circle with one line
    "Hidari mitsudomoe"     ->  left three comma-swirl

Three styles (KEY3), like the places kamon actually appear:
    ink      black crest on white paper
    lantern  red crest, as painted on paper lanterns and banners
    kimono   white crest on black, as on a formal crested kimono (montsuki)
"mixed" picks one of these at random for every crest.

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next crest
  KEY2  next collection ("Japanese Crest" series -> wider kamon search)
  KEY3  style: mixed -> ink -> lantern -> kimono
  KEY4  name and gloss on / off

Most crests in the main collection were drawn by the Commons user Mukai
and are licensed CC BY-SA; fine for a display at home, but credit the
author if you ever publish the images.

Put your e-mail in CONTACT: Wikimedia asks programs to identify themselves.

Run on a PC:
  python3 kamon.py --preview            # fetch one, save PNGs in all styles
  python3 kamon.py --image crest.png    # convert a local image
  python3 kamon.py --gloss "Maru ni hitotsuhiki"
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
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font (pixelfont.py)

# ---------------------------------------------------------------- settings
REFRESH_SECONDS = 5                  # pause after each refresh before the next crest
# Note: a full refresh of this 3-colour panel itself takes ~15 s, so one
# crest every ~20 s is the real minimum. Waveshare recommends at least
# 180 s between refreshes for the life of the panel; use a short interval
# for browsing and a longer one for leaving it running.
CONTACT = "your-email@example.com"   # Wikimedia's User-Agent policy asks for this
STYLE = "mixed"                      # mixed / ink / lantern / kimono
SHOW_TEXT = True
BUTTON_PINS = (5, 6, 13, 19)
CACHE_DIR = os.path.join(HERE, "kamon_cache")
CACHE_KEEP = 100

COLLECTIONS = [
    ("Japanese Crest series", 'intitle:"Japanese Crest" filemime:image/svg+xml'),
    ("Kamon (wide search)",   'kamon filemime:image/svg+xml'),
]
STYLES = ["mixed", "ink", "lantern", "kimono"]

WIDTH, HEIGHT = 176, 264
API = "https://commons.wikimedia.org/w/api.php"
UA = f"EinkKamon/1.0 ({CONTACT}) Python-urllib"

# ======================================================================
#  NAME -> ENGLISH GLOSS
# ======================================================================
# Common words in kamon names. Many appear in a voiced form inside a
# compound (tomoe -> domoe, hishi -> bishi), so both forms are listed.
WORDS = {
    "maru": "circle", "ni": "with", "no": "of", "mon": "crest",
    "hitotsu": "one", "futatsu": "two", "mitsu": "three", "mittsu": "three",
    "yotsu": "four", "itsutsu": "five", "mutsu": "six", "nanatsu": "seven",
    "yatsu": "eight", "kokonotsu": "nine", "too": "ten",
    "hidari": "left", "migi": "right",
    "tomoe": "comma-swirl", "domoe": "comma-swirl",
    "hiki": "line", "biki": "line", "monji": "character",
    "ichimonji": "character one", "jumonji": "cross", "juji": "cross",
    "hishi": "diamond", "bishi": "diamond", "hanabishi": "flower diamond",
    "kikko": "tortoiseshell", "kikkou": "tortoiseshell", "gikko": "tortoiseshell",
    "kiri": "paulownia", "giri": "paulownia",
    "kiku": "chrysanthemum", "giku": "chrysanthemum",
    "aoi": "hollyhock", "sasa": "bamboo grass", "zasa": "bamboo grass",
    "take": "bamboo", "dake": "bamboo", "matsu": "pine", "ume": "plum blossom",
    "sakura": "cherry blossom", "zakura": "cherry blossom", "fuji": "wisteria",
    "kashiwa": "oak leaf", "gashiwa": "oak leaf", "tachibana": "mandarin orange",
    "momiji": "maple", "karigane": "wild goose", "gari": "wild goose",
    "tsuru": "crane", "zuru": "crane", "cho": "butterfly", "chou": "butterfly",
    "ya": "arrow", "ogi": "fan", "oogi": "fan", "ougi": "fan", "wa": "ring",
    "mokko": "quince flower", "mokkou": "quince flower",
    "katabami": "wood sorrel", "kikyo": "bellflower", "kikyou": "bellflower",
    "myoga": "ginger", "myouga": "ginger", "tsuta": "ivy", "dzuta": "ivy",
    "uroko": "scale", "kuruma": "wheel", "guruma": "wheel", "genji": "Genji",
    "ken": "sword", "hane": "feather", "bane": "feather", "ha": "leaf", "ba": "leaf",
    "hana": "flower", "bana": "flower", "sagari": "hanging", "mukai": "facing",
    "chigai": "crossed", "gai": "crossed", "narabi": "side by side",
    "kumi": "interlaced", "gumi": "interlaced", "ishi": "stone", "hoshi": "star",
    "boshi": "star", "tsuki": "moon", "zuki": "moon", "nami": "wave", "kumo": "cloud",
    "gumo": "cloud", "yama": "mountain", "igeta": "well frame", "kaku": "square",
    "sumitate": "on-point square", "kai": "shell", "gai_": "shell",
    "kabuto": "helmet", "tora": "tiger", "ryu": "dragon", "ho": "sail",
    "fune": "boat", "naname": "diagonal", "kaji": "rudder", "kagi": "key",
    "hann": "seal", "han": "seal", "manji": "manji", "kasa": "umbrella",
    "gasa": "umbrella", "nadeshiko": "pink", "botan": "peony", "ine": "rice plant",
    "mame": "bean", "suhama": "sandbar", "kani": "crab", "usagi": "rabbit",
    "hato": "dove", "taka": "hawk", "daka": "hawk", "tsuno": "antler",
    "ito": "thread", "wachigai": "linked rings",
    "takanoha": "hawk feather", "gosan": "five-three", "goshichi": "five-seven",
    "chuwa": "medium ring", "hosowa": "thin ring", "futowa": "thick ring",
    "seimei": "Seimei", "abe": "Abe", "kamon": "crest",
}
NUMBERS = {"two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
PLURAL = {"line": "lines", "diamond": "diamonds", "comma-swirl": "comma-swirls",
          "leaf": "leaves", "arrow": "arrows", "scale": "scales", "star": "stars",
          "feather": "feathers", "ring": "rings", "fan": "fans", "stone": "stones",
          "crane": "cranes", "wave": "waves", "sword": "swords", "hawk feather": "hawk feathers",
          "bean": "beans", "dove": "doves", "butterfly": "butterflies", "wild goose": "wild geese"}
_MAXLEN = max(len(k) for k in WORDS)

def segment(word):
    """Split a romanised compound into known words (longest match first)."""
    out, i = [], 0
    while i < len(word):
        for L in range(min(_MAXLEN, len(word) - i), 0, -1):
            piece = word[i:i + L]
            if piece in WORDS and not piece.endswith("_"):
                out.append(WORDS[piece])
                i += L
                break
        else:
            return None                              # unknown part
    return out

def gloss(name):
    """English gloss of a kamon name, or '' if too little is recognised."""
    words = re.findall(r"[a-z]+", ascii_text(name).lower().replace("ō", "o").replace("ū", "u"))
    parts, known, total = [], 0, 0
    for w in words:
        total += len(w)
        seg = segment(w)
        if seg:
            parts += seg
            known += len(w)
        else:
            parts.append(w)
    if total == 0 or known / total < 0.6:
        return ""
    # plurals after a number: "two lines", "three comma-swirls"
    for i in range(1, len(parts)):
        if parts[i - 1] in NUMBERS and parts[i] in PLURAL:
            parts[i] = PLURAL[parts[i]]
    text = " ".join(parts)
    return re.sub(r"\b(\w+) \1\b", r"\1", text)

def ascii_text(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if ord(c) < 128)

def crest_name(title):
    base = re.sub(r"^File:", "", title)
    base = re.sub(r"\.svg$", "", base, flags=re.I).replace("_", " ")
    base = re.sub(r"^(Japanese\s+Crest|Japanese\s+crest|Kamon|Mon)\s+", "", base)
    base = re.sub(r"\s*\(.*?\)\s*$|\s+\d+$", "", base)
    return ascii_text(base).strip()

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

def fetch_crest(collection):
    name, query = COLLECTIONS[collection]
    info = get_json({"action": "query", "list": "search", "srsearch": query,
                     "srnamespace": "6", "srlimit": "1", "srinfo": "totalhits"})
    total = info.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
    if total == 0:
        return None
    offset = random.randint(0, max(0, min(total, 10000) - 40))
    data = get_json({"action": "query", "generator": "search", "gsrsearch": query,
                     "gsrnamespace": "6", "gsrlimit": "40", "gsroffset": str(offset),
                     "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": "500"})
    pages = [p for p in data.get("query", {}).get("pages", [])
             if p.get("title", "").lower().endswith(".svg")
             and p.get("imageinfo") and p["imageinfo"][0].get("thumburl")]
    if not pages:
        return None
    p = random.choice(pages)
    raw = get_bytes(p["imageinfo"][0]["thumburl"])
    cname = crest_name(p["title"])
    meta = {"id": re.sub(r"[^A-Za-z0-9_-]+", "_", p["title"])[:80],
            "name": cname, "gloss": gloss(cname), "collection": name}
    save_cache(raw, meta)
    return Image.open(BytesIO(raw)), meta

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
    if not os.path.isdir(CACHE_DIR):
        return None
    entries = []
    for fn in os.listdir(CACHE_DIR):
        if fn.endswith(".png") and fn[:-4] != exclude:
            try:
                with open(os.path.join(CACHE_DIR, fn[:-4] + ".json")) as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                meta = {"id": fn[:-4], "name": fn[:-4], "gloss": ""}
            entries.append((fn[:-4], meta))
    pool = [e for e in entries if e[1].get("collection") == collection_name] or entries
    if not pool:
        return None
    n, meta = random.choice(pool)
    return Image.open(os.path.join(CACHE_DIR, n + ".png")), meta

def pick(collection, current_id=None):
    """Fetch from the chosen collection only; offline: its cached crests."""
    name = COLLECTIONS[collection][0]
    for _ in range(4):
        try:
            got = fetch_crest(collection)
            if got:
                return got
            print(f"  {name}: no usable result, trying again")
        except Exception as e:
            print(f"  {name}: fetch failed: {e}")
        time.sleep(2)
    print(f"  {name}: offline or no result, using the cache")
    return from_cache(exclude=current_id, collection_name=name)

# ======================================================================
#  DRAWING
# ======================================================================
def crest_mask(img, size):
    """1-bit mask of the crest (255 = crest), fitted into size x size.
    The crest is drawn on transparency or white; whatever is dark and
    opaque is the crest."""
    img = img.convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 60 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    k = min(size / img.width, size / img.height)
    w, h = max(1, round(img.width * k)), max(1, round(img.height * k))
    img = img.resize((w, h), Image.LANCZOS)
    r, g, b, a = img.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    # dark and opaque -> crest; threshold slightly high keeps thin lines
    lp, ap = lum.load(), a.load()
    m = Image.new("L", (w, h), 0)
    mp = m.load()
    for y in range(h):
        for x in range(w):
            if ap[x, y] > 110 and lp[x, y] < 150:
                mp[x, y] = 255
    return m

def compose(img, meta, style="ink", show_text=True):
    if style == "mixed":
        style = random.choices(["ink", "lantern", "kimono"], [2, 1, 1])[0]
    name_lines = pixelfont.wrap(meta.get("name", ""), WIDTH - 8, 2) if show_text else []
    gloss_lines = pixelfont.wrap(meta.get("gloss", ""), WIDTH - 8, 2) if show_text else []
    top = (pixelfont.LINE_H * len(name_lines) + 8) if name_lines else 6
    bottom = HEIGHT - ((pixelfont.LINE_H * len(gloss_lines) + 6) if gloss_lines else 6)
    size = min(WIDTH - 16, bottom - top - 12)
    mask = crest_mask(img, size)
    cx = (WIDTH - mask.width) // 2
    cy = top + (bottom - top - mask.height) // 2

    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)
    if style == "kimono":
        db.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=0)          # black silk
        black.paste(1, (cx, cy), mask)                               # crest left white
        text_layer, text_fill = db, 1
    elif style == "lantern":
        red.paste(0, (cx, cy), mask)
        text_layer, text_fill = db, 0
    else:
        black.paste(0, (cx, cy), mask)
        text_layer, text_fill = db, 0

    y = 3
    for ln in name_lines:
        pixelfont.text_centered(text_layer, WIDTH / 2, y, ln, fill=text_fill)
        y += pixelfont.LINE_H
    if name_lines and style != "kimono":                             # thin rule under the name
        db.line((WIDTH / 2 - 30, y + 3, WIDTH / 2 + 30, y + 3), fill=0)
    y = bottom + 3
    gl_layer = dr if style == "ink" else text_layer                  # gloss in red on paper
    gl_fill = 0 if style == "ink" else text_fill
    for ln in gloss_lines:
        pixelfont.text_centered(gl_layer, WIDTH / 2, y, ln, fill=gl_fill)
        y += pixelfont.LINE_H
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
        self.collection = 0
        self.style = STYLE
        self.show_text = SHOW_TEXT
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
    for pin, act in zip(BUTTON_PINS, ["next", "collection", "style", "text"]):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda a=act: ctl.press(a))
            out.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return out

def main():
    if "--gloss" in sys.argv:
        print(gloss(sys.argv[sys.argv.index("--gloss") + 1]) or "(not enough known words)")
        return
    if "--image" in sys.argv:
        path = sys.argv[sys.argv.index("--image") + 1]
        name = crest_name(os.path.basename(path))
        meta = {"name": name, "gloss": gloss(name)}
        for st in ("ink", "lantern", "kimono"):
            b, r, _ = compose(Image.open(path), meta, st)
            save_preview(b, r, f"kamon_{st}.png")
            print(f"kamon_{st}.png")
        return
    if "--preview" in sys.argv:
        got = pick(0)
        if got:
            for st in ("ink", "lantern", "kimono"):
                b, r, _ = compose(*got, style=st)
                save_preview(b, r, f"kamon_{st}.png")
            print("kamon_*.png:", got[1]["name"], "|", got[1]["gloss"])
        return

    driver, epd = open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview or --image on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    current = None
    prefetched = {}

    def prefetch(collection, cur):
        got = pick(collection, cur[1]["id"] if cur else None)
        if got:
            got[0].load()                               # decode now, not later
            prefetched.update(crest=got, collection=collection)
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
                elif act == "text":
                    ctl.show_text = not ctl.show_text
                if act in ("next", "collection", None) or current is None:
                    got = None
                    if act != "collection" and prefetched.get("crest") \
                            and prefetched.get("collection") == ctl.collection:
                        got = prefetched["crest"]           # fetched during the last refresh
                    prefetched.clear()
                    if not got:
                        got = pick(ctl.collection, current[1]["id"] if current else None)
                    if got:
                        current = got
                # fetch the next crest in the background while the panel refreshes
                worker = threading.Thread(target=prefetch, args=(ctl.collection, current), daemon=True)
                worker.start()
                if current:
                    img, meta = current
                    black, red, used = compose(img, meta, ctl.style, ctl.show_text)
                    print(f"showing: {meta.get('name')} | {meta.get('gloss')} "
                          f"[{meta.get('collection', '?')}, {used}]")
                    save_preview(black, red, os.path.join(HERE, "last_kamon.png"))
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
