"""Build-document parsing: parts list extraction and schematic page rendering.

Text extraction uses poppler's `pdftotext -layout` (column alignment preserved),
rendering uses PyMuPDF. Both PedalPCB and AionFX docs share the same table
shape:  LOCATION|PART   VALUE   TYPE   NOTES
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pymupdf as fitz

from .models import BomRow
from .normalize import normalize_row, is_plausible, categorize
from .paths import CACHE_DIR, DATA_DIR

_HEADER_RE = re.compile(r"^\s*(LOCATION|PART|REF(?:ERENCE)?|DESIGNATOR|PART\s*#?)\s+VALUE\s+(TYPE|DESCRIPTION|QUANTITY|QTY)", re.I)
_PAGE_BREAK = "\f"


def pdf_text_pages(pdf: Path) -> list[str]:
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, check=False,
    ).stdout
    return out.split(_PAGE_BREAK)


_ONE_REF = r"[A-Za-z]+\d+[A-Za-z]?(?:\s*-\s*[A-Za-z]*\d+)?"
_REFS_RE = re.compile(rf"{_ONE_REF}(?:\s*,\s*{_ONE_REF})*|[A-Z][A-Z0-9 /.\-]{{1,14}}")


def expand_refs(ref: str) -> list[str]:
    """'C2, C5' -> [C2, C5]; 'D3-D6' / 'D3-6' -> [D3, D4, D5, D6]; 'DRIVE' -> [DRIVE]."""
    out: list[str] = []
    for part in re.split(r"\s*,\s*", ref.strip()):
        m = re.fullmatch(r"([A-Za-z]+)(\d+)([A-Za-z]?)\s*-\s*(?:[A-Za-z]+)?(\d+)", part)
        if m and 0 < int(m.group(4)) - int(m.group(2)) < 60:
            out.extend(f"{m.group(1)}{i}{m.group(3)}" for i in range(int(m.group(2)), int(m.group(4)) + 1))
        elif part:
            out.append(part)
    return out


def _col_starts(header: str) -> dict[str, int]:
    cols = {}
    for name in ("VALUE", "TYPE", "DESCRIPTION", "QUANTITY", "QTY", "NOTES"):
        i = header.upper().find(name)
        if i >= 0:
            cols[name] = i
    if "TYPE" not in cols and "DESCRIPTION" not in cols:
        # Reference / Value / Quantity / Notes layout: the third column is a count, not a type
        q = cols.get("QUANTITY", cols.get("QTY"))
        if q is not None:
            cols["TYPE"] = q
            cols["_QTY_IS_TYPE"] = 1
    return cols


def parse_bom(pages: list[str]) -> list[BomRow]:
    """Find every parts-list table in the document and parse its rows."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        lines = page.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if not _HEADER_RE.match(line):
                i += 1
                continue
            cols = _col_starts(line)
            v0 = cols.get("VALUE")
            t0 = cols.get("TYPE", cols.get("DESCRIPTION"))
            n0 = cols.get("NOTES")
            qty_col = "_QTY_IS_TYPE" in cols
            i += 1
            blank_run = 0
            while i < len(lines):
                ln = lines[i]
                i += 1
                if not ln.strip():
                    blank_run += 1
                    if blank_run > 3:
                        break
                    continue
                blank_run = 0
                if _HEADER_RE.match(ln):
                    cols = _col_starts(ln); v0 = cols.get("VALUE"); t0 = cols.get("TYPE", cols.get("DESCRIPTION")); n0 = cols.get("NOTES")
                    qty_col = "_QTY_IS_TYPE" in cols
                    continue
                # Footer / page-number lines end the table
                if re.search(r"Copyright|Page \d+ of \d+|PARTS LIST|^\s*\S.*\s{6,}\d{1,2}\s*$", ln) and not re.match(rf"^\s*(?:{_ONE_REF}(?:\s*,\s*{_ONE_REF})*|[A-Z]+\d*)\s+\S", ln, re.I):
                    if "Copyright" in ln or re.search(r"Page \d+ of", ln):
                        break
                    continue
                ref = ln[:v0].strip() if v0 else ""
                # Running page footer: "HEXATRON OPTICAL PHASER          4"
                if re.search(r"\s{4,}\d{1,2}\s*$", ln) and not re.search(r"\d", ref):
                    continue
                tokens = re.split(r"\s{2,}", ln.strip())
                # Columns that are centred or right-aligned don't line up with the header
                # labels; when the slice lands mid-token, fall back to whitespace tokens.
                if (" " in ref or not ref) and len(tokens) >= 2 and _REFS_RE.fullmatch(tokens[0]):
                    ref = tokens[0]
                    value = tokens[1]
                    rest = tokens[2:]
                    if qty_col and not rest:
                        value = re.sub(r"\s+\d{1,3}$", "", value)
                    if qty_col and rest and re.fullmatch(r"\d+", rest[0]):
                        rest = rest[1:]
                    ptype = "" if qty_col else (rest[0] if rest else "")
                    notes = " ".join(rest if qty_col else rest[1:])
                    key = f"{ref}|{value}|{ptype}"
                    if key not in seen:
                        seen.add(key)
                        for one in expand_refs(ref):
                            nr = normalize_row(BomRow(ref=one, value=value, part_type=ptype, notes=notes))
                            if is_plausible(nr):
                                rows.append(nr)
                    continue
                grouped = "," in ref and _REFS_RE.fullmatch(ref) is not None
                if not ref or " " in ref or (len(ref) > 12 and not grouped) or len(ref) > 60:
                    # continuation of a notes cell, append to previous row
                    if rows and ln.strip() and v0 and not ln[:v0].strip():
                        tail = ln[(n0 or t0 or v0):].strip()
                        if tail:
                            rows[-1].notes = (rows[-1].notes + " " + tail).strip()
                    continue
                value = ln[v0:t0].strip() if t0 else ln[v0:].strip()
                ptype = ln[t0:n0].strip() if (t0 and n0) else (ln[t0:].strip() if t0 else "")
                if qty_col:
                    ptype = ""
                    value = re.sub(r"\s+\d{1,3}$", "", value)  # quantity bled into the value slice
                notes = ln[n0:].strip() if n0 else ""
                if not value:
                    continue
                key = f"{ref}|{value}|{ptype}"
                if key in seen:
                    continue
                seen.add(key)
                for one in (expand_refs(ref) if grouped else [ref]):
                    nr = normalize_row(BomRow(ref=one, value=value, part_type=ptype, notes=notes))
                    if is_plausible(nr):
                        rows.append(nr)
    return rows


_COL_HEADERS = re.compile(r"RESISTORS|CAPACITORS|DIODES|TRANSISTORS|SEMICONDUCTORS|ELECTROMECHANICAL|POTENTIOMETERS|\bICS?\b|SWITCHES|PARTS LIST|B\.?O\.?M\.?|BILL OF MATERIALS", re.I)
_COL_DESIG = re.compile(r"(?<![A-Z0-9])((?:R|C|D|Q|IC|U|L|SW|Z|ZD|LED|VR|TR|OPTO|X|J)\d+[A-Z]?)[ \t]+(\S+(?:[ \t](?:Red|Green|Blue|Yellow|White|Amber)?[ \t]?(?:LED|LEDs|Zener|zener|elec)|[ \t]or[ \t]\d\S*)?)")
_COL_POT = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z.\-/]{1,13}(?: [A-Za-z.\-/]{1,12}){0,2}(?:,[ \t]*[A-Z][A-Za-z.\-/]{1,13}(?: [A-Za-z.\-/]{1,12}){0,2})*)[ \t]{2,}([ABCW]\d+(?:[.,]\d+)?[KkMm]|[ABW]\d{2,}|\d+(?:[.,]\d+)?[KkMm]? ?[ABCW])(?:[ \t]?(?:DG|dual(?:[ \-]gang)?))?(?![A-Za-z0-9])")
# Named pots and trimmers with no taper letter ("BIAS   10K") on pages that carry a Potentiometers heading.
_COL_POT_PLAIN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{3,12})[ \t]{2,}(\d+(?:[.,]\d+)?[KkMm])(?![A-Za-z0-9])")
_COL_POT_STOP = {"QTY", "TYPE", "VALUE", "PART", "LOCATION", "NOTES", "REF", "AND", "FOR", "THE", "USE", "SET", "WITH", "ALL", "NOTE", "OTHER"}
# "D1, D2, D5   3mm LED" and "D1, 2, 4   1N5817": a comma list of designators sharing one value.
_COL_LIST = re.compile(r"(?<![A-Za-z0-9])((?:R|C|D|Q|IC|U|L|LED)\d+(?:,[ \t]*(?:R|C|D|Q|IC|U|L|LED)?\d+)+)[ \t]+(\S+(?:[ \t](?:Red|Green|Blue|Yellow|White|Amber)?[ \t]?(?:LED|LEDs|Zener|zener|elec))?)")


