"""Read a KiCad Interactive HTML BOM (ibom) export: the page embeds `pcbdata`
as LZString-compressed JSON whose `bom.both` rows carry every designator with
its value and footprint. Exact, no OCR."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from .models import BomRow
from .normalize import normalize_row, is_plausible


def _pcbdata_from_html(html: str) -> dict | None:
    m = re.search(r'var pcbdata = JSON\.parse\(LZString\.decompressFromBase64\("([^"]+)"\)\)', html)
    if m:
        import lzstring
        return json.loads(lzstring.LZString().decompressFromBase64(m.group(1)))
    m = re.search(r"var pcbdata = (\{.*?\});\s*\n", html, re.S)
    if m:
        return json.loads(m.group(1))
    return None


def parse_ibom(path: Path) -> list[BomRow]:
    """`path` is an ibom .html or a .zip containing one."""
    html = ""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".html") and not n.startswith("__MACOSX")]
            if not names:
                return []
            html = z.read(names[0]).decode("utf-8", errors="replace")
    else:
        html = path.read_text(errors="replace")
    data = _pcbdata_from_html(html)
    if not data:
        return []
    rows: list[BomRow] = []
    seen: set[str] = set()
    bom = data.get("bom", {})
    fields = bom.get("fields") or {}  # ibom >= 2.4: footprint id -> [Value, Footprint, ...]
    for entry in bom.get("both", []):
        if entry and isinstance(entry[0], (list, tuple)):
            # New layout: the entry is the list of [ref, footprint id] pairs.
            for ref, fid in entry:
                fv = fields.get(str(fid)) or fields.get(fid) or []
                value = str(fv[0]) if fv else ""
                footprint = str(fv[1]) if len(fv) > 1 else ""
                _add(rows, seen, str(ref), value, footprint)
            continue
        if len(entry) < 4:
            continue
        _qty, value, footprint, refs = entry[0], str(entry[1]), str(entry[2]), entry[3]
        for ref_pair in refs:
            ref = str(ref_pair[0]) if isinstance(ref_pair, (list, tuple)) else str(ref_pair)
            _add(rows, seen, ref, value, footprint)
    return rows


def _add(rows: list[BomRow], seen: set[str], ref: str, value: str, footprint: str) -> None:
    if ref in seen or not value or value.upper() in ("DNP", "NC", "~"):
        return
    seen.add(ref)
    ptype = footprint.split(":")[-1].replace("_", " ")
    nr = normalize_row(BomRow(ref=ref, value=value, part_type=ptype))
    if is_plausible(nr):
        rows.append(nr)
