"""Parts lists from Eagle schematics. Eagle 6 and later save .sch files as XML, with one <part> per
placed component (name, value, library, deviceset), so the list is exact, with no OCR. Older Eagle
files are binary and return []. Named pots ('GAIN' valued 'A100K') become knobs; jacks, pads, frames
and power symbols are dropped."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .models import BomRow
from .normalize import is_plausible, normalize_row

_REF = re.compile(r"^(?:R|C|D|Q|IC|U|LED|L|SW|S|VR|RV|P|T|X|Y|OK|LDR|TR)\d{1,3}[A-Z]?$", re.I)
_SKIP_LIB = re.compile(r"supply|frame", re.I)
_SKIP_NAME = re.compile(r"^(?:IN|OUT|INPUT|OUTPUT|GND|VCC|VREF|9V|18V|DC|PWR|POWER|BATT?|JACK|J\d+|PAD\d*|TP\d*|M\d+|X\d+|LED[-_ ]?PAD|LUG\d*|FRAME\d*)$", re.I)
_POT_VALUE = re.compile(r"^(?:[ABCW]\s?\d+(?:\.\d+)?\s?[KkMR]?|\d+(?:\.\d+)?\s?[KkMR]?\s?[ABCW]?)$")


def is_eagle_xml(data: bytes) -> bool:
    head = data[:400].lstrip()
    return head.startswith(b"<?xml") and b"<eagle" in data[:2000]


def eagle_bom(data: bytes) -> list[BomRow]:
    if not is_eagle_xml(data):
        return []
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    rows: list[BomRow] = []
    seen: set[str] = set()
    for p in root.iter("part"):
        name = (p.get("name") or "").strip()
        value = (p.get("value") or "").strip()
        lib, dev = p.get("library") or "", (p.get("deviceset") or "").upper()
        if not name or _SKIP_LIB.search(lib) or _SKIP_NAME.match(name) or re.match(r"^(?:GND|VCC|V\+|FRAME)", dev):
            continue
        if _REF.match(name) and not value:
            # Value left blank: the part is the device ('LM308' + 'N'), or a generic symbol ('NPN-TO92' is an NPN).
            base = re.sub(r"[-_ ]?(?:TO-?\d+|SOT-?\d+|DIP\d*|TH|SMD)$", "", dev)
            if re.fullmatch(r"NPN|PNP|N-?JFET|P-?JFET|N-?MOSFET|P-?MOSFET|LED|LDR", base):
                value = base
            elif re.search(r"[A-Z]", base) and re.search(r"\d", base):
                value = base + re.sub(r"[^A-Z0-9]", "", (p.get("device") or "").upper())
        if re.fullmatch(r"\d{3,4}", value) and dev.startswith("1N"):
            value = "1N" + value                               # '4001' drawn with a 1N400X symbol
        if re.search(r"3PDT|4PDT", dev + " " + value.upper()):
            continue                                           # the bypass footswitch
        cat = ptype = ""
        if not _REF.match(name):
            # A part named for its job: a knob ('GAIN' = 'A100K'), a trimmer, or a switch.
            if _POT_VALUE.match(value) and (re.search(r"TRIM", dev) or not re.search(r"[ABCW]", value.upper())):
                cat, ptype = "TRIM", "Trimmer"                 # a trimmer, or a pot drawn without a taper
            elif _POT_VALUE.match(value) and (re.search(r"POT|ALPHA|R-?TRIM|VR", dev) or re.search(r"[ABCW]", value)):
                cat, ptype = "POT", "Potentiometer"
            elif re.search(r"SPDT|DPDT|SWITCH|TOGGLE", dev + " " + value.upper()):
                cat, ptype = "SW", "Switch"
            else:
                continue
            name = re.sub(r"(?<=[A-Za-z])1$", "", name).replace("_", " ").title()  # 'RATE1' is the Rate knob
        elif not value or value.upper() == name.upper():
            continue
        if name.upper() in seen:
            continue
        r = normalize_row(BomRow(ref=name, value=value, part_type=ptype, category=cat))
        if cat or is_plausible(r):
            seen.add(name.upper())
            rows.append(r)
    return rows
