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
_POT_DUAL = re.compile(r"\(?\b(?:dual(?:[- ]?gang(?:ed)?)?|stereo|ganged)\b\)?", re.I)
_POT_TWO = re.compile(r"^2\s*[x×]\s*", re.I)
_POT_TRIM = re.compile(r"\b(?:trim(?:mer|pot)?|preset)\b", re.I)


def _pot_parts(value: str) -> tuple[str, bool, bool]:
    """Split a pot value from the words written beside it: 'B100K DUAL' is a B100K dual-gang pot,
    '100K Trim' a trimmer, 'A500K **' a footnoted A500K. Also takes a lower-case or trailing taper
    ('c100K', '25kb', '1m C'). Returns the bare value, whether it is dual, whether it is a trimmer."""
    raw = re.sub(r"[*†‡]+", "", value).strip()
    raw = re.sub(r"\s{3,}\S{1,4}$", "", raw)  # column bleed: '25kB        16'
    dual = bool(_POT_DUAL.search(raw) or _POT_TWO.match(raw))
    trim = bool(_POT_TRIM.search(raw))
    raw = _POT_TWO.sub("", _POT_TRIM.sub(" ", _POT_DUAL.sub(" ", raw)))
    raw = re.sub(r"\s+", " ", raw).strip(" -,")
    raw = re.sub(r"^([abcw])(?=\s*\d)", lambda m: m.group(1).upper(), raw)
    raw = re.sub(r"(?<=\d)\s*m(?=\s*[ABCWabcw]?$)", "M", raw)  # '1m C': a pot is never milliohms
    raw = re.sub(r"(?<=[kKM])\s*([abcw])$", lambda m: m.group(1).upper(), raw)
    return raw, dual, trim


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
    (re.compile(r"^(LDR|OPTO|VTL|OC|OK)\d*$", re.I), "OPTO"),  # OK: Optokoppler
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
    if re.search(r"\b[SD]P[SD]T\b|3PDT|4PDT|\b[SD]P3T\b", v) or re.fullmatch(r"ON[-/ ]?(?:OFF[-/ ]?)?ON", v.strip()) or re.fullmatch(r"[SD]P[SD]T|[34]PDT", r.upper()):
        return "SW"  # 'DP3T ON-ON-ON', a switch named 'SPDT' whose value is 'On-off-on'
    if ("LED" in v or "LYSDIOD" in v) and not re.match(r"^(IC|U|Q)\d", r):  # Lysdiod: Swedish for LED (Moody)
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
    if re.match(r"^(?:XFM|XFMR|TRANS|TX)\d*$", r, re.I) or (re.match(r"^(?:T|TR)\d+$", r, re.I) and _XFM_HINT.match(v)) or _XFM_HINT.match(v):
        return "XFM"  # audio transformers: 42TM022, TY-141P, LT44, OEP1200 (European docs number them T1, TR1)
    if re.match(r"^T\d+$", r, re.I) and (_Q_HINT.match(v) or re.search(r"TRANSISTOR|\b[NP]PN\b|JFET|MOSFET", v)):
        return "Q"  # European docs number transistors T1, T2 (Carlin, BJF); a trimmer never carries a BC547B
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
    # Named pots: VOLUME, GAIN, TONE ... (PedalPCB style), but only with a pot value: in a hardware
    # table 'CUI  PQMC3-D1' is a DC jack and 'BRAND  PART #' a header, not knobs.
    if r.isalpha() and r.isupper() and len(r) >= 3 and (not v.strip() or re.match(r"^\s*(?:(?:DUAL|STEREO)(?:[- ]GANG(?:ED)?)?\s+)?[ABCWLG]?\s?\d", v) or re.search(r"\bPOT|LIN|LOG", v)):
        return "POT"
    for rx, cat in _VALUE_HINTS:  # a shopping-list row ("×2") is known only by its part number
        if rx.match(v):
            return cat
    return "OTHER"


