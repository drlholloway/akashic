"""Aion FX adapter. Custom WordPress theme; docs under /app/files/docs/."""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..pdf import process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SITEMAP = "https://aionfx.com/sitemap.xml"


@register
class AionFX(Adapter):
    vendor = "aionfx"

    def list_targets(self) -> Iterable[str]:
        xml = self.f.get_text(SITEMAP, ".xml") or ""
        yield from re.findall(r"<loc>(https://aionfx\.com/project/[^<]+)</loc>", xml)

    def parse(self, url: str) -> Circuit | None:
        html = self.f.get_text(url)
        if not html:
            return None
        doc = HTMLParser(html)
        pdfs = sorted(set(re.findall(r'https://aionfx\.com/app/files/docs/[^"\' >]+\.pdf', html)),
                      key=lambda u: (0 if u.lower().endswith("_documentation.pdf") else 1, u))
        if not pdfs or not pdfs[0].lower().endswith("_documentation.pdf"):
            return None  # accessories and articles link other PDFs, not a build doc

        h1 = doc.css_first("h1")
        sub = doc.css_first(".project__subtitle")
        subtitle = clean_text(sub.text()) if sub else ""
        name = clean_text(h1.text().replace(subtitle, "")) if h1 else ""
        slug = url.rstrip("/").rsplit("/", 1)[-1]

        def spec(cls: str) -> str:
            n = doc.css_first(f".{cls} .project__specs__content")
            return clean_text(n.text()) if n else ""

        based_on = spec("project__based-on")
        effect_type = spec("project__effect-type")
        diff = doc.css_first(".project__difficulty__text")
        difficulty = clean_text(diff.text()) if diff else ""

        summary_n = doc.css_first(".project__summary")
        summary = clean_text(summary_n.text()) if summary_n else ""
        summary = re.sub(r"^Project Summary\s*", "", summary)
        ov = doc.css_first(".project__overview")
        overview = html_to_text(ov.html) if ov else ""
        overview = re.sub(r"^Project overview\s*", "", overview)
        description = (summary + "\n\n" + overview).strip()

        price = None
        in_stock = None
        pcb = doc.css_first(".project__product--pcb")
        if pcb:
            m = re.findall(r"\$\s*([\d.]+)", clean_text(pcb.text()))
            if m:
                price = float(m[0])
            st = pcb.css_first(".project__stock")
            if st:
                in_stock = "in-stock" in (st.attributes.get("class") or "")

        image = ""
        og = doc.css_first('meta[property="og:image"]')
        if og:
            image = og.attributes.get("content", "")

        controls: list[str] = []

        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, subtitle=subtitle, url=url,
            based_on=based_on, description=description,
            category=classify(effect_type, subtitle, name), effect_type=effect_type,
            difficulty=difficulty, price=price, in_stock=in_stock, doc_url=pdfs[0],
            image_url=image, enclosure=find_enclosure(overview), controls=controls,
        )
        for a in doc.css(".project__docs__item__link, .project__docs a"):
            href = a.attributes.get("href", "")
            label = clean_text(a.text())
            if href and href != c.doc_url and label:
                c.extra_docs[label] = href

        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf:
            info = process_document(pdf, self.vendor, slug)
            c.__dict__.update(info)
            from ..pdf import pdf_text_pages
            pages = pdf_text_pages(pdf)
            c.controls = _controls_from_doc(pages)
            if not c.controls:  # legacy docs have no USAGE section but name the pots in the parts table
                c.controls = [r.ref.title() for r in c.bom if r.category == "POT" and r.ref.isalpha() and r.ref not in ("RPD", "LEDR", "CLR")]
            if not c.enclosure:
                c.enclosure = find_enclosure(*pages)
        return c


def _controls_from_doc(pages: list[str]) -> list[str]:
    """USAGE section bullets: '• Drive 1 sets the gain', '• Clipping (toggle) selects…'."""
    text = "\n".join(pages[:4])
    m = re.search(r"\nUSAGE\s*\n(.*?)(?:\n[A-Z][A-Z &]{5,}\s*\n|\Z)", text, re.S)
    if not m:
        return []
    out: list[str] = []
    for line in m.group(1).splitlines():
        b = re.match(r"\s*•\s*([A-Z][\w'’/\-]*(?: [A-Z0-9][\w'’/\-]*){0,3})(?:\s*\(([^)]*)\))?\s+[a-z]", line)
        if b:
            name = clean_text(b.group(1))
            if b.group(2) and re.search(r"toggle|switch|stomp", b.group(2), re.I):
                continue  # switches are not knobs
            out.append(name)
    return out
