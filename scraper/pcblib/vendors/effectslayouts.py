"""Effects Layouts adapter. WooCommerce Store API catalog; every product links a
build-doc PDF on the site (DESCRIPTION, SCHEMATIC, two-column BOM with named
pots under "Electromechanical", SHOPPING LIST, LAYOUT, DRILL TEMPLATE)."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable
from urllib.parse import unquote

from ..models import Circuit
from ..paths import DATA_DIR
from ..pdf import ocr_bom, pdf_text_pages, process_document
from ..taxonomy import classify_within, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://effectslayouts.com"
API = f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={{page}}"

_CAT = {"Distortion": "Distortion", "Overdrive": "Overdrive", "Fuzz": "Fuzz", "Boost": "Boost", "Tremolo": "Tremolo",
        "Delay": "Delay", "Reverb": "Reverb", "Chorus": "Vibrato / Chorus", "Vibrato": "Vibrato / Chorus", "Phaser": "Phaser",
        "Flanger": "Flanger", "EQ": "EQ / Filter", "Octave": "Octave / Pitch", "Preamp": "Preamp / Amp-in-a-box", "Utility": "Utility"}
_NAME = {"intercontinental": "The Intercontinental", "cossack": "Козак (Cossack)", "skeleklone2": "Skeleklone Mk.II"}
# Originals the description names only obliquely, or several at once.
_BASED_ON = {
    "ea-trem": "EA Tremolo", "illithid": "Fuzz Face into Big Muff", "schematic-fuzz": "Fuzz Face", "hybrender": "Sola Sound Tone Bender MKII",
    "long-tom": "Caroline Wave Cannon", "timbo-slice": "J. Rockett Archer / Timmy", "duo-vibe": "CultureJam Duo-Vibe (Wobbletron)",
    "chaos-bolt": "EHX Big Muff", "king-of-the-morning": "Marshall Bluesbreaker", "horde-howler": "Ibanez TS808", "widogast-fuzz": "EHX Big Muff",
    "kentauride": "Ibanez TS-10 & Klon Centaur", "grizzled-grime": "Fulltone OCD", "lightland": "Greer Lightspeed & Southland",
    "sasquatch2": "Green Ringer + Big Muff", "intercontinental": "EHX Op-Amp Big Muff", "hot-bod": "DOD FX91", "earthbender": "EQD Black Ash",
    "red-clay-overdrive": "Ibanez Tube Screamer", "skeleklone2": "Klon Centaur", "microbuffer": "Klon buffer", "darkmantle": "EQD Tentacle / Green Ringer",
    "drivestortion": "MXR Distortion+ / DOD 250", "triangulus": "EHX Big Muff", "beauregard": "Dallas Rangemaster / EQD Bows",
    "crempog": "Crowther Hotcake", "crankyspeaker": "Electra Distortion", "ache-pedal": "EQD Life Pedal", "pepperbox": "ProCo RAT",
    "one_knobber": "", "tape-delay": "", "777": "Basic Audio Lucky Number", "sunndering": "", "undercut": "Mad Professor Evolution Orange",
    "corsair": "EHX Freedom Amp preamp", "spotted-dick": "Crowther Prunes & Custard", "six-shooter": "Lovepedal Super Six",
    "melody-malfunction": "Death By Audio Soundwave Breakdown 2", "discretionary": "EQD White Light", "cloak-dagger": "Chase Tone Secret Preamp",
    "black_tan": "Ross Distortion", "great-vengeance": "D*A*M Ezekiel 25:17", "menhir": "Mountainking Megalith", "octomos": "JPTR FX Silver Machine",
    "frizz": "EWS Fuzzy Drive", "lilliput": "SS/BS Mini", "range-bender": "Colorsound Hybrid Tone Bender", "lead-foot": "Rostex Turbo Metal",
}
_ORIG = re.compile(r"(?i:based (?:on|around)|inspired by|take on|clone of|version of|emulator of|developed from)\s+"
                   r"(?:the |an? |my own take on )?(?:classic |now discontinued |discontinued |often copied and tweaked |newer |big box |somewhat rare |hyped |never released |old )*"
                   r"([A-Z0-9’'][^.,;()]{2,60}?)(?=\s+(?:and|with|but|which|that|in|from|pushing|the big|itself)\b|[.,;(]|$)")


@register
class EffectsLayouts(Adapter):
    vendor = "effectslayouts"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page = 1
        while True:
            raw = self.f.get_text(API.format(page=page), ".json")
            items = json.loads(raw) if raw else []
            if not items:
                break
            for pr in items:
                self.products[pr["slug"]] = pr
                yield pr["slug"]
            if len(items) < 100:
                break
            page += 1

    def parse(self, slug: str) -> Circuit | None:
        pr = self.products.get(slug)
        if not pr:
            return None
        if re.search(r"\bSO\d+ CONVERTER\b", pr["name"], re.I):
            return None  # SMD-to-DIP adapters
        cats = [c["name"] for c in pr.get("categories", [])]
        desc_html = (pr.get("description") or "") + "\n" + (pr.get("short_description") or "")
        body = html_to_text(desc_html)
        body = clean_text(re.sub(r"^\s*Build Doc\s*$", "", body, flags=re.M))
        pdfs = [u for u in re.findall(r'href="([^"]+\.pdf(?:\?dl=\d)?)"', desc_html, re.I) if not re.search(r"drill", u, re.I)]
        if not pdfs:
            # Some products link a "build doc" page on the site instead; that page links the PDF (single-quoted href).
            for page_url in re.findall(r'href="(https://effectslayouts\.com/[^"]*build-doc[^"]*)"', desc_html, re.I):
                page = self.f.get_text(page_url) or ""
                found = re.findall(r"""href=['"]([^'"]+\.pdf)['"]""", page, re.I)
                if found:
                    pdfs = [found[0]]
                    break
        drills = [u for u in re.findall(r'href="([^"]+)"', desc_html) if re.search(r"drill", u, re.I)]
        name = _NAME.get(slug) or " ".join(w.title() if len(w) > 2 and not re.search(r"\d", w) else w
                                           for w in _html.unescape(pr["name"]).split())
        name = re.sub(r"\bMk\.ii\b", "Mk.II", name)
        if slug in _BASED_ON:
            based_on = _BASED_ON[slug]
        else:
            m = _ORIG.search(re.sub(r"\b(Co|J|Inc)\.", r"\1", body))
            based_on = clean_text(m.group(1)).replace(" Co ", " Co. ") if m else ""
        allowed = {_CAT[c] for c in cats if c in _CAT}
        category = classify_within(allowed, name, based_on, default=next((_CAT[c] for c in cats if c in _CAT), "Other")) if allowed else "Other"
        if "Bass" in cats and category == "Other":
            category = "Bass"
        prices = pr.get("prices") or {}
        minor = int(prices.get("currency_minor_unit", 2))
        price = int(prices["price"]) / (10 ** minor) if str(prices.get("price", "")).isdigit() else None
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=pr.get("permalink") or f"{BASE}/product/{slug}/",
            based_on=based_on, description=body, category=category,
            tags=[c for c in cats if c in ("DIY Classics", "2-in-1s", "Bass")], price=price,
            currency=prices.get("currency_code", "USD"), sku=pr.get("sku") or "", in_stock=pr.get("is_in_stock"),
            doc_url=pdfs[0] if pdfs else "", enclosure=find_enclosure(body),
            image_url=((pr.get("images") or [{}])[0].get("src") or "").split("?")[0],
        )
        for u in pdfs[1:]:
            c.extra_docs[re.sub(r"[-_]+", " ", unquote(u.rsplit("/", 1)[-1].split("?")[0]).rsplit(".", 1)[0])] = u
        for u in drills:
            c.extra_docs["Drill template"] = u
        if not c.doc_url:
            return c
        pdf = self.f.get_file(c.doc_url.replace("dl=0", "dl=1"), ".pdf")
        if pdf and pdf.stat().st_size > 2000 and pdf.read_bytes()[:5] == b"%PDF-":
            res = process_document(pdf, self.vendor, slug)
            c.doc_local = res["doc_local"]
            c.bom, c.schematic_local, c.schematic_page, c.doc_version = res["bom"], res["schematic_local"], res["schematic_page"], res["doc_version"]
            text = "\n".join(pdf_text_pages(pdf))
            if len(c.bom) < 8 and "dropbox.com" in c.doc_url:
                ocr = ocr_bom(pdf, self.vendor, slug, max_pages=4, thorough=True)  # old blog-era project PDFs have unreadable font encodings
                if len(ocr) > len(c.bom):
                    c.bom = ocr
            m = re.search(r"DRILL TEMPLATE \(([0-9A-Z]+)\)", text)
            if m:
                c.enclosure = m.group(1)
            elif not c.enclosure:
                c.enclosure = find_enclosure(text)
            if re.search(r"^\s*Part\s+(\d{4}|original) spec\s+", text, re.M):
                specs = re.findall(r"^\s*Part\s+(.+?)\s{2,}(.+?)\s*$", text, re.M)
                if specs:
                    c.description += f"\n\nThe parts list follows the {specs[0][0]} column of the build document; the doc also gives {specs[0][1]} values."
            first = next((r.variant for r in c.bom if r.variant), "")
            pots = list({r.ref: r for r in c.bom if r.category == "POT" and r.variant in ("", first)}.values())
            if pots and all(r.ref.startswith("×") for r in pots):
                n = sum(int(r.ref[1:]) for r in pots)
                c.controls = [f"{n} knobs" if n > 1 else "1 knob"]
            else:
                c.controls = [r.ref.title() if r.ref.isupper() else r.ref for r in pots]
        return c
