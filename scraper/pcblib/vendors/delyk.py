"""delyk PCBs adapter: a WooCommerce shop (USD). Product pages carry no document links;
the build documents ('<Name>-BOM.pdf', a P/N / Value / Notes table per section) sit in the
WordPress media library and are matched to products by name."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.delykpcb.com"
_SKIP = re.compile(r"3PDT|Relay Bypass|ISP Helper|SMD to THD|Custom Payment|TAPLFO|Rotary Switch|MPQ3904|\bKit\b", re.I)
_ALIAS = {"the-tremolo-jumped-over-the-moon": "tremolojump", "up-down-daddy": "udd", "rdist-equals-dist-plus-250": "250",
          "absolute-revolt": "revolt", "countenance-alliance-si": "alliancesi", "el-rey-de-la-gloria-azul-ii": "elrey",
          "el-rey-de-la-gloria-azul": "elrey", "ensi-genxydes-hybrid-distortion": "ensi", "cherry-pie-tap-tempo-tremolo": "cherrypie"}


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@register
class Delyk(Adapter):
    vendor = "delyk"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}
        self.docs: dict[str, str] = {}  # key -> pdf url

    def list_targets(self) -> Iterable[str]:
        for page in range(1, 6):
            raw = self.f.get_text(f"{BASE}/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={page}", ".json")
            try:
                media = json.loads(raw) if raw else []
            except ValueError:
                media = []
            if not isinstance(media, list) or not media:
                break
            for m in media:
                fname = m["source_url"].rsplit("/", 1)[-1]
                self.docs[_key(re.sub(r"[-_ ]?(?:BOM|Drill[-_ ]Template)\.pdf$", "", fname, flags=re.I)) + ("|drill" if re.search(r"drill", fname, re.I) else "")] = m["source_url"]
        for page in (1, 2):
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            prods = json.loads(raw) if raw else []
            if not prods:
                break
            for p in prods:
                cats = {c["slug"] for c in p.get("categories", [])}
                name = _html.unescape(p["name"])
                if cats <= {"parts", "clearance", "swag"} or _SKIP.search(name):
                    continue
                self.products[p["slug"]] = p
                yield p["slug"]

    def _doc(self, slug: str, name: str, drill: bool = False) -> str:
        keys = [_ALIAS.get(re.sub(r"-pcb$", "", slug), ""), _key(re.sub(r"\bPCB\b", "", name)), _key(slug.replace("-pcb", ""))]
        suffix = "|drill" if drill else ""
        for k in keys:
            if k and k + suffix in self.docs:
                return self.docs[k + suffix]
        for k in keys:
            if k:
                hit = next((u for dk, u in self.docs.items() if dk.endswith(suffix) and (dk.split("|")[0] and (k.startswith(dk.split("|")[0]) or dk.split("|")[0].startswith(k))) and (drill or "|" not in dk)), "")
                if hit:
                    return hit
        return ""

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        title = clean_text(_html.unescape(p["name"]))
        name = re.sub(r"\s+PCB\s*$", "", title).strip("“” ")
        attrs = {a["name"].lower(): ", ".join(t["name"] for t in a.get("terms", [])) for a in p.get("attributes", [])}
        based_on = attrs.get("based on", "")
        based_on = "" if re.search(r"original|n/a|none", based_on, re.I) else re.sub(r"TubeScreamer", "Tube Screamer", based_on)
        prices = p.get("prices") or {}
        doc = self._doc(slug, name)
        c = Circuit(vendor=self.vendor, slug=slug.replace("-pcb", ""), name=name, url=p["permalink"], based_on=based_on,
                    description=html_to_text(p.get("short_description") or p.get("description") or "")[:700],
                    price=int(prices["price"]) / 10 ** int(prices.get("currency_minor_unit", 2)) if prices.get("price") else None,
                    currency=prices.get("currency_code", "USD"), in_stock=p.get("is_in_stock"), doc_url=doc or p["permalink"],
                    image_url=(p.get("images") or [{}])[0].get("src", ""), difficulty=attrs.get("difficulty", ""),
                    enclosure=find_enclosure(attrs.get("smallest enclosure", "")), sku=p.get("sku", ""))
        drill = self._doc(slug, name, drill=True)
        if drill:
            c.extra_docs["Drill template"] = drill
        if doc:
            pdf = self.f.get_file(doc, ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                res = process_document(pdf, self.vendor, c.slug)
                c.bom, c.schematic_local, c.schematic_page, c.doc_version = res["bom"], res["schematic_local"], res["schematic_page"], res["doc_version"]
                trims = {m.group(1).upper() for m in re.finditer(r"(?m)^\s*([A-Z][A-Z0-9]{1,11})\s+\S+\s+Trim ?pot", "\n".join(pages))}
                c.bom = [r for r in c.bom if r.ref.upper() not in ("OMIT", "NONE", "N/A")]
                for r in c.bom:
                    if r.category == "POT" and (r.ref.upper() in trims or re.search(r"trim", r.notes, re.I)):
                        r.category = "TRIM"
                intro = re.search(r"Introduction\s*\n(.{20,400}?)\n\s*\n", "\n".join(pages[:2]), re.S)
                if intro and len(c.description) < 40:
                    c.description = clean_text(intro.group(1))
        cats = {c_["slug"] for c_ in p.get("categories", [])}
        c.category = "Utility" if "utility-boards" in cats else classify(name, based_on, c.description[:300])
        pots = [r for r in c.bom if r.category == "POT" and r.ref.upper() != "TRIM"]
        named = list(dict.fromkeys(r.ref.title() if r.ref.isupper() else r.ref for r in pots if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref)))
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += [r.ref.title() for r in c.bom if r.category == "SW" and re.fullmatch(r"[A-Za-z][A-Za-z /-]{2,15}", r.ref)]
        return c
