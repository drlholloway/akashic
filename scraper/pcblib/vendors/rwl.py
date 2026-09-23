"""RWL Pedals adapter: a GitHub repository of KiCad pedal layouts with gerbers to send to a
fab. The root README's two tables name every board, its type and the circuit it is based on;
each project README carries a markdown parts table (or an interactive BOM as a fallback),
the enclosure, a gerber zip and the schematic image."""
from __future__ import annotations

import json
import re
from typing import Iterable

from ..ibom import parse_ibom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

REPO = "RWLPedal/music-pcbs"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
TREE = f"https://github.com/{REPO}/tree/main"
_ROW = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.*)$")
_TYPE_CATEGORY = {"PLL": "Octave / Pitch", "Acoustic Simulator": "EQ / Filter", "Preamp": "Preamp / Amp-in-a-box", "Harmonic Tremolo": "Tremolo",
                  "Envelope Filter": "EQ / Filter", "Boost & Buffer": "Boost", "Dirty Boost": "Boost", "Treble Boost": "Boost", "Octave Overdrive": "Overdrive"}
_POTVAL = re.compile(r"^[ABCW]\d+(?:\.\d+)?[kKM]?$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _md_text(s: str) -> str:
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return clean_text(re.sub(r"[*_`]", "", s))


_REFCOL = ("references", "reference", "ref", "part", "component", "component number", "designator")
_STDCOL = ("value", "type", "description", "notes", "note", "qty", "quantity")


def _row(ref: str, value: str, ptype: str, note: str, variant: str = "") -> BomRow | None:
    """One BOM row from a README or interactive-BOM entry: designators as they are, named pots
    and switches title-cased ('BASS_CUT' -> 'Bass Cut', 'VOL1' -> 'Vol', 'SW1: CLIP' -> 'Clip')."""
    value = value.replace("\\", "").strip()
    ref = re.sub(r"\s+potentiometer$", "", ref.replace("\\", "").strip(), flags=re.I)
    if re.fullmatch(r"(?:SW|S)\d+", ref) and re.fullmatch(r"[A-Za-z][A-Za-z _/-]{2,15}", value) and not re.match(r"^(?:SW_)?[SD]P[SD]T", value, re.I):
        ref, value = value, "SPDT"  # KiCad: the switch's name sits in its value
    if re.fullmatch(r"[A-Z]{1,4}\d{1,3}[A-Z]?", ref) and not re.fullmatch(r"[A-Z]{3,}\d", ref):
        cat = ""
    elif re.match(r"^SW_|^[SD]P[SD]T|switch", value + " " + ptype, re.I) and not _POTVAL.match(value):
        cat, value = "SW", re.sub(r"^SW_", "", value)
        ref = re.sub(r"(?<=[A-Za-z]{3})\d$", "", ref).replace("_", " ").title()
    elif _POTVAL.match(value) or re.search(r"potentiometer", ptype, re.I):
        cat = "TRIM" if re.search(r"trim", ptype, re.I) else "POT"
        ref = re.sub(r"(?<=[A-Za-z]{3})\d$", "", ref).replace("_", " ").title()
    elif re.fullmatch(r"[A-Z]{3,}\d", ref):
        cat = ""  # an annotated name with an ordinary value: keep as a designator
    else:
        return None
    nr = normalize_row(BomRow(ref=ref, value=value, part_type=ptype, notes=note, category=cat, variant=variant))
    return nr if cat or is_plausible(nr) else None


def _label(cell: str) -> str:
    """'Green ringer value' -> 'Green Ringer'; 'Sunn O))) value' -> 'Sunn O)))'."""
    v = re.sub(r"\s+value$", "", cell, flags=re.I).strip()
    return " ".join(w if any(ch.isupper() for ch in w[1:]) or not w[0].isalpha() else w.capitalize() for w in v.split())


def _md_bom(md: str) -> list[BomRow]:
    """The README's '| References | Value | Type | Notes |' table, or a per-build table
    ('| Component Number | 1966 | ColorSound | Meathead | Note |') whose value columns become
    variants."""
    rows: list[BomRow] = []
    seen: set[tuple[str, str]] = set()
    cols: list[str] = []
    variants: list[str] = []
    for line in md.splitlines():
        if not line.strip().startswith("|"):
            if cols and rows:
                break
            continue
        cells = [c.strip("* ") for c in _cells(line)]
        low = [c.lower() for c in cells]
        if any(c in _REFCOL for c in low) and ("value" in low or len(cells) >= 3):
            cols = low
            variants = [_label(cells[i]) for i, c in enumerate(low) if c not in _REFCOL and c not in _STDCOL and c]
            if "value" in low or len(variants) < 2:
                variants = []
            continue
        if not cols or set("".join(cells)) <= set(":- "):
            continue
        rec = dict(zip(cols, cells))
        refs = next((rec[c] for c in _REFCOL if rec.get(c)), "")
        ptype = rec.get("type") or rec.get("description") or ""
        note = rec.get("notes") or rec.get("note") or ""
        if not refs:
            continue
        values = [(rec.get("value", ""), "")] if not variants else [(next((rec[c] for c in cols if _label(c).lower() == v.lower()), ""), v) for v in variants]
        for ref in re.split(r"\s*,\s*", refs):
            for value, variant in values:
                if not ref or not value or (ref.upper(), variant) in seen:
                    continue
                nr = _row(ref, value, ptype, note, variant)
                if nr:
                    seen.add((ref.upper(), variant))
                    rows.append(nr)
    return rows


@register
class RWL(Adapter):
    vendor = "rwlpedal"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.meta: dict[str, dict] = {}
        self.files: set[str] = set()

    def list_targets(self) -> Iterable[str]:
        raw = self.f.get_text(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1", ".json")
        if raw:
            try:
                self.files = {t["path"] for t in json.loads(raw).get("tree", []) if t.get("type") == "blob"}
            except ValueError:
                pass
        readme = self.f.get_text(f"{RAW}/README.md", ".md") or ""
        commercial = False
        for line in readme.splitlines():
            if re.search(r"\|\s*Compare to\s*\|", line):
                commercial = True
            elif re.search(r"\|\s*Circuit Name\s*\|", line):
                commercial = False
            m = _ROW.match(line)
            if not m:
                continue
            name, path, rest = m.group(1), m.group(2).strip("/"), _cells("|" + m.group(3))
            if not path or "/" not in path:
                continue
            kind = rest[0] if rest else ""
            if commercial:
                circuit, author = rest[1] if len(rest) > 1 else "", ""
            else:
                circuit, author = (rest[1] if len(rest) > 1 else ""), (rest[2] if len(rest) > 2 else "")
            self.meta[path] = {"name": name, "type": kind, "circuit": circuit, "author": author, "commercial": commercial}
            yield path
        # Boards the root README has not listed yet: any project folder with a README and gerbers.
        folders = sorted({f.rsplit("/", 1)[0] for f in self.files if f.count("/") == 2 and f.endswith("/README.md")})
        for path in folders:
            if path in self.meta or path.startswith(("instructions/", "KiCAD/", "images/")):
                continue
            if not any(f.startswith(path + "/") and f.endswith(".zip") for f in self.files):
                continue
            self.meta[path] = {"name": "", "type": path.split("/")[0], "circuit": "", "author": "", "commercial": True, "from_tree": True}
            yield path

    def parse(self, path: str) -> Circuit | None:
        meta = self.meta.get(path)
        if not meta:
            return None
        md = self.f.get_text(f"{RAW}/{path}/README.md", ".md") or ""
        if not md:
            return None
        slug = path.rsplit("/", 1)[-1]
        slug = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", slug).lower()
        if meta.get("from_tree"):
            h1 = re.search(r"^#\s+(.+)$", md, re.M)
            meta["name"] = h1.group(1).strip() if h1 else re.sub(r"(?<=[a-z])(?=[A-Z])", " ", path.rsplit("/", 1)[-1])
            m0 = re.search(r"based on (?:the |a |an )?\[?([A-Z][^,.\]\n]{2,60}?)(?:\]|,|\.|\s+(?:itself|which|a\b))", md)
            meta["circuit"] = m0.group(1).strip() if m0 else ""
            meta["type"] = {"OverdriveFuzz": "Overdrive", "Pll": "PLL", "Other": ""}.get(meta["type"], meta["type"])
        name = clean_text(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", meta["name"]))  # CrimsonKiwi
        circuit = _md_text(meta["circuit"]).replace('"', "")
        m = re.search(r"\((?:based on|Based on)\s+(?:the\s+)?([^)]+)\)", meta["circuit"])
        author = meta["author"].strip()
        if author.lower() == "dylan159":
            author = "Bent Fishbowl"  # dylan159 publishes as Bent Fishbowl, a source in this library
        if meta["commercial"]:
            based_on = circuit.split("/")[0].strip()
        elif m:
            based_on = clean_text(m.group(1))
        elif circuit.upper() == "N/A":
            based_on = ""
        else:  # a DIY project: name its designer when the project name alone would not place it
            based_on = f"{author} {circuit}" if author and author.upper() != "N/A" and len(circuit.split()) <= 2 and author.lower() not in circuit.lower() else circuit
        based_on = re.sub(r"\s+and more$", "", based_on.replace("'s Preamp", " Preamp")).strip()
        body = md.split("## ", 1)[0] if "## " in md else md
        paras = [p for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith(("#", "![", "[!"))]
        description = _md_text(paras[0]) if paras else ""
        if not meta["commercial"] and author and circuit and circuit.upper() != "N/A":
            description = f"A layout of {author}'s {circuit}. " + description
        text = _md_text(md)
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=f"{TREE}/{path}", based_on=based_on, description=description,
                    price=None, currency="USD", in_stock=None, doc_url=f"{TREE}/{path}",
                    enclosure=find_enclosure(text) or "125B")  # the root README: every board fits a 125B
        c.bom = _md_bom(md)
        folder = {p for p in self.files if p.startswith(path + "/")}
        if f"{path}/interactive_bom.html" in folder and (len(c.bom) < 5 or not any(r.category in ("POT", "SW") for r in c.bom)):
            html = self.f.get_file(f"{RAW}/{path}/interactive_bom.html", ".html")
            if html:
                rows = []
                for r in parse_ibom(html):
                    nr = _row(r.ref, r.value, r.part_type, "interactive BOM")
                    if nr:
                        rows.append(nr)
                if len(rows) > len(c.bom):
                    c.bom = rows
                else:  # the README lists the passives; the interactive BOM knows the pots and switches
                    have = {r.ref.upper() for r in c.bom}
                    c.bom.extend(r for r in rows if r.category in ("POT", "SW") and r.ref.upper() not in have)
        for img in ("images/logo.png", "images/front_guts.png", "images/pcb_front.png"):
            if f"{path}/{img}" in folder:
                c.image_url = f"{RAW}/{path}/{img}"
                break
        if f"{path}/images/schematic.png" in folder:
            c.extra_docs["Schematic"] = f"{RAW}/{path}/images/schematic.png"
        zips = sorted(p for p in folder if p.endswith(".zip"))
        if zips:
            c.extra_docs["Gerbers"] = f"https://github.com/{REPO}/raw/refs/heads/main/{zips[0]}"
        if f"{path}/interactive_bom.html" in folder:
            c.extra_docs["Interactive BOM"] = f"https://html-preview.github.io/?url=https://github.com/{REPO}/blob/main/{path}/interactive_bom.html"
        # The designer's own write-up: dylan159's posts at Bent Fishbowl, or a freestompboxes thread.
        circuit_label = re.sub(r"\s*\(.*\)", "", circuit).strip() or "circuit"
        bf = re.findall(r"\((https://bentfishbowl\.wixsite\.com/electronics/post/[^)\s]+)\)", md)
        fsb = re.findall(r"\((https://www\.freestompboxes\.org/viewtopic\.php\?[^)\s]+)\)", md)
        if bf:
            c.extra_docs[f"{circuit_label} at Bent Fishbowl"] = bf[0]
        elif fsb:
            c.extra_docs[f"{circuit_label} thread at freestompboxes"] = fsb[0]
        pw = re.search(r"\((https://www\.pcbway\.com/project/shareproject/[^)]+)\)", md)
        if pw:
            c.extra_docs["Order at PCBWay"] = pw.group(1)
        m = re.search(r"^\* V?(\d+(?:\.\d+)*)\s*-", md.split("## Versions")[-1], re.M) if "## Versions" in md else None
        c.doc_version = m.group(1) if m else ""
        kind = meta["type"]
        c.category = _TYPE_CATEGORY.get(kind) or classify(name, based_on, f"{kind}. {description}")
        if c.category == "Other":
            c.category = classify(kind, "", "")
        named = [r.ref for r in c.bom if r.category == "POT" and not re.fullmatch(r"(?:RV|VR|P|POT)\d+", r.ref)]
        knobs = len({r.ref for r in c.bom if r.category == "POT"})
        c.controls = (named or ([f"{knobs} knobs" if knobs > 1 else "1 knob"] if knobs else [])) \
            + [r.ref for r in c.bom if r.category == "SW" and not re.fullmatch(r"(?:SW|S)\d+", r.ref)]
        c.controls = list(dict.fromkeys(c.controls))
        c.tags = [t for t in (meta["author"],) if t and t.upper() != "N/A"]
        return c
