"""Fill what a parts list leaves out from the schematic: pot and switch names for the
controls, and, when the parts list itself was an image the OCR could not read, the
designators and values. Runs after every adapter, only for boards that need it, and
never overwrites a row that came from a text table."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .db import VENDOR_KIND
from .models import BomRow, Circuit
from .paths import CACHE_DIR, DATA_DIR
from .pdf import _CONTROL_WORDS, ocr_schematic_bom, render_page, schematic_bom


def _one_off(a: str, b: str) -> bool:
    """Same length, exactly one character different: an OCR misread of the other."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1

_DESIG = re.compile(r"^(?:[A-Z]{1,4}\d{1,3}[A-Z]?|×\d+)$")
_KNOBS = re.compile(r"^\d+ knobs?$|^Toggle switch$", re.I)


def _named(rows: list[BomRow], cats=("POT", "SW", "TRIM")) -> list[BomRow]:
    return [r for r in rows if r.category in cats and not _DESIG.match(r.ref)]


def schematic_parts(pdf: Path, page_no: int, cache: Path) -> list[BomRow]:
    """Designator/value and name/taper pairs from a schematic page: the vector text when the
    page has it, otherwise OCR at two resolutions with the results unioned by ref. Cached."""
    if cache.exists():
        return [BomRow(**d) for d in json.loads(cache.read_text())]
    rows = schematic_bom(pdf, page_no)
    if len(rows) < 5 or not _named(rows):
        by_ref = {r.ref: r for r in rows}
        for dpi, scale in ((170, 2), (300, 1)):
            png = cache.with_name(cache.stem + f"-{dpi}.png")
            if not png.exists():
                render_page(pdf, page_no, png, dpi=dpi, max_px=6000)
            for r in ocr_schematic_bom(png, scale=scale, px_per_pt=dpi / 72):
                by_ref.setdefault(r.ref, r)
        rows = list(by_ref.values())
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([r.__dict__ for r in rows]))
    return rows


def enrich_from_schematic(c: Circuit) -> None:
    """Apply the schematic pairs to a parsed circuit when its parts list is thin, names no
    pots, or its controls are missing or only a knob count."""
    if not c.doc_local or not c.schematic_page or VENDOR_KIND.get(c.vendor) in ("archive", "projects"):
        return  # an archive's scans are already OCR'd by its own adapter; the pairing would cost hours for little
    pdf = DATA_DIR / c.doc_local
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        return
    thin = len(c.bom) < 8
    quantity_only = bool(c.bom) and all(r.ref.startswith("×") for r in c.bom)
    no_names = not c.controls or all(_KNOBS.match(x) for x in c.controls)
    if not (thin or quantity_only or (no_names and not _named(c.bom))):
        return
    rows = schematic_parts(pdf, c.schematic_page, CACHE_DIR / c.vendor / f"{c.slug}-schparts.json")
    if not rows:
        return
    have = {r.ref.upper() for r in c.bom}
    names = [r for r in _named(rows) if r.ref.upper() not in have]
    known = {r.ref.upper() for r in names if r.ref.upper() in _CONTROL_WORDS}
    names = [r for r in names if r.ref.upper() in known or not any(_one_off(r.ref.upper(), k) for k in known)]  # "Tome" beside "Tone"
    pots = [r for r in names if r.category == "POT"]
    if pots and no_names:
        counted = sum(int(m.group(1)) for x in c.controls for m in [re.match(r"^(\d+) knobs?$", x)] if m)
        if not counted or len(pots) >= counted:
            c.controls = [r.ref for r in pots] + [r.ref for r in names if r.category == "SW"]
            listed = [r for r in c.bom if r.category == "POT" and r.ref.startswith("×")]
            if len(pots) >= sum(int(r.ref[1:]) for r in listed):
                c.bom = [r for r in c.bom if r not in listed]
            c.bom.extend(names)
    if thin:
        c.bom.extend(r for r in rows if r.ref.upper() not in have and r not in names)
