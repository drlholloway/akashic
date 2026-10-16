"""Mod Electronics (MOD Kits DIY): complete pedal kits, sold through Amplified Parts. Most are wired
point to point on terminal strips, the Nexus series on a PCB. Each kit page links its instructions
and schematic as PDFs. A PCB kit's instructions hold a bill of materials the shared parsers read;
a terminal-strip kit's hold 'parts list' pages, drawings of every part captioned with its name,
stock number and quantity, read here. Mod Electronics PCBs sold without parts come from their build guides
on Amplified Parts, whose parts tables name every designator (amplifiedparts.py). The price and stock come from the kit's Amplified Parts page
(its schema.org Product data); while that store is down the kit is listed without a price."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import normalize_row
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document, schematic_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.modelectronics.com"
LISTINGS = ("/pedal-kits", "/pedal-amp-kits/discontinued")
_NOT_PEDALS = {"mod-101"}  # a tube amp kit on the discontinued page
_CATEGORY = {"tone-attack": "EQ / Filter", "step-ladder": "Utility",  # an active tone stack; a passive attenuator
             "pcb-odyssey": "Phaser", "pcb-axion": "Delay"}  # an optical phaser; a PT2399 delay with chorus
_DIFFICULTY = {"1": "Beginner", "2": "Easy", "3": "Medium", "4": "Advanced", "5": "Difficult"}
_FILE = re.compile(r'href="(https://www\.modelectronics\.com/sites/[^"]+\.pdf)"[^>]*>([^<]*)')
_STOCK = re.compile(r"(?<![\w-])[A-Z]{1,2}-[A-Z0-9][A-Za-z0-9./]*(?:-[A-Za-z0-9./]+)*(?![\w-])")  # 'R-A4D7K', 'P-Q2N5088', 'R-VAM100KL-SS'
_QTY = re.compile(r"\((\d{1,2})\)")
_SEG = re.compile(r"\S(?:.*?\S)?(?=\s{2,}|$)")
_NOTE = "from the kit's parts list"
# The PCB build guides: guide slug -> (name, original).
GUIDES = "https://www.amplifiedparts.com/pedal-guides/build-project-mod-electronics-"
PCB_GUIDES = {
    "amber": ("Amber", "Orange Squeezer"),
    "axion": ("Axion", ""),
    "deluge": ("Deluge", "Noah's Ark Distortion M"),
    "germanium_fuzz": ("Germanium Fuzz", "Dallas Arbiter Fuzz Face"),
    "memoria": ("Memoria", "Electro-Harmonix Small Clone"),
    "odyssey": ("Odyssey", ""),
    "quasar": ("Quasar", ""),
    "refraction": ("Refraction", ""),
    "tone-splendor": ("Tone Splendor MK2S", "Sola Sound Tone Bender MKII"),
}
_STORE = re.compile(r'href="(https?://www\.amplifiedparts\.com/products/K-[\w-]+)"')


def store_offer(page: str) -> tuple[float | None, bool | None]:
    """(price, in stock) from an Amplified Parts product page's schema.org Product data, or its price box."""
    for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue
        offers = data.get("offers") or []
        offer = (offers[0] if isinstance(offers, list) and offers else offers) or {}
        try:
            price = float(offer.get("price"))
        except (TypeError, ValueError):
            price = None
        avail = str(offer.get("availability") or "")
        if price:
            return price, (True if avail.endswith("InStock") else False if avail.endswith(("OutOfStock", "Discontinued", "SoldOut")) else None)
    # Some pages carry no Product data: the price and availability as shown ('$61<sup>.95</sup>', 'In Stock').
    m = re.search(r'class="sell-price[^"]*">\s*\$([\d,]+)(?:<sup>\.(\d+)</sup>)?', page)
    a = re.search(r'class="availability ([a-z_]+)"', page)
    if not m:
        return None, None
    stock = {"in_stock": True, "out_of_stock": False}.get(a.group(1)) if a else None
    return float(m.group(1).replace(",", "") + "." + (m.group(2) or "0")), stock


def _segments(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(0)) for m in _SEG.finditer(line)]