def parse_bom_columns(pages: list[str], max_col: int | None = None) -> list[BomRow]:
    """Fallback for docs that print the parts list as side-by-side columns
    (older PedalPCB, Madbean): scan every line for `REF VALUE` pairs."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        heads = _COL_HEADERS.findall(page)
        if len(heads) < 2 and not (len(heads) == 1 and re.match(r"B\.?O\.?M|PARTS LIST|BILL", heads[0], re.I) and len(_COL_DESIG.findall(page)) >= 8):
            continue  # a lone "BOM" heading over a dense run of designators is still a parts table (Part / spec columns)
        text = "\n".join(ln[:max_col] if max_col else ln for ln in page.splitlines())
        # "Q1-Q4   2N5457" ranges and "LEVEL tr  10K" trimmers
        for letter, a, b, val in re.findall(r"(?<![A-Z0-9])([RCDQ])(\d+)\s*[-–]\s*[RCDQ]?(\d+)[ \t]+((?:\d|[A-Z])[A-Za-z0-9.\-/]*)", text):
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 40:
                for i in range(lo, hi + 1):
                    ref = f"{letter}{i}"
                    if ref not in seen:
                        seen.add(ref)
                        nr = normalize_row(BomRow(ref=ref, value=val))
                        if is_plausible(nr):
                            rows.append(nr)
        for ref, val in re.findall(r"(?<![A-Za-z0-9])([A-Z]{3,12})\s+tr\.?\s+(\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", text):
            if ref not in seen:
                seen.add(ref)
                rows.append(normalize_row(BomRow(ref=ref, value=val.upper(), part_type="Trimmer", category="TRIM")))
        for refs, val in _COL_LIST.findall(text):
            val = val.strip().rstrip(",;")
            prefix = re.match(r"[A-Z]+", refs).group(0)
            for tok in re.split(r",\s*", refs):
                ref = tok if re.match(r"[A-Z]", tok) else prefix + tok
                if ref in seen:
                    continue
                nr = normalize_row(BomRow(ref=ref, value=val))
                if is_plausible(nr):
                    seen.add(ref)
                    rows.append(nr)
        for ref, val in _COL_DESIG.findall(text):
            val = val.strip().rstrip(",;")  # "2N5457, J201 or other FET" -> 2N5457
            if ref in seen or val.upper() in {"VALUE", "QTY", "TYPE", "OR", "AND"}:
                continue
            nr = normalize_row(BomRow(ref=ref, value=val))
            if is_plausible(nr):
                seen.add(ref)  # a junk pairing on a wiring page must not shadow the real row on the parts page
                rows.append(nr)
        for ref, val in re.findall(r"(?<![A-Za-z0-9])([A-Z]*TRIM[A-Z0-9]*)[ \t]+(\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", text):
            if ref not in seen:
                seen.add(ref)
                rows.append(normalize_row(BomRow(ref=ref, value=val.upper(), part_type="Trimmer", category="TRIM")))
        for refs, val in _COL_POT.findall(text):
            for ref in re.split(r",\s*", refs):
                ref = ref.strip()
                if ref in seen or ref.upper() in _COL_POT_STOP or _COL_HEADERS.fullmatch(ref) or ref.upper() in seen:
                    continue
                seen.add(ref)
                rows.append(normalize_row(BomRow(ref=ref.upper() if ref.istitle() else ref, value=val.replace(" ", "").upper(), part_type="Potentiometer", category="POT")))
        if re.search(r"POTENTIOMETERS?|\bPOTS\b", text, re.I):
            for ref, val in _COL_POT_PLAIN.findall(text):
                if ref in seen or ref in _COL_POT_STOP or _COL_HEADERS.fullmatch(ref) or re.match(r"^(?:CLR|LED|REG|TRIM)", ref):
                    continue
                seen.add(ref)
                rows.append(normalize_row(BomRow(ref=ref, value=val.upper(), part_type="Potentiometer", category="TRIM" if "TRIM" in ref else "POT")))
    return rows


_OCR_POT = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z\-]{2,12}[0-9?]?)\s+([0-9IlOoS]+(?:[.,]\d+)?[KkMm]?[ABCW]|[ABCWabcw8][0-9IlOoS]+(?:[.,]\d+)?[kKmM]?)(?![A-Za-z0-9])")
# "SWI  SPDT ON-ON", "BYPASS 3PDT": a switch named on the parts list
_OCR_SWITCH = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z\-]{1,12}[0-9?I]?)\s+([1-4SD]P[DS]T(?:[ \-]*(?:ON|OFF|/))*)(?![A-Za-z0-9])")
_POT_DIGITS = str.maketrans({"I": "1", "l": "1", "O": "0", "o": "0", "S": "5", "s": "5"})


def _repair_pot(v: str) -> str:
    """Pot values keep their taper letter; only the digit run is repaired (ASOOK -> A500K,
    BSOK -> B50K, BIM -> B1M, 8100K -> B100K where an 8 stands in for the B)."""
    v = v.replace(" ", "")
    m = re.match(r"^([ABCWabcw8])([0-9IlOoS]+(?:[.,]\d+)?)([kKmM]?)$", v)
    if m:
        taper, digits, unit = m.groups()
        taper = "B" if taper == "8" else taper.upper()
        return f"{taper}{digits.translate(_POT_DIGITS)}{unit.upper()}"
    m = re.match(r"^([0-9IlOoS]+(?:[.,]\d+)?)([kKmM]?)([ABCW])$", v)
    if m:
        digits, unit, taper = m.groups()
        return f"{digits.translate(_POT_DIGITS)}{unit.upper()}{taper}"
    return v.upper()
_OCR_VARIANT_STOP = {"PART", "VALUE", "REF", "TYPE", "NOTES", "QTY", "GND", "IN", "OUT", "LED", "PCB", "BOM", "PART VALUE", "GE", "SI"}
_OCR_POT_STOP = {"AND", "THE", "FOR", "OUT", "GND", "BOM", "MAIN", "BOARD", "NOTES", "TRANSISTORS", "RESISTORS", "CAPACITORS", "DIODES", "SWITCHES",
                 "POTS", "TRIMMERS", "VALUE", "PART", "PARTS", "QTY", "USE", "SWAP", "WITH", "TRY", "ANY", "PUT", "ADD", "FIT", "SET", "PREFER", "LIKE", "FROM", "INTO", "ALSO", "STANDARD"}
_RANGE = re.compile(r"\*?\b([RCDQ])(\d+)\s*[-–]\s*[RCDQ]?(\d+)\s+([A-Z0-9][A-Z0-9.]+)", re.I)


def _clean_ocr_line(ln: str) -> str:
    """Repair the OCR slips that recur in GuitarPCB parts tables."""
    ln = re.sub(r"[_—–‘’'\"|&*]+", " ", ln)
    # designators: c13 -> C13, RS -> R5, cs -> C8, cg -> C9, R8& -> R8
    def fix_ref(m: re.Match) -> str:
        letter = m.group(1).upper()
        num = (m.group(2).upper().replace("S", "5").replace("O", "0").replace("G", "9").replace("I", "1")
               .replace("L", "1").replace("A", "4").replace("T", "7"))
        return f"{letter}{num}"
    ln = re.sub(r"(?<![A-Za-z0-9])([RCDQrcdq])([0-9SOGILsogil]{1,3}|[AaTtLl]|[0-9][AaTt])(?![A-Za-z0-9])", fix_ref, ln)
    ln = re.sub(r"(?<![A-Za-z0-9])AT(?=[0-9]*[kKnpuµ]|[0-9])", "47", ln)   # "AT0k" -> 470k, "ATp" -> 47p
    ln = re.sub(r"(?<![A-Za-z0-9])I(?=[0-9]*[MK][ABCW]?\b)", "1", ln)     # "IMA" -> 1MA
    ln = re.sub(r"(?<![A-Za-z0-9])(?:IC|ic|Ic)([0-9SO]{1,2})(?![A-Za-z0-9])", lambda m: "IC" + m.group(1).replace("S", "5").replace("O", "0"), ln)
    ln = re.sub(r"(?<![A-Za-z0-9])(TRIM|POT|VR|SW)([0-9IlO]{1,2})(?![A-Za-z0-9])",
                lambda m: m.group(1) + m.group(2).replace("I", "1").replace("l", "1").replace("O", "0"), ln, flags=re.I)
    # values: 'in' -> '1n', 'lk' -> '1k', 'O' as zero inside numbers
    ln = re.sub(r"(?<![A-Za-z0-9])in(?![A-Za-z0-9])", "1n", ln)
    ln = re.sub(r"(?<![A-Za-z0-9])l([kKnpuM])(?![A-Za-z0-9])", r"1\1", ln)
    ln = re.sub(r"(?<=\d)O(?=\d|[kKnpuMR]\b)", "0", ln)
    ln = re.sub(r"(?<![A-Za-z0-9])O(?=\d)", "0", ln)
    ln = re.sub(r"\b(TL|LM|NE|RC|JRC|OP|LF|CA|MC)O(\d)", r"\g<1>0\2", ln)  # TLO72 -> TL072
    ln = re.sub(r"\bTL[O0]V2\b", "TL072", ln)
    ln = re.sub(r"\bIN(\d{4}[A-Z]?)\b", r"1N\1", ln)                        # IN4148 -> 1N4148
    ln = re.sub(r"\b25([ABCDKJ]\d{3,}[A-Z0-9\-]*)\b", r"2S\1", ln)         # 25C1815 -> 2SC1815
    ln = re.sub(r"\b([ABCW])([0-9IO]+)([KM]?)\b", lambda m: m.group(1) + m.group(2).replace("I", "1").replace("O", "0") + m.group(3), ln)  # BIM -> B1M
    return ln


def ocr_bom(pdf: Path, vendor: str, slug: str, max_pages: int = 9, min_rows: int = 12,
            pages: list[int] | None = None, thorough: bool = False) -> list[BomRow]:
    """OCR pages in order until one yields a real parts table, keeping the best.
    For vendors whose parts list is an image (GuitarPCB, Dead End FX)."""
    if not shutil.which("tesseract"):
        return []
    with fitz.open(pdf) as d:
        n_pages = d.page_count
    best: list[BomRow] = []
    if pages:
        # Caller knows which pages hold parts tables (e.g. "MAIN BOARD BOM" + "DAUGHTERBOARD BOM"):
        # OCR every one and merge, first occurrence of a designator wins.
        merged: list[BomRow] = []
        seen_refs: set[str] = set()
        for page_no in pages:
            if page_no < 1 or page_no > n_pages:
                continue
            for r in _ocr_page(pdf, vendor, slug, page_no, thorough):
                if r.ref not in seen_refs:
                    seen_refs.add(r.ref)
                    merged.append(r)
        return merged
    for page_no in range(1, min(n_pages, max_pages) + 1):
        rows = _ocr_page(pdf, vendor, slug, page_no, thorough)
        if len(rows) > len(best):
            best = rows
        if len(best) >= min_rows:
            break
    return best


def _tesseract_cached(png: Path, psm: int, tag: str = "") -> str:
    txt = png.with_name(f"{png.stem}{tag}{'' if psm == 6 else f'-psm{psm}'}.txt")
    if txt.exists():
        return txt.read_text()
    out = subprocess.run(["tesseract", str(png), "-", "--psm", str(psm)], capture_output=True, text=True).stdout
    txt.write_text(out)
    return out


def _merge_ocr_rows(variants: list[list[BomRow]]) -> list[BomRow]:
    """Union of several OCR passes: per designator keep the value most passes agree on,
    preferring values that parse (a numeric R/C) over ones that don't."""
    by_ref: dict[tuple[str, str], list[BomRow]] = {}
    order: list[tuple[str, str]] = []
    for rows in variants:
        for r in rows:
            key = (r.variant, r.ref)
            if key not in by_ref:
                order.append(key)
            by_ref.setdefault(key, []).append(r)
    # A pass that read the variant columns beats one that did not: drop unlabelled rows for
    # any designator that also has labelled ones, so R5 is not listed once per variant plus once more.
    labelled = {ref for (var, ref) in by_ref if var}
    order = [k for k in order if k[0] or k[1] not in labelled]
    out: list[BomRow] = []
    for key in order:
        cands = by_ref[key]
        def score(r: BomRow) -> tuple:
            parses = 1 if (r.category not in ("R", "C", "L") or r.sort_key > 0) else 0
            votes = sum(1 for o in cands if o.norm_value == r.norm_value)
            return (parses, votes)
        out.append(max(cands, key=score))
    return out


