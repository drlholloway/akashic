"""Parts-list audit: flag rows that do not look like valid parts, so they can be checked against
the source. Checks values that do not parse or sit outside a sane range or the standard series,
parts filed under the wrong kind, part numbers used once that are one character from a common
one, transistors the transistor database does not know, and mangled or duplicated designators.

`pcblib audit` runs it after a rescrape: it writes a filterable HTML report, a CSV and the flags
as JSON to data/cache/audit/, and compares with the previous run so a parser change that adds
flags shows up before it is deployed. A flag is a lead to check, not a verdict.
"""
from __future__ import annotations

import collections
import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import transistors
from .paths import CACHE_DIR, DATA_DIR

AUDIT_DIR = CACHE_DIR / "audit"



def find_flags(db: sqlite3.Connection, tdb: sqlite3.Connection) -> tuple[list[dict], int]:
    """Every flag for every parts row, most severe first; also returns the number of rows checked."""
    rows = db.execute("select circuit_id, coalesce(variant,''), ref, coalesce(value,''), category, coalesce(norm_value,''), coalesce(sort_key,0), coalesce(notes,''), coalesce(part_type,'') from bom").fetchall()
    circ = {r[0]: r[1:] for r in db.execute("select id, vendor, name, doc_url, url from circuits")}
    vendor_name = {r[0]: r[1] for r in db.execute("select id, name from vendors")}

    E24 = {10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91}
    VINTAGE = {25, 50}  # 0.05uF, 250pF: common on vintage schematics


    def mantissa(x: float) -> float:
        """Two leading digits as 10.0-99.9, without float drift (10pF is 1e-11, not 9.999e-12)."""
        import math
        e = math.floor(math.log10(x) + 1e-9)
        return round(x / 10 ** (e - 1), 4)


    def standard(x: float, e96_ok: bool) -> bool:
        m = mantissa(x)
        if abs(m - round(m)) < 0.05 and (round(m) in E24 or round(m) in VINTAGE):
            return True
        if e96_ok:  # 1% values like 49.9k, 90.9k, 6.19k: three significant digits
            m3 = m * 10
            return abs(m3 - round(m3)) < 0.05
        return False


    def source(notes: str) -> str:
        if "from schematic" in notes: return "schematic"
        if "OCR" in notes: return "OCR"
        return "text"


    REF_OK = re.compile(r"^(?:R|C|D|Q|U|IC|L|VR|RV|P|POT|SW|S|J|LED|TR|T|K|Z|ZD|DZ|X|XT|Y|F|FB|LDR|OC|OK|TRIM|RP|RT|CP|CR|VT|JP|OP|OA|B|BR|M|LD|RL|TL|PR|CT|CV|RLED|LEDR|CLR|RPD|CPD|REG|VREG|CB|RB|RC|RE|CE|CF|RF|RG|RS|RD)\d{0,3}[A-Za-z]?(?:\.\d)?$", re.I)
    RANGE_REF = re.compile(r"^[A-Z]{1,3}\d{1,3}\s*[-–]\s*[A-Z]{0,3}\d{1,3}$", re.I)
    NAMED = re.compile(r"^[A-Za-z][A-Za-z .&/+\-]{1,24}\d?$")  # a named control or part ('VOLUME', 'Tone 2')
    QTY = re.compile(r"^×\d+$")

    D_OK = re.compile(r"^(?:1N\d{3,4}[A-Z]?|1S\d{3,4}|1SS\d{2,3}|BAT\d{2}[A-Z]?|BA\d{3}|BAV\d{2}|BAS\d{2}|OA\d{2,3}|AA\d{3}|1N34A?|D9[A-Z]|FDH\d+|BZX\d+.*|BZV\d+.*|ZENER.*|\d{1,2}V\d?|\d+(?:\.\d)?V\s*ZENER|LEDS?|.*LED.*|GE|SI|GERMANIUM|SILICON|SCHOTTKY|MA\d{3}|SB\d+|SR\d+|UF\d+|11DQ\d+|MUR\d+|1N60P?|GD\d+|DD\d+|RB\d+|S1M|SS\d{2}|FR\d{3}|IS\d+)$", re.I)
    IC_OK = re.compile(r"^(?:[A-Z]{1,6}-?\d{2,}[A-Z0-9\-/.()]*|\d{2,5}[A-Z]{0,6}\d{0,5}[A-Z]{0,4}(?:[-/][A-Z0-9]+)*|CD4\d{3}[A-Z()]*|FV-?1|V\d{4}|THAT\d+.*|SPIN.*|BTDR-\d+H?|.*OP-?AMP.*|.*REGULATOR.*|VTL\d.*|NSL-?\d+.*|.*\bMODULE\b.*|.*CHARGE PUMP.*)$", re.I)
    KNOWN_IC = {"TL081", "TL082", "TL071", "TL072", "TL074", "TL084", "OP2134", "OPA2134", "7660SCPA", "7660S", "LM308", "LM741", "NE5532", "NE5534", "LM386", "CA3080", "LM13700", "PT2399", "MN3007", "MN3207", "MN3005", "MN3205", "MN3101", "MN3102", "V3207", "V3102", "LT1054", "MAX1044", "TC1044S", "ICL7660", "LM1458", "RC4558", "JRC4558", "NJM4558", "4558", "4580", "LF353", "TLC2272", "TLC2274", "OPA2604", "OPA1642", "LM324", "LM358", "LM833", "MC1458", "CD4049", "CD4069", "CD4013", "CD4066", "CD4046", "CD4007", "CD4040", "SA571", "NE570", "NE571", "V571", "LM311", "LM393", "TDA2003", "LM1036", "SSM2166",
                # real parts that sit one character from a commoner one
                "LF351", "LF356", "NE5534A", "4066", "CD4066", "4066N", "4046A", "MN3001", "MN3004", "MN3008", "MN3204", "MN3205", "MN3206", "MN3214",
                "TLC272", "5534", "NE5534", "CA741", "LM307", "LM301", "4559", "RC4559", "MC33174", "MC33178", "TLP222", "TLP222A",
                "LM741DIP", "LT1054/", "MAX1044S", "78L05Z", "TL061", "TL062", "TL064", "TL031", "OPA2134", "LM386N", "CD4024", "CD4029"}
    KNOWN_Q = {"BC264D", "BC264C", "BC264B", "2N6027", "2N2646", "CV7353", "CV7351", "FS36999", "2N2222A_CEB", "NP4124", "TI592", "A02650"}
    Q_WORDS = {"NPN", "PNP", "JFET", "FET", "MOSFET", "GE", "SI", "GE PNP", "GE NPN", "PNP GE", "NPN GE", "NPN SI", "PNP SI"}

    flags = []
    MARKS = re.compile(r"[*†‡#]+|\((?:optional|opt\.?|see notes?|ge|si)\)", re.I)
    ALT = re.compile(r"\s*(?:/|,|\bor\b|\bOR\b)\s*|\s+\(\s*|\)\s*")  # 'BAT41 (1N4148)' splits; 'CD4069(UBE)' is one part
    LED_WORDS = re.compile(r"^(?:\d\s?mm|red|green|blue|yellow|white|orange|amber|clear|diffused|bi-?colou?r|rgb|status|led|leds|lysdiod|flat top|\s)+$", re.I)
    PLACEHOLDER = re.compile(r"^(?:your|your choice|nothing|none|jumper|\(jumper\)|omit|n/?a|-|–|optional|\(optional\)|see notes?|tbd)$", re.I)
    GENERIC_Q = re.compile(r"^(?:(?:NPN|PNP|N-?CHANNEL|P-?CHANNEL|JFET|MOSFET|FET|BJT|GE|SI|GERMANIUM|SILICON|LOW|MEDIUM|HIGH|GAIN|HFE|TRANSISTOR|MATCHED|PAIR|\s|[()\[\]+.-])+)$", re.I)
    REGULATOR = re.compile(r"^(?:L?78L?\d{2}|L?79L?\d{2}|LM317|LM1117|AMS1117.*|LP2950.*|MCP1700.*|TL431.*|7660.*|ICL7660.*|TC1044.*|LT1054.*|MAX1044.*)", re.I)
    LOOSE_POT = re.compile(r"(?<![A-Za-z0-9])(?:[ABCWLG]\s?\d+(?:[.,]\d+)?\s?[kKmM]|\d+(?:[.,]\d+)?\s?[kKmM]\s?[ABCWLG]?|\d+(?:[.,]\d+)?\s?[kKmM]?\s?(?:lin|log|rev))(?![A-Za-z0-9])", re.I)


    def alternatives(v: str) -> list[str]:
        v = MARKS.sub("", v).strip()
        return [a.strip() for a in ALT.split(v) if a.strip()]


    def shorthand_q(a: str) -> list[str]:
        a = a.upper()
        if re.fullmatch(r"\d{3,4}[A-Z]?", a):
            return ["2N" + a, "BC" + a, "MPSA" + a]
        if re.fullmatch(r"C\d{3,4}.*|K\d{2,3}.*|A\d{3,4}.*", a):
            return ["2S" + a]
        return [a]


    def flag(r, severity, reason, suggestion="", kind="bad value"):
        cid, variant, ref, value, cat, norm, sk, notes, ptype = r
        vendor, name, doc_url, url = circ.get(cid, ("?", "?", "", ""))
        flags.append({"vendor": vendor, "vendor_name": vendor_name.get(vendor, vendor), "circuit": cid, "name": name,
                      "page": f"https://akashic.cryptideffects.com/circuit/{cid.replace(':', '-')}", "doc": doc_url or url,
                      "variant": variant, "ref": ref, "value": value, "category": cat, "source": source(notes),
                      "severity": severity, "kind": kind, "reason": reason, "suggestion": suggestion})


    # Library-wide use counts for part numbers, to spot one-off OCR slips of a common part.
    pn_count = collections.Counter()
    for r in rows:
        if r[4] in ("D", "Q", "IC"):
            pn_count[(r[4], r[3].strip().upper())] += 1


    def near(cat: str, v: str) -> str:
        """A common part number one edit away (substitution, insertion or deletion)."""
        best = ""
        for (c, other), n in pn_count.items():
            if c != cat or n < 5 or other == v or abs(len(other) - len(v)) > 1:
                continue
            if len(other) == len(v):
                ok = sum(a != b for a, b in zip(other, v)) == 1
            else:
                s, l = (v, other) if len(v) < len(other) else (other, v)
                ok = any(l[:i] + l[i + 1:] == s for i in range(len(l)))
            if ok and (not best or n > pn_count[(cat, best)]):
                best = other
        return best


    tcache = {}


    def known_transistor(v: str) -> bool:
        key = v.upper()
        if key not in tcache:
            try:
                tcache[key] = transistors.lookup(tdb, v) is not None
            except Exception:
                tcache[key] = False
        return tcache[key]


    # Per circuit/variant designator numbers, to spot outliers like R312 on a board whose resistors stop at R45.
    nums = collections.defaultdict(list)
    for r in rows:
        m = re.match(r"^([A-Z]+)(\d+)$", r[2].upper())
        if m:
            nums[(r[0], r[1], m.group(1))].append(int(m.group(2)))
    seen = collections.defaultdict(dict)

    for r in rows:
        cid, variant, ref, value, cat, norm, sk, notes, ptype = r
        v = re.sub(r"\s{2,}[A-Z]{1,2}$", "", value.strip())  # column bleed: '1N5817       S'
        V = v.upper()

        # Designator
        if RANGE_REF.match(ref):
            flag(r, "medium", "Designator range was not expanded into one row per part", kind="format the library can't read")
        elif not (REF_OK.match(ref) or QTY.match(ref) or (cat in ("POT", "SW", "TRIM", "LED", "CONN", "HW", "OTHER") and NAMED.match(ref))):
            if re.match(r"^[A-Z]{1,3}\d{4,}$", ref.upper()):
                flag(r, "medium", "Designator number has four or more digits (a part number read as a designator?)", kind="designator")
            elif re.match(r"^[A-Z]{1,3}\d+[A-Z0-9]{2,}$", ref.upper()) or re.search(r"\d[OISZ]\b|[OISZ]\d", ref.upper()[1:]):
                flag(r, "medium", "Designator looks mangled by OCR (letters inside the number)", kind="designator")
            elif cat in ("R", "C", "D", "Q", "IC", "L"):
                flag(r, "medium" if not re.search(r"\d", ref) and len(ref) > 4 else "low", "Designator is not a designator (a word from the page?)" if not re.search(r"\d", ref) and len(ref) > 4 else "Unusual designator", kind="designator")
        m = re.match(r"^([A-Z]+)(\d+)$", ref.upper())
        if m:
            others = sorted(nums[(cid, variant, m.group(1))])
            n = int(m.group(2))
            if len(others) >= 4:
                second = others[-2] if others[-1] == n else others[-1]
                if n > 100 and n > 3 * second and n - second > 60:
                    flag(r, "medium", f"Designator number far past the rest ({m.group(1)}{second} is the next highest)", kind="designator")
        key = ref.upper()
        if not QTY.match(ref) and key in seen[(cid, variant)] and seen[(cid, variant)][key] != norm:
            flag(r, "medium", f"Designator listed twice with different values (also {seen[(cid, variant)][key]})", kind="designator")
        seen[(cid, variant)].setdefault(key, norm)

        # Value, by category
        if cat == "R":
            digits = re.sub(r"\D", "", v).strip("0")  # 4700 is 47 then zeros; 4702 is four significant digits
            if re.fullmatch(r"\d+(?:[.,]\d+)?\s?(?:[pnuµ]F?|[pnuµ]\d+|F)", v, re.I):
                flag(r, "high", "Resistor carries a capacitor value", kind="wrong category")
            elif re.fullmatch(r"\d+m\d+", v) and sk < 1:
                flag(r, "high", "Resistor written '2m2' is read as milliohms, not megohms", kind="format the library can't read")
            elif sk <= 0:
                flag(r, "high", "Resistor value does not parse", kind="format the library can't read")
            elif re.match(r"^(?:1N|2N|BC|TL|LM)\d{3}", V):
                flag(r, "high", "Resistor carries a semiconductor part number", kind="wrong category")
            elif sk < 1 and not re.search(r"R|Ω|ohm", v, re.I):
                flag(r, "high", "Resistor under 1 ohm")
            elif sk > 22e6:
                flag(r, "high", "Resistor over 22M")
            elif re.match(r"^0\d", v):
                flag(r, "medium", "Resistor value with a leading zero")
            elif len(digits) >= 4 and not re.search(r"\d[.,]\d", v):
                flag(r, "medium", "Resistor value has four or more significant digits")
            elif not standard(sk, e96_ok=True):
                flag(r, "medium", "Resistor value is not a standard (E24/E96) value")
            elif re.fullmatch(r"\d{1,2}", v) and source(notes) != "text":
                flag(r, "low", "Bare one- or two-digit resistor value from OCR (unit lost?)")
        elif cat == "C":
            if re.match(r"^(?:1N\d{3}|BAT\d|2N\d{3}|BC\d{3}|LED)", V):
                flag(r, "high", "Capacitor carries a diode or transistor part number", kind="wrong category")
            elif re.fullmatch(r"\d+(?:[.,]\d+)?\s?[kKM]|\d+(?:[.,]\d+)?\s?(?:R|ohms?|Ω)", v, re.I):
                flag(r, "high", "Capacitor carries a resistor value", kind="wrong category")
            elif sk <= 0:
                flag(r, "high", "Capacitor value does not parse", kind="format the library can't read")
            elif sk < 0.5e-12 or sk > 22000e-6:
                flag(r, "high", "Capacitor value out of range (under 0.5pF or over 22000uF)")
            elif not standard(sk, e96_ok=False):
                flag(r, "medium", "Capacitor value is not a standard (E24) value")
        elif cat in ("POT", "TRIM"):
            noun = "Pot" if cat == "POT" else "Trimmer"
            if sk <= 0 and cat == "TRIM" and (known_transistor(v) or re.match(r"^(?:BC|BF|2N|2SK|2SC|J\d{3}|MPF)", V) or "TRANSISTOR" in V):
                flag(r, "high", f"Transistor filed as a trimmer (designator {ref})", kind="wrong category")
            elif sk <= 0 and re.search(r"[1-4]P\d{1,2}T|[SD]P[SD]T|ROTARY", V):
                flag(r, "medium", f"Switch filed as a {noun.lower()}", kind="wrong category")
            elif sk <= 0 and LOOSE_POT.search(v):
                flag(r, "medium", f"{noun} value has extra words the library does not read ('dual', 'trim', footnote marks)", kind="format the library can't read")
            elif sk <= 0:
                flag(r, "high" if cat == "POT" else "medium", f"{noun} value is not a pot value")
            elif sk < 100 or sk > 10e6:
                flag(r, "high", f"{noun} value out of range (under 100 ohms or over 10M)")
            elif not standard(sk, e96_ok=False):
                flag(r, "low", "Pot value is not a standard value")
        elif cat == "D":
            alts = alternatives(v)
            def diode_ok(a):
                A = a.upper()
                return bool(D_OK.match(A) or LED_WORDS.match(a) or re.fullmatch(r"\d{3,4}[A-Z]?|34A|60P?", A)
                            or re.fullmatch(r"\d{1,2}(?:[.V]\d)?V?\s*(?:ZENER)?|ZENER.*|.*SCHOTTKY.*|GERM.*|1S\d+|2D\d+.*|MA\d+.*|BAS\d+.*|.*\bDIODES?\b.*|.*\bZENER\b.*|1N47\d\d[AB]?\b.*", A))
            if re.fullmatch(r"\d+(?:\.\d+)?\s*[pnuµ]F?", v, re.I) or re.fullmatch(r"\d+(?:\.\d+)?\s*[kKM]", v):
                flag(r, "high", "Diode carries a capacitor or resistor value", kind="wrong category")
            elif re.match(r"^(?:TL|LM|NE|JRC|RC|CD|OP)\d|^\d{4}$|DIP|SOCKET", V) and not re.fullmatch(r"\d{3,4}", V):
                flag(r, "high", "Diode carries an IC or socket", kind="wrong category")
            elif re.match(r"^(?:2N|BC|2SC|2SK|J\d{3})\d*", V) and not re.match(r"^2N\d{0}$", V) and known_transistor(v):
                flag(r, "high", "Diode carries a transistor part number", kind="wrong category")
            elif PLACEHOLDER.match(v.strip()):
                flag(r, "low", "Placeholder instead of a part (nothing, jumper, your choice)")
            elif alts and not all(diode_ok(a) for a in alts):
                s = near("D", V)
                flag(r, "high" if s else "medium", "Unrecognised diode part number", s)
        elif cat == "Q":
            if re.fullmatch(r"\d+(?:\.\d+)?\s*[pnuµkKM]F?", v):
                flag(r, "high", "Transistor carries a passive value")
            elif re.match(r"^1N\d", V):
                flag(r, "high", "Transistor carries a diode part number")
            elif REGULATOR.match(V):
                pass  # a regulator or charge pump on a Q designator
            elif re.search(r"SOCKET|\bPIN\b|\bPAD\b", V):
                flag(r, "medium", "Transistor row carries a socket or pad, not a part", kind="wrong category")
            elif V in Q_WORDS or GENERIC_Q.match(V) or re.search(r"\bYOUR\b|\bANY\b|MATCHED|SEE |\bOR\b.*\bOR\b", V):
                pass  # a generic description ('NPN Germanium', 'Low gain')
            else:
                alts = [a for a in alternatives(re.sub(r"^(?:JFET|MOSFET|NPN|PNP)\s+", "", v, flags=re.I)) if a]
                parts = [a for a in alts if not GENERIC_Q.match(a)]
                if parts and not any(known_transistor(c) or c.upper().rstrip("*") in KNOWN_Q for a in parts for c in shorthand_q(a)):
                    s = near("Q", V)
                    flag(r, "high" if s else "medium", "Transistor not in the transistor database", s)
        elif cat == "IC":
            if re.fullmatch(r"\d+(?:\.\d+)?\s*[pnuµkKM]F?", v) or re.match(r"^(?:1N|2N|BC)\d", V):
                flag(r, "high", "IC carries a passive value or discrete part number")
            elif re.search(r"SOCKET|\bDIP\b.*(?:SWITCH|POS)|POS\.? DIP|SW_DIP", V):
                flag(r, "low", "IC row carries a socket or DIP switch", kind="wrong category")
            elif not all(IC_OK.match(MARKS.sub("", a).replace(" ", "")) for a in alternatives(v) or [v]):
                s = near("IC", V)
                flag(r, "high" if s else "medium", "IC part number does not look like one", s)
            elif pn_count[("IC", V)] == 1 and V not in KNOWN_IC and re.sub(r"(?:[A-Z]{1,3}|-\w+)$", "", V) not in KNOWN_IC:  # NE5534A, TL072CP
                s = near("IC", V)
                if s:
                    flag(r, "high", "One-off IC part number, one character from a common one", s)

    sev_rank = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: (sev_rank[f["severity"]], f["vendor"], f["circuit"], f["variant"], f["ref"]))
    return flags, len(rows)


