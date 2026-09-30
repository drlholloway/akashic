"""Scientific Guitarist adapter: DIY projects written up on a Wix site, each linking a GitHub
repository with the Eagle project. The parts list is Eagle's BOM export: a per-designator CSV
('Part;Value;Device;Package') and a grouped one ('Qty;Value;Device;Package;Parts;Description'),
either at the top of the repository or inside a '<Name>_FullProject.zip' (sometimes one zip
deeper). ICs and switches often have an empty value, so the device names them (PT2399_TH ->
PT2399, SPDT.LUGS -> SPDT); pots carry their knob names (TIME1, MIX2) and tapers (50kB), and a
DUALGANG device is a dual-gang pot. Pages without a repository (articles) are skipped."""
from __future__ import annotations

import csv
import html as _html
import io
import json
import re
import zipfile
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SITE = "https://scientificguitarist.wixsite.com/home"
LISTING = f"{SITE}/projects"
OWNER = "brianthornock"
_REPO = re.compile(rf"https?://github\.com/{OWNER}/([A-Za-z0-9_.-]+)")
_NOT_PROJECTS = {"projects", "articles", "blog", "contact", "gallery", "how-to-design-guitar-pedals", "schematic-elements",
                 "sustainer-reverse-engineering", "programming-attiny-mcu-s", "why-gibson-headstocks-break", "tone-controls"}
# Repositories that are software or guitar parts, not a pedal board with a parts list.
_NOT_BOARDS = re.compile(r"programmer|tinylfo|tap_?tempo|examples|pickup|sustainer|bobbin|pwm_lfo", re.I)
_POT_VALUE = re.compile(r"^[ABCW]?\d+(?:\.\d+)?\s?[kKM][ABCW]?$")
_BASED = re.compile(r"(?:based on|clone of|take on|version of|inspired by|modeled after|derived from)\s+(?:the\s+|an?\s+)?"
                    r"([A-Z][\w'’\-]*(?:\s+[A-Z0-9][\w'’\-]*){0,4})")


def _device_value(device: str) -> str:
    """A value from Eagle's device name when the part has none: PT2399_TH -> PT2399, TL072P -> TL072,
    SPDT.LUGS -> SPDT, LED.3 -> LED."""
    d = device.split(".")[0]
    d = re.sub(r"[_-](?:TH|SMD|DIP\d*|SOIC\d*|THT|LUGS)$", "", d, flags=re.I)
    return d


