"""OP Electronics adapter: an Italian PrestaShop store (EUR) whose 'PCBs for assembly'
category lists bare boards for classic circuits. Each product page attaches a datasheet PDF
with a Qty / Value / Parts / Description part list (two of them side by side when one board
builds two circuits) and an SVG drill template."""
from __future__ import annotations

import html as _html
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from ..gsheet import grid_bom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR, RAW_DIR
from ..pdf import expand_refs, find_schematic_page, ocr_bom, pdf_text_pages, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.op-electronics.com"
CATEGORY = f"{BASE}/en/169-pcbs-for-assembly"
_SKIP = re.compile(r"\bkit\b|adapter|componenti|relay switch|coming soon", re.I)
_UTILITY = re.compile(r"buffer board|blend board|tap tempo|3pdt|relay", re.I)
_TM = re.compile(r"\s*\((?:TM|R)\)|™|®", re.I)
_HEADER = re.compile(r"(?:Qty\s+|QTY\s+)?(?:Parts?\s+)?Value\s+(?:Package\s+)?(?:Parts\s+)?(?:Package\s+)?Description")
_COLS = {"Qty": "qty", "Value": "value", "Parts": "parts", "Part": "parts", "Description": "desc", "Package": "package"}
_CATEGORY = {"guvnor": "Overdrive", "hot-tubes": "Overdrive", "ocd": "Overdrive", "sac": "Preamp / Amp-in-a-box", "noise-gate": "Noise Gate",
             "tap-tempo": "Utility", "blend-board": "Utility", "buffer-board": "Utility", "king-drive": "Overdrive", "z-drive": "Overdrive"}
_DRILL = re.compile(r"1590|125B|drill|template|panel|\.svg", re.I)
_BASED_ON = {"t-screamer": "Ibanez Tube Screamer", "b-breaker": "Marshall Blues Breaker", "rd-compressor": "Ross Compressor / MXR Dyna Comp",
             "ge-601": "Ibanez GE-601 Graphic Equalizer", "phase-90": "MXR Phase 90", "phase-45": "MXR Phase 45", "ce-2": "Boss CE-2 Chorus",
             "hot-tubes": "Electro-Harmonix Hot Tubes", "kc-overdrive": "Klon Centaur", "distortion-plus": "MXR Distortion+", "muff-of-doom": "Electro-Harmonix Big Muff",
             "muff": "Electro-Harmonix Big Muff", "z-drive": "Hermida Zendrive", "guvnor": "Marshall Guv'nor", "octavia": "Tycobrahe Octavia",
             "fuzzrite": "Mosrite Fuzzrite", "ocd": "Fulltone OCD", "sac": "Tech 21 SansAmp Classic", "king-drive": "Analog Man King of Tone", "fuzz-industries": "ZVex Fuzz Factory",
             "gold-distortion": "Marshall Shred Master", "lpb": "Electro-Harmonix LPB-1", "mosfet-booster": "AMZ MOSFET Booster", "sho": "ZVex Super Hard-On",
             "rat": "ProCo RAT", "tone-machine": "Foxx Tone Machine", "electric-flanger": "Electric Mistress", "newvibe": "Shin-ei Uni-Vibe",
             "trouble-boost": "", "deluxe-delay": "", "octaverb": "", "spring-reverb": "", "noise-gate": "", "3-band-eq": "", "digital-delay": "", "wah-wah": "Vox / Dunlop Cry Baby wah"}