def _grid_lines(dark, axis: int, frac: float) -> list[tuple[int, int]]:
    """Positions of ruled lines along one axis: rows (axis 0) or columns (axis 1) whose
    longest unbroken dark run covers at least `frac` of the image, merged when adjacent."""
    import numpy as np
    arr = dark if axis == 0 else dark.T
    n = arr.shape[1]
    out: list[list[int]] = []
    for i, line in enumerate(arr):
        # longest run of True in `line`
        padded = np.concatenate(([0], line.astype(np.int8), [0]))
        edges = np.flatnonzero(np.diff(padded))
        longest = int((edges[1::2] - edges[::2]).max()) if edges.size else 0
        if longest >= frac * n:
            if out and i - out[-1][-1] <= 3:
                out[-1].append(i)
            else:
                out.append([i])
    return [(g[0], g[-1]) for g in out]


_GRID_REF = re.compile(r"^(?:(?:R|C|D|Q|IC|U|L|SW|LED|VR|TR)\d{1,3}[A-Z]?|CLR|TRIM\d?)$")


def _ocr_grid_rows(bin_png: Path) -> list[BomRow]:
    """Parts tables drawn as a ruled grid defeat page-level OCR: read the grid instead.
    Ruled lines give the cell boundaries; each cell is OCR'd on its own as one line of
    text, and adjacent cells pair up as designator (or pot name) and value."""
    import json
    import numpy as np
    from PIL import Image
    cache = bin_png.with_name(bin_png.stem + "-grid.json")
    if cache.exists():
        cells_rows = json.loads(cache.read_text())
    else:
        Image.MAX_IMAGE_PIXELS = None
        img = np.array(Image.open(bin_png).convert("L"))
        dark = img < 128
        hl = _grid_lines(dark, 0, 0.12)
        vl = _grid_lines(dark, 1, 0.08)
        cells_rows = []
        if len(hl) >= 4 and len(vl) >= 3:
            tmp = bin_png.with_name(bin_png.stem + "-cell.png")
            for (_, y1), (y2, _) in zip(hl, hl[1:]):
                top, bot = y1 + 2, y2 - 2
                if not 12 <= bot - top <= 120:
                    continue
                texts: list[str] = []
                for (x0, x1), (x2, _) in zip(vl, vl[1:]):
                    left, right = x1 + 2, x2 - 2
                    if not 20 <= right - left <= 900 or dark[top:bot, x0:x1 + 1].max(axis=1).mean() <= 0.5:
                        texts.append("")  # not a cell: the left rule does not span this row
                        continue
                    cell = img[top:bot, left:right]
                    if (cell < 128).mean() < 0.004:
                        texts.append("")
                        continue
                    big = Image.fromarray(cell).resize((cell.shape[1] * 3, cell.shape[0] * 3))
                    Image.fromarray(np.pad(np.array(big), 15, constant_values=255)).save(tmp)
                    texts.append(subprocess.run(["tesseract", str(tmp), "-", "--psm", "7"], capture_output=True, text=True).stdout.strip())
                if any(texts):
                    cells_rows.append(texts)
            tmp.unlink(missing_ok=True)
        cache.write_text(json.dumps(cells_rows))
    rows: list[BomRow] = []
    seen: set[str] = set()
    last_in_col: dict[int, tuple[str, int]] = {}  # column -> (prefix, number) of the last designator read there

    def clean_ref(raw: str, col: int) -> str:
        ref = re.sub(r"[^A-Za-z0-9\-]", "", raw)
        m = re.match(r"^(IC|LED|CLR|TRIM|SW|VR|TR|R|C|D|Q|U|L)([A-Za-z0-9\-]*)$", ref, re.I)
        if not m:
            return ref.upper()
        prefix, rest = m.group(1).upper(), m.group(2).translate(str.maketrans("lIOo", "1100"))  # S is left alone: RS may be R5 or R8
        if not rest and prefix in ("IC", "SW", "Q", "D"):
            rest = "1"  # a bare IC or SW is the only one
        if not re.fullmatch(r"\d{1,3}[A-Z]?", rest):
            prev = last_in_col.get(col)
            if prev and prev[0] == prefix:
                rest = str(prev[1] + 1)  # R7, R?, R9: the unreadable one is R8
            else:
                return prefix + rest
        return prefix + rest

    for texts in cells_rows:
        for k in range(len(texts) - 1):
            ref_raw, val_raw = texts[k].strip(), texts[k + 1].strip()
            if not ref_raw or not val_raw:
                continue
            ref = clean_ref(ref_raw, k)
            val = _repair_value(val_raw.rstrip(" .:;|*").split("  ")[0])
            if _GRID_REF.match(ref) and re.search(r"\d|Ge|Si|NPN|PNP|LED|SPDT|DPDT", val) and ref not in seen:
                mm = re.match(r"^([A-Z]+)(\d+)", ref)
                if mm:
                    last_in_col[k] = (mm.group(1), int(mm.group(2)))
                nr = normalize_row(BomRow(ref=ref, value=val, notes="OCR grid"))
                if is_plausible(nr):
                    seen.add(ref)
                    rows.append(nr)
            elif re.fullmatch(r"[A-Z][A-Z .\-]{2,12}", ref_raw.strip(" |")) and ref_raw.strip(" |") not in seen \
                    and (re.fullmatch(r"[ABCW]?\d+(?:[.,]\d+)?[kKM]?[ABCW]?", val) or re.search(r"[SD]P[SD]T|3PDT|toggle", val, re.I)):
                name = ref_raw.strip(" |")
                seen.add(name)
                cat = "SW" if re.search(r"[SD]P[SD]T|3PDT|toggle", val, re.I) else ("TRIM" if "TRIM" in name else "POT")
                rows.append(normalize_row(BomRow(ref=name, value=val.upper(), part_type="Potentiometer" if cat != "SW" else "", category=cat, notes="OCR grid")))
    return rows