def parts_list_items(pages: list[str]) -> list[tuple[int, str, str]]:
    """(quantity, stock number, caption) for every part drawn on the 'PARTS LIST' pages. A caption sits
    above its stock number in the same column (now and then below it), the quantity to the right of
    the number or on the line under it."""
    out: list[tuple[int, str, str]] = []
    for page in pages:
        if not re.search(r"^\s*PARTS LIST\b", page, re.M | re.I) or re.search(r"TABLE OF CONTENTS", page, re.I):
            continue
        lines = page.split("\n")
        for i, line in enumerate(lines):
            stocks = list(_STOCK.finditer(line))
            for k, m in enumerate(stocks):
                end = stocks[k + 1].start() if k + 1 < len(stocks) else len(line)
                q = _QTY.search(line, m.end(), end)
                for j in (i + 1, i + 2):  # '(1)' dropped under the number by a label in the drawing
                    if q or j >= len(lines) or _STOCK.search(lines[j]):
                        break
                    q = next((x for x in _QTY.finditer(lines[j]) if m.start() - 4 <= x.start() < end + 12), None)
                if not q:
                    continue
                caption = ""
                for j in [i - 1, i - 2, i - 3, i + 1]:
                    if not 0 <= j < len(lines):
                        continue
                    near = [t for pos, t in _segments(lines[j]) if abs(pos - m.start()) <= 3 and not _STOCK.fullmatch(t) and not _QTY.fullmatch(t)]
                    if near:
                        caption = near[0]
                        break
                    if lines[j].strip() and j < i and any(abs(pos - m.start()) <= 3 for pos, _ in _segments(lines[j])):
                        break  # another part's stock number is right above: this one has no caption
                out.append((int(q.group(1)), m.group(0), caption))
    return out


_TABLE_HEAD = re.compile(r"^\s*Part\s+Value\s+Type\s*$", re.I)
_TABLE_ROW = re.compile(r"^\s*([A-Z][A-Za-z_]{0,9}\d{0,3})\s{2,}(\S+)\s+(\S.*?)\s*$")
_QTY_ROW = re.compile(r"^\s*([A-Z]{1,2}-[A-Z0-9][A-Za-z0-9./-]*)\s+Qty\s+(\d{1,2})\s+(\S.*?)\s*$")


def table_rows(pages: list[str]) -> list[BomRow]:
    """A PCB kit's bill of materials: 'Part  Value  Type' tables, one part to a line ('R5  8k2  2W PR02
    Metal Film Resistor'). Read here because the heading's columns are narrower than the rows under it."""
    rows: list[BomRow] = []
    for page in pages:
        inside = False
        for line in page.split("\n"):
            if _TABLE_HEAD.match(line):
                inside = True
            elif inside and (m := _TABLE_ROW.match(line)):
                value = re.sub(r"(?<=\d)Ω(?=K$)", "", m.group(2))  # 'B500ΩK' in the Seismic Shift's table is a B500K pot
                rows.append(normalize_row(BomRow(ref=m.group(1), value=value, part_type=m.group(3))))
    return rows


def offboard_items(pages: list[str]) -> list[tuple[int, str, str]]:
    """The parts off the board on a PCB kit, listed 'R-VAM500KA-SS  Qty 1  500KΩ Log 16mm Potentiometer'."""
    return [(int(m.group(2)), m.group(1), m.group(3)) for page in pages for line in page.split("\n") if (m := _QTY_ROW.match(line))]


def _ohms(code: str) -> str:
    """'4D7K' -> '4.7k', '100K' -> '100k', '2M' -> '2M', '470' -> '470R' (the stock numbers write a decimal point as D)."""
    m = re.fullmatch(r"(\d+)(?:D(\d+))?([KM]?)", code)
    if not m:
        return ""
    return m.group(1) + (f".{m.group(2)}" if m.group(2) else "") + ({"K": "k", "M": "M", "": "R"}[m.group(3)])