KINDS = ["bad value", "wrong category", "format the library can't read", "designator"]


def _key(f: dict) -> tuple:
    return (f["circuit"], f["variant"], f["ref"], f["value"], f["reason"])


def write_report(flags: list[dict], rows_checked: int, boards_total: int, out: Path, run_at: str = "") -> None:
    """The filterable HTML report: flags grouped by board, linked to the board page and its build doc."""
    vendors = sorted({f["vendor"] for f in flags})
    vname = {f["vendor"]: f["vendor_name"] for f in flags}
    reasons = sorted({f["reason"] for f in flags})
    boards: dict[str, dict] = {}
    for f in flags:
        b = boards.setdefault(f["circuit"], {"c": f["circuit"], "n": f["name"], "v": vendors.index(f["vendor"]), "p": f["page"],
                                             "d": f["doc"], "r": []})
        b["r"].append([f["ref"], f["variant"], f["value"], {"high": 0, "medium": 1, "low": 2}[f["severity"]], KINDS.index(f["kind"]),
                       reasons.index(f["reason"]), f["suggestion"], {"text": 0, "OCR": 1, "schematic": 2}[f["source"]], f["category"]])
    data = {"vendors": [[v, vname[v]] for v in vendors], "kinds": KINDS, "reasons": reasons, "boards": list(boards.values()),
            "stats": {"rows": rows_checked, "boards": boards_total, "flags": len(flags), "flagged": len(boards),
                      "date": run_at or datetime.now().strftime("%Y-%m-%d %H:%M")}}
    tpl = (Path(__file__).with_name("audit_report.html")).read_text()
    out.write_text(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False)))


