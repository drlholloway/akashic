"""Revolution Deux adapter: a UK builder's Blogger blog (2008-2017) of boutique and vintage pedal
schematics, most traced by the freestompboxes.org community, many with a vero layout beside them. No
board is sold; the post is the source. A post can hold several circuits (the Twosome post has the Fix'd
Fuzz and the Musket), so the posts were read by eye once: revolutiondeux.json lists the circuits in each
post (name, original, the schematic and layout pictures, controls), and transcribed/revolutiondeux__*
holds their parts, with the corrections the author gives for the schematics he shares applied to the
rows and listed as fixes. The feed is read on every scrape so a post that goes away is marked delisted;
a new post is printed so it can be read."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..models import Circuit
from ..taxonomy import find_enclosure
from . import register
from .base import Adapter

BLOG = "https://revolutiondeux.blogspot.com"
_PAGE = 150  # Blogger serves at most 150 posts per request
_DATA = Path(__file__).with_suffix(".json")


def _slug(c: dict) -> str:
    return c["post"] + (f"-{c['key']}" if c["key"] else "")


@register
class RevolutionDeux(Adapter):
    vendor = "revolutiondeux"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.circuits = {_slug(c): c for c in json.loads(_DATA.read_text())["circuits"]}
        self.dates: dict[str, str] = {}

    def list_targets(self) -> Iterable[str]:
        posts: dict[str, str] = {}  # post slug ('2012-07-blackout-effectors-mantra-overdrive') -> url
        start = 1
        while True:
            raw = self.f.get_text(f"{BLOG}/feeds/posts/summary?alt=json&max-results={_PAGE}&start-index={start}", ".json")
            entries = (json.loads(raw).get("feed", {}).get("entry") or []) if raw else []
            for e in entries:
                url = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")
                if url:
                    slug = url.split(".com/", 1)[1].removesuffix(".html").replace("/", "-")
                    posts[slug] = url
                    self.dates[slug] = e.get("published", {}).get("$t", "")[:10]
            if len(entries) < _PAGE:
                break
            start += _PAGE
        read = {c["post"] for c in self.circuits.values()} | set(json.loads(_DATA.read_text()).get("skipped", {}))
        for slug in sorted(set(posts) - read):
            print(f"  revolutiondeux: new post not read yet: {posts[slug]}")
        yield from (s for s, c in self.circuits.items() if c["post"] in posts)

    def parse(self, slug: str) -> Circuit | None:
        d = self.circuits.get(slug)
        if not d:
            return None
        url = d["url"]
        text = d["description"] + ("\n\n" + " ".join(d["notes"]) if d.get("notes") else "")
        c = Circuit(vendor=self.vendor, slug=slug, name=d["name"], url=url, based_on=d["original"],
                    category=d["category"], description=text, doc_url=url, price=None, currency="USD",
                    doc_version=self.dates.get(d["post"], ""), controls=list(d.get("controls", [])),
                    enclosure=d.get("enclosure") or find_enclosure(text), tags=["freestompboxes.org trace"] if d.get("fsb") else [])
        if d.get("schematic"):
            c.image_url = d["schematic"]
            c.extra_docs["Schematic image"] = d["schematic"]
        also = {"Vero layout": "vero", "Perfboard layout": "perfboard", "Turret layout": "turret", "Tagboard layout": "tagboard"}
        for label, link in {**d.get("images", {}), **d.get("links", {})}.items():
            if label not in also:
                c.extra_docs.setdefault(label, link)
        # A layout the post gives beside the schematic: a second way to build it, with its own button.
        lays = [{"build": b, "url": d["images"][label]} for label, b in also.items() if label in d.get("images", {})]
        if lays:
            c.layout = {"also": lays}
        return c  # parts: transcribed/revolutiondeux__<slug>.json, applied when the circuit is stored
