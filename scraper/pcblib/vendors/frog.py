"""Frog Pedals adapter: a WooCommerce shop (behind a mod_security rule that wants a browser
user-agent) with a few tube preamp and overdrive PCBs; the documentation is sent to buyers,
so only the listing is indexed."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://frogpedals.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
            "Accept": "text/html,application/json,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
_BASED_ON = {"bluesmaster": "Marshall Blues Breaker", "tube-preamp-2-1": "Alembic F-2B", "f1a": "Fender Dual Showman"}


@register
class Frog(Adapter):
    vendor = "frog"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", ".json", headers=_HEADERS)
        for p in (json.loads(raw) if raw else []):
            cats = {c["slug"] for c in p.get("categories", [])}
            if not cats & {"pcb-products", "tube-preamp-pcbs", "guitareffectpedalpcbs", "powersupplypcbs"}:
                continue
            if re.search(r"cable|bundle|5 for", p["name"], re.I):
                continue
            self.products[p["slug"]] = p
            yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        title = clean_text(_html.unescape(p["name"]))
        name = re.sub(r"^Frog\s+|\s*\bPCB\b.*$|\s*for DIY.*$|\s*-\s*.*$|\s*–\s*.*$", "", title).strip()
        page = self.f.get_text(p["permalink"], ".html", headers=_HEADERS) or ""
        m = re.search(r'<div class="woocommerce-product-details__short-description">(.*?)</div>', page, re.S)
        body = clean_text(html_to_text(m.group(1))) if m else clean_text(html_to_text(p.get("short_description") or ""))
        prices = p.get("prices") or {}
        price = int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), "")
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], based_on=based_on,
                    description=(body + " Documentation is sent to buyers; it is not published.").strip(), price=price,
                    currency=prices.get("currency_code") or "USD", in_stock=p.get("is_in_stock"), doc_url=p["permalink"],
                    image_url=(p.get("images") or [{}])[0].get("src", "").split("?")[0], enclosure=find_enclosure(body))
        cats = {c_["slug"] for c_ in p.get("categories", [])}
        c.category = "Utility" if cats & {"powersupplypcbs", "stomp-switch-true-bypass-pcb"} and "preamp" not in slug else classify(name, based_on, title + ". " + body)
        return c