def _ocr_page(pdf: Path, vendor: str, slug: str, page_no: int, thorough: bool = False) -> list[BomRow]:
    png = CACHE_DIR / vendor / f"{slug}-p{page_no}.png"
    if not png.exists():
        render_page(pdf, page_no, png, dpi=300)
    variants = [_rows_from_ocr(_tesseract_cached(png, 6))]
    if not thorough:
        return variants[0]
    # Low-resolution scans (a BOM screenshot placed on a page): OCR the embedded
    # image itself, upscaled to ~1400px wide, in two segmentation modes.
    variants.append(_rows_from_ocr(_tesseract_cached(png, 4)))
    # Coloured table grids and tinted cells confuse tesseract; a hard threshold keeps
    # only the dark text. (Pillow is optional: skip silently without it.)
    try:
        from PIL import Image
        bpng = png.with_name(png.stem + "-bin.png")
        if not bpng.exists():
            Image.MAX_IMAGE_PIXELS = None
            im = Image.open(png).convert("L")
            im.point(lambda v: 255 if v > 90 else 0).save(bpng)
        for psm in (6, 4):
            variants.append(_rows_from_ocr(_tesseract_cached(bpng, psm)))
        names = _ocr_variant_names(_tesseract_cached(bpng, 6)) or _ocr_variant_names(_tesseract_cached(bpng, 4))
        if len(names) >= 2:
            strips = _ocr_column_strips(bpng, names)
            if strips:
                # Strip rows cannot mix columns; keep them and add what the page-level passes found beyond them.
                have = {(r.variant, r.ref) for r in strips}
                merged = _merge_ocr_rows(variants)
                return strips + [r for r in merged if (r.variant, r.ref) not in have and (r.variant or r.ref not in {ref for _, ref in have})]
        grid = _ocr_grid_rows(bpng)
        if len(grid) >= 8:
            # A ruled table read cell by cell is more reliable than any page-level pass, but it may
            # cover only some columns: keep every grid row and add the page-level rows for the
            # designators it lacks. Within a prefix the grid did read, a number far past its last
            # one (IC20 on a board whose grid stops at IC1) is silkscreen noise and is dropped.
            have = {r.ref for r in grid}
            top: dict[str, int] = {}
            for r in grid:
                mm = re.match(r"^([A-Z]+)(\d+)", r.ref)
                if mm:
                    top[mm.group(1)] = max(top.get(mm.group(1), 0), int(mm.group(2)))
            extra = []
            for r in _merge_ocr_rows(variants):
                if r.ref in have:
                    continue
                mm = re.match(r"^([A-Z]+)(\d+)", r.ref)
                if mm and mm.group(1) in top and int(mm.group(2)) > top[mm.group(1)] + 2:
                    continue
                extra.append(r)
            return grid + extra
    except ImportError:
        pass
    with fitz.open(pdf) as d:
        page = d[page_no - 1]
        for i, im in enumerate(page.get_images(full=True)):
            w, h = im[2], im[3]
            if w < 400 or h < 300 or w * h < 150_000:
                continue
            try:
                base = fitz.Pixmap(d, im[0])
                if base.n > 3:
                    base = fitz.Pixmap(fitz.csRGB, base)
                ipng = CACHE_DIR / vendor / f"{slug}-p{page_no}-img{i}.png"
                if not ipng.exists():
                    s = max(1.0, min(4.0, 1440 / w))
                    tmp = fitz.open("png", base.tobytes("png"))
                    pix = tmp[0].get_pixmap(matrix=fitz.Matrix(s * w / tmp[0].rect.width, s * h / tmp[0].rect.height), alpha=False)
                    pix.save(ipng)
            except Exception:  # noqa: BLE001 - odd colour spaces etc.
                continue
            for psm in (6, 4):
                variants.append(_rows_from_ocr(_tesseract_cached(ipng, psm)))
    return _merge_ocr_rows(variants)


_UNIT_TOKEN = re.compile(r"^[0-9ATtlIiOoS?£./]{1,6}(?:[kKMrRnpuµ]F?|[uµ]F|nF|pF)$")
_DIGIT_FIX = str.maketrans({"A": "4", "T": "7", "t": "7", "l": "1", "I": "1", "i": "7", "O": "0", "o": "0", "S": "5", "?": "2", "£": "", "/": "7"})


def _repair_value(v: str) -> str:
    """OCR of low-res tables swaps digits for look-alike letters: A7T0k -> 470k, 2?n -> 22n,
    ATr -> 47r. Only touch tokens that end in a unit and contain a look-alike."""
    if re.match(r"^[ABCW]\d", v):
        return v  # a pot value like A1M: the letter is the taper, not a misread digit
    v = re.sub(r"^T(?=[0-9OolI]|[kKMuµn])", "1", v)  # a leading T is a serifed 1 (TK5 -> 1K5, Tu -> 1u); an inner T stays a 7
    if _UNIT_TOKEN.match(v) and re.search(r"[ATtlIiOoS?£/]", v[:-1]):
        head, tail = re.match(r"^(.*?)([kKMrRnpuµ]F?|[uµ]F|nF|pF)$", v).groups()
        fixed = head.translate(_DIGIT_FIX)
        if re.fullmatch(r"\d+(?:\.\d+)?", fixed):
            v = fixed + tail
    m = re.match(r"^([47])(\d*(?:\.\d+)?)([kKMrRnpuµ]F?|[uµ]F|nF|pF)$", v)
    if m and not _is_e24(m.group(1) + m.group(2)) and _is_e24("1" + m.group(2)):
        return "1" + m.group(2) + m.group(3)  # 700uF and 400uF are not values; 100uF is: the 1 was read as 7 or 4
    v = re.sub(r"^[24](?=1N[0-9A-Za-z]{3,5}$)", "", v)  # "41N4001", "41N34e": a border read as a digit before the part number
    v = re.sub(r"^4N(?=\d{4})", "1N", v)  # "4N4004" is 1N4004 (4N25-style optocouplers have two digits)
    m = re.match(r"^[^A-Za-z0-9]*[1IilTtaA][Nn]([0-9A-Za-z]{3,5}[A-Z]?)$", v)
    if m:  # 1N-series diodes: "-tN4oo4", "IN9L4", "iNg14" -> 1N4004, 1N914, 1N914
        digits = m.group(1).translate(str.maketrans("oOlILgGSsBq", "00111995869"))
        if re.fullmatch(r"\d{3,4}[A-Z]?", digits):
            return "1N" + digits
    return v


_E24 = {10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91}


def _is_e24(num: str) -> bool:
    try:
        x = float(num)
    except ValueError:
        return False
    if x <= 0:
        return False
    while x >= 100:
        x /= 10
    while x < 10:
        x *= 10
    return round(x) in _E24 and abs(x - round(x)) < 0.05


def ocr_image_bom(image: Path, vendor: str, slug: str, tag: str = "bom") -> list[BomRow]:
    """Thorough OCR of a standalone parts-list image (a BOM photo or screenshot):
    two segmentation modes plus a thresholded pass, merged per designator."""
    if not shutil.which("tesseract"):
        return []
    png = CACHE_DIR / vendor / f"{slug}-{tag}.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    if not png.exists():
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            im = Image.open(image)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            if im.width < 1400:
                s = 1400 / im.width
                im = im.resize((int(im.width * s), int(im.height * s)))
            im.save(png)
        except Exception:  # noqa: BLE001
            return []
    variants = [_rows_from_ocr(_tesseract_cached(png, psm)) for psm in (6, 4)]
    try:
        from PIL import Image
        bpng = png.with_name(png.stem + "-bin.png")
        if not bpng.exists():
            Image.open(png).convert("L").point(lambda v: 255 if v > 110 else 0).save(bpng)
        variants += [_rows_from_ocr(_tesseract_cached(bpng, psm)) for psm in (6, 4)]
    except ImportError:
        pass
    return _merge_ocr_rows(variants)


def _ocr_variant_names(out: str) -> list[str]:
    """Variant names from a piped header line ("| RAT | -RAT2 | Turbo RAT | You Dirty RAT")."""
    for raw in out.splitlines():
        if raw.count("|") < 2:
            continue
        cols = [re.sub(r"^[^A-Za-z]+|[^A-Za-z0-9)]+$", "", c.strip()) for c in raw.split("|")]
        cols = [c for c in cols if c]
        if 2 <= len(cols) <= 6 and all(re.fullmatch(r"[A-Z][A-Za-z0-9 .\-']{1,18}", c) and re.search(r"[A-Z0-9]{2}|[A-Z][a-z]+ [A-Z]", c) for c in cols) \
                and not any(re.search(r"\d[kKMnpuµ]|^[RCDQ]\d|^\d?[NA]\d{3}", c) or c.upper() in _OCR_VARIANT_STOP for c in cols):
            return cols
    return []


