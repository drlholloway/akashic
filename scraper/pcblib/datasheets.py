"""Manufacturer datasheet links for the parts cross-reference. The site links to the maker's own
copy and never serves one: datasheets are the manufacturers' copyright (the same 'cache locally,
link publicly' rule as vendor build documents). candidates() proposes URLs from each maker's naming
pattern; `pcblib datasheets` checks them and records the ones that answer with a PDF in
datasheets.json, which the export reads. A local copy is cached under data/cache/datasheets/ for
the owner's reference. Generic entries (GE, NPN, a bare zener voltage) have no datasheet.
The one exception: a discontinued part whose maker no longer publishes the sheet is served from
app/static/datasheets/, recorded as a relative path ('datasheets/M51134P.pdf'). DISCONTINUED lists
those parts; their sheets come from an archive (Findchips links to The Datasheet Archive, which sits
behind a bot check, so they are downloaded by hand) and host() strips the archive's ad page and
metadata and checks the part number is in the sheet before it is served."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TABLE = Path(__file__).with_name("datasheets.json")
HOSTED = Path(__file__).resolve().parents[2] / "app" / "static" / "datasheets"
FINDCHIPS = "https://www.findchips.com/search/{}"

# Discontinued parts with no maker's copy: sheet name -> the spellings in the library it covers.
# Only parts that are out of production everywhere; a current part (BAT41, 2N5458 from Central,
# THAT2181) gets the maker's link instead.
DISCONTINUED: dict[str, list[str]] = {
    # diodes
    "1N34A": ["1N34A"], "1N270": ["1N270"], "1N60P": ["1N60P"], "1N100": ["1N100"], "1N695": ["1N695"],
    "OA90": ["OA90"], "AA112": ["AA112"], "AA119": ["AA119"], "BA282": ["BA282"], "BA482": ["BA482"],
    "1S1588": ["1S1588", "IS1588"], "1S2473": ["1S2473"], "MA150": ["MA150"], "MA856": ["MA856"],
    # ICs
    "CA3080": ["CA3080"], "LM308": ["LM308"], "LM13600": ["LM13600"], "NE570": ["NE570"], "NE571": ["NE571"],
    "XR2206": ["XR2206"], "MN3101": ["MN3101"], "M51134P": ["M51134P"], "M5216": ["M5216"], "M5218": ["M5218"],
    "M65831AP": ["M65831AP"], "HA1457W": ["HA1457W"], "TA7136P": ["TA7136P"], "UPC4570": ["UPC4570"],
    "TDA7052": ["TDA7052"], "TLP222A": ["TLP222A", "TLP222G"],
    # transistors
    "2SC1815": ["2SC1815", "2SC1815-GR", "2SC1815L-GR"], "2SA1015": ["2SA1015Y"], "2SC828": ["2SC828"],
    "2SC732": ["2SC732"], "2SC536": ["2SC536", "2SC536-F"], "2SC1000": ["2SC1000-GR"], "2SC2240": ["2SC2240", "C2240BL"],
    "2SC2458": ["2SC2458GR"], "2SA970": ["2SA970"], "2SB172": ["2SB172"], "2SD352": ["2SD352"],
    "2SK30A": ["2SK30A", "2SK30A-Y", "2SK30A-GR", "K30A-Y", "2SK30"], "2SK44": ["2SK44-C"], "2SK170": ["2SK170"],
    "2SK209": ["2SK209-GR"], "2SK246": ["2SK246"], "MPF4393": ["MPF4393"], "2N5952": ["2N5952"],
    "BC107": ["BC107", "BC107B", "BC108", "BC108C", "BC109", "BC109C"], "BC182": ["BC182L"], "BC183": ["BC183A", "BC183B"],
    "BC184": ["BC184", "BC184C"], "BC264": ["BC264D"], "2N3565": ["2N3565"], "2N3392": ["2N3391", "2N3391A", "2N3392", "2N3393"],
    "2N4124": ["2N4124"], "2N4125": ["2N4125"], "2N5133": ["2N5133"], "2N5172": ["2N5172"], "2N5306": ["2N5306"],
    "2N5308": ["2N5308"], "2N2646": ["2N2646"], "TIS93": ["TIS93"], "2N404A": ["2N404A"], "2N1302": ["2N1302"],
    "2N1304": ["2N1304"], "2N1306": ["2N1306"], "2N1308": ["2N1308"], "AC127": ["AC127"], "AC128": ["AC128"],
    "AC176": ["AC176"], "OC44": ["OC44"], "OC71": ["OC71"], "OC75": ["OC75"], "OC139": ["OC139"], "NKT275": ["NKT275"],
    # optos
    "VTL5C2": ["VTL5C2"], "VTL5C3": ["VTL5C3"], "NSL-32": ["NSL-32"],
}
_AD = re.compile(r"findchips\.com|datasheetarchive|alldatasheet|datasheetcatalog|datasheet4u", re.I)

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
    # Electric Druid's own chips, and the PT2399 sheet it keeps (Princeton publishes none).
    "PT2399": "https://electricdruid.net/datasheets/PT2399.pdf",
    "TAPLFO3": "https://electricdruid.net/datasheets/TAPLFO3Datasheet.pdf",
    "STOMPLFO": "https://electricdruid.net/datasheets/STOMPLFODatasheet.pdf",
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
    out = [TI.format(part.lower())]
    m = re.fullmatch(r"((?:LM|LF|LMC|TLC|OPA|TL|NE|SN)\w*\d)([A-Z]{1,3})", part)  # a package suffix: LF356N, OPA604AP, TLC27M4AIN
    if m:
        base, suffix = m.groups()
        out += [TI.format((base + suffix[:k]).lower()) for k in range(len(suffix) - 1, -1, -1)]
    return out


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


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _text(page) -> str:
    """A page's text, by tesseract when the page is a scan."""
    t = page.get_text()
    if len(t.split()) > 40 or not shutil.which("tesseract"):
        return t
    with tempfile.TemporaryDirectory() as d:
        png = Path(d) / "p.png"
        page.get_pixmap(dpi=200).save(png)
        return t + subprocess.run(["tesseract", str(png), "-", "--psm", "3"], capture_output=True, text=True).stdout


