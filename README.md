<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="app/static/wordmark-dark.png"><img src="app/static/wordmark.png" width="372" alt="Akashic: Guitar Effects PCB Lookup"></picture></p>


A searchable reference library of DIY guitar-pedal circuits, built from the build documents that PCB vendors publish. For every board it records what commercial pedal it is based on, the vendor and price with a link to buy the PCB, the build document, the controls and enclosure, and a fully parsed parts list with normalized values. Because every vendor's parts list lands in one database, the library can answer questions no vendor site can: every Rat derivative, every circuit that uses an LM308, every three-knob 125B board.

It ships as a static, offline-capable web app (PWA) that installs on macOS, Linux, Android and iOS.

**Live:** https://akashic.cryptideffects.com

## Sources

| Vendor | Circuits | Parts list | Notes |
|---|---|---|---|
| PedalPCB | ~540 | parsed from the build-doc PDF | current and legacy doc layouts |
| Aion FX | ~270 | parsed from the build-doc PDF | controls and difficulty from the doc |
| Fuzz Dog | ~600 | parsed from the build-doc PDF | kit pages carry the docs; the parts table is found on whichever page holds it; prices in GBP |
| Madbean Pedals | ~120 | parsed from the build-doc PDF | single projects table, archived rows kept; controls from the doc's Controls section |
| GuitarPCB | ~148 | OCR'd from the build-doc PDF (needs `tesseract`) | schematic and BOM are raster images in the PDF; a thorough OCR pass (upscaled, thresholded) runs when the quick one is thin; ~92% of boards parse, pots named from the table |
| Sheepylove | ~70 | parsed from the build-doc PDF | Shopify catalog via `products.json`; KiCad-exported docs; prices in EUR |
| Dead End FX | ~125 | schematic labels + OCR'd table | Big Cartel catalog; build docs on Google Drive; R/C/D/Q/IC read exactly from the vector schematic, pots and switches from OCR |
| Moonn Electronics | ~170 | parsed from the build-doc PDF | Big Cartel catalog; build docs on Dropbox; Qty/Value/Parts tables; prices in EUR |
| Five Cats Pedals | ~125 | KiCad interactive BOM (exact), else OCR of the insert | WooCommerce Store API; the ibom zip on each product gives every designator; older boards without one get their typeset insert table OCR'd; the insert's enclosure badge is OCR'd too; prices in GBP |
| Parasit Studio | ~33 | parsed from the build-doc PDF | shop is a JS widget, so circuits come from the static /pedals/ pages; no prices |
| PCB Guitar Mania | ~250 | parsed from the build-doc PDF | WooCommerce Store API; docs state the original, enclosure and difficulty; regional and gerber-only duplicates collapse onto the board; prices in EUR; circuit pages carry a quality caution |
| Dead Astronaut FX | ~19 | OCR'd from raster build docs | Wix site; pages named from the nav menu; PayPal prices in GBP |
| Bent Fishbowl | ~40 | OCR'd from the schematic image | Wix blog of original and derivative schematics (CC BY-NC-SA); no board to buy; designators and values paired by position |
| General Guitar Gadgets | ~77 | parsed from the project BOM PDF | Shopify store; per-version PDFs on the project pages; the BOM title gives the board's name and original; prices in USD |
| Lectric-FX | ~40 | parsed from the build-doc PDF, a linked Google Sheet, or grid OCR of scanned docs | WooCommerce Store API; multi-column B.O.M. with pots, trimmers and switches; three boards keep their parts list in a Google Sheet, read from its xlsx export; older scanned docs have their ruled table read cell by cell; prices in USD |
| Experimentalists Anonymous | ~780 | positional OCR of the drawing where legible | a plain file archive of traced schematics in category folders; no board to buy; MIDI, power-supply, synth-book and misc folders skipped |
| Zero G IOD | 16 | OCR'd from BOM and schematic images | closed Big Cartel store; every product image (BOM, drill guide, schematic) is committed under `data/archive/zerogiod/` for posterity |
| On The Road Effects | ~28 | parsed from the build-guide PDF | one WordPress page; boards sell on Etsy and Reverb; prices in USD |
| Dirt Monger Instruments | ~15 | OCR'd from the build doc's parts image | Shopify collection; build docs on Google Drive; prices in CAD |
| Mask Audio Electronics | ~26 | parsed from the Word build doc's table | Shopify collection; docs are .docx on Dropbox and Google Docs, read directly; one Eagle-schematic PDF paired by label; prices in USD |
| Effects Layouts | ~80 | parsed from the build-doc PDF | WooCommerce Store API; two-column BOM with named pots; the doc's drill template names the enclosure; prices in USD |
| JMK PCBs | ~39 | parsed from the build-doc PDF | WooCommerce with the REST API off, so products come from the sitemap and each page's JSON-LD; multi-column parts tables; prices in USD |
| Electronic Audio Experiments | 4 | spreadsheet BOM (exact), else the builder's guide | Squarespace DIY collection of retired EAE pedals; LaTeX-set guides name the controls; prices in USD |
| C2C Electronics | 15 | build document (Comment / Description / Designator / Qty tables; older docs list quantities only) | WooCommerce store; all-tube high-voltage preamps and pedals, docs on the site or Google Drive; prices in USD |
| Dead Air Studios | 5 | Google Doc build guide (one part per paragraph) or Google Sheet | Big Cartel shop; only the DIY PCB products are circuits; prices in USD |
| RWL Pedals | 41 | README markdown parts table, else the KiCad interactive BOM | GitHub repository of KiCad layouts with gerbers (CC BY-NC-SA); every board fits a 125B; no prices |
| Sheepylove on GitHub | 12 | CSV parts list where one exists; pot names read off the board render | Sheepylove's layouts for dylan159 designs with gerbers (CC BY-NC-SA); nine are not in the shop |
| Other Pedals | 10 | OCR of the value-first parts-list image (two columns), or the Name / Designator export table in a PDF | Squarespace shop; documents are JPEG images bundled into one cached PDF per board; prices in USD |
| God City Instruments | 24 | build guide (text table; older guides put each cell on its own line) | Shopify; Kurt Ballou's boards, guides on kurtballou.com; prices in USD |
| 1776 Effects | 17 | build document (text table, named pots) | Shopify; prices in USD |
| Rullywow Industries | 26 | build document (text table) | WooCommerce; originals named in the product titles; prices in USD |
| MAS Effects | 6 | PDFs and a CSV on mas-effects.com and GitHub; schematic images paired by OCR | Shopify DIY collection, mostly kits; only the circuit PCBs are listed; prices in USD |
| Tonepad | 55 | parts list on the layout page ('R1, R2 – 1M' or 'qty - value' per section) | Classic ASP catalog; layouts served only with the project page as referer; prices in USD |
| WRAA Labs | 4 | inline list in the build guide's page text ('R1 = 1k') | Big Cartel; lo-fi digital kits; prices in GBP |
| Frog Pedals | 5 | none: documentation is sent to buyers | WooCommerce behind a browser-agent check; listing only; prices in USD |
| TH Custom Effects | 22 | HTML build documentation with a Ref / Qty / Value / Notes table (linked from the shop table and product pages) | WooCommerce; prices in EUR |
| Guitar-Electronics.eu | 66 | short PDF: placement list ('R1 1M') and a bill of materials by value ('330R 1pcs. "R3"') | Polish Shoper store; boards named after the originals; prices in EUR |
| OP Electronics | 39 | datasheet PDF with a Qty / Value / Parts / Description list (two side by side for a two-circuit board become builds); zipped document sets are opened | Italian PrestaShop store; prices in EUR |
| Griffin Effects | 27 | project PDF with a three-column parts list; the schematic page is read for pot names | PrestaShop 1.6; every board 'compares to' a named original; prices in USD |
| Coda Effects | 6 | Google Drive build document (Name / Value columns; the Dolmen Fuzz has six Big Muff builds) | WooCommerce shop; documents linked from the old Blogger product pages; prices in EUR |
| delyk PCBs | 41 | '<Name>-BOM.pdf' from the WordPress media library (P/N / Value / Notes per section), matched to products by name | WooCommerce; based-on, difficulty and enclosure are product attributes; prices in USD |
| Tayda Electronics (DHEA) | 68 | Instruction Center 'Designators and components' page ('C1 47n' plus the Tayda part) with named pots and switches | taydakits.com; the store is behind Cloudflare, so no prices; buy link is the PCB's store page |
| Schalltechnik_04 | 10 | 'Required Parts' page: quantity / type shortcode tables per section (no designators) | kits discontinued in 2022, instructions still online; listed as read-the-post |
| Electric Druid | 4 | construction guide PDF (Order / Ref / Description / Value / Quantity table) | WooCommerce; Tom Wiltshire's stompbox boards; prices in GBP |
| Zeppelin Design Labs | 1 | assembly-instructions PDF (kit bill of materials with designators in the notes column) | Shopify; the Quaverato harmonic tremolo kit; prices in USD |
| Moody Sounds | 121 | kit instruction PDFs: Moody's own packing lists ('R1, R7 = 4k7') read by OCR because the text layer is shattered; BYOC checklists ('2 - 1k', '3 - A100k (VOLUME, ...)') from the text | Swedish WooCommerce kit shop; own, BJFE, Carlin, Vallhagen and Lehle-clone kits, resold BYOC kits and an archive of discontinued kits kept for their documentation; prices in SEK |
| Gigahearts FX | 5 | the build doc's parts table where the product links one (GIG BUFF v1.3); otherwise the schematic image on the product page, paired by OCR (GIG BUFF v2.0) | UK Shopify shop; the PCB collection only (the rest of the store is finished pedals); build docs for the other boards come with the board; prices in GBP |
| PCBWay: Glory to Ukraine | ~337 | none (BOM needs a PCBWay login) | one member's shared projects via the member JSONP list; schematic PNGs are CC BY-SA; no prices |

