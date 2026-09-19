from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .models import Circuit
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
    "pcbway-gtu": ("PCBWay: Glory to Ukraine", "https://www.pcbway.com/project/member/?bmbno=19C5FC6C-66B1-46",
                   "Shared projects are CC BY-SA 3.0; schematic images may be shown with attribution. BOM and gerbers need a PCBWay login."),
}


# What the vendor sells: "shop" (a PCB), "projects" (order the board from a fab), "blog" (a schematic to read).
VENDOR_KIND = {"pcbway-gtu": "projects", "bentfishbowl": "blog", "expanon": "archive"}

# A caution shown on every circuit page of a vendor, next to the buy link.
VENDOR_WARNING = {
    "pcbguitarmania": "Builders widely report inconsistent quality from PCB Guitar Mania boards, and whether a given "
                      "board works is a gamble. Read recent forum reports before ordering.",
}


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


def _dedupe_controls(names: list[str]) -> list[str]:
    """One knob, one name: exact repeats go, and when a doc section and a parts table name the
    same knob two ways (Vol and Volume) the longer spelling wins."""
    out: list[str] = []
    by_key: dict[str, int] = {}
    for n in (x.strip() for x in names if x.strip()):
        key = _CONTROL_ALIAS.get(n.lower(), n.lower())
        if key in by_key:
            if len(n) > len(out[by_key[key]]):
                out[by_key[key]] = n
            continue
        by_key[key] = len(out)
        out.append(n)
    return out


def upsert_circuit(conn: sqlite3.Connection, c: Circuit) -> None:
    c.controls = _dedupe_controls(c.controls)
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