def _ocr_column_strips(png: Path, names: list[str]) -> list[BomRow]:
    """A table with one column per variant: find the header words with tesseract's word
    boxes, cut the page into vertical strips halfway between them, and OCR each strip on
    its own so a line can never mix two columns. Rows carry their strip's variant name."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    tsv_path = png.with_name(png.stem + "-words.tsv")
    if not tsv_path.exists():
        tsv_path.write_text(subprocess.run(["tesseract", str(png), "-", "--psm", "11", "tsv"], capture_output=True, text=True).stdout)
    words = [(int(f[6]), int(f[7]), int(f[8]), f[11].strip()) for f in (ln.split("\t") for ln in tsv_path.read_text().splitlines()[1:])
             if len(f) == 12 and f[11].strip()]
    wanted = {re.sub(r"[^A-Za-z0-9]", "", t).upper() for n in names for t in n.split()}
    cands = sorted((x, y, w, t) for x, y, w, t in words if re.sub(r"[^A-Za-z0-9]", "", t).upper() in wanted)
    if len(cands) < 2:
        return []
    ys = [y for _, y, _, _ in cands]
    row_y = max(set(ys), key=ys.count)
    phrases: list[tuple[int, int]] = []
    for x, y, w, t in cands:
        if abs(y - row_y) > 25:
            continue
        if phrases and x - phrases[-1][1] < 80:
            phrases[-1] = (phrases[-1][0], x + w)
        else:
            phrases.append((x, x + w))
    if len(phrases) != len(names):
        return []
    im = Image.open(png).convert("L")
    W, H = im.size
    centers = [(a + b) / 2 for a, b in phrases]
    cuts = [0] + [int((a + b) / 2) for a, b in zip(centers, centers[1:])] + [W]
    rows: list[BomRow] = []
    for i, ((x0, x1), name) in enumerate(zip(zip(cuts, cuts[1:]), names)):
        spng = png.with_name(f"{png.stem}-strip{i}.png")
        if not spng.exists():
            im.crop((x0, max(0, row_y - 10), x1, H)).resize(((x1 - x0) * 2, (H - max(0, row_y - 10)) * 2)).save(spng)
        best: list[BomRow] = []
        for psm in (6, 4):
            got = _rows_from_ocr(_tesseract_cached(spng, psm))
            if len(got) > len(best):
                best = got
        for r in best:
            r.variant = name
            rows.append(r)
    return rows


def _rows_from_ocr(out: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()
    variants: list[str] = []

    def add(ref: str, value: str, ptype: str = "", cat: str = "", variant: str = "") -> None:
        value = _repair_value(value.strip().rstrip(".,;:").lstrip("-–—_ "))
        key = f"{variant}|{ref}"
        if key in seen or ref[0] in "J":
            return
        m_ref = re.match(r"^[A-Za-z]+(\d+)", ref)
        if m_ref and (int(m_ref.group(1)) == 0 or int(m_ref.group(1)) > 999):
            return  # R0 is never a real designator (big boards do reach R400)
        if cat not in ("POT", "SW") and (not re.search(r"\d", value) or not re.fullmatch(r"[A-Za-z0-9.\-/µu]{1,12}", value)):
            return
        nr = normalize_row(BomRow(ref=ref, value=value.strip(), part_type=ptype, notes="OCR", category=cat, variant=variant))
        if is_plausible(nr):
            seen.add(key)
            rows.append(nr)

    for raw in out.splitlines():
        ln = _clean_ocr_line(raw)
        if raw.count("|") >= 2:
            cols = [re.sub(r"^[^A-Za-z]+|[^A-Za-z0-9)]+$", "", c.strip()) for c in raw.split("|")]
            cols = [c for c in cols if c]
            # "| RAT | -RAT2 | Turbo RAT | You Dirty RAT '": short names, no values, one column per variant
            if 2 <= len(cols) <= 6 and all(re.fullmatch(r"[A-Z][A-Za-z0-9 .\-']{1,18}", c) and re.search(r"[A-Z0-9]{2}|[A-Z][a-z]+ [A-Z]", c) for c in cols) \
                    and not any(re.search(r"\d[kKMnpuµ]|^[RCDQ]\d|^\d?[NA]\d{3}", c) or c.upper() in _OCR_VARIANT_STOP for c in cols):
                variants = cols
                continue
        for letter, a, b, val in _RANGE.findall(ln):
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 40:
                for i in range(lo, hi + 1):
                    add(f"{letter.upper()}{i}", val)
        pairs = _COL_DESIG.findall(ln)
        # The board silkscreen also OCRs to stray pairs; the parts table has several per line.
        starts_with_pair = bool(pairs) and re.match(r"\s*" + re.escape(pairs[0][0]) + r"\s+" + re.escape(pairs[0][1]), ln) is not None
        if len(pairs) >= 2 or (len(pairs) == 1 and (starts_with_pair or re.search(r"\b(status|led|zener|ge)\b", ln, re.I))):
            by_column = len(variants) >= 2 and len(pairs) == len(variants)  # one pair per variant column
            for k, (ref, val) in enumerate(pairs):
                if val.upper() in {"PNP", "NPN", "STATUS", "LED"}:
                    continue
                if re.search(r"\d", val) or len(val) >= 4:
                    add(ref, val, variant=variants[k] if by_column else "")
        for ref, val in re.findall(r"(?<![A-Za-z0-9])([A-Z]*TRIM[A-Z0-9]*)\s+(\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", ln):
            if ref not in seen and re.search(r"[1-9]", val):
                add(ref, val.upper(), "Trimmer", "TRIM")
        for ref, val in _OCR_SWITCH.findall(ln):
            name = ref.strip("-")
            name = re.sub(r"^(SW)[I?l]$", r"\g<1>1", name).replace("?", "2")
            if name.upper() not in _OCR_POT_STOP and f"|{name.upper()}" not in seen:
                add(name.upper() if not name.isupper() or len(name) <= 4 else name.title(), val.strip(), "", "SW")
        for ref, val in _OCR_POT.findall(ln):
            ref = ref.strip("-")
            ref = re.sub(r"\?$", "2", ref)  # "SEN?" is SEN2: a 2 read as a question mark
            val = _repair_pot(val)
            val = re.sub(r"^([ABCW])0(?=[1-9])", r"\1", val)  # B01M guard
            if not re.search(r"[1-9]", val):
                continue  # "BOARD BOM" is not a pot
            if re.fullmatch(r"[RCDQL]\d+", val):
                continue  # "OOK C16": a designator read as a pot value
            if 3 <= len(ref) <= 13 and re.fullmatch(r"[A-Z][A-Za-z\-]+\d?", ref) and ref.upper() not in _OCR_POT_STOP \
                    and (ref.isupper() or re.fullmatch(r"[ABCW]\d+[kKM]", val)):  # a Title-case name only counts with an explicit taper
                add(ref.upper(), val, "Trimmer" if "TRIM" in ref.upper() else "Potentiometer", "TRIM" if "TRIM" in ref.upper() else "POT")
    # Variant labels are kept only when the table really had columns: at least two variants with four rows each.
    per: dict[str, int] = {}
    for r in rows:
        if r.variant:
            per[r.variant] = per.get(r.variant, 0) + 1
    if len(per) < 2 or min(per.values()) < 4:
        kept: list[BomRow] = []
        refs: set[str] = set()
        for r in rows:
            r.variant = ""
            if r.ref not in refs:
                refs.add(r.ref)
                kept.append(r)
        rows = kept
    return rows


_SCH_REF = re.compile(r"^(R|C|D|Q|IC|U|L|SW|FB|TRIM|VR|XFM|T|K|LED|LDR|Z|ZD)\d+[A-Z]?$")
_SCH_VALUE: dict[str, re.Pattern] = {
    "R": re.compile(r"^\d+(?:[.,]\d+)?[kKMR]?\d*(?:Ω|ohm)?$", re.I),
    "TRIM": re.compile(r"^\d+(?:[.,]\d+)?[kKM]?\d*$", re.I),
    "C": re.compile(r"^\d+(?:[.,]\d+)?[pnuµ]F?\d*$|^\d+(?:[.,]\d+)?[pnuµ]\d*$", re.I),
    "L": re.compile(r"^\d+(?:[.,]\d+)?[munµ]?H?\d*$", re.I),
    "D": re.compile(r"^(1N\d{3,4}[A-Z]?|BAT\d+[A-Z]?|LED|[A-Z]{1,3}\d{2,}[A-Z0-9\-/]*|\d[A-Z]\d{2,}[A-Z0-9]*)$", re.I),
    "Q": re.compile(r"^(\d[A-Z]{1,2}\d{2,}[A-Z0-9\-]*|[A-Z]{2,4}\d{2,}[A-Z0-9\-]*|J\d{3}|BS\d{3}|P\d{3}[A-Za-z]?|AC\d{3}|OC\d{2,3}|NKT\d+|GT\d+[A-Z]?)$", re.I),
    "IC": re.compile(r"^([A-Z]{1,5}\d{2,}[A-Z0-9\-/]*|\d{4}[A-Z]?)$", re.I),
}
_SCH_MAXDIST = {"R": 14.0, "C": 20.0, "L": 20.0, "TRIM": 14.0, "D": 18.0, "Q": 18.0, "IC": 22.0}
_SCH_SKIP_WORDS = {"GND", "VCC", "VDD", "VEE", "VREF", "IN", "OUT", "+9V", "9V", "+V", "-V", "+VE", "-VE", "+5V", "N/C", "NC"}


def _pair_labels(words: list, unit: float = 1.0) -> list[BomRow]:
    """Pair designator labels with the nearest value label. `words` are
    (x0, y0, x1, y1, text) boxes; `unit` scales the distance thresholds
    (1.0 for PDF points, larger for pixel coordinates)."""
    rows: list[BomRow] = []
    refs = [w for w in words if _SCH_REF.match(w[4])]
    others = [w for w in words if not _SCH_REF.match(w[4]) and w[4] not in _SCH_SKIP_WORDS]
    seen: set[str] = set()
    for r in refs:
        ref = re.sub(r"^((?:IC|U)\d+)[A-F]$", r"\1", r[4])
        if ref in seen:
            continue
        cat = categorize(ref, "")
        pat = _SCH_VALUE.get(cat)
        if not pat:
            continue
        rx, ry = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        best: tuple[float, str] | None = None
        for w in others:
            txt = w[4].strip(",;")
            if not pat.match(txt):
                continue
            if cat in ("D", "Q", "IC") and txt.isdigit():
                continue
            d = ((w[0] + w[2]) / 2 - rx) ** 2 + ((w[1] + w[3]) / 2 - ry) ** 2
            if best is None or d < best[0]:
                best = (d, txt)
        if best and best[0] ** 0.5 <= _SCH_MAXDIST[cat] * unit:
            seen.add(ref)
            nr = normalize_row(BomRow(ref=ref, value=best[1], notes="from schematic"))
            if is_plausible(nr):
                rows.append(nr)
    # Named pots: an upper-case label (DRIVE, DIST.) whose nearest neighbour is a taper value.
    potval = re.compile(r"^(?:[ABCW]\d+(?:[.,]\d+)?[kKM]?|\d+(?:[.,]\d+)?[kKM]?[ABCW])$")
    names = [w for w in words if re.fullmatch(r"[A-Z][A-Z.]{2,11}", w[4]) and w[4].rstrip(".") not in _SCH_SKIP_WORDS
             and w[4].rstrip(".") not in {"GND", "VCC", "OUT", "IN", "PCB", "REV", "TITLE", "DATE", "SHEET", "DIY", "AUDIO"}]
    for r in names:
        name = r[4].rstrip(".")
        if name in seen:
            continue
        rx, ry = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        best = None
        for w in others:
            if not potval.match(w[4]):
                continue
            d = ((w[0] + w[2]) / 2 - rx) ** 2 + ((w[1] + w[3]) / 2 - ry) ** 2
            if best is None or d < best[0]:
                best = (d, w[4])
        if best and best[0] ** 0.5 <= 16.0 * unit:
            seen.add(name)
            rows.append(normalize_row(BomRow(ref=name.title(), value=best[1].upper(), part_type="Potentiometer", category="POT", notes="from schematic")))
    rows.sort(key=lambda b: (b.category, int(re.sub(r"\D", "", b.ref) or 0), b.ref))
    return rows


def schematic_bom(pdf: Path, page_no: int) -> list[BomRow]:
    """Pair designator labels with their nearest value label on a vector schematic
    page (Eagle / KiCad exports keep both as text). Reliable for R, C, D, Q, IC;
    other parts need the parts list."""
    with fitz.open(pdf) as doc:
        if page_no < 1 or page_no > doc.page_count:
            return []
        words = doc[page_no - 1].get_text("words")
    return _pair_labels(words, unit=1.0)


def ocr_schematic_bom(image: Path, scale: int = 2) -> list[BomRow]:
    """Same pairing, but for a schematic *image*: OCR with word boxes (sparse
    text mode) after upscaling. Good for clean KiCad-style exports."""
    if not shutil.which("tesseract"):
        return []
    import csv
    import io
    native = fitz.Pixmap(str(image))  # true pixel size; the file's dpi tag must not shrink it
    with fitz.open(image) as d:
        rect = d[0].rect
        to_native = native.width / rect.width if rect.width else 1.0
        pix = d[0].get_pixmap(matrix=fitz.Matrix(to_native * scale, to_native * scale), alpha=False)
        up = image.with_name(image.stem + f"-x{scale}.png")
        pix.save(up)
    tsv = subprocess.run(["tesseract", str(up), "-", "--psm", "11", "tsv"], capture_output=True, text=True).stdout
    words = []
    for r in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        t = (r.get("text") or "").strip()
        try:
            conf = float(r.get("conf") or 0)
            x, y, w, h = int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"])
        except (KeyError, ValueError):
            continue
        if not t or conf < 30:
            continue
        t = re.sub(r"^(\d+(?:\.\d+)?)Meg$", r"\1M", t)
        words.append((x, y, x + w, y + h, t))
    # 12px text at 2x -> ~24px glyphs; thresholds in PDF points were tuned for ~7pt labels
    return _pair_labels(words, unit=3.0 * scale)


_QVP_HEADER = re.compile(r"^\s*Qty\.?\s+Value\s+(?:Parts?|Devices?|Refs?|Designators?)(?:\s+Notes?)?\s*$", re.I)
_QVP_ROW = re.compile(r"^\s*(\d{1,3})\s+(\S.*?\S|\S)\s{2,}([A-Za-z][A-Za-z0-9/\-]*(?:\s*,\s*[A-Za-z][A-Za-z0-9/\-]*)*)\s*,?(?:\s{2,}(\S.*?))?\s*$")
_QVP_SECTION = re.compile(r"^\s*([A-Z][A-Za-z ,&/]{3,60})\s*$")


def parse_bom_qty_value_parts(pages: list[str]) -> list[BomRow]:
    """'Qty  Value  Parts' tables (Moonn Electronics): one line per value with the
    designators grouped, under section headings that name the part type."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        lines = page.splitlines()
        i = 0
        while i < len(lines) and not _QVP_HEADER.match(lines[i]):
            i += 1
        if i >= len(lines):
            continue
        section = ""
        for ln in lines[i + 1:]:
            if not ln.strip():
                continue
            m = _QVP_ROW.match(ln)
            if m:
                _, value, parts, notes = m.groups()
                ptype = section
                for ref in re.split(r"\s*,\s*", parts.strip(", ")):
                    if not ref or ref in seen:
                        continue
                    seen.add(ref)
                    nr = normalize_row(BomRow(ref=ref, value=value.strip(), part_type=ptype, notes=(notes or "").strip()))
                    if is_plausible(nr):
                        rows.append(nr)
                continue
            if re.match(r"^\s*(Schematic|Offboard|Wiring|Drill|Notes?)\b", ln, re.I):
                break
            s = _QVP_SECTION.match(ln)
            if s:
                section = s.group(1).strip().rstrip(":")
    return rows