### Transistor substitutes

Every transistor a parts list names gets a substitutes section on its part page, drawn from
a transistor parameter database (a MySQL dump of about 150,000 parts with material, polarity
or channel, gain, voltage, current, power and frequency limits). Candidates share the
material and polarity or channel, sit in the same class (a power device is never offered
for a small-signal one), and are ranked by closeness of gain, voltage, power and speed.
Two tiers are shown: parts other boards in the library use, then the closest by the
numbers. The database has no package or pinout data, and the page says so.

```sh
cd scraper && .venv/bin/pcblib import-transistors ../transistor-dump   # once; builds data/transistors.sqlite
.venv/bin/pcblib export                                                # writes app/static/data/subs.json
```

The dump and the SQLite file stay out of git (`transistor-dump/`, `data/transistors.sqlite`);
the export ships only the limits of the few hundred transistors the library names.

### What is indexed and what is not

When a build document gives one value column per version of the circuit, every column is
kept and the circuit page offers a variant selector; counts and the parts cross-reference use
the first column. This covers per-column tables (Effects Layouts), repeated titled blocks
(Mask Audio, PedalPCB's Muffin Fuzz with its eight Big Muff versions) and OCR'd tables with a
piped header (Five Cats).

Names, prices, part values, controls, enclosures and the original circuit are indexed as facts and every record links back to the vendor's product page and build document. Build documents and their schematic images are copyrighted by the vendors: the scraper caches them locally under `data/raw/` and `data/cache/` (git-ignored) for personal reference, and the public export does not include them. Aion FX explicitly permits commercial use of its projects; GuitarPCB and Fuzz Dog explicitly forbid republishing their documents. The redistributable schematic is the optional KiCad fragment you draw yourself (see below).

## Layout

```
scraper/   Python package `pcblib`: vendor adapters, PDF parsing, SQLite, JSON export
app/       SvelteKit static PWA: search, facets, circuit pages, parts cross-reference
data/      library.sqlite plus raw/cache directories (all git-ignored)
```

## Building the data

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), poppler (`brew install poppler` for `pdftotext`), and tesseract (`brew install tesseract`) for the image-only parts lists of GuitarPCB and Dead End FX. On macOS the OCR passes also use Apple's Vision text recognizer, which reads thin and small type that tesseract garbles: `pcblib/vision_ocr/main.swift` is compiled with `swiftc` (Xcode command-line tools) into `data/cache/_bin` on first use. Without it tesseract works alone.

