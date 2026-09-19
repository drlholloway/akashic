"""On The Road Effects (OTRFX) adapter. One WordPress page lists every PCB with
its name (linked to Etsy), a one-line original, a price, a build-guide PDF and
Reverb/Etsy buttons, grouped under section headings. The guides are Illustrator
PDFs with a multi-column text parts list."""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..pdf import process_document, pdf_text_pages
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

PAGE = "https://ontheroadeffects.com/pcbs/"
_SECTION_CAT = {"compress": "Compressor", "boost": "Boost", "fuzz": "Fuzz", "overdrive": "Overdrive",
                "distortion": "Distortion", "delay": "Delay", "echo": "Delay", "modulation": "Vibrato / Chorus",
                "utility": "Utility", "bypass": "Utility", "tremolo": "Tremolo", "phaser": "Phaser"}


@register
class OTRFX(Adapter):
    vendor = "otrfx"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.entries: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        html = self.f.get_text(PAGE) or ""
        doc = HTMLParser(html)
        root = doc.css_first("main") or doc.body
        section, cur = "", None
        # Walk the page in document order: a linked h3 starts a board, a "$" h3 is its price,
        # any other heading is a section, and links until the next board belong to it.
        for node in root.traverse(include_text=False):
            tag = node.tag
            if tag in ("h2", "h3"):
                link = node.css_first("a")
                text = clean_text(node.text())
                if link and link.attributes.get("href", "").startswith("http") and not text.startswith("$"):
                    cur = {"name": text, "section": section, "price": None, "based_on": "", "pdf": "", "etsy": link.attributes.get("href", ""), "reverb": "", "image": ""}
                    self.entries[text] = cur
                elif text.startswith("$") and cur:
                    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
                    cur["price"] = float(m.group(1)) if m else None
                elif text and not text.startswith("$") and len(text) < 40 and not node.css_first("a"):
                    section = text
            elif tag == "p" and cur and not cur["based_on"]:
                t = clean_text(node.text())
                if t and len(t) < 90 and "build guide" not in t.lower():
                    cur["based_on"] = t
            elif tag == "a" and (node.attributes.get("href") or "").startswith("#") and node.attributes.get("id") is None:
                # The section anchors ("#fuzz", "#boost") double as the section labels.
                label = clean_text(node.text())
                if label and len(label) < 40:
                    section = label
            elif tag == "a" and cur:
                href = node.attributes.get("href", "") or ""
                if href.lower().endswith(".pdf") and not cur["pdf"]:
                    cur["pdf"] = href.replace("https://www.", "https://")
                elif "reverb.com" in href and not cur["reverb"]:
                    cur["reverb"] = href
                elif "etsy.com" in href and not cur["etsy"]:
                    cur["etsy"] = href
            elif tag == "img" and cur and not cur["image"]:
                src = node.attributes.get("data-tf-src") or node.attributes.get("src") or ""
                if src.startswith("http"):
                    cur["image"] = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", src)
        for name, e in self.entries.items():
            if e["pdf"]:
                yield name

    def parse(self, name: str) -> Circuit | None:
        e = self.entries.get(name)
        if not e or not e["pdf"]:
            return None
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        based_on = re.sub(r"^(?:modded|new!?)\s+", "", e["based_on"], flags=re.I)
        based_on = re.sub(r"\s*(?:pcb|pedal|version|circuit)\s*$", "", based_on, flags=re.I).strip(" -")
        combined = bool(re.search(r"&|\+|\band\b", e["section"]))
        section_cat = "" if combined else next((c for k, c in _SECTION_CAT.items() if k in e["section"].lower()), "")
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=e["etsy"] or e["reverb"] or PAGE, based_on=based_on,
            description=e["based_on"], category=classify(based_on, name, e["section"]) if not section_cat or section_cat in ("Fuzz", "Overdrive") else section_cat,
            effect_type=e["section"], price=e["price"], currency="USD", in_stock=bool(e["etsy"] or e["reverb"]),
            doc_url=e["pdf"], image_url=e["image"],
        )
        if e["reverb"]:
            c.extra_docs["Buy on Reverb"] = e["reverb"]
        if e["etsy"] and c.url != e["etsy"]:
            c.extra_docs["Buy on Etsy"] = e["etsy"]
        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.__dict__.update(process_document(pdf, self.vendor, slug))
            pages = pdf_text_pages(pdf)
            text = "\n".join(pages[:3])
            m = re.search(r"\((v[\d.]+)\)\s*Build Guide", text)
            if m:
                c.doc_version = m.group(1)
            c.enclosure = find_enclosure(text)
            c.bom = [r for r in c.bom if r.category != "CONN"]
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
                c.controls = [re.sub(r"\s+Pot$", "", r.ref.title()) for r in pots] if named else [f"{len(pots)} knobs"]
        return c
