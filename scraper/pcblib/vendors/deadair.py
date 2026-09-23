"""Dead Air Studios adapter. A Big Cartel shop of finished pedals with a handful of DIY PCBs;
`products.json` lists everything and the PCB products link a Google Doc (or Sheet) build
guide whose parts list is one part per paragraph ("R1   2.2 M", "VOLUME   A100K"), plus
Drive images of the schematic and drill guide."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..docx import read_docx
from ..gsheet import grid_bom, sheet_id
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://deadairstudios.bigcartel.com"
_BASED_ON = {"face-disaster-pcb": "Tim Escobedo Ugly Face", "sawzall-diy-hm2-eq-overdrive-pcb": "Boss HM-2 / MXR Distortion+",
             "dead-air-business-card-pcb": "Jordan Boss Tone", "tube-nightmare-pcb": "Ibanez Tube Screamer", "bow-echo-pcb": ""}
_CATEGORY = {"bow-echo-pcb": "Delay", "face-disaster-pcb": "Fuzz", "sawzall-diy-hm2-eq-overdrive-pcb": "Distortion",
             "dead-air-business-card-pcb": "Fuzz", "tube-nightmare-pcb": "Overdrive"}
_NOTICE = re.compile(r"(?:ORDERS WILL NOT SHIP.*?thanks for understanding!\s*|\*\*\s*Please note that it is assumed.*?(?:\n\s*\n|$))", re.I | re.S)
_REF = re.compile(r"^(?:[A-Z]{1,4}\d{1,3}[A-Z]?|CLR|LED|REG|VACT_?\d*)$", re.I)
_POTVAL = re.compile(r"^[ABCW]\d+(?:\.\d+)?[kKM]?$")
_SW = re.compile(r"^(?:[SD]P[SD]T|3PDT)\b", re.I)


_ACRONYMS = {"LFO", "EQ", "HF", "LF", "VCA", "VCO", "DC", "AC"}


def _nice(name: str) -> str:
    """'LFO-RATE' -> 'LFO Rate', 'HIGH_VOLUME' -> 'High Volume', '386-STARVE' -> '386 Starve'."""
    return " ".join(w if w in _ACRONYMS else w.title() for w in re.split(r"[_\-\s]+", name.strip()) if w)


def _para_bom(paras: list[str]) -> tuple[list[BomRow], str]:
    """'Part   Value' then one part per paragraph until prose resumes. Named pots and switches
    come as 'VOLUME   A100K' and 'MODULATION   DPDT   ON / OFF / ON'; a few run together
    ('MODULATIONB2M', 'HIGH_VOLUMEB10K'). Returns (rows, enclosure named in the guide)."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    enclosure = ""
    on = False
    prose = 0
    for p in paras:
        t = p.replace("\t", "  ").strip()
        if not t:
            continue
        enclosure = enclosure or find_enclosure(t)
        if re.match(r"^Part\s+Value$", t, re.I):
            on = True
            continue
        if not on:
            continue
        if t.startswith("http") or t.startswith("[") or t.startswith("("):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_/\-]*)\s+(.+)$", t)
        m2 = re.match(r"^([A-Z][A-Z_]{2,14})([ABCW]\d+(?:\.\d+)?[kKM]?)(?:\s|$)", t)  # 'MODULATIONB2M    ( Lower values ... )'
        if m2:
            m = m2
        head = m.group(1) if m else ""
        rest = m.group(2).strip() if m else ""
        is_part = bool(m) and (_REF.match(head) or _SW.match(rest) or _POTVAL.match(rest.split()[0]))
        if not is_part:
            if rows and len(t.split()) > 12:
                prose += 1
                if prose >= 2:
                    break  # the guide's notes after the list
            continue  # a heading ('LED', '16 PIN SOCKET') or a one-line remark between parts
        prose = 0
        ref = head
        rest = re.sub(r"\s*\(.*?\)\s*", " ", rest).strip()  # '( 25K, or 50K ... )'
        note = ""
        ref = re.sub(r"-USE_A_SOCKET$", "", ref, flags=re.I)
        if _REF.match(ref):
            cat = ""
            parts = re.split(r"\s{2,}", rest)
            value, ptype = parts[0].strip(), " ".join(parts[1:]).strip()
            value = re.sub(r"^(\d+(?:\.\d+)?)\s+([kKMnpuNPU]F?|uf|nf|pf|R)\b", r"\1\2", value)  # '2.2 M', '100 uf'
            if re.search(r"omit", value, re.I):
                continue
            value = re.split(r"\s+-\s+|\s+/\s+", value)[0].strip()  # 'LM555N - CMOS VERSION ONLY', 'LM386N / JRC386'
            if " " in value and not re.match(r"^\d", value):
                value = value.split()[0]
            if ptype and not re.match(r"^(film|electrolytic|ceramic|tantalum|mlcc)", ptype, re.I):
                note, ptype = ptype, ""
            ref = ref.upper()
        elif _SW.match(rest):
            cat, value, ptype = "SW", rest.split()[0].upper(), "Switch"
            note = " ".join(rest.split()[1:])
            ref = _nice(ref)
        elif _POTVAL.match(rest.split()[0]):
            cat, value, ptype = "POT", rest.split()[0].upper(), "Potentiometer"
            ref = _nice(ref)
        else:
            continue
        if ref.upper() in seen:
            continue
        nr = normalize_row(BomRow(ref=ref, value=value, part_type=ptype, notes=note, category=cat))
        if cat or is_plausible(nr):
            seen.add(ref.upper())
            rows.append(nr)
    return rows, enclosure