def parse_partlist(pages: list[str]) -> list[BomRow]:
    """Rows of the Qty / Value / Parts / Description table. The layout PDF sometimes emits a
    block of rows one column at a time (all quantities, then all values, ...), so cells are
    queued per column and zipped back into rows. Two tables side by side become variants."""
    rows: list[BomRow] = []
    seen: set[tuple[str, str]] = set()
    title_words = {w.lower() for w in re.findall(r"[A-Za-z]+", pages[0][:300])} if pages else set()
    for page in pages:
        lines = page.splitlines()
        hi = next((i for i, ln in enumerate(lines) if _HEADER.search(ln)), None)
        if hi is None:
            continue
        header = re.sub(r"\bQTY\b", "Qty", lines[hi])
        first = re.match(r"\s*(Qty|Parts?|Value)", header)
        if not first:
            continue
        starts = [m.start() for m in re.finditer(rf"\b{first.group(1)}\b", header)]
        spans = [(st, starts[i + 1] if i + 1 < len(starts) else 10_000) for i, st in enumerate(starts)]
        for lo, hi_ in spans:
            label = ""
            if len(spans) > 1:
                above = " ".join(ln[lo:hi_].strip() for ln in lines[max(0, hi - 2):hi])
                label = " ".join(w for w in re.sub(r"(?i)\bversion\b", "", above).split() if w.lower() not in title_words).strip(" -")
                label = label.title() if label.isupper() else label
            hdr = header[lo:hi_] if hi_ < 10_000 else header[lo:]
            found = [(_COLS[m.group(0)], m.start()) for m in re.finditer(r"Qty|Value|Parts|Part|Description|Package", hdr)]
            if not {"value", "parts", "desc"} <= {n for n, _ in found}:
                continue
            order = ["qty", "value", "parts", "desc"]
            cols = [next((st for n, st in found if n == name), -1) for name in order]
            bounds = sorted(st for _, st in found)
            queues: list[list[str]] = [[], [], [], []]
            carry = ""  # a Parts cell wrapped onto the line above its row
            for ln in lines[hi + 1:]:
                seg = ln[lo:hi_] if hi_ < 10_000 else ln[lo:]
                if not seg.strip():
                    continue
                if re.match(r"\s*(?:www|\.com|Rev|document)", seg, re.I) or len(seg.strip()) < 2 and not seg.strip().isdigit():
                    continue
                # Cells by column start; quantities are right-aligned so the leading integer is read first.
                cells = ["", "", "", ""]
                value_from = None
                if cols[0] >= 0:
                    mq = re.match(r"^\s*(\d+)(?:\s|$)", seg[:cols[1] + 1])
                    if mq:
                        cells[0], value_from = mq.group(1), mq.end()
                else:
                    cells[0] = "1"
                for ci in (1, 2, 3):
                    cs = cols[ci]
                    ce = next((b for b in bounds if b > cs), None)
                    start = value_from if ci == 1 and value_from is not None else max(0, cs - 1)
                    cells[ci] = (seg[start:ce - 1] if ce else seg[start:]).strip()
                if cells[2].endswith(",") and not cells[0] and not cells[1] and not cells[3]:
                    carry += cells[2] + " "
                    continue
                if carry and cells[2]:
                    cells[2], carry = carry + cells[2], ""
                present = [i for i, cell in enumerate(cells) if cell]
                if not present:
                    continue
                if present == [0, 1, 2, 3] or (present[:3] == [0, 1, 2]):
                    for i in range(4):
                        queues[i].append(cells[i])
                else:
                    for i in present:
                        queues[i].append(cells[i])
                while all(queues[i] for i in range(3)):
                    qty, value, parts = (queues[i].pop(0) for i in range(3))
                    desc = queues[3].pop(0) if queues[3] else ""
                    if not re.fullmatch(r"\d+", qty) or value.lower() in ("empty", "value") or re.match(r"^(?:www|Value)", parts):
                        continue
                    for ref in expand_refs(parts):
                        ref = ref.strip()
                        if not ref or (ref.upper(), label) in seen:
                            continue
                        cat = ""
                        if re.search(r"trim", desc + " " + ref, re.I) and not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref):
                            cat, ref = "TRIM", ref if re.search(r"\d", ref) else ref.title()
                        elif re.search(r"potentiometer", desc, re.I) and not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref):
                            cat, ref = "POT", ref if re.search(r"\d", ref) else ref.title()
                        elif re.search(r"switch", desc, re.I) and not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref):
                            cat, ref = "SW", ref.title()
                        elif re.fullmatch(r"L[+-]|LED\d?", ref):
                            ref = "LED"
                        elif not re.fullmatch(r"[A-Z]{1,4}\d{0,3}", ref):
                            continue
                        r = normalize_row(BomRow(ref=ref, value=value, part_type=desc.title() if desc.isupper() else desc, category=cat, variant=label))
                        if cat or is_plausible(r):
                            seen.add((ref.upper(), label))
                            rows.append(r)
    return rows


def _unpack_partlist(archive: Path, stem: Path) -> Path | None:
    """The member of a zip or rar that carries the part list (a datasheet, BOM or partlist
    PDF, or an .ods spreadsheet), extracted next to the cache with bsdtar."""
    for ext in (".pdf", ".ods", ".xlsx"):
        if stem.with_suffix(ext).exists():
            return stem.with_suffix(ext)
    listing = subprocess.run(["bsdtar", "-tf", str(archive)], capture_output=True, text=True, errors="replace").stdout.splitlines()
    members = [m for m in listing if m.lower().endswith((".pdf", ".ods", ".xlsx")) and not re.search(r"drill|template|1590|125b|-top|-bottom|-pcb\b|-sch\b|schematic|wiring|panel", m, re.I)]
    members.sort(key=lambda m: (0 if re.search(r"datasheet|partlist|bom", m, re.I) else 1, 0 if m.lower().endswith(".pdf") else 1))
    if not members:
        return None
    data = subprocess.run(["bsdtar", "-xOf", str(archive), members[0]], capture_output=True).stdout
    if not data:
        return None
    out = stem.with_suffix(Path(members[0]).suffix.lower())
    out.write_bytes(data)
    return out


def _ods_grid(path: Path) -> list[list[str]]:
    """Rows of the first sheet of an OpenDocument spreadsheet."""
    xml = subprocess.run(["bsdtar", "-xOf", str(path), "content.xml"], capture_output=True).stdout.decode("utf-8", errors="replace")
    grid: list[list[str]] = []
    for row in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", xml, re.S):
        cells: list[str] = []
        for attrs, body in re.findall(r"<table:(?:covered-)?table-cell([^>]*?)(?:/>|>(.*?)</table:(?:covered-)?table-cell>)", row, re.S):
            rep = re.search(r'number-columns-repeated="(\d+)"', attrs)
            txt = _html.unescape(re.sub(r"<[^>]+>", " ", body or "")).strip()
            cells.extend([txt] * min(int(rep.group(1)) if rep else 1, 20))
        if any(cells):
            grid.append(cells)
    return grid


