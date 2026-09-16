"""Normalize component values so that 1K5, 1.5k, 1k5 and 1500 all match.

Canonical forms:
  resistors   -> "1.5k", "560", "1M", "4.7k"      (ohms implied)
  capacitors  -> "4.7u", "22n", "100p", "1u"      (farads implied)
  inductors   -> "100mH" style left mostly alone, prefixed by category
  everything else (ICs, transistors, diodes, pots) -> uppercased, whitespace collapsed
"""
from __future__ import annotations

import re

from .models import BomRow

_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3,
       "k": 1e3, "K": 1e3, "M": 1e6, "R": 1.0, "": 1.0}

# 1K5, 4k7, 2M2, 560R, 1n, 33pF, 4.7uF, 100n, 0.1uF, 1u, 10uF, 4u7
_VAL_RE = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*([pnuµμmkKMR]?)\s*(\d*)\s*(?:[FfΩΩ]|ohm[s]?|H)?\s*$"
)

_POT_RE = re.compile(r"^\s*([ABCW])?\s*(\d+(?:[.,]\d+)?)\s*([kKM]?)\s*(?:ohm)?\s*([ABCW])?\s*(?:\(.*\))?\s*$")


def _parse_si(text: str) -> float | None:
    m = _VAL_RE.match(text)
    if not m:
        return None
    whole, prefix, frac = m.groups()
    whole = whole.replace(",", ".")
    if frac:  # "4k7" style: prefix acts as decimal point
        if "." in whole:
            return None
        num = float(f"{whole}.{frac}")
    else:
        num = float(whole)
    return num * _SI.get(prefix, 1.0)


def _fmt(num: float, unit_prefixes: list[tuple[float, str]]) -> str:
    for scale, suffix in unit_prefixes:
        if num >= scale * 0.9999:
            v = num / scale
            s = f"{v:.3g}".rstrip("0").rstrip(".") if "." in f"{v:.3g}" else f"{v:.3g}"
            return f"{s}{suffix}"
    s = f"{num:.3g}"
    return s


_R_PREFIX = [(1e6, "M"), (1e3, "k"), (1.0, "")]
_C_PREFIX = [(1e-3, "m"), (1e-6, "u"), (1e-9, "n"), (1e-12, "p")]
_L_PREFIX = [(1.0, "H"), (1e-3, "mH"), (1e-6, "uH")]

_CATEGORY_BY_REF = [
    (re.compile(r"^R\d+[A-Z]?$", re.I), "R"),
    (re.compile(r"^(RPD|LEDR|CLR|RB\d*)$", re.I), "R"),
    (re.compile(r"^C\d+[A-Z]?$", re.I), "C"),
    (re.compile(r"^D\d+[A-Z]?$", re.I), "D"),
    (re.compile(r"^(Z|ZD)\d+$", re.I), "D"),
    (re.compile(r"^Q\d+[A-Z]?$", re.I), "Q"),
    (re.compile(r"^(IC|U)\d+[A-Z]?$", re.I), "IC"),
    (re.compile(r"^L\d+$", re.I), "L"),
    (re.compile(r"^(X|XT|XTAL|Y)\d+$", re.I), "XTAL"),
    (re.compile(r"^(LED|LD)\d*$", re.I), "LED"),
    (re.compile(r"^(SW|S|FS)\d*$", re.I), "SW"),
    (re.compile(r"^(TR|TRIM|VR|RV|T)\d+$", re.I), "TRIM"),
    (re.compile(r"^(LDR|OPTO|VTL|OC)\d*$", re.I), "OPTO"),
    (re.compile(r"^(J|JACK)\d*$", re.I), "CONN"),
]

