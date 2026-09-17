"""Parasit Studio adapter. The shop is an Ecwid widget (JS only), but every
circuit has a server-rendered page under /pedals/<slug>/ that links the PCB
product, the build document PDF and any stripboard layout."""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..pdf import process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://parasitstudio.com"
_NOT_A_PEDAL = re.compile(r"\b(chip|microcontroller|amplifier chip|CMOS|series|IC|was |PLL|Phase Locked Loop|ATtiny\d*|[A-Z]{2,4}\d{3,}[A-Z]*)\b", re.I)


def _clean_based_on(s: str) -> str:
    s = re.split(r"\s+(?:which|that|and|with|but|so)\b", clean_text(s))[0].strip(" -")
    return "" if _NOT_A_PEDAL.search(s) else s


@register
class Parasit(Adapter):
    vendor = "parasit"

    def list_targets(self) -> Iterable[str]:
        xml = self.f.get_text(f"{BASE}/wp-sitemap-posts-page-1.xml", ".xml") or ""
        for url in re.findall(r"<loc>(https://parasitstudio\.com/pedals/[^<]+)</loc>", xml):
            if re.search(r"discontinued|old-|archive", url, re.I):
                continue
            yield url

    def parse(self, url: str) -> Circuit | None:
        html = self.f.get_text(url) or ""
        if not html:
            return None
        doc = HTMLParser(html)
        main = doc.css_first("main") or doc.body
        if main is None:
            return None
        links = {clean_text(a.text()).lower(): a.attributes.get("href", "") for a in main.css("a[href]")}
        doc_url = next((h for t, h in links.items() if h.lower().endswith("-doc.pdf") or "build doc" in t), "")
        if not doc_url:
            doc_url = next((h for t, h in links.items() if h.lower().endswith(".pdf") and "stripboard" not in t and "vero" not in h.lower()), "")
        if not doc_url:
            return None
        if doc_url.startswith("/"):
            doc_url = BASE + doc_url
        pcb_url = next((h for t, h in links.items() if "/shop/" in h and ("pcb" in t or "pcb" in h.lower())), "")
        if pcb_url.startswith("/"):
            pcb_url = BASE + pcb_url
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        heading = main.css_first("h1, h2")
        name = clean_text(heading.text()).title() if heading else slug.title()
        if re.search(r"Discontinued|Projects", name):
            return None
        name = re.sub(r"\bPcb\b", "PCB", name)
        text = html_to_text(main.html)
        text = re.sub(r"^\s*" + re.escape(clean_text(heading.text()) if heading else "") + r"\s*", "", text)
        m = re.search(r"(?:based on|clone of|inspired by|version of|take on)\s+(?:the |an? )?([A-Z][^.\n,;(]{3,60})", text)
        based_on = _clean_based_on(m.group(1)) if m else ""
        if re.search(r"original (?:design|circuit)|my own design", text, re.I) and not m:
            based_on = ""
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=pcb_url or url, based_on=based_on,
            description=text[:2000], category=classify(based_on, name, text[:400]),
            doc_url=doc_url, price=None, currency="EUR",
        )
        for t, h in links.items():
            if h.lower().endswith(".pdf") and h != doc_url and h.split("/")[-1] != doc_url.split("/")[-1]:
                c.extra_docs[t.title() if t else h.rsplit("/", 1)[-1]] = h if h.startswith("http") else BASE + h
        if pcb_url and pcb_url != c.url:
            c.extra_docs["PCB in the shop"] = pcb_url
        img = main.css_first("img[src]")
        if img:
            src = img.attributes.get("src", "")
            c.image_url = src if src.startswith("http") else BASE + src
        pdf = self.f.get_file(doc_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            info = process_document(pdf, self.vendor, slug)
            c.__dict__.update(info)
            from ..pdf import pdf_text_pages
            pages = pdf_text_pages(pdf)
            head = "\n".join(pages[:2])
            m = re.search(r"Drilling template.*?\((1590[A-Z]{0,2}\d?|125B)\)", "\n".join(pages), re.I)
            c.enclosure = m.group(1).upper() if m else find_enclosure(head, text)
            m = re.search(r"last updated\s+([A-Za-z]+ \d{4}).*?PCB version ([\d.]+)", head, re.I | re.S)
            if m:
                c.doc_version = f"v{m.group(2)} ({m.group(1)})"
            if not c.based_on:
                m = re.search(r"(?:based on|clone of|inspired by|version of)\s+(?:the |an? )?([A-Z][^.\n,;(]{3,60})", head)
                if m:
                    c.based_on = _clean_based_on(m.group(1))
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+", r.ref) for r in pots)
                c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