```sh
cd scraper
uv venv .venv && uv pip install -e .
.venv/bin/pcblib scrape pedalpcb      # each vendor: pedalpcb aionfx madbean guitarpcb fuzzdog sheepylove deadendfx moonn fivecats parasit pcbguitarmania deadastronaut bentfishbowl ggg lectricfx expanon zerogiod otrfx dirtmonger pcbway-gtu
.venv/bin/pcblib stats
.venv/bin/pcblib export               # writes app/static/data/*.json
.venv/bin/pcblib export --images      # also bundles cached schematic renders (local use only)
```

`export` also fetches USD exchange rates for EUR, GBP and CAD from the European Central Bank feed (frankfurter.dev) into `rates.json`, so the app can show every vendor's price in one currency; the app defaults to USD and offers EUR, GBP, or the vendor's own listing.

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

## Deploying

The build is static, so any static host works. A Cloudflare setup is included (Workers static assets, which is what Cloudflare Pages became):

```sh
cd app
npx wrangler login      # once; opens the browser
npm run deploy          # export data, build, publish
```

`npm run deploy` runs `scripts/deploy.sh`, which exports the data bundle (never with `--images`), builds the site, and runs `wrangler deploy` with the config in `app/wrangler.toml`. The site is served at `https://pcb-schematic-library.<account>.workers.dev`; add a custom domain in the Cloudflare dashboard under the Worker's settings. `static/_headers` sets long cache lifetimes for the hashed assets and fonts and a short one for the data bundle.

Deploy `app/build` to any other static host the same way.

`infra/cryptid-fx-redirect/` is a two-line Worker that sends the typo domain cryptid-fx.com to www.cryptideffects.com; deploy it from that directory with `npx wrangler deploy`. The search index is built in the browser from `data/index.json`; circuit pages load their own JSON on demand and are cached by the service worker for offline use.

## Data model

`circuits` holds one row per vendor board. `bom` holds one row per parts-list line with `category` (R, C, D, Q, IC, POT, TRIM, SW, LED, OPTO, CONN, HW) and `norm_value`, so `1K5`, `1.5k` and `1k5` all become `1.5k`, and `A100K`, `100KA` and `100k log` all become `A100k`. Categories are mapped to one shared taxonomy in `scraper/pcblib/taxonomy.py`.

## Contributing

Vendor suggestions, wrong-parse reports and fixes are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Security problems go through [private reporting](https://github.com/drlholloway/akashic/security/advisories/new).

## License

[PolyForm Shield 1.0.0](LICENSE): free to use, copy, modify and share, but not to build a competing product. The vendors' documents remain theirs; see the source table above.

## Conclusion

If this helps you out somehow, [buy me a coffee](https://buymeacoffee.com/drlholloway). :)
