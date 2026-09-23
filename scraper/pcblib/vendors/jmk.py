"""JMK PCBs adapter. WooCommerce store whose REST API is switched off, so the
catalog comes from the WordPress product sitemap and each product page's JSON-LD
(name, SKU, price, stock). Build docs are PDFs on the site with a multi-column
parts table (Resistors / Capacitors / Semiconductors / Potentiometers)."""
from __future__ import annotations

import json
import re
from typing import Iterable

from ..models import Circuit
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://jmkpcbs.com"
SITEMAP = f"{BASE}/wp-sitemap-posts-product-1.xml"

_CAT = {"delay": "Delay", "modulation": "Vibrato / Chorus", "dynamics": "Compressor", "fuzz": "Fuzz", "distortion": "Distortion",
        "overdrive": "Overdrive", "boost": "Boost", "utility": "Utility", "epic-bypass-looper": "Utility", "taptation": "Utility", "bass": "Bass"}
_PROPER = r"[A-Z][A-Za-z0-9’'\-]+(?: (?:of |the |and )?[A-Z0-9][A-Za-z0-9’'\-]*)*"
_ORIG = re.compile(r"(?:(?:slightly |near |modified )?(?:clone|rendition|version|copy|recreation) of (?:the |an? )?|"
                   r"based (?:on|upon|around) (?:the |an? )?)(?:classic |famous |original |old |venerable )*(" + _PROPER + r")")
_ORIG_CLONE = re.compile(r"is (?:essentially |basically |simply )?an? (" + _PROPER + r") clone\b")
# Originals the build notes name only obliquely ("a popular european builder's overdrive, the SS-2").
_BASED_ON = {
    "super-happy-overdrive": "Mad Professor Sweet Honey Overdrive", "steaming-kettle-overdrive": "Rockbox Boiling Point",
    "clean-drive": "Voodoo Lab Sparkle Drive", "moon-lander": "Lunar Deluxe (Fuzz Face)", "fuzz-muff": "EHX Muff Fuzz",
    "operational-muff": "EHX Op-Amp Big Muff", "flender-bender": "Fender Blender", "super-duper-fuzz": "Univox Super-Fuzz",
    "standard-fuzz": "Ibanez Standard Fuzz", "wakizashi-boost": "Keeley Katana", "beauty-booster": "Pink Booster",
    "happy-birthday-overdrive": "BJFe Honey Bee Overdrive", "mini-comp": "Valve Wizard Engineer's Thumb",
    "engineers-thumb-compressor": "Valve Wizard Engineer's Thumb", "soft-sustain-drive": "Cornish SS-2", "hamlet": "Jon Patton Hamlet Delay",
    "little-angel": "Frequency Central Little Angel", "companion-fuzz": "Shin-ei FY-2 Companion Fuzz", "scuba-muff": "EHX Big Muff",
    "si-fuzz": "Fuzz Face (silicon)", "expandora": "Bixonic Expandora", "big-bass-drive": "Darkglass Microtubes B3K",
    "level-up": "Ampeg Scrambler", "acdc-drive": "Xotic AC Booster / RC Booster",
    "classic-tremolo": "EA Tremolo", "5-knob-fuzz": "ZVex Fuzz Factory", "blue-warbler-2": "Jon Patton Blue Warbler",
    "super-phaser": "MXR Phase 90", "headphone-amplifier": "",
}
_CATEGORY = {"blue-warbler-2": "Tremolo", "panner": "Tremolo", "paralyzer": "Utility", "tiny-tester": "Utility",
             "level-up": "Octave / Pitch", "the-taptation": "Utility", "super-phaser": "Phaser", "flender-bender": "Fuzz",
             "little-angel": "Vibrato / Chorus", "mini-comp": "Compressor"}


