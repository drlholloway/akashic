"""Hand corrections to parts rows that no parser rule can make, each checked against the source
document by a person. Applied whenever a board is stored (db.upsert_circuit), after every parser has
run, so a rescrape keeps them. A value of None removes the row. Add a line per report, with where it
came from; remove it when a parser learns to read the board right.

    CORRECTIONS[circuit_id][designator] = corrected value, or None to drop the row
"""
from __future__ import annotations

from .models import BomRow
from .normalize import normalize_row

CORRECTIONS: dict[str, dict[str, str | None]] = {
    # Dead End FX Zuul: OCR reads IC3 as 'LhI3Z24' (reported 2026-09-29).
    "deadendfx:zuul": {"IC3": "LM324"},
}


def apply(circuit_id: str, bom: list[BomRow]) -> list[BomRow]:
    fixes = CORRECTIONS.get(circuit_id)
    if not fixes:
        return bom
    out: list[BomRow] = []
    for r in bom:
        if r.ref in fixes:
            value = fixes[r.ref]
            if value is None:
                continue
            if r.value != value:
                r.value, r.category, r.norm_value = value, "", ""
                r.notes = "; ".join(n for n in (r.notes, "corrected by hand") if n)
                normalize_row(r)
        out.append(r)
    return out
