"""Experimentalists Anonymous DIY archive adapter: a plain file index of traced
schematics (GIF/JPG/PNG/PDF) in ~24 category folders. One entry per file; no
board to buy. Values are read off the drawing by positional OCR where legible."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable
from urllib.parse import quote

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_schematic_bom, render_page, schematic_bom
from ..taxonomy import classify
from . import register
from .base import Adapter, clean_text

BASE = "https://www.experimentalistsanonymous.com/diy/"
INDEX = BASE + "index.php?dir=Schematics"
_BRANDS = re.compile(r"^(boss|dod|mxr|ehx|electro[- ]?harmonix|ibanez|maestro|proco|pro co|danelectro|arion|fender|vox|marshall|roland|yamaha|pearl|guyatone|colorsound|sola sound|univox|shin[- ]?ei|jen|ross|dallas|way huge|z\.?vex|zvex|fulltone|keeley|klon|lovetone|tech 21|digitech|morley|dunlop|ampeg|peavey|mu-?tron|musitronics|sovtek|tycobrahe|mosrite|gibson|ace tone|aria|korg|kay|dunlop|crybaby|cry baby|frantone|lovepedal|catalinbread|earthquaker|eqd|walrus|bjfe|bjf|mad professor|xotic|analogman|hermida|menatone|barber|voodoo lab|emma|carl martin|t-?rex|line 6|chandler|prescription|rocktron|electra|hohner|elka|jordan|foxx|systech|seamoon|craig anderton|anderton|coron|multivox|washburn|aria|aria pro|pearl|nobels|behringer|tone ?bender|big muff|fuzz face|tube screamer|rat\b|rangemaster|octavia|uni-?vibe|small stone|phase 90|blues driver|dyna comp|orange squeezer)\b", re.I)
_SKIP_DIRS = {"MIDI", "OOP Japanese Electronics Book", "Power Supplies and Other Useful Stuff", "Miscellaneous"}


@register
class ExpAnon(Adapter):
    vendor = "expanon"

    def list_targets(self) -> Iterable[str]:
        idx = self.f.get_text(INDEX) or ""
        for d in re.findall(r'href="(index\.php\?dir=Schematics/[^"]+)"', idx):
            d = _html.unescape(d)
            folder = d.split("/")[-1]
            if folder in _SKIP_DIRS:
                continue
            page = self.f.get_text(BASE + d.replace(" ", "%20")) or ""
            for href, title in re.findall(r'href="([^"]+)"[^>]*>([^<]*)<', page):
                href = _html.unescape(href)
                if href.startswith("index.php") or href == "style.css":
                    continue
                if not re.search(r"\.(gif|jpe?g|png|bmp|pdf)$", href, re.I):
                    continue
                yield f"{folder}\t{href}\t{clean_text(_html.unescape(title))}"

    def parse(self, target: str) -> Circuit | None:
        folder, href, title = target.split("\t", 2)
        file_url = BASE + quote(href)
        cat_url = BASE + "index.php?dir=" + quote(f"Schematics/{folder}")
        ext = href.rsplit(".", 1)[-1].lower()
        slug = re.sub(r"[^a-z0-9]+", "-", f"{folder} {title}".lower()).strip("-")[:80]
        name = title or href.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        based_on = name if _BRANDS.search(name) else ""
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=file_url, based_on=based_on,
            category=classify(name, folder), effect_type=folder, tags=[folder],
            price=None, currency="USD", doc_url=cat_url, image_url=file_url if ext != "pdf" else "",
        )
        blob = self.f.get_file(file_url, f".{ext}")
        if not blob:
            return c
        png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        try:
            if ext == "pdf":
                if blob.read_bytes()[:5] != b"%PDF-":
                    return c
                rows = schematic_bom(blob, 1)
                if not png.exists():
                    render_page(blob, 1, png, dpi=200)
                if len(rows) < 3:
                    rows = ocr_schematic_bom(png)
            else:
                if not png.exists():
                    from PIL import Image
                    Image.MAX_IMAGE_PIXELS = None
                    im = Image.open(blob)
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    im.save(png)
                from PIL import Image as _I
                width = _I.open(png).width
                rows = ocr_schematic_bom(png, scale=1 if width >= 2500 else 2)
        except Exception:  # noqa: BLE001 - corrupt or exotic image
            return c
        c.schematic_local = str(png.relative_to(DATA_DIR))
        c.schematic_page = 1
        c.bom = rows
        pots = [r for r in rows if r.category == "POT"]
        if pots:
            c.controls = [f"{len(pots)} knobs"]
        return c
