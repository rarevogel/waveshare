#!/usr/bin/env python3
"""
The Gelre Armorial on a Waveshare 2.7" e-Paper HAT (B).

The Wapenboek Gelre (c. 1370-1414, Royal Library of Belgium, ms. 15652-56)
is one of the great medieval armorials. On Wikimedia Commons every folio has
a gallery page ("Folio 26r de l'Armorial de Gelre") with vector drawings of
the arms on that folio. This program shows them one by one, coloured with
the Petra Sancta hatching of heraldry.py: gules red, azure horizontal lines,
vert diagonals, or dots, purpure the other diagonal, sable black.

Two ways of going through the book (KEY2):
  random   a random coat of arms from a random folio
  browse   leaf through the armorial in order, folio by folio, arms by arms
           (the position is remembered across restarts)

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next coat of arms
  KEY2  random <-> browse in order
  KEY3  description (folio and caption) on / off
  KEY4  gules as red / gules as vertical hatching

Needs heraldry.py and pixelfont.py in the same folder.
Put your e-mail in CONTACT: Wikimedia asks programs to identify themselves.

Run on a PC:
  python3 gelre.py --list             # list the folios found
  python3 gelre.py --preview          # fetch one, save gelre_preview.png
"""
import json
import os
import random
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from io import BytesIO
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heraldry                      # tincture recognition, hatching, layout
from heraldry import ascii_text, strip_html

# ---------------------------------------------------------------- settings
REFRESH_SECONDS = 5                  # pause after each refresh before the next arms
# A full refresh of the 3-colour panel takes ~15 s, so ~20 s per coat of
# arms is the real minimum. Waveshare recommends >= 180 s between refreshes
# for the life of the panel when it runs all day.
CONTACT = "your-email@example.com"   # Wikimedia's User-Agent policy asks for this
MODE = "random"                      # random / browse
SHOW_DESCRIPTION = True
GULES_AS_RED = True
BUTTON_PINS = (5, 6, 13, 19)

CATEGORY = "Category:Gelre Armorial"
FOLIO_RE = re.compile(r"^Folio\s+(\d+)\s*([rv])\b", re.I)
CACHE_DIR = os.path.join(HERE, "gelre_cache")
STATE_FILE = os.path.join(CACHE_DIR, "position.json")
LIST_MAX_AGE = 7 * 24 * 3600         # refresh the folio / gallery lists weekly

API = "https://commons.wikimedia.org/w/api.php"
UA = f"EinkGelre/1.0 ({CONTACT}) Python-urllib"

# ======================================================================
#  COMMONS API
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

def _cached_json(name, builder):
    """Keep slow-changing lists on disk; rebuild them weekly or when missing."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    try:
        if time.time() - os.path.getmtime(path) < LIST_MAX_AGE:
            with open(path) as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    try:
        data = builder()
    except Exception as e:
        print(f"  could not refresh {name}: {e}")
        try:
            with open(path) as f:                    # stale copy beats nothing
                return json.load(f)
        except (OSError, ValueError):
            raise e
    with open(path, "w") as f:
        json.dump(data, f)
    return data

def folio_key(title):
    m = FOLIO_RE.match(title)
    return (int(m.group(1)), 0 if m.group(2).lower() == "r" else 1) if m else (9999, 0)

def list_folios():
    """All 'Folio ..' gallery pages in the category, in book order."""
    def build():
        titles, cont = [], {}
        while True:
            data = get_json(dict({"action": "query", "list": "categorymembers",
                                  "cmtitle": CATEGORY, "cmtype": "page",
                                  "cmlimit": "500"}, **cont))
            titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
            if "continue" not in data:
                break
            cont = data["continue"]
        folios = [t for t in titles if FOLIO_RE.match(t)]
        return sorted(folios, key=folio_key)
    return _cached_json("folios.json", build)

def gallery_entries(folio):
    """[(file title, caption)] of the SVG arms on one folio page, in the
    order of the gallery. Captions come from the page's <gallery> wikitext."""
    def build():
        wt = get_json({"action": "parse", "page": folio, "prop": "wikitext"})
        text = wt.get("parse", {}).get("wikitext", "")
        entries = []
        for block in re.findall(r"<gallery[^>]*>(.*?)</gallery>", text, flags=re.S | re.I):
            for line in block.splitlines():
                line = line.strip()
                if not line:
                    continue
                name, _, cap = line.partition("|")
                name = re.sub(r"^(File|Image|Fichier|Bestand|Datei)\s*:", "", name.strip(), flags=re.I)
                if not name.lower().endswith(".svg"):
                    continue
                name = name.replace("_", " ")
                name = name[:1].upper() + name[1:]
                entries.append(("File:" + name, clean_caption(cap)))
        if not entries:                              # no gallery markup: use the page's images
            data = get_json({"action": "query", "titles": folio, "prop": "images",
                             "imlimit": "500"})
            for p in data.get("query", {}).get("pages", []):
                for im in p.get("images", []):
                    if im["title"].lower().endswith(".svg"):
                        entries.append((im["title"], ""))
        return entries
    safe = re.sub(r"[^A-Za-z0-9]+", "_", folio)[:60]
    return [tuple(e) for e in _cached_json(f"gallery_{safe}.json", build)]