@register
class DeadAir(Adapter):
    vendor = "deadair"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/products.json", ".json")
        for p in (json.loads(raw) if raw else []):
            if re.search(r"\bPCB\b", p.get("name", ""), re.I):
                self.products[p["permalink"]] = p
                yield p["permalink"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        desc_html = p.get("description") or ""
        links = [(u, clean_text(re.sub(r"<[^>]+>", " ", t))) for u, t in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', desc_html, re.S)]
        docs = [(u, t) for u, t in links if "docs.google.com/document" in u]
        sheets = [(u, t) for u, t in links if "docs.google.com/spreadsheets" in u]
        if not docs and not sheets:
            return None
        name = clean_text(_html.unescape(re.sub(r"<br\s*/?>", " ", p["name"], flags=re.I)))
        name = re.sub(r"\s*\bDIY\b|\s*\bPCB\b", "", name, flags=re.I).strip().title().replace("Hm2", "HM-2").replace("Eq", "EQ")
        description = clean_text(_NOTICE.sub("", html_to_text(desc_html)))
        description = re.sub(r"\s*DOCUMENTS?:.*$", "", description, flags=re.S | re.I)
        link_text = " ".join(t for _, t in links)
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=f"{BASE}/product/{slug}", description=description,
                    price=float(p["price"]) if p.get("price") is not None else None, currency="USD",
                    in_stock=p.get("status") == "active", image_url=((p.get("images") or [{}])[0].get("url") or "").split("?")[0],
                    based_on=_BASED_ON.get(slug, ""), enclosure=find_enclosure(link_text))
        for u, t in links:
            if "drive.google.com" in u or "docs.google.com" in u or "taydakits" in u:
                label = re.sub(r"^\s*\[\s*", "", t.split("]")[0]).strip() or "Document"  # one anchor can wrap two bracketed labels
                c.extra_docs.setdefault(label[:60], u)
        text = ""
        if docs:
            u, t = docs[0]
            c.doc_url = u
            fid = re.search(r"/d/([A-Za-z0-9_-]+)", u).group(1)
            path = self.f.get_file(f"https://docs.google.com/document/d/{fid}/export?format=docx", ".docx")
            if path and path.read_bytes()[:2] == b"PK":
                paras, tables, _ = read_docx(path)
                text = "\n".join(paras)
                c.bom, enc = _para_bom(paras)
                c.enclosure = c.enclosure or enc
                c.doc_local = str(path.relative_to(DATA_DIR)) if DATA_DIR in path.parents else str(path)
        if sheets and len(c.bom) < 8:
            u, t = sheets[0]
            c.doc_url = c.doc_url or u
            sid = sheet_id(u)
            path = self.f.get_file(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx", ".xlsx")
            if path and path.read_bytes()[:2] == b"PK":
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                grid = [list(r) for ws in wb.worksheets for r in ws.iter_rows(values_only=True)]
                wb.close()
                rows, enc = grid_bom(grid)
                if len(rows) > len(c.bom):
                    c.bom = rows
                c.enclosure = c.enclosure or enc
        m = re.search(r"based (?:off of|on) (?:the |a )?([A-Z][\w' -]+?)(?:\s+and\b|[.,])", text + " " + description)
        if not c.based_on and m:
            c.based_on = clean_text(m.group(1))
        c.category = _CATEGORY.get(slug) or classify(name, c.based_on, description)
        pots = [r for r in c.bom if r.category == "POT"]
        c.controls = [r.ref.title() if r.ref.isupper() else r.ref for r in pots] + [r.ref.title() if r.ref.isupper() else r.ref for r in c.bom if r.category == "SW" and not re.match(r"^(?:SW|S)\d", r.ref)]
        return c