def run(out_dir: Path = AUDIT_DIR) -> dict:
    """Audit the library, write the report, CSV and JSON, and compare with the previous run
    (out_dir/audit.json). Returns the counts and the flags this run added and cleared."""
    db = sqlite3.connect(DATA_DIR / "library.sqlite")
    tdb = sqlite3.connect(transistors.TRANS_DB)
    flags, rows_checked = find_flags(db, tdb)
    boards_total = db.execute("select count(*) from circuits").fetchone()[0]
    out_dir.mkdir(parents=True, exist_ok=True)
    run_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    meta_file = out_dir / "meta.json"
    previous_at = json.loads(meta_file.read_text()).get("run_at", "") if meta_file.exists() else ""
    last = out_dir / "audit.json"
    previous = json.loads(last.read_text()) if last.exists() else None
    last.write_text(json.dumps(flags, ensure_ascii=False))
    # The boards that existed at each run, so flags on a board a refresh just found are told apart
    # from flags a parser change added to a board that was already there.
    boards_file = out_dir / "boards.json"
    known = set(json.loads(boards_file.read_text())) if boards_file.exists() else None
    boards_file.write_text(json.dumps(sorted(r[0] for r in db.execute("select id from circuits"))))
    with open(out_dir / "audit.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()) if flags else ["circuit"])
        w.writeheader()
        w.writerows(flags)
    write_report(flags, rows_checked, boards_total, out_dir / "parts-audit.html", run_at)
    meta_file.write_text(json.dumps({"run_at": run_at, "previous_run_at": previous_at, "flags": len(flags), "rows": rows_checked}))
    result = {"run_at": run_at, "previous_run_at": previous_at, "rows": rows_checked, "flags": len(flags), "boards": len({f["circuit"] for f in flags}),
              "severity": dict(collections.Counter(f["severity"] for f in flags)), "previous": None, "added": [], "cleared": [],
              "reasons": collections.Counter(f["reason"].split(" (")[0] for f in flags)}
    if previous is not None:
        before = {_key(f): f for f in previous}
        now = {_key(f): f for f in flags}
        result["previous"] = {"flags": len(previous), "boards": len({f["circuit"] for f in previous})}
        added = [now[k] for k in now.keys() - before.keys()]
        result["added"] = [f for f in added if known is None or f["circuit"] in known]
        result["added_new_boards"] = [f for f in added if known is not None and f["circuit"] not in known]
        result["cleared"] = [before[k] for k in before.keys() - now.keys()]
        result["reasons_before"] = collections.Counter(f["reason"].split(" (")[0] for f in previous)
    return result
