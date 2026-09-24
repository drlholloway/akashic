"""TH Custom Effects adapter: a WooCommerce shop (EUR). The main shop page is a product
table whose rows carry a 'Build Instructions' link to an HTML build-documentation page
with a Ref / Qty / Value / Notes table; boards only in the store API have no document."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..gsheet import grid_bom
from ..models import Circuit
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://diy.thcustom.com"
SHOP = f"{BASE}/the-main-shop/"
_KEEP = {"overdrivedistortion", "modulation", "boost", "boost-kits", "eq", "tube", "splitter-mixer", "mixer-splitter", "other"}
_SKIP = re.compile(r"bundle|enclosure|helper|holder|jack|switch\b|socket|regulator|chip\b|software|download|service|tracer", re.I)
_BASED_ON = {"cruz-driver": "Jon Patton Cru'z Driver", "small-time": "Merlin Blencowe Small Time", "glassblower": "Merlin Blencowe Glassblower",
             "equinox": "Merlin Blencowe Equinox II", "tri-vibe": "RunOffGroove Tri-Vibe", "condor": "RunOffGroove Condor",
             "supreaux": "RunOffGroove Supreaux Deux", "umble": "RunOffGroove Umble", "azabache": "RunOffGroove Azabache",
             "ginger": "RunOffGroove Ginger", "tube-driver": "Chandler Tube Driver", "ac-sim": "", "u-boat": "", "re-verb": ""}
_CATEGORY = {"cruz-driver": "Overdrive", "small-time": "Delay", "glassblower": "Boost", "tube-driver": "Overdrive", "valv-e-tizer": "Preamp / Amp-in-a-box",
             "kittenqueen": "Overdrive", "tri-vibe": "Vibrato / Chorus", "condor": "Preamp / Amp-in-a-box", "supreaux": "Overdrive", "umble": "Overdrive",
             "azabache": "Overdrive", "ginger": "Preamp / Amp-in-a-box", "equinox": "Reverb", "re-verb": "Reverb", "ac-sim": "EQ / Filter", "u-boat": "Octave / Pitch",
             "headphone": "Utility", "optotronik": "Utility", "madbox": "Utility", "parametriq": "EQ / Filter", "5-band-eq": "EQ / Filter"}
_ORIG = re.compile(r"based on (?:the |a )?([A-Za-z][\w'&.-]*(?:\s+[A-Za-z0-9][\w'&.-]*){0,4}?)(?:\s+design|\s+circuit|[.,;])", re.I)


def _slug_key(slug: str) -> str:
    return next((k for k in _CATEGORY if k in slug), "")


@register
class THCustom(Adapter):
    vendor = "thcustom"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        shop = self.f.get_text(SHOP, ".html") or ""
        for pid, attrs, body in re.findall(r'<tr\s+data-wcpt-product-id="(\d+)"([^>]*)>(.*?)</tr>', shop, re.S):
            m = re.search(r"<a class='wcpt-title[^']*' href='([^']+)'[^>]*>(.*?)</a>", body, re.S)
            doc = re.search(r'href="([^"]*wpdmdl=\d+)"', body)
            if not m or not doc:
                continue
            url = m.group(1)
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            stock = re.search(r'data-wcpt-stock\s*=\s*"([^"]*)"', attrs)
            price = re.search(r'data-wcpt-price\s*=\s*"([^"]*)"', attrs)
            self.products[slug] = {"name": _html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(), "permalink": url, "doc": re.sub(r"^https?//", "https://", doc.group(1)),
                                   "price": float(price.group(1)) if price and re.match(r"^\d+(\.\d+)?$", price.group(1)) else None,
                                   "in_stock": None if not stock or not stock.group(1).strip() else int(stock.group(1)) > 0,
                                   "image": (re.search(r'<img[^>]+src="([^"]+)"', body) or [None, ""])[1]}
        for page in (1, 2, 3):  # the store API adds boards the shop table does not list, and the price behind a bundle row
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            prods = json.loads(raw) if raw else []
            if not prods:
                break
            for p in prods:
                cats = {c["slug"] for c in p.get("categories", [])}
                name = _html.unescape(p["name"])
                shop_key = next((s for s in self.products if p["slug"].startswith(s) and "Bundle" in self.products[s]["name"]), None)
                if shop_key and "PCB" in name and "Bundle" not in name:  # the shop table listed the bundle add-on; the PCB itself is here
                    prices = p.get("prices") or {}
                    self.products[shop_key].update({"name": name, "permalink": p["permalink"], "in_stock": p.get("is_in_stock"),
                                                    "price": int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None})
                    continue
                if p["slug"] in self.products or not cats & _KEEP or _SKIP.search(name) or not re.search(r"\bPCB\b|\bKit\b", name):
                    continue
                base = re.sub(r"\s*[–-]\s*(Kit|PCB).*$", "", name)
                if "Kit" in name and any(re.sub(r"\s*[–-]\s*(Kit|PCB).*$", "", _html.unescape(q["name"])) == base and "PCB" in q["name"] for q in prods):
                    continue
                if any(_slug_key(p["slug"]) and _slug_key(p["slug"]) == _slug_key(s) for s in self.products if _slug_key(s)):
                    continue  # a kit or older revision of a board the shop table documents
                prices = p.get("prices") or {}
                self.products[p["slug"]] = {"name": name, "permalink": p["permalink"], "doc": "", "in_stock": p.get("is_in_stock"),
                                            "price": int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None,
                                            "image": (p.get("images") or [{}])[0].get("src", ""), "cats": cats, "short": p.get("short_description") or ""}
        yield from list(self.products)

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        title = clean_text(p["name"])
        name = re.sub(r"\s*[–-]\s*(?:PCB|Kit|Bundle)\b.*$|\s*-?\s*PCB$|\s+V\d+(?:\.\d+)?\s*(?:PCB|Kit)?$", "", title).strip()
        name = re.sub(r"\s+PCB\s*$|\s*[–-]\s*$", "", name).strip()
        mv = re.search(r"\bV(\d+(?:\.\d+)?)\b", title)
        key = _slug_key(slug)
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), "")
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], based_on=based_on, price=p["price"], currency="EUR",
                    in_stock=p["in_stock"], doc_url=p["doc"] or p["permalink"], doc_version=mv.group(1) if mv else "",
                    image_url=(p.get("image") or "").split("?")[0])
        if not p["doc"]:  # boards only in the store API: their product page carries the same download link
            page = self.f.get_text(p["permalink"], ".html") or ""
            m = re.search(r"wpdmdl=(\d+)", page)
            if m:
                p["doc"] = f"{BASE}/?wpdmdl={m.group(1)}"
                c.doc_url = p["doc"]
        if p["doc"]:
            doc = self.f.get_text(p["doc"], ".html") or ""
            body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", doc, flags=re.S)
            paras = [clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", x))) for x in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
            c.description = " ".join(x for x in paras if len(x) > 40)[:700]
            if not c.based_on:
                m = _ORIG.search(c.description)
                if m and not re.match(r"^(?:a|an|the)\b", m.group(1), re.I):
                    c.based_on = clean_text(m.group(1)).replace("'s ", " ").replace("’s ", " ")
            text = clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", body)))
            c.enclosure = find_enclosure(text)
            for tbl in re.findall(r"<table.*?</table>", body, re.S):
                grid = [[_html.unescape(re.sub(r"<[^>]+>", " ", cell)).strip() for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]
                        for row in re.findall(r"<tr.*?</tr>", tbl, re.S)]
                rows, enc = grid_bom(grid)
                if len(rows) > len(c.bom):
                    c.bom = rows
                c.enclosure = c.enclosure or enc
        else:
            c.description = (clean_text(html_to_text(p.get("short", ""))) + " No build document is published; the board is sold bare.").strip()
        c.category = _CATEGORY.get(key) or classify(name, c.based_on, title + ". " + c.description)
        pots = [r for r in c.bom if r.category == "POT"]
        named = [r.ref.title() for r in pots if re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}\d?", r.ref)]
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{2,15}", r.ref)]
        return c
