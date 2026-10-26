# Akashic

A searchable reference library of DIY guitar-pedal circuits built from the build documents
that PCB vendors publish, plus schematic-only sources (a blog, an archive, a PCBWay member).
Every circuit has: what it is based on, the vendor and price with a buy link, the build
document, controls and enclosure, and a parsed, value-normalized parts list. Live at
https://akashic.cryptideffects.com.

Read `README.md` for the commands and the source table, `PRODUCT.md` for the product
decisions and `DESIGN.md` for the visual system. `CHANGELOG.md` becomes the release notes.

## Layout

- `scraper/` — Python package `pcblib` (uv, Python 3.12). `vendors/` holds one adapter per
  source; `pdf.py` the shared parsers (text tables, column layouts, Qty/Value/Parts tables,
  KiCad interactive BOMs via `ibom.py`, vector schematic label pairing, OCR of scanned
  tables and schematic images, cell-by-cell OCR of ruled grids; `vision.py` adds Apple Vision
  as a second OCR engine on macOS, beside tesseract; `gsheet.py` reads a
  parts list kept in a Google Sheet); `normalize.py` value normalization and part categories;
  `taxonomy.py` the effect categories and enclosure sizes; `db.py` SQLite plus the vendor
  registry (name, URL, licence note, kind); `export.py` the JSON bundle and exchange rates.
- `app/` — SvelteKit static PWA (Svelte 5 runes, adapter-static, every page prerendered).
  `src/lib/search.ts` filters and the MiniSearch index; `Faceplate.svelte` the signature
  glyph; `currency.svelte.ts` the price selector; `types.ts` vendor names and kinds.
- `data/` — `library.sqlite`, `raw/` (cached vendor responses and PDFs), `cache/`
  (renders and OCR text) and `transistors.sqlite` (the transistor parameter database, built
  by `pcblib import-transistors` from the MySQL dump in `transistor-dump/`), all git-ignored;
  `archive/` is committed and holds the documentation of closed stores. `transistors.py`
  holds the import, the tolerant part-number lookup and the substitute scoring.

## Commands

```sh
cd scraper && .venv/bin/pcblib scrape <vendor> [--only substring] [--limit N] [--reset] [--refresh-pages|--refresh]
.venv/bin/pcblib stats && .venv/bin/pcblib audit          # audit: flags added since the last run
.venv/bin/pcblib export                                  # never --images for a public deploy
cd app && npm run check && npm run build && npm run preview   # restart preview after each build
npm run deploy                                             # export, build, wrangler deploy
scripts/refresh.sh                                         # weekly: refresh pages, rebuild graph, audit, deploy if clean
```

Scrapes are cached, so re-running a vendor after a parser change costs no network. Several
vendors can run in parallel (WAL mode). The preview server caches its file list at startup,
so restart it after rebuilding.

## Look boards up in the graph

To answer questions about the library's contents (what a board is based on, which boards
copy a pedal, which use a part), query the graph instead of reading the database or the
JSON export. The `akashic-graph` MCP server (graphify, `.mcp.json`) serves
`graphify-out/graph.json`; rebuild it after a scrape with
`~/.local/share/uv/tools/graphifyy/bin/python scripts/graphify_export.py` (about 3 s);
`scripts/refresh.sh` rebuilds it every week.

- Nodes: boards ("<Vendor> <name>"), vendors, originals (what boards are based on, with
  spelling variants merged) and parts (ICs, transistors, diodes by normalized value).
- `get_node`: a board's facts in `attributes` (akashic_id, vendor, based_on, effect, price,
  status, url); `get_neighbors` on an original lists every board based on it, on a part
  every board using it. `query_graph` is fuzzy keyword search; keep `token_budget` small.
- Shell equivalents: `graphify explain "<label>"`, `graphify query "<q>" --budget 800`.

The graph is a read-only view; the database stays the source of truth.

## Conventions

- Cache locally, link publicly: vendor PDFs and schematic images never enter the export.
  Metadata, part values and links do. `data/archive/` is the one exception, for stores that
  have closed.
- Every parser change: re-run the affected vendors from cache and compare `pcblib stats`
  before and after, then run `pcblib audit` and read the flags it says were added before
  deploying. The table parsers in `pdf.text_bom` all run and the one with the most rows wins (a
  per-variant table takes over when it covers most of the refs), so a new layout should not
  regress an old one. Hand fixes for one-off misreads go in
  `scraper/pcblib/corrections.py`.
- Boards are never deleted when a vendor stops listing them: a full scrape marks them `delisted`
  (with the date) and the site says so. `--refresh-pages` re-fetches listings and product pages but
  keeps cached documents; a scrape that finds far fewer boards than before marks nothing.
  `--reset` only drops boards still listed that the run did not store (the adapter now skips or
  renames them), after a full run with no errors; it never touches delisted boards and refuses
  `--only`/`--limit`. A plain rescrape is enough to check a parser change.
- Adapters return `None` for products that are not circuits (kits, parts, faceplates,
  bundles) and dedupe regional or older-version listings of the same board.
- New vendor: adapter, `vendors/__init__.py`, `db.py`, `app/src/lib/types.ts`, README table,
  CHANGELOG line. Vendor kinds: `shop` (buy the PCB), `projects` (order at a fab), `repo` (download the
  gerbers from a code repository), `blog` (read the post), `archive` (open the schematic), `kit` (a complete kit), `layout` (build from a vero, perfboard,
  tagboard or turret drawing; `vendors/blogger.py` is the shared base, `layouts.py` reads the legend).
  `VENDOR_KIND` is kept in both `db.py` and `types.ts`; update both.
  A layout the same vendor publishes beside its PCB is attached to that circuit (`layout.also`), not a second entry.
- OCR is best effort and marked `OCR` or `from schematic` in the row notes; never let it
  overwrite a row that came from a text table.
- Commit only when asked. American spelling in the app.