def _rows_from_csv(text: str, descriptions: dict[str, str]) -> list[BomRow]:
    head = text.lstrip("\ufeff").split("\n", 1)[0]
    delim = ";" if head.count(";") >= head.count(",") else ","  # the header decides: designator lists hold commas
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=delim)
    header = [h.strip().lower() for h in next(reader, [])]
    rows: list[BomRow] = []
    if header[:2] == ["part", "value"]:
        records = [(r[0].strip(), r[1].strip(), r[2].strip() if len(r) > 2 else "") for r in reader if r and r[0].strip()]
    elif "designator" in header and ("designation" in header or "value" in header):
        idr, iv = header.index("designator"), header.index("designation" if "designation" in header else "value")
        records = [(ref, r[iv].strip(), "") for r in reader if len(r) > max(idr, iv) for ref in re.split(r"[,\s]+", r[idr].strip()) if ref]
    elif "parts" in header and "value" in header:
        iv, ip = header.index("value"), header.index("parts")
        idev = header.index("device") if "device" in header else None
        idesc = header.index("description") if "description" in header else None
        records = []
        for r in reader:
            if len(r) <= ip:
                continue
            for ref in re.split(r"[,\s]+", r[ip].strip()):
                if ref:
                    records.append((ref, r[iv].strip(), r[idev].strip() if idev is not None and len(r) > idev else ""))
                    if idesc is not None and len(r) > idesc and r[idesc].strip():
                        descriptions.setdefault(ref, r[idesc].strip())
    else:
        return []
    for ref, value, device in records:
        dev = device.upper()
        cat, ptype = "", ""
        if "DUALGANG" in dev or re.search(r"\b(?:16MM|9MM|ALPHA|POT)", dev) or (_POT_VALUE.match(value) and not re.match(r"^[RC]\d", ref)):
            cat, ptype = "POT", "Dual" if "DUALGANG" in dev else ""
        if dev.startswith("TRIM") or ref.upper().startswith("TRIM"):
            cat, ptype = "TRIM", "Trimmer"
        if re.search(r"[SD]PDT|[34]PDT|SPST", dev):
            cat = "SW"
        if cat in ("POT", "POT") and not re.search(r"[ABCW]", value.upper().replace("K", "")) and re.search(r"BIAS|TRIM|ADJ|^RLED|^LED", ref, re.I):
            cat, ptype = "TRIM", "Trimmer"  # BIAS1 100k, C_TRIM: an untapered, internal adjustment
        if cat in ("POT", "TRIM") and (not value or value.upper().startswith(("TRIM", "POT"))):
            value = ""  # the footprint name is not a value ('TRIM_US-B25P')
            r = normalize_row(BomRow(ref=ref, value="", part_type=ptype or ("Trimmer" if cat == "TRIM" else ""), category=cat))
            rows.append(r)
            continue
        if not value or value.endswith("."):
            if cat == "SW":
                value = re.search(r"[SD]PDT|[34]PDT|SPST", dev).group(0)
            elif re.match(r"^D\d", ref) and ref in descriptions and not dev.startswith("LED"):
                value = descriptions[ref]  # '1N400x, 1N5817': the diode the grouped export names
            elif dev:
                value = _device_value(device)
        if (dev.startswith("LED") and (not value or value.upper().startswith("LED"))) or re.fullmatch(r"LED\.\d+", value, re.I):
            value, cat = "LED", "LED"  # 'LED.3' is the footprint (3 mm), not a part
        if not value or re.fullmatch(r"(?:HOLE|MOUNT|FIDUCIAL|JUMPER|PAD|TP)\w*", value, re.I):
            continue
        r = normalize_row(BomRow(ref=ref, value=value, part_type=ptype, category=cat))
        if is_plausible(r) or r.category in ("POT", "TRIM", "SW", "LED", "IC", "Q", "D"):
            rows.append(r)
    return rows


def _bom_csvs(names: list[str]) -> list[str]:
    """BOM exports among file names, the per-designator one first."""
    boms = [n for n in names if n.lower().endswith(".csv") and "bom" in n.lower() and not re.search(r"offboard|cpl|pos", n, re.I)]
    return sorted(boms, key=lambda n: (0 if re.search(r"parts", n, re.I) else 1, n))