_VALUE_HINTS = [
    (re.compile(r"^(?:VTL\d|NSL-?\d{2,}|VT\d{3}|[46]N\d{2,3}\b|H11[A-Z]\d|PC8\d\d|TLP\d{3})", re.I), "OPTO"),  # vactrols, LDR and IC optocouplers (6N138 is not 6n)
    (re.compile(r"^(?:2N\d{3,4}|2S[ABCDJK]\d{2,4}|BC\d{3}|BF\d{3}|MPS[AW]?\d{2,3}|MMBT\d{4}|MMBFJ?\d{3,4}|KSP\d{2}|PN\d{4}|J\d{3}\b|BS\d{3}|IRF\d{3}|MPF\d{3}|AC1\d{2}|OC\d{2,3}|NKT\d{3}|TIP\d{2})"), "Q"),
    (re.compile(r"^(?:1N\d{3,4}|UF\d{4}|BAT\d{2}|BA\d{3}|1SS\d{2,3}|OA\d{2,3}|D9[A-Z]|SB\d{3})"), "D"),
    (re.compile(r"^\d+(?:[.,]\d+)?\s*[pnuµμ]\d*F?$", re.I), "C"),
    (re.compile(r"^\d+(?:[.,]\d+)?\s*(?:[kKMR]\d*|[kKM]?\s*(?:ohms?|Ω))$"), "R"),
    (re.compile(r"^(?:TL0[678]\d|LM\d{3,4}|NE55\d|OP\d{2,3}|JRC\d{4}|RC4\d{3}|CD4\d{3}|PT2399|MC1\d{3}|TC1044|LT1054|ICL7660|CA30\d\d|LF35\d|MN30\d{2}|BBD|L78\d\d|78L\d\d|79L\d\d|7[89]\d\d|TDA\d{4}|MAX\d{3,4}|4558|1458|LM13700|SSM\d{4}|V3\d{3})"), "IC"),
]
_Q_HINT = next(rx for rx, cat in _VALUE_HINTS if cat == "Q")
_XFM_HINT = re.compile(r"^(?:42T[ML]\d{3}|TM0\d\d|TY-?\d{3}|LT-?4\d\b|OEP\d|LM-NP|\S*\s*(?:audio )?transformer)", re.I)


_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
_E24_3 = {v * 10 for v in (10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91)}


def _resistor_code(raw: str) -> str:
    """'1002' in a resistor column is the 4-digit code (100 x 10^2 = 10k), not 1,002 ohms. Decoded only
    when the plain number is not a standard value and the code's three digits are (4700 stays 4700)."""
    m = re.fullmatch(r"([1-9]\d\d)([1-4])", raw)
    if not m or int(m.group(1)) not in _E24_3:
        return raw
    ohms = int(m.group(1)) * 10 ** int(m.group(2))
    for unit, div in (("M", 1_000_000), ("k", 1000)):
        if ohms >= div:
            n = ohms / div
            return f"{n:g}".replace(".", unit) if n != int(n) else f"{int(n)}{unit}"  # 2k2, 10k
    return str(ohms)


_ZENER_V = re.compile(r"^(?:ZENN?ER|ZEN)?[\s.:-]*(\d{1,2})(?:[.,](\d)\s*V?|V(\d)?)?[\s.-]*(?:ZENN?ER|ZEN)?(?:\s+DIODE)?$", re.I)  # 'Zenner' too


def zener_voltage(value: str) -> str:
    """A zener given by its voltage, in the standard form: '9.1V', '9v1', '9.1V Zener', 'ZENER 9V1' -> '9V1';
    '15v Zener', 'ZENER12V' -> '15V', '12V'. '' for anything else: a part number (1N4739, BZX79C9V1) or a
    bare number with no V, decimal or 'zener' to say it is a voltage."""
    v = value.strip()
    m = _ZENER_V.match(v)
    if not m or not (re.search(r"[Vv]|zen", v, re.I) or m.group(2)):
        return ""
    volts, dec = m.group(1), m.group(2) or m.group(3)
    return f"{int(volts)}V{dec}" if dec and dec != "0" else f"{int(volts)}V"


