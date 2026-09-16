"""Build-document parsing: parts list extraction and schematic page rendering.

Text extraction uses poppler's `pdftotext -layout` (column alignment preserved),
rendering uses PyMuPDF. Both PedalPCB and AionFX docs share the same table
shape:  LOCATION|PART   VALUE   TYPE   NOTES
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pymupdf as fitz

from .models import BomRow
from .normalize import normalize_row, is_plausible
from .paths import CACHE_DIR, DATA_DIR

_HEADER_RE = re.compile(r"^\s*(LOCATION|PART|REF|DESIGNATOR|PART\s*#?)\s+VALUE\s+(TYPE|DESCRIPTION)", re.I)
_PAGE_BREAK = "\f"


def pdf_text_pages(pdf: Path) -> list[str]:
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, check=False,
    ).stdout
    return out.split(_PAGE_BREAK)


def _col_starts(header: str) -> dict[str, int]:
    cols = {}
    for name in ("VALUE", "TYPE", "DESCRIPTION", "NOTES"):
        i = header.upper().find(name)
        if i >= 0:
            cols[name] = i
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
                    continue
                # Footer / page-number lines end the table
                if re.search(r"Copyright|Page \d+ of \d+|PARTS LIST|^\s*\S.*\s{6,}\d{1,2}\s*$", ln) and not re.match(r"^\s*[A-Z]+\d*\s+\S", ln):
                    if "Copyright" in ln or re.search(r"Page \d+ of", ln):
                        break
                    continue
                ref = ln[:v0].strip() if v0 else ""
                # Running page footer: "HEXATRON OPTICAL PHASER          4"
                if re.search(r"\s{4,}\d{1,2}\s*$", ln) and not re.search(r"\d", ref):
                    continue
                if not ref or " " in ref or len(ref) > 12:
                    # continuation of a notes cell, append to previous row
                    if rows and ln.strip() and v0 and not ln[:v0].strip():
                        tail = ln[(n0 or t0 or v0):].strip()
                        if tail:
                            rows[-1].notes = (rows[-1].notes + " " + tail).strip()
                    continue
                value = ln[v0:t0].strip() if t0 else ln[v0:].strip()
                ptype = ln[t0:n0].strip() if (t0 and n0) else (ln[t0:].strip() if t0 else "")
                notes = ln[n0:].strip() if n0 else ""
                if not value:
                    continue
                key = f"{ref}|{value}|{ptype}"
                if key in seen:
                    continue
                seen.add(key)
                nr = normalize_row(BomRow(ref=ref, value=value, part_type=ptype, notes=notes))
                if is_plausible(nr):
                    rows.append(nr)
    return rows


_COL_HEADERS = re.compile(r"RESISTORS|CAPACITORS|DIODES|TRANSISTORS|SEMICONDUCTORS|POTENTIOMETERS|\bICS?\b|SWITCHES|PARTS LIST|B\.?O\.?M\.?|BILL OF MATERIALS", re.I)
_COL_DESIG = re.compile(r"(?<![A-Z0-9])((?:R|C|D|Q|IC|U|L|SW|Z|ZD|LED|VR|TR|OPTO|X|J)\d+[A-Z]?)[ \t]+(\S+(?:[ \t](?:Red|Green|Blue|Yellow|White|Amber)?[ \t]?(?:LED|Zener|zener|elec))?)")
_COL_POT = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z .\-/]{1,14}?)[ \t]{2,}([ABCW]\d+(?:[.,]\d+)?[KM]|[ABCW]\d{2,}|\d+(?:[.,]\d+)?[KM]?[ABCW])(?![A-Z0-9])")


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
            if ref in seen or val.upper() in {"VALUE", "QTY", "TYPE"}:
                continue
            seen.add(ref)
            nr = normalize_row(BomRow(ref=ref, value=val.strip()))
            if is_plausible(nr):
                rows.append(nr)
        for ref, val in _COL_POT.findall(text):
            ref = ref.strip()
            if ref in seen or ref.upper() in {"QTY", "TYPE", "VALUE", "PART", "LOCATION"} or _COL_HEADERS.fullmatch(ref):
                continue
            seen.add(ref)
            rows.append(normalize_row(BomRow(ref=ref, value=val.replace(" ", ""), part_type="Potentiometer", category="POT")))
    return rows


def find_schematic_page(pages: list[str]) -> int | None:
    """1-based page index whose heading is SCHEMATIC (or 'Schematic Diagram')."""
    for idx, page in enumerate(pages, start=1):
        head = "\n".join(page.strip().splitlines()[:4]).upper()
        if re.search(r"\bSCHEMATIC\b", head) and "TABLE OF CONTENTS" not in head:
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
    bom = parse_bom(pages)
    if len(bom) < 4:
        bom = parse_bom_columns(pages) or bom
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
