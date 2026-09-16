"""Madbean Pedals adapter: a single static projects table."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import pdf_text_pages, find_schematic_page, render_page, parse_bom_columns
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

PROJECTS = "https://www.madbeanpedals.com/projects/"
_DIFF = {"n00b": "Beginner", "cowboy": "Intermediate", "genius": "Advanced", "super": "Expert"}


@register
class Madbean(Adapter):
    vendor = "madbean"

    def list_targets(self) -> Iterable[str]:
        html = self.f.get_text(PROJECTS) or ""
        doc = HTMLParser(html)
        section = ""
        for tr in doc.css("tr"):
            hdr = tr.css_first('td[colspan="9"]')
            if hdr:
                section = clean_text(hdr.text())
                continue
            a = tr.css_first('a[href*="/pdf/"]')
            if a:
                yield f"{section}\t{a.attributes['href']}\t{tr.html}"

    def parse(self, target: str) -> Circuit | None:
        section, href, row_html = target.split("\t", 2)
        tr = HTMLParser(f"<table>{row_html}</table>")
        tds = tr.css("td")
        name = based_on = ""
        for i, td in enumerate(tds):
            txt = clean_text(td.text())
            if "style3" in (td.attributes.get("class") or "") and txt and not td.css_first("img"):
                name = txt
                if i + 1 < len(tds):
                    based_on = clean_text(tds[i + 1].text())
                break
        if not name:
            return None
        enc_n = tr.css_first("td.style2, td span.style2")
        enclosure = find_enclosure(clean_text(enc_n.text()) if enc_n else "")
        price = None
        pr = tr.css_first("td.style11")
        if pr:
            m = re.search(r"\$(\d+(?:\.\d+)?)", pr.text())
            if m:
                price = float(m.group(1))
        in_stock = None if price is None else ("sold out" not in tr.text().lower())
        archived = tr.css_first('td[bgcolor="#074E91"]')
        archived_on = clean_text(archived.text()) if archived else ""
        diff_img = tr.css_first('img[src*="fxlevel_"]')
        difficulty = ""
        if diff_img:
            m = re.search(r"fxlevel_(\w+)\.png", diff_img.attributes.get("src", ""))
            if m:
                difficulty = _DIFF.get(m.group(1), m.group(1))
        doc_url = urljoin(PROJECTS, href)
        m = re.search(r"_folders/([^/]+)/pdf/([^/]+)\.pdf", href)
        folder = m.group(1) if m else ""
        slug = re.sub(r"[^a-z0-9]+", "-", (m.group(2) if m else name).lower()).strip("-")

        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=PROJECTS + f"#{slug}",
            based_on=based_on, category=classify(section, folder, based_on, name),
            effect_type=section, tags=[folder] if folder else [], enclosure=enclosure,
            price=price, in_stock=in_stock, difficulty=difficulty, doc_url=doc_url,
        )
        if archived_on:
            c.tags.append(f"archived {archived_on}")
        sch = tr.css_first('a[href*="/schematics/"]')
        if sch:
            c.extra_docs["Schematic image"] = urljoin(PROJECTS, sch.attributes["href"])
        zp = tr.css_first('a[href*="/docs/"]')
        if zp:
            c.extra_docs["Layout / drill files"] = urljoin(PROJECTS, zp.attributes["href"])

        pdf = self.f.get_file(doc_url, ".pdf")
        if pdf:
            pages = pdf_text_pages(pdf)
            c.bom = parse_bom_columns(pages, max_col=66)
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            page_no = find_schematic_page(pages)
            if page_no is None:
                page_no = len(pages) - 1 if pages and not pages[-1].strip() else len(pages)
            png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
            if page_no and not png.exists():
                try:
                    render_page(pdf, page_no, png)
                except Exception:
                    page_no = None
            if page_no:
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = page_no
            m = re.search(r"Terms of Use.*?(\d{4})", "\n".join(pages[:1]), re.S)
            c.doc_version = m.group(1) if m else ""
        return c


