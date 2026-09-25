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


# --- parts cross-reference keys -------------------------------------------------------------
_CATALOG_WORDS = {
    "GE": "GE", "GERM": "GE", "GERMANIUM": "GE", "GERMANIUM DIODE": "GE", "GERMANIUM DIODES": "GE", "GERMANIUMDIODER": "GE",
    "SI": "SI", "SILICON": "SI", "SILICON DIODE": "SI", "SILICON DIODES": "SI",
    "NPN": "NPN", "PNP": "PNP", "NPN GE": "NPN GE", "GE NPN": "NPN GE", "NPN GERMANIUM": "NPN GE", "GERMANIUM NPN": "NPN GE",
    "PNP GE": "PNP GE", "GE PNP": "PNP GE", "PNP GERMANIUM": "PNP GE", "GERMANIUM PNP": "PNP GE", "NPN SI": "NPN SI", "PNP SI": "PNP SI",
    "NPN SILICON": "NPN SI", "PNP SILICON": "PNP SI", "JFET": "JFET", "FET": "JFET", "N-CHANNEL JFET": "JFET", "MOSFET": "MOSFET",
    "LDR": "LDR", "PHOTOCELL": "LDR", "VACTROL": "VACTROL", "BBD": "BBD", "ZENER": "ZENER", "SCHOTTKY": "SCHOTTKY",
}
_CATALOG_PARTNO = re.compile(r"^(?=.*\d)[A-Z0-9][A-Z0-9.+-]{1,15}$")
_CATALOG_SPLIT = re.compile(r"\s*(?:/|\bOR\b|,|\+)\s*")
_CATALOG_NOISE = re.compile(r"^(?:DIP|SOIC|SOT|TO|SIP|TSSOP)-?\d+|^\d+-POS$|^GEN-IC|^\d+(?:\.\d+)?(?:MM|W|A|X\d+)$|^\d+[KMRUN]\d{0,2}$|^\d+(?:\.\d+)?[KMRUN]$|^[ABCW]\d+K$|^C\d+K$", re.I)
_CATALOG_SHORT = re.compile(r"^([A-Z]{1,2})\d{1,2}[A-Z]?$")
_CATALOG_SHORT_OK = {"OA", "OC", "AC", "AD", "AF", "GT", "MP", "KT", "KP", "D", "BA", "BC", "BF", "BS", "NK", "TI", "ZT", "MJ", "BD", "GC", "GA"}
_CATALOG_FIX = [
    (re.compile(r"^IN(\d{3,4}[A-Z]?)$"), r"1N\1"), (re.compile(r"^[4I]N(\d{4}[A-Z]?)$"), r"1N\1"), (re.compile(r"^INS(\d{4})$"), r"1N\1"),
    (re.compile(r"^TLO(\d\d)"), r"TL0\1"), (re.compile(r"^LMI(\d{3})"), r"LM\1"), (re.compile(r"^JRRC"), "JRC"), (re.compile(r"^NJZ"), "NJM"),
    (re.compile(r"^2[58]([CKA])(\d{2,4})"), r"2S\1\2"), (re.compile(r"^8C(\d{3})"), r"BC\1"), (re.compile(r"^BC5S(\d{2})"), r"BC5\1"), (re.compile(r"^BCS(\d{2})"), r"BC5\1"),
    (re.compile(r"^1N4O0"), "1N400"), (re.compile(r"^TC10445"), "TC1044S"), (re.compile(r"^L78LO"), "L78L0"), (re.compile(r"^MAXX"), "MAX"),
    (re.compile(r"^LWI13700"), "LM13700"), (re.compile(r"^LMIC660"), "LMC660"), (re.compile(r"^(?:AND|I)MN(\d)"), r"MN\1"), (re.compile(r"-+$"), ""),
]


def catalog_category(category: str, key: str) -> str:
    """A part filed under the wrong category by its designator (a TL072 as D3) goes where its
    part number says: the value hints decide for diodes, transistors and ICs."""
    if re.match(r"^(?:VTL|NSL|VACTROL|LDR)", key):
        return "OPTO"
    if re.search(r"\d(?:K|M)?HZ$", key):
        return "XTAL"
    if category in ("D", "Q", "IC"):
        for rx, cat in _VALUE_HINTS:
            if cat in ("D", "Q", "IC") and rx.match(key):
                return cat
    return category


def catalog_keys(category: str, value: str) -> list[str]:
    """The part identities a parts-list value contributes to the cross-reference: part
    numbers (one per alternative in '2N5088 or 2N5089', '7660S/LT1054'), a few generic
    descriptors (Ge, NPN, JFET), canonical pot and switch forms. Prose, colours, 'optional'
    and the like contribute nothing."""
    v = re.sub(r"\s+", " ", value.strip().upper().strip("*"))
    if category in ("D", "Q", "IC", "OPTO", "L", "XTAL"):
        v = re.sub(r"\s*\([^)]*\)?\s*", " ", v).strip()  # "(optional)", "(wired in reverse)", "J201(IDSS>Q1)"
        if v in _CATALOG_WORDS:
            return [_CATALOG_WORDS[v]]
        keys: list[str] = []
        for piece in _CATALOG_SPLIT.split(v):
            piece = piece.strip(" *.")
            if not piece:
                continue
            if piece in _CATALOG_WORDS:
                keys.append(_CATALOG_WORDS[piece])
                continue
            tokens = [t.strip("*.,;") for t in piece.split()]
            partnos = [t for t in tokens if _CATALOG_PARTNO.match(t) and (not t.isdigit() or (category == "IC" and 3 <= len(t) <= 5))
                       and not re.fullmatch(r"\d+(?:MM|V|W|A|HZ|MHZ|KHZ|PIN|X\d+)", t)]
            partnos = [t for t in partnos if not _CATALOG_NOISE.match(t) or (category == "D" and re.fullmatch(r"\d+V\d*|\d+(?:\.\d+)?V", t))]
            partnos = [t for t in partnos if not (_CATALOG_SHORT.match(t) and _CATALOG_SHORT.match(t).group(1) not in _CATALOG_SHORT_OK)]
            if partnos:
                t = partnos[0]
                for rx, rep in _CATALOG_FIX:
                    t = rx.sub(rep, t)
                if t and not re.search(r"\d\.[A-Z]|^[ABOPQSTUX]\d{3}$", t) and not re.fullmatch(r"\dATA|[A-Z]0\d\d", t):
                    keys.append(t)
            elif category == "XTAL" and (m := re.search(r"\d+(?:\.\d+)?\s*[KM]?HZ", piece)):
                keys.append(m.group(0).replace(" ", ""))
        return list(dict.fromkeys(keys))
    if category in ("POT", "TRIM"):
        m = re.search(r"(?<![A-Z0-9])([ABCW])?(\d+(?:\.\d+)?)([KM]?)\s?([ABCW])?(?![A-Z0-9])", v.replace("*", ""))
        if not m or (not m.group(3) and float(m.group(2)) < 100):
            return []  # a bare '1' or '10' is a quantity, not a pot
        taper = m.group(1) or m.group(4) or ""
        return [f"{taper}{m.group(2)}{m.group(3).replace('K', 'k')}"]
    if category == "SW":
        m = re.search(r"\b([1-4SD]P[1-4SD]T)\b", v)
        if not m:
            return []
        base = m.group(1).replace("1P", "SP").replace("2P", "DP")
        centre = bool(re.search(r"OFF|CNTR|CENTER|CENTRE", v))
        return [base + (" ON-OFF-ON" if centre and base in ("SPDT", "DPDT") else "")]
    return [v] if v else []