def host(src: Path, sheet: str, force: bool = False) -> tuple[Path | None, str]:
    """Copy an archived datasheet into app/static/datasheets/<sheet>.pdf without the archive's ad
    pages, links and metadata. Refused (None, reason) when no spelling of the part is in its first pages."""
    import pymupdf as fitz
    doc = fitz.open(src)
    if doc.page_count == 0:
        return None, "not a PDF"
    ads = [i for i, pg in enumerate(doc) if _AD.search(pg.get_text()) and not pg.get_images() and len(pg.get_text().split()) < 150]
    keep = [i for i in range(doc.page_count) if i not in ads]
    if not keep:
        return None, "only ad pages"
    names = {_norm(n) for n in [sheet, *DISCONTINUED.get(sheet, [])]}
    seen = _norm(" ".join(_text(doc[i]) for i in keep[:2]))
    if not force and not any(n in seen for n in names):
        return None, f"{sheet} not found on its first pages (OCR); check it and pass force"
    doc.select(keep)
    for pg in doc:
        for link in list(pg.get_links()):
            if _AD.search(link.get("uri") or ""):
                pg.delete_link(link)
    doc.set_metadata({k: "" for k in doc.metadata if k not in ("format", "encryption")} | {"title": f"{sheet} datasheet"})
    doc.del_xml_metadata()
    HOSTED.mkdir(parents=True, exist_ok=True)
    dst = HOSTED / f"{sheet}.pdf"
    doc.save(dst, garbage=4, deflate=True)
    return dst, f"{len(keep)} pages, {len(ads)} ad page(s) removed"


def sheet_for(name: str) -> str:
    """The DISCONTINUED sheet a downloaded file's name points at ('2SK30A-GR.pdf' -> '2SK30A'), or ''."""
    n = _norm(Path(name).stem)
    for sheet, spellings in DISCONTINUED.items():
        if n in {_norm(x) for x in [sheet, *spellings]}:
            return sheet
    return ""
