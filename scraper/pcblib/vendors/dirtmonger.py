"""Dirt Monger Instruments adapter. Shopify collection of DIY PCBs; each product
description links a build document (and sometimes a drill template) on Google
Drive. The docs are browser-printed PDFs whose parts list is an image, so the
BOM is OCR'd in thorough mode."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..pdf import expand_refs, ocr_bom, pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text, on_host
from .deadendfx import _drive_download

BASE = "https://dirtmongerinstruments.com"
COLLECTION = f"{BASE}/collections/diy-pcb-1/products.json?limit=250"
_ORIG = re.compile(r"(?:DIY clone of (?:the |an? )?|Circuit board for (?:the |an? )?|(?:to )?build (?:either |of )?(?:the |an? )?|clone of (?:the |an? )?)([A-Z][^.\n]{2,70}?)(?:\s+DIY build|\s+build\b|\s+depending\b|\s+with\b|[.\n]|$)")

_REF = r"[A-Z]{1,3}\d{1,3}"
_VALUE_REFS = re.compile(rf"^(.+?)\s+[-–]\s+((?:{_REF}|[A-Z][a-z]+)(?:\s*,\s*(?:{_REF}|[A-Z][a-z]+))*)\s*$")
_REF_VALUE = re.compile(rf"^({_REF})\s+[-–]\s+(\S+)")


_REFS_CELL = re.compile(rf"^{_REF}[A-Z]?(?:\s*,\s*{_REF}[A-Z]?)*,?$")
_NAMES_CELL = re.compile(r"^[A-Z][A-Za-z]{0,11}(?:\s*,\s*[A-Z][A-Za-z]{0,11})*$")
_POT_LIKE = re.compile(r"^(?:[ABCW]\d+(?:[.,]\d+)?\s*[kKM]?|\d+(?:[.,]\d+)?\s*[kKM][ABCW]?)\b", re.I)  # 'B100' when a font drops the K


def _clean_value(v: str) -> str:
    v = re.sub(r",?\s+\d+V$|\s+(?:anti[ -]?)?log$|\s+lin$", "", v.strip("* "), flags=re.I).rstrip(",")
    v = re.sub(r"^([12]) (\d{3,4}[A-Z]?)$", r"\1N\2", v)  # a font that drops the N: '2 5088', '1 4001'
    return re.sub(r"\s*ohm$", "R", v, flags=re.I)


_LIST_PAGE = re.compile(r"^\s*(?:.*\bPARTS\s?LIST|Parts List)\s*$|^\W*Resistors\W*\s{3,}Capacitors?\W*$", re.M | re.I)


def parse_value_list(pages: list[str], drop_bare: bool = True) -> list[BomRow]:
    """Dirt Monger's text parts lists run in two columns, value first: either 'value - refs' in one
    cell ('100K - R7, R20', 'C50K anti log - Treble, Bass') or the value and its designators in
    neighbouring cells ('1k   R4, R17   1n   C17'). A pot's refs may be its knob names
    ('B10k   L, ML, M, MH, H'). ICs and transistors may read 'ref - value'."""
    rows: list[BomRow] = []
    seen: set[str] = set()

    trim = False  # past a 'Trimmer' heading, name-first entries are trimmers ('*BIAS   20k')

    def add(ref: str, value: str) -> None:
        pot = not re.fullmatch(_REF + "[A-Z]?", ref)
        if pot and re.fullmatch(r"[ABCW]\d+", value):
            value += "K"  # 'B100' where the font dropped the K: pedal pots are never 100 ohms
        cat = ("TRIM" if trim else "POT") if pot else ""
        r = normalize_row(BomRow(ref=ref, value=value, category=cat, part_type="Trimmer" if cat == "TRIM" else ""))
        if ref not in seen and (pot or is_plausible(r)):
            seen.add(ref)
            rows.append(r)

    for page in pages:
        if not _LIST_PAGE.search(page):
            continue  # a titled parts list, or the 'Resistors   Capacitors' heading row that starts one
        for ln in page.splitlines():
            if re.search(r"b\S?pass buffer|offboard|wiring", ln, re.I):
                break  # the bypass-buffer board and the wiring drawing follow the list
            cells = [c.strip() for c in re.split(r"\s{3,}", ln) if c.strip()]
            if any(re.fullmatch(r"trimmers?", c, re.I) for c in cells):
                trim = True
            if len(cells) >= 2 and re.fullmatch(_REF + "[A-Z]?\\*?", cells[0]) and not _REFS_CELL.match(cells[1]) \
                    and not re.fullmatch(r"[ABCW]\d+", cells[0]):  # 'A50   DRIVE, LEVEL' is a pot value whose K the font dropped
                break  # designator first ('IC1   TL071'): the bypass-buffer board's table, not this list
            i = 0
            while i < len(cells):
                cell = cells[i]
                if re.fullmatch(r"(?:Resistors?|Capacitors?|Diodes?|Transistors?|ICs?|Potentiometers?|Pots|Switch(?:es)?|S\S?itches)", cell, re.I):
                    i += 1  # a section heading sitting in the left column
                    continue
                if m := _REF_VALUE.match(cell):
                    add(m.group(1), m.group(2))
                elif m := _VALUE_REFS.match(cell):
                    value = _clean_value(m.group(1))
                    for part in m.group(2).split(","):
                        for ref in expand_refs(part.strip()):
                            add(ref, value)
                elif i + 1 < len(cells) and re.fullmatch(r"\*?[A-Z][A-Z ]{2,14}", cell) and _POT_LIKE.match(cells[i + 1]):
                    add(cell.lstrip("*"), _POT_LIKE.match(cells[i + 1]).group(0).strip())  # 'BASS   B100K Dual': name first
                    i += 2
                    continue
                # A value with the designators beside it. TL074 looks like a designator itself, but a single
                # cell right before a designator list is always its value: the columns alternate value, refs.
                elif i + 1 < len(cells) and (not _REFS_CELL.match(cell) or ("," not in cell and _REFS_CELL.match(cells[i + 1]))) and len(cell) <= 30 and (
                        _REFS_CELL.match(cells[i + 1]) or (_POT_LIKE.match(cell) and _NAMES_CELL.match(cells[i + 1]))):
                    value = _clean_value(cell)
                    for part in cells[i + 1].rstrip(",").split(","):
                        part = part.strip()
                        for ref in (expand_refs(part) if re.fullmatch(_REF + "[A-Z]?", part) else [part]):
                            add(ref, value)
                    i += 2
                    continue
                i += 1
    # Some docs use a font that drops letters from the text layer: resistor units ('1 5' for 1k5,
    # '10' for 10k) and zener letters ('5 3 E E'). When the resistors show it, leave out every value
    # made only of digits and stray capitals rather than list wrong numbers; the rest read fine.
    bare = re.compile(r"\d+(?: \d+)*(?: [A-Z])*")
    res = [r for r in rows if r.category == "R"]
    if drop_bare and len(res) >= 5 and sum(1 for r in res if bare.fullmatch(r.value)) >= 0.3 * len(res):
        rows = [r for r in rows if not bare.fullmatch(r.value)]
    return rows


def _ocr_list(pdf, pages: list[str], slug: str) -> list[BomRow]:
    """The parts list read from the rendered page by OCR (Vision keeps the column layout)."""
    from .. import vision
    from ..paths import CACHE_DIR
    from ..pdf import render_page
    page_no = next((i for i, p in enumerate(pages, 1) if _LIST_PAGE.search(p)), None)
    if not page_no or not vision.available():
        return []
    png = CACHE_DIR / "dirtmonger" / f"{slug}-list-p{page_no}.png"
    if not png.exists():
        render_page(pdf, page_no, png, dpi=300)
    return parse_value_list([vision.text(png, layout=True)])


@register
class DirtMonger(Adapter):
    vendor = "dirtmonger"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(COLLECTION, ".json")
        for pr in (json.loads(raw).get("products", []) if raw else []):
            self.products[pr["handle"]] = pr
            yield pr["handle"]

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        body_html = pr.get("body_html") or ""
        links = [(u, clean_text(_html.unescape(re.sub(r"<[^>]+>", "", t)))) for u, t in
                 re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body_html, re.S)]
        docs = [u for u, t in links if on_host(u, "drive.google.com") and re.search(r"build|doc", t, re.I)]
        drills = [u for u, t in links if re.search(r"drill", t, re.I) or on_host(u, "taydakits.com")]
        if not docs:
            return None  # picks, covers, sockets and other non-PCB items
        title = _html.unescape(pr["title"])
        name = clean_text(re.sub(r"\s*(?:DIY PCB and guitar pick|Clone DIY PCB|DIY PCB|PCB)\s*$", "", title, flags=re.I))
        body = html_to_text(body_html)
        m = _ORIG.search(body)
        based_on = clean_text(m.group(1)) if m else ""
        based_on = re.split(r",\s*Includes|\s+Includes\b|\s+from the\b", based_on)[0]
        based_on = re.sub(r"\s+(?:clone|DIY)$", "", based_on, flags=re.I).strip(" ,")
        if re.match(r"^(HM-?T?-?2|XT-2|PW-2|MT-2|DS-1|HM-2)\b", based_on) or re.search(r"\bBoss\b", body) and not re.match(r"^Boss", based_on) and re.match(r"^[A-Z]{2,3}-\d", based_on):
            based_on = "Boss " + based_on
        if not based_on:
            based_on = re.sub(r"\s+(?:Clone|DIY|Combo)$", "", name, flags=re.I)
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        c = Circuit(
            vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/products/{handle}", based_on=based_on,
            description=re.sub(r"\s*(?:BUILD DOCUMENT(?:ATION)?|DRILL TEMPLATE[^\n]*|Complete .* available here|complete .* available here)\s*", " ", body).strip(),
            category=(lambda cat: "Distortion" if cat in ("Utility", "Other") else cat)(classify(based_on, name, body[:300])), price=price, currency="CAD",
            in_stock=variant.get("available"), doc_url=docs[0], enclosure=find_enclosure(body),
            image_url=(pr.get("images") or [{}])[0].get("src", "").split("?")[0],
        )
        for u in drills:
            c.extra_docs["Drill template"] = u
        for u, t in links:
            if on_host(u, "dirtmongerinstruments.com") and "products/" in u and "utm_" in u:
                c.extra_docs["Complete pedal"] = u.split("?")[0]
        pdf = self.f.get_file(_drive_download(c.doc_url), ".pdf")
        if pdf and pdf.stat().st_size > 2000 and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            m = re.search(r"\b(V\s?\d+(?:\.\d+)*)\s+Build Documentation", pages[0] if pages else "", re.I)
            if m:
                c.doc_version = m.group(1).replace(" ", "")
            if not c.enclosure:
                c.enclosure = find_enclosure(*pages[:2])
            # Some docs carry a text parts table; the rest have it as an image.
            c.__dict__.update({k: v for k, v in process_document(pdf, self.vendor, handle).items() if k in ("bom", "schematic_local", "schematic_page")})
            listed = parse_value_list(pages)
            if listed:
                c.bom = listed  # the document's own list; the table parsers read the same (sometimes broken) text worse
                if any(_LIST_PAGE.search(p) and re.search(r"(?:^|\s{3,})\d+(?: \d+)?\s{3,}[RC]\d", p, re.M) for p in pages):
                    # A bare number beside resistor or capacitor designators ('120   C7, C10'): the font dropped
                    # the units from the text layer. Read the list page's image and take the passives from it.
                    have = {r.ref for r in c.bom}
                    for r in _ocr_list(pdf, pages, handle):
                        if r.category in ("R", "C") and r.ref not in have:
                            r.notes = "OCR"
                            c.bom.append(r)
            if len(c.bom) < 8:
                ocr = ocr_bom(pdf, self.vendor, handle, max_pages=5, thorough=True)
                if len(ocr) > len(c.bom):
                    c.bom = ocr
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]*\d?", r.ref) for r in pots)
                # EQ bands named L, ML, M, MH, H stay as printed; longer names are title-cased
                c.controls = [r.ref if len(r.ref) <= 2 else r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
