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
  tables and schematic images); `normalize.py` value normalization and part categories;
  `taxonomy.py` the effect categories and enclosure sizes; `db.py` SQLite plus the vendor
  registry (name, URL, licence note, kind); `export.py` the JSON bundle and exchange rates.
- `app/` — SvelteKit static PWA (Svelte 5 runes, adapter-static, every page prerendered).
  `src/lib/search.ts` filters and the MiniSearch index; `Faceplate.svelte` the signature
  glyph; `currency.svelte.ts` the price selector; `types.ts` vendor names and kinds.
- `data/` — `library.sqlite`, `raw/` (cached vendor responses and PDFs) and `cache/`
  (renders and OCR text), all git-ignored; `archive/` is committed and holds the
  documentation of closed stores.

## Commands

```sh
cd scraper && .venv/bin/pcblib scrape <vendor> [--only slug] [--limit N] [--reset] [--refresh]
.venv/bin/pcblib stats && .venv/bin/pcblib export        # never --images for a public deploy
cd app && npm run check && npm run build && npm run preview   # restart preview after each build
npm run deploy                                             # export, build, wrangler deploy
```

Scrapes are cached, so re-running a vendor after a parser change costs no network. Several
vendors can run in parallel (WAL mode). The preview server caches its file list at startup,
so restart it after rebuilding.

## Conventions

- Cache locally, link publicly: vendor PDFs and schematic images never enter the export.
  Metadata, part values and links do. `data/archive/` is the one exception, for stores that
  have closed.
- Every parser change: re-run the affected vendors from cache and compare `pcblib stats`
  before and after. The three table parsers all run and the one with the most designators
  wins, so a new layout should not regress an old one.
- Adapters return `None` for products that are not circuits (kits, parts, faceplates,
  bundles) and dedupe regional or older-version listings of the same board.
- New vendor: adapter, `vendors/__init__.py`, `db.py`, `app/src/lib/types.ts`, README table,
  CHANGELOG line. Vendor kinds: `shop` (buy the PCB), `projects` (order at a fab), `blog`
  (read the post), `archive` (open the schematic).
- OCR is best effort and marked `OCR` or `from schematic` in the row notes; never let it
  overwrite a row that came from a text table.
- Commit only when asked. American spelling in the app.