# Zener part numbers -> nominal voltage, for the series pedal boards use. The part number stays the
# part; the voltage is a second cross-reference key, so a 1N4739 also counts as a 9V1 zener.
_ZENER_SERIES: dict[str, float] = {
    **dict(zip(range(4728, 4765), [3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10, 11, 12, 13, 15, 16, 18,
                                   20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91, 100])),    # 1N4728-1N4764, 1 W
    **dict(zip(range(5221, 5258), [2.4, 2.5, 2.7, 2.8, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.0, 6.2, 6.8, 7.5, 8.2, 8.7, 9.1,
                                   10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 27, 28, 30, 33])),     # 1N5221-1N5257, 500 mW
    **dict(zip(range(746, 760), [3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10, 12])),           # 1N746-1N759
}


_E24_ZENER = [2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10, 11, 12, 13, 15, 16, 18, 20, 22,
               24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75]
# Zener series a builder can buy for a voltage-only part: (series, how its parts are numbered, power, package,
# lowest voltage, the maker's series datasheet). Through-hole first, most common first.
_ZENER_CHOICES = [
    ("1N52xxB", "1N5221", "500 mW", "DO-35", "https://www.vishay.com/docs/85588/1n5221.pdf"),
    ("BZX55", "BZX55C", "500 mW", "DO-35", "https://www.vishay.com/docs/85604/bzx55.pdf"),
    ("BZX79", "BZX79C", "500 mW", "DO-35", "https://assets.nexperia.com/documents/data-sheet/BZX79_SER.pdf"),
    ("1N7xxA", "1N746", "500 mW", "DO-35", "https://my.centralsemi.com/datasheets/1N746A-759A.PDF"),
    ("1N47xxA", "1N4728", "1 W", "DO-41", "https://www.vishay.com/docs/85816/1n4728a.pdf"),
    ("BZX85", "BZX85C", "1.3 W", "DO-41", "https://www.vishay.com/docs/85607/bzx85.pdf"),
]
_BZX_LOW = {"BZX55C": 2.4, "BZX79C": 2.4, "BZX85C": 3.3}


def zener_choices(voltage: str) -> list[dict]:
    """Stock zeners for a part given only by its voltage ('9V1' -> 1N5239B, BZX55C9V1, BZX79C9V1, 1N757A,
    1N4739A, BZX85C9V1), each with its series, power, package and the maker's series datasheet."""
    m = re.fullmatch(r"(\d{1,2})V(\d)?", voltage)
    if not m:
        return []
    v = int(m.group(1)) + int(m.group(2) or 0) / 10
    out = []
    for series, prefix, power, pkg, sheet in _ZENER_CHOICES:
        if prefix.startswith("BZX"):
            if v not in _E24_ZENER or v < _BZX_LOW[prefix]:
                continue
            pn = prefix + (f"{int(v)}V{round(v % 1 * 10)}" if v % 1 or v < 10 else f"{int(v)}")
        else:
            start = int(prefix[2:])
            num = next((n for n, z in _ZENER_SERIES.items() if z == v and start <= n < start + 40), None)
            if num is None:
                continue
            pn = f"1N{num}" + ("B" if series == "1N52xxB" else "A")
        out.append({"pn": pn, "series": series, "power": power, "package": pkg, "datasheet": sheet})
    return out


def zener_of_part(part: str) -> str:
    """The voltage of a zener part number, in the standard form ('1N4739A' -> '9V1', 'BZX79C9V1' -> '9V1',
    'BZX55C12' -> '12V'), or '' for anything that is not one."""
    p = re.sub(r"[^A-Z0-9]", "", part.upper())
    m = re.fullmatch(r"1N(\d{3,4})[A-D]?", p)
    if m and int(m.group(1)) in _ZENER_SERIES:
        v = _ZENER_SERIES[int(m.group(1))]
        return f"{int(v)}V{round(v % 1 * 10)}" if v % 1 else f"{int(v)}V"
    m = re.fullmatch(r"BZ[XVYT]\d{2}[A-Z]?C?(\d{1,2})V?(\d)?", p)
    if m:
        return f"{int(m.group(1))}V{m.group(2)}" if m.group(2) and m.group(2) != "0" else f"{int(m.group(1))}V"
    return ""


