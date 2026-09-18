"""GuitarPCB adapter. WooCommerce; BOM and schematic exist only as raster images
inside the build document, so BOM rows are OCR'd (best effort) when tesseract is
available, otherwise left empty."""
from __future__ import annotations

import json
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import render_page, pdf_text_pages, ocr_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SITEMAP = "https://guitarpcb.com/wp-sitemap-posts-product-1.xml"
_SKIP_CATS = {"component-parts", "nostalgitone-components", "control-panels", "enclosures"}


@register
class GuitarPCB(Adapter):
    vendor = "guitarpcb"

    def list_targets(self) -> Iterable[str]:
        xml = self.f.get_text(SITEMAP, ".xml") or ""
        yield from re.findall(r"<loc>(https://guitarpcb\.com/product/[^<]+)</loc>", xml)

    def parse(self, url: str) -> Circuit | None:
        html = self.f.get_text(url)
        if not html:
            return None
        doc = HTMLParser(html)
        desc_n = doc.css_first("#tab-description")
        desc_html = desc_n.html if desc_n else ""
        pdfs = [a.attributes["href"] for a in HTMLParser(desc_html).css('a[href$=".pdf"]')
                if "Tonmann" not in a.attributes.get("href", "")]
        # Faceplate art and drill PDFs sit beside the build doc; put them last so the doc is parsed.
        pdfs = sorted(pdfs, key=lambda p: bool(re.search(r"final-?art|artwork|faceplate|drill|template", p, re.I)))
        if not pdfs:
            return None
        ld = _product_ld(html)
        title_n = doc.css_first("h2.product_title, h1.product_title")
        full_title = clean_text(title_n.text()) if title_n else clean_text(ld.get("name", ""))
        full_title, sale_tags = _strip_prefixes(full_title)
        if re.search(r"painted enclosure|gift card|t-shirt|sticker|^(?:NPN|PNP) Transistor|^Diode \S+|^SMD \S+ PCB|^SOT23|Adapter for|\(\d+\) Pack", full_title, re.I):
            return None  # merch and component packs
        name, based_on = _split_title(full_title)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        short = doc.css_first(".woocommerce-product-details__short-description")
        description = html_to_text((short.html if short else "") + desc_html)
        description = re.sub(r"^Description\s*", "", description)
        if not based_on:
            m = re.search(r"[Bb]ased on (?:the )?([A-Z][^.\n]{3,60}?)(?: circuit| pedal|\.|\n)", description)
            if m:
                based_on = clean_text(m.group(1))
        price = None
        offers = ld.get("offers") or []
        if offers:
            try:
                price = float(offers[0].get("price"))
            except (TypeError, ValueError):
                pass
        in_stock = None
        if offers:
            in_stock = "InStock" in (offers[0].get("availability") or "")
        body_cls = (doc.css_first("body").attributes.get("class") or "") if doc.css_first("body") else ""
        cats = [a.attributes.get("href", "").rstrip("/").rsplit("/", 1)[-1]
                for a in doc.css('a[href*="/product-category/"]')]
        cats = [c for c in cats if c]
        image = ""
        og = doc.css_first('meta[property="og:image"]')
        if og:
            image = og.attributes.get("content", "")

        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url, based_on=based_on,
            description=description, category=classify(" ".join(cats), full_title, description[:300]),
            tags=sorted(set(cats))[:6] + sale_tags, price=price, in_stock=in_stock, doc_url=pdfs[0],
            image_url=image, enclosure=find_enclosure(description),
        )
        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf and pdf.stat().st_size > 2000 and pdf.read_bytes()[:5] == b"%PDF-":
            pages = pdf_text_pages(pdf)
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            page_no = _schematic_page(pdf, pages)
            if page_no:
                png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                if not png.exists():
                    render_page(pdf, page_no, png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = page_no
            c.bom = ocr_bom(pdf, self.vendor, slug)
            if len(c.bom) < 12:
                thorough = ocr_bom(pdf, self.vendor, slug, thorough=True)  # upscaled, thresholded passes for small type
                if len(thorough) > len(c.bom):
                    c.bom = thorough
            if not c.controls:
                c.controls = [r.ref.title() for r in c.bom if r.category == "POT" and r.ref.isalpha()]
        return c


def _strip_prefixes(t: str) -> tuple[str, list[str]]:
    """'(*Brand New) NostalgiTone STADIUM ROCK: …' -> ('NostalgiTone Stadium Rock: …', ['new'])."""
    tags: list[str] = []
    while True:
        m = re.match(r"^\s*[\(\[]\s*\*?\s*([^\)\]]{1,30})[\)\]]\s*", t)
        if not m:
            break
        tag = m.group(1).strip().lower()
        if "new" in tag:
            tags.append("new")
        elif "clearance" in tag or "flash" in tag or "sale" in tag:
            tags.append("sale")
        elif "only" in tag:
            tags.append("limited stock")
        t = t[m.end():]
    t = re.sub(r"\b([A-Z]{4,}(?: [A-Z]{2,})*)\b", lambda m: m.group(1).title(), t)  # SHOUTING -> Title
    return t.strip(), sorted(set(tags))


def _split_title(t: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)\s*[-–]\s*(?:Based on|based on)\s+(?:the )?(.+)$", t)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2))
    m = re.match(r"^(.*?)\s*[-–]\s*(.+?)\s+style\b.*$", t, re.I)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2))
    m = re.match(r"^(.*?)\s*[-–]\s*(.+)$", t)
    if m:
        return clean_text(m.group(1)), ""
    return t, ""


def _schematic_page(pdf, pages) -> int | None:
    for i, p in enumerate(pages, start=1):
        if re.search(r"\bschematic\b", p, re.I) and i <= 3:
            return i
    return 2 if len(pages) >= 2 else None


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
