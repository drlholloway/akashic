"""EfektPol: turret board layouts drawn in DIY Layout Creator, shared on the site owner's layouts wiki
(drlholloway/guitar-effects-layouts) under CC BY-NC-SA 4.0 like the owner's own layouts, with credit to EfektPol. Each layout has a
wiki page with the Controls table and the BOM as Markdown tables, read like the Cryptid source; the main
repository holds the .diy file and a render of the drawing, which may be shown here."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote

from ..models import Circuit
from . import register
from .base import Adapter, clean_text
from .cryptid import GITHUB, RAW, WIKI_RAW, _bom, _tables

FOLDER = "EfektPol-Turret-Layouts"
# slug -> (wiki page, file stem in the repo folder, name, original, category)
LAYOUTS = {
    "dod-250": ("EfektPol-DOD-250", "efektpol-dod-250", "DOD 250 Overdrive Preamp", "DOD 250", "Overdrive"),
    "dunlop-gcb-95": ("EfektPol-Dunlop-GCB-95", "efektpol-dunlop-gcb-95", "Dunlop GCB-95 Cry Baby", "Dunlop GCB-95 Cry Baby", "Filter"),
    "green-russian-big-muff": ("EfektPol-Green-Russian-Big-Muff", "efektpol-green-russian-big-muff", "Green Russian Big Muff",
                               "EHX Green Russian Big Muff", "Fuzz"),
    "fulltone-ocd": ("EfektPol-Fulltone-OCD", "efektpol-fulltone-ocd", "Fulltone OCD", "Fulltone OCD", "Overdrive"),
    "mxr-distortion-plus": ("EfektPol-MXR-Distortion-Plus", "efektpol-mxr-distortion-plus", "MXR Distortion+", "MXR Distortion+", "Distortion"),
    "proco-rat": ("EfektPol-ProCo-Rat", "efektpol-proco-rat", "ProCo Rat", "ProCo Rat", "Distortion"),
    "univox-super-fuzz": ("EfektPol-Univox-Super-Fuzz", "efektpol-univox-super-fuzz", "Univox Super-Fuzz", "Univox Super-Fuzz", "Fuzz"),
}


@register
class EfektPol(Adapter):
    vendor = "efektpol"

    def list_targets(self) -> Iterable[str]:
        yield from LAYOUTS

    def parse(self, slug: str) -> Circuit | None:
        page, stem, name, based_on, category = LAYOUTS[slug]
        md = self.f.get_text(f"{WIKI_RAW}/{page}.md", ".md") or ""
        if not md:
            return None
        wiki = f"{GITHUB}/wiki/{page}"
        intro = re.search(r"## Introduction\s*\n(.+?)(?:\n### |\n## )", md, re.S)
        description = clean_text(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", re.sub(r"\*\*", "", intro.group(1) if intro else "")))
        image = f"{RAW}/{quote(FOLDER)}/{stem}-layout.png"
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=wiki, based_on=based_on, category=category,
                    description=description[:3000], doc_url=wiki, price=None, currency="USD", in_stock=None,
                    tags=["turret board", "DIY Layout Creator", "CC BY-NC-SA 4.0"], image_url=image)
        c.layout = {"build": "turret", "images": [image]}
        c.extra_docs["DIY Layout Creator file"] = f"{GITHUB}/raw/main/{quote(FOLDER)}/{stem}.diy"
        c.bom = _bom(md)
        c.controls = [r[0].strip() for h, rows in _tables(md) if rows and rows[0][:1] == ["Control"]
                      for r in rows[1:] if r and r[0].strip()]
        return c
