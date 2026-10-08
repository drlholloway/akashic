from __future__ import annotations

import re

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .models import Circuit
from .normalize import normalize_row
from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS vendors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, license_note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS circuits (
  id TEXT PRIMARY KEY, vendor TEXT NOT NULL REFERENCES vendors(id), slug TEXT NOT NULL,
  name TEXT NOT NULL, subtitle TEXT, based_on TEXT, description TEXT, category TEXT,
  effect_type TEXT, tags TEXT, enclosure TEXT, controls TEXT, difficulty TEXT,
  price REAL, currency TEXT, sku TEXT, in_stock INTEGER, url TEXT, doc_url TEXT,
  doc_local TEXT, extra_docs TEXT, image_url TEXT, schematic_local TEXT,
  schematic_page INTEGER, doc_version TEXT, kicad_path TEXT DEFAULT '',
  scraped_at TEXT
);
CREATE TABLE IF NOT EXISTS bom (
  circuit_id TEXT NOT NULL REFERENCES circuits(id) ON DELETE CASCADE,
  position INTEGER NOT NULL, ref TEXT, value TEXT, part_type TEXT, notes TEXT,
  category TEXT, norm_value TEXT, sort_key REAL, variant TEXT DEFAULT '',
  PRIMARY KEY (circuit_id, position)
);
CREATE INDEX IF NOT EXISTS bom_norm ON bom(category, norm_value);
CREATE INDEX IF NOT EXISTS circuits_vendor ON circuits(vendor);
"""

VENDORS = {
    "pedalpcb": ("PedalPCB", "https://www.pedalpcb.com",
                 "Build documents are © PedalPCB.com. Metadata and part values are indexed; "
                 "schematic images are cached locally only and linked to the source document."),
    "aionfx": ("Aion FX", "https://aionfx.com",
               "Projects may be used commercially without attribution per the license page in each "
               "build document; do not resell PCBs in kits or obfuscate the circuit."),
    "madbean": ("Madbean Pedals", "https://www.madbeanpedals.com", ""),
    "guitarpcb": ("GuitarPCB", "https://guitarpcb.com", ""),
    "fuzzdog": ("Fuzz Dog", "https://shop.pedalparts.co.uk", ""),
    "sheepylove": ("Sheepylove", "https://sheepylove.com",
                   "Build documents are © Sheepylove.com; indexed and linked, not redistributed."),
    "deadendfx": ("Dead End FX", "https://www.deadendfx.com",
                  "Build documents are hosted by Dead End FX on Google Drive; indexed and linked, not redistributed."),
    "moonn": ("Moonn Electronics", "https://moonnelectronics.bigcartel.com",
              "Build documents are hosted by Moonn Electronics on Dropbox; indexed and linked, not redistributed."),
    "fivecats": ("Five Cats Pedals", "https://www.five-cats-pedals.co.uk",
                 "PCB layouts are © Five Cats Pedals; build inserts and schematics are indexed and linked, not redistributed."),
    "parasit": ("Parasit Studio", "https://parasitstudio.com",
                "Designs are for personal use only per the build docs; documents are indexed and linked, not redistributed."),
    "pcbguitarmania": ("PCB Guitar Mania", "https://pcbguitarmania.com",
                       "Build documents are © PCB Guitar Mania; indexed and linked, not redistributed."),
    "deadastronaut": ("Dead Astronaut FX", "https://deadastronaut.wixsite.com/effects",
                      "Build docs are marked not for commercial use; indexed and linked, not redistributed."),
    "bentfishbowl": ("Bent Fishbowl", "https://bentfishbowl.wixsite.com/electronics/blog",
                     "Schematics are CC BY-NC-SA by bentfishbowl; no PCB is sold, the post is the source."),
    "ggg": ("General Guitar Gadgets", "https://store.generalguitargadgets.com/collections/pcbs",
            "Project PDFs are © JD Sleep and may only be served from generalguitargadgets.com; indexed and linked, not redistributed."),
    "lectricfx": ("Lectric-FX", "https://lectric-fx.com/shop/",
                  "Build documents are © Lectric-FX; indexed and linked, not redistributed."),
    "expanon": ("Experimentalists Anonymous", "https://www.experimentalistsanonymous.com/diy/index.php?dir=Schematics",
                "A community archive of traced schematics; no PCB is sold. Images are cached locally and linked to the archive."),
    "zerogiod": ("Zero G IOD", "https://www.zerogiod.com/category/diy-pcbs",
                 "Closed store; its BOM, drill guide and schematic images are archived in data/archive/zerogiod for posterity."),
    "otrfx": ("On The Road Effects", "https://ontheroadeffects.com/pcbs/",
              "Build guides are © On The Road Effects; indexed and linked, not redistributed. Boards sell on Etsy and Reverb."),
    "dirtmonger": ("Dirt Monger Instruments", "https://dirtmongerinstruments.com/collections/diy-pcb-1",
                   "Build documents are hosted by Dirt Monger on Google Drive; indexed and linked, not redistributed."),
    "maskaudio": ("Mask Audio Electronics", "https://maskaudioelectronics.com/collections/diy-projects",
                  "Build documents are hosted by Mask Audio on Dropbox and Google Docs; indexed and linked, not redistributed."),
    "effectslayouts": ("Effects Layouts", "https://effectslayouts.com/shop/",
                       "Build documents are © Effects Layouts; indexed and linked, not redistributed."),
    "jmk": ("JMK PCBs", "https://jmkpcbs.com/shop/",
            "Build documents are © JMK Pedals, for personal use only; indexed and linked, not redistributed."),
    "eae": ("Electronic Audio Experiments", "https://www.electronicaudioexperiments.com/diy",
            "Builder's guides are © Electronic Audio Experiments and John W Snyder; indexed and linked, not redistributed. No build support is offered."),
    "c2c": ("C2C Electronics", "https://c2celectronics.com/product-category/diy-project/",
            "Conspiracy to Commit Electronics (formerly Sushi Box FX) build documents are indexed and linked, not redistributed. "
            "Every board is a high-voltage tube circuit; the vendor says none is a beginner project."),
    "deadair": ("Dead Air Studios", "https://deadairstudios.bigcartel.com/products",
                "Build guides are Google Docs by Dead Air Studios; indexed and linked, not redistributed. The shop is mostly finished pedals; only the DIY PCBs are listed here."),
    "rwlpedal": ("RWL Pedals", "https://github.com/RWLPedal/music-pcbs",
                 "Layouts shared on GitHub under CC BY-NC-SA 4.0; download the gerbers and order at a fab. Parts lists and schematics are indexed and linked."),
    "sheepygit": ("Sheepylove on GitHub", "https://github.com/szukalski/pedal-dylan159",
                  "Sheepylove's layouts for dylan159 designs, shared on GitHub under CC BY-NC-SA 4.0; download the gerbers and order at a fab. Schematics are on the Bent Fishbowl blog."),
    "otherpedals": ("Other Pedals", "https://www.otherpedals.com/shop",
                    "Other* DIY parts lists, schematics and drill guides are images on the product pages; indexed and linked, not redistributed."),
    "godcity": ("God City Instruments", "https://www.godcityinstruments.com/collections/diy-pcbs",
                "Kurt Ballou's build guides are indexed and linked, not redistributed."),
    "effects1776": ("1776 Effects", "https://1776effects.com/collections/all",
                    "Build documents are indexed and linked, not redistributed."),
    "rullywow": ("Rullywow Industries", "https://rullywow.com/shop/",
                 "Build documents are indexed and linked, not redistributed."),
    "mas": ("MAS Effects", "https://shop.mas-effects.com/collections/diy",
            "Documents on mas-effects.com and GitHub are indexed and linked, not redistributed."),
    "tonepad": ("Tonepad", "https://www.tonepad.com/catalog2.asp",
                "Layouts are © their authors and served by tonepad.com only from the project page; indexed and linked, not redistributed."),
    "wraa": ("WRAA Labs", "https://wraa.bigcartel.com/category/pedal-kit",
             "Build guides on the WRAA blog are indexed and linked, not redistributed."),
    "frog": ("Frog Pedals", "https://frogpedals.com/index.php/product-category/pcb-products/",
             "Documentation is sent to buyers and not published; only the listing is indexed."),
    "thcustom": ("TH Custom Effects", "https://diy.thcustom.com/the-main-shop/",
                 "No build documents are published; only the listing is indexed."),
    "guitarelectronics": ("Guitar-Electronics.eu", "https://guitar-electronics.eu/en_US/c/KITs-PCBs/13",
                          "Build documents are indexed and linked, not redistributed."),
    "opelectronics": ("OP Electronics", "https://www.op-electronics.com/en/169-pcbs-for-assembly",
                      "Datasheets are indexed and linked, not redistributed."),
    "griffin": ("Griffin Effects", "https://griffineffects.com/byo-pcbs",
                "Project files are © Griffin Effects; indexed and linked, not redistributed."),
    "coda": ("Coda Effects", "https://shop.coda-effects.com/en/shop/",
             "Build documents on Google Drive are indexed and linked, not redistributed."),
    "delyk": ("delyk PCBs", "https://www.delykpcb.com/shop/",
              "delyk stopped selling online in October 2026; the catalog stays up and the maker sells remaining PCBs on request "
              "(contact through the site). Build documents are indexed and linked, not redistributed."),
    "tayda": ("Tayda Electronics (DHEA)", "https://www.taydakits.com/categories/diy-guitar-effects",
              "Instruction Center pages are indexed and linked, not redistributed; prices are not readable (Cloudflare)."),
    "schalltechnik": ("Schalltechnik_04", "https://schalltechnik04.de/en/instructions",
                      "Kits discontinued in 2022; the instructions stay online and are indexed and linked, not redistributed."),
    "electricdruid": ("Electric Druid", "https://electricdruid.net/product-category/stomp-box-parts/",
                      "Construction guides are indexed and linked, not redistributed."),
    "zeppelin": ("Zeppelin Design Labs", "https://zeppelindesignlabs.com/collections/diy-kits",
                 "Assembly instructions are indexed and linked, not redistributed."),
    "moody": ("Moody Sounds", "https://en.moodysounds.com/produkt-kategori/byggsatser/",
              "Kit instructions (Moody's own, BJFE, Carlin, Vallhagen and BYOC) are indexed and linked, not redistributed."),
    "scientificguitarist": ("Scientific Guitarist", "https://scientificguitarist.wixsite.com/home/projects",
                            "Eagle projects (gerbers, BOM, schematic) published on GitHub by the author; indexed and linked, not redistributed."),
    "gigahearts": ("Gigahearts FX", "https://www.gigaheartsfx.com/collections/pcb-products",
                   "Build documents are © Gigahearts FX; indexed and linked, not redistributed. Schematic images are read locally, not served."),
    "holyisland": ("Holy Island Audio", "https://holyislandaudio.bigcartel.com/product/diy-pcbs",
                   "Build guides are Google Docs by Holy Island Audio; indexed and linked, not redistributed. "
                   "The shop is mostly finished pedals; the vendor recommends the DIY boards for experienced builders and offers no build support."),
    "effdub": ("Eff Dub Audio", "https://effdubaudio.com/category/effects-projects/",
               "DIY projects posted free by Eff Dub Audio, with file packs (schematic, layout, Eagle CAD) on the site; "
               "indexed and linked, not redistributed. Parts are read from the Eagle schematics where a pack has them."),
    "cryptid": ("Cryptid Effects", "https://github.com/drlholloway/guitar-effects-layouts",
                "This site's own layouts, CC BY-NC-SA 4.0: gerbers and faceplates on GitHub, build notes and BOM on the wiki. "
                "The schematic and the finished-pedal photo are shown here with the author's permission."),
    "pcbway-gtu": ("PCBWay: Glory to Ukraine", "https://www.pcbway.com/project/member/?bmbno=19C5FC6C-66B1-46",
                   "Shared projects are CC BY-SA 3.0; schematic images may be shown with attribution. Parts are counted from the schematic's value labels "
                   "(the drawings name no designators); gerbers need a PCBWay login."),
}


# What the vendor sells: "shop" (a PCB), "projects" (order the board from a fab), "blog" (a schematic to read).
VENDOR_KIND = {"pcbway-gtu": "projects", "cryptid": "repo", "rwlpedal": "repo", "scientificguitarist": "repo", "sheepygit": "repo", "bentfishbowl": "blog", "effdub": "blog", "expanon": "archive", "schalltechnik": "blog"}

# The site owner's own designs: their schematic and photo are served, not only linked.
OWNER_VENDORS = {"cryptid"}

# A caution shown on every circuit page of a vendor, next to the buy link.
VENDOR_WARNING = {
    "moonn": "Moonn is a one-person shop and can be slow to ship, sometimes by weeks. Orders do arrive; allow for the wait.",
    "pcbguitarmania": "Builders widely report inconsistent quality from PCB Guitar Mania boards, and whether a given "
                      "board works is a gamble. Read recent forum reports before ordering.",
}


# Knob names that are acronyms stay in capitals when the rest are title-cased ('EQ', not 'Eq').
_ACRONYM_KNOBS = {"EQ", "LFO", "HPF", "LPF", "HP", "LP", "OD", "FX", "VCF", "VCA", "ENV", "BPM"}


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 60000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")   # several vendor scrapers write concurrently
    except sqlite3.OperationalError:
        pass  # another process already switched it; WAL persists in the file
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    if 'variant' not in [r[1] for r in conn.execute('PRAGMA table_info(bom)')]:
        conn.execute("ALTER TABLE bom ADD COLUMN variant TEXT DEFAULT ''")
    # last_listed: the date of the last full vendor scrape that found the board; delisted: the date a
    # full scrape first found it gone ('' while listed). A board the vendor drops is kept, not deleted.
    cols = [r[1] for r in conn.execute('PRAGMA table_info(circuits)')]
    if 'last_listed' not in cols:
        conn.execute("ALTER TABLE circuits ADD COLUMN last_listed TEXT DEFAULT ''")
        conn.execute("UPDATE circuits SET last_listed = substr(scraped_at, 1, 10)")
    if 'delisted' not in cols:
        conn.execute("ALTER TABLE circuits ADD COLUMN delisted TEXT DEFAULT ''")
    for vid, (name, url, note) in VENDORS.items():
        conn.execute("INSERT OR IGNORE INTO vendors(id,name,url,license_note) VALUES (?,?,?,?)",
                     (vid, name, url, note))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_CONTROL_ALIAS = {"vol": "volume", "lvl": "level", "lev": "level", "pres": "presence", "treb": "treble", "dist": "distortion",
                  "sus": "sustain", "spd": "speed", "fdbk": "feedback", "rpt": "repeats", "dpth": "depth", "freq": "frequency",
                  "res": "resonance", "bal": "balance", "att": "attack", "rel": "release", "thresh": "threshold"}


_CONTROL_JUNK = {"the", "these", "that", "this", "such", "shown", "here", "with", "any", "all", "and", "for", "not", "option", "install",
                 "connect", "convention", "boards", "board", "other", "used", "use", "works", "well", "remained", "touching", "transistor",
                 "potentiometers", "potentiometer", "pots", "pot", "alpha", "bourns", "leds", "two leds", "six potentiometers", "one", "two", "three", "see", "note", "txt", "val"}


def _dedupe_controls(names: list[str]) -> list[str]:
    """One knob, one name: exact repeats go, and when a doc section and a parts table name the
    same knob two ways (Vol and Volume) the longer spelling wins. Prose words that OCR pairs
    with a nearby value ("Install", "Shown") are dropped."""
    out: list[str] = []
    by_key: dict[str, int] = {}
    for n in (x.strip() for x in names if x.strip() and x.strip().lower() not in _CONTROL_JUNK):
        key = _CONTROL_ALIAS.get(n.lower(), n.lower())
        if key in by_key:
            if len(n) > len(out[by_key[key]]):
                out[by_key[key]] = n
            continue
        by_key[key] = len(out)
        out.append(n)
    return out


_BASED_ON_FILLER = re.compile(r"^(?:(?:(?:old|early|later|newer|original|first|second) version of(?: the)?|now[- ]discontinued|long[- ]discontinued|discontinued|"
                              r"the|an?|rare|classic|famous|legendary|iconic|popular|venerable|infamous|original|vintage|old)\s+)+", re.I)


def _clean_based_on(text: str) -> str:
    """'rare Last Gasp Arts Green Monster' -> 'Last Gasp Arts Green Monster': the original's
    name without the adjectives a description wraps it in, and without a trailing clause."""
    t = _BASED_ON_FILLER.sub("", text.strip())
    t = re.split(r",\s*(?:which|that|but|and it|as )", t)[0]
    t = re.sub(r"\s+(?:v|this|it|itself)$", "", t).strip(" ,.;")
    return t


def _fix_micro_read_as_pico(rows: list) -> None:
    """OCR reads the micro sign as a p (Vision and tesseract both): '1µ' comes out as 1p. A
    capacitor under 2pF is never a pedal part, so a machine-read one is taken as µF. Checked on
    every such row in the library (Big Muff, Rattus, SSM2166, panner, EA Tremolo); larger values
    such as 100p for 100µ are left alone, as 100pF is a real value."""
    for r in rows:
        if r.category != "C" or not ("OCR" in r.notes or "from schematic" in r.notes) or not 0 < r.sort_key < 2e-12:
            continue
        m = re.match(r"^(\d*\.?\d+)\s?[pP]", r.value)
        if m:
            was = r.value
            r.value = m.group(1) + "µF" + r.value[m.end():].lstrip("Ff")
            r.norm_value, r.category = "", "C"
            normalize_row(r)
            r.notes = (r.notes + f"; read as {was}").strip("; ")


def _fix_stray_digits(rows: list) -> None:
    """OCR reads R11 as R111 and C14 as C141 now and then. An OCR row whose number sits far
    outside the board's range for that prefix is renamed to the designator one dropped digit
    gives, when that lands inside the range and is not already taken in the same variant."""
    by_pre: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        m = re.fullmatch(r"([A-Z]{1,3})(\d{1,3})", r.ref)
        if m:
            by_pre.setdefault((r.variant, m.group(1)), []).append(int(m.group(2)))
    for r in rows:
        if "OCR" not in r.notes:
            continue
        m = re.fullmatch(r"([A-Z]{1,3})(\d{3})", r.ref)
        if not m:
            continue
        pre, num = m.group(1), int(m.group(2))
        others = [n for n in by_pre.get((r.variant, pre), []) if n != num]
        low = [n for n in others if n < 100]  # two strays must not vouch for each other (C141 and C412 on one board)
        base = max(low) if len(low) >= 3 else (max(others) if others else 0)
        if not base or num <= 3 * base:
            continue
        taken = set(by_pre.get((r.variant, pre), []))
        digits = m.group(2)
        for cand in (digits[:-1], digits[1:], digits[0] + digits[2]):
            n = int(cand)
            if 0 < n <= base + 2 and n not in taken:
                r.ref = f"{pre}{n}"
                r.notes = (r.notes + f"; read as {pre}{digits}").strip("; ")
                taken.add(n)
                break


def _dedupe_named_knobs(bom: list) -> list:
    """One knob read twice ('Level' from the schematic, 'LEVEL' from the parts table OCR) is one row.
    Within a build variant, pots and trimmers with the same name (ignoring case, spaces and
    underscores) collapse to the reading whose value parses, preferring a text table, then the
    schematic, then OCR. Quantity-named shopping-list rows ('×1') are different parts and stay."""
    def source_rank(r) -> int:
        n = (r.notes or "").lower()
        return 2 if "ocr" in n else 1 if "from schematic" in n else 0
    best: dict[tuple[str, str], object] = {}
    for r in bom:
        if r.category not in ("POT", "TRIM") or r.ref.startswith("×"):
            continue
        key = (r.variant or "", re.sub(r"[\s_]+", "", r.ref).upper())
        cur = best.get(key)
        if cur is None or ((r.sort_key or 0) > 0, -source_rank(r)) > ((cur.sort_key or 0) > 0, -source_rank(cur)):
            best[key] = r
    keep = {id(r) for r in best.values()}
    return [r for r in bom if r.category not in ("POT", "TRIM") or r.ref.startswith("×") or id(r) in keep]


def mark_listing(conn: sqlite3.Connection, vendor: str, seen: set[str], today: str) -> tuple[int, int, bool]:
    """After a full scrape of a vendor: boards it listed are marked listed today, boards it no longer
    lists are marked delisted (first date missing kept) and kept in the library. A scrape that found
    far fewer boards than the library holds as listed is a broken scrape (site down, layout changed),
    not a closing-down sale, so nothing is marked then. Returns (listed, newly delisted, applied)."""
    listed_before = conn.execute("SELECT COUNT(*) FROM circuits WHERE vendor=? AND COALESCE(delisted,'')=''", (vendor,)).fetchone()[0]
    if listed_before >= 10 and len(seen) < 0.5 * listed_before:
        return len(seen), 0, False
    ids = list(seen)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        conn.execute(f"UPDATE circuits SET last_listed=?, delisted='' WHERE id IN ({','.join('?' * len(chunk))})", (today, *chunk))
    candidates = [(r[0], r[1]) for r in conn.execute("SELECT id, url FROM circuits WHERE vendor=? AND COALESCE(delisted,'')=''", (vendor,))
                  if r[0] not in seen]
    # A listing can leave out live boards (an incomplete sitemap, a paginated catalogue that shifted),
    # so a board is only marked when its own page is gone as well.
    gone = [cid for cid, url in candidates if not _page_alive(url)]
    for cid in gone:
        conn.execute("UPDATE circuits SET delisted=? WHERE id=?", (today, cid))
    return len(seen), len(gone), True


def _page_alive(url: str) -> bool:
    """Whether a product page still answers: a 404 or 410, or a redirect to a page without the
    product's path (a shop's home or category page), means it is gone. A network error counts as
    alive, since one failed request should not delist a board."""
    import time
    import httpx
    from urllib.parse import urlparse
    if not url:
        return False
    try:
        time.sleep(1.0)
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (akashic parts library; +https://akashic.cryptideffects.com)"},
                      follow_redirects=True, timeout=30)
    except httpx.HTTPError:
        return True
    if r.status_code in (404, 410):
        return False
    path = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].lower()
    return not path or path in str(r.url).lower()


# Knob names beyond the pairing's own list, accepted when a scan is the only source of the name.
_KNOB_WORDS = {"REPEAT", "WAVE", "PEAK", "CLOCK", "AMPLITUDE", "FREQUENCY", "FREQ", "NOTCH", "TEMPO", "DISTORTION",
               "SENSITIVITY", "TUNE", "WAH", "EMPHASIS", "MOD", "MODULATION", "FINE", "ENVELOPE", "OCTAVE", "LENGTH",
               "THRESH", "GATE", "Q", "CONTOUR", "SUB", "FILTER", "BALANCE", "CLEAN", "EDGE", "TILT", "WARMTH"}


def upsert_circuit(conn: sqlite3.Connection, c: Circuit) -> None:
    from .corrections import apply as apply_corrections
    from .pdf import _expand_range_rows
    c.bom = _expand_range_rows(c.bom)  # 'Q1-2 2N5088' is Q1 and Q2, whichever parser read it
    c.bom = _dedupe_named_knobs(c.bom)
    from .normalize import is_prose_value
    c.bom = [r for r in c.bom if not is_prose_value(r.category, r.value)]  # 'for', 'Clipping', 'empty or your choice' as a part
    # 'A5', '16', '1' is never a pot or trimmer value: OCR prose ('WORKS  A5') or a schematic pin number
    c.bom = [r for r in c.bom if not (r.category in ("POT", "TRIM") and re.fullmatch(r"[ABCW]?\d{1,2}", r.value.strip()))]
    _fix_stray_digits(c.bom)
    _fix_micro_read_as_pico(c.bom)
    c.bom = apply_corrections(c.id, c.bom)  # last: hand fixes are keyed by the designators as stored
    from .corrections import CONTROLS, TRANSCRIBED
    if c.id in CONTROLS:
        c.controls = list(CONTROLS[c.id])
    elif c.id in TRANSCRIBED or not c.controls or (len(c.controls) == 1 and re.fullmatch(r"\d+ knobs?", c.controls[0])):
        # The adapter read its controls before the hand fixes ran, or could only count the knobs. Names
        # replace it only when every knob has one: 'RV1', 'Pot', '50K' or 'B1M' are not names.
        # A knob name read off a scan must be a word knobs are called: OCR turns VOLUME 1 into
        # 'Volumel' and DS-1's TONE into 'Vtav'. Names from a text table are taken as written.
        from .pdf import _CONTROL_WORDS
        known = _CONTROL_WORDS | _KNOB_WORDS
        pot_rows = [r for r in c.bom if r.category == "POT"]
        pots = [r.ref for r in pot_rows]
        machine = {r.ref for r in pot_rows if "OCR" in r.notes or "from schematic" in r.notes}
        named = [p for p in dict.fromkeys(pots) if re.fullmatch(r"[A-Za-z][A-Za-z. /\-]{2,}\d?", p)
                 and not re.fullmatch(r"(?:POT|VR|RV|P)\d*", p, re.I)
                 and (p not in machine or re.sub(r"\s*\d$", "", p).upper() in known)]
        if pots and len(named) == len(dict.fromkeys(pots)):
            c.controls = [p.title() if p.isupper() and p not in _ACRONYM_KNOBS else p for p in named]
    c.controls = _dedupe_controls(c.controls)
    c.based_on = _clean_based_on(c.based_on) if c.based_on else c.based_on
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """INSERT INTO circuits (id,vendor,slug,name,subtitle,based_on,description,category,
             effect_type,tags,enclosure,controls,difficulty,price,currency,sku,in_stock,url,
             doc_url,doc_local,extra_docs,image_url,schematic_local,schematic_page,doc_version,scraped_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, subtitle=excluded.subtitle, based_on=excluded.based_on,
             description=excluded.description, category=excluded.category,
             effect_type=excluded.effect_type, tags=excluded.tags, enclosure=excluded.enclosure,
             controls=excluded.controls, difficulty=excluded.difficulty, price=excluded.price,
             currency=excluded.currency, sku=excluded.sku, in_stock=excluded.in_stock,
             url=excluded.url, doc_url=excluded.doc_url, doc_local=excluded.doc_local,
             extra_docs=excluded.extra_docs, image_url=excluded.image_url,
             schematic_local=excluded.schematic_local, schematic_page=excluded.schematic_page,
             doc_version=excluded.doc_version, scraped_at=excluded.scraped_at""",
        (c.id, c.vendor, c.slug, c.name, c.subtitle, c.based_on, c.description, c.category,
         c.effect_type, json.dumps(c.tags), c.enclosure, json.dumps(c.controls), c.difficulty,
         c.price, c.currency, c.sku, None if c.in_stock is None else int(c.in_stock), c.url,
         c.doc_url, c.doc_local, json.dumps(c.extra_docs), c.image_url, c.schematic_local,
         c.schematic_page, c.doc_version, now),
    )
    conn.execute("DELETE FROM bom WHERE circuit_id = ?", (c.id,))
    conn.executemany(
        "INSERT INTO bom(circuit_id,position,ref,value,part_type,notes,category,norm_value,sort_key,variant) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(c.id, i, r.ref, r.value, r.part_type, r.notes, r.category, r.norm_value, r.sort_key, r.variant)
         for i, r in enumerate(c.bom)],
    )
