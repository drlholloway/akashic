"""Sheepylove's GitHub repository of layouts for dylan159 (Bent Fishbowl) designs: a root
README bullet per board, a gerber zip and a layout render each, a CSV parts list and
schematic image for a few. Nine of the twelve are not sold in the Sheepylove shop."""
from __future__ import annotations

import csv
import io
import re
from typing import Iterable

from ..gsheet import grid_bom
from ..models import Circuit
from ..models import BomRow
from ..normalize import normalize_row
from ..pdf import _CONTROL_WORDS, _ocr_word_boxes
from ..taxonomy import classify
from . import register
from .base import Adapter, clean_text

REPO = "szukalski/pedal-dylan159"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
TREE = f"https://github.com/{REPO}/tree/main"
_BULLET = re.compile(r"^\*\s+\[([^\]]+)\]\(/([^/)]+)/\)\s+is the\s+\[([^\]]+)\]\(([^)]+)\)(.*)$")
# The classic each board goes back to, where the README names one; else the dylan159 circuit.
_BASED_ON = {"argali": "EQD Plumes", "biggermuff": "EHX Big Muff", "bleepsheep": "", "bluesheep": "Boss BD-2 Blues Driver",
             "coreshaper": "Dylan159 Core Shaper", "katahdin": "Fairfield Circuitry Barbershop", "pelota2": "Dylan159 Pelota 2",
             "sarda": "Klon Centaur", "shornsheep": "Fuzz Face", "thatdrive": "Dylan159 that Overdrive",
             "topazsheep": "Dylan159 Sapphire Amp", "uggsy": "Dylan159 Boot Boost"}
_CATEGORY = {"bleepsheep": "Utility", "coreshaper": "EQ / Filter", "topazsheep": "Preamp / Amp-in-a-box", "uggsy": "Boost", "pelota2": "Delay",
             "argali": "Overdrive", "katahdin": "Overdrive", "bluesheep": "Overdrive", "sarda": "Overdrive", "thatdrive": "Overdrive"}


_TAPER = re.compile(r"^[ABCW][0-9IlLO]{1,3}[kKM]$")
_SWITCH = re.compile(r"^(?:ON/(?:OFF/)?ON|[SD]P[SD]T)$", re.I)
_NAME_STOP = {"LED", "OUT", "IN", "GND", "VCC", "PCB", "CC", "BY", "NC", "SA", "BASED", "DESIGN", "AND", "THE", "FOR", "VER", "CLR", "LEDR", "TLO", "DIP"}


def _fix_taper(t: str) -> str:
    return t[0].upper() + t[1:-1].replace("I", "1").replace("l", "1").replace("L", "1").replace("O", "0") + t[-1].upper()