def normalize_row(row: BomRow) -> BomRow:
    row.value = _ZERO_WIDTH.sub("", row.value)  # '\u200bTC1044SCPA' from a copied web page
    row.ref = _ZERO_WIDTH.sub("", row.ref)
    row.category = row.category or categorize(row.ref, row.part_type, row.value)
    if row.category == "POT" and re.search(r"[SD]P[SD]T|3PDT|4PDT", row.value.upper()):
        row.category = "SW"
    if row.category in ("POT", "TRIM"):
        bare, dual, trim = _pot_parts(row.value)
        if bare != row.value.strip() and (_POT_RE.match(bare) or _POT_WORDS.match(bare)):
            if trim and row.category == "POT":
                row.category = "TRIM"
                row.part_type = row.part_type or "Trimmer"
            if dual and "dual" not in row.part_type.lower():
                row.part_type = f"{row.part_type}, dual" if row.part_type else "Dual"
            row.value = bare
    raw = row.value.strip().replace("ų", "u").replace("μ", "u").replace("µ", "u")
    raw = re.sub(r"^(\d+(?:[.,]\d+)?)\s+([kKMRpnu])([Ff])?(?=\s|$)", r"\1\2\3", raw)  # '1 K', '2.2 M', '100 uf': a space before the unit
    if row.category in ("R", "C", "L", "TRIM", "POT"):
        raw = re.sub(r"^\.(?=\d)", "0.", raw)                # '.01uF', '.047' as old schematics write them
    if row.category in ("R", "TRIM", "POT"):
        raw = re.sub(r"(?i)(?<=\d)\s*meg(?:ohms?)?$", "M", raw)  # '1meg', '5Meg'
        raw = re.sub(r"^(\d+)E(\d*)$", r"\1R\2", raw)           # '220E', '4E7': E for ohms, as European drawings write it
        raw = re.sub(r"^([ABCW]?)(\d+)([kKM])(\d+)$", r"\1\2.\4\3", raw)  # 'A4k7', 'B2K2' (a resistor's 4k7 reads already)
    if row.category == "C" and (m := re.fullmatch(r"([1-9]\d)([1-6])", raw)):
        raw = f"{int(m.group(1)) * 10 ** int(m.group(2))}p"  # the printed code: '104' is 10 x 10^4 pF (100n); '470' stays 470pF
    if row.category == "Q" and re.match(r"^2[58][ABCDJK]\d{2,4}", row.value.strip()):
        row.value = "2S" + row.value.strip()[2:]  # OCR reads 2S as 25 or 28: 25K30A-Y is 2SK30A-Y (no part number starts 25K)
        raw = row.value
    if row.category in ("D", "Q", "IC"):
        fixed = _repair_part_number(row.category, row.value.strip())
        if fixed != row.value.strip():
            row.value = raw = fixed
    if row.category in ("D", "Q", "IC", "OPTO"):
        raw = re.sub(r"[*+†‡]+$", "", raw).strip()          # footnote markers: 2N5458**, 1N4148+
        raw = re.sub(r"\s+[A-Z]$", "", raw)                  # stray column bleed: "1N5817 S"
        raw = re.sub(r"(?i)^MPS-?A-?(\d)", r"MPSA\1", raw)    # 'MPS-A18', 'MPSA-13' as old drawings hyphenate them
    if row.category in ("R", "C", "L", "TRIM"):
        m = re.match(r"^(\d+(?:[.,]\d+)?\s*[pnuµμmkKMRr]?\d*\s*(?:[Ff]|ohms?|H)?)\s+([A-Za-z(][^\n]*|\d+/\d+\s*W.*)$", raw)
        if m and _parse_si(m.group(1)) is not None:   # "100p Silver Mica" -> value 100p, type "Silver Mica"
            raw = m.group(1).strip()
            row.value = raw
            row.part_type = row.part_type or m.group(2).strip()
    row.norm_value = re.sub(r"\s+", " ", raw).upper()
    if row.category == "D" and (z := zener_voltage(raw)):
        row.norm_value = z                                   # '9.1V Zener', '9v1', 'ZENER9V1' are all 9V1
    row.sort_key = 0.0

    if row.category == "R" or row.category == "TRIM":
        raw = re.sub(r"^(\d+(?:[.,]\d+)?)m$", r"\1M", raw)  # "1m" on a resistor means 1 megohm, never milliohm
        raw = re.sub(r"^(\d+)m(\d+)$", r"\1M\2", raw)  # and "2m2" is 2.2 megohms
        if row.category == "TRIM":
            raw = re.sub(r"^[ABCW](?=\d)|(?<=[kKM])[ABCW]$", "", raw)  # 'B150K', '10KB': a trimmer's taper letter
        if row.category == "R":
            coded = _resistor_code(raw)
            if coded != raw:
                row.value = raw = coded
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


