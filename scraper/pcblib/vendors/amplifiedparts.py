"""Amplified Parts pedal guides: build projects on turret, eyelet and stripboard, each with a layout,
a schematic and, on most, a parts list table grouped by section (Capacitors, Potentiometers, Resistors,
Semiconductors, Other Items) with values, quantities and Amplified Parts SKUs but no designators.
The parts are listed as counted values ('×2 1M'), the pots by the control they are. 'Layout only'
guides (all stripboard) have no table and their drawings are outlined text, so they are listed without
parts. Eyelet boards count as turret builds.

The guides for Mod Electronics PCBs (designators on every row) are read by the Mod Electronics source
with `guide_rows`; the Iss. 1 guide, for Amplified Parts' own Fuzz Face PCB, is neither and is skipped."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import normalize_row
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

SITE = "https://www.amplifiedparts.com"
GUIDES = SITE + "/pedal-guides"
_SKIP = re.compile(r"^build-project-(?:mod-electronics-|iss1-)")
# slug (after 'build-project-') -> the original, in the names the library already uses.
BASED_ON = {
    "blackout-fuzz": "Dallas Arbiter Fuzz Face",
    "burns-buzzaround-eyelet": "Baldwin-Burns Buzzaround",
    "carlsbro-fuzz-tone": "Carlsbro Fuzz-Tone",
    "dinosaural-tubebender": "Dinosaural Tube Bender",
    "distortion-plus": "MXR Distortion+",
    "foxx-tone-machine": "Foxx Tone Machine",
    "fuzz-face-rangemaster-eyelet": "Fuzz Face / Rangemaster",
    "fuzz-face-rangemaster-stripboard": "Fuzz Face / Rangemaster",
    "fuzz-face-with-bias": "Dallas Arbiter Fuzz Face",
    "fuzzrite-germanium": "Mosrite Fuzzrite",
    "fuzzz-boxx": "Sam Ash Fuzzz Boxx",
    "graphic-fuzz": "Earth Sound Research Graphic Fuzz",
    "grind-customs-deprofundis-delay": "Grind Customs FX DeProfundis Delay",
    "harmonic-percolator-albini-version": "Interfax Harmonic Percolator",
    "harmonic-percolator-stock-version": "Interfax Harmonic Percolator",
    "hofner-buzztone": "Höfner Buzztone",
    "lpb1": "Electro-Harmonix LPB-1",
    "maestro-fz-1-fuzz-tone": "Maestro FZ-1 Fuzz-Tone",
    "one-knob-fuzz-face": "Dallas Arbiter Fuzz Face",
    "one-knob-tonebender-mk1": "Sola Sound Tone Bender MKI",
    "one-knob-tonebender-mk2": "Sola Sound Tone Bender MKII",
    "park-fuzz-sound-2-knob": "Park Fuzz Sound",
    "proco-rat": "ProCo Rat",
    "rangemaster": "Dallas Rangemaster",
    "rangemaster-range-toggle": "Dallas Rangemaster",
    "rangemaster-terminal-strip": "Dallas Rangemaster",
    "tonebender-mk1": "Sola Sound Tone Bender MKI",
    "tonebender-mk1-original-stripboard": "Sola Sound Tone Bender MKI",
    "tonebender-mk2": "Sola Sound Tone Bender MKII",
    "tonebender-mk2-silicon": "Sola Sound Tone Bender MKII",
    "tonebender-mk3": "Sola Sound Tone Bender MkIII",
    "top-gear-fuzz": "Top Gear Fuzz",
    "tycobrahe": "Tycobrahe Octavia",
    "zonk2-germanium": "Hornby Skewes Zonk Machine II",
}
# Where the guide's words mislead the classifier: treble boosters, a clean boost, a drive.
_CATEGORY = {"rangemaster": "Boost", "rangemaster-range-toggle": "Boost", "rangemaster-terminal-strip": "Boost",
             "lpb1": "Boost", "dinosaural-tubebender": "Overdrive"}
_COLUMNS = {"reference": "ref", "value": "value", "val": "value", "qty": "qty", "sku": "sku", "type": "type",
            "package type": "type", "footprint": "type", "note": "note", "notes": "note"}
_SECTION = {"capacitors": "C", "potentiometers": "POT", "resistors": "R", "semiconductors": "", "transistors": "Q", "other items": "OTHER"}


def _cells(tr: str) -> list[str]:
    return [clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", td))) for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]


def table_items(page: str) -> list[dict]:
    """Every row of the guide's parts tables as {ref, value, qty, sku, type, note, section}."""
    out: list[dict] = []
    for table in re.findall(r"<table.*?</table>", page, re.S):
        if "View cart" in table:
            continue
        cols: list[str] = []
        section = ""
        for tr in re.findall(r"<tr.*?</tr>", table, re.S):
            cells = _cells(tr)
            if "<th" in tr:
                cols = [_COLUMNS.get(c.lower(), "") for c in cells]
                if "value" not in cols:
                    break  # a transistor gain table, not parts
                continue
            if len(cells) == 1:
                section = _SECTION.get(cells[0].lower(), section)
                continue
            # A table without a heading row: Value, SKU, Note, or Value, Qty, SKU, Type.
            if cols and len(cells) > len(cols):
                # a trailing cell the heading does not name: a note, or empty
                extra = " ".join(x for x in cells[len(cols):] if x)
                cells = cells[:len(cols)] + ([extra] if "note" not in cols else [])
                if "note" in cols and extra:
                    cells[cols.index("note")] = f"{cells[cols.index('note')]} {extra}".strip()
            names = (cols + ["note"])[:len(cells)] if cols and len(cells) in (len(cols), len(cols) + 1) else {3: ["value", "sku", "note"], 4: ["value", "qty", "sku", "type"]}.get(len(cells), [])
            if not names:
                continue
            item = {k: v for k, v in zip(names, cells) if k}
            item["section"] = section
            out.append(item)
    return out