def clean_caption(cap):
    cap = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", cap)   # [[link|text]] -> text
    cap = re.sub(r"'{2,}", "", cap)                                # ''italic'' / '''bold'''
    cap = re.sub(r"\{\{[^}]*\}\}", "", cap)                        # templates
    cap = re.sub(r"(alt|link|page|class)\s*=\s*[^|]*", "", cap)
    return ascii_text(strip_html(cap)).strip(" |-")

def fetch_image(file_title):
    data = get_json({"action": "query", "titles": file_title, "prop": "imageinfo",
                     "iiprop": "url|extmetadata", "iiurlwidth": "500",
                     "iiextmetadatafilter": "ObjectName|ImageDescription"})
    pages = data.get("query", {}).get("pages", [])
    if not pages or not pages[0].get("imageinfo"):
        return None, {}
    info = pages[0]["imageinfo"][0]
    url = info.get("thumburl") or info.get("url")
    return get_bytes(url), info.get("extmetadata", {})

# ======================================================================
#  CHOOSING THE NEXT COAT OF ARMS
# ======================================================================
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"folio": 0, "entry": -1}

def save_state(st):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(st, f)

def next_entry(mode, folios):
    """Returns (folio title, file title, caption, position in folio, total)."""
    if mode == "browse":
        st = load_state()
        fi, ei = st.get("folio", 0) % len(folios), st.get("entry", -1) + 1
        for _ in range(len(folios)):
            entries = gallery_entries(folios[fi])
            if ei < len(entries):
                save_state({"folio": fi, "entry": ei})
                return folios[fi], entries[ei][0], entries[ei][1], ei + 1, len(entries)
            fi, ei = (fi + 1) % len(folios), 0
        return None
    for _ in range(10):
        folio = random.choice(folios)
        entries = gallery_entries(folio)
        if entries:
            i = random.randrange(len(entries))
            return folio, entries[i][0], entries[i][1], i + 1, len(entries)
    return None

def short_folio(folio):
    m = FOLIO_RE.match(folio)
    return f"folio {m.group(1)}{m.group(2).lower()}" if m else folio

def bearer_name(file_title, caption, ext):
    if caption:
        return caption
    obj = ascii_text(strip_html((ext.get("ObjectName") or {}).get("value", "")))
    if obj:
        return obj
    base = re.sub(r"^File:|\.svg$", "", file_title, flags=re.I)
    base = re.sub(r"\b(Blason|Gelre|Armorial|Wapenboek|Arms|of|de|du|des)\b", " ", base, flags=re.I)
    return ascii_text(re.sub(r"[\s_\-,()]+", " ", base)).strip() or "Unknown arms"

