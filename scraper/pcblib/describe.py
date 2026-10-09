"""Short descriptions for the parts index, one scheme per category: 'Dual JFET-Input Op-Amp DIP-8 /
SOIC-8', '100 kΩ Log (A) Potentiometer', '50 kΩ Trimmer 3362P', 'SPDT On-Off-On Toggle', 'Vactrol (LED +
LDR)', '500 mH Inductor', 'Audio Transformer 10 kΩ CT : 600 Ω CT', '32.768 kHz Crystal'. Transistors and
diodes have their own (transistors.describe, diodes.describe). What a part is comes from its number or
value; a detail that is not certain (a package, a taper) is left out rather than guessed."""
from __future__ import annotations

import re

from .normalize import _parse_si

# --- ICs ----------------------------------------------------------------------------------------------
# (pattern on the number with any maker prefix removed, description, packages: through-hole first, then
# surface mount). A number carries its package in the maker's suffix (TL072CP is DIP, TL072CD SOIC); with
# no suffix both are listed.
_D8, _D14, _D16 = ("DIP-8", "SOIC-8"), ("DIP-14", "SOIC-14"), ("DIP-16", "SOIC-16")
_OPAMP = [  # (number pattern, channels, input type)
    (r"TL0[5-8]1", "Single", "JFET"), (r"TL0[5-8]2", "Dual", "JFET"), (r"TL0[5-8]4", "Quad", "JFET"),
    (r"LF35[16]", "Single", "JFET"), (r"LF353|LF412", "Dual", "JFET"), (r"LF347", "Quad", "JFET"),
    (r"OPA2134|OPA2604|AD712|OPA2132", "Dual", "JFET"), (r"OPA134|OPA604", "Single", "JFET"), (r"TLE207[14]", "Quad", "JFET"),
    (r"4558|4559|4580|1458|LM833|NE5532|MC3317[28]|M5218|UPC4570|4570|LM4562|LM358|LM258|2904|TL022|747", "Dual", "BJT"),
    (r"741|748|NE5534|LM301A?|LM308", "Single", "BJT"), (r"LM324|3403|4136|HA1457", "Quad", "BJT"),
    (r"OP275", "Dual", "JFET/BJT"),
    (r"TLC22[67]2|TLC272", "Dual", "CMOS"), (r"TLC27M4|LMC660", "Quad", "CMOS"),
    (r"CA3130|CA3140", "Single", "MOSFET"), (r"CA3240|CA3260", "Dual", "MOSFET"),
]
_IC: list[tuple[str, str, tuple[str, ...]]] = [
    (r"LM13700|LM13600", "Dual OTA", _D16), (r"CA3080", "OTA", _D8), (r"CA3094", "OTA with Power Output", _D8),
    (r"BA6110", "Voltage-Controlled Amplifier", ("SIP-9",)),
    (r"TC1044S?|ICL7660|7660S?|LTC1044|MAX1044|LTC1144", "Charge Pump Voltage Converter", _D8),
    (r"LT1054", "Charge Pump Voltage Converter", ("DIP-8", "SOIC-16")),
    (r"PT2399", "Echo Processor", ("DIP-16", "SOP-16")), (r"FV-?1", "Reverb and Multi-Effects DSP", ("SOIC-28",)),
    (r"MN3207|MN3007|BL3207|V3207", "1024-Stage BBD", ("DIP-8",)), (r"MN3208|MN3008|BL3208|V3208", "2048-Stage BBD", ("DIP-8",)),
    (r"MN3005|MN3205|V3205", "4096-Stage BBD", ("DIP-8",)), (r"MN3002", "512-Stage BBD", ("DIP-8",)),
    (r"SAD1024", "Dual 512-Stage BBD", ("DIP-16",)), (r"SAD512", "512-Stage BBD", ("DIP-8",)),
    (r"MN310[12]|BL310[12]|V3102|CT3101", "BBD Clock Driver", ("DIP-8",)),
    (r"NE57[01]|SA571", "Compandor", _D16), (r"LM386", "Audio Power Amplifier", _D8),
    (r"NE555|LM555", "Timer", _D8), (r"ICM7555|TLC555", "CMOS Timer", _D8), (r"NE556", "Dual Timer", _D14),
    (r"(?:LM)?311", "Comparator", _D8), (r"(?:LM)?393", "Dual Comparator", _D8), (r"(?:LM)?339", "Quad Comparator", _D14),
    (r"LM319", "Dual High-Speed Comparator", _D14), (r"LM3900", "Quad Norton Amplifier", _D14),
    (r"XR2206", "Function Generator", _D16), (r"I?C?L?8038", "Waveform Generator", ("DIP-14",)),
    (r"CA3046|LM3046", "NPN Transistor Array", _D14), (r"CA3019", "Diode Array", ("DIP-14",)), (r"27C?64", "64 Kbit EPROM", ("DIP-28",)), (r"AD633", "Analog Multiplier", _D8),
    (r"LM1496|MC1496", "Balanced Modulator", _D14), (r"LM567", "Tone Decoder", _D8),
    (r"LM3914", "Bar/Dot Display Driver", ("DIP-18",)), (r"CEM3340", "VCO", ("DIP-16",)),
    (r"24LC32A?", "32 Kbit I2C EEPROM", _D8), (r"ATTINY85", "8-bit Microcontroller", _D8),
    (r"PIC12F675", "8-bit Microcontroller", _D8), (r"TLP222[AG]?", "Photo-MOSFET Relay", ("DIP-4",)),
    (r"BTDR-?[23]H?", "Digital Reverb Module", ()), (r"723", "Adjustable Voltage Regulator", _D14),
]
_CMOS = {  # CD4000 logic: number -> function and pin count
    "4001": ("Quad 2-Input NOR", 14), "4007": ("Dual Complementary Pair and Inverter", 14), "4009": ("Hex Inverting Buffer", 16),
    "4011": ("Quad 2-Input NAND", 14), "4013": ("Dual D Flip-Flop", 14), "4015": ("Dual 4-Stage Shift Register", 16),
    "4016": ("Quad Bilateral Switch", 14), "4017": ("Decade Counter", 16), "4022": ("Octal Counter", 16),
    "4024": ("7-Stage Binary Counter", 14), "4027": ("Dual JK Flip-Flop", 16), "4040": ("12-Stage Binary Counter", 16),
    "4046": ("Phase-Locked Loop", 16), "4047": ("Monostable/Astable Multivibrator", 14), "4049": ("Hex Inverting Buffer", 16),
    "4050": ("Hex Buffer", 16), "4051": ("8-Channel Analog Multiplexer", 16), "4052": ("Dual 4-Channel Analog Multiplexer", 16),
    "4053": ("Triple 2-Channel Analog Multiplexer", 16), "4060": ("14-Stage Counter and Oscillator", 16),
    "4066": ("Quad Bilateral Switch", 14), "4069": ("Hex Inverter", 14), "4070": ("Quad XOR", 14),
    "4093": ("Quad 2-Input NAND Schmitt Trigger", 14), "40106": ("Hex Schmitt Trigger Inverter", 14),
}
_TTL = {  # 74-series logic: number -> function and pin count
    "00": ("Quad 2-Input NAND", 14), "04": ("Hex Inverter", 14), "U04": ("Unbuffered Hex Inverter", 14), "08": ("Quad 2-Input AND", 14),
    "14": ("Hex Schmitt Trigger Inverter", 14), "32": ("Quad 2-Input OR", 14), "74": ("Dual D Flip-Flop", 14),
    "157": ("Quad 2-Input Multiplexer", 16), "174": ("Hex D Flip-Flop", 16), "195": ("4-Bit Shift Register", 16),
    "374": ("Octal D Flip-Flop", 20), "4040": ("12-Stage Binary Counter", 16),
}
_DIP_SUFFIX = re.compile(r"(?:C?P|C?N|AP|ACN|IN|PN|PU|PA|E|EZ|BP|CPD|CCPD|N8|CN8)(?:-\d+)?$")
_SO_SUFFIX = re.compile(r"(?:C?D|DR|M|MX|DT|SO|S8|CSO|SW)$")


