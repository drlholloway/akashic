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


_COL_HEADERS = re.compile(r"RESISTORS|CAPACITORS|DIODES|TRANSISTORS|SEMICONDUCTORS|POTENTIOMETERS|\bICS?\b|SWITCHES|PARTS LIST|B\.?O\.?M\.?|BILL OF MATERIALS", re.I)
_COL_DESIG = re.compile(r"(?<![A-Z0-9])((?:R|C|D|Q|IC|U|L|SW|Z|ZD|LED|VR|TR|OPTO|X|J)\d+[A-Z]?)[ \t]+(\S+(?:[ \t](?:Red|Green|Blue|Yellow|White|Amber)?[ \t]?(?:LED|Zener|zener|elec))?)")
_COL_POT = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z .\-/]{1,14}?)[ \t]{2,}([ABCW]\d+(?:[.,]\d+)?[KM]|[ABCW]\d{2,}|\d+(?:[.,]\d+)?[KM]? ?[ABCW])(?![A-Z0-9])")


def parse_bom_columns(pages: list[str], max_col: int | None = None) -> list[BomRow]:
    """Fallback for docs that print the parts list as side-by-side columns
    (older PedalPCB, Madbean): scan every line for `REF VALUE` pairs."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    for page in pages:
        if len(_COL_HEADERS.findall(page)) < 2:
            continue
        text = "\n".join(ln[:max_col] if max_col else ln for ln in page.splitlines())
        for ref, val in _COL_DESIG.findall(text):
            val = val.strip().rstrip(",;")  # "2N5457, J201 or other FET" -> 2N5457
            if ref in seen or val.upper() in {"VALUE", "QTY", "TYPE", "OR", "AND"}:
                continue
            seen.add(ref)
            nr = normalize_row(BomRow(ref=ref, value=val))
            if is_plausible(nr):
                rows.append(nr)
        for ref, val in re.findall(r"(?<![A-Za-z0-9])([A-Z]*TRIM[A-Z0-9]*)[ \t]+(\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", text):
            if ref not in seen:
                seen.add(ref)
                rows.append(normalize_row(BomRow(ref=ref, value=val.upper(), part_type="Trimmer", category="TRIM")))
        for ref, val in _COL_POT.findall(text):
            ref = ref.strip()
            if ref in seen or ref.upper() in {"QTY", "TYPE", "VALUE", "PART", "LOCATION"} or _COL_HEADERS.fullmatch(ref):
                continue
            seen.add(ref)
            rows.append(normalize_row(BomRow(ref=ref, value=val.replace(" ", ""), part_type="Potentiometer", category="POT")))
    return rows


_OCR_POT = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z\-]{2,12})\s+(\d+(?:[.,]\d+)?[KM]?[ABCW]|[ABCWabcw][0-9IlO]+(?:[.,]\d+)?[kKmM]?)(?![A-Za-z0-9])")
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
            pages: list[int] | None = None) -> list[BomRow]:
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
            for r in _ocr_page(pdf, vendor, slug, page_no):
                if r.ref not in seen_refs:
                    seen_refs.add(r.ref)
                    merged.append(r)
        return merged
    for page_no in range(1, min(n_pages, max_pages) + 1):
        rows = _ocr_page(pdf, vendor, slug, page_no)
        if len(rows) > len(best):
            best = rows
        if len(best) >= min_rows:
            break
    return best


def _ocr_page(pdf: Path, vendor: str, slug: str, page_no: int) -> list[BomRow]:
    png = CACHE_DIR / vendor / f"{slug}-p{page_no}.png"
    txt = png.with_suffix(".txt")
    if txt.exists():
        out = txt.read_text()
    else:
        if not png.exists():
            render_page(pdf, page_no, png, dpi=300)
        out = subprocess.run(["tesseract", str(png), "-", "--psm", "6"], capture_output=True, text=True).stdout
        txt.write_text(out)
    return _rows_from_ocr(out)


def _rows_from_ocr(out: str) -> list[BomRow]:
    rows: list[BomRow] = []
    seen: set[str] = set()

    def add(ref: str, value: str, ptype: str = "", cat: str = "") -> None:
        value = value.strip().rstrip(".,;:")
        if ref in seen or ref[0] in "J":
            return
        if cat != "POT" and (not re.search(r"\d", value) or not re.fullmatch(r"[A-Za-z0-9.\-/µu]{1,12}", value)):
            return
        nr = normalize_row(BomRow(ref=ref, value=value.strip(), part_type=ptype, notes="OCR", category=cat))
        if is_plausible(nr):
            seen.add(ref)
            rows.append(nr)

    for raw in out.splitlines():
        ln = _clean_ocr_line(raw)
        for letter, a, b, val in _RANGE.findall(ln):
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 40:
                for i in range(lo, hi + 1):
                    add(f"{letter.upper()}{i}", val)
        pairs = _COL_DESIG.findall(ln)
        # The board silkscreen also OCRs to stray pairs; the parts table has several per line.
        starts_with_pair = bool(pairs) and re.match(r"\s*" + re.escape(pairs[0][0]) + r"\s+" + re.escape(pairs[0][1]), ln) is not None
        if len(pairs) >= 2 or (len(pairs) == 1 and (starts_with_pair or re.search(r"\b(status|led|zener|ge)\b", ln, re.I))):
            for ref, val in pairs:
                if val.upper() in {"PNP", "NPN", "STATUS", "LED"}:
                    continue
                if re.search(r"\d", val) or len(val) >= 4:
                    add(ref, val)
        for ref, val in re.findall(r"(?<![A-Za-z0-9])([A-Z]*TRIM[A-Z0-9]*)\s+(\d+(?:[.,]\d+)?[kKM]?)(?![A-Za-z0-9])", ln):
            if ref not in seen and re.search(r"[1-9]", val):
                add(ref, val.upper(), "Trimmer", "TRIM")
        for ref, val in _OCR_POT.findall(ln):
            ref = ref.strip("-")
            val = val.replace(" ", "").upper().replace("I", "1").replace("L", "1").replace("O", "0")
            val = re.sub(r"^([ABCW])0(?=[1-9])", r"\1", val)  # A0100K -> A100K never happens, but B01M guard
            if not re.search(r"[1-9]", val):
                continue  # "BOARD BOM" is not a pot
            if 3 <= len(ref) <= 12 and re.fullmatch(r"[A-Z][A-Z\-]+", ref) and ref.upper() not in {"AND", "THE", "FOR", "OUT", "GND", "BOM", "MAIN", "BOARD", "NOTES"}:
                add(ref, val, "Trimmer" if "TRIM" in ref else "Potentiometer", "TRIM" if "TRIM" in ref else "POT")
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
    with fitz.open(image) as d:
        pix = d[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
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


def render_page(pdf: Path, page_no: int, out_png: Path, dpi: int = 170) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        page = doc[page_no - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
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
    return ""


def process_document(pdf: Path, vendor: str, slug: str) -> dict:
    """Return bom rows, schematic png (relative to data/), page number, version."""
    pages = pdf_text_pages(pdf)
    # Vendors lay their parts lists out three ways; run every parser and keep the
    # one that recovered the most designators (they never both succeed on one doc).
    bom = max((parse_bom(pages), parse_bom_qty_value_parts(pages), parse_bom_columns(pages)), key=len)
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
