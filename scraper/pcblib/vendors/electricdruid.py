"""Electric Druid adapter: Tom Wiltshire's four stompbox PCBs in a WooCommerce shop (GBP),
each with a construction guide PDF whose Bill of Materials is an Order / Ref / Description /
Value / Quantity table."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..gsheet import grid_bom
from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://electricdruid.net"
_BOARDS = {
    "hard-bargain-pcb": {"name": "Hard Bargain", "guide": f"{BASE}/wp-content/uploads/2019/11/HardBargainConstructionGuide.pdf",
                         "drill": f"{BASE}/wp-content/uploads/2019/11/HardBargainDrillTemplate.pdf", "page": f"{BASE}/designing-the-hard-bargain-distortion-pedal/", "category": "Distortion"},
    "flangelicious-pcb": {"name": "Flangelicious", "guide": f"{BASE}/wp-content/uploads/2016/05/FlangeliciousConstructionGuide.pdf",
                          "page": f"{BASE}/flangelicious-a-super-dooper-flanger/", "category": "Flanger"},
    "digidelay-pcb": {"name": "DigiDelay", "guide": f"{BASE}/wp-content/uploads/2016/12/DigiDelayConstructionGuide.pdf",
                      "drill": f"{BASE}/wp-content/uploads/2017/01/DigiDelayPanel.pdf", "page": f"{BASE}/diy-digital-delay/", "category": "Delay"},
    "filterfx-pcb": {"name": "FilterFX", "guide": f"{BASE}/wp-content/uploads/2019/02/FilterFXConstructionGuide.pdf",
                     "drill": f"{BASE}/wp-content/uploads/2019/04/FilterFXDrillTemplate.pdf", "page": f"{BASE}/filterfx-lp-bp-hp-lfo-filter/", "category": "EQ / Filter"},
}


def parse_order_table(pages: list[str]):
    """Rows of the 'Order Ref Description Value Quantity' table, split on runs of spaces; a
    line of designators alone continues the row above."""
    grid: list[list[str]] = []
    active = False
    for page in pages:
        for ln in page.splitlines():
            if re.match(r"\s*Order\s+Ref\s+Description\s+Value\s+Quantity", ln):
                active = True
                grid.append(["Order", "Ref", "Description", "Value", "Quantity"])
                continue
            if not active:
                continue
            if re.match(r"\s*(?:Additionally|Offboard components|Page \d+)", ln):
                active = False
                continue
            cells = [c.strip() for c in re.split(r"\s{2,}", ln.strip()) if c.strip()]
            if not cells:
                continue
            if len(cells) == 1 and grid and re.fullmatch(r"[A-Z]{1,3}\d{1,3}(?:,\s*[A-Z]{1,3}\d{1,3})*,?", cells[0]) and len(grid[-1]) > 2:
                grid[-1][1] = grid[-1][1].rstrip(",") + ", " + cells[0]
                continue
            if re.fullmatch(r"\d+", cells[0]) and len(cells) >= 4:
                if len(cells) == 4:  # a row without a value ("Indicator LEDs")
                    cells = cells[:3] + [""] + cells[3:]
                grid.append(cells[:5])
    return grid_bom(grid)


@register
class ElectricDruid(Adapter):
    vendor = "electricdruid"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        for slug in _BOARDS:
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?slug={slug}", ".json")
            prods = json.loads(raw) if raw else []
            if prods:
                self.products[slug] = prods[0]
                yield slug

    def parse(self, slug: str) -> Circuit | None:
        p, b = self.products.get(slug), _BOARDS[slug]
        if not p:
            return None
        prices = p.get("prices") or {}
        desc = html_to_text(p.get("description") or p.get("short_description") or "")
        c = Circuit(vendor=self.vendor, slug=slug.replace("-pcb", ""), name=b["name"], url=p["permalink"], description=desc[:700],
                    price=int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None,
                    currency=prices.get("currency_code", "GBP"), in_stock=p.get("is_in_stock"), doc_url=b["guide"],
                    image_url=(p.get("images") or [{}])[0].get("src", ""), enclosure=find_enclosure(desc), category=b["category"])
        c.extra_docs["Project page"] = b["page"]
        if b.get("drill"):
            c.extra_docs["Drill template"] = b["drill"]
        pdf = self.f.get_file(b["guide"], ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            res = process_document(pdf, self.vendor, c.slug)
            rows, _ = parse_order_table(pages)
            rows = [r for r in rows if not re.search(r"socket|DIP", r.part_type + " " + r.value, re.I)]
            for r in rows:
                if r.category == "TRIM" and re.search(r"transistor", r.part_type, re.I):
                    r.category = "Q"
            c.bom = max(res["bom"], rows, key=len)
            c.schematic_local, c.schematic_page, c.doc_version = res["schematic_local"], res["schematic_page"], res["doc_version"]
            over = re.search(r"Overview\s*\n(.{40,600}?)\n\s*\n", "\n".join(pages[:3]), re.S)
            if over:
                c.description = clean_text(over.group(1))[:700]
        pots = [r for r in c.bom if r.category == "POT"]
        c.controls = [f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else []
        return c
