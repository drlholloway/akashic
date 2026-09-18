"""Read Word (.docx) build documents without a converter: paragraphs, tables and
embedded images straight from the OOXML, plus a parts-list extractor for the
tables vendors draw by hand (designator/value pairs laid out side by side per
part family, sometimes value first with a comma list of designators)."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import BomRow
from .normalize import is_plausible, normalize_row

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_HEADERS = re.compile(
    r"^(resistors?|cap[ais]+[ist]+ors?|capacitors?|diodes?|transistors?|ics?|op-?amps?|pots?|"
    r"potentiometers?|switch(?:es)?|hardware|vactrol|transformer|active components|misc|other|"
    r"[a-z ]+ (?:parts list|bill of materials))$", re.I)
_DESIGNATOR = re.compile(r"^(?:R|C|D|Q|L|IC|U|SW|LED|TR|VR|RV|POT|XFM|VACT|CLR)_?\d*[A-Z]?$", re.I)
_LIST_SEP = re.compile(r"\s*[,/&]\s*")
_POT_VALUE = re.compile(r"^[ABCW]?\s?\d+(?:[.,]\d+)?\s?[kKmM]?(?:\s?(?:ohm|trim|pot|dual|log|lin|rev|[ABCW]))*\s?$", re.I)
_SWITCH_VALUE = re.compile(r"\b[1-4]?P\d?[DST]T\b|\bSP[DS]T\b|\bDP[DS]T\b|toggle|on/(?:off/)?on", re.I)
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 ./_+-]{1,18}$")


def read_docx(path: Path) -> tuple[list[str], list[list[list[str]]], dict[str, bytes]]:
    """Return (paragraphs, tables as rows of cell strings, media name -> bytes)."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        media = {n.rsplit("/", 1)[-1]: z.read(n) for n in z.namelist()
                 if n.startswith("word/media/") and n.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))}
    body = root.find(_W + "body")
    paras: list[str] = []
    tables: list[list[list[str]]] = []
    if body is None:
        return paras, tables, media
    for el in body:
        if el.tag == _W + "p":
            t = "".join(x.text or "" for x in el.iter(_W + "t")).strip()
            if t:
                paras.append(t)
        elif el.tag == _W + "tbl":
            rows = []
            for tr in el.iter(_W + "tr"):
                cells = ["".join(x.text or "" for x in tc.iter(_W + "t")).strip() for tc in tr.findall(_W + "tc")]
                rows.append(cells)
            tables.append(rows)
    return paras, tables, media


def _is_designators(s: str) -> bool:
    parts = [p for p in _LIST_SEP.split(s) if p]
    return bool(parts) and all(_DESIGNATOR.match(p) for p in parts)


def _is_names(s: str) -> bool:
    """Named controls: LOUD, Boost A, HI/LO, 'MORE, LOUD'."""
    if _HEADERS.match(s) or _is_designators(s):
        return False
    parts = [p for p in s.split(",") if p.strip()]
    return bool(parts) and all(_NAME.match(p.strip()) and not re.match(r"^\d", p.strip()) for p in parts)


def _looks_like_value(s: str) -> bool:
    return bool(s) and not _HEADERS.match(s) and not _is_designators(s) and bool(re.search(r"\d|Ge|Si|LED", s))


def _control_category(ref: str, value: str) -> str:
    if _SWITCH_VALUE.search(value):
        return "SW"
    if re.search(r"trim", value, re.I) or re.search(r"trim", ref, re.I):
        return "TRIM"
    return "POT"


def _split_value(raw: str) -> tuple[str, str]:
    """'8k1 (10k)' -> ('8k1', '(10k)'); '1n* (See mod notes)' -> ('1n', 'see mod notes')."""
    v = raw.strip()
    note = ""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", v)
    if m and m.group(1).strip():
        v, note = m.group(1).strip(), m.group(2).strip()
        if re.match(r"^\d", note):
            note = f"or {note}"
    if v.endswith("*"):
        v = v.rstrip("* ")
        note = note or "see mod notes"
    m = re.match(r"^(\d+(?:[.,]\d+)?[pnukKMRr]?\d*)\s*(?:-|–|to)\s*(\d+(?:[.,]\d+)?[pnukKMRr]?\d*)$", v)
    if m:  # "10k-100k": keep the low end, note the range
        v, note = m.group(1), f"{m.group(1)} to {m.group(2)}, to taste"
    return v, note


def docx_bom(tables: list[list[list[str]]]) -> list[BomRow]:
    """Extract designator/value rows from side-by-side parts tables. A designator
    that repeats starts a new variant block, labelled by the one-cell title row
    above it ("Classic", "BIG CLANG", "AILBINI"); rows carry that label when the
    table has more than one block."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    block = 0
    labels: list[str] = []
    title = ""
    for table in tables:
        for cells in table:
            cells = [c.strip() for c in cells]
            filled = [c for c in cells if c]
            if len(filled) == 1 and not _HEADERS.match(filled[0]) and not _is_designators(filled[0]) and len(filled[0]) <= 24 \
                    and not re.search(r"parts list|bill of materials", filled[0], re.I):
                title = filled[0]  # a block title row
                continue
            if any(_is_designators(c) and c in seen for c in cells):
                block += 1  # the designators start again: a new variant of the same board
                seen.clear()
                labels.append(title)
                title = ""
            elif block == 0 and not labels and filled and any(_is_designators(c) for c in cells):
                labels.append(title)
                title = ""
            i = 0
            while i < len(cells) - 1:
                a, b = cells[i], cells[i + 1]
                if not a or not b:
                    i += 1
                    continue
                pair: list[tuple[str, str, str]] = []  # (ref, value, category)
                if _is_designators(a) and not _is_designators(b) and _looks_like_value(b):
                    pair = [(r, b, "") for r in _LIST_SEP.split(a) if r]
                elif _is_designators(b) and not _is_designators(a) and _looks_like_value(a):
                    pair = [(r, a, "") for r in _LIST_SEP.split(b) if r]
                elif _is_names(a) and (_POT_VALUE.match(b) or _SWITCH_VALUE.search(b)):
                    pair = [(n.strip(), b, _control_category(n, b)) for n in a.split(",") if n.strip()]
                elif _is_names(b) and (_POT_VALUE.match(a) or _SWITCH_VALUE.search(a)) and not _looks_like_value(b):
                    pair = [(n.strip(), a, _control_category(n, a)) for n in b.split(",") if n.strip()]
                if not pair:
                    i += 1
                    continue
                for ref, value, cat in pair:
                    ref = ref.strip().replace("_", "")
                    if ref in seen or ref == "*":
                        continue
                    seen.add(ref)
                    v, note = _split_value(value)
                    if cat == "" and re.match(r"^VACT", ref, re.I):
                        cat = "OPTO"
                    nr = normalize_row(BomRow(ref=ref, value=v, notes=note, category=cat, variant=str(block)))
                    if is_plausible(nr):
                        rows.append(nr)
                i += 2
    if block == 0:
        for r in rows:
            r.variant = ""
    else:
        names = [lab or f"Variant {i + 1}" for i, lab in enumerate(labels)]
        for r in rows:
            r.variant = names[int(r.variant)] if int(r.variant) < len(names) else f"Variant {int(r.variant) + 1}"
    return rows