_SHOP_ROW = re.compile(r"^\s*(\S[^\n]*?\S|\S)\s{2,}(\S[^\n]*?\S)\s{2,}(\d{1,2})\s*$", re.M)
_SHOP_VALUE_CAT = [
    (r"^(?:1N|BA[TRV]?|MA|1n)\d{2,}", "D"), (r"^(?:2N|2SC|2SA|BC|MPSA|MPF|BS|J|PN)\d{3,}", "Q"),
    (r"^(?:JRC|TL|NE|LM|CD|OP|TLE|CA|MC|PT|LT|MN|RC|UA|NJM)\d{3,}", "IC"), (r"^(?:[ABCW]\d+(?:[.,]\d+)?[kKmM]?|\d+(?:[.,]\d+)?[kKmM]?[ABCW])$", "POT"),
]
_SHOP_TYPES = [
    (r"resistor|metal or carbon|carbon film|metal film|¼ ?watt|1/4 ?w", "R"),
    (r"\bcap|electrolytic|ceramic|tantalum|mylar|polyester|^film$|film cap|mlcc|c0g|np0|x7r", "C"),
    (r"trim|3362|3296", "TRIM"), (r"\bpot\b|potentiometer|pc mount|right angle|plastic shaft", "POT"),
    (r"\bled\b", "LED"), (r"diode|rectifier|schottky|zener|germanium", "D"),
    (r"transistor|\bbjt\b|jfet|mosfet|\bnpn\b|\bpnp\b", "Q"),
    (r"op ?amp|\bic\b|regulator|charge pump|chip|\bdip\b", "IC"),
    (r"switch|toggle|footswitch", "SW"), (r"vactrol|\bldr\b|photocell|optocoupler", "OPTO"),
    (r"inductor", "L"), (r"jack|socket|header", "CONN"),
]


def parse_shopping_list(pages: list[str]) -> list[BomRow]:
    """Last resort for docs that give only a shopping list (value, suggested type,
    quantity) and no designators. Rows are named by quantity ("×2") and categorized
    from the type column, so they still feed the parts cross-reference."""
    rows: list[BomRow] = []
    # Join pages: the list can run onto the next page without repeating its heading.
    text = "\n".join(pages)
    blocks = [m.group(1) for m in re.finditer(r"(?:SHOPPING LIST|PARTS LIST)\s*\n(.*?)(?=\n\s*(?:LAYOUT|DRILL TEMPLATE|NOTES?|SCHEMATIC|BOM|INSTALLATION|WIRING|This list)\b|\Z)", text, re.S | re.I)]
    # A "Value  QTY  Type" header may also sit under prose that ends a heading block early: take it from wherever it is.
    for hm in re.finditer(r"^[ \t]*(?:Value|Part)[ \t]+Q(?:ty|uantity)\b.*$", text, re.M | re.I):
        blocks.append(text[hm.start():hm.start() + 4000])
    for block in blocks:
        # "Value Qty Type" or "PART QTY TYPE NOTES" (Aion FX modules: the values are printed on the PCB, so no designators)
        header = next((ln for ln in block.splitlines() if re.search(r"\b(?:Value|Part)\b", ln, re.I) and re.search(r"\bQ(?:ty|uantity)\b", ln, re.I)
                       and not re.search(r"\b(?:Location|Ref|Reference|Designator)\b", ln, re.I)), "")
        found: list[tuple[str, str, str]] = []
        if header:
            # Read the column order from the header ("Value QTY Type ..." or "QTY Value Type ...") and split rows on 2+ spaces.
            # Columns are 2+ spaces apart, except single-spaced runs of column words ("QTY Value", "Rating Spacing").
            cols: list[str] = []
            for tok in re.split(r"\s{2,}", header.strip()):
                words = tok.split()
                if all(w.lower() in {"qty", "quantity", "value", "type", "rating", "spacing", "part", "notes"} for w in words):
                    cols.extend(w.lower() for w in words)
                else:
                    cols.append(tok.lower())
            iv = next((i for i, c in enumerate(cols) if c.startswith(("value", "part"))), None)
            iq = next((i for i, c in enumerate(cols) if c.startswith(("qty", "quantity"))), None)
            if iv is None or iq is None:
                continue
            it = next((i for i, c in enumerate(cols) if c.startswith("type")), None)
            inote = next((i for i, c in enumerate(cols) if c.startswith("note")), None)
            for ln in block.splitlines()[block.splitlines().index(header) + 1:]:
                cells = re.split(r"\s{2,}", ln.strip())
                if len(cells) <= max(iv, iq) or not re.fullmatch(r"\d{1,2}", cells[iq]):
                    continue
                note = cells[inote] if inote is not None and inote < len(cells) else ""
                found.append((cells[iv], cells[it] if it is not None and it < len(cells) else "", cells[iq], note))
        else:
            found = [(v, t, q, "") for v, t, q in _SHOP_ROW.findall(block)]
        for value, ptype, qty, note in found:
            if value.lower() in ("part", "value") or len(value) > 24 or re.fullmatch(r"[\d.]+", value):
                continue  # a bare number is a pin or a count, not a part
            value = re.sub(r"\s*\(.*\)\s*$", "", value)  # "470n (0.47uF)"
            ref = f"×{qty}"
            if re.fullmatch(r"(?:LEDR|CLR|RLED|RPD)", value, re.I):
                # A designator in the value column with the value in the notes ("Recommended value is 4.7k")
                mv = re.search(r"\b(\d+(?:\.\d+)?[kKMR]?\d*)\b(?!\s*W)", note or "")
                if not mv:
                    continue
                ref, value = value.upper(), mv.group(1)
            ptype = re.split(r"\s{2,}", ptype.strip())[0]  # drop the rating / spacing columns
            cat = next((c for rx, c in _SHOP_TYPES if re.search(rx, ptype, re.I)), "")
            if not cat:
                cat = next((c for rx, c in _SHOP_VALUE_CAT if re.match(rx, value, re.I)), "")
            if not cat and re.search(r"3362|3296|trim", ptype, re.I):
                cat = "TRIM"
            if not cat and re.fullmatch(r"\d+(?:[.,]\d+)?[kKMR]?\d*(?:Ω|ohm)?", value):
                cat = "R"  # "100R  *see notes": the value alone says resistor
            if not cat and re.fullmatch(r"\d+(?:[.,]\d+)?[pnuµ]F?\d*", value):
                cat = "C"
            cat = cat or categorize("", ptype, value)
            nr = normalize_row(BomRow(ref=ref, value=value, part_type=ptype, notes=(note.strip() or "shopping list") if ref.startswith("×") else note.strip(), category=cat))
            if (is_plausible(nr) or cat in ("HW", "CONN", "SW", "OTHER")) and (nr.ref, nr.value, nr.part_type) not in {(r.ref, r.value, r.part_type) for r in rows}:
                rows.append(nr)
    return rows


