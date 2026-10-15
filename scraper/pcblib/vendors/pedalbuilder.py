"""PedalBuilder (Naegele Audio) adapter: a builder on the PedalPCB forum who lays out PCBs for clones
and modded circuits and sells them by direct message, with no shop to scrape. Each circuit is a build
report thread; the parts come from the schematic in the post, read by eye (transcribed/pedalbuilder__*).

Two boards are free: PCBs PedalBuilder laid out for Chuck D. Bones' Boneyard Hoof and Hybrid Fuzz
Driver Deluxe, hosted with permission on the site owner's layouts wiki (not under its Creative Commons
license). Those are read from the wiki page: BOM tables, controls, the gerber and drill-template links."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable
from urllib.parse import quote

from ..models import Circuit
from ..taxonomy import find_enclosure
from . import register
from .base import Adapter, clean_text
from .cryptid import GITHUB, RAW, WIKI_RAW, _bom, _tables

FORUM = "https://forum.pedalpcb.com/threads/"
PROFILE = "https://forum.pedalpcb.com/members/pedalbuilder.487/"

# Build report threads: slug, thread path, name, original, category. PedalBuilder's own names where he
# gives one ('The Ocelot'); the original is the pedal the circuit clones or starts from.
THREADS = [
    ("harmonic-percolator", "harmonic-percolator-with-some-mods.22248", "Harmonic Percolator (with mods)", "Interfax Harmonic Percolator", "Fuzz"),
    ("tone-bender-mk-iv", "sola-sound-tone-bender-mk-iv.29468", "Tone Bender Mk. IV", "Sola Sound Tone Bender MkIV", "Fuzz"),
    ("ocelot", "the-ocelot-modified-univox-super-fuzz.22824", "The Ocelot", "Univox Super-Fuzz", "Fuzz"),
    ("yellow-hybrid-tone-bender", "yellow-hybrid-tone-bender.27472", "Yellow Hybrid Tone Bender", "Colorsound Yellow Hybrid Tone Bender", "Fuzz"),
    ("supa-pie", "supa-pie-colorsound-supa-tone-bender.27443", "Supa Pie", "Colorsound Supa Tone Bender", "Fuzz"),
    ("sungrazer", "sungrazer-high-gain-germanium-fuzz-monolith-oracle.27363", "Sungrazer", "Monolith Oracle", "Fuzz"),
    ("electric-talons", "electric-talons-baldwin-burns-buzzaround.26983", "Electric Talons", "Baldwin-Burns Buzzaround", "Fuzz"),
    ("trumpet-fuzz", "trumpet-fuzz-paul-trombetta-rotobone.27241", "Trumpet Fuzz", "Paul Trombetta Rotobone", "Fuzz"),
    ("hurts-percolators", "more-harmonic-percolators.27192", "Hurts Harmonic Percolators", "Latent Lemon Hurts", "Fuzz"),
    ("latent-lemon-hurts", "latent-lemon-hurts-modded-harmonic-percolator-w-octave-down-schematic.26954", "Latent Lemon Hurts (trace)", "Latent Lemon Hurts", "Fuzz"),
    ("fuzz-standard", "fuzz-standard-ibanez-standard-fuzz-clone.25190", "Fuzz Standard", "Ibanez Standard Fuzz", "Fuzz"),
    ("mechanic-fuzz", "the-mechanic-fuzz-from-chucks-boneyard.24706", "The Mechanic Fuzz", "Chuck D. Bones Mechanic Fuzz", "Fuzz"),
    ("event-horizon", "event-horizon-or-a-rotobone-puts-on-a-space-suit.20372", "Event Horizon", "Paul Trombetta Rotobone", "Fuzz"),
    ("tone-bender-mk-iii", "modded-tone-bender-mk-iii.22664", "Modded Tone Bender Mk. III", "Sola Sound Tone Bender MkIII", "Fuzz"),
    ("dizzy-tone", "elka-dizzy-tone-clone.22629", "Dizzy Tone", "Elka Dizzy Tone", "Fuzz"),
    ("sputnik", "spaceman-sputnik-ii-iii-clone.19274", "Sputnik II/III", "Spaceman Sputnik II", "Fuzz"),
]
# The free boards on the layouts wiki: slug -> (wiki page and repo folder, gerber file, thread, name, original, category).
FREE = {
    "boneyard-hoof": ("Boneyard-Hoof", "Boneyard-Hoof-PedalBuilder-GERBER.zip",
                      "the-week-on-the-breadboard-eqd-hoof-boneyard-mod.21830", "Boneyard Hoof", "EarthQuaker Devices Hoof", "Fuzz"),
    "hybrid-fuzz-driver-deluxe": ("Hybrid-Fuzz-Driver-Deluxe", "Gerber_Boneyard-Hybrid-Fuzz-Driver_PCB_Boneyard-Hybrid-Fuzz-Driver_2025-03-26.zip",
                                  "this-week-on-the-breadboard-the-hybrid-fuzz-driver-deluxe.25456", "Hybrid Fuzz Driver Deluxe", "Skreddy Hybrid Fuzz Driver", "Fuzz"),
}


def _first_post(page: str, author: str = "PedalBuilder") -> str:
    m = re.search(rf'<article class="message[^"]*"[^>]*data-author="{author}".*?<div class="bbWrapper">(.*?)</article>', page, re.S)
    if not m:
        return ""
    body = re.sub(r"<(?:br|/p|/div|/li)[^>]*>", "\n", m.group(1))
    return "\n".join(clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", line))) for line in body.splitlines()).strip()


@register
class PedalBuilder(Adapter):
    vendor = "pedalbuilder"

    def list_targets(self) -> Iterable[str]:
        yield from FREE
        yield from (t[0] for t in THREADS)

    def parse(self, slug: str) -> Circuit | None:
        if slug in FREE:
            return self._free(slug)
        _, path, name, based_on, category = next(t for t in THREADS if t[0] == slug)
        url = FORUM + path + "/"
        page = self.f.get_text(url, ".html") or ""
        text = _first_post(page)
        if not text:
            return None
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=url, based_on=based_on, category=category,
                    description=re.sub(r"\s*\n\s*", " ", text)[:3000], doc_url=url, price=None, currency="USD",
                    enclosure=find_enclosure(text), tags=["PedalPCB forum", "PCB by message"])
        # A Chuck D. Bones circuit (the Mechanic Fuzz): the post points to his thread for the schematic, and the
        # page links that thread rather than the schematic.
        post = re.search(r'data-author="PedalBuilder".*?<div class="bbWrapper">(.*?)</article>', page, re.S)
        for href, label in re.findall(r'href="(https://forum\.pedalpcb\.com/threads/[^"#]+)[^"]*"[^>]*>([^<]{1,60})<', post.group(1) if post else ""):
            if "schematic" in label.lower():
                c.extra_docs["Chuck D. Bones' thread (PedalPCB forum)"] = _html.unescape(href)
                break
        return c

    def _free(self, slug: str) -> Circuit | None:
        page, gerber, thread, name, based_on, category = FREE[slug]
        md = self.f.get_text(f"{WIKI_RAW}/{page}.md", ".md") or ""
        if not md:
            return None
        wiki = f"{GITHUB}/wiki/{page}"
        intro = re.search(r"## Introduction\s*\n(.+?)(?:\n### |\n## )", md, re.S)
        description = clean_text(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", re.sub(r"\*\*", "", intro.group(1) if intro else "")))
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=wiki, based_on=based_on, category=category,
                    description=description[:3000], doc_url=wiki, price=None, currency="USD",
                    tags=["free gerbers", "circuit by Chuck D. Bones"], image_url=f"{RAW}/{quote(page)}/{quote(page.lower())}-pcb-front.png")
        c.extra_docs["PCB gerbers"] = f"{GITHUB}/raw/main/{quote(page)}/{quote(gerber)}"
        c.extra_docs["Chuck D. Bones' thread (PedalPCB forum)"] = FORUM + thread + "/"
        drill = re.search(r"\((https://drill\.taydakits\.com/[^)\s]+)\)", md)
        if drill:
            c.extra_docs["Tayda drill template"] = drill.group(1)
        c.bom = _bom(md)
        c.controls = [r[0].strip() for h, rows in _tables(md) if rows and rows[0][:1] == ["Control"]
                      for r in rows[1:] if r and r[0].strip() and "trim" not in " ".join(r[1:2]).lower()]
        return c
