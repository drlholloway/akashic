"""Mask Audio Electronics adapter. Shopify collection of DIY boards; each product
description links a Word build document (Dropbox or Google Docs) whose parts
list is a real table, plus drill templates. One PDF doc (the Damnation Audio
Parallel Drive) is an Eagle schematic and is read by label pairing."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable
from urllib.parse import unquote

from ..docx import docx_bom, read_docx
from ..models import BomRow, Circuit
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import process_document, schematic_bom
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://maskaudioelectronics.com"
COLLECTION = f"{BASE}/collections/diy-projects/products.json?limit=250"

_NAME = {
    "the-notch-diy": "The Notch", "no-diy": "NO.", "yes-diy": "YES!", "ears-come-do-die-diy": "Ears Come To Die",
    "pcb": "Business Card", "damnation-audio-diy-parallel-drive-1": "Parallel Drive",
    "small-format-drive-sfd-diy-project": "Small Format Drive", "biamp-diy-project": "BIAMP",
}
# What each board is based on, from the build docs; MAE's own designs stay empty.
_BASED_ON = {
    "dark-grime-diy-project": "EFE Black Dust", "iommic-boost-diy-project": "D*A*M B13 (Rangemaster)",
    "modern-revolt-octave-fuzz-diy-project": "Death By Audio Octave Clang", "small-format-drive-sfd-diy-project": "Rounding Error",
    "big-clang-diy-project": "Interfax Harmonic Percolator", "biamp-diy-project": "DOD FX10 BiFET Preamp",
    "akron-rubber-fire-diy-project": "Electra Distortion / MOSFET boost", "sock-diy-project": "Ibanez Tube Screamer",
    "titan": "EHX Big Muff", "massive-amp-diy-project": "MXR Micro Amp", "the-notch-diy": "Intersound The Notch",
    "hmtone-diy-project": "BOSS HM-2 (tone stack)", "ears-come-do-die-diy": "Devi Ever Hounds Tooth into Ruiner",
    "fragments-diy-project": "Tone Bender MKII / Flatline Compressor", "helvetica-92-od-diy": "EHX Big Muff",
    "shattered-glass-diy-project": "Anderton Super Tone Control", "damnation-audio-diy-parallel-drive-1": "Damnation Audio Parallel Drive",
    "freebies#one-knob-clang": "Interfax Harmonic Percolator", "freebies#quick-face": "Fuzz Face",
    "freebies#msb": "Devi Ever Mirro Safety Bag", "freebies#deimos": "Mask Audio LARAN",
}
_CATEGORY = {"helvetica-92-od-diy": "Overdrive", "t-amp-diy-project": "Preamp / Amp-in-a-box", "pcb": "Fuzz",
             "freebies#deimos": "Fuzz", "freebies#msb": "Fuzz"}
_TAG_CATEGORY = [("filter", "EQ / Filter"), ("EQ", "EQ / Filter"), ("Fuzz", "Fuzz"), ("Overdrive", "Overdrive"),
                 ("Boost", "Boost"), ("Octave", "Octave / Pitch"), ("Dynamics", "Compressor"), ("utility", "Utility")]
_LABEL_LINE = re.compile(r"^\s*(?:Build (?:Doc|Guide|Documents?)|Drill (?:Template|Layout)|125B Top Jack[^\n]*|Short Demo|VARIATIONS|"
                         r"Mod Notes|DOC|DRILL|[A-Z0-9 .!]+ (?:DOC|DRILL))\s*:?\s*$", re.M)


def _links(body_html: str) -> list[tuple[str, str]]:
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body_html, re.S):
        href = _html.unescape(href)
        m = re.search(r"https://www\.dropbox\.com/[^\s\"<]+|https://docs\.google\.com/document/d/[A-Za-z0-9_-]+", href)
        url = m.group(0) if m else href
        url = re.sub(r"<br>.*$", "", url)
        out.append((url, clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", label)))))
    return out


def _fetch_url(url: str) -> tuple[str, str]:
    """Return (download url, extension) for a Dropbox or Google Docs link."""
    if "docs.google.com/document" in url:
        fid = re.search(r"/d/([A-Za-z0-9_-]+)", url).group(1)
        return f"https://docs.google.com/document/d/{fid}/export?format=docx", ".docx"
    ext = ".pdf" if re.search(r"\.pdf(?:\?|$)", url, re.I) else ".docx" if re.search(r"\.docx(?:\?|$)", url, re.I) else ".bin"
    if "dl=0" in url:
        url = url.replace("dl=0", "dl=1")
    elif "dl=1" not in url:
        url += ("&" if "?" in url else "?") + "dl=1"
    return url, ext


def _sub_name(label: str) -> str:
    n = re.sub(r"\s*(?:BUILD\s+)?(?:DOC(?:UMENT)?|GUIDE|DRILL)\s*$", "", label, flags=re.I).strip()
    return " ".join(w if len(w) <= 3 and not re.search(r"[AEIOU]", w) else w.title() for w in n.split())


@register
class MaskAudio(Adapter):
    vendor = "maskaudio"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def _docs(self, pr: dict) -> list[tuple[str, str]]:
        """(url, label) of every build document linked from the product."""
        return [(u, t) for u, t in _links(pr.get("body_html") or "")
                if (re.search(r"\b(?:build|doc|guide)\b", t, re.I) or "docs.google.com/document" in u)
                and not re.search(r"drill|mod notes|variation|video", t, re.I)
                and re.search(r"dropbox\.com|docs\.google\.com", u)]

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(COLLECTION, ".json")
        for pr in (json.loads(raw).get("products", []) if raw else []):
            self.products[pr["handle"]] = pr
            docs = self._docs(pr)
            if len(docs) > 1:
                for _, label in docs:
                    yield f"{pr['handle']}#{re.sub(r'[^a-z0-9]+', '-', _sub_name(label).lower()).strip('-')}"
            else:
                yield pr["handle"]

    def parse(self, target: str) -> Circuit | None:
        handle, _, sub = target.partition("#")
        pr = self.products.get(handle)
        if not pr:
            return None
        docs = self._docs(pr)
        if not docs:
            return None  # daughterboards, converters, the LARAN kit
        links = _links(pr.get("body_html") or "")
        if sub:
            docs = [(u, t) for u, t in docs if re.sub(r"[^a-z0-9]+", "-", _sub_name(t).lower()).strip("-") == sub]
            if not docs:
                return None
            name = _sub_name(docs[0][1])
            key = re.sub(r"\s+", "", name.lower())
            drills = [(u, t) for u, t in links if re.search(r"drill", t, re.I) and re.sub(r"\s+", "", _sub_name(t).lower()) == key]
            price = None
        else:
            title = _html.unescape(pr["title"])
            name = _NAME.get(handle) or clean_text(re.sub(r"\s*(?:DIY Project|DIY KIT|DIY|PCB)\s*$", "", title, flags=re.I))
            if name.islower():
                name = name.title()
            drills = [(u, t) for u, t in links if re.search(r"drill", t, re.I)]
            variant = (pr.get("variants") or [{}])[0]
            price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        key = f"{handle}#{sub}" if sub else handle
        body = _LABEL_LINE.sub("", html_to_text(pr.get("body_html") or ""))
        body = clean_text(re.sub(r"\n{3,}", "\n\n", body))
        tags = [t for t in pr.get("tags", []) if t not in ("DIY", "Easy", "Intermediate", "kit")]
        category = _CATEGORY.get(key) or next((c for t, c in _TAG_CATEGORY if t in pr.get("tags", [])), "") \
            or classify(name, _BASED_ON.get(key, ""), body[:300])
        c = Circuit(
            vendor=self.vendor, slug=re.sub(r"[#]", "-", key), name=name, url=f"{BASE}/products/{handle}",
            based_on=_BASED_ON.get(key, ""), description=body, category=category, tags=tags,
            difficulty=next((t for t in pr.get("tags", []) if t in ("Easy", "Intermediate", "Advanced")), ""),
            price=price, currency="USD", in_stock=(pr.get("variants") or [{}])[0].get("available"),
            doc_url=docs[0][0], image_url=(pr.get("images") or [{}])[0].get("src", "").split("?")[0],
        )
        for u, t in drills:
            c.extra_docs["125B top-jack drill template" if re.search(r"125B", t) else "Drill template"] = u
        for u, t in links:
            if re.search(r"variation", t, re.I):
                c.extra_docs["Variations"] = u
            elif re.search(r"mod notes", t, re.I):
                c.extra_docs["Mod notes"] = u
            elif re.search(r"demo", t, re.I) or "instagram.com" in u:
                c.extra_docs["Demo"] = u
        if sub:
            c.description += "\n\nFree with any PCB order, or all of the freebies together as a bundle."
        fetch_url, ext = _fetch_url(c.doc_url)
        path = self.f.get_file(fetch_url, ext)
        if not path or path.stat().st_size < 2000:
            return c
        c.doc_local = str(path.relative_to(DATA_DIR))
        m = re.search(r"(\d+\.\d+)\.docx", unquote(c.doc_url))
        if m:
            c.doc_version = m.group(1)
        if ext == ".docx" and path.read_bytes()[:2] == b"PK":
            paras, tables, media = read_docx(path)
            c.bom = docx_bom(tables)
            c.enclosure = find_enclosure(*paras)
            if sum(1 for tb in tables for row in tb for cell in row if cell.strip() == "R1") > 1:
                c.description += "\n\nThe parts list shows the first of several variant specs in the build document."
            intro = next((p for p in paras if len(p) > 80 and not re.match(r"^(The (?:six|four|ten|two) |For Limited|Terms of Use|NOTE)", p)), "")
            if intro and intro[:60] not in c.description:
                c.description = clean_text(c.description + "\n\n" + intro)
            out = CACHE_DIR / self.vendor
            out.mkdir(parents=True, exist_ok=True)
            for i, (mname, data) in enumerate(sorted(media.items()), 1):
                (out / f"{c.slug}-img{i}{'.jpg' if mname.lower().endswith(('.jpg', '.jpeg')) else '.png'}").write_bytes(data)
        elif ext == ".pdf" and path.read_bytes()[:5] == b"%PDF-":
            res = process_document(path, self.vendor, c.slug)
            c.bom = res["bom"]
            c.schematic_local, c.schematic_page = res["schematic_local"], res["schematic_page"]
            if len(c.bom) < 8 and c.schematic_page:
                rows = schematic_bom(path, c.schematic_page)
                if len(rows) > len(c.bom):
                    for r in rows:
                        r.notes = r.notes or "from schematic"
                    c.bom = rows
        if not c.enclosure and any("125B" in t for _, t in drills):
            c.enclosure = "125B"
        pots = [r for r in c.bom if r.category == "POT" and not re.match(r"^(?:POT|P|RV|VR)\d+$", r.ref, re.I)]
        c.controls = [re.sub(r"^([A-Za-z]{3,})([AB])$", r"\1 \2", r.ref).title() if r.ref.isupper() else r.ref for r in pots]
        return c
