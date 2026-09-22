"""C2C Electronics (Conspiracy to Commit Electronics, formerly Sushi Box FX) adapter. A
WooCommerce store of all-tube high-voltage PCB sets; the Store API lists the products and
each product page links a build document (a PDF on the site or Google Drive, one Google
Doc). The documents set their parts list as a positional Comment / Description
[/ Designator] / Quantity / Link table whose cells wrap onto the lines above and below."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..docx import read_docx
from ..gsheet import grid_bom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text
from .deadendfx import _drive_download

BASE = "https://c2celectronics.com"
API = f"{BASE}/wp-json/wc/store/v1/products?category=diy-project&per_page=100"
_HEAD = re.compile(r"^\s*Comment\s+Description\s+(?:Designator\s+)?(?:Quantity|Qty)\b")
_HARDWARE = re.compile(r"socket|header|jack|knob|enclosure|footswitch|standoff|screw|wire|nut\b|washer|shield", re.I)
_DESIG = re.compile(r"^[A-Z]{1,4}\d{1,3}[A-Z]?$")
_ORIG = re.compile(r"(?:based on|inspired by|recreation of|clone of)\s+(?:the\s+)?(?:vintage |legendary |popular |classic |famous )?"
                   r"(?:[A-Z0-9]+ channel of the\s+)?([A-Z][\w/&.'-]*(?:\s+[A-Z0-9][\w/&.'-]*)*)(?:\s+(preamp))?")
_BOILER = re.compile(r"[^.]*(?:not a beginner project|not responsible for|as affordable and as easy|pre-drilled enclosure|build document with|"
                     r"daughter ?board|footswitch PCB|PCB set for building)[^.]*\.\s*", re.I)
_WOO_CATEGORY = {"tremolo": "Tremolo", "buffer": "Buffer", "utility": "Utility", "tube-preamp": "Preamp / Amp-in-a-box"}


def _split_value(comment: str) -> tuple[str, str]:
    """'10uF 250V' -> ('10uF', '250V'); '*A1M/B1M/C1M' -> ('A1M', 'or B1M/C1M'); '130p 50V (or 120pF)' -> ('130p', '50V; or 120pF')."""
    c = comment.strip().lstrip("*")
    notes: list[str] = []
    m = re.search(r"\((?:or|alt\.?)\s+([^)]+)\)", c, re.I)
    if m:
        notes.append("or " + m.group(1)); c = c[:m.start()].strip()
    m = re.match(r"^(\S+)\s+(\d+V)$", c)
    if m:
        c, _ = m.group(1), notes.append(m.group(2))
    if re.match(r"^[ABCW]\d+[kKM]?/[ABCW]\d+", c):
        first, rest = c.split("/", 1)
        notes.append("or " + rest); c = first
    c = re.sub(r"\s+On/(?:Off/)?On$", "", c, flags=re.I)
    if re.search(r"\s+Dual$", c, re.I):
        c, _ = re.sub(r"\s+Dual$", "", c, flags=re.I), notes.append("dual gang")
    c = re.sub(r"^SW\s+", "", c)
    m = re.match(r"^(\S+)\s*(?:\bor\b|/)\s*(\S+)$", c)  # '12AT7 or 12AX7', '12AT7 /12AX7'
    if m and not re.match(r"^[ABCW]\d", c):
        c = m.group(1); notes.append("or " + m.group(2))
    c = re.sub(r"\s+or$", "", c)
    return c, "; ".join(notes)


_RUNNING = re.compile(r"^\s*(?:Conspiracy to Commit Electronics|Sushi Box FX)\s*[–-].*Build Instructions|^\s*\d{1,2}\s*$")
_DESIG_LIST = re.compile(r"^(?:[A-Z]{1,4}\d{1,3}[A-Z]?,?\s*)+$")
_LINK = re.compile(r"^(?:Tayda|AES|SBP|PPCB|PedalPCB|AP|Mouser|Digikey|Amazon|TubeDepot)(?:\s+Link)?$", re.I)


def _assign(line: str, names: list[str], starts: list[int]) -> dict[str, str]:
    """Split a table line into chunks (runs separated by two or more spaces) and give each to a
    column: designator lists, bare quantities and vendor links by content, the rest by the
    nearest column start. Wrapped fragments are often centred, so slicing by position alone
    puts half a designator list into the description."""
    out: dict[str, str] = {}
    for m in re.finditer(r"\S+(?: \S+)*", line):
        chunk, pos = m.group(0), m.start()
        past_comment = pos >= starts[names.index("Description")] - 2
        if past_comment and "Designator" in names and _DESIG_LIST.match(chunk):
            col = "Designator"
        elif re.fullmatch(r"\d{1,2}", chunk) and pos > starts[names.index("Description")] + 8:
            col = "Quantity"
        elif past_comment and _LINK.match(chunk):
            col = "Link"
        else:  # nearest column start; wrapped cells are centred, so a start up to 8 columns to the right still counts
            col = min(zip(names, starts), key=lambda ns: abs(ns[1] - pos) if ns[1] <= pos + 8 else 10_000)[0]
            if col in ("Quantity", "Qty", "Link", "Alternate"):
                col = "Description" if pos < starts[-1] else "Link"
        out[col] = (out.get(col, "") + " " + chunk).strip()
    return out


def _table(pages: list[str]) -> tuple[list[BomRow], str, int, int]:
    """Read the document's parts table. Returns (rows, enclosure, pot count, toggle count).
    A line without a quantity is a fragment of the record above or below it (values,
    descriptions and designator lists wrap both ways); the table runs across pages without
    repeating its header and ends at a footnote or a paragraph of prose."""
    records: list[list[str]] = []
    designated = False
    cols: list[int] | None = None
    names: list[str] = []
    pending: list[list[str]] = []
    for page in pages:
        for line in page.splitlines():
            if _HEAD.match(line):
                names = re.findall(r"Comment|Description|Designator|Quantity|Qty|Link|Alternate", line)
                names = ["Quantity" if n == "Qty" else n for n in names]
                cols = [line.index(n) for n in re.findall(r"Comment|Description|Designator|Quantity|Qty|Link|Alternate", line)]
                designated = designated or "Designator" in names
                pending = []
                continue
            if cols is None or not line.strip() or _RUNNING.match(line):
                continue
            rec = _assign(line, names, cols)
            qty = rec.get("Quantity", "")
            if not re.fullmatch(r"\d+", qty):
                if line.strip().startswith("*") or (not line[0].isspace() and len(line.strip()) > 45) or re.match(r"^\s*(?:Schematic|Board Layout|Drill Template)", line):
                    cols = None  # a footnote, a heading or prose after the table
                    continue
                frag = [rec.get("Comment", ""), rec.get("Description", ""), rec.get("Designator", "")]
                prev = records[-1] if records and not pending else None
                if prev is not None and (prev[2].endswith(",") or frag[0].startswith("(") or (not prev[0] and frag[0]) or (not prev[1] and frag[1])):
                    for i in range(3):
                        prev[i] = (prev[i] + " " + frag[i]).strip()
                else:
                    pending.append(frag)
                continue
            rec_ = [rec.get("Comment", ""), rec.get("Description", ""), rec.get("Designator", ""), qty]
            for frag in pending:
                for i in range(3):
                    rec_[i] = (frag[i] + " " + rec_[i]).strip()
            pending = []
            records.append(rec_)
    rows: list[BomRow] = []
    seen: set[str] = set()
    enclosure = ""
    pots = toggles = 0
    for comment, desc, desig, qty in records:
        if not comment:
            continue
        if re.search(r"enclosure", desc, re.I):
            enclosure = enclosure or find_enclosure(comment)
            continue
        if _HARDWARE.search(desc) or _HARDWARE.search(comment) or comment.lower() in ("knobs", "led") and not _DESIG.match(desig):
            continue
        value, notes = _split_value(comment)
        is_pot = bool(re.search(r"potentiometer", desc, re.I))
        is_sw = bool(re.search(r"toggle|switch|rotary", desc + " " + comment, re.I)) and not is_pot
        if is_pot:
            pots += int(qty)
        if is_sw:
            toggles += int(qty)
        if designated:
            refs = [r.strip() for r in re.split(r"\s*,\s*", desig) if r.strip()]
            for ref in refs:
                if _DESIG.match(ref):
                    cat = ""
                elif is_pot and re.fullmatch(r"[A-Z][A-Za-z0-9 ./-]{1,17}", ref):
                    cat, ref = "POT", ref.title() if ref.isupper() else ref
                elif is_sw and re.fullmatch(r"[A-Z][A-Za-z0-9 ./-]{1,17}", ref):
                    cat, ref = "SW", ref.title() if ref.isupper() else ref
                else:
                    continue
                if ref.upper() in seen:
                    continue
                nr = normalize_row(BomRow(ref=ref, value=value, part_type=desc, notes=notes, category=cat))
                if cat or is_plausible(nr):
                    seen.add(ref.upper())
                    rows.append(nr)
        else:
            cat = "POT" if is_pot else "SW" if is_sw else ""
            nr = normalize_row(BomRow(ref=f"×{qty}", value=value, part_type=desc, notes=("shopping list; " + notes).strip("; "), category=cat))
            if cat or is_plausible(nr):
                rows.append(nr)
    return rows, enclosure, pots, toggles


@register
class C2C(Adapter):
    vendor = "c2c"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(API, ".json")
        for p in (json.loads(raw) if raw else []):
            self.products[p["slug"]] = p
            yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        cats = {c["slug"] for c in p.get("categories", [])}
        if cats & {"magnetics", "finished-pedal"}:
            return None
        page = self.f.get_text(p["permalink"], ".html") or ""
        m = re.search(r'<div class="woocommerce-product-details__short-description">(.*?)</div>', page, re.S)
        body = m.group(1) if m else ""
        docs = [u for u in re.findall(r'href="([^"]+)"', body) if re.search(r"\.pdf|drive\.google|docs\.google", u, re.I)]
        if not docs:
            return None
        doc_url = _html.unescape(docs[0])
        text_web = html_to_text(body)
        description = clean_text(_BOILER.sub("", text_web))
        name = clean_text(_html.unescape(p["name"]))
        name = re.sub(r"\s*(?:DIY\s+)?PCB(?:\s+Set)?$", "", name, flags=re.I)
        prices = p.get("prices") or {}
        minor = int(prices.get("currency_minor_unit", 2))
        price = int(prices["price"]) / (10 ** minor) if prices.get("price") else None
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], description=description, price=price,
                    currency=prices.get("currency_code") or "USD", in_stock=p.get("is_in_stock"), doc_url=doc_url,
                    image_url=(p.get("images") or [{}])[0].get("src", ""))
        text = ""
        if "docs.google.com/document" in doc_url:
            fid = re.search(r"/d/([A-Za-z0-9_-]{20,})", doc_url).group(1)
            path = self.f.get_file(f"https://docs.google.com/document/d/{fid}/export?format=docx", ".docx")
            if path and path.read_bytes()[:2] == b"PK":
                paras, tables, _ = read_docx(path)
                text = "\n".join(paras)
                for t in tables:
                    rows, enc = grid_bom(t)
                    if len(rows) > len(c.bom):
                        c.bom, c.enclosure = rows, enc
                c.controls = [r.ref.title() for r in c.bom if r.category == "POT"]
        else:
            fetch = _drive_download(doc_url) if "drive.google" in doc_url else doc_url
            path = self.f.get_file(fetch, ".pdf")
            if path and path.read_bytes()[:5] == b"%PDF-":
                res = process_document(path, self.vendor, slug)
                c.doc_local, c.bom, c.schematic_local, c.schematic_page = res["doc_local"], res["bom"], res["schematic_local"], res["schematic_page"]
                pages = pdf_text_pages(path)
                text = "\n".join(pages)
                rows, enc, pots, toggles = _table(pages)
                if len(rows) > len(c.bom):
                    c.bom = rows
                c.enclosure = enc
                sch = [i for i, pg in enumerate(pages, 1) if re.search(r"^\s*Schematic", pg, re.M)]
                if sch:
                    c.schematic_page = sch[-1]  # the audio schematic follows the power supply's
                named = [r.ref.title() for r in c.bom if r.category == "POT" and not r.ref.startswith("×")]
                if named:
                    c.controls = named + [r.ref for r in c.bom if r.category == "SW" and not r.ref.startswith("×")]
                elif pots:
                    c.controls = [f"{pots} knobs" if pots > 1 else "1 knob"] + (["Toggle switch"] * toggles)
        for r in c.bom:
            r.value = re.sub(r"\s+regulator$", "", r.value, flags=re.I)
        intro = re.sub(r"\s+", " ", text[:1500])
        intro = intro[:intro.find("DISCLAIMER")] if "DISCLAIMER" in intro else intro
        m = _ORIG.search(intro) or _ORIG.search(text_web)
        if m and not re.match(r"^[A-Z]{1,3}\d{3,}", m.group(1)):  # "based on the PT2399 delay IC" is not an original
            c.based_on = clean_text(m.group(1) + (" Preamp" if m.group(2) and " " not in m.group(1) else ""))
        c.enclosure = c.enclosure or find_enclosure(text)
        c.category = next((v for k, v in _WOO_CATEGORY.items() if k in cats and k != "tube-preamp"), "") or classify(name, c.based_on, intro or description)
        if "tube-preamp" in cats and (c.category in ("Boost", "Utility", "Other", "Preamp / Amp-in-a-box")
                                      or (c.category == "Overdrive" and not re.search(r"overdrive", intro.split(". ")[0], re.I))):
            c.category = _WOO_CATEGORY["tube-preamp"]  # the vendor files these as tube preamps; only a stated drive/delay/reverb overrides that
        return c