def _value(value: str, section: str) -> str:
    v = value.replace("Ω", "").replace("μ", "u").replace("µ", "u").strip()
    v = re.sub(r"\s*\(.*?\)", "", v)  # '10 nF (.01 µF)'
    if section == "POT":
        m = re.search(r"([\d.]+\s?[kKM]?)\s*(Audio|Log|Linear|Reverse)?", v, re.I)
        if m:
            taper = {"audio": "A", "log": "A", "linear": "B", "reverse": "C"}.get((m.group(2) or "").lower(), "")
            return taper + m.group(1).replace(" ", "")
    return re.sub(r"(?<=\d) (?=[pnumkKM]F?\b|[kKM]$)", "", v)


def item_row(item: dict) -> BomRow | None:
    """A designator-less row: counted ('×2'), or a pot named by its control ('Fuzz control' is Fuzz)."""
    section, value = item.get("section", ""), item.get("value", "")
    kind, note, sku = item.get("type", ""), item.get("note", ""), item.get("sku", "")
    text = f"{value} {kind} {note}"
    if not section:  # a table with no section headings: the row says what it is
        section = ("POT" if re.search(r"\bpot|potentiometer", kind, re.I) else "R" if re.search(r"resistor", kind, re.I) or "Ω" in value
                   else "C" if re.search(r"\bcap", kind, re.I) or re.search(r"\d\s?[pnuµμ]F\b", value) else "")
    if (refs := re.fullmatch(r"(?:Q\d+\s*(?:&|,|and)?\s*)+", value)) and (m := re.fullmatch(r"P-Q(\w+)", sku)):
        item = {**item, "value": m.group(1), "qty": len(re.findall(r"Q\d+", value))}  # 'Q1 & Q2' with the part in the SKU
        value, section = item["value"], "Q"
    if section == "OTHER" or not section:
        if re.search(r"rotary switch|toggle|\bSPDT|\bDPDT", text, re.I) and not re.search(r"footswitch|3PDT|battery", text, re.I):
            category = "SW"
        elif section == "" and re.search(r"diode", text, re.I):
            category = "D"
        elif section == "" and re.search(r"transistor|germanium|silicon|NPN|PNP|JFET", text, re.I):
            category = "Q"
        elif section == "" and re.search(r"op.?amp|\bIC\b|regulator", text, re.I):
            category = "IC"
        elif section == "" and re.search(r"\bLED\b", text):
            category = "LED"
        else:
            return None  # hardware: the board, enclosure, jacks, knobs, wire, battery clip
    else:
        category = section
    if category in ("R", "C") and not re.search(r"\d", value):
        return None  # 'R LED': a resistor chosen to taste
    try:
        qty = int(item.get("qty") or 1)
    except ValueError:
        qty = 1
    ref = f"×{qty}"
    if category == "POT":
        name = re.sub(r"\s*(?:control|knob|pot(?:entiometer)?)\b.*$", "", re.split(r"[.(]", note or kind)[0], flags=re.I).strip()
        if qty == 1 and name and len(name) <= 24 and not re.search(r"\d", name):
            ref = name.title()
        if re.search(r"trim", text, re.I):
            category = "TRIM"
    notes = "; ".join(x for x in (note if category != "POT" else "", f"({sku})" if sku else "") if x)
    return normalize_row(BomRow(ref=ref, value=_value(value, category), part_type=kind if category != "POT" else "Potentiometer",
                                category=category, notes=notes))


