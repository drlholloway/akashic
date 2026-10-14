"""Export the SQLite library to a static JSON bundle for the web app.

Outputs (in app/static/data/):
  index.json     – one compact record per circuit for the list + search index
  circuits/<id>.json – full record including BOM and description; read while prerendering each circuit
                       page, never deployed (static/.assetsignore)
  sets/<nnn>.json – the same records in 512 bundles (set_of), which the app fetches when it moves to a
                    circuit page: one file per circuit would pass the host's 20,000-file limit
  parts.json     – part value -> circuit ids (the cross-reference index)
  needs.json     – what each board takes (alternatives and how many), for 'What can I build'
  vendors.json
  images/<vendor>/<slug>.png – schematic previews (only when --include-images)
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from collections import defaultdict
from datetime import date, timedelta

from . import db as dbm
from .corrections import UNCERTAIN
from .datasheets import SHEET_ONLY, all_sheets, is_selector, table as datasheet_table
from .originals import COVERS, harmonize, key as original_key, learn_brands, original
from .normalize import catalog_category, catalog_keys, ic_name, zener_choices, zener_of_part
from .paths import EXPORT_DIR, owner_schematic

SETS = 512


def set_of(file_id: str) -> str:
    """The bundle a circuit's record is in: FNV-1a of its id, as setOf in app/src/lib/data.ts computes it."""
    h = 0x811C9DC5
    for b in file_id.encode():
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return f"{h % SETS:03x}"


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("tags", "controls", "extra_docs"):
        d[k] = json.loads(d.get(k) or ("{}" if k == "extra_docs" else "[]"))
    d["in_stock"] = None if d["in_stock"] is None else bool(d["in_stock"])
    d["layout"] = json.loads(d.get("layout") or "{}")
    d["file_id"] = re.sub(r"[^a-z0-9]+", "-", d["id"].lower()).strip("-")
    return d


def _build_fields(layout: dict) -> dict:
    """How a circuit is built, for the list and its filter: nothing for a plain PCB (the common case, so
    the index stays small), else every way it can be built, first its own ('vero'; 'pcb' then 'vero' for
    a board whose vendor also publishes a stripboard layout), with the board size and whether the
    source marks the layout as verified by a build."""
    if not layout:
        return {}
    builds = list(dict.fromkeys([layout.get("build") or "pcb"] + [a["build"] for a in layout.get("also", [])]))
    out: dict = {"builds": builds}
    if layout.get("board"):
        out["board"] = layout["board"]
    if "verified" in layout:
        out["verified"] = layout["verified"]
    return out


