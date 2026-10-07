"""Manufacturer datasheet links for the parts cross-reference. The site links to the maker's own
copy and never serves one: datasheets are the manufacturers' copyright (the same 'cache locally,
link publicly' rule as vendor build documents). candidates() proposes URLs from each maker's naming
pattern; `pcblib datasheets` checks them and records the ones that answer with a PDF in
datasheets.json, which the export reads. A local copy is cached under data/cache/datasheets/ for
the owner's reference. Generic entries (GE, NPN, a bare zener voltage) have no datasheet."""
from __future__ import annotations

import json
import re
from pathlib import Path

TABLE = Path(__file__).with_name("datasheets.json")

TI = "https://www.ti.com/lit/ds/symlink/{}.pdf"
NJM = "https://www.nisshinbo-microdevices.co.jp/en/pdf/datasheet/{}_E.pdf"
ONSEMI = "https://www.onsemi.com/download/data-sheet/pdf/{}-d.pdf"
DIODES = "https://www.diodes.com/assets/Datasheets/{}.pdf"
VISHAY = "https://www.vishay.com/docs/{}.pdf"
ADI = "https://www.analog.com/media/en/technical-documentation/data-sheets/{}.pdf"
NEXPERIA = "https://assets.nexperia.com/documents/data-sheet/{}.pdf"

# Makers whose datasheet URLs follow no pattern, or whose file covers a series: part -> URL.
_FIXED: dict[str, str] = {
    "TC1044": "https://ww1.microchip.com/downloads/en/DeviceDoc/21348a.pdf",
    "LT1054": ADI.format("LT1054-1054L"), "LTC1144": ADI.format("1144fa"),
    "7660S": "https://www.renesas.com/en/document/dst/icl7660s-icl7660a-datasheet",
    "7660": "https://www.renesas.com/en/document/dst/icl7660-datasheet",
    "CA3130": "https://www.renesas.com/en/document/dst/ca3130-ca3130a-datasheet",
    "24LC32A": "https://ww1.microchip.com/downloads/en/DeviceDoc/21713M.pdf",
    "1N4148": VISHAY.format("81857/1n4148"),
    "1N4001": VISHAY.format("88503/1n4001"), "1N4002": VISHAY.format("88503/1n4001"), "1N4003": VISHAY.format("88503/1n4001"),
    "1N4004": VISHAY.format("88503/1n4001"), "1N4005": VISHAY.format("88503/1n4001"), "1N4007": VISHAY.format("88503/1n4001"),
    "1N5817": VISHAY.format("88525/1n5817"), "1N5818": VISHAY.format("88525/1n5817"), "1N5819": VISHAY.format("88525/1n5817"),
    "UF4007": VISHAY.format("88755/uf4001"),
    # onsemi dropped the J201; Linear Systems still makes it, and its sheet is page 62 of their data book.
    "J201": "https://www.linearsystems.com/_files/ugd/4be30b_607189520e6a46f6a40c6d98393625e8.pdf#page=62",
}
# A series datasheet: the part's TI file is named after the series.
_TI_NAMES: dict[str, list[str]] = {
    "4558": ["rc4558"], "741": ["ua741", "lm741"], "1458": ["mc1458"], "NE555": ["ne555"], "NE556": ["ne556"],
    "LM301A": ["lm301a"], "LF353": ["lf353"], "LF347": ["lf347"], "LF351": ["lf351"], "LF412": ["lf412"],
    "78L05": ["ua78l"], "L78L05": ["ua78l"], "LM78L05": ["ua78l", "lm78l"], "L78L33": ["ua78l"], "78L15": ["ua78l"],
    "7805": ["ua78", "lm340"], "7806": ["ua78"], "7809": ["ua78"], "7812": ["ua78"], "7815": ["ua78"],
}


def _ti(part: str) -> list[str]:
    if part in _TI_NAMES:
        return [TI.format(n) for n in _TI_NAMES[part]]
    m = re.fullmatch(r"CD(4\d{3,4})(UB)?", part)
    if m:
        return [TI.format(f"cd{m.group(1)}{'ub' if m.group(2) else 'b'}".lower())]
    return [TI.format(part.lower())]


def candidates(category: str, part: str) -> list[str]:
    """Datasheet URLs to try for a part, most likely first ([] for a generic entry)."""
    p = part.upper()
    if p in _FIXED:
        return [_FIXED[p]]
    if not re.search(r"\d", p) or re.fullmatch(r"\d+V\d*|\d+(?:\.\d+)?V", p):
        return []  # GE, NPN, LDR, 9V1: no part number
    out: list[str] = []
    if category == "IC":
        out += _ti(p)
        m = re.fullmatch(r"(?:NJM|JRC)?(\d{3,5})[A-Z]*", p)
        if m:
            out.append(NJM.format(f"NJM{m.group(1)}"))
        out.append(ADI.format(p))
    elif category == "Q":
        out += [ONSEMI.format(p.lower()), DIODES.format(p), NEXPERIA.format(p)]
        m = re.fullmatch(r"(BC5\d)(\d)[A-C]?", p)
        if m:
            out.insert(0, ONSEMI.format("bc546"))  # onsemi's BC546-BC550 sheet covers the series
    elif category == "D":
        out += [ONSEMI.format(p.lower()), DIODES.format(p), VISHAY.format(p.lower())]
    elif category == "OPTO":
        out += [ONSEMI.format(p.lower()), VISHAY.format(p.lower())]
    return list(dict.fromkeys(out))


def table() -> dict[str, str]:
    """Verified links: '<category>:<part>' -> URL."""
    try:
        return json.loads(TABLE.read_text())
    except (OSError, ValueError):
        return {}
