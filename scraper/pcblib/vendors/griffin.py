"""Griffin Effects adapter: a PrestaShop 1.6 store (USD) whose BYO PCBs category lists boards
that 'compare to' a named original. Each product page attaches a project PDF with a
three-column parts list, drill template, wiring and schematic."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..ibom import parse_ibom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import parse_bom_columns, pdf_text_pages, process_document, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://griffineffects.com"
LISTING = f"{BASE}/byo-pcbs"
_SKIP_CAT = {"utility", "switching", "coming-soon"}
_UTILITY = re.compile(r"3pdt|breakout|charge pump|audio probe|top mount jack", re.I)


_DASH = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,3}\d{1,3}|[A-Z][A-Z]{2,11})\s*[-–]\s*([A-Za-z0-9.µ]+(?:\s?(?:PCB Mount|electrolytic|ceramic|film))?)(?![A-Za-z0-9])")


def parse_dash_list(pages: list[str]) -> list[BomRow]:
    """Older Griffin guides list parts as 'R1 - 10K' and 'LEVEL – A500K PCB Mount'."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        if not re.search(r"Parts Checklist|Component List", page, re.I):
            continue
        for ref, val in _DASH.findall(page):
            val = re.sub(r"\s*(?:PCB Mount|electrolytic|ceramic|film)$", "", val).rstrip("*")
            if ref in seen or ref in ("LED", "PCB", "DC", "AC"):
                continue
            cat = "POT" if ref.isalpha() and re.match(r"^[ABCW]?\d+[kKM]?[ABCW]?$", val) else ""
            r = normalize_row(BomRow(ref=ref if cat else ref, value=val, category=cat))
            if cat or (re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref) and is_plausible(r)):
                seen.add(ref)
                rows.append(r)
    return rows


@register
class Griffin(Adapter):
    vendor = "griffin"

    def list_targets(self) -> Iterable[str]:
        seen: set[str] = set()
        for page in range(1, 10):
            h = self.f.get_text(f"{LISTING}?p={page}" if page > 1 else LISTING, ".html") or ""
            links = sorted(set(re.findall(r'href="(https://griffineffects\.com/byo-pcbs/[a-z0-9-]+/[a-z0-9-]+)"', h)))
            new = [l for l in links if l not in seen]
            if not new:
                break
            for l in new:
                seen.add(l)
                if l.split("/")[-2] in _SKIP_CAT or _UTILITY.search(l.rsplit("/", 1)[-1]):
                    continue
                yield l

    def parse(self, url: str) -> Circuit | None:
        h = self.f.get_text(url, ".html")
        if not h:
            return None
        title = clean_text(_html.unescape(re.sub(r"\s*-\s*Griffin Effects\s*$", "", (re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1])))
        name = re.sub(r"\s+PCB\s*$", "", title).strip()
        price = re.search(r'itemprop="price"[^>]*content="([\d.]+)"', h)
        avail = re.search(r'id="availability_value"[^>]*>([^<]*)<', h)
        compare = re.search(r"Compare to (?:the )?([^<]+)<", h)
        desc = html_to_text((re.search(r'id="idTab1"[^>]*>(.*?)</div>', h, re.S) or [None, ""])[1])
        att = re.search(r'attachment\?id_attachment=(\d+)"[^>]*>\s*([^<]+?)\s*<', h)
        if not att:
            return None  # boards announced as coming soon have no project file yet
        img = re.search(r'id="bigpic"[^>]*src="([^"]+)"', h) or re.search(r'property="og:image" content="([^"]+)"', h)
        diff = re.search(r"Difficulty/([a-z]+)\d*\.png", h)
        based_on = clean_text(_html.unescape(compare.group(1))) if compare else ""
        based_on = re.sub(r"\s+(?:which|that)\b.*$", "", based_on).strip(" .")
        doc = f"{BASE}/attachment?id_attachment={att.group(1)}"
        c = Circuit(vendor=self.vendor, slug=url.rsplit("/", 1)[-1].replace("-pcb", ""), name=name, url=url, based_on=based_on,
                    description=desc[:700], price=float(price.group(1)) if price and float(price.group(1)) > 0 else None, currency="USD",
                    in_stock=None if not avail else avail.group(1).strip().lower() == "in stock", doc_url=doc,
                    image_url=img.group(1) if img else "", enclosure=find_enclosure(desc), difficulty=diff.group(1).capitalize() if diff else "")
        pdf = self.f.get_file(doc, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            mv = re.search(r"\bv(\d+(?:\.\d+)*)\b", pages[0] if pages else "", re.I)
            c.doc_version = mv.group(1) if mv else ""
            res = process_document(pdf, self.vendor, c.slug)
            c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
            if len(c.bom) < 8:
                c.bom = max(c.bom, parse_dash_list(pages), parse_bom_columns(["PARTS LIST\n" + p for p in pages[:3]]), key=len)
            ib = re.search(r"https?://files\.griffineffects\.com/ibom/\S+\.html", "\n".join(pages[:2]))
            if ib and len(c.bom) < 8:
                page = self.f.get_file(ib.group(0), ".html")
                if page:
                    c.bom = max(c.bom, parse_ibom(page), key=len)
                    c.extra_docs["Interactive BOM"] = ib.group(0)
            if not c.schematic_page:
                for i, page in enumerate(pages, start=1):
                    heads = [ln.strip() for ln in page.splitlines() if ln.strip()][:2]
                    if heads and re.fullmatch(r"\d\.\s*Schematic:?", heads[0]) and len(heads) == 1:
                        png = CACHE_DIR / self.vendor / f"{c.slug}-schematic.png"
                        if not png.exists():
                            render_page(pdf, i, png)
                        c.schematic_local, c.schematic_page = str(png.relative_to(DATA_DIR)), i
                        break
            c.enclosure = c.enclosure or find_enclosure("\n".join(pages[:2]))
        c.category = classify(name, based_on, desc[:300])
        pots = [r for r in c.bom if r.category == "POT"]
        c.controls = [f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else []
        return c
