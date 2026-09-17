"""Bent Fishbowl Electronics adapter: a Wix blog of original and derivative
pedal schematics (CC BY-NC-SA). No board to buy; each post's first figure is
a clean KiCad-style schematic image, which is OCR'd with word positions to
recover designators and values."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_schematic_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://bentfishbowl.wixsite.com/electronics"
_NOT_PEDAL = re.compile(r"retrospective|cable|tester|tube amp|\bamp\b|amplifier|meazzi|fbt|power supply", re.I)


@register
class BentFishbowl(Adapter):
    vendor = "bentfishbowl"

    def list_targets(self) -> Iterable[str]:
        xml = self.f.get_text(f"{BASE}/blog-posts-sitemap.xml", ".xml") or ""
        for url in re.findall(r"<loc>(https://bentfishbowl\.wixsite\.com/electronics/post/[^<]+)</loc>", xml):
            yield url

    def parse(self, url: str) -> Circuit | None:
        html = self.f.get_text(url) or ""
        if not html:
            return None
        doc = HTMLParser(html)
        title_n = doc.css_first('[data-hook="post-title"]') or doc.css_first("h1")
        title = clean_text(title_n.text()) if title_n else ""
        art = doc.css_first('article[data-hook="post"]') or doc.css_first("article")
        body = html_to_text(art.html) if art else ""
        body = re.split(r"\n\s*Tags:\s*", body)[0]
        tags = sorted(set(re.findall(r'href="[^"]*/blog/tags/([^"/?]+)"', html)))
        cats = sorted(set(re.findall(r'href="[^"]*/blog/categories/([^"/?]+)"', html)))
        if _NOT_PEDAL.search(title) or (tags and "pedals" not in tags and "schematic" not in tags):
            return None
        figs = []
        for fig in doc.css("figure wow-image"):
            info = fig.attributes.get("data-image-info") or ""
            try:
                data = json.loads(_html.unescape(info)).get("imageData", {})
            except json.JSONDecodeError:
                continue
            if data.get("uri"):
                figs.append((data["uri"], int(data.get("width") or 0), int(data.get("height") or 0)))
        schem = next(((u, w, h) for u, w, h in figs if h and w / h < 2.6), figs[0] if figs else None)
        published = ""
        m = re.search(r'"datePublished":"([^"]+)"', html)
        if m:
            published = m.group(1)[:10]
        first_para = body.split("\n")[0] if body else ""
        m = re.search(r"(?:version of|based on|clone of|inspired by|re-?implementation of|take on|derived from)\s+(?:the |an? |my )?([A-Z][^.,;\n(]{3,60})", body)
        based_on = clean_text(m.group(1)).strip(" -") if m else ""
        based_on = re.sub(r"\s+(?:by|from|which|that|with|using)\b.*$", "", based_on)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        c = Circuit(
            vendor=self.vendor, slug=slug, name=title, url=url, based_on=based_on, description=body[:3000],
            category=classify(based_on, title, " ".join(tags), first_para[:300]),
            tags=[t for t in tags if t not in ("schematic", "pedals")] + [x.replace("-", " ") for x in cats],
            price=None, currency="USD", doc_url=url, doc_version=published, enclosure=find_enclosure(body),
        )
        if schem:
            uri, w, h = schem
            img_url = f"https://static.wixstatic.com/media/{uri}"
            c.image_url = img_url
            c.extra_docs["Schematic image (CC BY-NC-SA)"] = img_url
            img = self.f.get_file(img_url, ".png")
            if img:
                png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                png.parent.mkdir(parents=True, exist_ok=True)
                if not png.exists():
                    png.write_bytes(img.read_bytes())
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = 1
                c.bom = ocr_schematic_bom(png)
                pots = [r for r in c.bom if r.category == "POT"]
                if pots:
                    c.controls = [f"{len(pots)} knobs"]
        return c
