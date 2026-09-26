"""Gigahearts FX adapter. A small UK Shopify shop whose PCB collection holds a handful of
boards; the rest of the store is finished pedals. Only some product descriptions link the
build document (a Word-exported PDF with an ordinary parts table); the others say the
document comes with the board, so their parts are read from the schematic image on the
product page by OCR."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_schematic_bom, pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.gigaheartsfx.com"
COLLECTION = f"{BASE}/collections/pcb-products/products.json?limit=250"

# The descriptions name the originals loosely ("the ultimate Broadcast variant"); the build doc
# states the GIG BUFF's ("based on the EHX/JHS BIG MUFF 2"). The category is set where the
# description's words mislead the classifier (the Broadcast's "treble cut" reads as a filter).
_BASED_ON = [
    (re.compile(r"gig-buff"), "EHX/JHS Big Muff 2", "Fuzz"),
    (re.compile(r"broadcast"), "Hudson Broadcast", "Overdrive"),
    (re.compile(r"full-moon"), "G.S. Wyllie Moon Rock / JHS Coyote", "Fuzz"),
]


@register
class Gigahearts(Adapter):
    vendor = "gigahearts"

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
        body = html_to_text(body_html)
        title = clean_text(_html.unescape(pr["title"]))
        # 'Full Moon  PCB Project - G.S. Wyllie Moon Rock / JHS Coyote', 'GIG BUFF PCB v1_3', '"Broadcast" with mods'
        name = re.split(r"\s+-\s+", title)[0]
        name = clean_text(re.sub(r"\bPCB(?: Project)?\b", "", name).replace('"', "").replace("_", "."))
        based_on, category = next(((orig, cat) for pat, orig, cat in _BASED_ON if pat.search(handle)), ("", ""))
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        images = [i["src"].split("?")[0] for i in pr.get("images") or []]
        c = Circuit(
            vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/products/{handle}", based_on=based_on,
            description=re.sub(r"\s*Build Document \(Latest Version [^)]*\)\s*", " ", body).strip(),
            category=category or classify(based_on, name, body[:400]), price=price, currency="GBP",
            in_stock=variant.get("available"), enclosure=find_enclosure(body), image_url=images[0] if images else "",
        )
        docs = [u for u in re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', body_html)]
        if docs:
            c.doc_url = docs[0]
            pdf = self.f.get_file(c.doc_url, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                c.__dict__.update({k: v for k, v in process_document(pdf, self.vendor, handle).items() if k in ("bom", "schematic_local", "schematic_page", "doc_version")})
                c.enclosure = c.enclosure or find_enclosure(*pages[:2])
        if not c.bom:
            # No public build doc: the product page shows the schematic, so pair its labels by OCR.
            schem = [u for u in images if re.search(r"schem", u.rsplit("/", 1)[-1], re.I)]
            if schem:
                blob = self.f.get_file(schem[0], "." + schem[0].rsplit(".", 1)[-1].lower())
                if blob:
                    png = CACHE_DIR / self.vendor / f"{handle}-schematic.png"
                    png.parent.mkdir(parents=True, exist_ok=True)
                    if not png.exists():
                        from PIL import Image
                        Image.MAX_IMAGE_PIXELS = None
                        im = Image.open(blob)
                        (im.convert("RGB") if im.mode not in ("RGB", "L") else im).save(png)
                    c.schematic_local = str(png.relative_to(DATA_DIR))
                    c.schematic_page = 1
                    c.bom = ocr_schematic_bom(png)
        for r in c.bom:
            if r.category == "POT" and re.search(r"\bLED\b", r.ref, re.I):
                r.category, r.part_type = "TRIM", "Trimmer"  # the LED brightness pot is a board-mounted 3362 trimmer, not a knob
        pots = [r for r in c.bom if r.category == "POT"]
        if pots:
            named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
            c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
