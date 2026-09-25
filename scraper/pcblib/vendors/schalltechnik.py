"""Schalltechnik_04 adapter: a German kit maker that stopped selling in 2022 and keeps its
build instructions online. Each instruction is a multi-page WordPress post whose 'Required
Parts' page holds quantity | type shortcode tables per section (no designators)."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://schalltechnik04.de"
INDEX = f"{BASE}/en/instructions"
_SKIP = {"ms-truebypass"}
_UTILITY = re.compile(r"looper|bypass|vong", re.I)
_BASED_ON = {"guma-drive": "Mad Professor Sweet Honey Overdrive", "guma-antique": "Mad Professor Sweet Honey Overdrive", "kasza": "", "paranoia": "",
             "pumpernickel": "", "ne_04-v2": "", "omnilooper": ""}
_CATEGORY = {"paranoia": "EQ / Filter", "ne_04-v2": "Utility", "mini-hp-vong": "EQ / Filter", "mini-lp-vong": "EQ / Filter", "vong-filterung": "EQ / Filter"}
_ROW = re.compile(r"^\s*(\d+)\s*x\s*\|\s*(.+?)\s*$")


def _value_of(kind: str) -> tuple[str, str, str]:
    """('0,1u (100n) (spacing 5.0mm, film)') -> value, part type, category hint."""
    t = kind.strip()
    cat = ""
    if re.search(r"\bpot\b|potentiometer", t, re.I):
        cat = "POT"
        m = re.search(r"\b(\d+(?:[.,]\d+)?[kKM]?)\s*([ABC])\b", t) or re.search(r"\b(\d+(?:[.,]\d+)?[kKM]?)\b", t)
        return (m.group(1) + (m.group(2) if m.lastindex and m.lastindex > 1 else "")) if m else t, "Potentiometer", cat
    if re.search(r"toggle|switch|footswitch", t, re.I):
        kind_ = re.search(r"SPDT|DPDT|3PDT|ON-OFF-ON|ON-ON|ON-OFF", t, re.I)
        return kind_.group(0).upper() if kind_ else "switch", "Toggle switch" if "toggle" in t.lower() else "Switch", "SW"
    if re.search(r"\bjack\b|\bknob|enclosure|screw|wire|standoff|cable|socket|header|battery", t, re.I):
        return "", "", "skip"
    paren = re.findall(r"\(([^()]*)\)", t)
    head = re.sub(r"\s*\(.*$", "", t).strip()
    alt = next((p for p in paren if re.fullmatch(r"\d+(?:[.,]\d+)?\s*[pnuµ]F?|\d+(?:\.\d+)?[kKMR]?", p.strip())), "")
    value = alt or head.split()[0] if head else t
    value = value.replace(",", ".")
    kinds = " ".join(paren).lower()
    ptype = "Ceramic capacitor" if "ceramic" in kinds else "Film capacitor" if "film" in kinds else "Electrolytic capacitor" if "electrolytic" in kinds else ""
    if not re.fullmatch(r"[\d.]+\s*[pnuµ]?F?[kKMR]?|[A-Za-z0-9][A-Za-z0-9./-]{1,14}", value) or re.fullmatch(r"[a-z]+", value) or ":" in value:
        return "", "", "skip"
    if re.match(r"^LED\b", head, re.I):
        return "LED", head, "LED"
    if re.fullmatch(r"\d+(?:\.\d+)?\s*[mu]H", value, re.I):
        return value, "Inductor", "L"
    return value, ptype, ""


def parse_shortcode_tables(html: str) -> list[BomRow]:
    text = _html.unescape(re.sub(r"<br\s*/?>", "\n", html))
    text = re.sub(r"<[^>]+>", "", text)
    rows: list[BomRow] = []
    section = ""
    for ln in text.splitlines():
        m = re.search(r"\[table caption=[”\"']([^”\"'\n]*)", ln)
        if m:
            section = m.group(1).strip().lower()
            continue
        m = _ROW.match(ln)
        if not m:
            continue
        qty, kind = m.groups()
        kind = re.sub(r"\s*\|.*$", "", kind)
        value, ptype, cat = _value_of(kind)
        if cat == "skip" or not value:
            continue
        if not ptype and section:
            ptype = {"resistors": "Resistor", "capacitors": "Capacitor", "semiconductors": "", "mechanical": ""}.get(section.split()[0], "")
        r = normalize_row(BomRow(ref=f"×{qty}", value=value, part_type=ptype, notes="shopping list", category=cat))
        if cat or is_plausible(r):
            rows.append(r)
    return rows


@register
class Schalltechnik(Adapter):
    vendor = "schalltechnik"

    def list_targets(self) -> Iterable[str]:
        h = self.f.get_text(INDEX, ".html") or ""
        for slug in sorted(set(re.findall(r'href="https://schalltechnik04\.de/en/instructions/([a-z0-9_-]+)"', h))):
            if slug not in _SKIP:
                yield slug

    def parse(self, slug: str) -> Circuit | None:
        url = f"{INDEX}/{slug}"
        h = self.f.get_text(url, ".html")
        if not h:
            return None
        body = (re.search(r'itemprop="articleBody">(.*?)</article>', h, re.S) or [None, h])[1]
        body = re.sub(r"<nav.*?</nav>|<div class=\"mpp-toc[^\"]*\">.*?</nav></div>", "", body, flags=re.S)
        title = clean_text(_html.unescape((re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [None, slug])[1]))
        title = re.sub(r"\s*[–-]\s*Schalltechnik_04$", "", title)
        name = re.sub(r"_", " ", title).replace("NE 04", "NE_04")
        text = html_to_text(body)
        desc = " ".join(p for p in text.split("\n") if len(p) > 40 and "[table" not in p)[:700]
        enclosure = find_enclosure(text)
        parts_page = ""
        for p, label in re.findall(r'href="(https://schalltechnik04\.de/en/instructions/[a-z0-9_-]+/\d+)"[^>]*>\s*([^<]+)<', h):
            if re.search(r"parts", label, re.I):
                parts_page = p
                break
        pots = re.findall(r"<strong>([A-Za-z][A-Za-z.\- ]{1,14})</strong>\s*-?\s*Pot", body) + re.findall(r"\b([A-Za-z][A-Za-z.]{1,12})-Pot\b", text)
        controls = list(dict.fromkeys(p.strip(" .-").replace(".", "/").title() if p.isupper() or p.islower() or "." in p else p.strip(" .-") for p in pots))
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=url, based_on=_BASED_ON.get(slug, ""), description=desc, currency="EUR",
                    in_stock=False, doc_url=parts_page or url, enclosure=enclosure, tags=["kits discontinued"], controls=controls)
        c.extra_docs["Instructions"] = url
        if parts_page:
            page = self.f.get_text(parts_page, ".html") or ""
            c.bom = parse_shortcode_tables(page)
        c.category = _CATEGORY.get(slug) or ("Utility" if _UTILITY.search(slug) else classify(name, c.based_on, desc[:300]))
        if not c.controls:
            n = sum(int(r.ref[1:]) for r in c.bom if r.category == "POT" and r.ref.startswith("×"))
            c.controls = [f"{n} knobs"] if n > 1 else ["1 knob"] if n else []
        return c