def ocr_enclosure(pdf: Path, vendor: str, slug: str, page_no: int = 1) -> str:
    """Read an enclosure size printed as a graphic (Five Cats' "minimum enclosure"
    stamp). OCRs the right-hand column of the page, then the whole page, and
    repairs the B that condensed fonts turn into 6 or 8 before matching a size."""
    from PIL import Image
    from .taxonomy import find_enclosure
    png = CACHE_DIR / vendor / f"{slug}-p{page_no}.png"
    if not png.exists():
        try:
            render_page(pdf, page_no, png, dpi=200)
        except Exception:  # noqa: BLE001
            return ""
    crop = png.with_name(f"{slug}-p{page_no}-right.png")
    if not crop.exists():
        im = Image.open(png)
        w, h = im.size
        part = im.crop((int(w * 0.50), int(h * 0.25), int(w * 0.98), int(h * 0.55))).convert("L")
        part.resize((part.width * 2, part.height * 2)).save(crop)

    def repair(t: str) -> str:
        return re.sub(r"[1IL|]\s?(590|25)\s?([A-Z0-9]{1,3})\b", lambda m: "1" + m.group(1) + m.group(2).replace("8", "B").replace("6", "B"), t.upper())

    for img, psm in ((crop, 11), (crop, 6), (crop, 4), (png, 11)):
        found = find_enclosure(repair(_tesseract_cached(img, psm, "enc")))
        if found:
            return found
    return ""


_QVR_TRIPLE = re.compile(r"(?<![A-Za-z0-9])(\d{1,2})[ \t]+([A-Za-z0-9.µ/+\-]{1,12}(?:[ \t](?!\d{1,2}[ \t])[A-Za-z0-9.µ/\-]{1,10})?)[ \t]+((?:R|C|D|Q|IC|U|L|SW|LED|VR|TR)\d{1,3}[A-Z]?)(?![A-Za-z0-9])")
_QVR_POT = re.compile(r"(?<![A-Za-z0-9])(\d{1,2})[ \t]+([ABCW]\d+(?:[.,]\d+)?[kKM]?)[ \t]+([A-Z][A-Z\-]{2,12})(?![A-Za-z0-9])")


_BLOCK_HEADING = re.compile(r"^(resistors?|capacitors?|semiconductors?|transistors?|diodes?|potentiometers?|integrated circuits?|ics?|switches|hardware|optical|actives?)\b", re.I)
_VARIANT_SKIP = {"omit", "jump", "jumper", "-", "n/a", "none", "empty", "x"}
_VARIANT_LABEL = re.compile(r"^[A-Za-z0-9“\"][A-Za-z0-9 .'’“”\"/\-]{1,22}$")
_VARIANT_REF = re.compile(r"^(?:R|C|D|Q|IC|U|L|SW|LED|VR|TR|CLR|TRIM)\d*[A-Z]?$", re.I)
_VARIANT_POTVAL = re.compile(r"^(?:[ABCW]\d+(?:[.,]\d+)?[kKM]?|\d+(?:[.,]\d+)?[kKM]?[ABCW])(?:\s?(?:dual|trim))?$", re.I)
_VARIANT_NAME = re.compile(r"^[A-Za-z][A-Za-z. ]{1,14}$")


def _variant_label_ok(c: str) -> bool:
    """A plausible version name: not a value, designator, column word, broken word or parts-row text."""
    return bool(_VARIANT_LABEL.match(c)) and not re.search(r"\d[kKMnpuµ]", c) and c.lower() not in ("value", "qty", "quantity", "type", "notes") \
        and not _VARIANT_REF.match(c) and not c.isdigit() and bool(re.search(r"[A-Z0-9]", c)) \
        and not re.search(r"(?:^| )[a-z](?: |$)", c) \
        and not re.search(r"switch|on/(?:off/)?on|\b[1-4SD]P[DS]T\b|\bpot\b|trim", c, re.I)


def _variant_heading(c: str) -> bool:
    return bool(re.fullmatch(r"(?:part|ref|reference|location|designator|component)s?", c, re.I) or _BLOCK_HEADING.match(c) or _COL_HEADERS.fullmatch(c))


def _variant_header(cells: list[str]) -> list[str]:
    """Column labels of a per-variant header. Two shapes: a part column name or part-type
    heading followed by the labels ('Part | 1977 spec | 2003 spec', 'Resistors | Guitar Mod |
    Bass Mod | Capacitors | Guitar Mod | Bass Mod'), or the label group alone, repeated once
    per side-by-side part type ('Albini | Stock | Albini | Stock', 'II | III | IV | Capacitors |
    II | III | IV'). Returns [] when the line is not such a header."""
    ok, heading = _variant_label_ok, _variant_heading
    cells = [c.strip("“”\"") for c in cells]
    if len(cells) >= 3 and heading(cells[0]):
        labels: list[str] = []
        for c in cells[1:]:
            if not ok(c) or heading(c) or (labels and c.lower() == labels[0].lower()):
                break
            labels.append(c)
        return labels if len(labels) >= 2 else []
    # No heading cell: the label group must repeat on the line.
    if len(cells) >= 4 and not heading(cells[0]):
        group: list[str] = []
        for c in cells:
            if group and (c.lower() == group[0].lower() or heading(c)):
                break  # the group ends where it repeats or where the next part type's heading sits
            group.append(c)
        if len(group) >= 2 and all(ok(c) for c in group):
            rest = [c for c in cells[len(group):] if not heading(c)]
            n = len(group)
            if rest and len(rest) % n == 0 and all(rest[i].lower() == group[i % n].lower() for i in range(len(rest))):
                return group
    return []


def parse_bom_variant_columns(pages: list[str]) -> list[BomRow]:
    """Tables with one value column per build variant ('Part  1977 spec  2003 spec',
    'Resistors  Guitar Mod  Bass Mod'): every column is kept and each row is labelled
    with its column's name. Groups may sit side by side on a line, and a later header
    with the same labels continues the table (a second board, the actives)."""
    rows: list[BomRow] = []
    seen: set[tuple[str, str]] = set()
    labels: list[str] = []

    def accepted() -> bool:
        per: dict[str, int] = {}
        for r in rows:
            per[r.variant] = per.get(r.variant, 0) + 1
        return len(per) >= 2 and max(per.values()) >= 4 and min(per.values()) >= 1  # a version that omits most parts is still a version

    for page in pages:
        plines = page.splitlines()
        for li, ln in enumerate(plines):
            cells = [c.strip() for c in re.split(r"\s{2,}", ln.strip()) if c.strip()]
            if not cells:
                continue
            hdr = _variant_header(cells)
            if not hdr and not labels and 2 <= len(cells) <= 8 and all(_variant_label_ok(c) and not _variant_heading(c) for c in cells) \
                    and not any(c.upper() in _SCH_SKIP_WORDS or c.upper() in _OCR_VARIANT_STOP or re.fullmatch(r"[A-Z +\-]{1,5}", c) for c in cells) \
                    and not all(c.isupper() for c in cells):
                # A bare line of version names ("Meathead  Meathead Dark  Ritual Fuzz") counts when a designator
                # row with exactly that many values follows within three lines (a part-type heading may sit between).
                for nxt in [x for x in plines[li + 1:li + 4] if x.strip()][:3]:
                    ncells = [c.strip() for c in re.split(r"\s{2,}", nxt.strip()) if c.strip()]
                    if ncells and _VARIANT_REF.match(ncells[0]):
                        if len(ncells) - 1 == len(cells):
                            hdr = cells
                        break
            if hdr:
                if labels and [h.lower() for h in hdr] != [l.lower() for l in labels] and not accepted():
                    rows, seen = [], set()  # the previous header led nowhere; start over with this one
                    labels = []
                labels = labels or hdr
                continue
            if not labels:
                continue
            i = 0
            n = len(labels)
            while i < len(cells):
                ref = cells[i]
                vals = cells[i + 1:i + 1 + n]
                is_ref = bool(_VARIANT_REF.match(ref))
                is_pot = not is_ref and bool(_VARIANT_NAME.match(ref)) and len(vals) == n and all(_VARIANT_POTVAL.match(v) for v in vals)
                if (is_ref or is_pot) and len(vals) == n:
                    for lab, val in zip(labels, vals):
                        val = val.strip()
                        if val.lower() in _VARIANT_SKIP:
                            continue
                        note = ""
                        m = re.match(r"^([^/*]+)/([^*]+)\*?$", val)
                        if m:
                            val, note = m.group(1), f"or {m.group(2)}"
                        val = val.rstrip("*")
                        r = BomRow(ref=ref.upper() if is_ref else ref.rstrip(".").title(), value=val, notes=note, variant=lab,
                                   part_type="Potentiometer" if is_pot else "", category="POT" if is_pot else "")
                        nr = normalize_row(r)
                        if (lab, nr.ref) not in seen and is_plausible(nr):
                            seen.add((lab, nr.ref))
                            rows.append(nr)
                    i += 1 + n
                else:
                    i += 1
    return rows if accepted() else []