def _packages(rest: str, pkgs: tuple[str, ...], jrc: bool) -> str:
    """The package a maker's suffix names, else every package the part comes in."""
    if not pkgs:
        return ""
    if len(pkgs) > 1 and rest:
        if jrc and re.fullmatch(r"D|DD", rest):
            return pkgs[0]  # JRC: NJM4558D is the DIP, NJM4558M the SOIC
        if _DIP_SUFFIX.search(rest):
            return pkgs[0]
        if _SO_SUFFIX.search(rest):
            return pkgs[1]
    return " / ".join(pkgs)


def _regulator(p: str) -> str:
    m = re.fullmatch(r"(?:L|LM|UA|MC|KA)?(7[89])(L?)(\d\d)(?:[A-Z]{0,3}\d?)?(?:-[\d.]+)?", p)
    if not m or not (2 <= int(m.group(3)) <= 24 or m.group(3) == "33"):
        m2 = re.fullmatch(r"(?:LM)?340K?-?(\d\d)", p)
        return f"{int(m2.group(1))} V 1.5 A Positive Regulator TO-3" if m2 and "K" in p else ""
    v, low = int(m.group(3)), bool(m.group(2))
    v_txt = "3.3 V" if v == 33 else f"{v} V"
    sign = "Positive" if m.group(1) == "78" else "Negative"
    pkg = "TO-92 / SOT-89" if low else "TO-220"
    if low and p.rstrip("A").endswith("Z"):
        pkg = "TO-92"
    return f"{v_txt} {'100 mA' if low else '1 A'} {sign} Regulator {pkg}"


