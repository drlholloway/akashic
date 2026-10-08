"""Dead Astronaut FX adapter. A Wix site: every page is server-rendered, the
nav menu names the ~19 PCB pages, each page states a GBP price and links raster
"BUILD DOCS" PDFs on filesusr.com whose BOM page is a screenshot (OCR'd)."""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.lexbor import LexborHTMLParser

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import ocr_bom, parse_eagle_partlist, pdf_text_pages
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

BASE = "https://deadastronaut.wixsite.com/effects"
_SKIP = re.compile(r"^(home|deadastronautfxmusic|pedals-for-sale|copy-of-pedals-for-sale-now|3xpcbbundle|crybabywah-light-plates|rc600screenprotector|copy-of-mega-16-midi-drums)$")


@register
class DeadAstronaut(Adapter):
    vendor = "deadastronaut"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.labels: dict[str, str] = {}

    def list_targets(self) -> Iterable[str]:
        home = self.f.get_text(BASE) or ""
        doc = LexborHTMLParser(home)
        for a in doc.css("a[href]"):
            href = a.attributes.get("href") or ""
            m = re.match(re.escape(BASE) + r"/([a-z0-9-]+)/?$", href)
            if not m:
                continue
            slug = m.group(1)
            label = clean_text(a.text())
            if _SKIP.match(slug) or not label or len(label) < 3:
                continue
            self.labels.setdefault(slug, label)
        for slug in self.labels:
            yield slug

    def parse(self, slug: str) -> Circuit | None:
        url = f"{BASE}/{slug}"
        html = self.f.get_text(url) or ""
        if not html:
            return None
        doc = LexborHTMLParser(html)
        pdfs = re.findall(r'href="(https://[a-f0-9-]+\.filesusr\.com/ugd/[^"]+\.pdf)"[^>]*(?:title|aria-label)="([^"]+)"', html)
        build = [(u, t) for u, t in pdfs if re.search(r"build|doc", t, re.I)]
        if not build and not pdfs:
            return None
        doc_url, doc_title = build[0] if build else pdfs[0]
        main = doc.css_first("main") or doc.body
        blocks = [clean_text(n.text()) for n in main.css(".wixui-rich-text__text")] if main else []
        blocks = [b for b in blocks if b and b not in ("DEADASTRONAUTFX", "GUITAR AND MUSIC EFFECTS")]
        text = "\n".join(dict.fromkeys(blocks))
        title_n = doc.css_first("title")
        name = self.labels.get(slug) or clean_text(re.sub(r"\s*\(?deadastronautfx\)?\s*$", "", title_n.text() if title_n else slug, flags=re.I))
        name = re.sub(r"\s+PCB$", "", name, flags=re.I).title().replace("Fv-24", "FV-24").replace("Midi", "MIDI")
        m = re.search(r"(\d+(?:\.\d\d)?)\s?GBP", text)
        price = float(m.group(1)) if m else None
        m = re.search(r"based on (?:the |a |an )?(?:classic |original )?([^,.\n]{3,60})", text, re.I)
        based_on = clean_text(m.group(1)) if m else ""
        desc = re.sub(r"ALL purchases include.*$", "", text, flags=re.S | re.I)
        desc = re.sub(r"^.*?\d+(?:\.\d\d)?\s?GBP\.?\s*", "", desc, flags=re.S) if price else desc
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url, based_on=based_on, description=desc.strip()[:2000],
            category=classify(name, based_on, desc[:300]), price=price, currency="GBP", in_stock=True if price else None,
            doc_url=doc_url, enclosure=find_enclosure(text),
        )
        for u, t in pdfs:
            if u != doc_url:
                c.extra_docs[clean_text(t).replace(".pdf", "").title()] = u
        img = doc.css_first('meta[property="og:image"]')
        if img:
            c.image_url = (img.attributes.get("content") or "").split("/v1/")[0]
        pdf = self.f.get_file(doc_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            # Several docs print the Eagle parts list as text, which is exact; the rest are scans, OCR'd.
            text = parse_eagle_partlist(pdf_text_pages(pdf))
            ocr = ocr_bom(pdf, self.vendor, slug, max_pages=8, thorough=True)
            if len(text) >= 8:
                # OCR fills what the text list leaves out (a page of it that is a scan) but never runs past
                # it: D7 beside a list that ends at D4 is a misread label ('t.C2').
                def key(ref: str) -> tuple[str, int] | None:
                    """'Q04' and 'IC4D' (a gate of IC4) are the parts Q4 and IC4."""
                    mm = re.fullmatch(r"([A-Z]+)(\d+)[A-Z]?", ref.upper())
                    return (mm.group(1), int(mm.group(2))) if mm else None
                have, top = {key(r.ref) for r in text} - {None}, {}
                for k in have:
                    top[k[0]] = max(top.get(k[0], 0), k[1])
                fill = [r for r in ocr if (k := key(r.ref)) and k not in have and (k[0] not in top or k[1] <= top[k[0]])
                        and k[0] in ("R", "C", "D", "Q", "IC", "U", "L") and r.category != "OTHER"]
                c.bom = text + fill
            else:
                c.bom = ocr
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
                c.controls = [r.ref if r.ref != r.ref.upper() else r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