# OCR and typing slips in well-known part families, each unambiguous: no real part is spelled the
# slipped way. (category, pattern, replacement)
_PART_SLIPS = [
    ("Q", re.compile(r"^ZN(\d{4}[A-Z]?)$"), r"2N\1"),                  # ZN3904: a 2 read as Z
    ("IC", re.compile(r"^TL[QDO](\d\d[A-Z]?)$", re.I), r"TL0\1"),      # TLQ72, TLD82, TLO72
    ("IC", re.compile(r"^CO4(\d{3}[A-Z]*)$", re.I), r"CD4\1"),          # CO4047
    ("IC", re.compile(r"^(?:[XL]M|LM9)324([A-Z]*)$", re.I), r"LM324\1"), # XM324, LM9324
    ("IC", re.compile(r"^RC[Y4]558([A-Z]*)$", re.I), r"RC4558\1"),       # RCY558
    ("IC", re.compile(r"^WA741([A-Z]*)$", re.I), r"uA741\1"),            # WA741 (uA741 is already right)
    ("IC", re.compile(r"^PT239[59]$", re.I), "PT2399"),                   # pt2395
    ("D", re.compile(r"^1(4[01]\d\d|4148|581[789]|914)$"), r"1N\1"),       # 14001: the N dropped
    ("D", re.compile(r"^1M(\d{2,4}[A-Z]?)$", re.I), r"1N\1"),              # 1M34A: an N read as M (no diode is 1M...)
    ("D", re.compile(r"^BAT[- ](\d\d[A-Z]?)\b", re.I), r"BAT\1"),        # BAT-41, BAT 41
]


def _repair_part_number(category: str, value: str) -> str:
    for cat, rx, rep in _PART_SLIPS:
        if cat == category and rx.search(value):
            return rx.sub(rep, value, count=1)
    return value


# Words a semiconductor row may carry without a part number ('Germanium', 'NPN JFET', 'Dual op amp').
# Any other digit-free value is prose or a placeholder picked up as a part: 'for', 'are', 'Clipping',
# 'empty or your choice', 'Jumper*', '(optional'.
_PART_WORDS = {"ge", "si", "germanium", "germ", "silicon", "schottky", "led", "leds", "zener", "npn", "pnp", "jfet", "fet",
               "mosfet", "bjt", "bjet", "transistor", "transistors", "diode", "diodes", "red", "green", "blue", "yellow", "white",
               "amber", "orange", "clear", "diffused", "bicolor", "bi-color", "bicolour", "rgb", "status", "ldr", "vactrol", "opamp",
               "op", "amp", "op-amp", "opamps", "dual", "quad", "single", "bbd", "pic", "microcontroller", "regulator", "charge", "pump",
               "low", "gain", "high", "medium", "noise", "matched", "pair", "n-channel", "p-channel", "channel", "small", "signal",
               "general", "purpose", "rectifier", "lysdiod", "germaniumdioder", "germaniumdiod", "photocell", "optocoupler", "flat", "top",
               "photo", "pinout", "ebc", "ecb", "cbe", "bce", "bec", "ceb", "spin"}