@register
class JMK(Adapter):
    vendor = "jmk"

    def list_targets(self) -> Iterable[str]:
        xml = self.f.get_text(SITEMAP, ".xml") or ""
        for url in re.findall(r"<loc>(https://jmkpcbs\.com/product/[^<]+)</loc>", xml):
            yield url

    def parse(self, url: str) -> Circuit | None:
        page = self.f.get_text(url, ".html")
        if not page:
            return None
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        ld = None
        for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                ld = data
                break
        name = clean_text(ld["name"]) if ld else clean_text(re.sub(r"<[^>]+>", "", (re.search(r'class="product_title[^"]*">(.*?)</h1>', page, re.S) or [None, slug])[1]))
        i = page.find('id="tab-description"')
        i = page.find(">", i) + 1 if i > 0 else i  # past the tab's own attributes
        desc_html = page[i:page.find("</div>", page.find("Reviews", i))] if i > 0 else ""
        # Innermost anchors only: one page nests a dead localhost link around the real one.
        links = [(u, clean_text(t)) for u, t in re.findall(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', desc_html)]
        docs = [u for u, t in links if u.lower().endswith(".pdf") and u.startswith(BASE) and re.search(r"build doc", t, re.I)]
        if not docs or re.search(r"\bkit\b", name, re.I):
            return None  # kits, parts and pages without a build document
        body = html_to_text(re.sub(r"<a [^>]*>.*?</a>", "", desc_html, flags=re.S))
        body = clean_text(re.sub(r"^\s*Description\s*$", "", body, flags=re.M))
        body = re.sub(r"\s*Reviews\s+There are no reviews yet\.?\s*$", "", body)
        cats = sorted(set(re.findall(r"product_cat-([a-z0-9-]+)", page)))
        offer = (ld or {}).get("offers", [{}])
        offer = offer[0] if isinstance(offer, list) and offer else (offer if isinstance(offer, dict) else {})
        raw_price = offer.get("price") or offer.get("lowPrice") or ""
        price = float(raw_price) if re.match(r"^\d+(\.\d+)?$", str(raw_price)) else None
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url, description=body, price=price,
            currency=offer.get("priceCurrency", "USD"), sku=str((ld or {}).get("sku") or ""),
            in_stock=("InStock" in str(offer.get("availability", ""))) if offer else None,
            difficulty="Easy" if "beginner-friendly" in cats else "",
            doc_url=docs[0], enclosure=find_enclosure(body), image_url=str((ld or {}).get("image") or ""),
        )
        for u, t in links:
            if u in docs[1:]:
                c.extra_docs[f"Build doc ({u.rsplit('/', 1)[-1]})"] = u
            elif re.search(r"drill", t, re.I):
                c.extra_docs["Drill template"] = u
            elif u.lower().endswith(".pdf"):
                c.extra_docs[t or u.rsplit("/", 1)[-1]] = u
        best = None
        for u in docs:
            pdf = self.f.get_file(u, ".pdf")
            if not pdf or pdf.stat().st_size < 2000 or pdf.read_bytes()[:5] != b"%PDF-":
                continue
            res = process_document(pdf, self.vendor, f"{slug}-{docs.index(u)}" if len(docs) > 1 else slug)
            res["url"], res["text"] = u, "\n".join(pdf_text_pages(pdf))
            if best is None or len(res["bom"]) > len(best["bom"]):
                best = res
        if best:
            c.doc_url = best["url"]
            c.doc_local, c.bom, c.schematic_local, c.schematic_page, c.doc_version = \
                best["doc_local"], best["bom"], best["schematic_local"], best["schematic_page"], best["doc_version"]
            text = re.sub(r"[!ʼ]", "", best["text"])
            m = _ORIG_CLONE.search(text) or _ORIG.search(text)
            c.based_on = _BASED_ON[slug] if slug in _BASED_ON else (clean_text(m.group(1)) if m else "")
            if not c.enclosure:
                c.enclosure = find_enclosure(text)
            pots = [r for r in c.bom if r.category == "POT"]
            c.controls = [r.ref.title() if r.ref.isupper() else r.ref for r in pots]
        guess = classify(name, c.based_on)
        c.category = _CATEGORY.get(slug) or (guess if guess != "Other" else next((_CAT[k] for k in cats if k in _CAT), "Other"))
        c.tags = [k for k in cats if k not in _CAT and k != "beginner-friendly"]
        return c
