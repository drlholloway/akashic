"""Sheepy Love adapter. Shopify store: the public products.json lists the catalog,
each product page links a build document PDF (KiCad-exported: text BOM + vector schematic)."""
from __future__ import annotations

import json
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..pdf import process_document, pdf_text_pages
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://sheepylove.com"
_TAG_CATEGORY = {"od": "Overdrive", "distortion": "Distortion", "fuzz": "Fuzz", "boost": "Boost",
                 "utility": "Utility", "modulation": "Vibrato / Chorus", "delay": "Delay", "filter": "EQ / Filter"}


@register
class SheepyLove(Adapter):
    vendor = "sheepylove"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page = 1
        while True:
            raw = self.f.get_text(f"{BASE}/products.json?limit=250&page={page}", ".json")
            items = json.loads(raw).get("products", []) if raw else []
            if not items:
                break
            for pr in items:
                tags = {t.lower() for t in pr.get("tags", [])}
                if pr.get("product_type") != "PCB" or tags & {"faceplate", "drill template"}:
                    continue
                self.products[pr["handle"]] = pr
                yield pr["handle"]
            page += 1

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        url = f"{BASE}/products/{handle}"
        html = self.f.get_text(url) or ""
        pdfs = sorted(set(re.findall(r'(?://|https://)sheepylove\.com/cdn/shop/files/[^"?]+\.pdf', html)),
                      key=lambda u: (0 if "build_doc" in u.lower() else 1, u))
        if not pdfs:
            return None  # adapters, breakouts and templates have no build document
        doc_url = "https:" + pdfs[0] if pdfs[0].startswith("//") else pdfs[0]

        body_html = pr.get("body_html") or ""
        body = html_to_text(body_html)
        m = re.search(r"Sounds\s+like\s+(.+?)(?:\n|$)", body, re.I)
        based_on = clean_text(m.group(1)) if m else ""
        based_on = re.sub(r"\s+with mods by .*$", "", based_on).rstrip(".")
        based_on = re.sub(r"^(?:the original|the|an|a)\s+", "", based_on, flags=re.I)
        description = re.sub(r"^Sounds\s+like\s+[^\n]*\n?", "", body, flags=re.I).strip()

        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        in_stock = variant.get("available")
        images = [i["src"] for i in pr.get("images", [])]
        sku = ""
        m = re.search(r"/files/(PCB\d{3})[_-]", (images[0] if images else "") + " " + doc_url)
        if m:
            sku = m.group(1)
        tags = pr.get("tags", [])
        tag_cat = next((_TAG_CATEGORY[t.lower()] for t in tags if t.lower() in _TAG_CATEGORY and t.lower() != "od"), "")
        category = tag_cat or classify(based_on, pr["title"], description[:300]) if tag_cat or based_on else classify(pr["title"], description[:300], "overdrive" if "OD" in tags else "")
        if not tag_cat and "OD" in tags and category in ("Other", "Overdrive"):
            category = "Overdrive"

        c = Circuit(
            vendor=self.vendor, slug=handle, name=pr["title"], url=url, based_on=based_on,
            description=description, category=category, effect_type=", ".join(tags),
            tags=[t for t in tags if t.lower() not in ("od",)] or [], price=price, currency="EUR",
            sku=sku, in_stock=in_stock, doc_url=doc_url, image_url=images[0] if images else "",
        )
        for a in HTMLParser(body_html).css("a[href]"):
            href = a.attributes.get("href", "")
            if href.startswith("http") and "sheepylove.com" not in href:
                c.extra_docs[clean_text(a.text()) or "Designer's notes"] = href

        pdf = self.f.get_file(doc_url, ".pdf")
        if pdf:
            c.__dict__.update(process_document(pdf, self.vendor, handle))
            pages = pdf_text_pages(pdf)
            c.enclosure = find_enclosure(description, *pages)
            m = re.search(r"Updated:\s*(\d{4}-\d{2}-\d{2})", pages[0] if pages else "")
            if m:
                c.doc_version = m.group(1)
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                c.controls = [f"{len(pots)} knobs"]
        return c
