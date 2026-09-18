"""Madbean Pedals adapter: a single static projects table."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import pdf_text_pages, find_schematic_page, render_page, parse_bom_columns, parse_shopping_list
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
            c.bom = parse_bom_columns(pages)  # the pots and semiconductors sit in the right-hand columns
            if len(c.bom) < 8:  # the VFE docs give a shopping list (value, qty, type) instead of a designator table
                shop = parse_shopping_list(pages)
                if len(shop) > len(c.bom):
                    c.bom = shop
            c.controls = _controls_from_doc(pages, [r.ref for r in c.bom if r.category == "POT"])
            if not c.controls:  # a shopping list names no pots, but it counts them
                n = sum(int(r.ref[1:]) for r in c.bom if r.category == "POT" and r.ref.startswith("×"))
                if n:
                    c.controls = [f"{n} knobs" if n > 1 else "1 knob"]
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


_CTRL_BULLET = re.compile(r"^\s*•\s*([A-Za-z][A-Za-z0-9 /\-]{0,24}?)\s*(\([^)]*\))?\s*:\s*(.*)$")
# Older docs drop the bullet: "LVL, TONE, DRIVE: Self-explanatory." at the left margin, names in caps.
_CTRL_PLAIN = re.compile(r"^\s{0,4}([A-Z][A-Z0-9/\-]{1,12}(?:,\s*[A-Z][A-Z0-9/\-]{1,12})*)\s*(\([^)]*\))?:\s*(.*)$")
# VFE docs: "Level (100kA): Sets the output volume" - a Title-case name with the pot value in parentheses.
_CTRL_TITLE = re.compile(r"^\s{0,4}([A-Z][a-z0-9/\-]{1,12}(?: [A-Z][a-z0-9/\-]{1,12})?)\s*(\([^)]*\d[kKM][ABCW]?\)):\s*([A-Z].*)$")
# A control is not a knob when its description opens by calling it a trimmer, switch, jack or LED
# ("This trimmer sets...", "Toggle between...", "3PDT foot-switches for..."); a knob whose text merely
# mentions a switch later ("rate is fixed via the C.V switch") is still a knob.
_NOT_A_KNOB = re.compile(r"^\s*(?:this is |it is |it's )?(?:the |an? |these |two )?(?:[\w.'’-]+,? ){0,5}"
                         r"(?:trimmers?|trim ?pots?|switch(?:es)?|toggles?|rotary|foot-?switch(?:es)?|DIP|jumpers?|pads?|jacks?|LEDs?)\b"
                         r"|^\s*(?:this )?(?:switches|toggles|selects|chooses|shorts)\b", re.I)
_CTRL_STOP = {"CURRENT DRAW", "NOTE", "NOTES", "TIP", "HTTP", "HTTPS", "INPUT", "OUTPUT", "RPD", "DIRECT OUT", "SEND", "RETURN"}


def _controls_from_doc(pages: list[str], pot_refs: list[str]) -> list[str]:
    """The doc's centered "Controls" heading is followed by '•  NAME: what it does' bullets
    for knobs, trimmers and switches alike; keep the knobs, in the doc's order. Boards
    without the section fall back to the named pots in the parts table."""
    text = "\n".join(pages[:6])
    m = re.search(r"^\s*Controls\s*$", text, re.M)
    names: list[str] = []
    if m:
        seen_bullet = False
        for line in text[m.end():].splitlines():
            if seen_bullet and re.match(r"^\s{30,}[A-Z][A-Za-z ]{2,30}\s*$", line):
                break  # next centered heading (Voltages, Notes, Wiring ...)
            b = _CTRL_BULLET.match(line) or _CTRL_PLAIN.match(line) or _CTRL_TITLE.match(line)
            if not b:
                continue
            seen_bullet = True
            paren, desc = b.group(2) or "", b.group(3)
            for name in re.split(r",\s*", b.group(1).strip()):
                if name.upper() in _CTRL_STOP or re.fullmatch(r"T\d(?:/T\d)?", name) or _NOT_A_KNOB.search(paren + " " + desc[:140]) or re.search(r"switch|toggle|trim", paren, re.I) \
                        or re.match(r"^(?:[RCDQL]|IC|SW)\d", name) or re.search(r"\bout\b|\bin\b", name, re.I):
                    continue  # part-mod bullets ("R4: ...") and jacks are not knobs
                names.append(name)
    pots = [r for r in pot_refs if r.isalpha() and r.upper() not in _CTRL_STOP]
    if names and pots:
        matched = [n for n in names if n.upper() in {p.upper() for p in pots}]
        if matched:
            names = matched
    if not names:
        names = pots
    return [n.title() if n.isupper() else n for n in names]