def item_row(qty: int, stock: str, caption: str) -> BomRow | None:
    """One parts-list item as a row, or None for hardware (jacks, screws, the enclosure, knobs, wire).
    The value comes from the caption where it has one and from the stock number where it does not:
    a group of pots is captioned once ('Potentiometers: 100KL and 100KA') and numbered one by one."""
    cap = caption.replace("µ", "u").strip("* ")
    head = stock.split("-", 1)[0]
    value = category = kind = ""
    if m := re.fullmatch(r"R-V[A-Z0-9]*?-?(\d+(?:D\d+)?[KM])(RA|A|L|C)?(?:-.*)?", stock):
        taper = "C" if re.search(r"reverse", cap, re.I) or m.group(2) in ("RA", "C") else {"A": "A", "L": "B"}.get(m.group(2) or "", "")
        taper = taper or ("A" if re.search(r"audio", cap, re.I) else "B" if re.search(r"linear", cap, re.I) else "")
        value, category, kind = taper + _ohms(m.group(1)).replace("R", ""), "POT", "Potentiometer"
    elif re.search(r"\bpot\b|potentiometer", cap, re.I) and (m := re.search(r"(\d+(?:\.\d+)?)\s?([kKM])", cap)):
        value, category, kind = m.group(1) + m.group(2).replace("K", "k"), "POT", cap
    elif head == "R" and (m := re.fullmatch(r"R-[A-Z](\d+(?:D\d+)?[KM]?)", stock)):
        value, category, kind = _ohms(m.group(1)), "R", "Resistor, 1/2W"
    elif re.search(r"capacitor", cap, re.I) and (m := re.search(r"(\d*\.?\d+)\s?([upn])F", cap)):
        value, category = f"{m.group(1)}{m.group(2)}F", "C"
        kind = "Electrolytic capacitor" if re.search(r"polarized|electrolytic", cap, re.I) else "Capacitor"
        kind += f", {v.group(0)}" if (v := re.search(r"\d+(?:\.\d+)?\s?k?V\b", cap)) else ""
    elif re.search(r"\bLED\b|light emitting", cap, re.I) and "switch" not in cap.lower():
        value, category = "LED", "LED"
    elif m := re.search(r"\b([1-4SD]P[1-4SDT]T)\b", cap):
        value, category, kind = m.group(1), "SW", cap
    elif re.search(r"BJT|darlington|MOSFET|JFET", cap, re.I) and (m := re.search(r"\(([A-Z0-9-]+)\)", cap)):
        value, category, kind = re.sub(r"(?<=\d)TAR$", "", m.group(1)), "Q", re.sub(r"\s*\(.*", "", cap)  # 'TAR': tape and reel
    elif re.search(r"diode", cap, re.I) and (m := re.search(r"\b(1N\d{2,4}[A-Z]?|BAT\d+)\b", cap)):
        value, category, kind = m.group(1), "D", re.sub(r"\s*\(?\b1N\d{2,4}[A-Z]?\)?\s*", " ", cap).strip().capitalize()
    elif re.search(r"regulator|effector|op.?amp|\bIC\b", cap, re.I) and (m := re.search(r"\(([A-Z0-9-]+)\)", cap)):
        value, category, kind = m.group(1), "IC", re.sub(r"\s*\(.*", "", cap)
    elif re.search(r"reverb module", cap, re.I) and (m := re.fullmatch(r"P-R(BTDR-\d[A-Z]?)(?:-.*)?", stock)):
        value, category, kind = m.group(1), "IC", "Reverb module"
    elif re.search(r"transformer", cap, re.I):
        value, category, kind = (re.search(r"\(([^)]*)\)", cap) or re.search(r"()", cap)).group(1).replace(" ", "") or stock, "XFM", "Audio transformer"
    elif re.search(r"inductor", cap, re.I) and (m := re.search(r"(\d+(?:\.\d+)?)\s?([mu]?H)", cap)):
        value, category, kind = m.group(1) + m.group(2), "L", "Inductor"
    elif re.search(r"\btube\b", cap, re.I) and "socket" not in cap.lower():
        value, category, kind = stock.split("-", 1)[1], "OTHER", cap
    elif head == "P" and not cap and (m := re.fullmatch(r"P-Q((?:2N|1N|MPS|BS|PF|BC|J)\w+)", stock)):
        value, category = m.group(1), "D" if m.group(1).startswith("1N") else "Q"
    if not value:
        return None
    return normalize_row(BomRow(ref=f"×{qty}", value=value, part_type=kind, category=category, notes=f"{_NOTE} ({stock})"))


