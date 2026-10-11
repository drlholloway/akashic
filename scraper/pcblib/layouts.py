"""Board layouts (stripboard, tag strip, turret, perfboard): what the text printed on a layout
drawing says. A DIYLC drawing prints the values on the parts, turned and too small to OCR, but
it prints the parts that matter for a cross-reference in a legend under the board ('IC1 is OP07,
BJTs are BC546', 'Q2/Q4: BS170', 'Gain A47K') and names every pot at its three wires
('Gain 1', 'Tone 1&2'). Those lines read cleanly; the passives wait for a reading by eye
(transcribed/, see corrections.py)."""
from __future__ import annotations

import re

from .models import BomRow
from .normalize import normalize_row

BUILDS = ("pcb", "vero", "tagboard", "turret", "perfboard")

_NOTE = "OCR; from the layout legend"
_REFS = r"(?:IC|Q|D|T|U|LED|TR|VR)\d{1,2}(?:\s?[-–/&,]\s?(?:(?:IC|Q|D|T|U|LED|TR|VR)?\d{1,2}))*"
_PART = r"[A-Z0-9][A-Za-z0-9\-/]{2,14}"
_REF_CLAUSE = re.compile(rf"^({_REFS})\s*(?:is|are|:|=)\s*({_PART})$")
_KIND = {"bjt": "Q", "bjts": "Q", "jfet": "Q", "jfets": "Q", "fet": "Q", "fets": "Q", "mosfet": "Q", "mosfets": "Q",
         "transistor": "Q", "transistors": "Q", "trannies": "Q", "ic": "IC", "ics": "IC", "opamp": "IC", "op-amp": "IC",
         "opamps": "IC", "diodes": "D", "diode": "D", "all diodes": "D", "all transistors": "Q"}
_KIND_CLAUSE = re.compile(rf"^(all (?:diodes|transistors)|[A-Za-z\-]{{2,11}})\s*(?:is|are|:|=)\s*({_PART})$", re.I)
_POT_VALUE = r"(?:[ABCW]\s?\d+(?:[.,]\d+)?\s?[kKM]|\d+(?:[.,]\d+)?\s?[kKM]\s?[ABCW])\b"
_POT_CLAUSE = re.compile(rf"^([A-Za-z][A-Za-z .&/+\-]*?)\s*(?::|=|is|are)?\s*({_POT_VALUE})$")
_LUG = re.compile(r"^([A-Z][A-Za-z.]*(?: [A-Z][A-Za-z.]*){0,2}) [123](?:\s?&\s?[123])*$")
_NOT_KNOB = re.compile(r"^(?:sw|switch|input|output|ground|gnd|led|in|out|jack|dc|board|pin|lug|q|ic|d|level \d)\b", re.I)


def _clauses(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        for piece in line.split(" | "):
            # 'Gain A47K, Tone B100K': one fact per comma, but '4,7µF' and '2,2K' are decimals
            out += [c.strip(" .;") for c in re.split(r",\s+|;\s*", piece) if c.strip(" .;")]
    return out


def _expand(refs: str) -> list[str]:
    """'D2-D3' -> D2, D3; 'Q2/Q4' -> Q2, Q4; 'Q1-3' -> Q1, Q2, Q3."""
    pre = re.match(r"[A-Z]+", refs).group(0)
    out: list[str] = []
    for part in re.split(r"\s?[/&,]\s?", refs):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if re.search(r"[-–]", part) and len(nums) == 2 and nums[0] < nums[1] <= nums[0] + 12:
            out += [f"{pre}{n}" for n in range(nums[0], nums[1] + 1)]
        else:
            out += [f"{pre}{n}" for n in nums]
    return list(dict.fromkeys(out))


def controls(text: str) -> list[str]:
    """Knob names from the wire labels: a pot is named at each of its lugs ('Gain 1', 'Tone 1&2')."""
    names: list[str] = []
    for c in _clauses(text):
        m = _LUG.match(c)
        if m and not _NOT_KNOB.match(m.group(1)) and m.group(1) not in names:
            names.append(m.group(1))
    return names


def legend_rows(text: str) -> list[BomRow]:
    """The parts a layout's legend names: ICs, transistors and diodes by designator or by kind
    ('BJTs are BC546' is one row named BJTs, the count not being printed), and pots by knob name."""
    rows: list[BomRow] = []
    knobs = controls(text)
    seen: set[tuple[str, str]] = set()

    def add(ref: str, value: str, category: str) -> None:
        if (ref, value) in seen:
            return
        seen.add((ref, value))
        rows.append(normalize_row(BomRow(ref=ref, value=value, category=category, notes=_NOTE)))

    for c in _clauses(text):
        c = re.sub(r"^0(?=\d(?:\s?[-–]\s?\d)?\s*[:=])", "Q", c)  # 'Q1-3:' read as '01-3:'
        if m := _REF_CLAUSE.match(c):
            pre = re.match(r"[A-Z]+", m.group(1)).group(0)
            cat = {"IC": "IC", "U": "IC", "D": "D", "LED": "LED", "VR": "TRIM"}.get(pre, "Q")
            for ref in _expand(m.group(1)):
                add(ref, m.group(2), cat)
        elif (m := _POT_CLAUSE.match(c)) and not re.match(_REFS, c):
            value = re.sub(r"\s", "", m.group(2))
            value = re.sub(r"^(\d+(?:[.,]\d+)?[kKM])([ABCW])$", r"\2\1", value).upper().replace(",", ".")
            who = m.group(1).strip(" :")
            if re.fullmatch(r"(?:all )?pots?(?: are)?", who, re.I):
                for k in knobs:
                    add(k, value, "POT")
            else:
                for name in re.split(r"\s*(?:&|/|\band\b)\s*", who):
                    if name and not _NOT_KNOB.match(name):
                        add(name, value, "POT")
        elif (m := _KIND_CLAUSE.match(c)) and m.group(1).lower() in _KIND and re.search(r"\d", m.group(2)):
            add(m.group(1), m.group(2), _KIND[m.group(1).lower()])
    return rows
