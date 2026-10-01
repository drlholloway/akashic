"""Holy Island Audio adapter. A Big Cartel shop of finished pedals with one DIY PCB product whose
options are the boards (Phantom Coil, Sun Swallower...), each with its own price and stock state.
The product description gives each board a heading, a paragraph and a link to a Google Doc build
guide. The guides list parts one per paragraph in three layouts: 'VALUE - R1, R2' (named pots as
'A100K - VOLUME'), the same with a leading quantity ('2   100K  -  R23, R26'), and 'R1 - 1K'."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..docx import read_docx
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..pdf import expand_refs
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text, on_host

BASE = "https://holyislandaudio.bigcartel.com"
_BASED_ON = {"harmonic-percolator": "Interfax Harmonic Percolator"}
_CATEGORY = {"phantom-coil": "Reverb", "sun-swallower": "Ring Mod / Synth", "emf-sniffer": "Other",
             "harmonic-percolator": "Fuzz"}
_REF = re.compile(r"^(?:R|C|D|Q|L|IC|U|SW|LED|CLR)\d{0,3}[A-Z]?$", re.I)
_POTVAL = re.compile(r"^[ABCW]\d+(?:\.\d+)?[KM]?$", re.I)
_ACRONYMS = {"EMF", "LFO", "DC"}
_SPLIT = re.compile(r"\s+-\s+|\s{2,}")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _refs(s: str) -> list[str]:
    """'C1, C2, C3' or 'R2,R4' -> designators; [] if any item is not one."""
    items = [x.strip() for x in re.split(r"\s*,\s*", s.strip()) if x.strip()]
    out: list[str] = []
    for x in items:
        if not _REF.match(x):
            return []
        out += expand_refs(x)
    return out


def _names(s: str) -> list[str]:
    """'WET, MASTER' or 'TUNE 1, TUNE2' -> knob names; [] if it reads like prose."""
    items = [x.strip() for x in s.split(",") if x.strip()]
    if not items or any(len(x) > 14 or not re.fullmatch(r"[A-Z][A-Z ]*\d?", x) for x in items):
        return []
    return [re.sub(r"(\D)\s?(\d)$", r"\1 \2", x).title() for x in items]


def _value(v: str) -> tuple[str, str]:
    """Strip the remark in brackets: '470NF ... (THESE SHOULD BE CERAMIC...)' -> ('470NF', note)."""
    note = " ".join(re.findall(r"\(([^)]*)\)?", v)).strip()
    v = re.sub(r"\(.*$", "", v).strip()
    m = re.match(r"^(\d+(?:\.\d+)?\s?MH)\s+INDUCTOR$", v, re.I)  # '100MH INDUCTOR' is 100 mH, not 100 megohm
    if m:
        return m.group(1).replace(" ", "")[:-2] + "mH", note
    return v, note.capitalize()


def para_bom(paras: list[str]) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()

    def add(ref: str, value: str, note: str = "", cat: str = "", ptype: str = "") -> None:
        if not value or ref.upper() in seen:
            return
        r = normalize_row(BomRow(ref=ref, value=value, notes=note, category=cat, part_type=ptype))
        if cat or is_plausible(r):
            seen.add(ref.upper())
            rows.append(r)

    for p in paras:
        t = re.sub(r"^\d{1,2}\s+(?=\S)", "", p.replace("\t", "  ").strip())  # a leading quantity
        if not t or t.startswith("http") or len(t) > 160:
            continue
        parts = [x.strip() for x in _SPLIT.split(t, maxsplit=2) if x.strip()]
        if len(parts) < 2 and re.fullmatch(r"\S+ (?:IC|U|Q|D)\d{1,2}", t):  # 'BS170 Q1'
            parts = t.split()
        if len(parts) < 2:
            continue
        left, right = parts[0], " - ".join(parts[1:])
        if _POTVAL.match(left) and _names(right):                          # 'A100K - WET, MASTER', 'C500K - GAIN'
            for n in _names(right):
                add(n, left.upper(), cat="POT", ptype="Potentiometer")
        elif _REF.match(left) and not re.match(r"^SW", left, re.I):     # 'R1 - 1K', 'CLR - 4K7 (INCREASE ...)'
            value, note = _value(right)
            if len(value.split()) > 2:                                     # 'Q2 + Q3 - These are the two ...'
                continue
            add(left.upper(), value, note)
        elif re.match(r"^\d+(?:\.\d+)?K$", left, re.I) and re.match(r"^TRIM", parts[1], re.I) and len(parts) == 3:
            add(parts[2].title(), left.upper(), cat="TRIM", ptype="Trimmer")   # '100K - TRIMMER - INPUT'
        elif _names(left) and _POTVAL.match(right):                        # 'HARMONICS - A100K'
            add(_names(left)[0], right.upper(), cat="POT", ptype="Potentiometer")
        else:
            value, note = _value(left)
            refs = _refs(re.sub(r"\(.*$", "", right))
            if refs:                                                       # '100K - R1, R2', 'LM386  IC1'
                note = note or _value(right)[1]
                for ref in refs:
                    add(ref.upper(), value, note)
    return rows


@register
class HolyIsland(Adapter):
    vendor = "holyisland"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.boards: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/products.json", ".json")
        for p in (json.loads(raw) if raw else []):
            if not any(c.get("permalink") == "diy" for c in p.get("categories") or []):
                continue
            desc = p.get("description") or ""
            links = [(u, clean_text(re.sub(r"<[^>]+>", " ", _html.unescape(t))))
                     for u, t in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', desc, re.S)]
            text = html_to_text(desc)
            for o in p.get("options") or []:
                name = clean_text(o["name"])
                doc = next((u for u, t in links if "docs.google.com/document" in u and t.upper().startswith(name.upper())), "")
                slug = _slug(name)
                self.boards[slug] = {"product": p, "option": o, "name": name, "doc": doc, "text": text}
                yield slug

    def _blurb(self, text: str, name: str) -> str:
        """The paragraphs between the board's heading and its BUILD DOC link. A heading is an upper-case
        line sharing a word with the board's name, so a misspelt one ('HARMOMOC PERCOLATOR') still counts."""
        lines = [ln.strip() for ln in text.split("\n")]
        words = set(name.upper().split())
        start = next((i for i, ln in enumerate(lines)
                      if ln.isupper() and "BUILD DOC" not in ln and words & set(ln.split())), None)
        if start is None:
            return ""
        out = []
        for ln in lines[start + 1:]:
            if "BUILD DOC" in ln.upper():
                break
            if ln and not re.match(r"^Please find the build", ln, re.I):
                out.append(ln)
        return clean_text(" ".join(out))

    def parse(self, slug: str) -> Circuit | None:
        b = self.boards.get(slug)
        if not b or not b["doc"]:
            return None
        p, o = b["product"], b["option"]
        name = " ".join(w if w in _ACRONYMS else w.title() for w in b["name"].split())
        description = self._blurb(b["text"], b["name"])
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=f"{BASE}/product/{p['permalink']}",
                    description=description, price=float(o["price"]) if o.get("price") is not None else None,
                    currency="GBP", in_stock=not o.get("sold_out"),
                    image_url=((p.get("images") or [{}])[0].get("url") or "").split("?")[0],
                    based_on=_BASED_ON.get(slug, ""), difficulty="Advanced")
        c.doc_url = b["doc"]
        fid = re.search(r"/d/([A-Za-z0-9_-]+)", b["doc"]).group(1)
        path = self.f.get_file(f"https://docs.google.com/document/d/{fid}/export?format=docx", ".docx")
        text = ""
        if path and path.read_bytes()[:2] == b"PK":
            paras, _, _ = read_docx(path)
            text = "\n".join(paras)
            c.bom = para_bom(paras)
            c.doc_local = str(path.relative_to(DATA_DIR)) if DATA_DIR in path.parents else str(path)
            for i, para in enumerate(paras):
                u = para.strip()
                if u.startswith("http") and on_host(u, "drill.taydakits.com", "drive.google.com"):
                    label = "Tayda drill template" if "taydakits" in u else (paras[i - 1].strip().title() if i else "Drill guide")
                    c.extra_docs.setdefault(label[:60], u)
        c.enclosure = find_enclosure(text) or find_enclosure(description)
        c.category = _CATEGORY.get(slug) or classify(name, c.based_on, description)
        c.controls = [r.ref for r in c.bom if r.category in ("POT",)]
        return c
