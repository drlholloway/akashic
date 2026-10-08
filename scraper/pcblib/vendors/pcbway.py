"""PCBWay shared-project adapter for one community member's catalogue of
guitar-pedal boards. The member page lists projects through a JSONP endpoint;
each project page carries a public schematic PNG (CC BY-SA). The member uploads no
BOM (a login only adds a PDF of the same drawing and a layout render), and the
drawings print values without designators, so the parts list is the schematic's
value labels counted ('×4 470k') with its named knobs. Fetched slowly: ten seconds
between any two requests to PCBWay's hosts."""
from __future__ import annotations

import json
import math
import re
from typing import Iterable

from selectolax.lexbor import LexborHTMLParser

from ..models import Circuit
from ..pdf import schematic_value_bom
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
# A schematic image is named '..._schematic.png' on most projects, 'schem.png' or 'schematic.png' on a few.
_SCHEM_NAME = re.compile(r"(?:^|[_\-\s])schem(?:atic)?\.(?:png|jpe?g|gif)$", re.I)
# Older projects upload their images unnamed; these were looked at and the schematic picked by hand.
# slug -> image URL
_SCHEMATIC: dict[str, str] = {
    "basic-audio-scarab-deluxe-fuzz": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/07/24/0435155368476.png",
    "bearfoot-sea-blue-eq": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/08/29/1722318278838.png",
    "dallas-fuzz-face": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/06/18/0247429255480.jpg",
    "eqd-crimson-drive": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/09/06/1833216060061.png",
    "eqd-crysalis-overdrive": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/06/22/0017594035716.jpg",
    "lovepedal-hermida-audio-zendrive": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/06/21/1208061166560.jpg",
    "marshall-jmp-cabsim": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/06/12/0134106354156.jpg",
    "maxon-od808-overdrive": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/21/02/10/0629191375325.png",
    "mxr-blue-box-octave-fuzz": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/21/05/08/2251064590356.png",
    "mxr-microamp": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/21/01/08/1055496267202.png",
    "proco-rat-distortion": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/11/07/0700535728662.png",
    "sky-river-distortion": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/10/02/1948339051160.png",
    "zvex-super-duper-smd": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/21/01/23/2059206313486.png",
    "zvex-super-hard-on": "https://pcbwayfile.s3-us-west-2.amazonaws.com/project/20/06/13/0827279720305.jpg",
}


class _PCBWayMember(Adapter):
    vendor = ""
    bmbno = ""

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.f.min_interval = max(self.f.min_interval, 10.0)
        self.f.one_clock = True
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
        doc = LexborHTMLParser(html)
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
        schem = _SCHEMATIC.get(c.slug) or next((li.attributes.get("data-url") or "" for li in doc.css("li.img-pics")
                                                 if _SCHEM_NAME.search(li.attributes.get("data-name") or "")), "")
        if schem:
            c.extra_docs["Schematic image (CC BY-SA)"] = schem
            ext = "." + schem.rsplit(".", 1)[-1].lower()
            img = self.f.get_file(schem, ext if ext in (".png", ".jpg", ".jpeg", ".gif") else ".png")
            if img:
                png = CACHE_DIR / self.vendor / f"{c.slug}-schematic.png"
                if not png.exists():
                    png.parent.mkdir(parents=True, exist_ok=True)
                    if img.suffix.lower() == ".png":
                        png.write_bytes(img.read_bytes())
                    else:
                        from PIL import Image
                        Image.open(img).convert("RGB").save(png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = 1
                c.bom = schematic_value_bom(png)
                c.controls = [r.ref for r in c.bom if r.category == "POT"]
        return c


for _vid, (_bmbno, _hint) in MEMBERS.items():
    cls = type(f"PCBWay_{_vid.replace('-', '_')}", (_PCBWayMember,), {"vendor": _vid, "bmbno": _bmbno})
    register(cls)
