"""GuitarPCB adapter. WooCommerce; BOM and schematic exist only as raster images
inside the build document, so BOM rows are OCR'd (best effort) when tesseract is
available, otherwise left empty."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import render_page, pdf_text_pages, _COL_DESIG, _COL_POT
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
        doc = HTMLParser(html)
        desc_n = doc.css_first("#tab-description")
        desc_html = desc_n.html if desc_n else ""
        pdfs = [a.attributes["href"] for a in HTMLParser(desc_html).css('a[href$=".pdf"]')
                if "Tonmann" not in a.attributes.get("href", "")]
        pdfs = [p for p in pdfs if re.search(r"build|BD_|doc", p + " ", re.I) or True]
        if not pdfs:
            return None
        ld = _product_ld(html)
        title_n = doc.css_first("h2.product_title, h1.product_title")
        full_title = clean_text(title_n.text()) if title_n else clean_text(ld.get("name", ""))
        full_title, sale_tags = _strip_prefixes(full_title)
        if re.search(r"painted enclosure|gift card|t-shirt|sticker", full_title, re.I):
            return None
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
            c.bom = _ocr_bom(pdf, slug, len(pages))
        return c


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


_OCR_POT = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,12})\s+(\d+(?:[.,]\d+)?[KM]?[ABCW])(?![A-Za-z0-9])")
_RANGE = re.compile(r"\*?\b([RCDQ])(\d+)\s*[-–]\s*[RCDQ]?(\d+)\s+([A-Z0-9][A-Z0-9.]+)", re.I)


def _clean_ocr_line(ln: str) -> str:
    """Repair the OCR slips that recur in GuitarPCB parts tables."""
    ln = re.sub(r"[_—–‘’'\"|&*]+", " ", ln)
    # designators: c13 -> C13, RS -> R5, cs -> C8, cg -> C9, R8& -> R8
    def fix_ref(m: re.Match) -> str:
        letter = m.group(1).upper()
        num = m.group(2).upper().replace("S", "5").replace("O", "0").replace("G", "9").replace("I", "1").replace("L", "1")
        return f"{letter}{num}"
    ln = re.sub(r"(?<![A-Za-z0-9])([RCDQrcdq])([0-9SOGILsogil]{1,3})(?![A-Za-z0-9])", fix_ref, ln)
    ln = re.sub(r"(?<![A-Za-z0-9])(?:IC|ic|Ic)([0-9SO]{1,2})(?![A-Za-z0-9])", lambda m: "IC" + m.group(1).replace("S", "5").replace("O", "0"), ln)
    # values: 'in' -> '1n', 'lk' -> '1k', 'O' as zero inside numbers
    ln = re.sub(r"(?<![A-Za-z0-9])in(?![A-Za-z0-9])", "1n", ln)
    ln = re.sub(r"(?<![A-Za-z0-9])l([kKnpuM])(?![A-Za-z0-9])", r"1\1", ln)
    ln = re.sub(r"(?<=\d)O(?=\d|[kKnpuMR]\b)", "0", ln)
    ln = re.sub(r"(?<![A-Za-z0-9])O(?=\d)", "0", ln)
    ln = re.sub(r"\b(TL|LM|NE|RC|JRC|OP|LF|CA|MC)O(\d)", r"\g<1>0\2", ln)  # TLO72 -> TL072
    return ln


def _ocr_bom(pdf, slug: str, n_pages: int) -> list[BomRow]:
    """OCR pages in order until one yields a real parts table (12+ rows), keeping
    the best: GuitarPCB puts the table on page 1, 2, 3 or later depending on the doc's age."""
    if not shutil.which("tesseract"):
        return []
    import pymupdf
    with pymupdf.open(pdf) as d:
        n_pages = d.page_count
    best: list[BomRow] = []
    for page_no in range(1, min(n_pages, 9) + 1):
        png = CACHE_DIR / "guitarpcb" / f"{slug}-p{page_no}.png"
        txt = png.with_suffix(".txt")
        if txt.exists():
            out = txt.read_text()
        else:
            if not png.exists():
                render_page(pdf, page_no, png, dpi=300)
            out = subprocess.run(["tesseract", str(png), "-", "--psm", "6"], capture_output=True, text=True).stdout
            txt.write_text(out)
        rows = _rows_from_ocr(out)
        if len(rows) > len(best):
            best = rows
        if len(best) >= 12:
            break
    return best


def _rows_from_ocr(out: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()

    def add(ref: str, value: str, ptype: str = "", cat: str = "") -> None:
        value = value.strip().rstrip(".,;:")
        if ref in seen or ref[0] in "J":
            return
        if cat != "POT" and (not re.search(r"\d", value) or not re.fullmatch(r"[A-Za-z0-9.\-/µu]{1,12}", value)):
            return
        nr = normalize_row(BomRow(ref=ref, value=value.strip(), part_type=ptype, notes="OCR", category=cat))
        if is_plausible(nr):
            seen.add(ref)
            rows.append(nr)

    for raw in out.splitlines():
        ln = _clean_ocr_line(raw)
        for letter, a, b, val in _RANGE.findall(ln):
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 40:
                for i in range(lo, hi + 1):
                    add(f"{letter.upper()}{i}", val)
        pairs = _COL_DESIG.findall(ln)
        # The board silkscreen also OCRs to stray pairs; the parts table has several per line.
        if len(pairs) >= 2 or (len(pairs) == 1 and re.search(r"\b(status|led|zener|ge)\b", ln, re.I)):
            for ref, val in pairs:
                if val.upper() in {"PNP", "NPN", "STATUS", "LED"}:
                    continue
                if re.search(r"\d", val) or len(val) >= 4:
                    add(ref, val)
        for ref, val in _OCR_POT.findall(ln):
            ref = ref.strip()
            if 3 <= len(ref) <= 12 and ref.isalpha() and ref.upper() not in {"AND", "THE", "FOR", "OUT", "GND"}:
                add(ref, val.replace(" ", ""), "Potentiometer", "POT")
    return rows


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