def is_prose_value(category: str, value: str) -> bool:
    """A diode, transistor or IC row whose value is a word or placeholder, not a part."""
    if category not in ("D", "Q", "IC", "OPTO"):
        return False
    v = value.strip(" *†‡()[].,:;-")
    if not v or re.search(r"\d", v):
        return False
    words = re.findall(r"[a-z]+", v.lower())  # 'low-gain' is two words
    return bool(words) and any(w not in _PART_WORDS for w in words)


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


_IC_ONLY = re.compile(r"^(?:BA6\d{3}|BA7\d\d\b|HD14\d{3}|L78L\d\d|NJM\d{4})")


def catalog_category(category: str, key: str) -> str:
    """A part filed under the wrong category by its designator (a TL072 as D3) goes where its
    part number says: the value hints decide for diodes, transistors and ICs."""
    if re.match(r"^(?:VTL|NSL|VACTROL|LDR)", key):
        return "OPTO"
    if re.search(r"\d(?:K|M)?HZ$", key):
        return "XTAL"
    if category in ("D", "Q", "IC") and _IC_ONLY.match(key):
        return "IC"  # ROHM's BA6110 VCA and BA718 op amp are no BA-series diodes; Hitachi's HD14011 is a CD4011
    if category in ("D", "Q", "IC"):
        for rx, cat in _VALUE_HINTS:
            if cat in ("D", "Q", "IC") and rx.match(key):
                return cat
    return category


# IC families written under many names: (second-source prefixes, number, canonical name). The prefix
# list is per family so a different chip that shares the number stays apart (LM4040 is a voltage
# reference, CD4040 a counter; TLC555 is the CMOS 555); any package or grade suffix after the number
# (CP, N, D, SCPA, N-1, BE) is the same chip.
_IC_FAMILIES: list[tuple[str, str, str]] = [
    ("TL|JRC|NJM|KIA", "0([2-8][1-4])", "TL0{0}"),
    ("J?RC|NJM|LM|KA|MC|HA", "4558", "4558"), ("J?RC|NJM", "4559", "4559"), ("J?RC|NJM", "4580", "4580"),
    ("LM|MC|JRC|NJM|LH|CA|RC|KA", "1458", "1458"), ("LM|UA|CA|JRC|NJM|MC|KA", "741", "741"),
    ("LM|JRC|NJM", "386", "LM386"), ("LM|NJM", "833", "LM833"), ("NE|SA|LM", "5532", "NE5532"),
    ("NE|SA|JRC|NJM", "5534", "NE5534"), ("LM|JRC|NJM|V", "13700", "LM13700"), ("LM|JRC|NJM", "13600", "LM13600"),
    ("OPA?", "2134", "OPA2134"), ("OPA?", "1678", "OPA1678"), ("OPA", "2604", "OPA2604"), ("OPA", "134", "OPA134"),
    ("LM|JRC|NJM|KA", "358", "LM358"), ("LM|KA", "324", "LM324"), ("LM", "308", "LM308"), ("CA|LM", "3080", "CA3080"),
    ("MN|V|BL", "3102", "MN3102"), ("MN|V|BL", "3207", "MN3207"), ("MN|V|BL", "3205", "MN3205"), ("MN|V|BL", "3007", "MN3007"),
    ("LF|LM", "353", "LF353"), ("LF", "347", "LF347"), ("LF", "351", "LF351"), ("LF", "412", "LF412"),
    ("LM", "311", "LM311"), ("LM", "301", "LM301A"), ("CA", "3130", "CA3130"), ("CA", "3260", "CA3260"),
    ("XR", "2206", "XR2206"), ("RC|NJM|MC|LM", "3403", "3403"), ("NE|SA|V", "571", "NE571"), ("TLC", "2262", "TLC2262"),
    ("LM|JRC|NJM", "4562", "LM4562"), ("M", "5218", "M5218"), ("M", "5216", "M5216"), ("NJM|LM", "2904", "2904"),
    ("UPC|C", "4570", "UPC4570"), ("MC", "33179", "MC33179"), ("LM", "339", "LM339"), ("THAT", "2181", "THAT2181"),
    ("TDA", "7052", "TDA7052"), ("TLC", "272", "TLC272"), ("PT-?", "2399", "PT2399"), ("LT", "1054", "LT1054"),
    ("TC|MAX|LTC|ICL", "1044", "TC1044"), ("NE|LM|SA|UA", "555", "NE555"), ("NE|LM|SA", "556", "NE556"),
    ("L|LM|UA|MC|KA", "78(0[5-9]|1[0-5])", "78{0}"), ("L|LM|UA|MC|KA", "79(0[5-9]|1[0-5])", "79{0}"),
]
# The suffix starts with a letter: 'LM3080' is not the LM308 with a 0 after it.
_IC_FAMILY_RE = [(re.compile(rf"^(?:{pre})?{num}(?:[A-Z]{{1,6}}\d?)?(?:-[A-Z0-9]{{1,4}})?$"), name) for pre, num, name in _IC_FAMILIES]


