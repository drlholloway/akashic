"""Parts lists kept in a Google Sheet (Lectric-FX): fetch the workbook as xlsx and read
every tab as designator / value rows."""
from __future__ import annotations

import re
from pathlib import Path

from .models import BomRow
from .normalize import is_plausible, normalize_row

_ID = re.compile(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")
_REF = re.compile(r"^(?:R|C|D|Q|IC|U|L|SW|LED|VR|TR|CLR|LEDR|RPD)\d{0,3}[A-Z]?$", re.I)
_POTVAL = re.compile(r"^(?:[ABCW]\s?\d+(?:[.,]\d+)?[kKM]?|\d+(?:[.,]\d+)?[kKM]?\s?-?\s?[ABCW]|\d+(?:[.,]\d+)?[kKM]?\s*trim)(?:\s.*)?$", re.I)


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


_POTWORD = re.compile(r"^(\d+(?:[.,]\d+)?[kKM]?)\s*(?:Ω|ohms?)?\s+(linear|lin|log|audio|logarithmic|rev-?log|reverse(?: log| audio)?|anti-?log)\b", re.I)
_TAPERS = {"linear": "B", "lin": "B", "log": "A", "audio": "A", "logarithmic": "A", "revlog": "C", "reverse": "C", "reverselog": "C", "reverseaudio": "C", "antilog": "C"}
_XLSX_COLS = {"qty": "qty", "quantity": "qty", "ref": "ref", "refs": "ref", "reference": "ref", "references": "ref", "designator": "ref", "refdes": "ref", "pattern": "package",
              "designators": "ref", "value": "value", "description": "type", "type": "type", "rating/package": "type", "package": "package", "notes": "notes", "note": "notes"}


def grid_bom(grid: list[list[str]]) -> tuple[list[BomRow], str]:
    """A parts table given as rows of cells with a header row naming its columns (Qty / Value /
    Ref / Description, Value / Designator / Quantity ...): one row per designator, comma lists
    split, named pots and switches kept, hardware rows skipped. Returns (rows, enclosure named
    in a hardware row)."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    enclosure = ""
    cols: dict[str, int] = {}
    for raw in grid:
        cells = ["" if c is None else str(c).strip() for c in raw]
        if not any(cells):
            continue
        low = [c.lower() for c in cells]
        if ("value" in low or "name" in low) and any(k in low for k in ("ref", "refs", "refdes", "reference", "references", "designator", "designators", "part #", "part")):
            cols = {_XLSX_COLS[c]: i for i, c in enumerate(low) if c in _XLSX_COLS}
            if "value" not in cols and "name" in low:  # EasyEDA exports call the value 'Name'
                cols["value"] = low.index("name")
            if "ref" not in cols:  # 'PART #' names the designator when nothing else does
                cols["ref"] = next(i for i, c in enumerate(low) if c in ("part #", "part"))
            continue
        if not cols or "ref" not in cols or "value" not in cols or len(cells) <= max(cols["ref"], cols["value"]):
            continue  # a section heading spanning the table is a short row
        refs, value = cells[cols["ref"]], cells[cols["value"]]
        value = re.sub(r"\s*\([^)]*\)\s*$", "", value)  # '10 kΩ log (A10K)', '100 k log (A)'
        value = re.sub(r"^(\d+(?:[.,]\d+)?)\s+([kKM])(?=\s|Ω|$|-)", r"\1\2", value)  # '10 kΩ' -> '10kΩ'
        value = re.sub(r"^(\d+(?:[.,]\d+)?[kKM]?)(?:Ω|ohms?)?-(?=[A-Za-z])", r"\1 ", value)  # '50k-lin' -> '50k lin'; '1k-B' is handled below
        ptype = cells[cols["type"]] if "type" in cols and cols["type"] < len(cells) else ""
        note = cells[cols["notes"]] if "notes" in cols and cols["notes"] < len(cells) else ""
        if not refs or not value:
            continue
        if re.fullmatch(r"enclosure", refs, re.I):
            from .taxonomy import find_enclosure
            enclosure = enclosure or find_enclosure(value)
            continue
        if re.search(r"knob|jack|^in\b|^out\b|^9v|led|battery|wire|screw", refs, re.I) and not _REF.match(refs):
            continue  # hardware
        for ref in re.split(r"\s*,\s*", refs):
            if not ref or ref.upper() in seen:
                continue
            if _REF.match(ref) or re.fullmatch(r"[A-Z]{1,4}\d{1,3}[A-Z]?", ref):
                cat = ""
            elif _POTVAL.match(value) or re.search(r"potentiometer", ptype, re.I) or _POTWORD.match(value):
                cat = "TRIM" if re.search(r"trim", ptype + value, re.I) else "POT"
                mw = _POTWORD.match(value)
                if mw:  # '10kΩ linear', '500kΩ rev-log' -> B10k, C500k
                    value = _TAPERS[re.sub(r"[^a-z]", "", mw.group(2).lower())] + mw.group(1)
            elif re.search(r"[SD]P[SD]T|\dP[SD]T|toggle|rotary|switch", value + " " + ptype, re.I):
                cat = "SW"
            else:
                continue
            v = re.sub(r"^A(\d+(?:\.\d+)?[kKM]?)\s+Rev(?:erse)?\.?$", r"C\1", value, flags=re.I)  # 'A10k Rev': reverse audio
            v = re.sub(r"^(\d+(?:[.,]\d+)?[kKM]?)\s?-\s?([ABCW])$", r"\2\1", v, flags=re.I)  # '1k-B' -> B1k
            if cat in ("POT", "SW", "TRIM") and re.search(r"\s{2,}", v):  # 'A500K    16MM POTENTIOMETER', 'SPDT    ON / ON TOGGLE SWITCH'
                v, tail = re.split(r"\s{2,}", v, 1)
                ptype = ptype or tail
            nr = normalize_row(BomRow(ref=ref.upper() if cat != "SW" else ref.title(), value=v, part_type=ptype, notes=note, category=cat))
            if is_plausible(nr) or cat in ("SW", "POT", "TRIM"):
                seen.add(ref.upper())
                rows.append(nr)
    return rows, enclosure


def xlsx_bom(path: Path) -> tuple[list[BomRow], str]:
    """Every sheet of a spreadsheet BOM through `grid_bom`."""
    try:
        import openpyxl
    except ImportError:
        return [], ""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    grid = [list(r) for ws in wb.worksheets for r in ws.iter_rows(values_only=True)]
    wb.close()
    return grid_bom(grid)
