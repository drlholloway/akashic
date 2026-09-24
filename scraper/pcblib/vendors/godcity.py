"""God City Instruments adapter: a Shopify collection of Kurt Ballou's DIY PCBs, each linking
a text build guide PDF on kurtballou.com with a parts table and named pots."""
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

BASE = "https://www.godcityinstruments.com"
COLLECTION = f"{BASE}/collections/diy-pcbs/products.json?limit=250"
_ORIG = re.compile(r"(?:based on|inspired by|derived from|interpretation of|clone of|version of)[ ]+(?:an? |the )?(?:NPN interpretation of the |early experiment with (?:the |an? )?)?"
                   r"([A-Z][\w'&+/-]*(?:\.(?=[A-Z]))?(?:[ ]+(?:[A-Z0-9][\w'&+/-]*|Jr\.)){0,4})")
_BOSS = re.compile(r"^(DS-1|HM-2|MT-2|ODB-3|SD-1|OD-1|BD-2)\b")


@register
class GodCity(Adapter):
    vendor = "godcity"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(COLLECTION, ".json")
        prods = json.loads(raw).get("products", []) if raw else []
        # An older revision of a board (Baracus V1.5 beside V1.6) is not a second board.
        latest: dict[str, tuple[float, str]] = {}
        for pr in prods:
            m = re.match(r"^(.*?)\s+V(\d+(?:\.\d+)?)\s*$", pr["title"], re.I)
            if m:
                key, ver = m.group(1).lower(), float(m.group(2))
                if key not in latest or ver > latest[key][0]:
                    latest[key] = (ver, pr["handle"])
        for pr in prods:
            m = re.match(r"^(.*?)\s+V(\d+(?:\.\d+)?)\s*$", pr["title"], re.I)
            if m and latest.get(m.group(1).lower(), (0, ""))[1] != pr["handle"]:
                continue
            self.products[pr["handle"]] = pr
            yield pr["handle"]

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        body_html = pr.get("body_html") or ""
        links = [(u, clean_text(_html.unescape(re.sub(r"<[^>]+>", "", t)))) for u, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body_html, re.S)]
        docs = list(dict.fromkeys(u for u, t in links if re.search(r"\.pdf(?:\?|$)", u, re.I)))
        if not docs or re.search(r"pre-populated|3PDT UTILITY", pr["title"], re.I):
            return None  # utility boards and populated boards have no build guide
        title = _html.unescape(pr["title"]).strip()
        name = " ".join(w.capitalize() if (w.isupper() and w.isalpha() and len(w) > 3) else w for w in title.split())  # BARACUS -> Baracus, HM-1 stays
        name = re.sub(r"\bJr\b\.?", "Jr.", name)
        body = html_to_text(body_html)
        m = _ORIG.search(body)
        based_on = clean_text(m.group(1)) if m else ""
        based_on = re.sub(r"\s+(?:circuit|pedal|design|topology)s?$", "", based_on).strip(" ,.")
        if _BOSS.match(based_on):
            based_on = "Boss " + based_on
        if re.match(r"^(?:GCI|God City)\b", based_on):
            based_on = based_on.replace("GCI", "God City Instruments", 1)
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        c = Circuit(vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/products/{handle}", based_on=based_on,
                    description=body, price=price, currency="USD", in_stock=variant.get("available"), doc_url=docs[0],
                    enclosure=find_enclosure(body), image_url=(pr.get("images") or [{}])[0].get("src", "").split("?")[0])
        for u in docs[1:]:
            c.extra_docs[u.rsplit("/", 1)[-1].replace("%20", " ")[:50]] = u
        pdf = self.f.get_file(docs[0], ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            pages = pdf_text_pages(pdf)
            mv = re.search(r"\bV(\d+(?:\.\d+)*)\s+Build guide", pages[0] if pages else "", re.I)
            c.doc_version = mv.group(1) if mv else ""
            c.enclosure = c.enclosure or find_enclosure("\n".join(pages[:3]))
            res = process_document(pdf, self.vendor, handle)
            c.bom, c.schematic_local, c.schematic_page = res["bom"], res["schematic_local"], res["schematic_page"]
            if len(c.bom) < 8:
                c.bom = max(c.bom, ocr_bom(pdf, self.vendor, handle), key=len)
        c.category = classify(name, based_on, body[:300])
        if re.search(r"\b(?:passive|active)?\s*(?:\d-band |sweepable |mid-range )?EQ\b", body[:120], re.I) and c.category in ("Boost", "Other", "Utility"):
            c.category = "EQ / Filter"
        if re.search(r"amp-in-a-(?:pedal|box)", body[:200], re.I):
            c.category = "Preamp / Amp-in-a-box"
        pots = [r for r in c.bom if r.category == "POT"]
        named = [r.ref.title() for r in pots if re.fullmatch(r"[A-Za-z][A-Za-z /\-]{1,15}\d?", r.ref)]
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{2,15}", r.ref)]
        return c
