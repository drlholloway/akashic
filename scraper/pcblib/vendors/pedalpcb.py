"""PedalPCB adapter. WooCommerce store; build docs on docs.pedalpcb.com."""
from __future__ import annotations

import json
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..pdf import process_document
from ..paths import RAW_DIR
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SITEMAP_INDEX = "https://www.pedalpcb.com/sitemap_index.xml"


@register
class PedalPCB(Adapter):
    vendor = "pedalpcb"

    def list_targets(self) -> Iterable[str]:
        idx = self.f.get_text(SITEMAP_INDEX, ".xml") or ""
        for sm in re.findall(r"<loc>(https://www\.pedalpcb\.com/product-sitemap\d+\.xml)</loc>", idx):
            xml = self.f.get_text(sm, ".xml") or ""
            for url in re.findall(r"<loc>(https://www\.pedalpcb\.com/product/[^<]+)</loc>", xml):
                yield url

    def parse(self, url: str) -> Circuit | None:
        html = self.f.get_text(url)
        if not html:
            return None
        doc = HTMLParser(html)
        ld = _product_ld(html)
        category_path = _unescape(ld.get("category", "")) if ld else ""
        if category_path.split(">")[0].strip().lower() in {"components", "enclosures", "hardware", "gift cards"}:
            return None
        pdfs = sorted(set(re.findall(r'https://docs\.pedalpcb\.com/[^"\' >]+\.pdf', html)))
        if not pdfs:
            return None  # not a documented PCB project (kits, parts, misc)

        h1 = doc.css_first("h1.product_title")
        name = clean_text(h1.text()) if h1 else clean_text((doc.css_first("title").text() if doc.css_first("title") else "").split(" - ")[0])
        sku_n = doc.css_first("span.sku")
        sku = clean_text(sku_n.text()) if sku_n else (ld.get("sku", "") if ld else "")
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        price = None
        pn = doc.css_first(".product-page-price") or doc.css_first("p.price")
        if pn:
            m = re.findall(r"(\d+(?:\.\d{2})?)", pn.text())
            if m:
                price = float(m[-1])
        stock = doc.css_first("p.stock")
        in_stock = None
        if stock:
            in_stock = "in-stock" in (stock.attributes.get("class") or "")

        desc_n = doc.css_first("#tab-description")
        desc_html = desc_n.html if desc_n else ""
        controls = [clean_text(_unescape(re.sub(r"<[^>]+>", "", m))) for m in
                    re.findall(r"<li>\s*<(?:b|strong)>(.*?)</(?:b|strong)>", desc_html)]
        controls = [c.strip(" –-") for c in controls if c.strip(" –-")]
        description = html_to_text(re.sub(r'<div class="icon-box.*$', "", desc_html, flags=re.S))

        based_on = ""
        if ld:
            m = re.search(r"Compare(?:d)? to (?:the )?(.+)", _unescape(ld.get("description", "")), re.I)
            if m:
                based_on = clean_text(m.group(1)).rstrip(".")
        tags = [clean_text(a.text()) for a in doc.css("span.tagged_as a")]
        cats = [clean_text(a.text()) for a in doc.css("span.posted_in a")]
        image = ""
        og = doc.css_first('meta[property="og:image"]')
        if og:
            image = og.attributes.get("content", "")

        enclosure = find_enclosure(description, " ".join(tags))
        category = classify(category_path.split(">")[-1] if category_path else "", " ".join(cats), name)

        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url, based_on=based_on,
            description=description, category=category,
            effect_type=clean_text(category_path.split(">")[-1]) if category_path else "",
            tags=tags, enclosure=enclosure, controls=controls, price=price, sku=sku,
            in_stock=in_stock, doc_url=pdfs[0], image_url=image,
        )
        tayda = re.search(r'https://drill\.taydakits\.com/[^"\' >]+', html)
        if tayda:
            c.extra_docs["Tayda drill template"] = tayda.group(0)
        for extra in pdfs[1:]:
            c.extra_docs[extra.rsplit("/", 1)[-1]] = extra

        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf:
            c.__dict__.update(process_document(pdf, self.vendor, slug))
        return c


def _unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s or "").replace("\xa0", " ")


def _product_ld(html: str) -> dict:
    for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph", [data]) if isinstance(data, dict) else data
        for node in graph:
            if isinstance(node, dict) and node.get("@type") == "Product":
                return node
    return {}
