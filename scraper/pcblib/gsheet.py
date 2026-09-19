"""Parts lists kept in a Google Sheet (Lectric-FX): fetch the workbook as xlsx and read
every tab as designator / value rows."""
from __future__ import annotations

import re
from pathlib import Path

from .models import BomRow
from .normalize import is_plausible, normalize_row

_ID = re.compile(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")
_REF = re.compile(r"^(?:R|C|D|Q|IC|U|L|SW|LED|VR|TR|CLR|LEDR|RPD)\d{0,3}[A-Z]?$", re.I)
_POTVAL = re.compile(r"^(?:[ABCW]\s?\d+(?:[.,]\d+)?[kKM]?|\d+(?:[.,]\d+)?[kKM]?\s?[ABCW]|\d+(?:[.,]\d+)?[kKM]?\s*trim)(?:\s.*)?$", re.I)


def sheet_id(url: str) -> str:
    m = _ID.search(url)
    return m.group(1) if m else ""


def sheet_bom(fetcher, url: str) -> list[BomRow]:
    """Every tab's rows whose first cell is a designator (or a control name with a taper
    value) and whose second cell is a value. A third cell becomes the note."""
    sid = sheet_id(url)
    if not sid:
        return []
    try:
        import openpyxl
    except ImportError:
        return []
    path: Path | None = fetcher.get_file(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx", ".xlsx")
    if not path or path.read_bytes()[:2] != b"PK":
        return []
    rows: list[BomRow] = []
    seen: set[str] = set()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for raw in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in raw if c not in (None, "") and str(c).strip()]
            if len(cells) < 2:
                continue
            ref, value = cells[0], cells[1]
            note = " ".join(cells[2:4]) if len(cells) > 2 else ""
            if ref.upper() in seen:
                continue
            if _REF.match(ref):
                cat = ""
            elif re.fullmatch(r"[A-Za-z][A-Za-z0-9 .\-/]{1,14}", ref) and _POTVAL.match(value):
                cat = "TRIM" if "trim" in (ref + value).lower() else "POT"
            elif re.fullmatch(r"[A-Za-z][A-Za-z0-9 .\-/]{1,14}", ref) and re.search(r"[SD]P[SD]T|\dP\dT|3PDT|4PDT|toggle|rotary", value, re.I):
                cat = "SW"
            else:
                continue
            m_or = re.match(r"^(\S+)\s+or\s+(.+?)\s*\**$", value)  # "NE570 or NE571 or v571"
            if m_or and cat == "":
                value, note = m_or.group(1), (f"or {m_or.group(2)}" + (f"; {note}" if note else ""))
            nr = normalize_row(BomRow(ref=ref.upper() if cat != "SW" else ref.title(), value=value, notes=note, category=cat))
            if is_plausible(nr) or cat in ("SW", "POT", "TRIM"):
                seen.add(ref.upper())
                rows.append(nr)
    wb.close()
    return rows
