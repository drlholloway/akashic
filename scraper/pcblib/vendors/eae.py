"""Electronic Audio Experiments adapter. A Squarespace DIY collection (`?format=json`
gives the items) of retired EAE pedals released as PCBs, each with a LaTeX-set
builder's guide and, usually, a spreadsheet BOM."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..gsheet import _REF, xlsx_bom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.electronicaudioexperiments.com"
COLLECTION = f"{BASE}/diy?format=json"
_ORIG = re.compile(r"(?:take on the|based on the|clone of the|version of the)\s+(?:vintage |classic |discontinued )?([A-Z][^.,;]{2,50}?)(?=\s*[.,;]|\s+(?:Similar|Includes)\b)")
_HEAD = re.compile(r"^\s*Qty\s+Value\s+Ref\s*#?s?\s+Description", re.I)
_TAPER = {"audio": "A", "log": "A", "linear": "B", "lin": "B", "reverse audio": "C", "reverse log": "C", "rev audio": "C", "rev log": "C", "rev": "C"}
_CATEGORY = {"mu-blaster-pcb": "Boost", "hd130-pcb": "Preamp / Amp-in-a-box"}  # "boost/drive" and a pedal-ized amp
_STOP = {"The", "This", "There", "One", "It", "In", "If", "You", "We", "A", "An", "Note", "For", "As", "When", "With", "All"}


def _pot_value(v: str) -> tuple[str, str]:
    """'100kΩ Audio' -> ('A100k', 'POT'); '1MΩ Reverse Audio' -> ('C1M', 'POT'); '100kΩ Trim' -> ('100k', 'TRIM')."""
    m = re.match(r"^([ABCW])?(\d+(?:\.\d+)?)\s*([kKM]?)\s*(?:Ω|ohms?)?\s*(.*)$", v.strip())
    if not m:
        return v, ""
    t, num, pre, rest = m.groups()
    rest = rest.strip().lower()
    if "trim" in rest:
        return f"{num}{pre}", "TRIM"
    taper = _TAPER.get(rest, t or "")
    return f"{taper}{num}{pre}", "POT" if taper else ""


def _guide_bom(pages: list[str]) -> tuple[list[BomRow], str]:
    """The guide's LaTeX-set Qty / Value / Ref #s / Description tables: cells are sliced by the
    header's column positions and a line with an empty Qty cell continues the row above (the
    ref lists and long values wrap). Returns (rows, enclosure from the off-board table)."""
    raw: list[list[str]] = []
    for page in pages:
        cols: list[int] | None = None
        prev_blank = False
        for line in page.splitlines():
            if _HEAD.match(line):
                cols = [line.index("Qty"), line.index("Value"), line.index("Ref"), line.index("Description")]
                prev_blank = False
                continue
            if cols is None:
                continue
            if not line.strip():
                prev_blank = True
                continue
            line = line.replace("\u2126", "Ω")  # the OHM SIGN, which LaTeX prefers to Greek omega
            cells = [re.sub(r"\s+", " ", line[a:b]).strip() for a, b in zip(cols, cols[1:] + [None])]
            qty, value, ref, desc = cells
            if re.fullmatch(r"\d+", qty):
                if value or ref:
                    raw.append([qty, value, ref, desc])
            elif not qty and raw and not prev_blank and (value or ref or desc) and not re.fullmatch(r"\d+", ref):
                r = raw[-1]
                r[1], r[2], r[3] = (r[1] + " " + value).strip(), (r[2] + " " + ref).strip(), (r[3] + " " + desc).strip()
            else:
                cols = None  # a group title or prose ends the table; the next group has its own header
            prev_blank = False
    rows: list[BomRow] = []
    seen: set[str] = set()
    enclosure = ""
    for qty, value, refs, desc in raw:
        if re.match(r"^enclosure", value, re.I):
            enclosure = enclosure or find_enclosure(desc)
            continue
        if re.search(r"jack|knob|battery|wire|screw|standoff", value, re.I):
            continue
        for ref in re.split(r"\s*,\s*", refs):
            ref = re.sub(r"\s*\(.*\)$", "", ref).strip()
            if not ref or ref.upper() in seen or re.fullmatch(r"n/?a", ref, re.I):
                continue
            v, cat = re.sub(r"[*†‡]+$", "", value.replace("Ω", "")).strip(), ""
            if _REF.match(ref) or re.fullmatch(r"[A-Z]{1,4}\d{1,3}[A-Z]?", ref, re.I):
                pass
            elif re.search(r"[SD]P[SD]T|\dP[SD]T|toggle|rotary|switch", value, re.I):
                cat, ref = "SW", ref.title()
            else:
                v, cat = _pot_value(value)
                if not cat:
                    continue
                ref = ref.upper() if cat == "TRIM" else ref.title()
            nr = normalize_row(BomRow(ref=ref, value=v, part_type=desc, category=cat))
            if cat or is_plausible(nr):
                seen.add(ref.upper())
                rows.append(nr)
    return rows, enclosure


def _controls(text: str) -> list[str]:
    """'The controls are as follows:' then one 'Name  description' entry per line, continuation
    lines indented; the list ends at a sentence or an indented new paragraph. Trimpots are internal."""
    m = re.search(r"The controls are as follows:\s*\n(.*)", text, re.S)
    if not m:
        return []
    out: list[str] = []
    prev_blank = False
    for line in m.group(1).splitlines():
        if not line.strip():
            prev_blank = True
            continue
        if line[0].isspace():
            if prev_blank:
                break
            prev_blank = False
            continue
        prev_blank = False
        w = line.split()
        if w[0] in _STOP or not w[0][0].isupper() or len(out) >= 12:
            break
        name = w[0]
        if len(w) > 1 and w[1] in ("Footswitch", "Switch", "Toggle", "Mix", "Trim", "Blend"):
            name += " " + w[1]
        if "trimpot" in line.lower()[:len(name) + 12] or "trim" in name.lower():
            continue
        out.append(name)
    return out


@register
class EAE(Adapter):
    vendor = "eae"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.items: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(COLLECTION, ".json")
        for it in (json.loads(raw).get("items", []) if raw else []):
            slug = it.get("urlId") or it["fullUrl"].rsplit("/", 1)[-1]
            self.items[slug] = it
            yield slug

    def parse(self, slug: str) -> Circuit | None:
        it = self.items.get(slug)
        if not it:
            return None
        raw = self.f.get_text(f"{BASE}{it['fullUrl']}?format=json", ".json")  # the listing's body is null
        if raw:
            try:
                it = {**it, **(json.loads(raw).get("item") or {})}
            except ValueError:
                pass
        body = it.get("body") or ""
        body = re.sub(r"#block-[\w-]+\s*\{[^}]*\}", "", body)
        links = re.findall(r'href="(/s/[^"]+)"', body)
        pdfs = [BASE + u for u in links if u.lower().endswith(".pdf")]
        sheets = [BASE + u for u in links if u.lower().endswith((".xlsx", ".xls"))]
        if not pdfs and not sheets:
            return None
        excerpt = html_to_text(it.get("excerpt") or "")
        name = clean_text(_html.unescape(it["title"]))
        name = re.sub(r"\s*(?:DIY )?PCB$", "", name, flags=re.I)
        m = _ORIG.search(excerpt)
        based_on = clean_text(m.group(1)) if m else ""
        if not based_on and re.search(r"discontinued|no longer in production|archived product page", excerpt, re.I):
            based_on = f"Electronic Audio Experiments {name}"  # a retired EAE pedal released as a DIY project
        variant = (it.get("variants") or [{}])[0]
        price = variant.get("price")
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=BASE + it["fullUrl"], based_on=based_on,
            description=excerpt, category=_CATEGORY.get(slug) or classify(name, based_on, re.sub(r"[^.]*daughterboard[^.]*\.", "", excerpt)), price=(price / 100) if isinstance(price, (int, float)) else None,
            currency="USD", in_stock=None if variant.get("unlimited") is None else bool(variant.get("unlimited") or (variant.get("qtyInStock") or 0) > 0),
            doc_url=pdfs[0] if pdfs else sheets[0], image_url=(((it.get("items") or [{}])[0].get("assetUrl") or (variant.get("mainImage") or {}).get("assetUrl") or "")).split("?")[0], enclosure=find_enclosure(excerpt),
        )
        for u in sheets:
            c.extra_docs["BOM spreadsheet"] = u
        if pdfs:
            pdf = self.f.get_file(pdfs[0], ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                res = process_document(pdf, self.vendor, slug)
                c.doc_local, c.bom, c.schematic_local, c.schematic_page = res["doc_local"], res["bom"], res["schematic_local"], res["schematic_page"]
                pages = pdf_text_pages(pdf)
                text = "\n".join(pages)
                m = re.search(r"Version\s+(\d+(?:\.\d+)*)\s*\n", text)
                c.doc_version = m.group(1) if m else ""
                c.enclosure = c.enclosure or find_enclosure(text)
                c.controls = _controls(text)
                guide_rows, enc = _guide_bom(pages)
                if len(guide_rows) > len(c.bom):
                    c.bom = guide_rows
                c.enclosure = c.enclosure or enc
        if sheets:
            xlsx = self.f.get_file(sheets[0], ".xlsx")
            if xlsx and xlsx.read_bytes()[:2] == b"PK":
                rows, enc = xlsx_bom(xlsx)
                if len(rows) > len(c.bom):
                    c.bom = rows  # the spreadsheet is exact; the guide's table is the fallback
                c.enclosure = c.enclosure or enc
        if not c.controls:
            c.controls = [r.ref.title() for r in c.bom if r.category == "POT"]
        return c