_BLOCK_STOP = re.compile(r"all trademarks|copyright ©|^\s*page \d|bill of materials|parts list", re.I)
_BLOCK_COLHEAD = re.compile(r"^\s*(?:(?:part|ref|value|type|qty|notes)\s*)+$", re.I)  # "Part  Value  Part  Value" over each block


def parse_bom_version_blocks(pages: list[str]) -> list[BomRow]:
    """Version matrices (PedalPCB's Muffin Fuzz, OTRFX's OmniMuff): the same 'REF  VALUE'
    block printed two or three times across the page, each under the version's name,
    over several pages."""
    rows: list[BomRow] = []
    for page in pages:
        lines = page.splitlines()
        first = next((i for i, ln in enumerate(lines) if len(re.findall(r"(?<![A-Za-z0-9])R1(?=\s)", ln)) >= 2), None)
        if first is None:
            continue
        starts = [m.start() for m in re.finditer(r"(?<![A-Za-z0-9])R1(?=\s)", lines[first])]
        spans = [(a, b) for a, b in zip(starts, starts[1:] + [10_000])]
        k = first - 1
        while k >= 0 and (not lines[k].strip() or _BLOCK_STOP.search(lines[k]) or _BLOCK_COLHEAD.match(lines[k])):
            k -= 1
        if k < 0:
            continue
        titles = [lines[k][a:b].strip() for a, b in spans]
        if not all(titles) or any(_BLOCK_HEADING.match(t) for t in titles):
            continue
        for ln in lines[first:]:
            if _BLOCK_STOP.search(ln):
                break
            for (a, b), title in zip(spans, titles):
                seg = ln[a:b]
                for ref, val in _COL_DESIG.findall(seg):
                    val = val.strip().rstrip(",;")
                    nr = normalize_row(BomRow(ref=ref, value=val, variant=title))
                    if is_plausible(nr):
                        rows.append(nr)
                for ref, val in re.findall(r"(?<![A-Za-z0-9])(RLED|CLR|LEDR)\s+(\S+)", seg):
                    nr = normalize_row(BomRow(ref=ref, value=val, variant=title))
                    if is_plausible(nr):
                        rows.append(nr)
                for refs, val in _COL_POT.findall(seg):
                    for ref in re.split(r",\s*", refs):
                        if ref.strip().upper() not in _COL_POT_STOP and not _COL_HEADERS.fullmatch(ref.strip()):
                            rows.append(normalize_row(BomRow(ref=ref.strip().upper(), value=val.replace(" ", "").upper(), part_type="Potentiometer", category="POT", variant=title)))
                m = re.search(r"([A-Z][A-Z ]{2,24}?SWITCH)\s{2,}([1-4SD]P[DS]T\S*)", seg)
                if m:
                    rows.append(normalize_row(BomRow(ref=m.group(1).strip().title(), value=m.group(2), category="SW", variant=title)))
                # "Vol B100K•": a pot named in Title case with its value one space away
                for name, val in re.findall(r"(?<![A-Za-z0-9])([A-Z][a-z]{2,9}|[A-Z]{3,10})\s([ABCW]\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", seg):
                    if name.upper() not in _COL_POT_STOP and not _COL_HEADERS.fullmatch(name):
                        rows.append(normalize_row(BomRow(ref=name.upper(), value=val.upper(), part_type="Potentiometer", category="POT", variant=title)))
    seen: set[tuple[str, str]] = set()
    out: list[BomRow] = []
    for r in rows:
        if (r.variant, r.ref) not in seen:
            seen.add((r.variant, r.ref))
            out.append(r)
    per: dict[str, int] = {}
    for r in out:
        per[r.variant] = per.get(r.variant, 0) + 1
    if len(per) < 2 or min(per.values()) < 8:
        return []
    return out


def parse_bom_qty_value_ref(pages: list[str]) -> list[BomRow]:
    """Older PedalPCB docs: 'qty  value  ref' triplets side by side under part-type
    headings ('1  1K3  R2   1  100p  C1   1  2N5089  Q1'), pots as '1  B10K LEVEL'."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        if not re.search(r"parts list|bill of materials", page, re.I):
            continue
        for ln in page.splitlines():
            for _, value, ref in _QVR_TRIPLE.findall(ln):
                if ref in seen:
                    continue
                nr = normalize_row(BomRow(ref=ref, value=value.strip()))
                if is_plausible(nr):
                    seen.add(ref)
                    rows.append(nr)
            for _, value, name in _QVR_POT.findall(ln):
                if name in seen or name in _COL_POT_STOP:
                    continue
                seen.add(name)
                rows.append(normalize_row(BomRow(ref=name, value=value.upper(), part_type="Potentiometer", category="POT")))
    return rows


def find_schematic_page(pages: list[str]) -> int | None:
    """1-based page index whose heading is SCHEMATIC (or 'Schematic Diagram'),
    or a KiCad-exported sheet (numbered column labels along the top edge)."""
    for idx, page in enumerate(pages, start=1):
        head_lines = [ln.strip() for ln in page.strip().splitlines() if ln.strip()][:4]
        if any(re.fullmatch(r"SCHEMATICS?(?: DIAGRAM)?:?", ln.upper()) for ln in head_lines):
            return idx
    for idx, page in enumerate(pages, start=1):
        head = "\n".join(page.strip().splitlines()[:4]).upper()
        if re.search(r"\bSCHEMATIC\b", head) and not re.search(r"TABLE OF CONTENTS|INDEX|\d\.\s*SCHEMATIC", head):
            return idx
    for idx, page in enumerate(pages, start=1):
        first = next((ln for ln in page.splitlines() if ln.strip()), "")
        if re.match(r"^\s*1\s{3,}2\s{3,}3(\s{3,}\d)*\s*$", first):
            return idx
    return None


def render_page(pdf: Path, page_no: int, out_png: Path, dpi: int = 170, max_px: int = 3600) -> Path:
    """Render a page to PNG. Scanned docs sometimes declare huge page sizes (a 2550x3300
    JPEG placed on a 35x45 inch page), so the longest side is capped at `max_px`:
    tesseract reads ~300 dpi letter-size text well and giant glyphs badly."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        page = doc[page_no - 1]
        scale = dpi / 72
        longest = max(page.rect.width, page.rect.height) * scale
        if longest > max_px:
            scale *= max_px / longest
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pix.save(out_png)
    return out_png


def doc_version(pages: list[str]) -> str:
    text = "\n".join(pages[:2])
    m = re.search(r"Revised\s+(\d{1,2}/\d{1,2}/\d{2,4})", text)
    if m:
        return m.group(1)
    m = re.search(r"DOCUMENT VERSION\s*\n?.*?(\d+\.\d+\.\d+\s*\(\d{4}-\d{2}-\d{2}\))", text, re.S)
    if m:
        return m.group(1)
    m = re.search(r"\bVersion\s+(\d+(?:\.\d+)+)", text)
    if m:
        return m.group(1)
    return ""


def _expand_range_rows(rows: list[BomRow]) -> list[BomRow]:
    """'Q1-Q5  2N5088' is five transistors, not one part called Q1-Q5: expand any row whose
    designator is a range or a comma list, whichever parser produced it."""
    out: list[BomRow] = []
    seen = {r.ref for r in rows}
    for r in rows:
        refs = expand_refs(r.ref) if re.search(r"\d\s*[-–,]\s*[A-Za-z]*\d", r.ref) else [r.ref]
        if len(refs) <= 1:
            out.append(r)
            continue
        for ref in refs:
            if ref in seen and ref != r.ref:
                continue  # the parser also listed this designator on its own
            seen.add(ref)
            out.append(normalize_row(BomRow(ref=ref, value=r.value, part_type=r.part_type, notes=r.notes, variant=r.variant)))
    return out


def process_document(pdf: Path, vendor: str, slug: str) -> dict:
    """Return bom rows, schematic png (relative to data/), page number, version."""
    pages = pdf_text_pages(pdf)
    # Vendors lay their parts lists out three ways; run every parser and keep the
    # one that recovered the most designators (they never both succeed on one doc).
    bom = _expand_range_rows(max((parse_bom(pages), parse_bom_qty_value_parts(pages), parse_bom_columns(pages), parse_bom_qty_value_ref(pages)), key=len))
    variant_rows = max(parse_bom_variant_columns(pages), parse_bom_version_blocks(pages), key=len)
    if variant_rows and len({r.ref for r in variant_rows}) >= len({r.ref for r in bom}) * 0.8:
        # A per-variant table names the same parts once per column; parts it does not cover stay unlabelled.
        covered = {r.ref.upper().rstrip(".") for r in variant_rows}
        bom = variant_rows + [r for r in bom if r.ref.upper().rstrip(".") not in covered]
    if not bom:
        bom = parse_shopping_list(pages)
    page_no = find_schematic_page(pages)
    schematic_rel = ""
    if page_no:
        png = CACHE_DIR / vendor / f"{slug}-schematic.png"
        if not png.exists():
            render_page(pdf, page_no, png)
        schematic_rel = str(png.relative_to(DATA_DIR))
    return {
        "bom": bom,
        "schematic_local": schematic_rel,
        "schematic_page": page_no,
        "doc_version": doc_version(pages),
        "doc_local": str(pdf.relative_to(DATA_DIR)) if DATA_DIR in pdf.parents else str(pdf),
    }
