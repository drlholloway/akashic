"""GuitarPCB adapter. WooCommerce; most build documents hold the BOM and schematic only
as raster images, so BOM rows are OCR'd (best effort) when tesseract is available. A
document whose text layer carries the table (the MUFF'N variant chart) is read from it."""
from __future__ import annotations

import json
import re
from typing import Iterable

from selectolax.lexbor import LexborHTMLParser

from ..db import _ACRONYM_KNOBS
from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import expand_refs, render_page, pdf_text_pages, ocr_bom, text_bom
from ..normalize import is_prose_value
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
        doc = LexborHTMLParser(html)
        desc_n = doc.css_first("#tab-description")
        desc_html = desc_n.html if desc_n else ""
        pdfs = [a.attributes["href"] for a in LexborHTMLParser(desc_html).css('a[href$=".pdf"]')
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
            # Many docs (the NostalgiTone line, the MUFF'N's ten-variant chart) carry the table in their text
            # layer, which is exact; OCR only adds the parts it does not list and never replaces one it does.
            text = [r for r in _text_bom_per_circuit(pages) if not (r.category in ("D", "Q", "IC")
                    and (re.match(r"^[^\w*]", r.value) or re.fullmatch(r"[a-z]{3,}", r.value)))  # '(Q1 -Q2)', 'Q8 require' in prose
                    and not is_prose_value(r.category, r.value)]  # 'D1 – D4 Clipping Diodes' is a note, not four parts
            for r in text:
                if r.category in ("D", "Q", "IC", "LED") and r.value.startswith("*"):  # '*TL072': a footnote star
                    r.value, r.norm_value, r.notes = r.value.lstrip("* "), "", "; ".join(x for x in (r.notes, "see the build notes") if x)
                    normalize_row(r)
            if len({r.ref.upper() for r in text}) < 12:
                text = []  # a few parts read out of prose ('Q8 require'), not a table
            ocr = ocr_bom(pdf, self.vendor, slug)
            if len(ocr) < 12:
                thorough = ocr_bom(pdf, self.vendor, slug, thorough=True)  # upscaled, thresholded passes for small type
                if len(thorough) > len(ocr):
                    ocr = thorough
            have = {r.ref.upper() for r in text}
            knobs = any(r.category in ("POT", "TRIM") for r in text)
            # As in process_document, parts no variant names stay unlabelled. A knob OCR names differently
            # ('FUZZ' for the text's 'Sus/Fuzz') cannot be matched, so named rows only come in when text has none.
            from_grid = bool(text) and len(_BOM_HEADING.findall("\n".join(pages))) < 2 and _grid_wins(pages)  # a heading-free grid table lists every part
            top: dict[str, int] = {}
            for r in text:
                if m := re.fullmatch(r"([A-Z]+)(\d+)[A-Z]?", r.ref.upper()):
                    top[m.group(1)] = max(top.get(m.group(1), 0), int(m.group(2)))

            def fills_gap(ref: str) -> bool:
                """Beside a grid table, OCR may fill a gap (R5 between R4 and R6) or a kind it lacks (no ICs), but
                not run past it: R20 or D7 beside a table that ends at R8 and D2 is a misread label."""
                m = re.fullmatch(r"([A-Z]+)(\d+)[A-Z]?", ref.upper())
                return not m or m.group(1) not in top or int(m.group(2)) <= top[m.group(1)]
            c.bom = text + [r for r in ocr if r.ref.upper() not in have and not (knobs and not re.search(r"\d", r.ref))
                            and (not from_grid or fills_gap(r.ref))]
            if not c.controls:
                c.controls = list(dict.fromkeys((r.ref if r.ref != r.ref.upper() or r.ref in _ACRONYM_KNOBS else r.ref.title())
                                                for r in c.bom if r.category == "POT"
                                                and re.sub(r"[/ ]", "", r.ref).isalpha()))  # 'Sus/Fuzz'; once across variants
        return c


_BOM_HEADING = re.compile(r"^\s*Bill of Materials\s+(?:for\s+)?(.+?)\s*:\s*$", re.I | re.M)


def _text_bom_per_circuit(pages: list[str]) -> list[BomRow]:
    """Dual-combo docs hold one parts table per pedal ('Bill of Materials Doomstortion:' then
    'Bill of Materials Harbinger Fuzz:'), numbered from R1 each. Each section is read on its own and
    its rows are labelled with the pedal's name, so the two boards' R7s stay apart."""
    whole = "\n".join(pages)
    heads = list(_BOM_HEADING.finditer(whole))
    if len(heads) < 2:
        return _grid_bom(pages) if _grid_wins(pages) else text_bom(pages)
    rows: list[BomRow] = []
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else len(whole)
        part = text_bom([whole[m.start():end]])  # the heading stays: the column parser starts at it
        if not part:
            return text_bom(pages)  # one pedal's table is an image (Sonic Bloom): read the doc whole, OCR fills in
        name = m.group(1).strip(" –—-")
        for r in part:
            r.variant = f"{name} {r.variant}".strip()
            rows.append(r)
    return rows


def _grid_wins(pages: list[str]) -> bool:
    """The heading-free grid reads the doc when it finds more parts than the table parsers, which can
    pick a few pairs out of the prose ('TR1 so', 'Q2 after' in Blues Power) that are filtered later."""
    return len(_grid_bom(pages)) > len(text_bom(pages))


_GRID_ONE = r"(?:R|C|D|Q|IC|U|LED|L|TR|VR|RV|SW|P)\d{1,3}[A-Z]?"
_GRID_REF = re.compile(rf"^\*?{_GRID_ONE}(?:\s*[-–,]\s*(?:{_GRID_ONE}|\d{{1,3}}))*\*?$")  # 'R1', 'Q1 - Q4', 'D1, D2', 'D3-D6'
_GRID_KNOB = re.compile(r"^\*?[A-Z][A-Za-z/. ]{1,13}\d?\*?$")  # 'GAIN.BRT', 'VOL2'
_GRID_POT = re.compile(r"^([ABCW]?)\s?(\d+(?:\.\d+)?\s?[kKM]?)\s?([ABCW]?)(?:\s+(LIN|LINEAR|LOG|AUDIO|REV|REVLOG|TRIM|TRIMMER))?(?=\s|$)", re.I)
_TAPER = {"LIN": "B", "LINEAR": "B", "LOG": "A", "AUDIO": "A", "REV": "C", "REVLOG": "C"}


def _grid_bom(pages: list[str]) -> list[BomRow]:
    """A parts table with no headings, laid out as REF VALUE pairs across the row (the pink GuitarPCB
    table: 'R1  1M  C1  220n  Q1  2N3904'). Ranges and lists expand ('Q1 - Q4  J113'), named knobs take
    their taper from a letter or a word ('VOL  A100k', 'PINCH  500k Lin'; 'BIAS  10k Trim' is a
    trimmer), and a version-tagged cell ('D1  V4 - 1N5817.') is that version's part. Footnote stars
    are dropped with a note. Only a run of twelve or more designators counts, so pairs read out of
    prose or a schematic never do."""
    rows: list[BomRow] = []
    for page in pages:
        found: list[tuple[str, str]] = []
        for line in page.splitlines():
            cells = []
            for cell in re.split(r"\s{2,}", line.replace("–", "-").strip()):
                cell = cell.strip()
                if not cell or re.fullmatch(r"\d+(?:\.\d+)?\s?V", cell):    # a voltage-rating column ('63V')
                    continue
                m = re.match(rf"^\**\s*({_GRID_ONE}(?:\s*-\s*{_GRID_ONE})?)\s+((?!-)\S.{{0,24}})$", cell)
                cells += [m.group(1), m.group(2)] if m else [cell]       # '** Q2-Q6 J201 (see notes)' is a pair in one cell
            pairs, k = [], 0
            while k < len(cells) - 1:  # pair cell by cell, so one stray cell ('BTDR-2H') does not shift the row
                a, b = cells[k], cells[k + 1]
                knob = _GRID_KNOB.match(a) and not _GRID_REF.match(a) and (_GRID_POT.match(b.strip("* ")) or re.search(r"\b[SD]P[SD]T\b", b))
                if knob or (_GRID_REF.match(a) and not _GRID_REF.match(b)):  # 'DECAY  C1M': a pot value, not the designator C1M
                    pairs.append((a, b))
                    k += 2
                else:
                    k += 1
            short = len(pairs) == 1 and len(cells) <= 3 and len(pairs[0][1]) <= 20  # a column's last row: 'C9  100n'
            if (len(pairs) >= 2 or short) and len(pairs) * 2 >= len(cells) - 2:
                found += pairs
        if sum(len(expand_refs(a.strip("*"))) for a, _ in found if _GRID_REF.match(a)) < 12:
            continue
        for ref, value in found:
            note = "see the build notes" if "*" in ref + value else ""
            ref, variant, cat, ptype = ref.strip("* "), "", "", ""
            value = re.sub(r"\s*\*+\s*", " ", value).strip()            # '1k8 *CLR', '*** J113'
            value = re.sub(r"\s*\(see notes?\)$", "", value, flags=re.I)
            if m := re.fullmatch(r"(.+?)\s*\(([A-Za-z ]+)\)", value):     # 'Yellow (vibe)': the part's role is a note
                value, note = m.group(1), "; ".join(x for x in (note, m.group(2)) if x)
            if m := re.fullmatch(r"(\S*\d\S*)\s+-\s+(\d+(?:\.\d+)?\s?[vV])", value):  # '1N5232 - 5.6v': a zener's voltage
                value, note = m.group(1), "; ".join(x for x in (note, m.group(2).replace(" ", "").upper()) if x)
            if m := re.match(r"^V(\d+)\s*[-–]\s*(.+?)\.?$", value):   # 'V4 - 1N5817.'
                variant, value = f"V{m.group(1)}", m.group(2)
            if not _GRID_REF.match(ref):                                  # a named knob or switch
                name = ref.title() if len(ref) > 3 else ref.upper()       # EQ stays EQ
                if m := _GRID_POT.match(value):
                    word = (m.group(4) or "").upper()
                    taper = m.group(1) or m.group(3) or _TAPER.get(word, "")
                    rest = value[m.end():].strip()                        # '*B5K and 5k1 Resistor'
                    note = "; ".join(x for x in (note, rest) if x)
                    trim = word.startswith("TRIM") or (not taper and re.search(r"BIAS|TRIM|ADJ|SET", name, re.I))
                    cat = "TRIM" if trim else "POT"                       # 'BIAS  20K' is a trimmer, 'TREB  50k' a knob
                    value = (taper if cat == "POT" else "") + m.group(2).replace(" ", "")
                    ptype = "Trimmer" if cat == "TRIM" else "Potentiometer"
                else:
                    cat, ptype = "SW", "Switch"
                refs = [name]
            elif re.fullmatch(r"P\d+", ref) and not _GRID_POT.match(value):
                continue                                                  # 'P1  VOL 1': a knob's label, not its value
            else:
                refs = expand_refs(ref)
            for one in refs:
                r = normalize_row(BomRow(ref=one, value=value, notes=note, category=cat, part_type=ptype, variant=variant))
                if cat or is_plausible(r) or r.category in ("LED", "D"):
                    rows.append(r)
        break
    variants = sorted({r.variant for r in rows if r.variant}, key=lambda v: -int(v[1:]))  # newest version first
    return sorted(rows, key=lambda r: variants.index(r.variant) if r.variant else -1) if variants else rows


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
