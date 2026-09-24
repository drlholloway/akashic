"""Other Pedals adapter. A Squarespace shop of finished pedals with a row of DIY PCBs whose
documents are JPEG images: a value-first parts list ("4k7 - R4C,R10", "A100k - LEVEL") in
two columns, a schematic and a drill guide. The images are bundled into one cached PDF per
board so the schematic page and the shared machinery apply; two boards have PDF build docs
with an EasyEDA-style Name / Designator / Footprint / Quantity table instead."""
from __future__ import annotations

import html as _html
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_bom, process_document, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.otherpedals.com"
_BASED_ON = {"americas-preamp": "DOD 250", "skywater-pcb": "Fuzz Face", "so-long-and-thanks-for-all-the-fuzz-pcb": "Electra Distortion",
             "honey-coma-pcb-yellow": "Roland AF-100 Bee Baa", "everythang-vibrato-phaser-tbntt": "DOD FX22 Vibrothang",
             "od30-overdrive-pcb": "Digiplay OD-30", "bassment-show-distortion-pcb": "Arion Bass Distortion",
             "all-your-bass-overdrive-pcb": "DOD FX91 Bass Overdrive", "different-green-pcb": "Ibanez TS7 Tube Screamer",
             "super-murid-64-pcb": "ProCo RAT"}
_CATEGORY = {"honey-coma-pcb-yellow": "Fuzz", "americas-preamp": "Overdrive", "skywater-pcb": "Fuzz"}
_SEG = re.compile(r"(?P<val>[A-Za-z0-9][A-Za-z0-9.,/’'\"]*(?: [A-Za-z0-9/]+){0,2}?)\s*-\s*"
                  r"(?P<refs>(?:[A-Z]{1,3}\d{1,3}[A-Z]?|LED\d*|CLR)(?:\s*,\s*(?:[A-Z]{0,3}\d{1,3}[A-Z]?|LED\d*))*"
                  r"|(?:[A-Z][a-z]{2,11}\d?(?: [A-Z][a-z]{2,11}\d?)?|[A-Z]{3,12}(?:/[A-Z]{3,12})?)(?:\s*,\s*(?:[A-Z][a-z]{2,11}\d?(?: [A-Z][a-z]{2,11}\d?)?|[A-Z]{3,12}(?:/[A-Z]{3,12})?))*)(?P<type>\s+[a-z][a-z ]{2,20})?")
_COLOR = re.compile(r"^(RED|GREEN|BLUE|YELLOW|WHITE|AMBER|ORANGE)\s+\d+mm", re.I)