def describe_ic(value: str) -> str:
    v = re.sub(r"\s+", "", value.upper())
    v = re.sub(r"^(?:TL)-(?=\d)", "TL", v)  # 'TL-082'
    if r := _regulator(v):
        return r
    jrc = v.startswith(("JRC", "NJM"))
    p = re.sub(r"^(?:JRC|NJM|KIA|KA|HA|UPC|UA|MC|LM|NE|SA|RC|CA|AD|IC|TC|ICL|LT|LTC)(?=\d)", "", v)  # maker prefixes on bare numbers
    p = re.sub(r"^HD14(\d{3})|^MC14(\d{3})|^14(0\d\d)(?=[A-Z]|$)", lambda m: "CD4" + (m.group(1) or m.group(2) or m.group(3)), p)
    for num, ch, inp in _OPAMP:
        for cand in (v, p):
            m = re.match(rf"(?:[A-Z]{{0,4}})?({num})(.*)$", cand)
            if m and (m.start(1) == 0 or cand[:m.start(1)].isalpha()):
                pkgs = _D14 if ch == "Quad" or num == "747" else _D8
                return f"{ch} {inp}-Input Op-Amp {_packages(m.group(2), pkgs, jrc)}".strip()
    m = re.fullmatch(r"(?:CD|HEF|MC1)?(4[05]\d{2,3})(UB|B|BE|BCN|BM|BF|BP)?(.*)", p)
    if m and m.group(1) in {k for k in _CMOS} | {"4069", "4049"}:
        fn, pins = _CMOS[m.group(1)]
        unb = "Unbuffered " if m.group(2) == "UB" and m.group(1) == "4069" else ""
        return f"CMOS {unb}{fn} {_packages(m.group(3) or (m.group(2) or '')[1:], (f'DIP-{pins}', f'SOIC-{pins}'), False)}"
    m = re.fullmatch(r"(?:SN|MM|DM)?74(LS|HC|HCT|AC|ACT|C|F|ALS|LV)?(U?\d{2,4})(.*)", v)
    if m and m.group(2) in _TTL:
        fn, pins = _TTL[m.group(2)]
        fam = f"74{m.group(1)} " if m.group(1) else "74 "
        return f"{fam}{fn} {_packages(m.group(3), (f'DIP-{pins}', f'SOIC-{pins}'), False)}"
    for num, fn, pkgs in _IC:  # noqa: B007
        for cand in (v, p):
            m = re.fullmatch(rf"(?:[A-Z]{{0,4}})?({num})([A-Z0-9-]*)", cand)
            if m:
                return f"{fn} {_packages(m.group(2), pkgs, jrc)}".strip()
    return ""


