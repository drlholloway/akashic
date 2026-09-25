"""Moody Sounds adapter: a Swedish WooCommerce kit shop (SEK). The kits category holds
Moody's own designs, official BJFE (Bjorn Juhl), Carlin and Vallhagen kits, Lehle clones and
BYOC kits sold with BYOC's instruction PDFs, plus an archive of discontinued kits kept online
for their documentation. Moody's own PDFs have a broken text layer, so their packing lists
('R1, R7 = 4k7 (yellow purple ...)') are read by OCR of the first pages; BYOC checklists
('2 - 1k', '3 - A100k (VOLUME, DISTORTION, FILTER)') come from the text layer."""
from __future__ import annotations

import html as _html
import json
import re
from pathlib import Path
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import _tesseract_cached, pdf_text_pages, process_document, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://en.moodysounds.com"
API = f"{BASE}/wp-json/wc/store/v1/products?per_page=100&category=29"  # byggsatser = kits
_SKIP = re.compile(r"diy galleri|Boston|Klisterdekal|\bmodul\b|Modkit|Uppgradering|bricka|kopplingsschema|Signaltestare|studio kit|Reamping|"
                   r"Relästyrd|Dying Battery|Loop kit|AB box|Attenuator|Buffer|Splitter|bypass|Looper|Amp Selector|Blend kit|Switch mot jord|\bmodule\b", re.I)
_VARIANT = re.compile(r"\s*\((?:kort och komponenter|exkl\. låda|ink\. LPB module|med leds|utan LED.s)\)|\s*utan box|\s*(?:röd|gul) fasel", re.I)
_ORIG = re.compile(r"^(.*?)\s*\b(?:klon|clone)\b(?:\s*\(utökad\))?(?:\s+mini)?\s*[”\"“]?\s*(.*?)\s*[”\"“]?$", re.I)
_BRAND = {"TS-808": "Ibanez TS-808", "TS 808": "Ibanez TS-808", "RAT": "ProCo RAT", "ProCo RAT": "ProCo RAT", "Phase 90": "MXR Phase 90", "Klon": "Klon Centaur",
          "Fuzz Face": "Dallas Arbiter Fuzz Face", "Big Muff": "Electro-Harmonix Big Muff", "Super hard on": "ZVex Super Hard-On", "EA Tremolo": "EA Tremolo",
          "Dynacomp": "MXR Dyna Comp", "Ross Compressor": "Ross Compressor", "Orange Squeezer": "Dan Armstrong Orange Squeezer", "Red Llama": "Way Huge Red Llama",
          "Mutron Octave Divider": "Mu-Tron Octave Divider", "Acoustic 360": "Acoustic 360 preamp", "Tonebender MKII": "Sola Sound Tone Bender MkII",
          "Tycho Brahe Octavia": "Tycobrahe Octavia", "Univox Superfuzz": "Univox Super-Fuzz", "Marhsall Bluesbreaker": "Marshall Blues Breaker",
          "Colorsound Overdriver": "Colorsound Overdriver", "Analog Chorus": "Boss CE-2", "Phaser 90": "MXR Phase 90", "Marshall Guvnor": "Marshall Guv'nor",
          "Marshall Shredmaster": "Marshall Shred Master", "Boss SG-1": "Boss SG-1 Slow Gear", "Pearl OD-05": "Pearl OD-05 Overdrive", "Maxon OD-820": "Maxon OD-820"}
_SWEDISH = {"Volym": "Volume", "Nivå": "Level", "Ton": "Tone", "Hastighet": "Speed", "Djup": "Depth", "Intervall": "Interval"}
_DOC_BAD = re.compile(r"schem|artwork|drill|info|mod|recesion|modifieringar|datasheet|Installation|Bygger|-fra-|manual", re.I)
_EQ = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,3}\d{1,3}(?:\s*,\s*[A-Z]{1,3}\d{1,3})*)\s*=\s*([^=()\n]{1,40}?)\s*(?:\(([^()\n]*)\))?\s*(?=[A-Z]{1,3}\d{1,3}\s*[,=]|$|\n)", re.M)
_QTY = re.compile(r"^\s*(\d+)\s*[-–]\s*(.+?)\s*$", re.M)
_SECTION = re.compile(r"^\s*(Resistors|Capacitors|Diodes|Transistors|ICs?|Sockets|Potentiometers|Switches|Hardware|Other)\s*:", re.I | re.M)


_VALUE_TOKEN = re.compile(r"(?<![A-Za-z0-9])(\d+(?:[.,]\d+)?\s?(?:[pnuµ]F?|[kKM](?:\d+)?|[RΩ]|ohm)?\d*|(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{2,}|LED|Ge|Si)(?![A-Za-z0-9])")


