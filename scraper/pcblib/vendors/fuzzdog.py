"""Fuzz Dog (Pedal Parts Ltd) adapter. Freewebstore, server-rendered.
Kit pages carry the description and the build-doc link; bare PCB pages point
back to the kit page, so we walk the circuit categories and parse kit pages."""
from __future__ import annotations

import re
from typing import Iterable

from selectolax.parser import HTMLParser

from ..models import BomRow, Circuit
from ..normalize import normalize_row, is_plausible
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import parse_bom_columns, pdf_text_pages, render_page
from ..taxonomy import classify, classify_within, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://shop.pedalparts.co.uk"
CATEGORIES = ["fuzz", "od-distortion", "boost", "compressors", "delay-mod-filter",
              "bigmuffbased", "noisy", "other", "fuzzpups", "1590afriendly", "bass-friendly"]


@register
class FuzzDog(Adapter):
    vendor = "fuzzdog"

    def list_targets(self) -> Iterable[str]:
        seen: set[str] = set()
        for cat in CATEGORIES:
            page = 1
            while True:
                url = f"{BASE}/category/{cat}/" if page == 1 else f"{BASE}/category/{cat}/{page}/name"
                html = self.f.get_text(url)
                if not html:
                    break
                doc = HTMLParser(html)
                links = [a.attributes.get("href", "") for a in doc.css(".product_name a")]
                new = 0
                for href in links:
                    if href and href not in seen:
                        seen.add(href)
                        new += 1
                        yield f"{cat}\t{href}"
                if new == 0:
                    break
                pag = doc.css_first("ul.pagination")
                if not pag or f"/{page + 1}/" not in pag.html:
                    break
                page += 1

    def parse(self, target: str) -> Circuit | None:
        cat, url = target.split("\t", 1)
        html = self.f.get_text(url)
        if not html:
            return None
        all_pdfs = [re.sub(r"\s+", "", p) for p in re.findall(r'href="(https?://pedalparts\.co\.uk/docs/[^"]+\.pdf)"', html)
                    if "GeneralBuildGuide" not in p]  # one page wraps a link across a line break
        # The FuzzPup family guide (FuzzPups.pdf, FuzzPups-V2.pdf) is linked ahead of the circuit's own doc.
        general = [p for p in all_pdfs if re.search(r"/FuzzPups(?:-V\d)?\.pdf$", p, re.I)]
        pdfs = [p for p in all_pdfs if p not in general] or all_pdfs
        if not pdfs:
            return None  # PCB-only page or accessory; the kit page carries the doc
        doc = HTMLParser(html)

        def meta(name: str, attr: str = "itemprop") -> str:
            n = doc.css_first(f'meta[{attr}="{name}"]')
            return clean_text(n.attributes.get("content", "")) if n else ""

        name = meta("name") or (clean_text(doc.css_first("h1").text()) if doc.css_first("h1") else "")
        sku = meta("sku")
        price = float(meta("price")) if re.match(r"^\d+(\.\d+)?$", meta("price")) else None
        currency = meta("priceCurrency") or "GBP"
        og_cat = meta("og:category", "property")
        desc_n = doc.css_first(".product_description")
        desc_html = desc_n.html if desc_n else ""
        specs = {clean_text(k).lower(): clean_text(re.sub(r"<[^>]+>", "", v))
                 for k, v in re.findall(r"<p>([^<]*?):\s*<span class=\"redb\">(.*?)</span>", desc_html)}
        description = html_to_text(desc_html)
        slug = url.rstrip("/").rsplit("/", 1)[-1].lower()
        knobs = specs.get("knobs required", "")
        m = re.match(r"(\d+)", knobs)

        category = _fuzzdog_category(cat, name, specs.get("inspired by", ""), description)
        c = Circuit(
            vendor=self.vendor, slug=slug, name=name, url=url,
            based_on=specs.get("inspired by", ""), description=description,
            category=category, effect_type=og_cat or cat,
            tags=[cat], enclosure=find_enclosure(specs.get("enclosure", ""), description),
            difficulty=specs.get("difficulty", ""), price=price, currency=currency, sku=sku,
            doc_url=pdfs[0],
        )
        if m:
            c.controls = [f"{m.group(1)} knobs"]
        for g in general:
            c.extra_docs["FuzzPup build guide"] = g
        pdf = self.f.get_file(c.doc_url, ".pdf")
        if pdf:
            pages = pdf_text_pages(pdf)
            c.doc_local = str(pdf.relative_to(DATA_DIR))
            page_no = next((i for i, p in enumerate(pages, 1) if re.search(r"schematic", p, re.I)), None)
            if page_no:
                png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
                if not png.exists():
                    render_page(pdf, page_no, png)
                c.schematic_local = str(png.relative_to(DATA_DIR))
                c.schematic_page = page_no
            # The BOM is on the schematic page in older docs and a few pages later in the 2023 layout.
            variants = _fuzzdog_variants(pages, name) if pages else []
            if variants:
                c.bom = variants
            else:
                per_page = [_parse_fuzzdog_bom(p) for p in pages]
                c.bom = max(per_page + [parse_bom_columns(pages)], key=len) if pages else []
            first = next((r.variant for r in c.bom if r.variant), "")
            pots = list({r.ref: r for r in c.bom if r.category == "POT" and r.ref.isalpha() and r.variant in ("", first)}.values())
            if pots and (not c.controls or c.controls[0].endswith("knobs")):
                c.controls = [r.ref.title() for r in pots]
            m = re.search(r"©\s*(\d{4})", "\n".join(pages))
            c.doc_version = m.group(1) if m else ""
        return c


