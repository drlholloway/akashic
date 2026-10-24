"""Build a graphify graph of the library so Claude can look boards up without reading the database.

Run with graphify's own interpreter (it has networkx and graphify):
  ~/.local/share/uv/tools/graphifyy/bin/python scripts/graphify_export.py

Reads data/library.sqlite read-only and writes graphify-out/graph.json (git-ignored), which the
`akashic-graph` MCP server in .mcp.json serves. Nodes:
  board    one per circuit; its facts (vendor, based on, effect, price, status, URL) are attributes
  vendor   one per source
  original what boards are based on, with spelling variants of the same name merged
  part     ICs, transistors and diodes from the parsed parts lists
Edges: board -sold_by-> vendor, board -based_on-> original, board -uses_part-> part.
Like the export, only metadata, part values and links go in; never documents or schematics.
"""
import collections
import re
import sqlite3
from pathlib import Path

from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.export import to_json

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "library.sqlite"
PART_CATEGORIES = {"IC": "IC", "Q": "transistor", "D": "diode"}
SOURCE = "data/library.sqlite"

# spelling variants that should land on the same original
ALIASES = [
    (r"\belectro[- ]?harmoni[cx]s?\b|\behx\b", "ehx"),
    (r"\bpro ?co( sound)?\b", "proco"),
    (r"\bdallas[- ]arbiter\b", "dallas arbiter"),
    (r"\bsola ?sound\b", "sola sound"),
    (r"\bthe\b", ""),
]


def original_key(text: str) -> str:
    t = text.lower()
    for pattern, repl in ALIASES:
        t = re.sub(pattern, repl, t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def clip(text, n=300):
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def main() -> None:
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    vendors = {r["id"]: r for r in db.execute("select * from vendors")}
    circuits = db.execute("select * from circuits").fetchall()

    parts = collections.defaultdict(set)  # circuit id -> {(category, value)}
    for r in db.execute("select circuit_id, category, norm_value from bom "
                        "where category in ('IC','Q','D') and norm_value != ''"):
        parts[r["circuit_id"]].add((r["category"], r["norm_value"].strip()))

    nodes, edges = [], []
    seen_vendor, originals, seen_part = set(), {}, set()
    labels_by_key = collections.defaultdict(collections.Counter)
    for c in circuits:
        if c["based_on"]:
            labels_by_key[original_key(c["based_on"])][c["based_on"].strip()] += 1

    for c in circuits:
        vid = c["vendor"]
        vname = vendors[vid]["name"] if vid in vendors else vid
        if vid not in seen_vendor:
            seen_vendor.add(vid)
            v = vendors.get(vid)
            nodes.append({"id": f"vendor:{vid}", "label": vname, "file_type": "concept",
                          "source_file": SOURCE, "source_location": None,
                          "attributes": {"type": "vendor", "id": vid,
                                         "url": v["url"] if v else None,
                                         "license_note": clip(v["license_note"] if v else "", 200)}})
        status = "delisted " + c["delisted"] if c["delisted"] else (
            "in stock" if c["in_stock"] == 1 else "out of stock" if c["in_stock"] == 0 else None)
        attrs = {"type": "board", "akashic_id": c["id"], "vendor": vname,
                 "based_on": clip(c["based_on"], 120), "effect": c["effect_type"] or c["category"],
                 "price": f"{c['price']} {c['currency'] or ''}".strip() if c["price"] not in (None, "") else None,
                 "status": status, "url": c["url"] or c["doc_url"],
                 "controls": clip(c["controls"], 120), "description": clip(c["description"], 260)}
        nodes.append({"id": f"board:{c['id']}", "label": f"{vname} {c['name']}", "file_type": "concept",
                      "source_file": SOURCE, "source_location": None,
                      "attributes": {k: v for k, v in attrs.items() if v not in (None, "", [])}})
        edges.append({"source": f"board:{c['id']}", "target": f"vendor:{vid}", "relation": "sold_by",
                      "confidence": "EXTRACTED", "source_file": SOURCE, "source_location": None, "weight": 1.0})
        if c["based_on"]:
            key = original_key(c["based_on"])
            if key and key not in originals:
                label = labels_by_key[key].most_common(1)[0][0]
                originals[key] = f"original:{key.replace(' ', '-')}"
                nodes.append({"id": originals[key], "label": label, "file_type": "concept",
                              "source_file": SOURCE, "source_location": None,
                              "attributes": {"type": "original",
                                             "boards": sum(labels_by_key[key].values()),
                                             "spellings": [s for s, _ in labels_by_key[key].most_common(5)]}})
            if key:
                edges.append({"source": f"board:{c['id']}", "target": originals[key], "relation": "based_on",
                              "confidence": "EXTRACTED", "source_file": SOURCE, "source_location": None,
                              "weight": 1.0})
        for cat, value in sorted(parts.get(c["id"], ())):
            pid = f"part:{cat}:{value.lower()}"
            if pid not in seen_part:
                seen_part.add(pid)
                nodes.append({"id": pid, "label": value, "file_type": "concept", "source_file": SOURCE,
                              "source_location": None,
                              "attributes": {"type": "part", "category": PART_CATEGORIES[cat]}})
            edges.append({"source": f"board:{c['id']}", "target": pid, "relation": "uses_part",
                          "confidence": "EXTRACTED", "source_file": SOURCE, "source_location": None,
                          "weight": 1.0})

    G = build_from_json({"nodes": nodes, "edges": edges, "hyperedges": []}, directed=True, dedup=False)
    communities = cluster(G)
    out = ROOT / "graphify-out" / "graph.json"
    out.parent.mkdir(exist_ok=True)
    to_json(G, communities, str(out), force=True)
    kinds = collections.Counter(n["attributes"]["type"] for n in nodes)
    print(f"graphify: {G.number_of_nodes()} nodes ({dict(kinds)}), {G.number_of_edges()} edges, "
          f"{len(communities)} communities -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
