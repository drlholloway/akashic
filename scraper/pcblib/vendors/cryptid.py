"""Cryptid Effects: the site owner's own layouts, shared on GitHub (drlholloway/guitar-effects-layouts)
under CC BY-NC-SA 4.0. The repository README lists the pedals (name, status, wiki page, folder); each
folder holds the PCB and faceplate gerbers, renders and a schematic SVG, and each wiki page carries
the Controls table and the BOM as Markdown tables ('Component Name | Value | Note' per part type).
Being the owner's work, the schematic SVG and the finished-pedal photo may be shown on the site."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import owner_schematic
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

REPO = "drlholloway/guitar-effects-layouts"
GITHUB = f"https://github.com/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
WIKI_RAW = f"https://raw.githubusercontent.com/wiki/{REPO}"
API_TREE = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
_BASED_ON = {"Biggus-Dickus": "Chuck D. Bones Biggus Dickus", "Ground-Fault": "Fuzzhugger FX Arc Flash",
             "The-Everlasting-Tantrum": "DOD / Devi Ever Grindhaus"}
_CATEGORY = {"Biggus-Dickus": "Distortion", "Ground-Fault": "Fuzz", "The-Everlasting-Tantrum": "Fuzz"}
_HARDWARE = re.compile(r"jack|footswitch|header|battery|enclosure|knob|^J\d", re.I)


def _tables(md: str) -> list[tuple[str, list[list[str]]]]:
    """Markdown tables with the heading above each: [(heading, rows of cells)], header row first."""
    out: list[tuple[str, list[list[str]]]] = []
    heading, rows = "", []
    for line in md.splitlines() + [""]:
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
        elif rows:
            out.append((heading, rows))
            rows = []
    return out


def _bom(md: str) -> list[BomRow]:
    bom: list[BomRow] = []
    seen: set[str] = set()
    for heading, rows in _tables(md):
        if not rows or [c.lower() for c in rows[0][:2]] != ["component name", "value"]:
            continue
        for cells in rows[1:]:
            ref, value = cells[0], cells[1] if len(cells) > 1 else ""
            note = cells[2] if len(cells) > 2 else ""
            if not value or _HARDWARE.search(ref) or _HARDWARE.search(note if not value else ""):
                continue
            m = re.fullmatch(r"(?:VR|RV|U|SW|S)\d+\s*-\s*(.+)", ref)  # 'VR1 - GAIN', 'U1 - MODE'
            if not m and re.fullmatch(r"[A-Z][A-Z ]+", ref):          # a bare knob name: 'GAIN | 500kB'
                m = re.fullmatch(r"(.+)", ref)
            name = m.group(1).strip().title() if m else ""
            cat, ptype = "", ""
            if re.fullmatch(r"\d+(?:\.\d+)?\s?[kKM]?[ABCW]", value) and name:      # 1kC, 500kB
                taper = value[-1].upper()
                value, cat, ptype = f"{taper}{value[:-1].strip()}", "POT", "Potentiometer"
            elif re.search(r"\b[SD]P[DS]T\b|3PDT|4PDT", value, re.I) and name:
                cat, ptype = "SW", "Switch"
                note = "; ".join(x for x in (note,) if x)
            elif name:
                continue
            elif re.search(r"\btrim", note, re.I):                              # 'RV1 | 1k | Trimmer, bias adjustment'
                cat, ptype = "TRIM", "Trimmer"
            r = BomRow(ref=name or ref, value=value, part_type=ptype, notes=note, category=cat)
            r = normalize_row(r)
            if r.ref.upper() not in seen and (cat or is_plausible(r)):
                seen.add(r.ref.upper())
                bom.append(r)
    return bom


@register
class Cryptid(Adapter):
    vendor = "cryptid"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.pedals: dict[str, dict] = {}
        self.files: list[str] = []

    def list_targets(self) -> Iterable[str]:
        readme = self.f.get_text(f"{RAW}/README.md", ".md") or ""
        tree = self.f.get_text(API_TREE, ".json") or ""
        self.files = re.findall(r'"path":\s*"([^"]+)"', tree)
        for line in readme.splitlines():
            m = re.match(r"\|\s*\*\*(.+?)\*\*\s*-\s*(.+?)\|\s*(.+?)\|\s*\[Wiki page\]\((\S+?)\)\s*\|\s*\[(.+?)/?\]", line)
            if not m:
                continue
            name, blurb, status, wiki, folder = (clean_text(g) for g in m.groups())
            folder = folder.strip("/")
            self.pedals[folder] = {"name": name, "blurb": blurb, "status": status, "wiki": wiki}
            yield folder

    def parse(self, folder: str) -> Circuit | None:
        p = self.pedals.get(folder)
        if not p:
            return None
        files = [f for f in self.files if f.startswith(folder + "/")]
        page = p["wiki"].rsplit("/", 1)[-1]
        md = self.f.get_text(f"{WIKI_RAW}/{page}.md", ".md") or ""
        readme = self.f.get_text(f"{RAW}/{quote(folder)}/README.md", ".md") or ""
        verified = not re.search(r"not verified", p["status"], re.I)
        intro = re.search(r"## Introduction\s*\n(.+?)(?:\n##|\n###)", md, re.S)
        description = clean_text(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", re.sub(r"\*\*", "", intro.group(1) if intro else p["blurb"])))
        c = Circuit(vendor=self.vendor, slug=re.sub(r"[^a-z0-9]+", "-", folder.lower()).strip("-"), name=p["name"],
                    url=f"{GITHUB}/tree/main/{quote(folder)}", doc_url=p["wiki"], description=description[:900],
                    based_on=_BASED_ON.get(folder, ""), price=None, currency="USD", in_stock=None,
                    enclosure=find_enclosure(readme) or find_enclosure(md),
                    tags=["verified" if verified else "not verified", "gerbers", "faceplate", "CC BY-NC-SA 4.0"])
        c.category = _CATEGORY.get(folder) or classify(p["name"], c.based_on, description[:300])
        photo = next((f for f in files if f.endswith("-complete.jpg")), "") or next((f for f in files if f.endswith("-faceplate.png")), "")
        c.image_url = f"{RAW}/{quote(photo)}" if photo else ""
        for f in files:
            base = f.rsplit("/", 1)[-1]
            if base.lower().endswith(".zip"):
                label = "Faceplate gerbers" if "faceplate" in base.lower() else "PCB gerbers"
                c.extra_docs[label] = f"{GITHUB}/raw/main/{quote(f)}"
        drill = re.search(r"\((https://drill\.taydakits\.com/[^)\s]+)\)", md)
        if drill:
            c.extra_docs["Tayda drill template"] = drill.group(1)
        c.bom = _bom(md)
        controls = [r[0].strip().title() for h, rows in _tables(md) if rows and rows[0][:1] == ["Control"] for r in rows[1:] if r and r[0].strip()]
        c.controls = controls or [r.ref for r in c.bom if r.category == "POT"]
        svg_name = next((f for f in files if f.endswith("-schematic.svg")), "")
        if svg_name:
            svg = self.f.get_file(f"{RAW}/{quote(svg_name)}", ".svg")
            if svg:
                dst = owner_schematic(self.vendor, c.slug)  # the export serves it (the owner's own drawing)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(svg.read_bytes())
        return c
