"""Board layouts (stripboard, tag strip, turret, perfboard): what the text printed on a layout
drawing says. A DIYLC drawing prints the values on the parts, turned and too small to OCR, but
it prints the parts that matter for a cross-reference in a legend under the board ('IC1 is OP07,
BJTs are BC546', 'Q2/Q4: BS170', 'Gain A47K') and names every pot at its three wires
('Gain 1', 'Tone 1&2'). Those lines read cleanly; the passives wait for a reading by eye
(transcribed/, see corrections.py)."""
from __future__ import annotations

import re

from .models import BomRow
from .normalize import is_plausible, normalize_row

BUILDS = ("pcb", "vero", "tagboard", "turret", "perfboard", "p2p")

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


# DIY Layout Creator's PDF export keeps every label as text: the value on each part, each pot's name
# over its value and taper ('Level' / '100K Log'), and the notes under the board ('Q1 - BC337-16').
# Older exports space the digits and units apart ('4 7 0', '12 K', '0,1 uF').
_DIYLC_TAPER = {"log": "A", "lin": "B", "linear": "B", "revlog": "C", "rev.log": "C", "w": "W"}  # keys lower-cased, spaces dropped
_DIYLC_POT = re.compile(r"(\d+(?:[.,]\d+)?[kKM])\s*(Rev\.?\s?log|Log|Lin(?:ear)?|W)", re.I)
_DIYLC_MARK = re.compile(r"\s*(?:\*+|\((?:\*|\?|\+|-)\)|\[\+\])\s*")
_DIYLC_REF = r"(?:Q|D|T|IC|U)\s?\d{1,2}"
_DIYLC_LEGEND = re.compile(rf"({_DIYLC_REF}(?:\s*(?:,|&|/|and)\s*(?:{_DIYLC_REF}|\d{{1,2}}))*)\s*[-–:=]\s*(.+?)"
                           rf"(?=\s*(?:[,&]\s*)?{_DIYLC_REF}\s*[-–:=]|$)")
_DIYLC_KIND = re.compile(r"^(Transistors?|IC|Diodes?)\s*(?:is|are|-|–|:)\s*(.+)$", re.I)
_DIYLC_PART = re.compile(r"^(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{2,11}\*?$", re.I)
_DIYLC_GENERIC = re.compile(r"\b(NPN|PNP)\b.*?\b(Ge(?:rmanium)?|Si(?:licon)?)\b|\b(Ge(?:rmanium)?|Si(?:licon)?)\b.*?\b(NPN|PNP)\b", re.I)


def _diylc_line(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"\d(?: \d)+", s):  # '4 7 0'
        s = s.replace(" ", "")
    return re.sub(r"(?<=\d) (?=(?:[kKMR]|[pnuµ]F|mH)\b)", "", s)  # '12 K', '0,1 uF', '100 K Log'


def _diylc_value(t: str) -> tuple[str, str] | None:
    """A part label on the board: (category, value), or None for anything else."""
    from .pdf import _VAL_C, _VAL_D, _VAL_IC, _VAL_Q, _VAL_R
    if t == "914":
        return "D", "1N914"
    if t == "Germ":
        return "D", "Ge"
    if re.fullmatch(r"(?:1[nN](?:34|60|\d{3,4})|2[nN]\d{4})[A-Za-z]?", t):
        t = t.upper()  # '1n914', '2n3702': a lower-case n is not a nanofarad here
    for cat, rx in (("C", _VAL_C), ("D", _VAL_D), ("Q", _VAL_Q), ("IC", _VAL_IC), ("R", _VAL_R)):
        if rx.match(t):
            return cat, t
    if re.fullmatch(r"\d+(?:[.,]\d+)?mH", t):
        return "L", t
    if re.fullmatch(r"[1-9]\d{1,3}", t):
        return "R", t  # a bare number on a DIYLC board is a resistor in ohms ('470', '51')
    return None


def _diylc_semi(desc: str) -> tuple[str, str]:
    """'2N4401 or similar CBE pinout' -> ('2N4401', 'or similar CBE pinout'); 'Higher gain PNP Germanium
    transistor' -> ('PNP Ge', 'Higher gain PNP Germanium transistor'); 'BC108 or BC107' kept whole."""
    desc = desc.strip(" .")
    words = desc.split()
    if words and _DIYLC_PART.match(words[0]):
        part = words[0].rstrip("*").upper().replace("1n", "1N")
        rest = " ".join(words[1:])
        if m := re.match(r"or\s+([A-Z0-9][A-Z0-9-]{2,11})\b(.*)", rest, re.I):
            if re.search(r"\d", m.group(1)):
                return f"{part} or {m.group(1).upper()}", m.group(2).strip(" ,")
        return part, rest
    if m := _DIYLC_GENERIC.search(desc):
        pol = (m.group(1) or m.group(4)).upper()
        mat = (m.group(2) or m.group(3))[:2].title()
        return f"{pol} {mat}", desc
    return "", desc


