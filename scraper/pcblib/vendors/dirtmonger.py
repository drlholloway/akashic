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
from .base import Adapter, clean_text, html_to_text
from .deadendfx import _drive_download

BASE = "https://dirtmongerinstruments.com"
COLLECTION = f"{BASE}/collections/diy-pcb-1/products.json?limit=250"
_ORIG = re.compile(r"(?:DIY clone of (?:the |an? )?|Circuit board for (?:the |an? )?|(?:to )?build (?:either |of )?(?:the |an? )?|clone of (?:the |an? )?)([A-Z][^.\n]{2,70}?)(?:\s+DIY build|\s+build\b|\s+depending\b|\s+with\b|[.\n]|$)")

_REF = r"[A-Z]{1,3}\d{1,3}"
_VALUE_REFS = re.compile(rf"^(.+?)\s+[-–]\s+((?:{_REF}|[A-Z][a-z]+)(?:\s*,\s*(?:{_REF}|[A-Z][a-z]+))*)\s*$")
_REF_VALUE = re.compile(rf"^({_REF})\s+[-–]\s+(\S+)")


def parse_value_list(pages: list[str]) -> list[BomRow]:
    """Newer docs list parts in two columns as 'value - refs' ('100K - R7, R20',
    'C50K anti log - Treble, Bass') and 'ref - value' for ICs and transistors."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        if not re.search(r"^\s*Parts List\s*$", page, re.M):
            continue
        cells = [c.strip() for ln in page.splitlines() for c in re.split(r"\s{3,}", ln) if c.strip()]
        for cell in cells:
            if m := _REF_VALUE.match(cell):
                pairs = [(m.group(1), m.group(2))]
            elif m := _VALUE_REFS.match(cell):
                value = re.sub(r",?\s+\d+V$|\s+(?:anti[ -]?)?log$|\s+lin$", "", m.group(1), flags=re.I).rstrip(",")
                value = re.sub(r"\s*ohm$", "R", value, flags=re.I)
                pairs = [(r, value) for part in m.group(2).split(",") for r in expand_refs(part.strip())]
            else:
                continue
            for ref, value in pairs:
                pot = not re.fullmatch(_REF, ref)
                r = normalize_row(BomRow(ref=ref, value=value, category="POT" if pot else ""))
                if ref not in seen and (pot or is_plausible(r)):
                    seen.add(ref)
                    rows.append(r)
    return rows


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
        docs = [u for u, t in links if "drive.google.com" in u and re.search(r"build|doc", t, re.I)]
        drills = [u for u, t in links if re.search(r"drill", t, re.I) or "taydakits" in u]
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
            if BASE in u and "products/" in u and "utm_" in u:
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
            if len(listed) > len(c.bom):
                c.bom = listed
            if len(c.bom) < 8:
                ocr = ocr_bom(pdf, self.vendor, handle, max_pages=5, thorough=True)
                if len(ocr) > len(c.bom):
                    c.bom = ocr
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
                c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
