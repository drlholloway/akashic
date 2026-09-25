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
    r"^\s*(\d+(?:[.,]\d+)?)\s*([pnuµμmkKMRr]?)\s*(\d*)\s*(?:[FfΩΩ]|ohm[s]?|H)?\s*$"
)

_POT_RE = re.compile(r"^\s*([ABCW])?\s*(\d+(?:[.,]\d+)?)\s*([kKM]?)\s*(?:ohms?|Ω)?\s*-?\s*([ABCW])?\s*(?:\(.*\))?\s*$")
_POT_WORDS = re.compile(r"^(\d+(?:[.,]\d+)?\s*[kKM]?)\s*(?:Ω|ohms?)?\s*[- ]\s*(linear|lin|log|audio|logarithmic|rev\.?-?\s?log|reverse(?:[- ](?:log|audio))?|anti-?log)\.?\s*(?:pot(?:entiometer)?s?)?$", re.I)
_TAPER_WORD = {"linear": "B", "lin": "B", "log": "A", "audio": "A", "logarithmic": "A", "revlog": "C", "reverse": "C", "reverselog": "C", "reverseaudio": "C", "antilog": "C"}


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
    (re.compile(r"^(POT|P|RV|VR)\d+$", re.I), "POT"),
    (re.compile(r"^(TR|TRIM|T)\d+$", re.I), "TRIM"),
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
    if "TRIM" in r.upper():
        return "TRIM"
    t0 = part_type.lower()
    if re.match(r"^(IC|U)\d+[A-Z]?$", r, re.I):
        return "IC"  # an IC in a socket footprint is still an IC
    if re.match(r"^(RV|VR|POT|P|R)\d+$", r, re.I) and re.search(r"trim", t0):
        return "TRIM"  # KiCad calls both pots and trimmers RVn; the footprint tells them apart
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
    if re.match(r"^(?:REG|VREG|U)\d*$", r, re.I):
        return "IC"  # a voltage regulator
    if re.match(r"^(?:RPD|CLR|LEDR|RLED|RPU)$", r, re.I):
        return "R"  # pull-down and LED resistors named by role
    # Named pots: VOLUME, GAIN, TONE ... (PedalPCB style)
    if r.isalpha() and r.isupper() and len(r) >= 3:
        return "POT"
    for rx, cat in _VALUE_HINTS:  # a shopping-list row ("×2") is known only by its part number
        if rx.match(v):
            return cat
    return "OTHER"


_VALUE_HINTS = [
    (re.compile(r"^(?:2N\d{3,4}|2S[ABCDJK]\d{2,4}|BC\d{3}|BF\d{3}|MPS[AW]?\d{2,3}|MMBT\d{4}|MMBFJ?\d{3,4}|KSP\d{2}|PN\d{4}|J\d{3}\b|BS\d{3}|IRF\d{3}|MPF\d{3}|AC1\d{2}|OC\d{2,3}|NKT\d{3}|TIP\d{2})"), "Q"),
    (re.compile(r"^(?:1N\d{3,4}|UF\d{4}|BAT\d{2}|BA\d{3}|1SS\d{2,3}|OA\d{2,3}|D9[A-Z]|SB\d{3})"), "D"),
    (re.compile(r"^\d+(?:[.,]\d+)?\s*[pnuµμ]\d*F?$", re.I), "C"),
    (re.compile(r"^\d+(?:[.,]\d+)?\s*(?:[kKMR]\d*|[kKM]?\s*(?:ohms?|Ω))$"), "R"),
    (re.compile(r"^(?:TL0[678]\d|LM\d{3,4}|NE55\d|OP\d{2,3}|JRC\d{4}|RC4\d{3}|CD4\d{3}|PT2399|MC1\d{3}|TC1044|LT1054|ICL7660|CA30\d\d|LF35\d|MN30\d{2}|BBD|L78\d\d|78L\d\d|79L\d\d|7[89]\d\d|TDA\d{4}|MAX\d{3,4}|4558|1458|LM13700|SSM\d{4}|V3\d{3})"), "IC"),
]


def normalize_row(row: BomRow) -> BomRow:
    row.category = row.category or categorize(row.ref, row.part_type, row.value)
    if row.category == "POT" and re.search(r"[SD]P[SD]T|3PDT|4PDT", row.value.upper()):
        row.category = "SW"
    raw = row.value.strip().replace("ų", "u").replace("μ", "u").replace("µ", "u")
    raw = re.sub(r"^(\d+(?:[.,]\d+)?)\s+([kKMRpnu])([Ff])?(?=\s|$)", r"\1\2\3", raw)  # '1 K', '2.2 M', '100 uf': a space before the unit
    if row.category in ("D", "Q", "IC", "OPTO"):
        raw = re.sub(r"[*+†‡]+$", "", raw).strip()          # footnote markers: 2N5458**, 1N4148+
        raw = re.sub(r"\s+[A-Z]$", "", raw)                  # stray column bleed: "1N5817 S"
    if row.category in ("R", "C", "L", "TRIM"):
        m = re.match(r"^(\d+(?:[.,]\d+)?\s*[pnuµμmkKMRr]?\d*\s*(?:[Ff]|ohms?|H)?)\s+([A-Za-z(][^\n]*|\d+/\d+\s*W.*)$", raw)
        if m and _parse_si(m.group(1)) is not None:   # "100p Silver Mica" -> value 100p, type "Silver Mica"
            raw = m.group(1).strip()
            row.value = raw
            row.part_type = row.part_type or m.group(2).strip()
    row.norm_value = re.sub(r"\s+", " ", raw).upper()
    row.sort_key = 0.0

    if row.category == "R" or row.category == "TRIM":
        raw = re.sub(r"^(\d+(?:[.,]\d+)?)m$", r"\1M", raw)  # "1m" on a resistor means 1 megohm, never milliohm
        n = _parse_si(raw)
        if n is not None:
            row.norm_value = _fmt(n, _R_PREFIX)
            row.sort_key = n
    elif row.category == "C":
        raw = re.sub(r"(?<=\d)([UNP])(?=\d|F?$)", lambda m: m.group(1).lower(), raw)  # 2U2, 100N: an upper-case unit letter
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
        raw = re.sub(r"(?i)(\d)\s*meg\b", r"\1M", raw)  # C1Meg
        mw = _POT_WORDS.match(raw)
        if mw:  # '500K REV LOG', '10K Lin', '100k-log': the taper as a word
            raw = _TAPER_WORD.get(re.sub(r"[^a-z]", "", mw.group(2).lower()), "") + mw.group(1).replace(" ", "")
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
    if row.category in ("D", "Q", "IC") and (re.fullmatch(r"(?:[RCLDQ]|IC|U|SW|LED|VR|TR)\d{1,3}", row.value.strip().upper())  # L7805 is a regulator, not L7805
                                             or (len(row.value.strip()) < 3 and row.value.strip().upper() not in ("GE", "SI"))):
        return False
    if row.category in ("R", "C", "L") and row.sort_key <= 0:
        return False
    if row.category in ("R", "C") and not re.search(r"\d", row.value):
        return False
    return True
