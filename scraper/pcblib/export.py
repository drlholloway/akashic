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
        vendors = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM vendors")}
        circuits = [_row(r) for r in conn.execute("SELECT * FROM circuits ORDER BY vendor, name")]
        for c in circuits:
            bom = [dict(b) for b in conn.execute(
                "SELECT ref,value,part_type,notes,category,norm_value,sort_key FROM bom "
                "WHERE circuit_id=? ORDER BY position", (c["id"],))]
            c["bom"] = bom
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
    (EXPORT_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False))
    (EXPORT_DIR / "parts.json").write_text(json.dumps(parts_out, ensure_ascii=False))
    (EXPORT_DIR / "vendors.json").write_text(json.dumps(vendors, ensure_ascii=False))
    print(f"exported {len(index)} circuits, {len(parts_out)} indexed part values -> {EXPORT_DIR}")