@register
class ScientificGuitarist(Adapter):
    vendor = "scientificguitarist"

    slugs: set[str] = set()

    def list_targets(self) -> Iterable[str]:
        h = self.f.get_text(LISTING, ".html") or ""
        seen: set[str] = set()
        self.slugs = {sl for sl in re.findall(rf"{re.escape(SITE)}/([a-z0-9-]+)", h) if sl not in _NOT_PROJECTS}
        for slug in re.findall(rf"{re.escape(SITE)}/([a-z0-9-]+)", h):
            if slug in _NOT_PROJECTS or slug in seen:
                continue
            seen.add(slug)
            yield f"{SITE}/{slug}"

    def _contents(self, repo: str) -> list[dict]:
        raw = self.f.get_text(f"https://api.github.com/repos/{OWNER}/{repo}/contents", ".json")
        try:
            data = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def parse(self, url: str) -> Circuit | None:
        page = self.f.get_text(url, ".html")
        if not page:
            return None
        m = _REPO.search(page)
        if not m or _NOT_BOARDS.search(m.group(1)):
            return None
        repo = m.group(1).rstrip(".")
        files = self._contents(repo)
        if not files:
            return None
        heads = [clean_text(_html.unescape(re.sub(r"<[^>]+>", "", h))) for h in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", page, re.S)]
        heads = [h for h in heads if h]
        name = heads[0] if heads else repo
        subtitle = heads[1] if len(heads) > 1 and heads[1] != name else ""
        text = html_to_text(page)
        overview = text.split("Overview", 1)[1] if "Overview" in text else text
        overview = re.split(r"\bHow It Works\b|\bBuild Documentation\b|\bDemo\b", overview)[0]
        overview = clean_text(overview)[:900]
        bm = _BASED.search(overview)
        based_on = clean_text(bm.group(1)) if bm else ""
        own = {w for sl in self.slugs for w in sl.split("-") if len(w) > 3}
        if re.search(r"\b[A-Z]{2,}\d{3}", based_on) or (based_on and based_on.split()[0].lower() in own):
            based_on = ""  # 'the LM386' is the chip it uses; 'the Wobble Box LFO' is one of the author's own projects
        repo_url = f"https://github.com/{OWNER}/{repo}"
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        og = re.search(r'property="og:image"\s+content="([^"]+)"', page)
        c = Circuit(vendor=self.vendor, slug=slug, name=name, subtitle=subtitle, url=repo_url, based_on=based_on,
                    description=overview, category=classify(subtitle, name, overview[:300]), price=None, currency="USD",
                    in_stock=None, doc_url=repo_url, enclosure=find_enclosure(text), image_url=og.group(1) if og else "")
        c.extra_docs["Project page"] = url

        by_name = {f["name"]: f for f in files if f.get("type") == "file"}
        descriptions: dict[str, str] = {}
        odt_list: list[BomRow] = []
        csv_texts: list[tuple[str, str]] = []
        schematic: tuple[str, bytes] | None = None
        for n in _bom_csvs(list(by_name)):
            t = self.f.get_text(by_name[n]["download_url"], ".csv")
            if t:
                csv_texts.append((n, t))
        for n, f in by_name.items():
            if re.search(r"build.*doc|user.?guide|assembly", n, re.I) and n.lower().endswith((".pdf", ".odt")):
                c.extra_docs.setdefault("Build documentation", f["html_url"])
            if re.search(r"schematic", n, re.I) and n.lower().endswith((".pdf", ".png")) and not schematic:
                data = self.f.get_bytes(f["download_url"], "." + n.rsplit(".", 1)[-1].lower())
                if data:
                    schematic = (n, data)
        if not csv_texts or not schematic:
            # The project zip holds the exports, the schematic and the gerbers (sometimes one zip deeper).
            for n, f in by_name.items():
                if not n.lower().endswith(".zip") or f.get("size", 0) > 25_000_000 or re.search(r"ch341|driver", n, re.I):
                    continue
                data = self.f.get_bytes(f["download_url"], ".zip")
                if not data:
                    continue
                self._scan_zip(data, csv_texts, lambda s: None, depth=0)
                if not odt_list:
                    odt_list = self._odt_list(data)
                if not schematic:
                    found: list = []
                    self._scan_zip(data, [], found.append, depth=0)
                    schematic = found[0] if found else None
                if csv_texts and schematic:
                    break
        seen: set[str] = set()
        for n, t in sorted(csv_texts, key=lambda x: (0 if re.search(r"parts", x[0], re.I) else 1)):
            if not re.search(r"parts", n, re.I):
                _rows_from_csv(t, descriptions)  # the grouped export: descriptions for parts with no value
        for n, t in sorted(csv_texts, key=lambda x: (0 if re.search(r"parts", x[0], re.I) else 1)):
            rows = _rows_from_csv(t, descriptions)
            if rows:
                for r in rows:
                    if r.ref not in seen:
                        seen.add(r.ref)
                        c.bom.append(r)
                break
        if len(c.bom) < 8 and schematic and schematic[0].lower().endswith(".pdf"):
            # No BOM export in the repository: the Eagle schematic PDF keeps its labels as text, so pair
            # each designator with its value there.
            from ..pdf import schematic_bom
            pdf_path = CACHE_DIR / self.vendor / f"{slug}-schematic.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(schematic[1])
            paired = schematic_bom(pdf_path, 1)
            if len(paired) > len(c.bom):
                c.bom = paired
        if len(c.bom) < 8 and odt_list:
            c.bom = odt_list  # the build document's shopping list: parts by quantity, no designators
        if schematic:
            n, data = schematic
            png = CACHE_DIR / self.vendor / f"{slug}-schematic.png"
            png.parent.mkdir(parents=True, exist_ok=True)
            try:
                if n.lower().endswith(".pdf"):
                    import pymupdf as fitz
                    with fitz.open(stream=data, filetype="pdf") as d:
                        d[0].get_pixmap(dpi=170).save(png)
                else:
                    png.write_bytes(data)
                c.schematic_local, c.schematic_page = str(png.relative_to(DATA_DIR)), 1
            except Exception:  # noqa: BLE001 - an odd file is not worth losing the board over
                pass
        pots = [r for r in c.bom if r.category == "POT"]
        if pots:
            # 'CLN_GAIN' -> 'Cln Gain', 'PAN1' and 'PAN2' are two knobs -> 'Pan 1', 'Pan 2'
            names = list(dict.fromkeys(re.sub(r"(?<=[A-Za-z])(\d+)$", r" \1", re.sub(r"(?<=[A-Za-z])0$", "", r.ref).replace("_", " ")).title() for r in pots))  # REV0 is the only Rev
            c.controls = names if all(re.fullmatch(r"[A-Za-z][A-Za-z0-9 \-/]*", n) for n in names) else [f"{len(pots)} knobs"]
        return c if c.bom or c.schematic_local else None

    @staticmethod
    def _odt_list(zip_data: bytes) -> list[BomRow]:
        """The build document's parts table ('68R Resistor | 1 | notes'): one row per value, named by
        quantity, as for the shopping lists of other vendors."""
        try:
            z = zipfile.ZipFile(io.BytesIO(zip_data))
            odt = next((n for n in z.namelist() if n.lower().endswith(".odt")), None)
            if not odt:
                return []
            xml = zipfile.ZipFile(io.BytesIO(z.read(odt))).read("content.xml").decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, KeyError):
            return []
        rows: list[BomRow] = []
        for table in re.findall(r"<table:table [^>]*>(.*?)</table:table>", xml, re.S):
            cells = [[_html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<table:table-cell[^>]*>(.*?)</table:table-cell>", r, re.S)]
                     for r in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", table, re.S)]
            if not cells or [h.lower().rstrip(".") for h in cells[0][:2]] != ["part", "qty"]:
                continue
            for row in cells[1:]:
                if len(row) < 2 or not re.fullmatch(r"\d+", row[1].strip()):
                    continue
                m = re.match(r"^(\S+)\s+(.*)$", row[0])
                value, ptype = (m.group(1), m.group(2)) if m else (row[0], "")
                r = normalize_row(BomRow(ref=f"×{row[1].strip()}", value=value, part_type=ptype, notes="shopping list"))
                if is_plausible(r) or r.category in ("POT", "SW", "IC", "Q", "D", "LED"):
                    rows.append(r)
        return rows

    def _scan_zip(self, data: bytes, csv_texts: list, on_schematic, depth: int) -> None:
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return
        names = [n for n in z.namelist() if not n.startswith("__MACOSX")]
        for n in _bom_csvs(names):
            csv_texts.append((n.rsplit("/", 1)[-1], z.read(n).decode("utf-8", errors="replace")))
        for n in names:
            if re.search(r"schematic", n, re.I) and n.lower().endswith((".pdf", ".png")):
                on_schematic((n, z.read(n)))
                break
        if depth == 0 and not _bom_csvs(names):
            for n in names:
                if n.lower().endswith(".zip"):
                    self._scan_zip(z.read(n), csv_texts, on_schematic, depth=1)
