"""Transistor parameter database: import a MySQL dump of parts and their properties
into data/transistors.sqlite, and look up substitutes for the transistors the
library's parts lists name."""
from __future__ import annotations

import math
import re
import sqlite3
from pathlib import Path
from typing import Iterator

from .paths import DATA_DIR

TRANS_DB = DATA_DIR / "transistors.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parts (id INTEGER PRIMARY KEY, partnum TEXT NOT NULL, part_type TEXT NOT NULL DEFAULT '',
  partnum_ll TEXT, partnum_tr TEXT, sort TEXT, sort_tr TEXT);
CREATE TABLE IF NOT EXISTS props (id INTEGER PRIMARY KEY, partnum TEXT NOT NULL, p_key TEXT, p_key_q TEXT, p_unit TEXT,
  p_val TEXT NOT NULL DEFAULT '', p_val_rng1 TEXT NOT NULL DEFAULT '', p_val_rng2 TEXT NOT NULL DEFAULT '', p_src TEXT NOT NULL, date_modified TEXT);
CREATE TABLE IF NOT EXISTS prop_names (id INTEGER PRIMARY KEY, prop_key TEXT, prop_name TEXT, prop_unit TEXT, value_type TEXT, enumOpts_json TEXT);
"""
_INDEXES = """
CREATE INDEX IF NOT EXISTS parts_partnum ON parts(partnum);
CREATE INDEX IF NOT EXISTS props_partnum ON props(partnum);
CREATE INDEX IF NOT EXISTS props_key_val ON props(p_key, p_val);
"""
_TABLES = {"parts": "parts", "_assoc__part_props": "props", "_dict__prop_names": "prop_names"}


def _tuples(line: str) -> Iterator[list]:
    """Parse one `(...),(...)` line of a MySQL INSERT into Python values."""
    i, n = 0, len(line)
    while i < n:
        if line[i] != "(":
            i += 1
            continue
        i += 1
        row: list = []
        while i < n:
            c = line[i]
            if c in " ,":
                i += 1
                continue
            if c == ")":
                i += 1
                break
            if c == "'":
                j = i + 1
                buf = []
                while j < n:
                    if line[j] == "\\":
                        buf.append(line[j + 1])
                        j += 2
                    elif line[j] == "'":
                        break
                    else:
                        buf.append(line[j])
                        j += 1
                row.append("".join(buf))
                i = j + 1
            else:
                j = i
                while j < n and line[j] not in ",)":
                    j += 1
                tok = line[i:j].strip()
                row.append(None if tok == "NULL" else (int(tok) if tok.lstrip("-").isdigit() else tok))
                i = j
        yield row


def import_dump(dump_dir: Path, db_path: Path = TRANS_DB) -> dict[str, int]:
    """Load the three dump files into SQLite. Re-runnable: tables are rebuilt."""
    conn = sqlite3.connect(db_path)
    conn.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
    for t in _TABLES.values():
        conn.execute(f"DROP TABLE IF EXISTS {t}")
    conn.executescript(_SCHEMA)
    counts: dict[str, int] = {}
    for src, table in _TABLES.items():
        path = dump_dir / f"{src}.sql"
        if not path.exists():
            continue
        ncols = {"parts": 7, "props": 10, "prop_names": 6}[table]
        placeholders = ",".join("?" * ncols)
        batch: list[list] = []
        n = 0
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.startswith("("):
                    continue
                for row in _tuples(line.rstrip("\n").rstrip(";").rstrip(",")):
                    if len(row) == ncols:
                        batch.append(row)
                if len(batch) >= 20000:
                    conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", batch)
                    n += len(batch)
                    batch = []
        if batch:
            conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", batch)
            n += len(batch)
        conn.commit()
        counts[table] = n
    conn.executescript(_INDEXES)
    conn.commit()
    conn.close()
    return counts


# ---------------------------------------------------------------------------
# Substitution: a flat spec table pivoted from the property rows, a tolerant
# part-number lookup, and a scored search for parts of the same kind.

_SPEC_KEYS = {
    "TranMat": "mat", "Pol": "pol", "hFE": "hfe", "Vce": "vce", "Vcb": "vcb", "Ic": "ic", "Pc": "pc", "ft": "ft",
    "FETType": "fettype", "CntlChType": "ch", "Vds": "vds", "Vgs": "vgs", "Vgs(th)": "vgsth", "Vgs(off)": "vgsoff",
    "Id": "idmax", "Pd": "pd", "Rds": "rds",
}
_NUMERIC = ("hfe", "vce", "vcb", "ic", "pc", "ft", "vds", "vgs", "vgsth", "vgsoff", "idmax", "pd", "rds")


def build_specs(db_path: Path = TRANS_DB) -> int:
    """Pivot the property rows into one row per part; re-runnable."""
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS specs")
    conn.execute("CREATE TABLE specs (partnum TEXT PRIMARY KEY, kind TEXT, mat TEXT, pol TEXT, fettype TEXT, ch TEXT, "
                 + ", ".join(f"{k} REAL" for k in _NUMERIC) + ")")
    rows: dict[str, dict] = {}
    for partnum, key, val in conn.execute("SELECT partnum, p_key, p_val FROM props WHERE p_key IN (%s)" % ",".join("?" * len(_SPEC_KEYS)), list(_SPEC_KEYS)):
        col = _SPEC_KEYS[key]
        d = rows.setdefault(partnum, {})
        if col in _NUMERIC:
            try:
                d[col] = float(val)
            except ValueError:
                continue
        else:
            d[col] = val
    out = []
    for pn, d in rows.items():
        kind = "bjt" if "pol" in d else ("jfet" if d.get("fettype") == "JFET" else ("mosfet" if d.get("fettype") else ""))
        if not kind:
            continue
        out.append((pn, kind, d.get("mat"), d.get("pol"), d.get("fettype"), d.get("ch"), *[d.get(k) for k in _NUMERIC]))
    conn.executemany("INSERT OR REPLACE INTO specs VALUES (" + ",".join("?" * (6 + len(_NUMERIC))) + ")", out)
    conn.execute("CREATE INDEX IF NOT EXISTS specs_kind ON specs(kind, mat, pol, fettype, ch)")
    conn.commit()
    conn.close()
    return len(out)


def _candidates(pn: str) -> list[str]:
    """Spellings to try for a parts-list value: '2SC1815-GR' -> 2SC1815-GR, 2SC1815;
    'MMBFJ201' -> J201; 'J201/MMBFJ201' -> J201; '2N5088BU' -> 2N5088."""
    p = pn.upper()
    pieces = [x for x in re.split(r"\s+OR\s+|/|\(", p) if re.search(r"[A-Z0-9]", x)]
    p = pieces[0] if pieces else ""  # "2N5088 OR 2N5089", "J201/MMBFJ201", "J201(IDSS>Q1)", "(J201)": the first name
    p = re.sub(r"^[^A-Z0-9]+|[^A-Z0-9]+$", "", p.strip()).replace(" ", "")  # "*2N3904", "(J201)"
    if not p:
        return []
    out = [p]
    if "-" in p:
        out.append(p.split("-")[0])
    m = re.match(r"^MMBF(J?\d{3,4}[A-Z]?)$", p)  # SMD twins of the J and 2N JFETs
    if m:
        out += [m.group(1), "2N" + m.group(1)] if not m.group(1).startswith("J") else [m.group(1)]
    # Package suffixes (2N5088BU, BC549CTA, 2N3904G): peel trailing letters one at a time.
    q = p
    while re.search(r"[0-9][A-Z]{1,4}$", q):
        q = q[:-1]
        out.append(q)
    return list(dict.fromkeys(out))


_PREFERRED = re.compile(r"^(2N|2SC|2SA|2SK|2SJ|BC|BF|MPS|MPSA|PN|KSP|KSC|KSA|J\d|MPF|BS|AC|OC|NKT|GT|SFT)")
_CORE_STRIP = re.compile(r"^(?:FMMT|MMBT|MMBF|CMST|CMKT|KMBT|KST|DST|SMMBT|PMBT|PMBF|LBC|BCW|BCX|BCV|CSC|CSA|KTC|KTA|KTD|GES|MPQ|SS|KSP|KSC|KSA|PN|2N|2SC|2SA|2SK|2SJ|BC|MPSA|MPS|J)")


def _core(pn: str) -> str:
    """The die a part number names, ignoring maker prefix and package suffix: 2N5088, MMBT5088
    and KST5088G share core 5088; BC549C and BC549CTA share 549C; 2SC1815-GR keeps its GR group."""
    p = pn.upper()
    p = re.sub(r"-(GR|BL|Y|O|R|Q|P|L|K)$", r"\1", p)  # a gain group written after a dash
    m = re.search(r"(\d{3,5})([A-Z]{0,2})", p)  # the die number, wherever the maker's prefix leaves it
    if not m:
        return p
    digits, letters = m.group(1), m.group(2)
    family = p[:m.start()]
    gain = letters if (family.startswith(("BC", "LBC", "2SC", "2SA", "2SK", "CSC", "CSA", "KTC", "KTA")) and letters in ("A", "B", "C", "GR", "BL", "Y", "O", "R")) else ""
    return digits + gain


def _digits(pn: str) -> str:
    m = re.search(r"\d{3,5}", pn.upper())
    return m.group(0) if m else pn.upper()


def lookup(conn: sqlite3.Connection, pn: str) -> dict | None:
    for cand in _candidates(pn):
        row = conn.execute("SELECT * FROM specs WHERE partnum = ? COLLATE NOCASE", (cand,)).fetchone()
        if row:
            cols = [c[1] for c in conn.execute("PRAGMA table_info(specs)")]
            return dict(zip(cols, row))
    return None


def _ratio(a: float | None, b: float | None) -> float | None:
    if not a or not b or a <= 0 or b <= 0:
        return None
    return math.log(a / b)


def substitutes(conn: sqlite3.Connection, spec: dict, popularity: dict[str, int], limit: int = 8) -> dict[str, list[dict]]:
    """Parts of the same kind, material and polarity or channel, within a sensible
    class (not a power device for a small-signal one), ranked by closeness of gain,
    voltage, power and speed, with a bonus for parts other boards in the library use."""
    cols = [c[1] for c in conn.execute("PRAGMA table_info(specs)")]
    kind = spec["kind"]
    if kind == "bjt":
        rows = conn.execute("SELECT * FROM specs WHERE kind='bjt' AND mat IS ? AND pol IS ? AND partnum <> ?", (spec["mat"], spec["pol"], spec["partnum"])).fetchall()
    else:
        rows = conn.execute("SELECT * FROM specs WHERE kind=? AND ch IS ? AND partnum <> ?", (kind, spec["ch"], spec["partnum"])).fetchall()
    scored = []
    for r in rows:
        c = dict(zip(cols, r))
        if kind == "bjt":
            if not c.get("hfe") or not c.get("vce"):
                continue
            if c["vce"] < 0.75 * (spec.get("vce") or 0) or (spec.get("ic") and c.get("ic") and not 0.5 <= c["ic"] / spec["ic"] <= 25) \
                    or (spec.get("pc") and c.get("pc") and not 0.5 <= c["pc"] / spec["pc"] <= 25):
                continue
            d = 3.0 * abs(_ratio(c["hfe"], spec.get("hfe")) or 0) + 0.5 * abs(_ratio(c["vce"], spec.get("vce")) or 0) \
                + 0.5 * abs(_ratio(c.get("pc"), spec.get("pc")) or 0) + 0.7 * abs(_ratio(c.get("ft"), spec.get("ft")) or 0)
        else:
            if not c.get("vds"):
                continue
            if c["vds"] < 0.75 * (spec.get("vds") or 0) or (spec.get("pd") and c.get("pd") and not 0.4 <= c["pd"] / spec["pd"] <= 25) \
                    or (spec.get("idmax") and c.get("idmax") and not 0.2 <= c["idmax"] / spec["idmax"] <= 20):
                continue
            d = 2.0 * abs(_ratio(c.get("idmax"), spec.get("idmax")) or 0) + 2.0 * abs(_ratio(c.get("vgs"), spec.get("vgs")) or 0) \
                + 0.5 * abs(_ratio(c["vds"], spec.get("vds")) or 0) + 1.0 * abs(_ratio(c.get("vgsth"), spec.get("vgsth")) or 0) \
                + 0.5 * abs(_ratio(c.get("rds"), spec.get("rds")) or 0)
        pop = popularity.get(c["partnum"].upper(), 0)
        scored.append((d, pop, c))
    # Same die under another maker's prefix or package suffix is not a different substitute:
    # keep one name per core, preferring a through-hole family name and a name the library uses.
    own_digits = _digits(spec["partnum"])
    best: dict[str, tuple] = {}
    for d, pop, c in scored:
        core = _core(c["partnum"])
        if _digits(c["partnum"]) == own_digits:
            continue  # NSVMMBT5088LT3G is a 2N5088 in another package, not a substitute
        rank = (0 if pop else 1, 0 if _PREFERRED.match(c["partnum"]) else 1, len(c["partnum"]), d)
        if core not in best or rank < best[core][0]:
            best[core] = (rank, d, pop, c)
    fields = ("hfe", "vce", "ic", "pc", "ft", "vds", "vgs", "vgsth", "idmax", "pd", "rds")
    def row(d, pop, c):
        return {"pn": c["partnum"], "boards": pop, "score": round(d, 2), **{k: c[k] for k in fields if c.get(k) is not None}}
    used = sorted((v for v in best.values() if v[2]), key=lambda v: (v[1], -v[2]))
    rest = [v for v in best.values() if not v[2]]
    familiar = [v for v in rest if _PREFERRED.match(v[3]["partnum"])]  # through-hole family names a builder can buy
    closest = sorted(familiar if len(familiar) >= 3 else rest, key=lambda v: (v[1], v[3]["partnum"]))
    return {"used": [row(d, pop, c) for _, d, pop, c in used[:limit]],
            "closest": [row(d, pop, c) for _, d, pop, c in closest[:limit]]}
