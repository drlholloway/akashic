"""Export the SQLite library to a static JSON bundle for the web app.

Outputs (in app/static/data/):
  index.json     – one compact record per circuit for the list + search index
  circuits/<id>.json – full record including BOM and description
  parts.json     – part value -> circuit ids (the cross-reference index)
  vendors.json
  images/<vendor>/<slug>.png – schematic previews (only when --include-images)
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict

from . import db as dbm
from .paths import EXPORT_DIR


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in ("tags", "controls", "extra_docs"):
        d[k] = json.loads(d.get(k) or ("{}" if k == "extra_docs" else "[]"))
    d["in_stock"] = None if d["in_stock"] is None else bool(d["in_stock"])
    d["file_id"] = re.sub(r"[^a-z0-9]+", "-", d["id"].lower()).strip("-")
    return d


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
    parts: dict[str, dict] = {}
    with dbm.connect() as conn:
        vendors = {r["id"]: {**dict(r), "kind": dbm.VENDOR_KIND.get(r["id"], "shop"), "warning": dbm.VENDOR_WARNING.get(r["id"], "")}
                   for r in conn.execute("SELECT * FROM vendors")}
        circuits = [_row(r) for r in conn.execute("SELECT * FROM circuits ORDER BY vendor, name")]
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
            actives = sorted({b["norm_value"] for b in bom if b["category"] in ("IC", "Q", "OPTO")})
            index.append({
                "id": c["id"], "file_id": c["file_id"], "vendor": c["vendor"], "name": c["name"],
                "subtitle": c["subtitle"], "based_on": c["based_on"], "category": c["category"],
                "effect_type": c["effect_type"], "enclosure": c["enclosure"], "difficulty": c["difficulty"],
                "price": c["price"], "currency": c["currency"], "in_stock": c["in_stock"],
                "url": c["url"], "doc_url": c["doc_url"], "image_url": c["image_url"],
                "controls": c["controls"], "tags": c["tags"], "actives": actives,
                "bom_count": len(bom), "has_schematic": has_schematic,
                "has_kicad": bool(c.get("kicad_path")),
            })
            for b in bom:
                if b["category"] in ("R", "C", "HW", "CONN", "OTHER", ""):
                    continue  # passives are too common to be a useful cross-reference
                key = f"{b['category']}:{b['norm_value']}"
                p = parts.setdefault(key, {"key": key, "category": b["category"],
                                           "value": b["norm_value"], "circuits": set(),
                                           "types": set()})
                p["circuits"].add(c["id"])
                if b["part_type"]:
                    p["types"].add(b["part_type"])
            if images and c.get("schematic_local"):
                src = DATA_DIR / c["schematic_local"]
                if src.exists():
                    dst = img_dir / f"{c['file_id']}.png"
                    if not dst.exists():
                        shutil.copyfile(src, dst)
                    c["schematic_image"] = f"schematics/{c['file_id']}.png"
            c.pop("doc_local", None)
            c.pop("schematic_local", None)
            c["has_schematic"] = has_schematic
            (EXPORT_DIR / "circuits" / f"{c['file_id']}.json").write_text(json.dumps(c, ensure_ascii=False))
    parts_out = sorted(
        ({**p, "circuits": sorted(p["circuits"]), "types": sorted(p["types"])[:5],
          "count": len(p["circuits"]),
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
    (EXPORT_DIR / "subs.json").write_text(json.dumps(_transistor_subs(conn), ensure_ascii=False))
    (EXPORT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False))
    (EXPORT_DIR / "parts.json").write_text(json.dumps(parts_out, ensure_ascii=False))
    (EXPORT_DIR / "vendors.json").write_text(json.dumps(vendors, ensure_ascii=False))
    write_rates()
    print(f"exported {len(index)} circuits, {len(parts_out)} indexed part values -> {EXPORT_DIR}")


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
