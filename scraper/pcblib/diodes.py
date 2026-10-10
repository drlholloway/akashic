"""Short descriptions of diode parts for the parts index: 'Si Signal Diode DO-35 TH',
'Si Schottky DO-41 TH', 'Ge Signal Diode DO-7 TH', 'Si Zener 9.1 V 1 W DO-41
TH'. The package is the one the part number is registered in, from a table of well-known
families; a family whose package is not certain is described without one rather than guessed."""
from __future__ import annotations

import re

from .normalize import _ZENER_SERIES, zener_of_part

# (pattern on the part number, material, kind, package). First match wins.
_FAMILIES: list[tuple[re.Pattern, str, str, str]] = [(re.compile(rx), mat, kind, pkg) for rx, mat, kind, pkg in [
    # surface-mount spellings first: 1N4148W is SOD-123, 1N914BWS SOD-323
    (r"^1N4148W(?:S|T)\b|^1N914BWS|^B581[789]WS", "Si", "", "SOD-323"),
    (r"^1N4148W\b|^1N4148W-", "Si", "Signal Diode", "SOD-123"),
    (r"^BAT54", "Si", "Schottky", "SOT-23"),
    (r"^(?:1N914[AB]?|1N916[AB]?|1N4148|1N4448|1N4149|1N4150|1N4446|1N4447|1N45[6-9]A?|1N3600|1N3064|BAV2[01])$", "Si", "Signal Diode", "DO-35"),
    (r"^(?:1N400[1-7]|1N400X)$", "Si", "Rectifier", "DO-41"),
    (r"^UF400[1-7]$", "Si", "Ultrafast Rectifier", "DO-41"),
    (r"^1N540[0-8]$", "Si", "Rectifier", "DO-201AD"),
    (r"^(?:1N581[789]|SB1[2-6]0)$", "Si", "Schottky", "DO-41"),
    (r"^(?:BAT4[1-9]|BAT8[1-6]|1N5711|1N6263|SD101[ABC]?)$", "Si", "Schottky", "DO-35"),
    (r"^SB3[2-6]0$", "Si", "Schottky", "DO-201AD"),
    (r"^(?:1N34A?|1N270|1N695|1N100)$", "Ge", "Signal Diode", "DO-7"),
    (r"^(?:1N60P?|1N276|OA9[01]|OA47|OA79|OA81|OA85|AA11[2-9]|AA143|D9[A-Z]?|D18|D20|D311|GD\w+)$", "Ge", "Signal Diode", ""),
    (r"^(?:1S1555|1S1588|1S2473|1S953|1S2076|1SS133|1SS174|1SS176|1SS188|1SS270|1SS302|1SS352|MA150|MA856|BAS33|DS448|OA200|KD5(?:10|21)A?)", "Si", "Signal Diode", ""),
    (r"^(?:FDH?-?333)$", "Si", "Signal Diode", "DO-35"),
    (r"^BAS28", "Si", "Dual Signal Diode", "SOT-143"),
    (r"^(?:DAN|DAP)20[12]|^MA157", "Si", "Dual Signal Diode", ""),
    (r"^BA[24]82$", "Si", "Band-Switching Diode", ""),
    (r"^(?:1S188(?:FM)?|1N3666|GA\d{3}|OA61)$", "Ge", "Signal Diode", ""),
    (r"^(?:SR1K-?2|S5500G?|S5688G?|1S1885)$", "Si", "Rectifier", ""),
    (r"^1N580[2-6]$", "Si", "Fast Rectifier", ""),
    (r"^1N(?:25[3-6]|33[2-9]|34\d)$", "Si", "Rectifier", "DO-4"),  # stud-base rectifiers (NJ Semi sheet: 1N346 is 200 V 0.6 A)
    (r"^CDSH\d", "Si", "Schottky", "SOD-323"),
    (r"^(?:SM581[789]|RB1\d\d)", "Si", "Schottky", "SMD"),
    (r"^BAT8[1-6]S$", "Si", "Schottky", ""),
    (r"^(?:B\d{2,3}C\d{2,4}|W-?0[0-9]M?|DI1[05]\d{2}|MP35\d\d)$", "Si", "Bridge Rectifier", ""),
    (r"^0A9(?:DIL)?$", "Si", "Bridge Rectifier", "DIP-4"),  # a 4-pin DIL full bridge (Expanon MN3011 reverb PSU)
]]
# Zener series: (pattern, power, package)
_ZENER_PKG = [(re.compile(rx), pw, pkg) for rx, pw, pkg in [
    (r"^1N52[2-8]\d[A-D]?$", "500 mW", "DO-35"),
    (r"^1N(?:74[6-9]|75\d|9[5-9]\d)[A-D]?$", "500 mW", "DO-35"),
    (r"^1N4(?:6[7-9]\d|70\d|71[0-7])$", "500 mW", "DO-35"),
    (r"^1N47[2-6]\d[A-D]?$", "1 W", "DO-41"),
    (r"^BZX(?:55|79)", "500 mW", "DO-35"),
    (r"^BZX85", "1.3 W", "DO-41"),
    (r"^ZPD", "500 mW", "DO-35"),
]]


def _volts(v: str) -> str:
    """'9V1' -> '9.1 V', '12V' -> '12 V'."""
    m = re.fullmatch(r"(\d+)V(\d)?", v)
    return f"{m.group(1)}.{m.group(2)} V" if m and m.group(2) else f"{m.group(1)} V" if m else ""


def _mount(pkg: str) -> str:
    if pkg in ("DO-4", "DO-5"):
        return "Stud Mount"  # bolted to a chassis or heatsink
    return "SMD" if pkg.startswith(("SOD", "SOT", "SMA", "MELF")) else "TH" if pkg else ""


def describe(value: str) -> str:
    """The description of a diode part number, or '' for anything not known (generic words, LEDs)."""
    p = re.sub(r"\s+", "", value.upper()).rstrip("*")
    p = re.sub(r"(?<=\d)-(?:\d|[A-Z])$", "", p) if not p.startswith(("RD", "UZ")) else p  # '1N4148-2', '1N5817-B': a library variant
    # a bare zener voltage ('9V1', '12V') from the parts index
    if re.fullmatch(r"\d{1,2}V\d?", p):
        return f"Zener {_volts(p)}"
    zv = _volts(zener_of_part(p))
    if not zv:  # makers that print the voltage in the number: ZPD4.7, Renesas RD5.1EB, ROHM MTZ5.6B, UZ-5.1B, Toshiba 05Z15A, GZA4.7Y
        m = re.fullmatch(r"(?:ZPD|RD-?|MTZJ?|UZ-?|05Z|GZA)(\d{1,2}(?:\.\d)?)(?:[A-Z]{0,3}\d?(?:-[A-Z0-9])?)", p)
        zv = f"{m.group(1)} V" if m else ""
    if zv:
        pw, pkg = next(((pw, pkg) for rx, pw, pkg in _ZENER_PKG if rx.match(p)), ("", ""))
        return " ".join(x for x in ("Si Zener", zv, pw, pkg, _mount(pkg)) if x)
    for rx, mat, kind, pkg in _FAMILIES:
        if rx.match(p):
            kind = kind or ("Schottky" if p.startswith("B58") else "Signal Diode")
            if mat == "Ge" and not pkg:
                return f"Ge {kind} TH"  # germanium diodes are all leaded
            if pkg == "SMD":
                return f"{mat} {kind} SMD"  # surface mount, package not certain
            return " ".join(x for x in (mat, kind, pkg, _mount(pkg)) if x)
    if p == "1N821":
        return "Si Zener 6.2 V reference"
    return ""

