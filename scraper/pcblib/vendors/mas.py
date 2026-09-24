"""MAS Effects adapter: a Shopify DIY collection that is mostly kits and accessories with a
handful of circuit PCBs whose documents live on mas-effects.com and GitHub."""
from __future__ import annotations

import csv
import html as _html
import io
import json
import re
from typing import Iterable

from ..gsheet import grid_bom
from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import ocr_bom, pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://shop.mas-effects.com"
COLLECTION = f"{BASE}/collections/diy/products.json?limit=250"
_BOARDS = {
    "dark-commotion-pcb-ibanez-black-noise-clone": {"name": "Dark Commotion", "based_on": "Ibanez BN-5 Black Noise", "category": "Distortion",
                                                    "docs": [("Build document", "https://mas-effects.com/files/black-noise-instructions.pdf")]},
    "mimirs-well-pcb": {"name": "Mimir's Well", "based_on": "", "category": "Other",
                        "docs": [("Bill of materials", "https://raw.githubusercontent.com/mstratman/fv1-pedal-platform/master/assembly/bill-of-materials.pdf"),
                                 ("Layout with values", "https://raw.githubusercontent.com/mstratman/fv1-pedal-platform/master/assembly/layout-with-values.pdf"),
                                 ("Drill template", "https://raw.githubusercontent.com/mstratman/fv1-pedal-platform/master/assembly/drill-template.pdf"),
                                 ("Project on GitHub", "https://github.com/mstratman/fv1-pedal-platform")]},
    "ocd-ep-booster-pcb": {"name": "OCD + EP Booster", "based_on": "Fulltone OCD / Xotic EP Booster", "category": "Overdrive",
                           "docs": [("Bill of materials (CSV)", "https://raw.githubusercontent.com/mstratman/OCDEP/master/bill-of-materials/BOM.csv"),
                                    ("Schematic", "https://raw.githubusercontent.com/mstratman/OCDEP/master/schematic/Schematic_OCD-EP-Boost_2020-05-24_00-28-09.pdf"),
                                    ("Drill template", "https://raw.githubusercontent.com/mstratman/OCDEP/master/assembly/drill-template.pdf"),
                                    ("Project on GitHub", "https://github.com/mstratman/OCDEP")]},
    "bazz-fuss-star-pcb": {"name": "Star", "based_on": "Bazz Fuss", "category": "Fuzz", "docs": [("Build document", "https://mas-effects.com/star.pdf")]},
    "stompfuzz": {"name": "StompFuzz", "based_on": "", "category": "Fuzz",
                  "docs": [("Schematic", "https://raw.githubusercontent.com/mstratman/stompfuzz/master/stompfuzz-schematic.png"), ("Project on GitHub", "https://github.com/mstratman/stompfuzz")]},
    "3-picofuzz-pcbs": {"name": "PicoFuzz", "based_on": "", "category": "Fuzz",
                        "docs": [("Schematic", "https://raw.githubusercontent.com/mstratman/picofuzz/master/picofuzz-schematic.png"), ("Project on GitHub", "https://github.com/mstratman/picofuzz")]},
}


@register
class MAS(Adapter):
    vendor = "mas"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(COLLECTION, ".json")
        for pr in (json.loads(raw).get("products", []) if raw else []):
            if pr["handle"] in _BOARDS:
                self.products[pr["handle"]] = pr
                yield pr["handle"]

    def parse(self, handle: str) -> Circuit | None:
        pr, meta = self.products.get(handle), _BOARDS[handle]
        if not pr:
            return None
        body = html_to_text(pr.get("body_html") or "")
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        docs = meta["docs"]
        c = Circuit(vendor=self.vendor, slug=handle, name=meta["name"], url=f"{BASE}/products/{handle}", based_on=meta["based_on"],
                    description=clean_text(body), category=meta["category"], price=price, currency="USD", in_stock=variant.get("available"),
                    doc_url=docs[0][1], enclosure=find_enclosure(body), image_url=(pr.get("images") or [{}])[0].get("src", "").split("?")[0])
        for label, u in docs[1:]:
            c.extra_docs[label] = u
        first_pdf = next((u for _, u in docs if u.lower().endswith(".pdf")), None)
        if first_pdf:
            pdf = self.f.get_file(first_pdf, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                res = process_document(pdf, self.vendor, handle)
                c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
                c.enclosure = c.enclosure or find_enclosure("\n".join(pdf_text_pages(pdf)[:3]))
                if len(c.bom) < 8:
                    c.bom = max(c.bom, ocr_bom(pdf, self.vendor, handle), key=len)
        csv_url = next((u for _, u in docs if u.lower().endswith(".csv")), None)
        if csv_url:
            raw = self.f.get_text(csv_url, ".csv") or ""
            rows, enc = grid_bom(list(csv.reader(io.StringIO(raw))))
            if len(rows) > len(c.bom):
                c.bom = rows
            c.enclosure = c.enclosure or enc
        png_url = next((u for _, u in docs if u.lower().endswith(".png")), None)
        if png_url and not c.bom:  # a KiCad schematic export: pair its labels
            png = self.f.get_file(png_url, ".png")
            if png:
                import pymupdf as fitz
                from ..pdf import ocr_schematic_bom
                w = fitz.Pixmap(str(png)).width
                c.bom = ocr_schematic_bom(png, scale=2, px_per_pt=max(1.0, w / 600))
        pots = [r for r in c.bom if r.category == "POT"]
        named = [r.ref.title() for r in pots if re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}\d?", r.ref)]
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        return c