def parse_value_dash(text: str) -> list[BomRow]:
    """'100R - R9', '10k - R2,R4B,R6', '1N914/1N4148 - CD3,CD4', 'A100k - LEVEL', 'RED 3mm - CD7'."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        while ln.endswith(("-", ",")) and i + 1 < len(lines):  # the designator or name list wrapped
            ln = ln + " " + lines[i + 1]
            i += 1
        i += 1
        for nm, kind, val in re.findall(r"(?<![A-Za-z0-9-])((?:[A-Z][a-z]{2,11}\d?(?: [A-Z][a-z]{2,11}\d?)?|[A-Z]{3,12}(?:/[A-Z]{3,12})?))\s+(?:([ABCW]\d+[kKM]?)|((?:[SD]P[SD]T|3PDT)(?:-?on/(?:off/)?on)?))(?![A-Za-z0-9])", ln):
            # name first: 'LEVEL A100k', 'MODE SPDT-on/on'
            name = nm.title()
            if name in seen or name.lower() in ("value", "part", "type"):
                continue
            seen.add(name)
            if kind:
                rows.append(normalize_row(BomRow(ref=name, value=kind.upper(), part_type="Potentiometer", category="POT", notes="OCR")))
            else:
                rows.append(normalize_row(BomRow(ref=name, value=val.split("-")[0].upper(), part_type="Switch", notes="OCR; " + val.split("-", 1)[1] if "-" in val else "OCR", category="SW")))
        for s in _SEG.finditer(ln):
            val, refs, typ = s.group("val").strip(), s.group("refs"), (s.group("type") or "").strip()
            note = "OCR"
            if _COLOR.match(val):
                note, val = f"OCR; {val.split()[0].lower()} LED", "LED"
            elif "/" in val:
                first, rest = val.split("/", 1)
                val, note = first.strip(), f"OCR; or {rest.strip()}"
            if not re.match(r"[A-Z]{1,3}\d|LED|CLR", refs):  # named pots: 'LEVEL', 'Clean Level, Dirt Level, Distortion'
                if re.fullmatch(r"[ABCW]\d+[kKM]?", val):
                    for nm in re.split(r"\s*,\s*", refs):
                        nm = nm.title()
                        if nm and nm not in seen:
                            seen.add(nm)
                            rows.append(normalize_row(BomRow(ref=nm, value=val.upper(), part_type="Potentiometer", category="POT", notes="OCR")))
                continue
            pre = re.match(r"[A-Z]+", refs).group(0)
            for ref in re.split(r"\s*,\s*", refs):
                if not re.match(r"[A-Z]", ref):
                    ref = pre + ref
                if ref.upper() in seen:
                    continue
                nr = normalize_row(BomRow(ref=ref.upper(), value=val, part_type=typ, notes=note))
                if is_plausible(nr):
                    seen.add(ref.upper())
                    rows.append(nr)
    return rows


def image_bom(png: Path) -> list[BomRow]:
    """OCR the parts-list image as one block and as two overlapping columns split at 45% and
    50% of the width; the reading that yields the most rows wins (the list is two-column but
    the artwork behind it defeats a measured split)."""
    import pymupdf as fitz
    pix = fitz.Pixmap(str(png))
    gray = fitz.Pixmap(fitz.csGRAY, pix) if pix.n - pix.alpha >= 3 else pix
    W, H = gray.width, gray.height
    rows: list[BomRow] = []
    seen: set[str] = set()
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(page.rect, pixmap=gray)
    for split in (None, 0.45, 0.5):  # the readings are unioned: each recovers rows the others clip
        parts = [(0, W)] if split is None else [(0, int(W * (split + 0.04))), (int(W * (split - 0.04)), W)]
        for k, (a, b) in enumerate(parts):
            out = png.with_name(f"{png.stem}-s{int((split or 0) * 100)}-{k}.png")
            if not out.exists():
                page.get_pixmap(clip=fitz.Rect(a, 0, b, H), dpi=72).save(out)
            txt_path = out.with_suffix(".txt")
            if not txt_path.exists():
                txt_path.write_text(subprocess.run(["tesseract", str(out), "-", "--psm", "4"], capture_output=True, text=True).stdout)
            for r in parse_value_dash(txt_path.read_text()):
                if r.ref not in seen:
                    seen.add(r.ref)
                    rows.append(r)
    doc.close()
    return rows


@register
class OtherPedals(Adapter):
    vendor = "otherpedals"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.items: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/shop?format=json", ".json")
        for it in (json.loads(raw).get("items", []) if raw else []):
            if re.search(r"\bPCB\b", it.get("title", ""), re.I):
                slug = it["fullUrl"].rsplit("/", 1)[-1]
                self.items[slug] = it
                yield slug

    def parse(self, slug: str) -> Circuit | None:
        it = self.items.get(slug)
        if not it:
            return None
        raw = self.f.get_text(f"{BASE}{it['fullUrl']}?format=json", ".json")
        if raw:
            try:
                it = {**it, **(json.loads(raw).get("item") or {})}
            except ValueError:
                pass
        excerpt = it.get("excerpt") or ""
        links = [(u, clean_text(re.sub(r"<[^>]+>", " ", t))) for u, t in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', excerpt, re.S)]
        docs = [(BASE + u if u.startswith("/") else u, t) for u, t in links if re.search(r"\.(?:jpe?g|png|pdf)(?:\?|$)", u, re.I)]
        if not docs:
            return None
        name = re.sub(r"\s*\bPCB\b\s*$", "", clean_text(_html.unescape(it["title"])), flags=re.I)
        text = html_to_text(excerpt)
        description = clean_text(re.split(r"\b(?:Documents?|Documentation|Build (?:Doc|Guide|Documents))\s*:|Build Doc here|Join the discord", text, 1, flags=re.I)[0])
        description = re.sub(r"\*{2,}.*?\*{2,}", "", description).strip()
        variant = (it.get("variants") or [{}])[0]
        price = variant.get("price")
        if re.fullmatch(r"[a-z0-9]{20,}", slug):  # Squarespace's random id: slug from the name instead
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("’", "").replace("'", "")).strip("-")
        key = slug
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=BASE + it["fullUrl"], based_on=_BASED_ON.get(key, ""), description=description,
                    price=(price / 100) if isinstance(price, (int, float)) else None, currency="USD",
                    in_stock=bool(variant.get("unlimited") or (variant.get("qtyInStock") or 0) > 0) if variant else None,
                    image_url=(((it.get("items") or [{}])[0].get("assetUrl") or it.get("assetUrl") or "")).split("?")[0],
                    enclosure=find_enclosure(text))
        for u, t in docs:
            label = t[:40] if t and t.lower() not in ("here", "link", "document", "pdf") else ("Build document" if u.lower().endswith(".pdf") else "Document")
            c.extra_docs.setdefault(label, u)
        pdfs = [u for u, t in docs if u.lower().endswith(".pdf")]
        if pdfs:
            pdf = self.f.get_file(pdfs[0], ".pdf")
            c.doc_url = pdfs[0]
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                res = process_document(pdf, self.vendor, slug)
                c.doc_local, c.bom, c.schematic_local, c.schematic_page, c.doc_version = res["doc_local"], res["bom"], res["schematic_local"], res["schematic_page"], res["doc_version"]
                if len(c.bom) < 8:
                    c.bom = max(c.bom, ocr_bom(pdf, self.vendor, slug), key=len)
        else:
            # Bundle the images into one PDF: parts list first, then the schematic, then the drill guide.
            order = {"bom": 0, "bill": 0, "schem": 1, "drill": 2}
            imgs = sorted(((min((v for k, v in order.items() if k in t.lower()), default=3), u, t) for u, t in docs if not u.lower().endswith(".pdf")))
            paths = [(self.f.get_file(u, Path(u).suffix.lower() or ".jpg"), t) for _, u, t in imgs]
            paths = [(p, t) for p, t in paths if p and p.stat().st_size > 1000]
            if not paths:
                return c
            import pymupdf as fitz
            out = DATA_DIR / "raw" / self.vendor / f"{slug}-doc.pdf"
            out.parent.mkdir(parents=True, exist_ok=True)
            if not out.exists():
                pdf = fitz.open()
                for p, _ in paths:
                    pix = fitz.Pixmap(str(p))
                    page = pdf.new_page(width=pix.width * 72 / 300, height=pix.height * 72 / 300)
                    page.insert_image(page.rect, pixmap=pix)
                pdf.save(out)
                pdf.close()
            c.doc_url = imgs[0][1]
            c.doc_local = str(out.relative_to(DATA_DIR))
            sch = next((i for i, (_, t) in enumerate(paths, 1) if "schem" in t.lower()), None)
            if sch:
                c.schematic_page = sch
                png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                if not png.exists():
                    render_page(out, sch, png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
            bom_img = next((p for p, t in paths if re.search(r"bom|bill", t, re.I)), None)
            if bom_img:
                c.bom = image_bom(bom_img)
        c.category = _CATEGORY.get(slug) or classify(name, c.based_on, description)
        c.controls = [r.ref for r in c.bom if r.category == "POT"] + [r.ref for r in c.bom if r.category == "SW"]
        return c
