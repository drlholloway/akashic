"""PCB Guitar Mania adapter. WooCommerce (Store API). Each physical board's
description links a self-hosted "Building Docs" PDF whose first page is a
header table (Based on / Enclosure / Effect type / Build difficulty) and whose
BOM is a multi-column Part/Value table. Regional duplicates ("... - America",
the "australia" category) and "Eagle and Gerber files" variants collapse onto
the physical board."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..pdf import process_document, pdf_text_pages
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://pcbguitarmania.com"
_CAT = {"fuzz": "Fuzz", "overdrives": "Overdrive", "distortion": "Distortion", "high-gain": "Distortion",
        "boost": "Boost", "chorus-vibrato": "Vibrato / Chorus", "compressor": "Compressor", "delay": "Delay",
        "eq-cabsim": "EQ / Filter", "filter": "EQ / Filter", "envelope-filer": "Wah / Envelope", "flanger": "Flanger",
        "fv-1": "DSP", "noise-gate": "Noise Gate", "octave-pitch": "Octave / Pitch", "phaser": "Phaser",
        "pre-amp": "Preamp / Amp-in-a-box", "reverb": "Reverb", "ring-modulator": "Ring Mod / Synth",
        "tremolo": "Tremolo", "bass": "Bass", "synth-bitcrusher-fuzzes": "Ring Mod / Synth"}
_CAT_ORDER = ["delay", "reverb", "chorus-vibrato", "flanger", "phaser", "tremolo", "octave-pitch", "ring-modulator",
              "synth-bitcrusher-fuzzes", "compressor", "noise-gate", "envelope-filer", "eq-cabsim", "filter", "fv-1",
              "fuzz", "distortion", "high-gain", "overdrives", "pre-amp", "boost", "bass"]
_REGION = re.compile(r"\s*[–-]\s*(america|australia|europe|usa|uk)\s*$", re.I)
_FILES = re.compile(r"eagle|gerber", re.I)


def _base(name: str) -> str:
    n = _html.unescape(name)
    n = re.sub(r"\s*[–-]\s*eagle and gerber files?\s*$", "", n, flags=re.I)
    n = _REGION.sub("", n)
    return re.sub(r"[^a-z0-9]+", " ", n.lower()).strip()


def _header_field(page: str, label: str) -> str:
    """First-page header: labels on one line, values on the next, column-aligned."""
    lines = page.splitlines()
    for i, ln in enumerate(lines):
        j = ln.find(label)
        if j < 0:
            continue
        for nxt in lines[i + 1:i + 4]:
            if nxt.strip():
                seg = nxt[j:]
                seg = re.split(r"\s{3,}", seg.strip())[0] if seg.strip() else ""
                return clean_text(seg)
    return ""


@register
class PCBGuitarMania(Adapter):
    vendor = "pcbguitarmania"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}
        self.docs_by_base: dict[str, list[str]] = {}

    def list_targets(self) -> Iterable[str]:
        page, chosen = 1, {}
        while True:
            raw = self.f.get_text(f"{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}", ".json")
            items = json.loads(raw) if raw else []
            if not items:
                break
            for pr in items:
                name = _html.unescape(pr["name"])
                slugs = {c["slug"] for c in pr.get("categories", [])}
                desc = pr.get("description") or ""
                pdfs = re.findall(r'href="(https://pcbguitarmania\.com/wp-content/uploads/[^"]+\.pdf)"', desc)
                base = _base(name)
                if pdfs:
                    self.docs_by_base.setdefault(base, []).extend(pdfs)
                if slugs & {"gerber-files", "combos-packs"} or re.search(r"combo|pack\b|bundle", name, re.I):
                    continue
                regional = bool(_REGION.search(name)) or "australia" in slugs
                files_only = bool(_FILES.search(name))
                rank = (files_only, regional)  # prefer the plain physical board
                if base not in chosen or rank < chosen[base][0]:
                    chosen[base] = (rank, pr)
            page += 1
        for base, (_rank, pr) in chosen.items():
            self.products[pr["slug"]] = pr
            yield pr["slug"]

    def parse(self, slug: str) -> Circuit | None:
        pr = self.products.get(slug)
        if not pr:
            return None
        name = _html.unescape(pr["name"])
        files_only = bool(_FILES.search(name))
        name = _REGION.sub("", re.sub(r"\s*[–-]\s*eagle and gerber files?\s*$", "", name, flags=re.I)).strip()
        desc_html = pr.get("description") or ""
        pdfs = re.findall(r'href="(https://pcbguitarmania\.com/wp-content/uploads/[^"]+\.pdf)"', desc_html)
        if not pdfs:
            pdfs = self.docs_by_base.get(_base(name), [])
        docs = [u for u in pdfs if re.search(r"build|doc", u, re.I)] or pdfs
        if not docs:
            return None
        short = html_to_text(pr.get("short_description") or "")
        m = re.search(r"inspired by\s+(?:the |an? )?(.+?)(?:[.\n]|$)", short, re.I)
        based_on = clean_text(m.group(1)) if m else ""
        description = html_to_text(desc_html)
        description = re.sub(r"Product Format Clarification.*?(?=Project Overview|Introduction|$)", "", description, flags=re.S | re.I).strip()
        slugs = [c["slug"] for c in pr.get("categories", [])]
        category = next((_CAT[s] for s in _CAT_ORDER if s in slugs), "")
        prices = pr.get("prices") or {}
        minor = int(prices.get("price") or 0)
        tags = [t for t in ("smd", "beginner", "diy-originals", "soviet", "tube") if t in slugs]
        if files_only:
            tags.append("gerber files only")
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=pr.get("permalink") or f"{BASE}/product/{slug}/",
            based_on=based_on, description=description[:2500], category=category or classify(based_on, name, description[:300]),
            effect_type=", ".join(c["name"] for c in pr.get("categories", []) if c["slug"] not in ("australia", "sale", "smd")),
            tags=tags, price=minor / 100 if minor else None, currency=prices.get("currency_code", "EUR"),
            in_stock=pr.get("is_in_stock"), doc_url=docs[0], image_url=(pr.get("images") or [{}])[0].get("src", ""),
        )
        for u in pdfs:
            if u != docs[0]:
                c.extra_docs["Drill template" if re.search(r"drill", u, re.I) else u.rsplit("/", 1)[-1]] = u
        for u in re.findall(r'href="(https?://(?:www\.)?(?:freestompboxes|diystompboxes)\.[^"]+)"', desc_html):
            c.extra_docs.setdefault("Forum discussion", _html.unescape(u))
        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            c.__dict__.update(process_document(pdf, self.vendor, slug))
            pages = pdf_text_pages(pdf)
            first = pages[0] if pages else ""
            hb = _header_field(first, "Based on:")
            if hb and not re.search(r"original|n/a|^-$", hb, re.I):
                c.based_on = hb
            c.enclosure = find_enclosure(_header_field(first, "Enclosure type:"), first, description)
            c.difficulty = _header_field(first, "Build difficult")
            et = _header_field(first, "Effect type:")
            if et:
                c.effect_type = et
                if not category:
                    c.category = classify(et, c.based_on, name)
            m = re.search(r"Document version\s+([\d.]+v?),?\s*([^\n]+)", "\n".join(pages[:2]))
            if m:
                c.doc_version = f"{m.group(1)} ({clean_text(m.group(2))})"
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                named = all(re.fullmatch(r"[A-Za-z][A-Za-z \-/]+\d?", r.ref) for r in pots)
                c.controls = [r.ref.title() for r in pots] if named else [f"{len(pots)} knobs"]
        return c
