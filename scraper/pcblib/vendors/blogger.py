"""Shared base for the layout blogs on Blogger (Tagboard Effects, Dirtbox Layouts, the Effects
Layouts blog). Nothing is sold: each post is one board layout drawn in DIYLC, a stripboard
(vero), tag strip, turret or perfboard build of a pedal, with the values printed on the parts.
The post feed gives title, labels (maker, effect type, Verified / Unverified) and body; the
layout image gives the board size and the cut and link counts printed under the board."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..layouts import controls, legend_rows
from ..models import Circuit
from ..taxonomy import classify, find_enclosure
from .base import Adapter, clean_text, html_to_text

_PAGE = 150  # Blogger serves at most 150 full posts per request
_IMG_HEADERS = {"Accept": "image/png,image/*"}  # without it the image host answers with a viewer page

_CATEGORY = {"fuzz": "Fuzz", "overdrive": "Overdrive", "distortion": "Distortion", "boost": "Boost", "booster": "Boost",
             "delay": "Delay", "echo": "Delay", "reverb": "Reverb", "tremolo": "Tremolo", "phaser": "Phaser", "flanger": "Flanger",
             "chorus": "Vibrato / Chorus", "vibrato": "Vibrato / Chorus", "vibe": "Vibrato / Chorus", "compressor": "Compressor",
             "octave": "Octave / Pitch", "eq": "EQ / Filter", "filter": "EQ / Filter", "wah": "Wah / Envelope", "preamp": "Preamp / Amp-in-a-box",
             "pre-amp": "Preamp / Amp-in-a-box", "pre amp": "Preamp / Amp-in-a-box", "amp emulation": "Preamp / Amp-in-a-box",
             "amp emulator": "Preamp / Amp-in-a-box", "amp sim": "Preamp / Amp-in-a-box", "utility": "Utility", "buffer": "Utility",
             "synth": "Ring Mod / Synth", "ringmod": "Ring Mod / Synth", "ring modulator": "Ring Mod / Synth", "noise gate": "Noise Gate",
             "modulation": "Vibrato / Chorus", "modulator": "Vibrato / Chorus", "envelope filter": "Wah / Envelope", "bass": "Bass",
             "treble boost": "Boost", "bass boost": "Boost", "equaliser": "EQ / Filter", "equalizer": "EQ / Filter",
             "limiter": "Compressor"}
_BUILD_LABEL = {"vero": "vero", "stripboard": "vero", "tagboard": "tagboard", "tag board": "tagboard", "tag strip": "tagboard",
                "turret": "turret", "turret board": "turret", "eyelet": "turret", "perf": "perfboard", "perfboard": "perfboard",
                "point to point": "p2p", "p2p": "p2p", "pcb": "pcb", "pcb layout": "pcb"}
_STATUS = {"verified": True, "unverified": False, "unverifed": False}
_DIFFICULTY = {"easy": "Easy", "medium": "Medium", "difficult": "Difficult", "hard": "Difficult"}
_BOX = re.compile(r"^(?:1590[a-z]{1,2}\d?|125b|1790ns)$", re.I)
_SIZE = re.compile(r"\b(\d{1,2})\s?[x×]\s?(\d{1,2})\b")
_CUTS = re.compile(r"\b(\d{1,3})\s+cuts?\b", re.I)
_LINKS = re.compile(r"\b(\d{1,3})\s+(?:links?|jumpers?)\b", re.I)
# The drawing: Blogger's image host, by the link around it (full size) or, unlinked, the image itself.
# Newer uploads have no file extension ('.../img/a/AVv...=s1356').
_IMAGE = re.compile(r'(?:href|src)="(https://blogger\.googleusercontent\.com/img/[^"]+|https?://\d\.bp\.blogspot\.com/[^"]+\.(?:png|jpe?g|gif))"', re.I)


def _post_slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")


class BloggerLayouts(Adapter):
    blog = ""           # '<name>.blogspot.com'
    build = "vero"      # what the blog draws unless a label says otherwise
    skip_labels: frozenset[str] = frozenset()  # posts that are not a layout: news, tools, off-board wiring
    not_makers: frozenset[str] = frozenset()   # labels that are neither a maker nor an effect type
    not_layouts: frozenset[str] = frozenset()  # posts with labels and pictures that are still no circuit, by post slug
    # A post that holds several circuits, one drawing each: post slug -> (name, category) per picture, in the
    # post's order. Each becomes its own circuit ('<post>#2' as its target, the name in its slug).
    split: dict[str, list[tuple[str, str]]] = {}

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self._entries: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        start = 1
        while True:
            url = f"https://{self.blog}/feeds/posts/default?alt=json&max-results={_PAGE}&start-index={start}"
            raw = self.f.get_text(url, ".json")
            entries = (json.loads(raw).get("feed", {}).get("entry") or []) if raw else []
            for e in entries:
                link = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")
                if link:
                    self._entries[link] = e
                    parts = self.split.get(_post_slug(link))
                    yield from ([f"{link}#{i + 1}" for i in range(len(parts))] if parts else [link])
            if len(entries) < _PAGE:
                return
            start += _PAGE

    def labels(self, e: dict) -> list[str]:
        return [c["term"].strip() for c in e.get("category", []) if c.get("term", "").strip()]

    def parse(self, url: str) -> Circuit | None:
        url, _, nth = url.partition("#")
        e = self._entries.get(url)
        if e is None:
            return None
        one = self.split[_post_slug(url)][int(nth) - 1] if nth else None  # one circuit of a post that holds several
        title = one[0] if one else clean_text(_html.unescape(e["title"]["$t"]))
        labels = self.labels(e)
        low = {l.lower() for l in labels}
        if not title or not labels or low & self.skip_labels or _post_slug(url) in self.not_layouts:
            return None  # every layout carries labels; a post without any is an announcement
        content = e.get("content", {}).get("$t", "")
        # The oldest posts link '/s1600-h/', a viewer page; the picture itself is at '/s1600/'.
        found = list(dict.fromkeys(_html.unescape(u).replace("/s1600-h/", "/s1600/") for u in _IMAGE.findall(content)))
        full = {u.replace("/s1600/", "//") for u in found if "/s1600/" in u}
        found = [u for u in found if "/s1600/" in u or re.sub(r"/s\d{2,4}/(?=[^/]+$)", "//", u) not in full]  # '/s200/', '/s640/' of a drawing kept at full size
        # A linked drawing appears twice, full size and as its thumbnail ('=w400-h244', '/w578-h640/'): keep the full size.
        images = [u for u in found if not re.search(r"(?:=|/)w\d+-h\d+", u)]
        if not images:  # an unlinked drawing is embedded as a thumbnail; the same address serves it at full size
            images = [re.sub(r"/w\d+-h\d+(?:-[a-z]+)*/(?=[^/]+$)", "/s1600/", re.sub(r"=w\d+-h\d+(?:-[a-z]+)*$", "=s1600", u)) for u in found]
        if one:
            images = images[int(nth) - 1:int(nth)]
        if not images:
            return None  # a post without a drawing is news, not a layout
        body = html_to_text(content)
        build = next((_BUILD_LABEL[l] for l in sorted(low) if l in _BUILD_LABEL), self.build)
        status = next((_STATUS[l] for l in low if l in _STATUS), None)
        cats = [_CATEGORY[l.lower()] for l in labels if l.lower() in _CATEGORY]
        cats.sort(key=lambda c: c == "Bass")  # 'Bass' beside 'Fuzz' is a bass fuzz: the effect is the category
        if one:  # the post's labels and text cover all of its circuits
            cats, labels, body = ([one[1]] if one[1] else []), [l for l in labels if l.lower() in _STATUS or l.lower() in _BUILD_LABEL], f"One of {len(self.split[_post_slug(url)])} layouts in the post '{clean_text(_html.unescape(e['title']['$t']))}'."
        makers = [l for l in labels if l.lower() not in _CATEGORY and l.lower() not in _BUILD_LABEL
                  and l.lower() not in _STATUS and l.lower() not in _DIFFICULTY and not _BOX.match(l)
                  and l.lower() not in self.not_makers]
        layout = {"build": build, "images": images[:6]}
        if status is not None:
            layout["verified"] = status
        self.read_image(images[0], layout)
        text = layout.pop("text", "")
        # Tagboard Effects files its turret boards under 'Tagboard'; the drawing's own title says which it is.
        if build == "tagboard" and re.search(r"turret", text + " " + images[0], re.I):
            layout["build"] = "turret"
        # What the post links: the schematic or build document the layout was drawn from, a forum thread.
        docs: dict[str, str] = {}
        for href, inner in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', content, re.S | re.I):
            host = href.split("/")[2].lower()
            label = clean_text(re.sub(r"<[^>]+>", "", _html.unescape(inner)))
            if "<img" in inner.lower() or not label or host.endswith(("blogspot.com", "googleusercontent.com", "youtube.com", "youtu.be", "blogger.com")):
                continue
            if re.fullmatch(r"here|this|link|click here", label, re.I) or len(label) > 40:
                label = "Schematic" if re.search(r"schem", body, re.I) and not docs else f"Linked in the post ({host.removeprefix('www.')})"
            docs.setdefault(label[:1].upper() + label[1:], _html.unescape(href))
            if len(docs) == 4:
                break
        slug = _post_slug(url) + ("-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") if one else "")
        year = url.split(self.blog + "/", 1)[-1][:7].replace("/", "-")
        return Circuit(
            vendor=self.vendor, slug=f"{year}-{slug}", name=title, url=url, based_on=self.based_on(title, makers),
            description=body[:3000], category=cats[0] if cats else classify(title, " ".join(labels), body[:300]),
            tags=[l for l in labels if l.lower() not in _STATUS and l.lower() not in _BUILD_LABEL
                  and l.lower() not in _DIFFICULTY and not _BOX.match(l)],
            difficulty=next((_DIFFICULTY[l] for l in sorted(low) if l in _DIFFICULTY), ""),
            price=None, currency="USD", doc_url=url, doc_version=e.get("published", {}).get("$t", "")[:10],
            extra_docs=docs, enclosure=find_enclosure(body) or next((l.upper() for l in labels if _BOX.match(l)), ""), image_url="", layout=layout,
            controls=controls(text), bom=legend_rows(text),
        )

    def based_on(self, title: str, makers: list[str]) -> str:
        """The post title is the original pedal, maker first ('T-Rex Mudhoney V1.1'), on all three blogs."""
        return title

    def read_image(self, url: str, layout: dict) -> None:
        """Board size and the cut and link counts, printed under the board on the drawing. The image
        is cached, never exported; the values on the parts are too small and turned to OCR reliably."""
        from .. import vision
        m = re.search(r"\.(png|jpe?g|gif)$", url, re.I)
        ext = "." + m.group(1).lower() if m else ".png"  # no extension: Blogger serves these as PNG or JPEG; the reader goes by content
        path = self.f.get_file(url, ext, _IMG_HEADERS)
        if not path:
            return
        text = vision.text(path) if vision.available() else ""
        layout["text"] = text
        m = _CUTS.search(text)
        if m:
            layout["cuts"] = int(m.group(1))
            size = _SIZE.search(text[max(0, m.start() - 40):m.start() + 60]) or _SIZE.search(text)
        else:
            size = _SIZE.search(text)
        if size and layout["build"] in ("vero", "perfboard"):
            layout["board"] = f"{size.group(1)}x{size.group(2)}"
        m = _LINKS.search(text)
        if m:
            layout["links"] = int(m.group(1))