def write_rates() -> None:
    """Bundle USD-based exchange rates (ECB via frankfurter.app) so the app can show
    every vendor's price in one currency offline. Keeps the previous file if offline."""
    import httpx
    out = EXPORT_DIR / "rates.json"
    try:
        r = httpx.get("https://api.frankfurter.dev/v1/latest", params={"base": "USD", "symbols": "GBP,EUR,CAD,SEK"},
                      timeout=15, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
        out.write_text(json.dumps({"base": "USD", "date": data["date"], "rates": {"USD": 1.0, **data["rates"]}}))
        print(f"rates as of {data['date']}: {data['rates']}")
    except Exception as exc:  # noqa: BLE001
        if out.exists():
            print(f"rates fetch failed ({exc}); keeping previous rates.json")
        else:
            out.write_text(json.dumps({"base": "USD", "date": None, "rates": {"USD": 1.0}}))
            print(f"rates fetch failed ({exc}); prices will show in vendor currency")


def write_changes() -> None:
    """The commit history grouped by week (Monday to Sunday), newest first, for the changelog page:
    each change is its commit subject and the first paragraph of its message. Merge commits are left
    out (their changes are already listed), and so are the co-author and session trailer lines."""
    repo = EXPORT_DIR.parents[2]
    try:
        out = subprocess.run(["git", "-C", str(repo), "log", "--no-merges", "--date=short", "--format=%H%x1f%ad%x1f%s%x1f%b%x1e"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return  # no git here: keep whatever changes.json the last export wrote
    weeks: dict[str, list[dict]] = defaultdict(list)
    for rec in out.split("\x1e"):
        f = rec.strip("\n").split("\x1f")
        if len(f) < 4:
            continue
        sha, day, subject, body = f
        detail = "\n".join(ln for ln in body.strip().split("\n\n")[0].splitlines()
                           if not re.match(r"^(?:Co-Authored-By|Claude-Session|Signed-off-by):", ln, re.I)).strip()
        d = date.fromisoformat(day)
        monday = (d - timedelta(days=d.weekday())).isoformat()
        weeks[monday].append({"sha": sha[:7], "date": day, "subject": subject.strip(), "detail": re.sub(r"\s*\n\s*", " ", detail)})
    changes = [{"week": w, "items": weeks[w]} for w in sorted(weeks, reverse=True)]
    (EXPORT_DIR / "changes.json").write_text(json.dumps(changes, ensure_ascii=False))


_MAKER_WORDS = re.compile(r"\b(?:fx|effects?|electronics|studios?|instruments|pedals|audio|devices|the|diy|layouts?|pcbs?)\b")


def _maker_key(name: str) -> str:
    """'Dead Astronaut FX Tremshifter' and 'DeadAstronaut Tremshifter' alike: a maker and model with the
    words a maker's name may or may not carry left out."""
    return re.sub(r"[^a-z0-9]+", "", _MAKER_WORDS.sub("", name.lower()))


# What may follow a part number and still name the same part: a package, grade or temperature code
# ('TL072' + 'CP', 'BC549' + 'C', '2SC1815' + '-GR', 'ATTINY85' + '-20PU'). A digit straight after is
# another part (2N508 + 8), and the few codes below change what the part is or how it is fitted.
_SUFFIX = re.compile(r"-?[A-Z][A-Z0-9.-]{0,7}|-\d[A-Z0-9.-]{0,6}")
_NOT_SUFFIX = {"UB", "RETROFIT", "SMD", "-2-PART"}
_NO_SUFFIX = {"7660"}  # the 7660S takes a higher supply (normalize.ic_name keeps them apart)


def _same_part(parts: list[dict]) -> list[tuple[str, str]]:
    """Pairs of catalog keys, (plain, fuller), that are one part written two ways: 'BC549' and 'BC549C',
    '78L05' and '78L05ACZ', and an op amp filed under its bare number with a maker's spelling of it
    ('4558' and 'NE4558N'). Two fuller spellings are not paired with each other: a BC549B is no BC549C."""
    pairs: list[tuple[str, str]] = []
    for cat in ("IC", "Q", "D", "OPTO"):
        values = {p["value"] for p in parts if p["category"] == cat}
        for v in values:
            for n in range(4, len(v)):
                if v[:n] in values and v[:n] not in _NO_SUFFIX and v[n:] not in _NOT_SUFFIX and _SUFFIX.fullmatch(v[n:]):
                    pairs.append((f"{cat}:{v[:n]}", f"{cat}:{v}"))
            if "-" in v and (plain := v.replace("-", "")) in values:
                pairs.append((f"{cat}:{plain}", f"{cat}:{v}"))  # '2SK30A-GR' and '2SK30AGR'
            if cat == "IC" and (m := re.fullmatch(r"[A-Z]{1,4}(\d{3,5})[A-Z]{0,4}", v)) and m.group(1) in values:
                pairs.append((f"IC:{m.group(1)}", f"IC:{v}"))
    return sorted(set(pairs))


def _row_qty(ref: str) -> int:
    """How many parts a row stands for: '×3' on a layout's legend, 'Q1, Q2' or 'D1-D4' on a table, else one."""
    if m := re.fullmatch(r"[×x]\s?(\d{1,2})", ref.strip()):
        return int(m.group(1))
    n = 0
    for piece in re.split(r"[,;&]|\band\b", ref):
        m = re.fullmatch(r"\s*([A-Za-z]{1,4})(\d{1,3})\s*[-–]\s*(?:\1)?(\d{1,3})\s*", piece)
        n += max(1, int(m.group(3)) - int(m.group(2)) + 1) if m and int(m.group(3)) - int(m.group(2)) < 16 else 1 if piece.strip() else 0
    return max(1, n)


def run(images: bool = False) -> None:
    """images=True also copies cached schematic PNGs into the bundle (local use only)."""
    import shutil
    from .paths import DATA_DIR
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = EXPORT_DIR / "schematics"
    if images:
        img_dir.mkdir(exist_ok=True)
    (EXPORT_DIR / "circuits").mkdir(exist_ok=True)
    index = []
    pending: list[dict] = []
    parts: dict[str, dict] = {}
    needs: dict[str, tuple[dict, int]] = {}
    with dbm.connect() as conn:
        vendors = {r["id"]: {**dict(r), "kind": dbm.VENDOR_KIND.get(r["id"], "shop"), "warning": dbm.VENDOR_WARNING.get(r["id"], "")}
                   for r in conn.execute("SELECT * FROM vendors")}
        circuits = [_row(r) for r in conn.execute("SELECT * FROM circuits ORDER BY vendor, name")]
        # The layout sites label each post with its maker: makers no fixed brand list knows ('One Control', 'VFE').
        learn_brands([(c["name"], c["tags"]) for c in circuits if vendors[c["vendor"]]["kind"] == "layout"])
        settled = harmonize([original(c["based_on"]) for c in circuits] + [n for names in COVERS.values() for n in names])
        # A maker's own board that other sources name as their original ('DeadAstronaut Tremshifter' on a layout
        # site, the Tremshifter here): it is that original, and the layouts and clones list beside it.
        own_names = {_maker_key(n): n for n in set(settled.values()) if n}
        for c in circuits:
            bom = [dict(b) for b in conn.execute(
                "SELECT ref,value,part_type,notes,category,norm_value,sort_key,variant FROM bom "
                "WHERE circuit_id=? ORDER BY position", (c["id"],))]
            c["bom"] = bom
            variants = list(dict.fromkeys(b["variant"] for b in bom if b["variant"]))
            c["variants"] = variants
            # Counts and the cross-reference use the first variant only, so a four-column table is not four boards.
            bom = [b for b in bom if not b["variant"] or b["variant"] == (variants[0] if variants else "")]
            has_schematic = bool(c.get("schematic_local"))
            # active-part signature for search: ICs, transistors, diodes, opto
            actives = sorted({b["norm_value"] for b in bom if b["category"] in ("IC", "Q", "OPTO")}
                             | {ic_name(b["norm_value"]) for b in bom if b["category"] == "IC" and b["norm_value"]})  # '072' also finds TL072
            o = original(c["based_on"])  # one name per original: 'EHX Big Muff' and 'Big Muff Pi' alike
            c["original"] = settled.get(o, o)
            if not c["original"] and (mine := own_names.get(_maker_key(f'{vendors[c["vendor"]]["name"]} {c["name"]}'))):
                c["original"], c["own_design"] = mine, True
            # a board its vendor says builds two originals is listed under each
            covers = COVERS.get(original_key(c["based_on"])) or COVERS.get(original_key(o))
            if covers:
                c["originals"] = [settled.get(n, n) for n in covers]
                c["original"] = c["originals"][0]
            index.append({
                "id": c["id"], "file_id": c["file_id"], "vendor": c["vendor"], "name": c["name"],
                "subtitle": c["subtitle"], "based_on": c["based_on"], "original": c["original"], "category": c["category"],
                "effect_type": c["effect_type"], "enclosure": c["enclosure"], "difficulty": c["difficulty"],
                "price": c["price"], "currency": c["currency"], "in_stock": c["in_stock"],
                "delisted": c.get("delisted") or "", "last_listed": c.get("last_listed") or "",
                "url": c["url"], "doc_url": c["doc_url"], "image_url": c["image_url"],
                "controls": c["controls"], "tags": c["tags"], "actives": actives,
                "bom_count": len(bom), "has_schematic": has_schematic,
                "has_kicad": bool(c.get("kicad_path")),
                **_build_fields(c["layout"]),
                **({"originals": c["originals"]} if c.get("originals") else {}),
                **({"own_design": True} if c.get("own_design") else {}),
            })
            counted = {id(b) for b in bom}
            need: dict[tuple[str, ...], int] = {}  # what the board takes: each row's alternatives, and how many of them
            unread = 0
            for b in c["bom"]:
                if b["category"] in ("R", "C", "LED", "HW", "CONN", "OTHER", ""):
                    continue  # passives and indicator LEDs are too common to be a useful cross-reference
                row_keys = [f"{catalog_category(b['category'], val)}:{val}" for val in catalog_keys(b["category"], b["norm_value"] or b["value"])]
                if id(b) in counted:
                    if row_keys:
                        need[tuple(row_keys)] = need.get(tuple(row_keys), 0) + _row_qty(b["ref"])
                    else:
                        unread += 1  # a row that names no part the catalog knows ('see notes', 'your choice')
                for key in row_keys:
                    cat, val = key.split(":", 1)
                    b.setdefault("xref", []).append(key)  # becomes [value, part page] once the pages are named
                    if id(b) not in counted:
                        continue  # a later variant's row links to the part but is not another board using it
                    p = parts.setdefault(key, {"key": key, "category": cat,
                                               "value": val, "circuits": set(),
                                               "types": {}})
                    p["circuits"].add(c["id"])
                    if b["part_type"] and not re.search(r"\b(?:qty|quantity|value|description|designator)\b", b["part_type"], re.I):
                        p["types"][b["part_type"]] = p["types"].get(b["part_type"], 0) + 1
            if need:
                needs[c["id"]] = (need, unread)
            if images and c.get("schematic_local"):
                src = DATA_DIR / c["schematic_local"]
                if src.exists():
                    dst = img_dir / f"{c['file_id']}.png"
                    if not dst.exists():
                        shutil.copyfile(src, dst)
                    c["schematic_image"] = f"schematics/{c['file_id']}.png"
            if c["vendor"] in dbm.OWNER_VENDORS:  # the site owner's own work: schematic and photo are shown
                svg = owner_schematic(c["vendor"], c["slug"])
                if svg.exists():
                    (EXPORT_DIR / "owner").mkdir(exist_ok=True)
                    shutil.copyfile(svg, EXPORT_DIR / "owner" / f"{c['file_id']}.svg")
                    c["owner_schematic"] = f"owner/{c['file_id']}.svg"
                c["owner_photo"] = c["image_url"]
            c.pop("doc_local", None)
            c.pop("schematic_local", None)
            c["has_schematic"] = has_schematic
            if c["id"] in UNCERTAIN and any("by eye" in (r.get("notes") or "") for r in c.get("bom", [])):  # a by-eye reading's doubts, shown above the parts list
                c["uncertain"] = UNCERTAIN[c["id"]]
            pending.append(c)  # written once the part pages have their names: each row links to its own
    sheets = datasheet_table()  # manufacturer links only; datasheets themselves are never exported
    descs = _transistor_descs([p["value"] for p in parts.values() if p["category"] == "Q"])
    from .diodes import describe as describe_diode
    diode_descs = {p["value"]: d for p in parts.values() if p["category"] == "D" and (d := describe_diode(p["value"]))}  # kept apart: 'GE' is a diode and a transistor
    from .describe import describe as describe_part
    top_types = {p["key"]: [t for t, _ in sorted(p["types"].items(), key=lambda kv: (-kv[1], kv[0]))] for p in parts.values()}
    parts_out = sorted(
        ({**p, "circuits": sorted(p["circuits"]), "datasheet": sheets.get(p["key"], ""), "selector": is_selector(sheets.get(p["key"], "http")),
          "datasheets": all_sheets(p["value"], sheets.get(p["key"], "")), "types": [t for t, _ in sorted(p["types"].items(), key=lambda kv: (-kv[1], kv[0]))][:5],
          "count": len(p["circuits"]),
          **({"sheet_only": True} if Path(sheets.get(p["key"], "")).stem in SHEET_ONLY else {}),
          **({"zeners": z} if p["category"] == "D" and (z := zener_choices(p["value"])) else {}),
          **({"desc": d} if (d := descs.get(p["value"]) if p["category"] == "Q" else diode_descs.get(p["value"]) if p["category"] == "D" else describe_part(p["category"], p["value"], top_types[p["key"]])) else {}),
          "slug": re.sub(r"[^a-z0-9.]+", "-", p["key"].lower())} for p in parts.values()),
        key=lambda p: (-p["count"], p["key"]))
    # dedupe part slugs (different keys can collapse to one slug)
    seen: dict[str, int] = {}
    for p in parts_out:
        if p["slug"] in seen:
            seen[p["slug"]] += 1
            p["slug"] = f"{p['slug']}-{seen[p['slug']]}"
        else:
            seen[p["slug"]] = 1
    page = {p["key"]: [p["value"], p["slug"]] for p in parts_out}
    sets: dict[str, dict] = defaultdict(dict)
    for c in pending:
        for b in c["bom"]:
            if "xref" in b:
                b["xref"] = [page[k] for k in b["xref"] if k in page]
        (EXPORT_DIR / "circuits" / f"{c['file_id']}.json").write_text(json.dumps(c, ensure_ascii=False))
        sets[set_of(c["file_id"])][c["file_id"]] = c
    shutil.rmtree(EXPORT_DIR / "sets", ignore_errors=True)
    (EXPORT_DIR / "sets").mkdir()
    for name, members in sets.items():
        (EXPORT_DIR / "sets" / f"{name}.json").write_text(json.dumps(members, ensure_ascii=False, separators=(",", ":")))
    # What each board takes, for 'What can I build': parts by their place in parts.json, one entry per
    # distinct requirement as [how many, part, alternative, ...]. 'also' is what owning a part covers
    # besides itself: a 1N4739 is a 9V1 zener, a TL072CP is a TL072 and a TL072 will do for a TL072CP.
    at = {p["key"]: i for i, p in enumerate(parts_out)}
    also: dict[int, set[int]] = defaultdict(set)
    for p in parts_out:
        if p["category"] == "D" and (z := "D:" + zener_of_part(p["value"])) != "D:" and z in at and z != p["key"]:
            also[at[p["key"]]].add(at[z])
    for a, b in _same_part(parts_out):  # the plain part number and its fuller spelling stand in for each other
        also[at[a]].add(at[b])
        also[at[b]].add(at[a])
    (EXPORT_DIR / "needs.json").write_text(json.dumps({
        "also": {i: sorted(v) for i, v in sorted(also.items())},
        "circuits": {cid: {"n": [[n, *(at[k] for k in keys)] for keys, n in need.items()], **({"u": unread} if unread else {})}
                     for cid, (need, unread) in needs.items()},
    }, separators=(",", ":")))
    (EXPORT_DIR / "subs.json").write_text(json.dumps(_transistor_subs(conn), ensure_ascii=False))
    (EXPORT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False))
    (EXPORT_DIR / "parts.json").write_text(json.dumps(parts_out, ensure_ascii=False))
    (EXPORT_DIR / "vendors.json").write_text(json.dumps(vendors, ensure_ascii=False))
    write_rates()
    write_changes()
    # Counts and the export time for the About page, so it stays true after every refresh.
    from datetime import datetime, timezone
    (EXPORT_DIR / "meta.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "circuits": len(index), "sources": len(vendors),
        "parts_rows": sum(c.get("bom_count", 0) for c in index),
        "part_values": len(parts_out),
        "delisted": sum(1 for c in index if c.get("delisted")),
    }))
    print(f"exported {len(index)} circuits, {len(parts_out)} indexed part values -> {EXPORT_DIR}")


