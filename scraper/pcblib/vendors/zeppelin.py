"""Zeppelin Design Labs adapter: a Shopify store (USD) whose one guitar-pedal kit, the
Quaverato harmonic tremolo, has an assembly-instructions PDF with a kit bill of materials
(ZDL part number / description / designators / quantity)."""
from __future__ import annotations

import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..pdf import expand_refs, pdf_text_pages, process_document
from ..taxonomy import find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://zeppelindesignlabs.com"
_KITS = {"quaverato-harmonic-tremolo-pedal-diy-kit": {"name": "Quaverato", "category": "Tremolo",
         "doc": "https://cdn.shopify.com/s/files/1/0833/3731/4563/files/zeppelin-quaverato-assembly-instructions.pdf",
         "manual": "https://cdn.shopify.com/s/files/1/0833/3731/4563/files/zeppelin-quaverato-owners-manual.pdf",
         "controls": ["Depth", "Rate", "Gain", "Spacing", "Multiplier", "Shape", "Duty"]}}
_ROW = re.compile(r"^\s*([A-Z]{2}\s?-\d{2}-\d{2})\s{2,}(.+?)\s{2,}(\S.*?)\s{2,}(\d+)\s*$")
_VALUE = re.compile(r"(\d+(?:\.\d+)?\s?(?:[pnuµ]F|[kKM]?(?:Ω|ohm)?|MHz)|[A-Za-z0-9]{2,}[A-Za-z0-9-]*\d[A-Za-z0-9-]*)\s*$")
_TRAIL = re.compile(r"\s+(Bipolar|NP|Non-Polar|Audio|Linear|Lin|Log)\s*$", re.I)


def parse_kit_bom(pages: list[str]) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()
    for ln in "\n".join(pages).splitlines():
        m = _ROW.match(ln)
        if not m:
            continue
        _, desc, notes, _qty = m.groups()
        refs = [r for r in expand_refs(notes.replace(" - ", "-")) if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.strip())]
        if not refs:
            continue
        desc = desc.replace("Diode1N", "Diode 1N")
        trail = _TRAIL.search(desc)
        if trail:
            desc = desc[:trail.start()]
        mv = _VALUE.search(desc)
        if not mv:
            continue
        value = mv.group(1).strip()
        ptype = clean_text(desc[:mv.start()]).strip(" ,") + (f" ({trail.group(1)})" if trail else "")
        for ref in refs:
            ref = ref.strip()
            if ref in seen:
                continue
            r = normalize_row(BomRow(ref=ref, value=value, part_type=ptype))
            if is_plausible(r):
                seen.add(ref)
                rows.append(r)
    return rows


@register
class Zeppelin(Adapter):
    vendor = "zeppelin"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        for handle in _KITS:
            raw = self.f.get_text(f"{BASE}/products/{handle}.json", ".json")
            if raw:
                self.products[handle] = json.loads(raw).get("product", {})
                yield handle

    def parse(self, handle: str) -> Circuit | None:
        p, k = self.products.get(handle), _KITS[handle]
        if not p:
            return None
        body = html_to_text(p.get("body_html") or "")
        v = (p.get("variants") or [{}])[0]
        c = Circuit(vendor=self.vendor, slug=k["name"].lower(), name=k["name"], url=f"{BASE}/products/{handle}", description=body[:700],
                    price=float(v["price"]) if re.match(r"^\d+(\.\d+)?$", str(v.get("price", ""))) else None, currency="USD",
                    in_stock=v.get("available"), doc_url=k["doc"], image_url=((p.get("images") or [{}])[0].get("src") or "").split("?")[0],
                    enclosure=find_enclosure(body), category=k["category"], controls=k["controls"], tags=["kit"])
        c.extra_docs["Owner's manual"] = k["manual"]
        pdf = self.f.get_file(k["doc"], ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            res = process_document(pdf, self.vendor, c.slug)
            c.bom = max(res["bom"], parse_kit_bom(pages), key=len)
            c.schematic_local, c.schematic_page, c.doc_version = res["schematic_local"], res["schematic_page"], res["doc_version"]
        return c