# --- pots and trimmers ----------------------------------------------------------------------------------
_TAPER = {"A": "Log (A)", "B": "Linear (B)", "C": "Reverse Log (C)", "W": "W-Taper", "G": "G-Taper", "D": "D-Taper"}


def _ohms(n: float) -> str:
    for div, unit in ((1e6, "MΩ"), (1e3, "kΩ"), (1, "Ω")):
        if n >= div:
            x = n / div
            return f"{x:g} {unit}"
    return f"{n:g} Ω"


def describe_pot(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"([ABCWGD]?)(\d+(?:[.,]\d+)?)\s*([kKmM]?)", value.strip())
    if not m:
        return ""
    n = _parse_si(m.group(2).replace(",", ".") + {"k": "k", "K": "k", "m": "M", "M": "M"}.get(m.group(3), ""))
    if not n:
        return ""
    dual = bool(types) and bool(re.search(r"\bdual\b|\bstereo\b|gang", types[0], re.I))  # the most common listing only
    taper = _TAPER.get(m.group(1).upper(), "")
    return " ".join(x for x in (_ohms(n), taper, "Dual-Gang" if dual else "", "Potentiometer") if x)


def describe_trim(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"[ABCW]?(\d+(?:[.,]\d+)?)\s*([kKmM]?)", value.strip())  # '100KB' on a service sheet: the taper is immaterial
    if not m:
        return ""
    n = _parse_si(m.group(1).replace(",", ".") + {"k": "k", "K": "k", "m": "M", "M": "M"}.get(m.group(2), ""))
    if not n:
        return ""
    return f"{_ohms(n)} Trimmer"  # the model (3362P, multi-turn) differs from board to board


# --- switches -------------------------------------------------------------------------------------------
def describe_switch(value: str, types: list[str]) -> str:
    v = value.upper().replace(" ", "")
    m = re.match(r"^(SP|DP|3P|4P|[1-6]P)(ST|DT|[2-9]T)", v)
    if not m:
        return ""
    poles = {"SP": "SP", "DP": "DP", "1P": "SP", "2P": "DP"}.get(m.group(1), m.group(1))
    throws = m.group(2)
    name = poles + throws
    t = (types[0] if types else "").lower()  # the most common listing: others may be a different switch of the same poles
    pos = re.search(r"\(?ON\)?-?OFF-?\(?ON\)?|ON-?ON-?ON|ON-?ON|ON-?OFF", v + " " + t.upper())
    pos_txt = ""
    if pos:
        p = pos.group(0).replace("(", "").replace(")", "")
        p = re.sub(r"ON-?OFF-?ON", "On-Off-On", p, flags=re.I)
        p = re.sub(r"ON-?ON-?ON", "On-On-On", p, flags=re.I)
        p = re.sub(r"ON-?ON", "On-On", p, flags=re.I)
        p = re.sub(r"ON-?OFF", "On-Off", p, flags=re.I)
        pos_txt = p
    if "rotary" in t:
        kind = "Rotary"
    elif "slide" in t:
        kind = "Slide"
    elif re.search(r"stomp|foot", t):
        kind = "Footswitch"
    elif "toggle" in t:
        kind = "Toggle"
    elif name in ("3PDT", "4PDT"):
        kind = "Footswitch"
    elif throws in ("ST", "DT") and name in ("SPST", "SPDT", "DPST", "DPDT"):
        kind = "Toggle"
    elif re.fullmatch(r"[4-9]T", throws):
        kind = "Rotary"
    else:
        kind = "Switch"
    if kind == "Rotary":
        pos_txt = ""
    return " ".join(x for x in (name, pos_txt, kind) if x)