def render_controls(png) -> list[BomRow]:
    """Pot and switch names printed on a board render next to their taper or type. The render
    is white on red, so it is read inverted, at 2x, upright and turned for sideways labels;
    the nearest name within a quarter of the board width pairs with each value."""
    import pymupdf as fitz
    pix = fitz.Pixmap(str(png))
    gray = fitz.Pixmap(fitz.csGRAY, pix) if pix.n - pix.alpha >= 3 else pix
    gray.invert_irect()
    inv = png.with_name(png.stem + "-inv.png")
    gray.save(inv)
    with fitz.open(inv) as d:
        up = png.with_name(png.stem + "-inv-x2.png")
        d[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(up)
    width = gray.width * 2
    found: dict[str, tuple[str, str]] = {}
    for rotate in (0, 90, 270):
        words = _ocr_word_boxes(up, rotate)
        names = [w for w in words if re.fullmatch(r"[A-Z]{3,12}", w[4]) and w[4] not in _NAME_STOP
                 and (w[4] in _CONTROL_WORDS or len(w[4]) >= 5)  # a short word we do not know as a knob is an OCR fragment
                 and not _TAPER.match(w[4]) and not re.fullmatch(r"[ABCW][IO0-9]{1,4}[KM]?", w[4])]
        for w in words:
            if _TAPER.match(w[4]):
                kind, value = "POT", _fix_taper(w[4])
            elif _SWITCH.match(w[4]):
                kind, value = "SW", w[4].upper()
            else:
                continue
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            best = None
            for n in names:
                nx, ny = (n[0] + n[2]) / 2, (n[1] + n[3]) / 2
                d = ((nx - cx) ** 2 + (ny - cy) ** 2) ** 0.5
                if d <= width / 4 and (best is None or d < best[0]):
                    best = (d, n[4])
            if best:
                name = best[1].title()
                if name not in found or (name in found and found[name][0] == "SW" and kind == "POT"):
                    found[name] = (kind, value)
    return [normalize_row(BomRow(ref=n, value=v, part_type="Potentiometer" if k == "POT" else "Switch", category=k, notes="from the board render"))
            for n, (k, v) in found.items()]


@register
class SheepyGit(Adapter):
    vendor = "sheepygit"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.meta: dict[str, dict] = {}
        self.files: list[str] = []

    def list_targets(self) -> Iterable[str]:
        import json
        raw = self.f.get_text(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1", ".json")
        if raw:
            try:
                self.files = [t["path"] for t in json.loads(raw).get("tree", []) if t.get("type") == "blob"]
            except ValueError:
                pass
        readme = self.f.get_text(f"{RAW}/README.md", ".md") or ""
        for line in readme.splitlines():
            m = _BULLET.match(line.strip())
            if m:
                name, folder, circuit, link, rest = m.groups()
                self.meta[folder] = {"name": name, "circuit": circuit, "link": link, "rest": clean_text(rest.strip(" ,."))}
                yield folder

    def parse(self, folder: str) -> Circuit | None:
        meta = self.meta.get(folder)
        if not meta:
            return None
        files = [p for p in self.files if p.startswith(folder + "/")]
        gerbers = [p for p in files if p.endswith(".zip") and "faceplate" not in p]
        if not gerbers:
            return None
        name = clean_text(meta["name"])
        circuit = clean_text(meta["circuit"])
        desc = f"A layout of dylan159's {circuit}" + (f", {meta['rest']}" if meta["rest"] else "") + ". Designed for JLCPCB; verified working by the author."
        m = re.search(r"_v(\d+(?:\.\d+)*)", gerbers[0])
        c = Circuit(vendor=self.vendor, slug=folder, name=name, url=f"{TREE}/{folder}", based_on=_BASED_ON.get(folder, f"Dylan159 {circuit}"),
                    description=desc, price=None, currency="USD", in_stock=None, doc_url=f"{TREE}/{folder}", doc_version=m.group(1) if m else "")
        c.extra_docs["Gerbers"] = f"https://github.com/{REPO}/raw/main/{gerbers[0]}"
        for p in files:
            base = p.rsplit("/", 1)[-1]
            if p.endswith(".zip") and "faceplate" in p:
                c.extra_docs["Faceplate gerbers"] = f"https://github.com/{REPO}/raw/main/{p}"
            elif "schematic" in base:
                c.extra_docs["Schematic"] = f"{RAW}/{p}"
            elif base.endswith(".csv"):
                c.extra_docs["Parts list (CSV)"] = f"{RAW}/{p}"
            elif base.endswith(".pdf"):
                c.extra_docs["Parts list (PDF)"] = f"{RAW}/{p}"
        c.extra_docs[f"{circuit} at Bent Fishbowl" if "bentfishbowl" in meta["link"] else f"{circuit} thread"] = meta["link"]
        renders = [p for p in files if p.endswith(".png") and "faceplate" not in p and "schematic" not in p and "resdef" not in p]
        if renders:
            c.image_url = f"{RAW}/{renders[0]}"
        csvs = [p for p in files if p.endswith(".csv")]
        if csvs:
            raw = self.f.get_text(f"{RAW}/{csvs[0]}", ".csv") or ""
            rows, _ = grid_bom(list(csv.reader(io.StringIO(raw))))
            c.bom = rows
        if not any(r.category in ("POT", "SW") for r in c.bom):
            # Pot names and tapers are printed on the board render next to each other.
            for p in renders[:1]:
                png = self.f.get_file(f"{RAW}/{p}", ".png")
                if png:
                    have = {r.ref.upper() for r in c.bom}
                    c.bom.extend(r for r in render_controls(png) if r.ref.upper() not in have)
        c.category = _CATEGORY.get(folder) or classify(name, c.based_on, circuit + ". " + meta["rest"])
        c.controls = [r.ref for r in c.bom if r.category == "POT"] + [r.ref for r in c.bom if r.category == "SW"]
        c.tags = ["dylan159"]
        return c
