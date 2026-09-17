"""PCBWay shared-project adapter for one community member's catalogue of
guitar-pedal boards. The member page lists projects through a JSONP endpoint;
each project page carries a public schematic PNG (CC BY-SA) but the BOM and
gerbers need a PCBWay login, so no parts list is indexed."""
from __future__ import annotations

import json
import math
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..taxonomy import classify
from . import register
from .base import Adapter, clean_text, html_to_text

MEMBERS = {
    # vendor id -> (bmbno, display hint)
    "pcbway-gtu": ("19C5FC6C-66B1-46", "Glory to Ukraine"),
}
LIST = "https://member.pcbway.com/Project/GetProject_ShareProjectList?callback=cb&bmbno={bmbno}&type=&page={page}"
PROJECT = "https://www.pcbway.com/project/shareproject/{file}.html"


class _PCBWayMember(Adapter):
    vendor = ""
    bmbno = ""

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.items: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page, total = 1, None
        while total is None or (page - 1) * 12 < total:
            raw = self.f.get_text(LIST.format(bmbno=self.bmbno, page=page), ".js") or ""
            m = re.search(r"^\s*cb\((.*)\)\s*;?\s*$", raw, re.S)
            if not m:
                break
            data = json.loads(m.group(1))
            total = int(data.get("TotalCount") or 0)
            for it in data.get("DataList", []):
                if it.get("Status") not in (None, 2) or it.get("IsStop"):
                    continue
                self.items[it["FileName"]] = it
                yield it["FileName"]
            page += 1
            if page > 200:
                break

    def parse(self, file_name: str) -> Circuit | None:
        it = self.items.get(file_name)
        if not it:
            return None
        url = PROJECT.format(file=file_name)
        html = self.f.get_text(url) or ""
        doc = HTMLParser(html)
        title = clean_text(it.get("Title") or (doc.css_first("h1.project-title").text() if doc.css_first("h1.project-title") else file_name))
        m = re.match(r"^(.+?)\s+-\s+(.+)$", title)
        # Titles are "<Brand> - <Pedal>": the pedal is the board's name, brand + pedal the original.
        name = clean_text(m.group(2)) if m else title
        based_on = f"{clean_text(m.group(1))} {clean_text(m.group(2))}" if m else ""
        brand = clean_text(m.group(1)) if m else ""
        desc_node = doc.css_first("div.ql-editor")
        description = html_to_text(desc_node.html) if desc_node else clean_text(it.get("Note_Check") or "")
        if description.strip() == title:
            description = ""
        tags = [t.get("Tag") for t in it.get("ProjectTags", []) if t.get("Tag")]
        published = ""
        pm = doc.css_first("div.project-published span")
        if pm:
            published = clean_text(pm.text())
        c = Circuit(
            vendor=self.vendor, slug=re.sub(r"[^a-z0-9]+", "-", file_name.lower()).strip("-"), name=name, url=url,
            based_on=based_on, description=description,
            category=classify(name, description[:300]), tags=([brand] if brand else []) + [t for t in tags if t.lower() not in ("audio", "diy", "guitar")],
            price=None, currency="USD", in_stock=True, doc_url=url,
            image_url=(it.get("Pics") or "").replace("m.png", ".png"), doc_version=published,
        )
        schem = next((li.attributes.get("data-url") or "" for li in doc.css("li.img-pics")
                      if re.search(r"_schematic\.(png|jpe?g)$", li.attributes.get("data-name") or "", re.I)), "")
        if schem:
            c.extra_docs["Schematic image (CC BY-SA)"] = schem
            img = self.f.get_file(schem, ".png")
            if img:
                png = CACHE_DIR / self.vendor / f"{c.slug}-schematic.png"
                if not png.exists():
                    png.parent.mkdir(parents=True, exist_ok=True)
                    png.write_bytes(img.read_bytes())
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = 1
        return c


for _vid, (_bmbno, _hint) in MEMBERS.items():
    cls = type(f"PCBWay_{_vid.replace('-', '_')}", (_PCBWayMember,), {"vendor": _vid, "bmbno": _bmbno})
    register(cls)