# --- optos ----------------------------------------------------------------------------------------------
_LDR_SPECS = {"GL5516": "5-10 kΩ light 0.5 MΩ dark", "GL5528": "10-20 kΩ light 1 MΩ dark", "GL5537-1": "20-30 kΩ light 2 MΩ dark",
              "GL5537-2": "30-50 kΩ light 3 MΩ dark", "GL5539": "50-100 kΩ light 5 MΩ dark", "GL5549": "100-200 kΩ light 10 MΩ dark"}


def describe_opto(value: str, types: list[str]) -> str:
    v = value.upper().replace(" ", "")
    if re.match(r"^VTL5C\d", v) or v == "VACTROL":
        return "Vactrol (LED + LDR)"
    if re.match(r"^NSL-?32", v):
        return "Optocoupler (LED + LDR)"
    if re.match(r"^CLM6000", v):
        return "Optocoupler (LED + LDR)"
    if re.match(r"^H11F[123]", v):
        return "Photo-FET Optocoupler DIP-6"
    if re.match(r"^6N13[89]", v):
        return "Darlington Optocoupler DIP-8"
    if re.match(r"^CPC1017", v):
        return "Solid-State Relay SOP-4"
    if v in _LDR_SPECS:
        return f"LDR (Photoresistor) {_LDR_SPECS[v]}"
    if re.match(r"^(?:LDR\d*|GL55\d\d|PDV-P\d+|NSL-19|KE-?10720)", v):
        return "LDR (Photoresistor)"
    return ""


# --- inductors, transformers, crystals ------------------------------------------------------------------
def describe_inductor(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:-(\d+(?:\.\d+)?))?\s*([UMN]?)H", value.upper().replace("Μ", "U"))
    if not m:
        return ""
    unit = {"U": "µH", "M": "mH", "N": "nH", "": "H"}[m.group(3)]
    val = f"{m.group(1)}-{m.group(2)}" if m.group(2) else f"{float(m.group(1)):g}"
    return f"{val} {unit} {'Adjustable ' if m.group(2) else ''}Inductor"


_XFM = {"42TL019": "10 kΩ CT : 600 Ω CT", "42TM022": "1.5 kΩ CT : 600 Ω CT", "LT44": "20 kΩ : 1 kΩ CT"}


def describe_transformer(value: str, types: list[str]) -> str:
    v = re.sub(r"\s+.*$", "", value.upper())
    base = re.sub(r"(?:-?RC|-R|T)$", "", v)
    if base in _XFM:
        return f"Audio Transformer {_XFM[base]}"
    if re.match(r"^(?:42T[LM]\d{3}|TY-?\d{3}P?|OEP\d|LT\d\d|LM-NP)", v):
        return "Audio Transformer"
    return ""


def describe_crystal(value: str, types: list[str]) -> str:
    v = value.upper()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(K|M)HZ", v)
    if not m and re.match(r"^DT-?38$", v) and any("32.768" in t for t in types):
        m = re.match(r"(32.768)(K)", "32.768K")
    if not m:
        return ""
    cyl = " Cylinder" if re.search(r"AB38T|DT-?38", v) else ""
    return f"{m.group(1)} {m.group(2).lower() if m.group(2) == 'K' else 'M'}Hz Crystal{cyl}"


def describe(category: str, value: str, types: list[str]) -> str:
    fn = {"IC": lambda v, t: describe_ic(v), "POT": describe_pot, "TRIM": describe_trim, "SW": describe_switch,
          "OPTO": describe_opto, "L": describe_inductor, "XFM": describe_transformer, "XTAL": describe_crystal}.get(category)
    return fn(value, types) if fn else ""