def diylc_pdf(pdf) -> dict:
    """The parts of a DIY Layout Creator PDF export, which has no designators on the passives: every
    value label counted ('×3 10K'), pots by the name printed over them, and the transistors, ICs and
    diodes the notes name by designator (or by kind: 'Transistors - BC107'). A part printed on the board
    and named in the notes is listed once. Returns {'rows', 'controls', 'text', 'board'}."""
    import pymupdf as fitz
    lines: list[str] = []
    words: list[str] = []
    with fitz.open(pdf) as doc:
        for page in doc:
            lines += [_diylc_line(l) for l in page.get_text("text").splitlines() if l.strip()]
            words += [w[4] for w in page.get_text("words")]
    text = "\n".join(lines)
    counts: dict[tuple[str, str], int] = {}
    pots: dict[str, str] = {}
    unnamed: dict[str, int] = {}
    legend: list[BomRow] = []
    named_values: set[str] = set()

    def semi(refs: list[str], desc: str, cat: str) -> None:
        value, note = _diylc_semi(desc)
        if not value:
            return
        for ref in refs:
            r = normalize_row(BomRow(ref=ref, value=value, category=cat, notes=note))
            legend.append(r)
        named_values.add(value.split(" or ")[0].upper())

    q_labels = sorted({w for w in words if re.fullmatch(r"Q\d{1,2}", w)}, key=lambda w: int(w[1:]))
    for i, line in enumerate(lines):
        bare = _DIYLC_MARK.sub(" ", line).strip()
        if m := _DIYLC_POT.fullmatch(bare):
            value = _DIYLC_TAPER[re.sub(r"\s", "", m.group(2).lower())] + m.group(1).upper().replace(",", ".")
            name = _DIYLC_MARK.sub(" ", lines[i - 1]).strip(" -") if i else ""
            if name and re.fullmatch(r"[A-Za-z][A-Za-z .'&/]{1,24}", name) and not _NOT_KNOB.match(name):
                key = name.title() if name.isupper() or name.islower() else name
                if key.lower() not in {k.lower() for k in pots}:
                    pots[key] = value
            elif not re.search(r"[A-Za-z]{3}", lines[i - 1] if i else ""):
                unnamed[value] = unnamed.get(value, 0) + 1
            continue
        if m := re.fullmatch(r"([A-Za-z][A-Za-z '&/]{1,24}?)\s*-?\s*" + _DIYLC_POT.pattern, bare, re.I):
            # 'Depth - 10k LINEAR' in the notes, or 'Sustain 100k LOG' repeating a pot already named on the drawing
            name = m.group(1).strip()
            if not _NOT_KNOB.match(name) and name.lower() not in {k.lower() for k in pots}:
                pots[name.title() if name.isupper() or name.islower() else name] = (
                    _DIYLC_TAPER[re.sub(r"\s", "", m.group(3).lower())] + m.group(2).upper().replace(",", "."))
            continue
        if any(_DIYLC_LEGEND.fullmatch(c.strip()) for c in [bare]) or re.match(_DIYLC_REF + r"\s*[-–:=,&/]", bare):
            for m in _DIYLC_LEGEND.finditer(bare):
                refs = _expand(re.sub(r"\s", "", m.group(1)).replace("and", "&"))
                pre = re.match(r"[A-Z]+", refs[0]).group(0) if refs else ""
                semi(refs, m.group(2), {"Q": "Q", "T": "Q", "D": "D"}.get(pre, "IC"))
            continue
        if m := _DIYLC_KIND.match(bare):
            kind = m.group(1).lower()
            cat = "Q" if kind.startswith("transistor") else "D" if kind.startswith("diode") else "IC"
            refs = (q_labels if cat == "Q" and q_labels else ["Q1"] if kind == "transistor"
                    else [m.group(1).title()])  # 'Transistor is 2N5088': the only one
            semi(refs, m.group(2), cat)
            continue
        tokens = re.sub(r"\s+\d+(?:/\d+)?W$", "", bare).split()  # '4k7 2W'
        found = [_diylc_value(t) for t in tokens]
        if tokens and all(found):
            for cat, value in found:
                counts[(cat, value)] = counts.get((cat, value), 0) + 1

    # 'Q1 - OC76' then 'Q1/Q2 - Ge PNP hfe ~112/304': a designator keeps its part number over the kind.
    by_ref: dict[str, BomRow] = {}
    for r in legend:
        if r.ref not in by_ref or (re.search(r"\d", r.value) and not re.search(r"\d", by_ref[r.ref].value)):
            by_ref[r.ref] = r
    legend = list(by_ref.values())
    rows: list[BomRow] = []
    order = {"IC": 0, "Q": 1, "D": 2, "C": 3, "R": 4, "L": 5}
    for (cat, value), n in counts.items():
        if cat in ("Q", "D", "IC") and value.upper() in named_values:
            continue
        r = normalize_row(BomRow(ref=f"×{1 if cat == 'IC' else n}", value=value, category=cat))
        if is_plausible(r):
            rows.append(r)
    rows.sort(key=lambda r: (order.get(r.category, 9), r.sort_key or 0))
    rows = legend + rows
    rows += [normalize_row(BomRow(ref=k, value=v, category="POT")) for k, v in pots.items()]
    rows += [normalize_row(BomRow(ref=f"×{n}", value=v, category="POT")) for v, n in unnamed.items()]
    m = re.search(r"\b(\d{1,2})\s?x\s?(\d{1,2})\b", text)
    return {"rows": rows, "controls": list(pots), "text": text, "board": f"{m.group(1)}x{m.group(2)}" if m else ""}
