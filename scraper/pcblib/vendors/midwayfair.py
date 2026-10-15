"""Jon Patton (midwayfair) adapter: the boards he shares on OSH Park, ordered from the fab at OSH Park's
price for three. The profile lists five projects a page; each has a name, a one-line description, the
board size and price, and usually the Eagle board file, whose <element>s carry every part's value, so
the parts list is exact (eagle.py). The board files are cached locally and linked, not served.
His microphone and mic preamp boards are skipped: not guitar pedals."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..eagle import eagle_bom
from ..models import Circuit
from ..taxonomy import classify
from . import register
from .base import Adapter, clean_text

SITE = "https://oshpark.com"
PROFILE = SITE + "/profiles/midwayfair"
_NOT_PEDAL = re.compile(r"\bmic(?:rophone)?s?\b|preamp|control panel|condenser|capsule", re.I)
# token -> (name, original, subtitle, category or "" to classify). His own designs have no original: the vendor name and board name
# ('Jon Patton Hamlet Delay') are what other sources call them, so the clones list beside his board.
BOARDS = {
    "MBLU5JlE": ("Rust Bunny", "Sam Ash Fuzzstainer", "", ""),
    "ukDVIAMW": ("Orphan Fuzz", "Orpheum Fuzz", "", ""),
    "A7kxlzV2": ("Clipper Ship", "", "v2.5, with an input buffer", "Overdrive"),
    "TFSrpOSQ": ("Millennium II Bypass", "Millennium Bypass 2", "", ""),
}


@register
class Midwayfair(Adapter):
    vendor = "midwayfair"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.items: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page, last = 1, 1
        while page <= last and page < 50:
            html = self.f.get_text(PROFILE if page == 1 else f"{PROFILE}/page/{page}") or ""
            last = max([last] + [int(n) for n in re.findall(r"/profiles/midwayfair/page/(\d+)", html)])
            for tok, body in re.findall(r'<turbo-frame id="project_(\w+)">(.*?)</turbo-frame>', html, re.S):
                lines = [clean_text(_html.unescape(x)) for x in re.sub(r"<[^>]+>", "\n", body).split("\n")]
                lines = [x for x in lines if x]
                if "Total Price:" not in lines or "Top" not in lines:
                    continue
                i = lines.index("Total Price:")
                design = re.search(r'href="([^"]+/uploads/project/design/[^"]+)"', body)
                self.items[tok] = {
                    "title": lines[lines.index("Top") - 1], "price": lines[i + 1],
                    "description": lines[i + 2] if i + 2 < len(lines) and lines[i + 2] not in ("Top", "Actions") else "",
                    "size": next((x for x in lines if "layer board" in x), ""),
                    "design": _html.unescape(design.group(1)) if design else "",
                    "image": next(iter(re.findall(r'src="([^"]+/top_image/[^"]+)"', body)), "").replace("thumb_i.png", "large_i.png"),
                }
                yield tok
            page += 1

    def parse(self, tok: str) -> Circuit | None:
        it = self.items.get(tok)
        if not it or _NOT_PEDAL.search(f'{it["title"]} {it["description"]}'):
            return None
        name, based_on, subtitle, category = BOARDS.get(tok, (it["title"], "", "", ""))
        url = f"{SITE}/shared_projects/{tok}"
        price = re.search(r"[\d.]+", it["price"])
        size = re.search(r"of ([\d.]+ x [\d.]+) inches", it["size"])
        description = it["description"].rstrip(".") + "." if it["description"] else ""
        c = Circuit(vendor=self.vendor, slug=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), name=name,
                    subtitle=subtitle, url=url, based_on=based_on, description=description,
                    category=category or classify(f"{name} {based_on}", description), price=float(price.group()) if price else None,
                    currency="USD", in_stock=True, doc_url=url, image_url=it["image"],
                    tags=["OSH Park", "price for 3 boards"] + ([f'{size.group(1)} in'] if size else []))
        if it["design"]:
            c.extra_docs["Eagle board file"] = it["design"]
            path = self.f.get_file(it["design"], ".brd")
            if path:
                c.bom = eagle_bom(path.read_bytes())
                c.controls = [r.ref for r in c.bom if r.category == "POT"]
        return c
