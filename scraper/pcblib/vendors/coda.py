"""Coda Effects adapter: a WooCommerce shop (EUR) for six PCBs whose build documents are
Google Drive PDFs linked from the old Blogger product pages on coda-effects.com."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SHOP = "https://shop.coda-effects.com"
BLOG = "https://www.coda-effects.com"
_BLOG_SLUG = {"oecd-pcb": "ocde-pcb", "supreaux-deux-pcb": "slightly-modified-supreaux-deux-pcb"}
_BASED_ON = {"supreaux-deux-pcb": "RunOffGroove Supreaux Deux", "oecd-pcb": "Fulltone OCD", "fools-gold-pcb": "EarthQuaker Devices Acapulco Gold",
             "black-hole-pcb": "Sunn Model T preamp", "golden-hour-pcb": "Vemuram Jan Ray", "dolmen-fuzz-pcb": "Electro-Harmonix Big Muff"}
_VARIANTS = {"Head violet": "V2 Ram's Head violet era", "Head 73": "V2 Ram's Head 73", "Russian": "Green Russian Tall Font",
             "with Power": "Civil War with Power Booster", "V3 Big Muff": "V3 Big Muff"}


@register
class Coda(Adapter):
    vendor = "coda"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{SHOP}/wp-json/wc/store/v1/products?per_page=100", ".json")
        for p in json.loads(raw) if raw else []:
            if any(c["slug"] == "pcb" for c in p.get("categories", [])):
                self.products[p["slug"]] = p
                yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        name = re.sub(r"\s+PCB\s*$", "", clean_text(_html.unescape(p["name"]))).replace("OECD", "OCDE")
        prices = p.get("prices") or {}
        short = html_to_text(p.get("short_description") or "")
        m = re.match(r"^[–-]\s*(.+?)\s*[–-]$", short)
        based_on = _BASED_ON.get(slug) or (clean_text(m.group(1)) if m else "")
        blog = f"{BLOG}/p/{_BLOG_SLUG.get(slug, slug)}.html"
        page = self.f.get_text(blog, ".html") or ""
        drive = re.search(r'href="(https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/[^"]*)"', page)
        c = Circuit(vendor=self.vendor, slug=slug.replace("-pcb", ""), name=name, url=p["permalink"], based_on=based_on,
                    description=html_to_text(p.get("description") or "")[:700],
                    price=int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None,
                    currency=prices.get("currency_code", "EUR"), in_stock=p.get("is_in_stock"),
                    doc_url=_html.unescape(drive.group(1)) if drive else blog, image_url=(p.get("images") or [{}])[0].get("src", ""))
        c.extra_docs["Product page on coda-effects.com"] = blog
        if drive:
            rk = re.search(r"resourcekey=([A-Za-z0-9_-]+)", _html.unescape(drive.group(1)))
            dl = f"https://drive.google.com/uc?export=download&id={drive.group(2)}" + (f"&resourcekey={rk.group(1)}" if rk else "")
            pdf = self.f.get_file(dl, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                res = process_document(pdf, self.vendor, c.slug)
                c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
                for r in c.bom:
                    r.variant = _VARIANTS.get(r.variant, r.variant)
                c.bom = [r for r in c.bom if r.variant != "Name" and r.ref.upper() != "ENCLOSURE"]
                for r in c.bom:
                    if r.ref.upper() == "LDR":
                        r.category = "OPTO"
                c.enclosure = find_enclosure("\n".join(pages))
                c.description = c.description or clean_text(" ".join(pages[:1]))[:700]
        c.category = classify(name, based_on, c.description[:300])
        first = next((r.variant for r in c.bom if r.variant), "")
        pots = [r for r in c.bom if r.category == "POT" and r.variant in ("", first) and not re.match(r"^POT\d|^BOOST$|^LDR$", r.ref, re.I)]
        named = list(dict.fromkeys(r.ref.title() if r.ref.isupper() else r.ref for r in pots if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref)))
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        variants = sorted({r.variant for r in c.bom if r.variant})
        if variants:
            c.tags = [f"{len(variants)} builds"]
        return c
