"""1776 Effects adapter: a Shopify shop whose every product links a text build document PDF
(parts table, named pots, schematic) hosted on the Shopify CDN."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import ocr_bom, pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://1776effects.com"
COLLECTION = f"{BASE}/collections/all/products.json?limit=250"
_BASED_ON = {"bear-hug-compressor-new-version": "Jon Patton Bear Hug", "britannia": "RunOffGroove Britannia", "buzz-saw-fuzz": "Roland AF-100 Bee Baa",
             "cardinal-tremolo-v2": "", "five-oclock-fuzz": "Fuzz Face", "multiplex-echo-machine": "", "multiplex-jr-delay": "Maestro Echoplex EP-3",
             "rub-a-dub-deluxe-pcb-only": "", "rub-a-dub-reverb": "", "six-shooter-6-band-eq": "", "sucker-punch-fuzz": "Colorsound Bass Fuzz / Super Tonebender",
             "thunderbird": "RunOffGroove Thunderbird", "unicorn-breath-buffer": "Klon Centaur buffer", "finish-line-relay-bypass": "", "opto-tron-optical-bypass": "",
             "mp-modulation-add-on-pcb": "", "3pdt-pcb": ""}
_CATEGORY = {"thunderbird": "Overdrive", "britannia": "Overdrive"}
_UTILITY = {"3pdt-pcb", "finish-line-relay-bypass", "opto-tron-optical-bypass", "mp-modulation-add-on-pcb"}


@register
class Effects1776(Adapter):
    vendor = "effects1776"

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
        docs = list(dict.fromkeys(u for u in re.findall(r'href="([^"]+)"', body_html) if re.search(r"\.pdf(?:\?|$)", u, re.I)))
        if not docs:
            return None  # the H11F1 optocoupler and other parts
        title = clean_text(_html.unescape(pr["title"]))
        name = re.sub(r"\s*[–-]\s*NEW Version$|\s*\(PCB only\)$", "", title, flags=re.I).strip()
        body = html_to_text(body_html)
        body = re.sub(r"\s*\S+ Build Document\s*$", "", body).strip()
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        c = Circuit(vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/products/{handle}", based_on=_BASED_ON.get(handle, ""),
                    description=body, price=price, currency="USD", in_stock=variant.get("available"), doc_url=docs[0].split("?")[0],
                    enclosure=find_enclosure(body), image_url=(pr.get("images") or [{}])[0].get("src", "").split("?")[0])
        pdf = self.f.get_file(docs[0], ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            c.enclosure = c.enclosure or find_enclosure("\n".join(pages[:3]))
            mv = re.search(r"\b(?:v|version|rev\.?)\s?(\d+(?:\.\d+)+)\b", "\n".join(pages[:2]), re.I)
            c.doc_version = mv.group(1) if mv else ""
            res = process_document(pdf, self.vendor, handle)
            c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
            if len(c.bom) < 8:
                c.bom = max(c.bom, ocr_bom(pdf, self.vendor, handle), key=len)
        c.category = "Utility" if handle in _UTILITY else _CATEGORY.get(handle) or classify(name, c.based_on, body[:300])
        pots = [r for r in c.bom if r.category == "POT"]
        named = [r.ref.title() for r in pots if re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}\d?", r.ref)]
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{2,15}", r.ref)]
        return c
