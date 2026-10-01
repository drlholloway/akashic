"""Hand corrections to parts rows that no parser rule can make, each checked against the source
document by a person. Applied whenever a board is stored (db.upsert_circuit), after every parser has
run, so a rescrape keeps them. A value of None removes the row; a value for a row the parsers missed
adds it, after the nearest lower designator of its kind. Add a line per report, with where it came
from; remove it when a parser learns to read the board right.

    CORRECTIONS[circuit_id][designator] = corrected value, or None to drop the row
    CORRECTIONS[circuit_id][(variant, designator)] = the same, for one build variant only
    (designators match regardless of case: 'CLEAN' corrects a knob stored as 'Clean')
"""
from __future__ import annotations

import re

from .models import BomRow
from .normalize import normalize_row

Key = str | tuple[str, str]

CORRECTIONS: dict[str, dict[Key, str | None]] = {
    # Dead End FX Zuul: OCR reads IC3 as 'LhI3Z24' (reported 2026-09-29).
    "deadendfx:zuul": {"IC3": "LM324"},
    # Dead End FX 2952: the schematic prints CLEAN A15K, the parts table A20K; A20K is right (reported 2026-09-29).
    "deadendfx:2952": {"CLEAN": "A20K"},
    # Moonn Kloppe Gerät: the build doc itself prints 1A34A, a typo for the 1N34A germanium diode (reported 2026-09-30).
    "moonn:kloppe-gerat": {"D1": "1N34A**", "D2": "1N34A**"},
    # Lectric-FX Mongrel: grid OCR misreads D1, R18 and C10 and pairs two junk IC rows (checked 2026-10-01).
    "lectricfx:mongrel": {"D1": "1N4002", "R18": "4K7", "C10": "100uF", "IC6": None, "IC16": None},
    # Five Cats Rattus: Vision reads the RAT's C13 1µF as 1pF and skips cells that are not plain
    # values: RAT2 R1, Turbo RAT C7, C9 and its LED clippers (checked 2026-10-01).
    "fivecats:rattus-rat-rat2-you-dirty-rat-turbo-rat-clone": {
        ("RAT", "C13"): "1µF",
        ("RAT2", "R1"): "47r or 100r",
        ("Turbo RAT", "C7"): "2.2µF",
        ("Turbo RAT", "C9"): "4.7µF",
        ("Turbo RAT", "D2"): "5mm Red LED",
        ("Turbo RAT", "D3"): "5mm Red LED",
    },
    # Experimentalists Anonymous scans: values a wider pairing pass found and lost again, plus pin
    # numbers and pin names paired as values, each read off the drawing (checked 2026-10-01).
    "expanon:vibrato-and-pitch-shift-boss-oc-2": {
        "Q1": None, "Q2": None,  # MC14013 / MC14027 pin names, not transistors
        "R17": "1M", "R18": "1M", "R19": "47K", "R28": "47K", "R30": "47K", "R48": "470K", "R52": "10k",
    },
    "expanon:filters-wahs-and-vcfs-tau-1010-ladder-filter": {
        "R2": "100K", "R6": "100K", "R7": "12K", "R15": "100K", "R18": "6.8K", "R21": "91K", "R29": "26K",
        "R34": "680", "C1": "0.01uF", "C2": "0.01uF", "C3": "0.01uF", "C4": "0.01uF", "C5": "18pF", "C6": "18pF",
        "C7": "0.05uF", "D1": "1N4148", "D2": "1N4148", "U1": "LM301A",
    },
    # A clean CAD drawing of which the pairing read 14 rows, two of them wrong (R16 1100k, R20 122k).
    "expanon:phasers-univox-microphaser": {
        **{f"R{n}": "100k" for n in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19)},
        "R1": "220k", "R2": "220k", "R3": "470k", "R17": "2k2", "R18": "1k", "R20": "22k", "R22": "47k",
        "R24": "2k7", "R25": "3k3", "R31": "1M",
        **{f"C{n}": "50n" for n in range(1, 6)},
        "C6": "1µ", "C7": "33µ", "C8": "10µ", "C9": "4µ7 Ta", "D1": "ZPD 4V7", "BIAS": "100k trim",  # TP1, labeled BIAS
        **{f"Q{n}": "2SK34D" for n in range(1, 5)}, **{f"OP{n}": "1458" for n in range(1, 7)},
        "RATE": "A1M",
    },
}

_NOTE = "corrected by hand"


def _split(ref: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref.upper())
    return (m.group(1), int(m.group(2))) if m else (ref.upper(), -1)


def _insert_at(bom: list[BomRow], variant: str, ref: str) -> int:
    """Index after the nearest lower designator of the same kind in the variant, else after the
    variant's last row, else at the end."""
    prefix, num = _split(ref)
    best, last = -1, -1
    for i, r in enumerate(bom):
        if r.variant != variant:
            continue
        last = i
        p, n = _split(r.ref)
        if p == prefix and n < num:
            best = i
    return (best if best >= 0 else last) + 1 if last >= 0 else len(bom)


def apply(circuit_id: str, bom: list[BomRow]) -> list[BomRow]:
    fixes: dict[tuple[str | None, str], str | None] = {}
    for k, v in (CORRECTIONS.get(circuit_id) or {}).items():
        variant, ref = k if isinstance(k, tuple) else (None, k)
        fixes[(variant, ref.upper())] = v
    if not fixes:
        return bom
    seen: set[tuple[str | None, str]] = set()
    out: list[BomRow] = []
    for r in bom:
        key = (r.variant, r.ref.upper()) if (r.variant, r.ref.upper()) in fixes else (None, r.ref.upper())
        if key in fixes:
            seen.add(key)
            value = fixes[key]
            if value is None:
                continue
            if r.value != value:
                r.value, r.category, r.norm_value = value, "", ""
                r.notes = "; ".join(n for n in (r.notes, _NOTE) if n)
                normalize_row(r)
        out.append(r)
    for (variant, ref), value in fixes.items():
        if value is None or (variant, ref) in seen:
            continue
        row = normalize_row(BomRow(ref=ref, value=value, notes=_NOTE, variant=variant or ""))
        out.insert(_insert_at(out, row.variant, ref), row)
    return out