@register
class OPElectronics(Adapter):
    vendor = "opelectronics"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        for page in range(1, 8):
            h = self.f.get_text(f"{CATEGORY}?page={page}" if page > 1 else CATEGORY, ".html") or ""
            arts = re.findall(r'<article class="product-miniature[^"]*" data-id-product="(\d+)"[^>]*>(.*?)</article>', h, re.S)
            if not arts:
                break
            for pid, body in arts:
                href = re.search(r'href="(https://www\.op-electronics\.com/en/[^"]+\.html)"', body)
                name = re.search(r'alt\s*=\s*"([^"]+)"', body)
                if not href or not name or href.group(1) in self.products:
                    continue
                title = _html.unescape(name.group(1))
                if _SKIP.search(title):
                    continue
                self.products[href.group(1)] = {"id": pid, "name": title}
                yield href.group(1)

    def parse(self, url: str) -> Circuit | None:
        h = self.f.get_text(url, ".html")
        m = re.search(r'id="product-details"\s+data-product="([^"]+)"', h or "")
        if not m:
            return None
        d = json.loads(_html.unescape(m.group(1)))
        title = clean_text(_html.unescape(d.get("name", "")))
        name = re.sub(r"\s+PCB\s*$", "", title).strip()
        short = html_to_text(d.get("description_short") or "")
        slug = d.get("link_rewrite") or url.rsplit("/", 1)[-1].replace(".html", "")
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), None)
        if based_on is None:
            based_on = clean_text(_TM.sub("", short)).strip(" .")
            based_on = re.sub(r"\s+sharing the same PCB.*$|^Suitable.*$|\s+REPLICA$|\s+with optional.*$", "", based_on, flags=re.I)
            if len(based_on) > 60 or re.search(r"\b(?:is|are|the pcb|board)\b", based_on, re.I) or based_on.lower() == name.lower():
                based_on = ""
            based_on = based_on.replace("EHX ", "Electro-Harmonix ")
        desc = html_to_text(d.get("description") or "")
        atts = [a for a in d.get("attachments", []) if not _DRILL.search(a.get("name", "") + " " + a.get("mime", ""))]
        atts.sort(key=lambda a: 0 if re.search(r"datasheet|partlist|bom", a.get("name", ""), re.I) else 1)
        att = atts[:1]
        doc = f"{BASE}/en/index.php?controller=attachment&id_attachment={att[0]['id_attachment']}" if att else ""
        img = ((d.get("cover") or {}).get("large") or {}).get("url", "")
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=url,
                    based_on=based_on, description=(short + " " + desc).strip()[:700], price=float(d["price_amount"]) if d.get("price_amount") is not None else None,
                    currency="EUR", in_stock=d.get("availability") == "available" if d.get("availability") else None,
                    doc_url=doc or url, image_url=img, enclosure=find_enclosure(desc))
        for a in d.get("attachments", []):
            if a is not att[0] if att else True:
                c.extra_docs[a.get("name", "")[:40]] = f"{BASE}/en/index.php?controller=attachment&id_attachment={a['id_attachment']}"
        if doc:
            pdf = self.f.get_file(doc, ".bin")
            if pdf and pdf.read_bytes()[:4] in (b"PK\x03\x04", b"Rar!"):  # an archive of documents: keep the one holding the part list
                pdf = _unpack_partlist(pdf, RAW_DIR / self.vendor / f"{c.slug}-doc")
            if pdf and pdf.suffix == ".ods":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                c.bom, _ = grid_bom(_ods_grid(pdf))
            elif pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                c.bom = parse_partlist(pages)
                if len(c.bom) < 8:
                    c.bom = max(c.bom, ocr_bom(pdf, self.vendor, c.slug), key=len)
                mv = re.search(r"document revision\s+(\S+)", "\n".join(pages), re.I)
                c.doc_version = mv.group(1) if mv else ""
                page_no = find_schematic_page(pages)
                if page_no:
                    png = CACHE_DIR / self.vendor / f"{c.slug}-schematic.png"
                    if not png.exists():
                        render_page(pdf, page_no, png)
                    c.schematic_local, c.schematic_page = str(png.relative_to(DATA_DIR)), page_no
        c.category = next((v for k, v in _CATEGORY.items() if k in slug), "") or ("Utility" if _UTILITY.search(name) else classify(name, based_on, desc[:300]))
        variants = sorted({r.variant for r in c.bom if r.variant})
        if variants:
            c.tags = [f"{len(variants)} builds"]
        pots = [r for r in c.bom if r.category == "POT" and (not r.variant or r.variant == variants[0])]
        named = list(dict.fromkeys(r.ref.replace("_", " ").rstrip("*") for r in pots if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref) and not re.search(r"trim|bias", r.ref, re.I)))
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += list(dict.fromkeys(r.ref for r in c.bom if r.category == "SW" and not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref) and r.ref not in c.controls))
        return c