@register
class ModElectronics(Adapter):
    vendor = "modelectronics"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.discontinued: set[str] = set()

    def list_targets(self) -> Iterable[str]:
        seen: set[str] = set()
        for path in LISTINGS:
            page = self.f.get_text(BASE + path) or ""
            for slug in re.findall(r'href="/product/([^"#?]+)"', page.split('id="main-content"', 1)[-1]):
                if slug in seen or slug in _NOT_PEDALS:
                    continue
                seen.add(slug)
                if "discontinued" in path:
                    self.discontinued.add(slug)
                yield slug
        for guide in PCB_GUIDES:
            yield "pcb-" + guide.replace("_", "-")

    def parse(self, slug: str) -> Circuit | None:
        if slug.startswith("pcb-"):
            return self._pcb(slug)
        url = f"{BASE}/product/{slug}"
        page = self.f.get_text(url)
        if not page:
            return None
        files = [(_html.unescape(u), clean_text(_html.unescape(label))) for u, label in _FILE.findall(page)]
        manual = next(((u, l) for u, l in files if re.search(r"instruction", l, re.I)), None)
        if not manual:
            return None  # an old kit whose documents are gone: nothing to index
        title = clean_text(_html.unescape(re.search(r"<title>([^<|]*)", page).group(1)))
        main = page.split('id="main-content"', 1)[-1].split("Product Files", 1)[0]
        body = re.sub(r"\s*\d\s*Build Difficulty.*", "", html_to_text(main), flags=re.S)
        body = clean_text(re.sub(r"^.*?\n", "", body, count=1) if body.lower().startswith(title.lower()) else body)
        body = clean_text(re.sub(r"^\s*>\s*$", "", body, flags=re.M))  # the breadcrumb's last arrow
        kind = body.split("\n", 1)[0].strip()  # the line under the name says what it is: 'JFET Boost Pedal'
        based = re.search(r"\bBased on the ([A-Z][^.\n]{3,60}?)(?=[.,\n]|$)", body)
        rating = re.search(r"(\d)\s*Build Difficulty", re.sub(r"<[^>]+>", " ", page))
        photo = re.search(r'src="(/sites/modelectronics\.com/files/media_product_photos/[^"?]+)', page)
        c = Circuit(vendor=self.vendor, slug=slug, name=title, url=url, based_on=clean_text(based.group(1)) if based else "", subtitle=kind if len(kind) < 50 else "", description=body[:3000],
                    category=_CATEGORY.get(slug) or classify(kind, title, body[:600]), difficulty=_DIFFICULTY.get(rating.group(1), "") if rating else "",
                    price=None, currency="USD", in_stock=False if slug in self.discontinued else None, doc_url=manual[0],
                    image_url=BASE + photo.group(1) if photo else "")
        if store := _STORE.search(page):
            url_store = store.group(1).replace("http://", "https://")
            c.extra_docs["Buy at Amplified Parts"] = url_store
            price, stock = store_offer(self.f.get_text(url_store) or "")
            if price:
                c.price = price
                c.in_stock = False if slug in self.discontinued else stock
        for u, label in files:
            if u != manual[0] and not re.search(r"soldering tips", label, re.I):
                label = re.sub(rf"^(?:The )?{re.escape(re.sub(r'^The ', '', title))}\s*(?:Tremolo\s*)?-?\s*", "", label, flags=re.I).strip() or label
                c.extra_docs.setdefault(label[:1].upper() + label[1:], u)
        pdf = self.f.get_file(manual[0], ".pdf")
        if not pdf or pdf.read_bytes()[:5] != b"%PDF-":
            return c
        c.doc_local = str(pdf.relative_to(DATA_DIR))
        pages = pdf_text_pages(pdf)
        res = process_document(pdf, self.vendor, slug)
        c.schematic_local, c.schematic_page = res["schematic_local"], res["schematic_page"]
        items = parts_list_items(pages)
        rows = [r for it in items if (r := item_row(*it))]
        table = max(table_rows(pages), res["bom"], key=len)
        if len(table) >= 12 and len(table) >= len(rows):
            c.bom = table  # a PCB kit: its bill of materials names every part by designator
            if not any(r.category == "R" for r in table):  # the Vortex prints its resistor table as a picture
                from ..pdf import _ocr_page
                for n, text in enumerate(pages, 1):
                    if any(_TABLE_HEAD.match(line) for line in text.split("\n")):
                        c.bom += [r for r in _ocr_page(pdf, self.vendor, slug, n, thorough=True) if r.category == "R"]
            items = offboard_items(pages)
            on_board = {r.category for r in table}
            c.bom += [r for it in items if (r := item_row(*it)) and r.category not in on_board]  # the pots and footswitch wired to the board
        else:
            c.bom = rows
            if any("terminal strip" in cap.lower() for _, _, cap in items):
                c.layout = {"build": "tagboard"}  # wired point to point on tag strips, from the manual's drawings
        box = next((re.search(r"1590[A-Z]{1,2}?(?=CE|-|$)|125B", stock) for _, stock, cap in items if "enclosure" in cap.lower()), None)
        c.enclosure = (box.group(0) if box else "") or find_enclosure("\n".join(pages[:4]))
        # The knobs are named on the schematic, where each pot carries its control's name.
        schematic = next((u for u, l in files if re.search(r"schematic", l, re.I) and not re.search(r"add|mod", l, re.I)), None)
        named: list[str] = []
        if schematic and (sp := self.f.get_file(schematic, ".pdf")) and sp.read_bytes()[:5] == b"%PDF-":
            try:
                named = [r.ref.title() for r in schematic_bom(sp, 1) if re.search(r"\d+\s?[KM]", r.value, re.I) and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}", r.ref)
                         and not re.fullmatch(r"VAC|VDC|MADC|MIN|MAX", r.ref, re.I)]
            except Exception:
                named = []
        pots = sum(int(r.ref[1:]) if r.ref.startswith("×") else 1 for r in c.bom if r.category == "POT")
        c.controls = named if named and len(named) == pots else [r.ref.title() for r in c.bom if r.category == "POT" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}", r.ref)] or ([f"{pots} knobs"] if pots > 1 else ["1 knob"] if pots else [])
        return c

    def _pcb(self, slug: str) -> Circuit | None:
        """A Mod Electronics PCB sold on its own, from its Amplified Parts build guide."""
        from .amplifiedparts import SITE, guide_rows, main_body, paragraphs, table_items
        guide = next(g for g in PCB_GUIDES if "pcb-" + g.replace("_", "-") == slug)
        name, based_on = PCB_GUIDES[guide]
        page = self.f.get_text(GUIDES + guide)
        if not page:
            return None
        body = main_body(page)
        text = " ".join(paragraphs(body))
        product = re.search(r'href="(/products/pcb-mod-electronics-[^"]+)"', body)
        pdf = re.search(r'href="([^"]+\.pdf)"', body)
        photo = next((u for u in re.findall(r'<img[^>]+src="([^"]+/tech_corner/img/[^"]+)"', body) if not u.endswith(".svg")), "")
        store = SITE + product.group(1) if product else GUIDES + guide
        box = re.search(r"1590n1|1590bb?|125b", product.group(1) if product else "", re.I)
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=store, based_on=based_on, subtitle="PCB",
                    description=text[:3000], category=_CATEGORY.get(slug) or classify(name, text[:400]), price=None, currency="USD",
                    doc_url=GUIDES + guide, image_url=photo, enclosure=box.group(0).upper() if box else find_enclosure(text),
                    tags=["PCB only"])
        c.extra_docs["Build guide (Amplified Parts)"] = GUIDES + guide
        if pdf:
            c.extra_docs["PDF build guide"] = (SITE if pdf.group(1).startswith("/") else "") + pdf.group(1)
        if product:
            price, stock = store_offer(self.f.get_text(store) or "")
            c.price, c.in_stock = price, stock
        c.bom = guide_rows(table_items(body))
        pots = [r for r in c.bom if r.category == "POT"]
        named = [m.group(1) for r in pots if (m := re.match(r"(.+?) control\b", r.notes))]
        c.controls = named if pots and len(named) == len(pots) else [f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else []
        return c
