"""Five Cats Pedals adapter. WooCommerce (Store API for the catalogue); each
product page's attribute table links the build insert (raster PDF), a vector
schematic PDF and a KiCad interactive BOM zip, which gives the exact parts list."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..ibom import parse_ibom
from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_enclosure, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.five-cats-pedals.co.uk"
PCB_CATEGORY = "diy-guitar-effects-pedal-pcbs"
_CAT = {"fuzz": "Fuzz", "overdrive": "Overdrive", "distortion": "Distortion", "boosts": "Boost",
        "amp-in-a-box": "Preamp / Amp-in-a-box", "amps": "Preamp / Amp-in-a-box", "pre-amp-pcb-boards": "Preamp / Amp-in-a-box",
        "modulation": "Vibrato / Chorus", "buffers": "Utility", "utility": "Utility", "misc": "Utility",
        "dynamics": "Compressor", "delay": "Delay", "filter": "EQ / Filter", "reverb": "Reverb", "wah": "Wah / Envelope"}


@register
class FiveCats(Adapter):
    vendor = "fivecats"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        # PCB products are usually assigned only to a child category (fuzz, overdrive, ...),
        # so accept anything under the PCB parent and reject the built-pedal / parts trees.
        raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products/categories?per_page=100", ".json")
        cats = json.loads(raw) if raw else []
        parent_id = next((c["id"] for c in cats if c["slug"] == PCB_CATEGORY), None)
        pcb_slugs = {c["slug"] for c in cats if c["id"] == parent_id or c["parent"] == parent_id}
        non_pcb = {c["slug"] for c in cats if c["parent"] == 0 and c["slug"] != PCB_CATEGORY}
        page = 1
        while True:
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            items = json.loads(raw) if raw else []
            if not items:
                break
            for pr in items:
                slugs = {c["slug"] for c in pr.get("categories", [])}
                if not (slugs & pcb_slugs) or (slugs & non_pcb) or "bundles" in slugs or re.search(r"-pack\b|bundle", pr["slug"]):
                    continue
                self.products[pr["slug"]] = pr
                yield pr["slug"]
            page += 1

    def parse(self, slug: str) -> Circuit | None:
        pr = self.products.get(slug)
        if not pr:
            return None
        url = pr.get("permalink") or f"{BASE}/product/{slug}/"
        html = self.f.get_text(url) or ""
        doc = HTMLParser(html)

        def attr(name: str) -> tuple[str, str]:
            cell = doc.css_first(f"tr.woocommerce-product-attributes-item--attribute_pa_{name} td")
            if not cell:
                return "", ""
            a = cell.css_first("a")
            return clean_text(cell.text()), (a.attributes.get("href", "") if a else "")

        compares, _ = attr("compares-to")
        _, insert_pdf = attr("build-docs")
        _, schematic_pdf = attr("schematic")
        _, ibom_zip = attr("interactive-b-o-m")
        _, guide_pdf = attr("general-build-guide")
        if not (insert_pdf or ibom_zip or schematic_pdf):
            return None

        full_name = _html.unescape(pr["name"])
        m = re.match(r"^(.+?)\s+[–-]\s+(.+?)\s+Clone\s*$", full_name)
        parts = re.split(r"\s+[–-]\s+", full_name, maxsplit=1)
        name = clean_text(m.group(1)) if m else clean_text(parts[0])
        based_on = compares or (clean_text(m.group(2)) if m else "")
        if not m and len(parts) > 1 and not re.search(r"\bQTY\b|pack|1590", parts[1], re.I):
            suffix = clean_text(parts[1])
            looks_like_product = re.search(r"\bClone\b|\bStyle\b|\bReplica\b|\b[A-Z]{3,}\b", suffix) is not None
            if not based_on and looks_like_product:
                based_on = re.sub(r"\s*\b(Clone|Style|Replica)\b.*$", "", suffix).strip(" -")
                name = clean_text(parts[0])
            else:
                name = f"{clean_text(parts[0])} ({suffix})" if not based_on else clean_text(parts[0])
        description = html_to_text(pr.get("description") or pr.get("short_description") or "")
        prices = pr.get("prices") or {}
        minor = int(prices.get("price") or 0)
        try:
            minor = int((pr.get("price_range") or {}).get("min_amount") or minor)
        except (TypeError, ValueError):
            pass
        currency = prices.get("currency_code", "GBP")
        cat_slugs = [c["slug"] for c in pr.get("categories", []) if c["slug"] != PCB_CATEGORY]
        category = next((_CAT[s] for s in cat_slugs if s in _CAT), "") or classify(based_on, name, description[:300])
        image = ""
        if pr.get("images"):
            image = pr["images"][0].get("src", "")

        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url, based_on=based_on,
            description=description, category=category,
            effect_type=", ".join(c["name"] for c in pr.get("categories", []) if c["slug"] != PCB_CATEGORY),
            price=minor / 100 if minor else None, currency=currency,
            in_stock=pr.get("is_in_stock"), doc_url=insert_pdf or schematic_pdf, image_url=image,
            enclosure=find_enclosure(description),
        )
        if schematic_pdf:
            c.extra_docs["Schematic PDF"] = schematic_pdf
        if ibom_zip:
            c.extra_docs["Interactive BOM"] = ibom_zip
        if guide_pdf:
            c.extra_docs["General build guide"] = guide_pdf

        if ibom_zip:
            z = self.f.get_file(ibom_zip, ".zip")
            if z:
                try:
                    c.bom = parse_ibom(z)
                except Exception:  # noqa: BLE001 - a bad zip shouldn't kill the run
                    c.bom = []
        if insert_pdf:
            pdf = self.f.get_file(insert_pdf, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                m = re.search(r"-V(\d+)-(\d+)", insert_pdf)
                c.doc_version = f"V{m.group(1)}.{m.group(2)}" if m else ""
                if not c.enclosure:
                    c.enclosure = ocr_enclosure(pdf, self.vendor, slug)  # newer inserts stamp "minimum enclosure" as a graphic
                # No OCR fallback: the inserts are low-resolution JPEG composites and the
                # results were unreliable; boards without an interactive BOM link to the doc.
        if schematic_pdf:
            spdf = self.f.get_file(schematic_pdf, ".pdf")
            if spdf and spdf.read_bytes()[:5] == b"%PDF-":
                png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                if not png.exists():
                    try:
                        render_page(spdf, 1, png)
                    except Exception:  # noqa: BLE001
                        png = None
                if png:
                    c.schematic_local = str(png.relative_to(DATA_DIR))
                    c.schematic_page = 1
        pots = [r for r in c.bom if r.category == "POT"]
        if pots:
            names = [re.sub(r"\d+$", "", r.ref) for r in pots]
            c.controls = [n.title() for n in names] if all(re.fullmatch(r"[A-Za-z][A-Za-z\-/]+", n) for n in names) else [f"{len(pots)} knobs"]
        return c
