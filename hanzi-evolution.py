#!/usr/bin/env python3
"""
The evolution of Chinese characters on a Waveshare 2.7" e-Paper HAT (B).

For one character at a time it shows 3,000 years of its history, using the
public-domain drawings of the Ancient Chinese Characters project on
Wikimedia Commons (files like 馬-oracle.svg, 馬-bronze.svg, 馬-seal.svg):

    +--------------------------+
    |  mǎ   horse              |   pinyin and meaning
    |                          |
    |        [ oracle ]        |   large: oracle bone script, Shang
    |   oracle bone, c.1250 BC |
    |                          |
    |  [bronze] > [seal] > 馬  |   bronze inscription, small seal script,
    |                          |   and today's character in red
    +--------------------------+

Characters are chosen from a list of ~130 pictographic ones (horse, fish,
moon, mountain, chariot, dragon...) whose ancient forms are worth seeing.

Buttons (GPIO 5 / 6 / 13 / 19, top to bottom)
  KEY1  next character
  KEY2  random order <-> list order
  KEY3  large form: oracle bone -> bronze -> seal
  KEY4  labels on / off

Needs pixelfont.py (with accents) next to this script, and a CJK font for
today's character (fonts-noto-cjk). Put your e-mail in CONTACT.

Run on a PC:
  python3 hanzi-evolution.py --preview 馬
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
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pixelfont                     # crisp 6x8 bitmap font, with pinyin accents

# ---------------------------------------------------------------- settings
REFRESH_SECONDS = 5                  # pause after each refresh before the next character
# A full refresh of the 3-colour panel takes ~15 s, so ~20 s per character
# is the real minimum. Waveshare recommends >= 180 s between refreshes for
# the life of the panel when it runs all day.
CONTACT = "your-email@example.com"   # Wikimedia's User-Agent policy asks for this
ORDER = "random"                     # random / list
SHOW_LABELS = True
BUTTON_PINS = (5, 6, 13, 19)
CACHE_DIR = os.path.join(HERE, "hanzi_cache")

CJK_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

WIDTH, HEIGHT = 176, 264
API = "https://commons.wikimedia.org/w/api.php"
UA = f"EinkHanzi/1.0 ({CONTACT}) Python-urllib"

# ======================================================================
#  CHARACTERS (traditional forms, as used in the ACC file names)
# ======================================================================
CHARS = [
    ("人", "rén", "person"), ("大", "dà", "big"), ("子", "zǐ", "child"),
    ("女", "nǚ", "woman"), ("母", "mǔ", "mother"), ("父", "fù", "father"),
    ("日", "rì", "sun"), ("月", "yuè", "moon"), ("星", "xīng", "star"),
    ("山", "shān", "mountain"), ("水", "shuǐ", "water"), ("火", "huǒ", "fire"),
    ("木", "mù", "tree"), ("林", "lín", "grove"), ("雨", "yǔ", "rain"),
    ("雲", "yún", "cloud"), ("川", "chuān", "river"), ("田", "tián", "field"),
    ("禾", "hé", "grain"), ("米", "mǐ", "rice"), ("馬", "mǎ", "horse"),
    ("牛", "niú", "ox"), ("羊", "yáng", "sheep"), ("犬", "quǎn", "dog"),
    ("豕", "shǐ", "pig"), ("鹿", "lù", "deer"), ("虎", "hǔ", "tiger"),
    ("象", "xiàng", "elephant"), ("龍", "lóng", "dragon"), ("魚", "yú", "fish"),
    ("鳥", "niǎo", "bird"), ("隹", "zhuī", "short-tailed bird"), ("燕", "yàn", "swallow"),
    ("龜", "guī", "turtle"), ("目", "mù", "eye"), ("耳", "ěr", "ear"),
    ("口", "kǒu", "mouth"), ("自", "zì", "nose, self"), ("首", "shǒu", "head"),
    ("手", "shǒu", "hand"), ("又", "yòu", "right hand, again"), ("止", "zhǐ", "foot, stop"),
    ("足", "zú", "foot"), ("心", "xīn", "heart"), ("齒", "chǐ", "tooth"),
    ("舌", "shé", "tongue"), ("面", "miàn", "face"), ("見", "jiàn", "see"),
    ("立", "lì", "stand"), ("走", "zǒu", "run"), ("行", "xíng", "crossroads, go"),
    ("車", "chē", "chariot"), ("舟", "zhōu", "boat"), ("門", "mén", "gate"),
    ("戶", "hù", "door"), ("家", "jiā", "home"), ("宮", "gōng", "palace"),
    ("高", "gāo", "tall"), ("京", "jīng", "capital"), ("井", "jǐng", "well"),
    ("刀", "dāo", "knife"), ("弓", "gōng", "bow"), ("矢", "shǐ", "arrow"),
    ("戈", "gē", "dagger-axe"), ("王", "wáng", "king"), ("帝", "dì", "god, emperor"),
    ("天", "tiān", "sky, heaven"), ("示", "shì", "altar"), ("祖", "zǔ", "ancestor"),
    ("卜", "bǔ", "divination"), ("貝", "bèi", "cowrie shell"), ("玉", "yù", "jade"),
    ("鼎", "dǐng", "cauldron"), ("酉", "yǒu", "wine jar"), ("豆", "dòu", "food vessel"),
    ("皿", "mǐn", "dish"), ("冊", "cè", "bamboo book"), ("衣", "yī", "clothing"),
    ("糸", "mì", "silk thread"), ("絲", "sī", "silk"), ("生", "shēng", "grow, birth"),
    ("好", "hǎo", "good"), ("休", "xiū", "rest"), ("明", "míng", "bright"),
    ("東", "dōng", "east"), ("西", "xī", "west"), ("南", "nán", "south"),
    ("北", "běi", "north"), ("上", "shàng", "above"), ("下", "xià", "below"),
    ("中", "zhōng", "middle"), ("一", "yī", "one"), ("二", "èr", "two"),
    ("三", "sān", "three"), ("十", "shí", "ten"), ("百", "bǎi", "hundred"),
    ("千", "qiān", "thousand"), ("萬", "wàn", "ten thousand"), ("年", "nián", "year"),
    ("春", "chūn", "spring"), ("秋", "qiū", "autumn"), ("光", "guāng", "light"),
    ("美", "měi", "beautiful"), ("鬼", "guǐ", "ghost"), ("羽", "yǔ", "feather"),
    ("角", "jiǎo", "horn"), ("毛", "máo", "fur, hair"), ("石", "shí", "stone"),
    ("土", "tǔ", "earth"), ("金", "jīn", "metal, gold"), ("泉", "quán", "spring (water)"),
    ("谷", "gǔ", "valley"), ("鳳", "fèng", "phoenix"), ("風", "fēng", "wind"),
    ("安", "ān", "peace"), ("文", "wén", "pattern, writing"), ("武", "wǔ", "martial"),
    ("言", "yán", "speech"), ("書", "shū", "writing, book"), ("史", "shǐ", "scribe, history"),
    ("長", "cháng", "long"), ("老", "lǎo", "old"), ("兄", "xiōng", "elder brother"),
    ("夫", "fū", "man, husband"), ("妻", "qī", "wife"), ("孫", "sūn", "grandchild"),
    ("力", "lì", "strength"), ("男", "nán", "man"), ("爪", "zhǎo", "claw"),
    ("牢", "láo", "animal pen"), ("采", "cǎi", "pick, gather"), ("射", "shè", "shoot"),
]

# script forms in the order they appeared; (file suffix, label, approximate date)
ORACLE = [("oracle", "oracle bone", "c.1250 BC")]
BRONZE = [("bronze-shang", "bronze", "c.1100 BC"), ("bronze", "bronze", "c.1000 BC"),
          ("bronze-spring", "bronze", "c.600 BC"), ("bronze-warring", "bronze", "c.400 BC")]
SEAL = [("seal", "small seal", "c.220 BC"), ("slip", "Qin slip", "c.220 BC"),
        ("silk", "Chu silk", "c.300 BC"), ("bigseal", "big seal", "(later copy)")]
HERO_ORDER = ["oracle", "bronze", "seal"]
SHORT = {"oracle bone": "oracle", "small seal": "seal", "Qin slip": "slip",
         "Chu silk": "silk", "big seal": "big seal", "bronze": "bronze"}

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

def fetch_forms(ch):
    """{suffix: PIL image} for every ancient form of ch that exists."""
    suffixes = [s for s, _, _ in ORACLE + BRONZE + SEAL]
    titles = [f"File:{ch}-{s}.svg" for s in suffixes]
    data = get_json({"action": "query", "titles": "|".join(titles),
                     "prop": "imageinfo", "iiprop": "url", "iiurlwidth": "330"})
    forms = {}
    for p in data.get("query", {}).get("pages", []):
        if p.get("missing") or not p.get("imageinfo"):
            continue
        prefix = f"File:{ch}-"
        if not (p["title"].startswith(prefix) and p["title"].endswith(".svg")):
            continue
        suffix = p["title"][len(prefix):-4]          # e.g. "bronze-warring"
        url = p["imageinfo"][0].get("thumburl") or p["imageinfo"][0].get("url")
        try:
            raw = get_bytes(url)
        except Exception as e:
            print(f"  {p['title']}: {e}")
            continue
        forms[suffix] = raw
    return forms

def cache_dir(ch):
    return os.path.join(CACHE_DIR, f"{ord(ch):05X}")

def save_forms(ch, forms):
    d = cache_dir(ch)
    os.makedirs(d, exist_ok=True)
    for s, raw in forms.items():
        with open(os.path.join(d, s + ".png"), "wb") as f:
            f.write(raw)

def load_forms(ch):
    d = cache_dir(ch)
    if not os.path.isdir(d):
        return {}
    out = {}
    for fn in os.listdir(d):
        if fn.endswith(".png"):
            with open(os.path.join(d, fn), "rb") as f:
                out[fn[:-4]] = f.read()
    return out

def get_forms(ch):
    """Cached forms first (they never change), else fetch from Commons."""
    forms = load_forms(ch)
    if forms:
        return forms
    forms = fetch_forms(ch)
    if forms:
        save_forms(ch, forms)
    return forms

# ======================================================================
#  CHOOSING
# ======================================================================
def state_path():
    return os.path.join(CACHE_DIR, "position.json")

def next_char(order):
    if order == "list":
        try:
            with open(state_path()) as f:
                i = json.load(f).get("index", -1) + 1
        except (OSError, ValueError):
            i = 0
        i %= len(CHARS)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(state_path(), "w") as f:
            json.dump({"index": i}, f)
        return CHARS[i]
    return random.choice(CHARS)

def pick(order):
    """A character with at least an oracle or bronze form."""
    for _ in range(6):
        entry = next_char(order)
        try:
            forms = get_forms(entry[0])
        except Exception as e:
            print(f"  {entry[0]}: {e}")
            forms = load_forms(entry[0])
        if any(s in forms for s, _, _ in ORACLE + BRONZE):
            return entry, forms
        print(f"  {entry[0]} {entry[2]}: no early forms on Commons, next")
    # offline and nothing cached for those: any cached character
    cached = [c for c in CHARS if load_forms(c[0])]
    if cached:
        c = random.choice(cached)
        return c, load_forms(c[0])
    return None

# ======================================================================
#  DRAWING
# ======================================================================
def glyph_mask(raw, size):
    """1-bit mask (255 = ink) of a drawing, cropped and fitted in size x size."""
    img = Image.open(BytesIO(raw)).convert("RGBA")
    r, g, b, a = img.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    ink = Image.new("L", img.size, 0)
    ink.paste(255, (0, 0), Image.eval(a, lambda v: 255 if v > 110 else 0))
    ink.paste(0, (0, 0), Image.eval(lum, lambda v: 255 if v >= 150 else 0))
    box = ink.getbbox()
    if box:
        ink = ink.crop(box)
    k = min(size / ink.width, size / ink.height)
    w, h = max(1, round(ink.width * k)), max(1, round(ink.height * k))
    return ink.resize((w, h), Image.LANCZOS).point(lambda v: 255 if v > 100 else 0)

def modern_mask(ch, size):
    path = next((p for p in CJK_FONTS if os.path.exists(p)), None)
    if not path:
        return None
    try:
        f = ImageFont.truetype(path, int(size * 1.15), index=2)   # TC face in Noto .ttc
    except Exception:
        f = ImageFont.truetype(path, int(size * 1.15))
    tile = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(tile).text((size // 4, size // 4), ch, font=f, fill=255)
    box = tile.getbbox()
    if not box:
        return None
    tile = tile.crop(box)
    k = min(size / tile.width, size / tile.height, 1.0)
    tile = tile.resize((max(1, int(tile.width * k)), max(1, int(tile.height * k))), Image.LANCZOS)
    return tile.point(lambda v: 255 if v > 110 else 0)

def first(forms, options):
    for s, label, era in options:
        if s in forms:
            return s, label, era
    return None

def arrow(draw, x, y):
    draw.polygon([(x, y - 4), (x + 5, y), (x, y + 4)], fill=0)

def compose(entry, forms, hero="oracle", labels=True):
    ch, pinyin, meaning = entry
    black = Image.new("1", (WIDTH, HEIGHT), 1)
    red = Image.new("1", (WIDTH, HEIGHT), 1)
    db, dr = ImageDraw.Draw(black), ImageDraw.Draw(red)

    groups = {"oracle": ORACLE, "bronze": BRONZE, "seal": SEAL}
    # the large form: the chosen script, or the earliest that exists
    order = [hero] + [h for h in HERO_ORDER if h != hero]
    hero_pick = None
    for h in order:
        f = first(forms, groups[h])
        if f:
            hero_pick, hero_group = f, h
            break
    rest = [g for g in HERO_ORDER if g != hero_group]
    row = [first(forms, groups[g]) for g in rest]
    row = [r for r in row if r]

    # title bar: pinyin and meaning
    bar_h = 12
    db.rectangle((0, 0, WIDTH - 1, bar_h - 1), fill=0)
    title = pixelfont.wrap(f"{pinyin}  {meaning}", WIDTH - 6, 1)[0]
    pixelfont.text_centered(db, WIDTH / 2, 2, title, fill=1)

    # the large ancient form
    hero_size = 128
    m = glyph_mask(forms[hero_pick[0]], hero_size)
    hy = bar_h + 8 + (hero_size - m.height) // 2
    black.paste(0, ((WIDTH - m.width) // 2, hy), m)
    y = bar_h + 8 + hero_size + 4
    if labels:
        pixelfont.text_centered(db, WIDTH / 2, y, f"{hero_pick[1]}, {hero_pick[2]}")
    y += 14

    # evolution row: the other ancient forms, then today's character in red
    cells = [(r, None) for r in row] + [(("modern", "today", ""), "modern")]
    n = len(cells)
    cell_w = WIDTH // n
    size = min(50, cell_w - 12)
    db.line((10, y - 4, WIDTH - 11, y - 4), fill=0)
    for i, ((suffix, label, era), kind) in enumerate(cells):
        cx = i * cell_w + cell_w // 2
        if kind == "modern":
            mm = modern_mask(ch, size)
            if mm is not None:
                red.paste(0, (cx - mm.width // 2, y + (size - mm.height) // 2), mm)
        else:
            mm = glyph_mask(forms[suffix], size)
            black.paste(0, (cx - mm.width // 2, y + (size - mm.height) // 2), mm)
        if labels:
            pixelfont.text_centered(db, cx, y + size + 4, SHORT.get(label, label))
            if era:
                pixelfont.text_centered(db, cx, y + size + 4 + pixelfont.LINE_H, era)
        if i < n - 1:
            arrow(dr, (i + 1) * cell_w - 3, y + size // 2)

    # credit line, tiny but legible
    if labels:
        pixelfont.text_centered(db, WIDTH / 2, HEIGHT - 10, "Ancient Chinese Characters")
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
        self.order = ORDER
        self.hero = "oracle"
        self.labels = SHOW_LABELS
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
    for pin, act in zip(BUTTON_PINS, ["next", "order", "hero", "labels"]):
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
        entry = next((c for c in CHARS if c[0] == arg), None) or random.choice(CHARS)
        forms = get_forms(entry[0])
        if not forms:
            print("no forms found for", entry[0])
            return
        b, r = compose(entry, forms)
        save_preview(b, r, "hanzi_preview.png")
        print("hanzi_preview.png:", entry, "forms:", sorted(forms))
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
                elif act == "hero":
                    ctl.hero = HERO_ORDER[(HERO_ORDER.index(ctl.hero) + 1) % len(HERO_ORDER)]
                    print("large form:", ctl.hero)
                elif act == "labels":
                    ctl.labels = not ctl.labels
                if act in ("next", "order", None) or current is None:
                    got = None
                    if act != "order" and prefetched.get("item") and prefetched.get("order") == ctl.order:
                        got = prefetched["item"]
                    prefetched.clear()
                    if not got:
                        got = pick(ctl.order)
                    if got:
                        current = got
                if current:
                    threading.Thread(target=prefetch, args=(ctl.order,), daemon=True).start()
                    entry, forms = current
                    print(f"showing: {entry[0]} {entry[1]} {entry[2]}  forms: {sorted(forms)}")
                    black, red = compose(entry, forms, ctl.hero, ctl.labels)
                    save_preview(black, red, os.path.join(HERE, "last_hanzi.png"))
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
