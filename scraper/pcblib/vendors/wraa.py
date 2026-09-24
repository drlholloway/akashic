"""WRAA Labs adapter: a Big Cartel shop of lo-fi digital pedals whose DIY kits and one bare
PCB link a build guide on a Wix blog; the guide's parts list is inline text ('R1 = 1k',
'"DRY" - A100k') and the blog page carries it in its JSON-LD description."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://wraa.bigcartel.com"
_PART = re.compile(r'("?[A-Z]{1,4}\d{0,3}"?|"[A-Z][A-Z0-9 ]{1,12}")\s*[=\-–]\s*([^=\-–"]+?)(?=\s*"?[A-Z]{1,4}\d{0,3}"?\s*[=\-–]|\s*"[A-Z][A-Z0-9 ]{1,12}"\s*[=\-–]|$)')
_CATEGORY = {"retroflect": "Other", "glitchwave567": "Other", "katzenjammer": "Delay", "inkcap": "Vibrato / Chorus"}


def parse_inline_list(text: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()
    for ref, value in _PART.findall(text):
        ref = ref.strip('"')
        value = re.sub(r"\s*\(.*?\)", "", value).strip(" .,;")
        if not ref or ref.upper() in seen or re.fullmatch(r"none!?|omit", value, re.I):
            continue
        if re.fullmatch(r"[A-Z]{1,4}\d{1,3}", ref) or ref == "CLR":
            cat, name = "", ref
        elif re.match(r"^[ABCW]\d+[kKM]?", value):
            cat, name = "POT", ref.title()
        else:
            continue
        nr = normalize_row(BomRow(ref=name, value=value.split()[0] if cat == "POT" else value, part_type="Potentiometer" if cat == "POT" else "",
                                  notes="dual gang" if "dual" in value.lower() else "", category=cat))
        if cat or is_plausible(nr):
            seen.add(ref.upper())
            rows.append(nr)
    return rows


@register
class WRAA(Adapter):
    vendor = "wraa"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/products.json", ".json")
        for p in (json.loads(raw) if raw else []):
            if any(c["name"] == "Pedal Kit" for c in p.get("categories", [])) or re.search(r"\bPCB\b", p["name"]):
                self.products[p["permalink"]] = p
                yield p["permalink"]

    def parse(self, slug: str) -> Circuit | None:
        p = self.products.get(slug)
        if not p:
            return None
        desc = html_to_text(p.get("description") or "")
        guides = re.findall(r"https?://wraalabs\.wixsite\.com/pedals/single-post/[\w-]+", desc)
        name = re.sub(r"\s*-\s*.*$|\s*\bDIY\b.*$|\s*\bPCB\b.*$", "", clean_text(_html.unescape(p["name"]))).strip()
        sub = re.search(r"-\s*(.+?)(?:\s+DIY kit|\s+PCB|$)", clean_text(_html.unescape(p["name"])))
        description = clean_text(re.sub(r"https?://\S+", "", desc))
        c = Circuit(vendor=self.vendor, slug=slug, name=name, subtitle=clean_text(sub.group(1)) if sub else "", url=f"{BASE}/product/{slug}",
                    description=description, price=float(p["price"]) if p.get("price") is not None else None, currency="GBP",
                    in_stock=p.get("status") == "active", doc_url=guides[0] if guides else f"{BASE}/product/{slug}",
                    image_url=((p.get("images") or [{}])[0].get("url") or "").split("?")[0], enclosure=find_enclosure(desc))
        if guides:
            page = self.f.get_text(guides[0], ".html") or ""
            m = re.search(r'"description":"((?:[^"\\]|\\.)*)"', page)
            if m:
                text = _html.unescape(m.group(1).encode().decode("unicode_escape", errors="ignore"))
                c.bom = parse_inline_list(text)
        key = next((k for k in _CATEGORY if k in slug), "")
        c.category = _CATEGORY.get(key) or classify(name, "", description)
        c.controls = [r.ref for r in c.bom if r.category == "POT"]
        return c