def ic_name(part: str) -> str:
    """The canonical name of an IC part number: 072 and TL072CP are the TL072, JRC4558D and RC4558P the
    4558. 7660 and 7660S stay apart (the S takes a higher supply), as does a CD4000 chip's UB."""
    t = part.upper().replace(" ", "")
    m = re.fullmatch(r"(?:ICL|TC|TL|MAX|LTC|SI)?7660(S?)[A-Z]*\d?", t)
    if m:
        return "7660" + m.group(1)
    for rx, name in _IC_FAMILY_RE:  # op-amps first: 4558, 4559 and 4580 are not CMOS logic
        m = rx.match(t)
        if m:
            return name.format(*m.groups())
    # CMOS logic: a bare number only from the 4000s (4013, 40106); the 4500s need their CD/HEF prefix.
    m = re.fullmatch(r"(?:(CD|HEF|MC1)?(4[05]\d{2,3}))(UB)?(?:[A-Z]{1,4}\d{0,2})?(?:\.\d)?", t)
    if m and (m.group(2).startswith("40") or m.group(1)) and len(m.group(2)) in (4, 5):
        return f"CD{m.group(2)}" + ("UB" if m.group(2) in ("4049", "4069", "4007") or m.group(3) else "")
    return part


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
                       and not (re.fullmatch(r"\d+(?:MM|V|W|A|HZ|MHZ|KHZ|PIN|X\d+)", t)
                                and not (category == "D" and re.fullmatch(r"\d{1,2}V", t)))]  # a 12V zener
            partnos = [t for t in partnos if not _CATALOG_NOISE.match(t) or (category == "D" and re.fullmatch(r"\d+V\d*|\d+(?:\.\d+)?V", t))]
            partnos = [t for t in partnos if not (_CATALOG_SHORT.match(t) and _CATALOG_SHORT.match(t).group(1) not in _CATALOG_SHORT_OK)]
            if partnos:
                t = partnos[0]
                for rx, rep in _CATALOG_FIX:
                    t = rx.sub(rep, t)
                if t and not re.search(r"\d\.[A-Z]|^[ABOPQSTUX]\d{3}$", t) and not re.fullmatch(r"\dATA|[A-Z]0\d\d", t):
                    keys.append(ic_name(t) if category == "IC" else t)
            elif category == "XTAL" and (m := re.search(r"\d+(?:\.\d+)?\s*[KM]?HZ", piece)):
                keys.append(m.group(0).replace(" ", ""))
        if category == "D":
            keys += [z for k in keys if (z := zener_of_part(k))]  # a 1N4739 is also a 9V1 zener
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
