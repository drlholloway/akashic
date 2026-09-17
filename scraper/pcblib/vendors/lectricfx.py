"""Lectric-FX adapter. WooCommerce (Store API); each product description links
its self-hosted build document, a clean Affinity Publisher PDF with a
multi-column B.O.M. (resistors, caps, semis, pots, trimmers, switches)."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..pdf import process_document, pdf_text_pages, ocr_bom, schematic_bom, render_page
from ..paths import CACHE_DIR, DATA_DIR
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://lectric-fx.com"
_SKIP = re.compile(r"thripidity|3pdt pcb|jay-fetz|matched .*set|^pcb only$|^pcb plus", re.I)
_ORIG = re.compile(r"(?:based on|compare to|comparable to|adaptation of|recreation of|clone of|version of|inspired by|homage to|take on)\s+(?:the |an? )?(?:vintage(?: model)? |bygone |classic |old |original |legendary )?([A-Z0-9][^.,;\n(]{2,60})", re.I)


def _clean_orig(s: str) -> str:
    s = clean_text(s.replace("™", "").replace("®", ""))
    s = re.sub(r"^(?:renowned|revered|early|late|famous|legendary|classic|original|vintage|old|bygone|a |an |the )+\s*", "", s, flags=re.I)
    s = re.sub(r"^\d0['’]s\s+(?:schematic of the |version of the |era )?", "", s, flags=re.I)
    s = re.split(r"\s+(?:from|with|without|using|which|that|had|and|but|so|as)\b|[?!]", s)[0]
    s = re.sub(r"\s+(?:circuit|pedal|unit)$", "", s, flags=re.I)
    return s.strip(" -")


@register
class LectricFX(Adapter):
    vendor = "lectricfx"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page, best = 1, {}
        while True:
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            items = json.loads(raw) if raw else []
            if not items:
                break
            for pr in items:
                name = _html.unescape(pr["name"])
                if _SKIP.search(name):
                    continue
                # "Bloodstone Phase Shifter V.1.1" and "V.1.2" are the same board: keep the newest.
                m = re.search(r"\s+V\.?\s?(\d+(?:\.\d+)*)\b", name)
                ver = tuple(int(x) for x in m.group(1).split(".")) if m else (0,)
                key = re.sub(r"[^a-z0-9]+", " ", re.sub(r"\s+V\.?\s?\d+(?:\.\d+)*\b", "", name).lower()).strip()
                if key not in best or ver > best[key][0]:
                    best[key] = (ver, pr)
            page += 1
        for _ver, pr in best.values():
            self.products[pr["slug"]] = pr
            yield pr["slug"]

    def parse(self, slug: str) -> Circuit | None:
        pr = self.products.get(slug)
        if not pr:
            return None
        raw_name = _html.unescape(pr["name"]).replace("\u201c", "").replace("\u201d", "")
        m = re.search(r"\s+V\.?\s?(\d+(?:\.\d+)*)\b", raw_name)
        version = f"V{m.group(1)}" if m else ""
        name = clean_text(re.sub(r"\s+V\.?\s?\d+(?:\.\d+)*\b", "", raw_name)).strip(" -")
        desc_html = pr.get("description") or ""
        pdfs = [re.sub(r"^http://", "https://", u) for u in re.findall(r'href="(https?://lectric-fx\.com/wp-content/uploads/[^"]+\.pdf)"', desc_html, re.I)]
        pdfs = [u for u in pdfs if not re.search(r"/mini\.pdf|thripidity", u, re.I)]
        if not pdfs:
            return None
        stem = re.sub(r"[^a-z0-9]", "", name.split()[0].lower()) if name else ""
        docs = sorted(pdfs, key=lambda u: (0 if stem and stem in re.sub(r"[^a-z0-9]", "", u.rsplit("/", 1)[-1].lower()) else 1, pdfs.index(u)))
        doc_url = docs[0]
        description = html_to_text(desc_html)
        description = re.split(r"\n\s*(?:Older version|Current Version)", description)[0].strip()
        m = _ORIG.search(description)
        based_on = _clean_orig(m.group(1)) if m else ""
        prices = pr.get("prices") or {}
        minor = int(prices.get("price") or 0)
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=pr.get("permalink") or f"{BASE}/product/{slug}/",
            based_on=based_on, description=description[:2500], category=classify(based_on, name, description[:300]),
            price=minor / 100 if minor else None, currency=prices.get("currency_code", "USD"),
            in_stock=pr.get("is_in_stock"), doc_url=doc_url, doc_version=version,
            image_url=(pr.get("images") or [{}])[0].get("src", ""), enclosure=find_enclosure(description),
        )
        for u in docs[1:]:
            c.extra_docs[f"Older document: {u.rsplit('/', 1)[-1]}"] = u
        for u in re.findall(r'href="(https?://(?:docs|drive)\.google\.com/[^"]+)"', desc_html):
            c.extra_docs.setdefault("Google Drive document", u)
        pdf = self.f.get_file(doc_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.__dict__.update(process_document(pdf, self.vendor, slug))
            pages = pdf_text_pages(pdf)
            if len(c.bom) < 4:
                # Older docs are full-page scans; some newer ones have an image BOM but a
                # vector schematic. OCR the pages and read any vector schematic labels.
                have: set[str] = set()
                rows = []
                sch_pages = [i for i, pg in enumerate(pages, 1) if len(re.findall(r"\b[RC]\d+\b", pg)) >= 5]
                for pn in sch_pages:
                    for r in schematic_bom(pdf, pn):
                        if r.ref not in have:
                            have.add(r.ref)
                            rows.append(r)
                for r in ocr_bom(pdf, self.vendor, slug, max_pages=6, thorough=True):
                    if r.ref not in have:
                        have.add(r.ref)
                        rows.append(r)
                c.bom = rows
                if sch_pages and not c.schematic_local:
                    png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                    if not png.exists():
                        render_page(pdf, sch_pages[0], png)
                    c.schematic_local = str(png.relative_to(DATA_DIR))
                    c.schematic_page = sch_pages[0]
            head = "\n".join(pages[:2])
            if not c.based_on:
                m = _ORIG.search(head)
                if m:
                    c.based_on = _clean_orig(m.group(1))
            if not c.enclosure:
                c.enclosure = find_enclosure(head)
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+", r.ref) for r in pots)
                c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
