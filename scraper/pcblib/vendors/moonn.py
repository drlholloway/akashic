"""Moonn Electronics adapter. Big Cartel store; each product description links
its build document PDF on Dropbox. Docs are OpenOffice exports with a text
"Qty / Value / Parts" bill of materials and a schematic image."""
from __future__ import annotations

import json
import re
from typing import Iterable

from ..models import Circuit
from ..pdf import process_document, pdf_text_pages
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://moonnelectronics.bigcartel.com"
_SKIP_CATS = {"Bundles", "Services"}
_CAT = {"Fuzz": "Fuzz", "Distortion": "Distortion", "Overdrive": "Overdrive", "Boost": "Boost",
        "Modulation": "Vibrato / Chorus", "Preamp": "Preamp / Amp-in-a-box", "Delay": "Delay",
        "Reverb": "Reverb", "Bitcrusher": "Ring Mod / Synth", "Synthesizer": "Ring Mod / Synth",
        "Tools": "Utility", "Noisy stuff": "Fuzz", "Other": ""}
_CAT_ORDER = ["Delay", "Reverb", "Modulation", "Bitcrusher", "Synthesizer", "Preamp", "Fuzz",
              "Overdrive", "Distortion", "Boost", "Tools", "Noisy stuff", "Other"]


_GENERIC = re.compile(r"^(this|that|the|a|an|any|some|famous|my|your|it|of)\b|pedal\.?$|^anything", re.I)


def _based_on(text: str) -> str:
    m = re.search(r"clone of (?:the |an? )?(.+?)(?=\s+(?:wich|which|with|and have|and also|but|so |that|because|or |if )\b|[.!?\n]|,|$)", text, re.I)
    if not m:
        return ""
    s = clean_text(m.group(1))
    s = re.sub(r"\s+(with|by using|using) this .*$", "", s, flags=re.I)
    if len(s) < 4 or _GENERIC.match(s) or not re.search(r"[A-Z]", s):
        return ""
    return s


def _dropbox_direct(url: str) -> str:
    url = re.sub(r"([?&])dl=0", r"\1dl=1", url)
    if "dl=" not in url:
        url += ("&" if "?" in url else "?") + "dl=1"
    return url


@register
class Moonn(Adapter):
    vendor = "moonn"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/products.json", ".json") or "[]"
        for pr in json.loads(raw):
            cats = {c["name"] for c in pr.get("categories", [])}
            if cats & _SKIP_CATS:
                continue
            self.products[pr["permalink"]] = pr
            yield pr["permalink"]

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        desc_html = pr.get("description") or ""
        pdfs = [u for u in re.findall(r'href="(https?://[^"]+)"', desc_html)
                if re.search(r"dropbox\.com.*\.pdf", u, re.I)]
        if not pdfs:
            return None
        body = html_to_text(desc_html)
        based_on = _based_on(body)
        cats = [c["name"] for c in pr.get("categories", [])]
        tags = [c for c in cats if c in ("Bass Friendly", "Moonn Electronics 'Original'", "Fuzzhead FX", "Noisy stuff")]
        category = ""
        for key in _CAT_ORDER:
            if key in cats and _CAT.get(key):
                category = _CAT[key]
                break
        if not category:
            category = classify(based_on, pr["name"], body[:300])
        price = pr.get("default_price")
        c = Circuit(
            vendor=self.vendor, slug=handle, name=clean_text(pr["name"]), url=f"{BASE}/product/{handle}",
            based_on=based_on, description=re.sub(r"\s*Build Docs?\s*$", "", body).strip(),
            category=category, effect_type=", ".join(x for x in cats if x not in tags), tags=tags,
            price=float(price) if price is not None else None, currency="EUR",
            in_stock=(pr.get("status") == "active"), doc_url=pdfs[0],
            image_url=(pr.get("images") or [{}])[0].get("url", "").split("?")[0],
        )
        for u in re.findall(r'href="(https?://[^"]+)"', desc_html):
            if u not in pdfs and "moonnelectronics" not in u and "instagram" not in u:
                label = "Parts kit at Musikding" if "musikding" in u else u.split("/")[2]
                c.extra_docs.setdefault(label, u)
        pdf = self.f.get_file(_dropbox_direct(c.doc_url), ".pdf")
        if pdf and pdf.stat().st_size > 2000 and pdf.read_bytes()[:5] == b"%PDF-":
            c.__dict__.update(process_document(pdf, self.vendor, handle))
            pages = pdf_text_pages(pdf)
            # The doc's own "Use me to build a clone of the X" line is cleaner than the shop copy.
            head = " ".join(ln.strip() for ln in (pages[0] if pages else "").splitlines()[:6])
            head = re.split(r"\bHi\b|Thank you", head)[0]
            doc_based = _based_on(head)
            if doc_based:
                c.based_on = doc_based
            c.enclosure = find_enclosure(body, *pages[:2])
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z\-/]+", r.ref) for r in pots)
                c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
