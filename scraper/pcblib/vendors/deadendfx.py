"""Dead End FX adapter. Big Cartel store: products.json lists the catalog; build
documents live on Google Drive, linked from the /build-doc-links page. The docs
are Word exports whose parts table is rasterised, so the BOM is OCR'd."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import pdf_text_pages, ocr_bom, render_page, schematic_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.deadendfx.com"
_SKIP_CATS = {"SERVICE", "ADAPTER", "BYPASS PIC CHIP"}
_CAT = {
    "FUZZ": "Fuzz", "OVERDRIVE": "Overdrive", "DISTORTION": "Distortion", "BOOSTER": "Boost",
    "OCTAVE": "Octave / Pitch", "HARMONIZER": "Octave / Pitch", "MODULATION": "Vibrato / Chorus",
    "CHORUS": "Vibrato / Chorus", "PHASER": "Phaser", "FLANGER": "Flanger", "TREMOLO": "Tremolo",
    "PANNER": "Tremolo", "FILTER": "EQ / Filter", "EQ": "EQ / Filter", "ENVELOPE FILTERS": "Wah / Envelope",
    "FILTER WAH": "Wah / Envelope", "WAH": "Wah / Envelope", "FUZZ/WAH": "Fuzz",
    "RING MODULATION": "Ring Mod / Synth", "SAMPLE/HOLD": "Ring Mod / Synth", "BITCRUSHER": "Ring Mod / Synth",
    "COMPRESSOR": "Compressor", "ECHO": "Delay", "DELAY": "Delay", "REVERB": "Reverb", "PREAMP": "Preamp / Amp-in-a-box",
    "NOISE GATE": "Noise Gate", "LOOP BUFFER": "Utility", "UTILITY": "Utility", "SILENT RELAY BYPASS": "Utility",
    "FEEDBACK LOOPER": "Utility",
}
_STOP = {"pcb", "board", "defx", "version", "build", "document", "project", "plus", "kit", "reproduction",
         "original", "format", "update", "quantities", "limited", "new", "release"}


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\b(v\.?\s?\d+|20\d\d|\d{4} update)\b", "", s)
    return " ".join(w for w in re.findall(r"[a-z0-9#+]+", s) if w not in _STOP)


def _drive_download(url: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})|[?&]id=([A-Za-z0-9_-]{20,})", url)
    fid = (m.group(1) or m.group(2)) if m else ""
    return f"https://drive.google.com/uc?export=download&id={fid}" if fid else url


@register
class DeadEndFX(Adapter):
    vendor = "deadendfx"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}
        self.docs: dict[str, list[tuple[str, str]]] = {}  # normalised name -> [(label, url)]

    def _load_docs(self) -> None:
        h = self.f.get_text(f"{BASE}/build-doc-links") or ""
        h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S)
        h = re.sub(r'<a[^>]+href="(https://drive[^"]+)"[^>]*>', r" [[DOC:\1]] ", h)
        t = _html.unescape(re.sub(r"<[^>]+>", "\n", h))
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n", t)
        for name, url in re.findall(r"^\s*(.+?)\s*-\s*(?:\([^)]*\)\s*-\s*)?\[\[DOC:(https://drive[^\]]+)\]\]", t, re.M):
            self.docs.setdefault(_norm(name), []).append((clean_text(name), url))

    def _doc_for(self, name: str) -> tuple[str, str] | None:
        k = _norm(name)
        if k in self.docs:
            return self.docs[k][-1]  # the last listed entry is the newest revision
        cands = [d for d in self.docs if d and (k.startswith(d) or d.startswith(k))]
        if not cands and k:
            cands = [d for d in self.docs if d and d.split()[0] == k.split()[0]]
        if not cands:
            return None
        best = sorted(cands, key=lambda d: (-len(d), d))[0]
        return self.docs[best][-1]

    def list_targets(self) -> Iterable[str]:
        self._load_docs()
        raw = self.f.get_text(f"{BASE}/products.json", ".json") or "[]"
        for pr in json.loads(raw):
            cats = {c["name"].upper() for c in pr.get("categories", [])}
            if cats & _SKIP_CATS or pr.get("status") not in ("active", "sold-out"):
                continue
            self.products[pr["permalink"]] = pr
            yield pr["permalink"]

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        doc = self._doc_for(pr["name"])
        if not doc:
            return None
        doc_label, doc_url = doc
        body = html_to_text(pr.get("description") or "")
        m = re.search(r"clone (?:board |pcb )?of (?:the |an? )?(.+?)(?:[.!]|\n|$)", body, re.I)
        based_on = clean_text(m.group(1)) if m else ""
        cats = [c["name"].upper() for c in pr.get("categories", [])]
        tags = [c.title() for c in cats if c == "BEYOND MORE"]
        cat_names = [c for c in cats if c != "BEYOND MORE"]
        category = next((_CAT[c] for c in cat_names if c in _CAT), "") or classify(based_on, pr["name"], body[:300])
        name = clean_text(re.sub(r"\s*-\s*(PROJECT PLUS KIT.*|REPRODUCTION PCB|DEFX VERSION|ORIGINAL FORMAT|2024 UPDATE)$", "", pr["name"], flags=re.I)).title()
        name = re.sub(r"\b(Ii|Iii|Iv|Xy|Pu|Defx|Pll|Ehx|Mv)\b", lambda m: m.group(1).upper(), name)
        price = pr.get("default_price")
        c = Circuit(
            vendor=self.vendor, slug=handle, name=name, url=f"{BASE}/product/{handle}",
            based_on=based_on, description=body, category=category,
            effect_type=", ".join(x.title() for x in cat_names), tags=tags,
            price=float(price) if price is not None else None, currency="USD",
            in_stock=(pr.get("status") == "active"), doc_url=doc_url,
            image_url=(pr.get("images") or [{}])[0].get("url", "").split("?")[0],
        )
        pdf = self.f.get_file(_drive_download(doc_url), ".pdf")
        if pdf and pdf.stat().st_size > 2000 and pdf.read_bytes()[:5] == b"%PDF-":
            pages = pdf_text_pages(pdf)
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            head = "\n".join(pages[:2])
            if not c.based_on:
                m = re.search(r"clone of (?:the |an? )?(.+?)\)", head, re.I)
                if m:
                    c.based_on = clean_text(m.group(1))
            m = re.search(r"Enclosure\s{2,}(.+)", head)
            c.enclosure = find_enclosure(m.group(1) if m else "", head)
            m = re.search(r"Supply\s{2,}(.+)", head)
            if m:
                c.extra_docs["Power"] = clean_text(m.group(1))[:40]
            m = re.search(r"\((?:updated|rev\.?)\s*([^)]+)\)", doc_label, re.I)
            c.doc_version = clean_text(m.group(1)) if m else ""
            # The schematic is the vector drawing on the last page(s); read every page that
            # carries designator labels, last page first.
            sch_pages = [i for i in range(len(pages), 0, -1) if len(re.findall(r"\b[RC]\d+\b", pages[i - 1])) >= 5]
            sch_rows: list = []
            have: set[str] = set()
            if sch_pages:
                sch = sch_pages[0]
                png = CACHE_DIR / self.vendor / f"{handle}-schematic.png"
                if not png.exists():
                    render_page(pdf, sch, png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = sch
                for pn in sch_pages:
                    for r in schematic_bom(pdf, pn):
                        if r.ref not in have:
                            have.add(r.ref)
                            sch_rows.append(r)
            # The OCR'd parts table fills in whatever the schematic does not label
            # (pots, switches, transformers) and any designator it missed.
            maxnum: dict[str, int] = {}
            for r in sch_rows:
                pre = re.sub(r"\d.*$", "", r.ref)
                maxnum[pre] = max(maxnum.get(pre, 0), int(re.sub(r"\D", "", r.ref) or 0))
            ocr_rows = []
            for r in ocr_bom(pdf, self.vendor, handle, max_pages=4):
                if r.ref in have:
                    continue
                pre = re.sub(r"\d.*$", "", r.ref)
                num = int(re.sub(r"\D", "", r.ref) or 0)
                if pre in maxnum and num > maxnum[pre] * 1.5 + 5:
                    continue  # OCR misread designator (C110 for C10)
                have.add(r.ref)
                ocr_rows.append(r)
            c.bom = sch_rows + ocr_rows
            pots = [r for r in c.bom if r.category == "POT"]
            if pots:
                c.controls = [r.ref.title() for r in pots] if all(r.ref.isalpha() for r in pots) else [f"{len(pots)} knobs"]
        # "Power" is informational, not a document link
        c.extra_docs = {k: v for k, v in c.extra_docs.items() if v.startswith("http")}
        return c
