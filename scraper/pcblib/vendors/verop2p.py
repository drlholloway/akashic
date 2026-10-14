"""Vero P2P adapter (Guitar Related Ramblings, vero-p2p.blogspot.com): stripboard, point-to-point,
tag board and turret layouts of vintage and boutique fuzzes and drives, labelled by how they are
built (VERO, VERO 0.15", POINT TO POINT, TAG BOARD). The blog also posts schematics, amp work,
datasheets and value tables; only the posts with a layout label are circuits. Titles are
'MAKER: Pedal, Point to Point Layout'. See blogger.py."""
from __future__ import annotations

import re

from . import register
from .blogger import BloggerLayouts

# The labels that say how a post's layout is built, in the order the primary build is chosen.
_BUILDS = {"vero": "vero", 'vero 0.15"': "vero", "tag board": "tagboard", "tag strip": "tagboard",
           "turret board": "turret", "point to point": "p2p"}
_ORDER = ("vero", "tagboard", "turret", "p2p")
_NOT_PEDAL = {"valve amp", "se valve amp", "amp", "solid state amp"}  # amplifiers, not pedals
# What the title says about the layout rather than the pedal: ', Point to Point Layout', '(tagboard layout)', ' - Modded Layout'.
_BUILD_WORDS = r'(?:compact\s+)?(?:0\.15["”]\s*)?(?:point[- ]to[- ]point|vero|tag ?board|turret(?: board)?)'
_LAYOUT_NOTE = re.compile(
    rf",?\s*\(?{_BUILD_WORDS}(?:\s+(?:and|&)\s+{_BUILD_WORDS})?\s+layouts?\)?|,\s*0\.15[\"”](?:\s*vero)?(?=\s*\(|$)"
    r"|\s*\(old post\)|\s+-\s+modded layout|\s+layout$", re.I)
_SMALL = {"x", "v", "and", "of", "the", "by"}
_NO_MAKER = {"UNKNOWN", "POWER UTILITY"}


@register
class VeroP2P(BloggerLayouts):
    vendor = "verop2p"
    blog = "vero-p2p.blogspot.com"
    build = "vero"
    not_layouts = frozenset({
        "getting-started-building-diy-guitar",   # a guide to reading vero layouts
        "off-board-cornish-buffered-bypass",      # off-board wiring, no circuit
    })

    def parse(self, url: str):
        e = self._entries.get(url.partition("#")[0])
        if e is None:
            return None
        low = {l.lower() for l in self.labels(e)}
        builds = sorted({_BUILDS[l] for l in low if l in _BUILDS}, key=_ORDER.index)
        if not builds or low & _NOT_PEDAL:
            return None  # a schematic, a datasheet, a value table or an amplifier
        c = super().parse(url)
        if c is None:
            return None
        c.layout["build"] = builds[0]
        if len(builds) > 1:  # one post with both drawings ('Point to Point and Vero Layouts')
            c.layout["also"] = [{"build": b, "url": c.url} for b in builds[1:]]
        c.name = c.based_on = self._name(c.name, self.labels(e))
        c.tags = [t for t in c.tags if t.lower() not in _BUILDS]
        return c

    @staticmethod
    def _name(title: str, labels: list[str]) -> str:
        """'PETE CORNISH: TB-83 Treble Booster, Point to Point Layout' -> 'Pete Cornish TB-83 Treble Booster'.
        The maker is spelled as the blog's label for it; without one, capitalized word by word with short
        acronyms (MXR, RCA, D*A*M) kept."""
        title = re.sub(r"\s+", " ", _LAYOUT_NOTE.sub("", title)).strip(" ,-")
        m = re.match(r"([^:]{2,40}):\s+(.+)", title)  # not the '25:17' in 'Ezekiel 25:17'
        if not m:
            return title
        maker, rest = m.group(1).strip(), m.group(2).strip()
        if maker.upper() in _NO_MAKER:
            return rest
        spelled = {l.lower(): l for l in labels}

        def word(w: str) -> str:
            if w.lower() in spelled:
                return spelled[w.lower()]
            if w.lower() in _SMALL:
                return w.lower()
            return w if len(w) <= 3 or not w.isalpha() or w != w.upper() else w.capitalize()

        maker = spelled.get(maker.strip().lower()) or " ".join(
            "-".join(word(p) for p in w.split("-")) for w in maker.split())
        if rest.lower().startswith(maker.lower() + " "):  # 'SUNN: Sunn Buzz'
            return rest
        return f"{maker} {rest}".strip()
