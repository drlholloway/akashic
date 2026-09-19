"""Zero G IOD adapter. A Big Cartel store whose boards are all sold out; its
documentation exists only as product images (a BOM photo, a drill guide and a
schematic PNG). Everything is copied into data/archive/zerogiod so the
schematics survive the store."""
from __future__ import annotations

import html as _html
import json
import re
import shutil
from typing import Iterable

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_image_bom, ocr_schematic_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.zerogiod.com"
ARCHIVE = DATA_DIR / "archive" / "zerogiod"


@register
class ZeroGIOD(Adapter):
    vendor = "zerogiod"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"{BASE}/products.json", ".json") or "[]"
        for pr in json.loads(raw):
            if not any(c["name"].lower().startswith("diy") for c in pr.get("categories", [])):
                continue
            self.products[pr["permalink"]] = pr
            yield pr["permalink"]

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        title = _html.unescape(pr["name"])
        parts = re.split(r"\s+-\s+", title, maxsplit=1)
        name = re.sub(r"\s+(?:PCB(?: and Faceplate)?|and Faceplate)\s*$", "", parts[0], flags=re.I).strip()
        based_on = clean_text(parts[1]) if len(parts) > 1 else ""
        body = html_to_text(pr.get("description") or "")
        if not based_on:
            m = re.search(r"(?:clone of|inspired by|for building|based on)\s+(?:the |an? )?([A-Z][^.\n]{2,60})", body)
            based_on = clean_text(m.group(1)) if m else ""
        price = pr.get("default_price")
        c = Circuit(
            vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/product/{handle}", based_on=based_on,
            description=body, tags=["store closed"],
            # Classify without the packing list ("1 3PDT bypass board" would read as a utility board).
            category=classify(based_on, name, re.sub(r"(?im)^.*(?:you'll receive|bypass (?:pcb )?board|3pdt|faceplate).*$", "", body)[:300]),
            price=float(price) if price is not None else None, currency="USD", in_stock=False,
            doc_url=f"{BASE}/product/{handle}", enclosure=find_enclosure(body),
        )
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        dest_dir = ARCHIVE / handle
        dest_dir.mkdir(exist_ok=True)
        for img in pr.get("images", []):
            url = (img.get("url") or "").split("?")[0]
            if not url:
                continue
            fname = url.rsplit("/", 1)[-1]
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpg"
            blob = self.f.get_file(url, f".{ext}")
            if not blob:
                continue
            dest = dest_dir / fname
            if not dest.exists():
                shutil.copyfile(blob, dest)
            kind = ("bom" if re.search(r"bom", fname, re.I) else "schematic" if re.search(r"schem", fname, re.I)
                    else "drill" if re.search(r"drill", fname, re.I) else "photo")
            if kind == "schematic":
                png = CACHE_DIR / self.vendor / f"{handle}-schematic.png"
                png.parent.mkdir(parents=True, exist_ok=True)
                if not png.exists():
                    from PIL import Image
                    im = Image.open(blob)
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    im.save(png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = 1
                c.extra_docs["Schematic image"] = url
                if not c.bom:
                    c.bom = ocr_schematic_bom(png)
            elif kind == "bom":
                c.extra_docs["Parts list image"] = url
                rows = ocr_image_bom(blob, self.vendor, handle)
                if len(rows) > len(c.bom):
                    c.bom = rows
            elif kind == "drill":
                c.extra_docs["Drill guide image"] = url
            elif not c.image_url:
                c.image_url = url
        pots = [r for r in c.bom if r.category == "POT"]
        if pots:
            named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
            c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
