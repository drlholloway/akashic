"""General Guitar Gadgets adapter. The Shopify store lists ~77 ready-to-solder
PCBs; each links its project page on generalguitargadgets.com, which links
per-version PDFs named ggg_<proj>[_<ver>]_bom / _sc / _lo / _instruct.pdf.
The BOM is text ("Resistor ID  Value  3-band marking"), the schematic a raster."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import parse_bom_columns, pdf_text_pages, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

STORE = "https://store.generalguitargadgets.com"
SITE = "https://generalguitargadgets.com"
_CAT = {"Distortion": "Distortion", "Boosters": "Boost", "Fuzz Tones": "Fuzz", "Switchers & Routers": "Utility",
        "Octave Effects": "Octave / Pitch", "Modulation & Echo": "Vibrato / Chorus", "FILTERS (ENVELOPE)": "Wah / Envelope",
        "Bass Effects": "Bass", "Amps": "Preamp / Amp-in-a-box", "Power Supplies": "Utility", "Phase Shifters": "Phaser",
        "FILTERS (OTHER)": "EQ / Filter", "Direct Inject (DI)": "Utility", "Compressors": "Compressor", "compressors": "Compressor",
        "Wah Wah": "Wah / Envelope", "Reverb": "Reverb", "Tremolo": "Tremolo", "Add-On": "Utility"}
# Three shapes seen: "R3 (Distortion        100k Log Potentiometer" (Control) on the next line),
# "R4 - Volume Control   50k   Reverse Log Taper", "R6 (Volume)  100k Log Potentiometer".
_POT_LINE = re.compile(r"^\s*(R\d+)\s*(?:-|\()?\s*([A-Za-z][A-Za-z /]*?)\s*(?:Control)?\)?\s+(\d+(?:\.\d+)?\s?[kKM]?)\s+(Reverse (?:Log|Audio)|Rev\.? Log|Log(?: \(or Audio\))?|Audio(?: \(or Log\))?|Lin(?:ear)?)?\s*(?:Taper)?\s*(?:Potentiometer)?\s*$", re.M)
_TAPER = {"log": "A", "audio": "A", "lin": "B", "linear": "B", "rev": "C", "reverse": "C", "reverse log": "C", "reverse audio": "C", "rev log": "C"}


def _clean_title(t: str) -> str:
    t = _html.unescape(t).replace("™", "").replace("®", "")
    t = re.sub(r"\b(RTS|PCB|REPLICA|READY[- ]TO[- ]SOLDER)\b", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -").title().replace("Ehx", "EHX").replace("Mxr", "MXR").replace("Ic ", "IC ").replace("Aby", "ABY").replace("Di ", "DI ")


@register
class GGG(Adapter):
    vendor = "ggg"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.products: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page = 1
        while True:
            raw = self.f.get_text(f"{STORE}/collections/pcbs/products.json?limit=250&page={page}", ".json")
            items = json.loads(raw).get("products", []) if raw else []
            if not items:
                break
            for pr in items:
                self.products[pr["handle"]] = pr
                yield pr["handle"]
            page += 1

    def _find_project(self, title: str) -> str:
        """Store entries without a project link: ask the WordPress search API for the
        project page whose title shares a distinctive word with the product's."""
        from urllib.parse import quote
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", title) if w.lower() not in ("the", "and", "for", "add", "kit", "type")]
        if not words:
            return ""
        raw = self.f.get_text(f"{SITE}/wp-json/wp/v2/pages?search={quote(' '.join(words[:3]))}&per_page=8&_fields=link,title", ".json")
        try:
            hits = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            return ""
        for h in hits:
            link = h.get("link", "")
            t = _html.unescape(re.sub(r"<[^>]+>", "", (h.get("title") or {}).get("rendered", ""))).lower()
            if re.match(re.escape(SITE) + r"/effects-projects/[a-z0-9-]+/[a-z0-9-]+/$", link) and any(w.lower() in t for w in words):
                return link
        return ""

    def parse(self, handle: str) -> Circuit | None:
        pr = self.products.get(handle)
        if not pr:
            return None
        body_html = pr.get("body_html") or ""
        projects = [re.sub(r"^http://", "https://", u.replace("www.gggadgetstest.com", "generalguitargadgets.com").replace("www.generalguitargadgets.com", "generalguitargadgets.com"))
                    for u in re.findall(r'href="(https?://[^"]*generalguitargadgets\.com/effects-projects/[^"]+|https?://www\.gggadgetstest\.com/effects-projects/[^"]+)"', body_html)]
        title = _clean_title(pr["title"])
        variant = (pr.get("variants") or [{}])[0]
        price = float(variant["price"]) if re.match(r"^\d+(\.\d+)?$", str(variant.get("price", ""))) else None
        tags = pr.get("tags", [])
        category = next((_CAT[t] for t in tags if t in _CAT and t != "Add-On"), "") or (_CAT.get("Add-On", "") if "Add-On" in tags else "")
        is_replica = bool(re.search(r"replica", pr["title"], re.I))
        c = Circuit(
            vendor=self.vendor, slug=handle, name=title, url=f"{STORE}/products/{handle}", based_on=title if is_replica else "",
            description=html_to_text(body_html), category=category or classify(title), effect_type=", ".join(t for t in tags if t != "Add-On"),
            tags=[t for t in tags if t == "Add-On"], price=price, currency="USD", in_stock=variant.get("available"),
            image_url=(pr.get("images") or [{}])[0].get("src", ""),
        )
        if not projects:
            found = self._find_project(title)
            if found:
                projects = [found]
        if not projects:
            return c if price else None
        page_url = projects[0]
        html = self.f.get_text(page_url) or ""
        c.extra_docs["Project page"] = page_url
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        h1 = clean_text(_html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))) if m else ""
        if h1 and is_replica and not re.search(r"general guitar gadgets", h1, re.I):
            c.based_on = re.sub(r"\s+Replicas?$", "", h1).strip()
        pdfs = []
        for u in re.findall(r'href="(https?://(?:www\.)?generalguitargadgets\.com/pdf/[^"]+\.pdf)"', html):
            u = re.sub(r"^http://(www\.)?", "https://", u)
            if u not in pdfs:
                pdfs.append(u)
        boms = [u for u in pdfs if u.endswith("_bom.pdf")]
        if not boms:
            return c
        bom_url = boms[0]
        stem = bom_url.rsplit("/", 1)[-1][:-len("_bom.pdf")]
        sc_url = next((u for u in pdfs if u.endswith(f"/{stem}_sc.pdf")), next((u for u in pdfs if u.endswith("_sc.pdf")), ""))
        instruct = next((u for u in pdfs if u.endswith("_instruct.pdf") and "general_instruct" not in u), "")
        c.doc_url = instruct or bom_url
        if instruct:
            c.extra_docs["Bill of materials"] = bom_url
        if sc_url:
            c.extra_docs["Schematic PDF"] = sc_url
        lo = next((u for u in pdfs if u.endswith(f"/{stem}_lo.pdf")), "")
        if lo:
            c.extra_docs["Parts layout"] = lo
        others = [u for u in pdfs if u.endswith("_sc.pdf") and u != sc_url]
        for u in others[:8]:
            label = u.rsplit("/", 1)[-1][:-len("_sc.pdf")].replace("ggg_", "").replace("_", " ").upper()
            c.extra_docs[f"Schematic: {label}"] = u
        pdf = self.f.get_file(bom_url, ".pdf")
        if pdf and pdf.read_bytes()[:5] == b"%PDF-":
            pages = pdf_text_pages(pdf)
            text = "\n".join(pages)
            m = re.search(r"^\s*(.+?)\s*\((.+?)\s+Replica\)\s*(.*)$", pages[0] if pages else "", re.M)
            if m:
                c.name = clean_text(m.group(1)).replace("TM", "")
                c.based_on = clean_text(m.group(2)).replace("TM", "")
                version = clean_text(m.group(3))
                if version:
                    c.tags.append(version)
            m = re.search(r"Version\s+(\d{4}[A-Za-z]+\d+)", text)
            if m:
                c.doc_version = m.group(1)
            rows = [r for r in parse_bom_columns(pages) if r.category != "CONN"]
            seen = {r.ref for r in rows}
            for ref, name, val, taper in _POT_LINE.findall(text):
                name = clean_text(name)
                if name.lower() in ("optional", "boost volume", "volume") and not name:
                    continue
                rows = [r for r in rows if r.ref != ref]
                if name.upper() in seen:
                    continue
                seen.add(name.upper())
                tk = _TAPER.get(re.sub(r"\s*\(or (?:audio|log)\)", "", (taper or "").lower().replace(".", "")).strip(), "")
                rows.append(normalize_row(BomRow(ref=name.upper() or ref, value=f"{tk}{val.replace(' ', '')}", part_type="Potentiometer", category="POT")))
            c.bom = rows
            c.enclosure = find_enclosure(text)
            pots = [r for r in rows if r.category == "POT"]
            if pots:
                c.controls = [r.ref.title() for r in pots]
        if sc_url:
            spdf = self.f.get_file(sc_url, ".pdf")
            if spdf and spdf.read_bytes()[:5] == b"%PDF-":
                png = CACHE_DIR / self.vendor / f"{handle}-schematic.png"
                if not png.exists():
                    try:
                        render_page(spdf, 1, png)
                    except Exception:  # noqa: BLE001
                        png = None
                if png:
                    c.schematic_local = str(png.relative_to(DATA_DIR))
                    c.schematic_page = 1
        if instruct:
            ipdf = self.f.get_file(instruct, ".pdf")
            if ipdf and ipdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(ipdf.relative_to(DATA_DIR))
                if not c.enclosure:
                    c.enclosure = find_enclosure(*pdf_text_pages(ipdf))
        return c
