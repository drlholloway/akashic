"""Rullywow Industries adapter: a WooCommerce shop whose product pages link a text build
document PDF; product titles carry the original after a dash or in parentheses."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import ocr_bom, pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://rullywow.com"
API = f"{BASE}/wp-json/wc/store/v1/products?per_page=100"
_BRANDS = {"king of tone": "Analogman King of Tone", "pharoh": "Black Arts Toneworks Pharaoh", "pharaoh": "Black Arts Toneworks Pharaoh",
           "plexidrive": "Wampler Plexi-Drive", "bosstone": "Jordan Boss Tone", "rangemaster": "Dallas Rangemaster", "big muff pi": "EHX Op-Amp Big Muff",
           "superlead": "Lovepedal Superlead", "jan ray": "Vemuram Jan Ray", "compulator": "Demeter Compulator", "ts808": "Ibanez TS808",
           "axis fuzz": "Axis Fuzz", "talons": "Talons", "demo tape fuzz": "Demo Tape Fuzz", "schaller": "Schaller Tremolo", "dynamic overdrive": "Dynamic Overdrive",
           "lovepedal eternity": "Lovepedal Eternity", "eternity": "Lovepedal Eternity"}
_GENERIC = re.compile(r"^(?:compressor|fuzz|preamp|bass preamp|cocked wah effect|wacky fuzz pcb|diy optical tremolo|diy\. pcb\. crunch\. dist\.|snap off 3pdt daughterboard|"
                      r"diy guitar pedal[^|]*|bare pcb|inspired by\s*)$", re.I)
_GENERIC_WORDS = {"crunch", "dist", "distortion", "overdrive", "od", "fuzz", "compressor", "preamp", "bass", "boost", "tremolo", "optical", "wah",
                  "effect", "wacky", "pcb", "diy", "guitar", "pedal", "cocked", "clone", "inspired", "by", "and", "a", "an", "the", "snap", "off", "daughterboard", "opamp", "op", "amp"}
_UTILITY = ("3pdt", "daughterboard", "optical switching", "detour", "breakout")


def _split_title(title: str) -> tuple[str, str]:
    """'Uberlead – Lovepedal Superlead Distortion & OD' -> ('Uberlead', 'Lovepedal Superlead');
    'King Tut Fuzz (Pharoh clone) PCB' -> ('King Tut Fuzz', 'Black Arts Toneworks Pharaoh')."""
    t = clean_text(_html.unescape(title)).replace("“", "").replace("”", "").replace("™", "")
    t = re.sub(r"\s*\(bare PCB\)|\s*\bPCB\b\.?|\s*\bDIY\b\.?", "", t).strip()
    t = re.sub(r"(\s+[–\-])(?:\s*\.)+", r"\1", t)  # 'Superjudge – DIY. PCB. Crunch' left '– . .'
    paren = re.match(r"^(.*?)\s*(?:\[|\()(.+?)[\])]\s*$", t)
    dash = re.match(r"^(.*?)\s+[–\-]\s+(.+?)\s*$", t)
    if paren and dash and t.find("(") < t.find(" – ") + 1 and t.find("(") >= 0:
        dash = None  # the dash sits inside the parenthesis: 'Muff Opportunity (Big Muff Pi – Opamp clone)'
    m = dash or paren
    name, sub = (m.group(1).strip(), m.group(2).strip()) if m else (t, "")
    name = re.sub(r"\s*[–\-]\s*$", "", name).strip(" –-")
    sub = re.sub(r"^(?:inspired by|a|an)\s+|\s*(?:clone|inspired)\s*$", "", sub, flags=re.I).strip(" .")
    low = sub.lower()
    for k, v in _BRANDS.items():
        if k in low:
            return name, v
    words = [w for w in re.findall(r"[a-z]+", low) if w]
    if not sub or _GENERIC.match(sub) or all(w in _GENERIC_WORDS for w in words):
        return name, ""
    return name, re.sub(r"\s+(?:distortion|overdrive|fuzz|boost|&|and|od)\b.*$", "", sub, flags=re.I).strip()


@register
class Rullywow(Adapter):
    vendor = "rullywow"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(API, ".json")
        prods = json.loads(raw) if raw else []
        names = {re.sub(r"\s*\(.*$|\s*[–-].*$", "", clean_text(_html.unescape(p["name"]))).strip().lower() for p in prods}
        for p in prods:
            cats = {c["slug"] for c in p.get("categories", [])}
            if cats & {"arduino"}:
                continue
            base = re.sub(r"\s*\(.*$|\s*[–-].*$", "", clean_text(_html.unescape(p["name"]))).strip().lower()
            if re.fullmatch(r"queen of bone", base) and "queen of bone 2" in names:
                continue  # the older board beside its successor
            self.products[p["slug"]] = p
            yield p["slug"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        page = self.f.get_text(p["permalink"], ".html") or ""
        pdfs = list(dict.fromkeys(u.replace(" ", "%20") for u in re.findall(r'href="([^"]+\.pdf[^"]*)"', page, re.I)
                                  if not re.search(r"What-Components|Enclosure|Diagram|Dimensions", u, re.I)))
        pdfs.sort(key=lambda u: "%20" in u)  # a copy with spaces in its name serves 404s
        if not pdfs:
            return None
        name, based_on = _split_title(p["name"])
        m = re.search(r'<div class="woocommerce-product-details__short-description">(.*?)</div>', page, re.S)
        body = html_to_text(m.group(1)) if m else html_to_text(p.get("short_description") or p.get("description") or "")
        prices = p.get("prices") or {}
        price = int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")  # the shop's own slugs are copy-of-copy leftovers
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=p["permalink"], based_on=based_on, description=clean_text(body),
                    price=price or None, currency=prices.get("currency_code") or "USD", in_stock=p.get("is_in_stock"), doc_url=pdfs[0],
                    enclosure=find_enclosure(body), image_url=(p.get("images") or [{}])[0].get("src", "").split("?")[0])
        for u in pdfs[1:]:
            c.extra_docs[u.rsplit("/", 1)[-1][:50]] = u
        pdf = self.f.get_file(pdfs[0], ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            c.enclosure = c.enclosure or find_enclosure("\n".join(pages[:3]))
            mv = re.search(r"\b(?:v|version|rev\.?)\s?(\d+(?:\.\d+)+[A-Za-z]?)\b", "\n".join(pages[:2]), re.I)
            c.doc_version = mv.group(1) if mv else ""
            res = process_document(pdf, self.vendor, slug)
            c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
            if len(c.bom) < 8:
                c.bom = max(c.bom, ocr_bom(pdf, self.vendor, slug), key=len)
        c.category = "Utility" if any(k in slug for k in _UTILITY) else classify(name, based_on, _html.unescape(p["name"]) + ". " + body[:300])
        pots = [r for r in c.bom if r.category == "POT"]
        named = [r.ref.title() for r in pots if re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}\d?", r.ref)]
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{2,15}", r.ref)]
        return c
