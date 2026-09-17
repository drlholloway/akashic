# PCB Schematic Library

A searchable reference library of DIY guitar-pedal circuits, built from the build documents that PCB vendors publish. For every board it records what commercial pedal it is based on, the vendor and price with a link to buy the PCB, the build document, the controls and enclosure, and a fully parsed parts list with normalized values. Because every vendor's parts list lands in one database, the library can answer questions no vendor site can: every Rat derivative, every circuit that uses an LM308, every three-knob 125B board.

It ships as a static, offline-capable web app (PWA) that installs on macOS, Linux, Android and iOS.

## Sources

| Vendor | Circuits | Parts list | Notes |
|---|---|---|---|
| PedalPCB | ~540 | parsed from the build-doc PDF | current and legacy doc layouts |
| Aion FX | ~270 | parsed from the build-doc PDF | controls and difficulty from the doc |
| Fuzz Dog | ~600 | parsed from the build-doc PDF | kit pages carry the docs; prices in GBP |
| Madbean Pedals | ~120 | parsed from the build-doc PDF | single projects table, archived rows kept |
| GuitarPCB | ~160 | OCR'd from the build-doc PDF (needs `tesseract`) | schematic and BOM are raster images in the PDF; ~85% of real boards parse |
| Sheepy Love | ~70 | parsed from the build-doc PDF | Shopify catalog via `products.json`; KiCad-exported docs; prices in EUR |
| Dead End FX | ~125 | schematic labels + OCR'd table | Big Cartel catalog; build docs on Google Drive; R/C/D/Q/IC read exactly from the vector schematic, pots and switches from OCR |
| Moonn Electronics | ~170 | parsed from the build-doc PDF | Big Cartel catalog; build docs on Dropbox; Qty/Value/Parts tables; prices in EUR |
| Five Cats Pedals | ~120 | KiCad interactive BOM (exact) | WooCommerce Store API; the ibom zip on each product gives every designator; inserts are raster and not OCR'd; prices in GBP |
| Parasit Studio | ~33 | parsed from the build-doc PDF | shop is a JS widget, so circuits come from the static /pedals/ pages; no prices |
| PCB Guitar Mania | ~250 | parsed from the build-doc PDF | WooCommerce Store API; docs state the original, enclosure and difficulty; regional and gerber-only duplicates collapse onto the board; prices in EUR |
| Dead Astronaut FX | ~19 | OCR'd from raster build docs | Wix site; pages named from the nav menu; PayPal prices in GBP |
| Bent Fishbowl | ~40 | OCR'd from the schematic image | Wix blog of original and derivative schematics (CC BY-NC-SA); no board to buy; designators and values paired by position |
| PCBWay: Glory to Ukraine | ~337 | none (BOM needs a PCBWay login) | one member's shared projects via the member JSONP list; schematic PNGs are CC BY-SA; no prices |

### What is indexed and what is not

Names, prices, part values, controls, enclosures and the original circuit are indexed as facts and every record links back to the vendor's product page and build document. Build documents and their schematic images are copyrighted by the vendors: the scraper caches them locally under `data/raw/` and `data/cache/` (git-ignored) for personal reference, and the public export does not include them. Aion FX explicitly permits commercial use of its projects; GuitarPCB and Fuzz Dog explicitly forbid republishing their documents. The redistributable schematic is the optional KiCad fragment you draw yourself (see below).

## Layout

```
scraper/   Python package `pcblib`: vendor adapters, PDF parsing, SQLite, JSON export
app/       SvelteKit static PWA: search, facets, circuit pages, parts cross-reference
data/      library.sqlite plus raw/cache directories (all git-ignored)
```

## Building the data

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), poppler (`brew install poppler` for `pdftotext`), and tesseract (`brew install tesseract`) for the image-only parts lists of GuitarPCB and Dead End FX.

```sh
cd scraper
uv venv .venv && uv pip install -e .
.venv/bin/pcblib scrape pedalpcb      # each vendor: pedalpcb aionfx madbean guitarpcb fuzzdog sheepylove deadendfx moonn fivecats parasit pcbguitarmania deadastronaut bentfishbowl pcbway-gtu
.venv/bin/pcblib stats
.venv/bin/pcblib export               # writes app/static/data/*.json
.venv/bin/pcblib export --images      # also bundles cached schematic renders (local use only)
```

`export` also fetches USD exchange rates for EUR and GBP from the European Central Bank feed (frankfurter.dev) into `rates.json`, so the app can show every vendor's price in one currency; the app defaults to USD and offers EUR, GBP, or the vendor's own listing.

Every HTTP response and PDF is cached, so re-running a scrape after a parser change costs no network. Use `--reset` to drop a vendor's rows first, `--only <substring>` and `--limit N` to test on a few products, and `--refresh` to bypass the cache. Requests to each host are spaced 1.5 s apart.

Running all five scrapers in parallel is fine: the database is in WAL mode and each circuit commits on its own.

## Attaching a KiCad schematic

Every circuit has a slot for a hand-drawn KiCad fragment. Attach one and it becomes the circuit page's schematic, rendered with `kicad-cli`, with the `.kicad_sch` offered for download:

```sh
.venv/bin/pcblib attach-kicad pedalpcb:pcb038 ~/kicad/muroidea.kicad_sch
.venv/bin/pcblib export
```

## Running the app

Requires Node 22+.

```sh
cd app
npm install
npm run dev        # development server
npm run build      # static site in app/build (prerenders every circuit and part page)
npm run preview    # serve the build locally
```

Deploy `app/build` to any static host. The search index is built in the browser from `data/index.json`; circuit pages load their own JSON on demand and are cached by the service worker for offline use.

## Data model

`circuits` holds one row per vendor board. `bom` holds one row per parts-list line with `category` (R, C, D, Q, IC, POT, TRIM, SW, LED, OPTO, CONN, HW) and `norm_value`, so `1K5`, `1.5k` and `1k5` all become `1.5k`, and `A100K`, `100KA` and `100k log` all become `A100k`. Categories are mapped to one shared taxonomy in `scraper/pcblib/taxonomy.py`.

## Conclusion

If this helps you out somehow, buy me a coffee. :)