_MOD = {"Delay", "Vibrato / Chorus", "Phaser", "Flanger", "Tremolo", "EQ / Filter", "Wah / Envelope", "Reverb", "Octave / Pitch", "Ring Mod / Synth"}
_DRIVE = {"Overdrive", "Distortion", "Preamp / Amp-in-a-box", "Boost"}


def _fuzzdog_category(bucket: str, name: str, based_on: str, description: str) -> str:
    hints = (name, based_on, description[:600])
    if bucket in ("fuzz", "bigmuffbased", "fuzzpups"):
        return "Fuzz"
    if bucket == "od-distortion":
        return classify_within(_DRIVE, *hints, default="Overdrive")
    if bucket == "boost":
        return "Boost"
    if bucket == "compressors":
        return "Compressor"
    if bucket == "delay-mod-filter":
        return classify_within(_MOD, *hints, default="Delay")
    if bucket == "noisy":
        return classify_within(_MOD | {"Fuzz"}, *hints, default="Ring Mod / Synth")
    return classify(*hints, bucket)


_CELL = re.compile(r"\b([RCDQLU]\d+(?:-\d+)?|IC\d+|[A-Z]{2,6}\.?)\s{2,}(\S(?:.*?\S)?)(?=\s{3,}|\s*$)")
# "DRIVE 1MA (500KA)" / "TONE 10KA": a named pot may sit one space from its value
_POT_CELL = re.compile(r"\b([A-Z]{3,8})\s+([ABCW]?\d+(?:[.,]\d+)?[KM]?[ABCW]?)(?:\s*\(([ABCW]?\d+(?:[.,]\d+)?[KM]?[ABCW]?)\))?(?=\s{2,}|\s*$)")


