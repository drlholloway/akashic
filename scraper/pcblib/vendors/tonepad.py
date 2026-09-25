"""Tonepad adapter: the classic ASP catalog of layouts for clones of well-known pedals. Each
project page lists layout PDFs (served only after the project page has been visited, with
the page as referer); the layout page carries a parts list as 'R1, R2 – 1M' lines or, for
value-labelled layouts, as 'qty - value' counts per section."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..paths import CACHE_DIR
from ..pdf import _tesseract_cached, pdf_text_pages, render_page
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

BASE = "https://www.tonepad.com"
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_REFS = re.compile(r"^([A-Z]{1,3}(?:\d{1,3}|[a-z])(?:\s*(?:,|-|–|to)\s*[A-Z]{0,3}(?:\d{1,3}|[a-z]))*)\s*[–\-]\s*(.+?)\s*$")
_TAPER = {"lin": "B", "linear": "B", "log": "A", "audio": "A", "rev": "C", "reverse": "C", "rlog": "C"}
_QTY = re.compile(r"^(\d{1,2})\s*[–\-]\s*(.+?)\s*$")
_PN = re.compile(r"\b((?:2N|2SC|2SA|BC|MPSA|MPS|J|TL0|LM|NE|OP|CA|JRC|RC|MC|CD|4|1N|BAT)\w{2,8})\b")


def _text(h: str) -> str:
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", h or "", flags=re.S | re.I)
    return clean_text(_html.unescape(re.sub(r"<[^>]+>", " ", h)))


def _expand(refs: str) -> list[str]:
    out: list[str] = []
    pre = ""
    for part in re.split(r"\s*,\s*", refs):
        m = re.fullmatch(r"([A-Z]*)(\d+)\s*(?:-|–|to)\s*([A-Z]*)(\d+)", part.strip())
        if m:
            pre = m.group(1) or pre
            out.extend(f"{pre}{i}" for i in range(int(m.group(2)), int(m.group(4)) + 1))
        elif part.strip():
            m2 = re.match(r"([A-Z]+)", part.strip())
            pre = m2.group(1) if m2 else pre
            out.append(part.strip() if re.match(r"[A-Z]", part.strip()) else pre + part.strip())
    return out


def parse_layout_list(text: str) -> tuple[list[BomRow], int]:
    """Parts rows and a knob count from a layout page's text. Lines carry several segments
    separated by wide gaps (the columns of the parts box)."""
    rows: list[BomRow] = []
    seen: set[str] = set()
    knobs = 0
    for ln in text.splitlines():
        for seg in re.split(r"\s{3,}", ln.strip()):
            seg = re.sub(r"\s*\((?:\d+[kKM]\d*|[A-Za-z0-9,\s]{1,12})\)$", "", seg)  # '(3k3)' twin spellings, '(optional)'
            m = _REFS.match(seg)
            if m:
                refs, value = m.groups()
                value = re.sub(r"\*+$", "", value).strip()
                pot = bool(re.search(r"\bpot\b|potentiometer", value, re.I))
                if pot:
                    knobs += len(_expand(refs))
                if "(" in value and not re.match(r"^\d", value):  # 'High-gain darlington (2N5306, MPSA14, etc)'
                    pn = _PN.search(value[value.index("("):])
                    value = pn.group(1) if pn else value
                value = re.sub(r"\s+(?:linear|log|audio|reverse)?\s*pot.*$|\s+electro.*$|\s+or\s.*$|\s+to\s.*$", "", value, flags=re.I).strip()
                for ref in _expand(refs):
                    if ref in seen or len(value) > 24:
                        continue
                    nr = normalize_row(BomRow(ref=ref, value=value, category="POT" if pot else ""))
                    if pot or is_plausible(nr):
                        seen.add(ref)
                        rows.append(nr)
                continue
            m = _QTY.match(seg)
            if m:  # value-labelled layouts count parts per value: '2 - 6.8k (6k8)', '1 - 100k Lin'
                qty, value = m.groups()
                value = re.sub(r"\s*\(.*?\)|\s*/\s*NP.*$|\s+Tant\.?$|\s*\*.*$", "", value).strip()
                mp = re.match(r"^(\d+(?:\.\d+)?[kKM]?)\s+(Lin|Linear|Log|Audio|Rev|Reverse|RLog)\b", value, re.I)
                if mp:
                    knobs += int(qty)
                    nr = normalize_row(BomRow(ref=f"×{qty}", value=_TAPER[mp.group(2).lower()] + mp.group(1), part_type="Potentiometer", category="POT", notes="shopping list"))
                    rows.append(nr)
                    continue
                nr = normalize_row(BomRow(ref=f"×{qty}", value=value, notes="shopping list"))
                if is_plausible(nr):
                    rows.append(nr)
    return rows, knobs


@register
class Tonepad(Adapter):
    vendor = "tonepad"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.meta: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        cat = self.f.get_text(f"{BASE}/catalog2.asp?projectType=fx", ".html") or ""
        for row in _ROW.findall(cat):
            m = re.search(r'href="project\.asp\?id=(\d+)">([^<]+)</a></td><td>([^<]*)</td><td>(?:<span[^>]*>)?([^<]*)', row)
            if not m:
                continue
            pid, name, category, difficulty = m.groups()
            price = re.search(r"\$(\d+(?:\.\d+)?)", row)
            img = re.search(r'src="(/cart/[^"]+)"', row)
            self.meta[pid] = {"name": _html.unescape(name).strip(), "category": category.strip(), "difficulty": difficulty.strip(),
                              "price": float(price.group(1)) if price else None, "image": (BASE + img.group(1)) if img else ""}
            yield pid

    def parse(self, pid: str) -> Circuit | None:
        meta = self.meta.get(pid)
        if not meta:
            return None
        url = f"{BASE}/project.asp?id={pid}"
        page = self.f.get_text(url, ".html") or ""
        text = _text(page)
        desc = re.search(r"Description\s+(.*?)\s+Status\s+(\w+)", text)
        description = clean_text(desc.group(1)) if desc else ""
        status = desc.group(2) if desc else ""
        comments = re.search(r"Comments\s+(.*?)(?:\s+For offboard wiring|\s+Check out these|\s+Buy\b|$)", text)
        if comments and len(comments.group(1)) > 20:
            description = (description + " " + clean_text(comments.group(1))[:600]).strip()
        files = re.findall(r'href="getFileInfo\.asp\?id=(\d+)"[^>]*>([^<]+)<', page)
        revs = re.findall(r"(tonepad_\w+\.pdf)\s+[\d.]+\s*KB\s*--\s*([^\n]+?)(?=\s+tonepad_|\s+Order Printed|\s+Comments|$)", text)
        name = meta["name"]
        c = Circuit(vendor=self.vendor, slug=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), name=name, url=url, based_on=name,
                    description=description, price=meta["price"], currency="USD", in_stock=True, doc_url=url, image_url=meta["image"],
                    tags=[t for t in (meta["difficulty"].title(), status.title()) if t])
        if files:
            fid, fname = files[0]
            c.extra_docs["Layout"] = f"{BASE}/getFileInfo.asp?id={fid}"
            for fid2, fname2 in files[1:]:
                c.extra_docs[fname2] = f"{BASE}/getFileInfo.asp?id={fid2}"
            file_url = f"{BASE}/getFile.asp?id={fid}"
            pdf = self.f.get_file(file_url, ".pdf", headers={"Referer": url})
            if pdf and pdf.read_bytes()[:5] != b"%PDF-":
                # The download needs the session that a live visit to the project page creates;
                # a cached project page made no visit, so visit now and fetch the file again.
                pdf.unlink(missing_ok=True)
                pdf.with_suffix(".pdf.json").unlink(missing_ok=True)
                try:
                    self.f.client.get(url)
                except Exception:
                    pass
                pdf = self.f.get_file(file_url, ".pdf", headers={"Referer": url})
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_url = f"{BASE}/getFileInfo.asp?id={fid}"
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                ptext = "\n".join(pages)
                mv = re.search(r"Rev\.?\s*([\d._]+)", ptext)
                c.doc_version = mv.group(1).strip("._") if mv else ""
                c.enclosure = find_enclosure(ptext)
                c.bom, knobs = parse_layout_list(ptext)
                if len(c.bom) < 8 and len(ptext.strip()) < 200:  # an image-only layout: OCR it with the columns kept
                    png = CACHE_DIR / self.vendor / f"{c.slug}-p1.png"
                    if not png.exists():
                        render_page(pdf, 1, png, dpi=300)
                    for psm in (4, 6):
                        rows, k = parse_layout_list(_tesseract_cached(png, psm, preserve=True))
                        rows = [r for r in rows if not r.ref.startswith("×") or r.sort_key > 0 or r.category in ("D", "Q", "IC", "POT")]
                        if len(rows) > len(c.bom):
                            c.bom, knobs = rows, k
                    for r in c.bom:
                        r.notes = (r.notes + "; OCR").strip("; ")
                named = [r.ref.title() for r in c.bom if r.category == "POT" and re.fullmatch(r"[A-Za-z][A-Za-z /\-]{2,15}", r.ref)]
                knobs = knobs or sum(int(r.ref[1:]) for r in c.bom if r.category == "POT" and r.ref.startswith("×"))
                c.controls = named or ([f"{knobs} knobs" if knobs > 1 else "1 knob"] if knobs else [])
                if revs:
                    lay = re.split(r"\s*,\s*|\.?\s*Rev\b", revs[0][1], 1)[0]
                    c.subtitle = clean_text(lay)[:40] if lay.strip().lower() != name.lower() else ""  # the layout's own name (CompaRous, Revolcador)
        c.category = classify(name, name, meta["category"] + ". " + description)
        return c