def _broken_text(pages: list[str]) -> bool:
    """Moody's PDFs carry a text layer whose words are shattered into one-letter lines."""
    lines = [ln.strip() for ln in "\n".join(pages[:3]).splitlines() if ln.strip()]
    return len(lines) > 40 and sum(len(ln) <= 3 for ln in lines) / len(lines) > 0.12


def parse_eq_list(text: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()
    for refs, value, note in _EQ.findall(text):
        value = re.sub(r"\s*(?:©|O|Q)$", "", value.strip())  # OCR of the ohm sign
        value = re.sub(r"^(\d+)\s+([kKM])\b", r"\1\2", value)
        value = re.sub(r"(?<=[A-Z])O(?=\d)|(?<=\d)O(?=\d)", "0", value)  # TLO72
        if not re.fullmatch(r"[A-Za-z0-9.,+/-]{1,10}|\d+(?:[.,]\d+)? ?[pnuµkKM]?[FΩ]?", value):
            mt = _VALUE_TOKEN.search(value)
            value = mt.group(1) if mt else value
        note = clean_text(note)
        cat = ""
        name = ""
        if refs.startswith("T") and re.search(r"regulator|78L|LM78|7805", value + " " + note, re.I):
            cat = "IC"
        if refs.startswith("P") and re.search(r"\blin\b|\blog\b|[ABC]\d+k|\d+k\s*[ABC]\b", value + " " + note, re.I):
            cat = "POT"
            m = re.match(r"^([A-Za-z][A-Za-z /-]{1,15}?)\s*(?:,|$)", note)
            name = m.group(1).strip() if m and not re.match(r"denoted|cylinder", m.group(1), re.I) else ""
            mv = re.search(r"denoted\s*[“\"']?\s*([ABCW]\s?\d+[kKM]?)", note)
            value = mv.group(1).replace(" ", "") if mv else value
        for ref in re.split(r"\s*,\s*", refs):
            key = ref.upper()
            if key in seen:
                continue
            r = normalize_row(BomRow(ref=name.title() if name else ref, value=value, notes="" if cat else "", category=cat))
            if cat or is_plausible(r):
                seen.add(key)
                rows.append(r)
    return rows


def parse_checklist(text: str) -> list[BomRow]:
    """BYOC 'Parts Checklist': quantity - value lines under section headings."""
    m = re.search(r"Parts Checklist for[^\n]*\n(.*?)(?:\n\s*Hardware:|\nPopulating|\Z)", text, re.S)
    if not m:
        return []
    rows: list[BomRow] = []
    section = ""
    for ln in m.group(1).splitlines():
        sm = _SECTION.match(ln)
        if sm:
            section = sm.group(1).lower()
            continue
        qm = _QTY.match(ln)
        if not qm or section in ("hardware", "sockets", "other"):
            continue
        qty, rest = qm.groups()
        value = re.sub(r"\s*\(.*$", "", rest).strip()
        note = (re.search(r"\(([^)]*)\)", rest) or [None, ""])[1]
        if section.startswith("pot"):
            names = [n.strip().title() for n in note.split(",") if re.fullmatch(r"[A-Za-z][A-Za-z /-]{1,15}", n.strip())]
            for n in names or [f"×{qty}"]:
                rows.append(normalize_row(BomRow(ref=n, value=value.split()[0], category="POT")))
            continue
        value = re.sub(r"\s+(?:ohm|film|ceramic disc|aluminum electrolytic|electrolytic|tantalum|or similar.*|\(.*)$", "", value, flags=re.I)
        ptype = {"resistors": "Resistor", "capacitors": "Capacitor", "diodes": "Diode", "transistors": "Transistor", "ic": "IC", "ics": "IC", "switches": "Switch"}.get(section, "")
        value = re.sub(r"^\.(\d)", r"0.\1", value).replace("pf", "pF").replace("uf", "uF")
        r = normalize_row(BomRow(ref=f"×{qty}", value=value, part_type=ptype, notes="shopping list"))
        if is_plausible(r) or r.category in ("D", "Q", "IC", "LED", "SW"):
            rows.append(r)
    return rows


def _ocr_pages(pdf: Path, vendor: str, slug: str, pages: Iterable[int]) -> str:
    out = []
    for pg in pages:
        png = CACHE_DIR / vendor / f"{slug}-p{pg}.png"
        if not png.exists():
            try:
                render_page(pdf, pg, png, dpi=200)
            except Exception:  # noqa: BLE001
                break
        out.append(_tesseract_cached(png, 6, tag=f"{slug}-{pg}"))
    return "\n".join(out)


@register
class Moody(Adapter):
    vendor = "moody"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        prods = []
        for page in (1, 2, 3):
            raw = self.f.get_text(f"{API}&page={page}", ".json")
            batch = json.loads(raw) if raw else []
            if not batch:
                break
            prods += batch
        names = {re.sub(r"\s+kit\s*$", "", _VARIANT.sub("", _html.unescape(p["name"])), flags=re.I).lower(): p["slug"] for p in prods if not _VARIANT.search(_html.unescape(p["name"]))}
        for p in prods:
            name = _html.unescape(p["name"])
            if _SKIP.search(name) or p["prices"]["price"] in ("0", 0):
                continue
            if _VARIANT.search(name):
                continue  # the board-only or box-less variant of a kit listed in full
            self.products[p["slug"]] = p
            yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        title = clean_text(_html.unescape(p["name"])).replace("”", '"').replace("“", '"')
        cats = {c["slug"] for c in p.get("categories", [])}
        based_on, name = "", title
        m = _ORIG.match(title)
        if m and m.group(2):
            based_on, name = m.group(1).strip(), m.group(2).strip('" ')
        elif m:
            based_on, name = m.group(1).strip(), title
        if m and not based_on and title.lower().startswith("klon"):
            based_on = "Klon Centaur"
        based_on = next((v for k, v in _BRAND.items() if based_on.lower().startswith(k.lower())), based_on)
        based_on = re.sub(r"\s*\(utökad\)", "", based_on).strip()
        name = re.sub(r"\s*\((?:kort och komponenter|utökad|exkl\. låda|inkl\. tank|ink\. LPB module)\)|(?:\s+minipedal)?\s+kit\s*$|\s+byggsats$", "", name, flags=re.I).strip('" ')
        name = re.sub(r"\s+kit\s+", " ", name).replace("Li’l", "Li'l")
        name = re.sub(r"\s+kit\s*$", "", name, flags=re.I)
        if not name or name.lower() == "kit":
            name, based_on = based_on, ""
        if "byoc" in name.lower() and not based_on:
            name = re.sub(r"^BYOC\s+", "", name)
        prices = p.get("prices") or {}
        desc = html_to_text(p.get("description") or p.get("short_description") or "")
        page = self.f.get_text(p["permalink"].replace("//moodysounds.com/", "//en.moodysounds.com/"), ".html") or ""
        pdfs = list(dict.fromkeys(re.findall(r'href="(https?://[^"]+\.pdf)"', page)))
        docs = sorted(pdfs, key=lambda u: (0 if re.search(r"instructions|-eng|eng\d|kiteng", u, re.I) else 1, 1 if _DOC_BAD.search(u.rsplit("/", 1)[-1]) else 0, 0 if "sve" in u or "swe" in u else 1))
        doc = next((u for u in docs if not _DOC_BAD.search(u.rsplit("/", 1)[-1])), docs[0] if docs else "")
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], based_on=based_on, description=desc[:700],
                    price=int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None,
                    currency=prices.get("currency_code", "SEK"), in_stock=p.get("is_in_stock"), doc_url=doc or p["permalink"],
                    image_url=(p.get("images") or [{}])[0].get("src", ""), enclosure=find_enclosure(desc), tags=["kit"])
        if "arkiv" in cats:
            c.tags.append("discontinued")
        if "byoc-byggsatser" in cats or re.search(r"byoc", " ".join(pdfs), re.I):
            c.tags.append("BYOC kit")
        for u in pdfs:
            if u != doc:
                c.extra_docs[u.rsplit("/", 1)[-1][:40]] = u
        if doc:
            pdf = self.f.get_file(doc, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                text = "\n".join(pages)
                res = process_document(pdf, self.vendor, slug)
                c.bom = max(res["bom"], parse_checklist(text), parse_eq_list(text), key=len)
                c.schematic_local, c.schematic_page = res["schematic_local"], res["schematic_page"]
                if len(c.bom) < 8 or _broken_text(pages):
                    ocr = _ocr_pages(pdf, self.vendor, slug, range(1, min(len(pages), 4) + 1))
                    c.bom = max(c.bom, parse_eq_list(ocr), parse_checklist(ocr), key=len)
                    if c.bom and c.bom is not res["bom"]:
                        for r in c.bom:
                            r.notes = (r.notes + "; OCR").strip("; ") if "OCR" not in r.notes else r.notes
                c.enclosure = c.enclosure or find_enclosure(text)
        c.category = classify(name, based_on, desc[:300])
        pots = [r for r in c.bom if r.category == "POT"]
        named = list(dict.fromkeys(_SWEDISH.get(n, n) for n in (re.sub(r"\s+Knobs?$", "", r.ref) for r in pots) if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}|×\d+", n)))
        n = sum(int(r.ref[1:]) if r.ref.startswith("×") else 1 for r in pots)
        c.controls = named or ([f"{n} knobs"] if n > 1 else ["1 knob"] if n else [])
        return c