def _parse_fuzzdog_bom(page: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()
    for ln in page.splitlines():
        for name, val, alt in _POT_CELL.findall(ln):
            if name in seen or name in {"BOM", "PCB", "LED", "THE", "AND", "FOR", "ELEC"} or not re.search(r"[ABCW]", val):
                continue
            seen.add(name)
            rows.append(normalize_row(BomRow(ref=name, value=val, part_type="Potentiometer", category="POT", notes=f"or {alt}" if alt else "")))
        for ref, val in _CELL.findall(ln):
            if ref in seen or ref.upper() in {"BOM", "PCB", "LED", "THE", "AND", "FOR"} and not ref[-1].isdigit():
                continue
            if val.lower() in {"empty", "omit", "-"}:
                continue
            seen.add(ref)
            alt = ""
            m_alt = re.match(r"^(\S+)\s*\(([^)]+)\)\s*$", val)
            if m_alt:  # "22K (4K7)": the value in black and the alternate in blue
                val, alt = m_alt.group(1), m_alt.group(2)
            ptype = ""
            if re.search(r"elec", val, re.I):
                ptype = "Electrolytic capacitor"
                val = re.sub(r"\s*elec\w*", "", val, flags=re.I)
            nr = normalize_row(BomRow(ref=ref.rstrip("."), value=val, part_type=ptype, notes=f"or {alt}" if alt else ""))
            if is_plausible(nr):
                rows.append(nr)
    return rows


_PAGE_NOISE = re.compile(r"schematic\s*\+?\s*bom|schematic|\bbom\b|^\W*and the\b|\bversion\b|[-–:]+", re.I)


def _page_title(page: str) -> str:
    """The build a BOM page belongs to: 'PIG - Schematic + BOM' -> PIG, 'Schematic+BOM   DIRTY BIRD'
    -> DIRTY BIRD, a second line 'ORIGINAL PNP', or '...and the Dark Hill version' -> Dark Hill."""
    for ln in [x for x in page.splitlines() if x.strip()][:3]:
        t = re.sub(r"\s+[RC]\d+\b.*$", "", ln.strip())  # a row's designators on the same line
        t = _PAGE_NOISE.sub(" ", t)
        t = re.sub(r"\s+", " ", t).strip(" ./>")
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()  # "(standard)" but not "3rd (70s)"
        if _good_name(t):
            return t
    return ""


def _good_name(t: str) -> bool:
    """A build name, not a sentence, a row or a heading fragment."""
    return 2 <= len(t) <= 40 and not re.match(r"^[RCDQ]\d", t) and not re.search(r"\d+[knpuKMR]\b|\bR\d", t) \
        and not re.search(r"\b(?:it['’]s|leave|listed|additions?|schem\b|below|above|follow|notes?|empty|value|page|next)\b", t, re.I) \
        and len(t.split()) <= 5


_TWO_BUILDS = re.compile(r"For the (.{3,40}?) follow the standard BOM.*?For the (.{3,40}?)\s+substitute", re.S | re.I)


def _fuzzdog_variants(pages: list[str], product: str) -> list[BomRow]:
    """Fuzz Dog reuses a board across builds: a BOM page per version (the Big Muff docs,
    'PIG' and 'BELLS'), and sometimes one table whose parenthesized values make a second
    build ('For the Southern Drive follow the standard BOM. For the 186,282Mps substitute
    the parts in blue'). Returns rows with variant names, or [] when the doc has one build."""
    boms = [(t, rows) for t, rows in ((_page_title(p), _parse_fuzzdog_bom(p)) for p in pages) if len(rows) >= 8]
    two = _TWO_BUILDS.search("\n".join(pages))
    out: list[BomRow] = []
    for i, (title, rows) in enumerate(boms):
        name = title or (product if i == 0 else f"Version {i + 1}")
        if two and any(r.notes.startswith("or ") for r in rows) and not (title and i > 0):
            base, alt = two.group(1).strip(" ./"), two.group(2).strip(" ./")
            if not (_good_name(base) and _good_name(alt)):
                two = None
            for r in rows:
                out.append(BomRow(ref=r.ref, value=r.value, part_type=r.part_type, category=r.category, norm_value=r.norm_value, sort_key=r.sort_key, variant=base))
            for r in rows:
                v = r.notes[3:] if r.notes.startswith("or ") else r.value
                if v.lower() in ("empty", "omit", "jumper"):
                    continue
                nr = normalize_row(BomRow(ref=r.ref, value=v, part_type=r.part_type, category=r.category if r.category in ("POT", "TRIM", "SW") else "", variant=alt))
                if is_plausible(nr):
                    out.append(nr)
            continue
        if two is None and i == 0 and any(r.notes.startswith("or ") for r in rows):
            pass  # alternates stay as notes when the doc does not name the second build
        for r in rows:
            r.variant = name
            out.append(r)
    names = {r.variant for r in out}
    return out if len(names) >= 2 and all(names) else []