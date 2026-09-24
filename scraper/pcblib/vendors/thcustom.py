"""TH Custom Effects adapter: a WooCommerce shop (EUR) of mostly switchers, kits and parts,
with a row of effect PCBs. The product pages say 'PCB only!' and publish no build
documents, so only the listing is indexed."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://diy.thcustom.com"
_KEEP = {"overdrivedistortion", "modulation", "boost", "boost-kits", "eq", "tube", "splitter-mixer", "mixer-splitter", "other"}
_SKIP = re.compile(r"bundle|enclosure|helper|holder|jack|switch\b|socket|regulator|chip\b|software|download|service|tracer|tube driver1590bb v1\.3", re.I)
_BASED_ON = {"cruz-driver": "Jon Patton Cru'z Driver", "small-time": "Merlin Blencowe Small Time", "glassblower": "Merlin Blencowe Glassblower"}
_CATEGORY = {"cruz-driver": "Overdrive", "small-time": "Delay", "glassblower": "Boost", "tube-driver": "Overdrive", "valv-e-tizer": "Preamp / Amp-in-a-box", "kittenqueen": "Overdrive"}


@register
class THCustom(Adapter):
    vendor = "thcustom"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        for page in (1, 2, 3):
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            prods = json.loads(raw) if raw else []
            if not prods:
                break
            for p in prods:
                cats = {c["slug"] for c in p.get("categories", [])}
                name = _html.unescape(p["name"])
                if not cats & _KEEP or _SKIP.search(name) or not re.search(r"\bPCB\b|\bKit\b", name):
                    continue
                if "Kit" in name and any(re.sub(r"\s*[–-]\s*(Kit|PCB).*$", "", _html.unescape(q["name"])) == re.sub(r"\s*[–-]\s*(Kit|PCB).*$", "", name) and "PCB" in q["name"] for q in prods):
                    continue  # the kit beside its bare PCB
                self.products[p["slug"]] = p
                yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        title = clean_text(_html.unescape(p["name"]))
        name = re.sub(r"\s*[–-]\s*(?:PCB|Kit)\b.*$|\s*-?\s*PCB$|\s+V\d+(?:\.\d+)?\s*(?:PCB|Kit)?$", "", title).strip()
        page = self.f.get_text(p["permalink"], ".html") or ""
        tab = re.search(r'id="tab-description"[^>]*>(.*?)</div>', page, re.S)
        body = clean_text(html_to_text(tab.group(1))) if tab else clean_text(html_to_text(p.get("short_description") or ""))
        body = re.sub(r"Sound demo:\s*\S+", "", body).strip()
        prices = p.get("prices") or {}
        price = int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), "")
        mv = re.search(r"\bV(\d+(?:\.\d+)?)\b", title)
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], based_on=based_on,
                    description=(body + " No build document is published; the board is sold bare.").strip(), price=price,
                    currency=prices.get("currency_code") or "EUR", in_stock=p.get("is_in_stock"), doc_url=p["permalink"], doc_version=mv.group(1) if mv else "",
                    image_url=(p.get("images") or [{}])[0].get("src", "").split("?")[0], enclosure=find_enclosure(title + " " + body))
        cats = {c_["slug"] for c_ in p.get("categories", [])}
        c.category = next((v for k, v in _CATEGORY.items() if k in slug), "") or ("EQ / Filter" if re.search(r"\bEQ\b", title) else "Utility" if cats & {"splitter-mixer", "mixer-splitter"} else classify(name, based_on, title + ". " + body))
        return c