_TYPE_HINTS = [
    ("socket", "CONN"), ("enclosure", "HW"), ("knob", "HW"), ("hardware", "HW"),
    ("screw", "HW"), ("wire", "HW"), ("battery", "HW"), ("standoff", "HW"), ("nut", "HW"),
    ("trimmer", "TRIM"), ("trim pot", "TRIM"),
    ("pot", "POT"), ("potentiometer", "POT"),
    ("resistor", "R"), ("capacitor", "C"),
    ("zener", "D"), ("diode", "D"), ("led", "LED"), ("rectifier", "D"),
    ("transistor", "Q"), ("jfet", "Q"), ("mosfet", "Q"), ("bjt", "Q"),
    ("op-amp", "IC"), ("opamp", "IC"), ("op amp", "IC"), ("dip", "IC"), ("ic", "IC"),
    ("regulator", "IC"), ("charge pump", "IC"), ("bbd", "IC"), ("pt2399", "IC"),
    ("inductor", "L"), ("crystal", "XTAL"),
    ("switch", "SW"), ("footswitch", "SW"), ("toggle", "SW"),
    ("photocell", "OPTO"), ("ldr", "OPTO"), ("vactrol", "OPTO"), ("optocoupler", "OPTO"),
    ("jack", "CONN"), ("socket", "CONN"), ("header", "CONN"),
]


_EARLY_HINTS = ("socket", "enclosure", "knob", "standoff")


def categorize(ref: str, part_type: str, value: str = "") -> str:
    r = re.sub(r"-\d+$", "", ref.strip())  # D1-2 -> D1 (ranges)
    v = value.upper()
    if re.search(r"\b[SD]P[SD]T\b|3PDT|4PDT", v):
        return "SW"
    if "LED" in v and not re.match(r"^(IC|U|Q)\d", r):
        return "LED"
    t0 = part_type.lower()
    for hint in _EARLY_HINTS:
        if hint in t0:
            return "CONN" if hint == "socket" else "HW"
    for rx, cat in _CATEGORY_BY_REF:
        if rx.match(r):
            return cat
    t = part_type.lower()
    for hint, cat in _TYPE_HINTS:
        if hint in t:
            return cat
    # Named pots: VOLUME, GAIN, TONE ... (PedalPCB style)
    if r.isalpha() and r.isupper() and len(r) >= 3:
        return "POT"
    return "OTHER"


def normalize_row(row: BomRow) -> BomRow:
    row.category = row.category or categorize(row.ref, row.part_type, row.value)
    if row.category == "POT" and re.search(r"[SD]P[SD]T|3PDT|4PDT", row.value.upper()):
        row.category = "SW"
    raw = row.value.strip()
    if row.category in ("D", "Q", "IC", "OPTO"):
        raw = re.sub(r"[*+†‡]+$", "", raw).strip()          # footnote markers: 2N5458**, 1N4148+
        raw = re.sub(r"\s+[A-Z]$", "", raw)                  # stray column bleed: "1N5817 S"
    row.norm_value = re.sub(r"\s+", " ", raw).upper()
    row.sort_key = 0.0

    if row.category == "R" or row.category == "TRIM":
        n = _parse_si(raw)
        if n is not None:
            row.norm_value = _fmt(n, _R_PREFIX)
            row.sort_key = n
    elif row.category == "C":
        n = _parse_si(raw)
        if n is not None:
            # Bare numbers like "100" for caps are ambiguous; only accept with a prefix
            if re.search(r"[pnuµμ]", raw) or "." in raw:
                row.norm_value = _fmt(n, _C_PREFIX)
                row.sort_key = n
    elif row.category == "L":
        n = _parse_si(raw)
        if n is not None:
            row.norm_value = _fmt(n, _L_PREFIX)
            row.sort_key = n
    elif row.category == "POT":
        m = _POT_RE.match(raw)
        if m:
            t1, num, prefix, t2 = m.groups()
            taper = (t1 or t2 or "").upper()
            n = float(num.replace(",", ".")) * _SI.get(prefix, 1.0)
            row.norm_value = f"{taper}{_fmt(n, _R_PREFIX)}"
            row.sort_key = n
    return row


_JUNK = re.compile(r"^(omit|omitted|jumper|link|wire|none|n/?a|empty|—|-|your choice|see notes?|see text|optional|tbd|\?+)$", re.I)


def is_plausible(row: BomRow) -> bool:
    """Drop rows the table parsers picked up from prose (e.g. 'C10 is omitted')."""
    if _JUNK.match(row.value.strip()):
        return False
    if row.category in ("D", "Q", "IC") and (re.fullmatch(r"[RCLDQ]\d+", row.value.strip().upper()) or len(row.value.strip()) < 3):
        return False
    if row.category in ("R", "C", "L") and row.sort_key <= 0:
        return False
    if row.category in ("R", "C") and not re.search(r"\d", row.value):
        return False
    return True
