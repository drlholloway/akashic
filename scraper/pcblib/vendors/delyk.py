"""delyk PCBs adapter. delyk stopped selling online in October 2026 and turned the shop into a static
catalog (an Astro site): /shop/ lists every board, and each product page carries its category,
description, a Difficulty / Based on / Smallest enclosure list, tags and a Downloads section with
the build document ('<Name>-BOM.pdf', a P/N / Value / Notes table per section) and drill template.
There are no prices; a board with an 'Out of stock' badge is one the maker has no copies of left."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from selectolax.lexbor import LexborHTMLParser

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.delykpcb.com"
_SKIP = re.compile(r"3PDT|Relay Bypass|ISP Helper|SMD to THD|Custom Payment|TAPLFO|Rotary Switch|MPQ3904|\bKit\b", re.I)


@register
class Delyk(Adapter):
    vendor = "delyk"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.pages: dict[str, str] = {}

    def list_targets(self) -> Iterable[str]:
        shop = self.f.get_text(f"{BASE}/shop/") or ""
        for href in dict.fromkeys(re.findall(r'href="(/product/[^"#?]+)"', shop)):
            slug = href.rstrip("/").rsplit("/", 1)[-1]
            html = self.f.get_text(BASE + href) or ""
            doc = LexborHTMLParser(html)
            title = doc.css_first("h1")
            cats = {a.attributes.get("href", "").rstrip("/").rsplit("/", 1)[-1] for a in doc.css("p.cats a")}
            if not title or cats <= {"parts", "clearance", "swag"} or _SKIP.search(title.text()):
                continue
            self.pages[slug] = html
            yield slug

    def parse(self, slug: str) -> Circuit | None:
        html = self.pages.get(slug)
        if not html:
            return None
        page = LexborHTMLParser(html)
        title = clean_text(_html.unescape(page.css_first("h1").text()))
        name = re.sub(r"\s+PCB\s*$", "", title).strip("“” ")
        specs = {dt.text().strip().lower(): clean_text(dd.text()) for dt, dd in
                 zip(page.css("dl.specs dt"), page.css("dl.specs dd"))}
        based_on = specs.get("based on", "")
        based_on = "" if re.search(r"original|n/a|none", based_on, re.I) else re.sub(r"TubeScreamer", "Tube Screamer", based_on)
        lead = " ".join(html_to_text(n.html) for n in page.css("article .prose"))
        downloads = [(a.text().strip(), BASE + a.attributes["href"]) for a in page.css("section.docs a[href]")
                     if a.attributes.get("href", "").startswith("/")]
        doc = next((u for t, u in downloads if re.search(r"\bBOM\b|build", t, re.I)), "")
        img = page.css_first("#main-photo")
        url = f"{BASE}/product/{slug}/"
        c = Circuit(vendor=self.vendor, slug=slug.replace("-pcb", ""), name=name, url=url, based_on=based_on,
                    description=clean_text(lead)[:700], price=None, currency="USD",
                    in_stock=page.css_first("span.oos") is None, doc_url=doc or url,
                    image_url=BASE + img.attributes["src"] if img and img.attributes.get("src") else "",
                    difficulty=specs.get("difficulty", ""),
                    enclosure=find_enclosure(specs.get("smallest enclosure", "")) or find_enclosure(
                        page.css_first("p.tags").text() if page.css_first("p.tags") else ""))  # 'Tags: 1590B, distortion'

        for t, u in downloads:
            if re.search(r"drill", t, re.I):
                c.extra_docs["Drill template"] = u
        cats = {a.attributes.get("href", "").rstrip("/").rsplit("/", 1)[-1] for a in page.css("p.cats a")}
        if doc:
            pdf = self.f.get_file(doc, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                res = process_document(pdf, self.vendor, c.slug)
                c.bom, c.schematic_local, c.schematic_page, c.doc_version = res["bom"], res["schematic_local"], res["schematic_page"], res["doc_version"]
                trims = {m.group(1).upper() for m in re.finditer(r"(?m)^\s*([A-Z][A-Z0-9]{1,11})\s+\S+\s+Trim ?pot", "\n".join(pages))}
                c.bom = [r for r in c.bom if r.ref.upper() not in ("OMIT", "NONE", "N/A")]
                for r in c.bom:
                    if r.category == "POT" and (r.ref.upper() in trims or re.search(r"trim", r.notes, re.I)):
                        r.category = "TRIM"
                intro = re.search(r"Introduction\s*\n(.{20,400}?)\n\s*\n", "\n".join(pages[:2]), re.S)
                if intro and len(c.description) < 40:
                    c.description = clean_text(intro.group(1))
        c.category = "Utility" if "utility-boards" in cats else classify(name, based_on, c.description[:300])
        pots = [r for r in c.bom if r.category == "POT" and r.ref.upper() != "TRIM"]
        named = list(dict.fromkeys(r.ref.title() if r.ref.isupper() else r.ref for r in pots if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref)))
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /-]{2,15}", r.ref)]
        return c