def pick(mode):
    """Fetch the next coat of arms; offline, show one from the image cache."""
    try:
        folios = list_folios()
        for _ in range(4):
            choice = next_entry(mode, folios)
            if not choice:
                break
            folio, file_title, caption, pos, total = choice
            try:
                raw, ext = fetch_image(file_title)
            except Exception as e:
                print(f"  {file_title}: {e}")
                continue
            if not raw:
                continue
            name = bearer_name(file_title, caption, ext)
            meta = {"id": re.sub(r"[^A-Za-z0-9_-]+", "_", file_title)[:80],
                    "name": name,
                    "description": f"Gelre Armorial, {short_folio(folio)}, "
                                   f"arms {pos} of {total}",
                    "file": file_title}
            heraldry_cache_put(raw, meta)
            return Image.open(BytesIO(raw)), meta
    except Exception as e:
        print(f"  Commons not reachable: {e}")
    print("  using the image cache")
    return heraldry_cache_get()

IMG_DIR = os.path.join(CACHE_DIR, "images")

def heraldry_cache_put(raw, meta):
    os.makedirs(IMG_DIR, exist_ok=True)
    with open(os.path.join(IMG_DIR, meta["id"] + ".png"), "wb") as f:
        f.write(raw)
    with open(os.path.join(IMG_DIR, meta["id"] + ".json"), "w") as f:
        json.dump(meta, f)

def heraldry_cache_get():
    if not os.path.isdir(IMG_DIR):
        return None
    names = [n[:-4] for n in os.listdir(IMG_DIR) if n.endswith(".png")]
    if not names:
        return None
    n = random.choice(names)
    try:
        with open(os.path.join(IMG_DIR, n + ".json")) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        meta = {"id": n, "name": n, "description": "Gelre Armorial"}
    return Image.open(os.path.join(IMG_DIR, n + ".png")), meta

# ======================================================================
#  MAIN LOOP (same hardware handling as the other programs)
# ======================================================================
class Controller:
    def __init__(self):
        self.mode = MODE
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
    for pin, act in zip(BUTTON_PINS, ["next", "mode", "desc", "gules"]):
        try:
            b = Button(pin, bounce_time=0.15)
            b.when_pressed = (lambda a=act: ctl.press(a))
            out.append(b)
        except Exception as e:
            print(f"button on GPIO {pin} not available: {e}")
    return out

def main():
    if "--list" in sys.argv:
        folios = list_folios()
        print(f"{len(folios)} folios")
        for f in folios[:10]:
            print(" ", f, "-", len(gallery_entries(f)), "SVG arms")
        return
    if "--preview" in sys.argv:
        got = pick(MODE)
        if got:
            b, r = heraldry.compose(*got)
            heraldry.save_preview(b, r, "gelre_preview.png")
            print("gelre_preview.png:", got[1]["name"], "|", got[1]["description"])
        return

    driver, epd = heraldry.open_display()
    if epd is None:
        print("Waveshare driver not found; use --preview on a PC")
        return
    ctl = Controller()
    buttons = setup_buttons(ctl)
    current = None
    prefetched = {}

    def prefetch(mode):
        got = pick(mode)
        if got:
            got[0].load()
            prefetched.update(arms=got, mode=mode)

    try:
        while True:
            act, ctl.action = ctl.action, None
            ctl.busy = True
            try:
                if act == "mode":
                    ctl.mode = "browse" if ctl.mode == "random" else "random"
                    print("mode:", ctl.mode)
                elif act == "desc":
                    ctl.show_desc = not ctl.show_desc
                elif act == "gules":
                    ctl.gules_red = not ctl.gules_red
                if act in ("next", "mode", None) or current is None:
                    got = None
                    if act != "mode" and prefetched.get("arms") and prefetched.get("mode") == ctl.mode:
                        got = prefetched["arms"]
                    prefetched.clear()
                    if not got:
                        got = pick(ctl.mode)
                    if got:
                        current = got
                if current:
                    threading.Thread(target=prefetch, args=(ctl.mode,), daemon=True).start()
                    img, meta = current
                    print(f"showing: {meta.get('name')} | {meta.get('description')}")
                    black, red = heraldry.compose(img, meta, ctl.show_desc, ctl.gules_red)
                    heraldry.save_preview(black, red, os.path.join(HERE, "last_gelre.png"))
                    heraldry.show(epd, black, red)
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