def guide_rows(items: list[dict]) -> list[BomRow]:
    """The Mod Electronics PCB guides: one row per designator ('RV2  A10K  16mm ... pot  Level')."""
    rows: list[BomRow] = []
    for it in items:
        ref = it.get("ref", "")
        if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}[A-Z]?", ref):
            continue  # the off-board jacks
        value, kind, note = it.get("value", ""), it.get("type", ""), it.get("note", "")
        if m := re.fullmatch(r"(\d+(?:\.\d+)?[kKM]?)([LAC])", value):
            value = {"L": "B", "A": "A", "C": "C"}[m.group(2)] + m.group(1)  # '10kL' is a linear 10k, B10k
        category = "TRIM" if re.search(r"trim", kind, re.I) else "POT" if re.search(r"poten", kind, re.I) else ""  # 'poteniometer' too
        r = normalize_row(BomRow(ref=ref, value=value.replace("μ", "u").replace("µ", "u"), part_type=kind, category=category,
                                 notes=f'{note} ({it["sku"]})'.strip() if it.get("sku") else note))
        name = re.sub(r"\s*control$", "", note, flags=re.I).strip()
        if category == "POT" and name and len(name) <= 24:
            r.notes = f"{name} control" + (f' ({it["sku"]})' if it.get("sku") else "")
        rows.append(r)
    return rows


def main_body(page: str) -> str:
    start = page.find("<h1")
    end = page.find("Problems with your build", start)
    return page[start:end if end > 0 else len(page)]


def paragraphs(body: str) -> list[str]:
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
        t = clean_text(_html.unescape(re.sub(r"<[^>]+>", "", p)))
        if len(t) > 40 and not re.match(r"Note:|Printable|Problems with", t):
            out.append(t)
    return out


@register
class AmplifiedParts(Adapter):
    vendor = "amplifiedparts"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.f.min_interval = max(self.f.min_interval, 3.0)

    def list_targets(self) -> Iterable[str]:
        page = self.f.get_text(GUIDES) or ""
        for slug in dict.fromkeys(re.findall(r'href="/pedal-guides/(build-project-[^"#?/]+)"', page)):
            if not _SKIP.match(slug):
                yield slug

    def parse(self, slug: str) -> Circuit | None:
        url = f"{GUIDES}/{slug}"
        page = self.f.get_text(url)
        if not page:
            return None
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
        title = clean_text(_html.unescape(re.sub(r"<[^>]+>", "", h1.group(1)))) if h1 else slug
        name = re.sub(r"^Build\s*-\s*Pedal Project:\s*", "", title)
        layout_only = bool(re.search(r"\s-\s(?:Layout(?: Only)?|La\w*)$", name))
        name = re.sub(r"\s+-\s+Layout(?: Only)?$|\s*\(with Video Tutorial\)", "", name).replace("“", '"').replace("”", '"')
        body = main_body(page)
        text = " ".join(paragraphs(body))
        figures = " ".join(dict.fromkeys(re.findall(r"Figure \d+: ([^<\"]+)", body)))
        # The 'layout only' drawings are all stripboard, as is any guide whose figures say so.
        build = ("tagboard" if re.search(r"terminal strip", figures + " " + slug, re.I) else
                 "vero" if layout_only or re.search(r"strip ?board", figures + " " + slug, re.I) else "turret")
        items = table_items(body)
        bom = [r for it in items if (r := item_row(it))]
        board = next((it["value"] for it in items if it.get("section") == "OTHER" and re.search(r"\bboard\b", it.get("type", ""), re.I)
                      and re.match(r"\d+\s?x\s?\d+", it.get("value", ""))), "")
        images = [u for u in dict.fromkeys(re.findall(r'<img[^>]+src="([^"]+/tech_corner/img/[^"]+)"', body))]
        photo = next((u for u in images if not u.endswith(".svg")), images[0] if images else "")
        layout_svg = next((u for u in images if u.endswith(".svg")), "")
        key = slug.removeprefix("build-project-")
        c = Circuit(vendor=self.vendor, slug=key, name=name, url=url, based_on=BASED_ON.get(key, ""), description=text[:3000],
                    category=_CATEGORY.get(key) or classify(name, text[:400]), price=None, currency="USD", doc_url=url, image_url=photo,
                    enclosure=find_enclosure(" ".join(it.get("value", "") + " " + it.get("sku", "") for it in items) + " " + text),
                    tags=["layout only"] if layout_only else [])
        board = re.match(r"\d+\s?x\s?\d+", board).group(0).replace(" ", "") if board else ""
        c.layout = {"build": build, **({"board": board} if board else {})}
        if layout_svg:
            c.extra_docs["Layout drawing"] = layout_svg
        c.bom = bom
        c.controls = [r.ref for r in bom if r.category == "POT" and not r.ref.startswith("×")]
        return c