def _transistor_descs(values: list[str]) -> dict[str, str]:
    """'Si NPN BJT TO-92 TH' for each transistor part number the database or the package
    rules know (see transistors.describe). Empty when the transistor database is absent."""
    from .transistors import TRANS_DB, describe
    import sqlite3 as _sq
    if not TRANS_DB.exists():
        return {}
    tdb = _sq.connect(TRANS_DB)
    out = {v: d for v in values if (d := describe(tdb, v))}
    tdb.close()
    return out


def _transistor_subs(conn) -> dict:
    """Substitutes for every transistor the parts lists name, from data/transistors.sqlite
    (see `pcblib import-transistors`). Empty when that database is absent."""
    from .paths import DB_PATH
    from .transistors import TRANS_DB, lookup, substitutes
    import sqlite3 as _sq
    if not TRANS_DB.exists():
        return {}
    lib = _sq.connect(DB_PATH)  # the caller's connection may already be closed
    popularity = {r[0].upper(): r[1] for r in lib.execute(
        "SELECT norm_value, COUNT(DISTINCT circuit_id) FROM bom WHERE category='Q' AND norm_value<>'' GROUP BY 1")}
    lib.close()
    tdb = _sq.connect(TRANS_DB)
    if not tdb.execute("SELECT name FROM sqlite_master WHERE name='specs'").fetchone():
        return {}
    out = {}
    for value in sorted(popularity):
        spec = lookup(tdb, value)
        if not spec:
            continue
        subs = substitutes(tdb, spec, popularity)
        fields = ("hfe", "vce", "ic", "pc", "ft", "vds", "vgs", "vgsth", "idmax", "pd", "rds")
        out[value] = {"kind": spec["kind"], "mat": spec.get("mat"), "pol": spec.get("pol"), "ch": spec.get("ch"),
                      "spec": {"pn": spec["partnum"], **{k: spec[k] for k in fields if spec.get(k) is not None}},
                      **({"anchor": spec["anchor"]} if spec.get("anchor") else {}), **subs}
    tdb.close()
    return out
