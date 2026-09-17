# Contributing to Akashic

Thanks for your interest. This is a small project maintained by one person, so the most
useful contributions are focused ones: a vendor that should be indexed, a board whose
parts list came out wrong, a fix with a before-and-after count, or a wiki correction.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Suggest a vendor.** Use the *Vendor request* issue form with the shop URL and a link to
  one build document. Stores, project hosts and schematic archives are all welcome.
- **Report a wrong parse.** Use the *Wrong parts list* form. The circuit's URL in the
  library plus what the vendor's document actually says is usually all that is needed.
- **Report a bug** in the site itself with the *Bug report* form.
- **Suggest a feature** with the *Feature request* form.

## Development setup

The scraper is Python 3.12 managed with [uv](https://docs.astral.sh/uv/); the site is
SvelteKit on Node 22. Poppler (`pdftotext`) and tesseract are needed for the document
parsing. See the README for the full commands.

```sh
cd scraper && uv venv .venv && uv pip install -e . && .venv/bin/pcblib vendors
cd ../app && npm install && npm run check
```

## Adding a vendor

Every source is one adapter in `scraper/pcblib/vendors/`. Copy the closest existing one:

- WooCommerce stores: `fivecats.py`, `pcbguitarmania.py`, `lectricfx.py` (Store API listing)
- Shopify: `sheepylove.py`, `ggg.py` (`products.json`)
- Big Cartel: `deadendfx.py`, `moonn.py`, `zerogiod.py` (`products.json`)
- Wix: `deadastronaut.py`, `bentfishbowl.py`
- Static pages or archives: `madbean.py`, `parasit.py`, `expanon.py`

An adapter yields targets from `list_targets()` and returns a `Circuit` from `parse()`.
Reuse the shared parsers in `pcblib/pdf.py` (`process_document` for text PDFs,
`ocr_bom` for scans, `schematic_bom` for vector schematics, `ocr_schematic_bom` for
schematic images) rather than writing new ones. Register the vendor in
`vendors/__init__.py`, `db.py` (name, URL, licence note, kind), `app/src/lib/types.ts`
and the README table.

Test on one product first, then the whole vendor:

```sh
.venv/bin/pcblib scrape <vendor> --only <slug> --limit 1
.venv/bin/pcblib scrape <vendor> --reset
.venv/bin/pcblib stats
```

## What a pull request needs

- The vendor's stats line (circuits, with BOM, with schematic) in the description, before
  and after if you changed a parser.
- Parser changes checked against at least two other vendors (`pcblib scrape <vendor>
  --reset` runs from cache, so this is quick).
- A line under **Unreleased** in `CHANGELOG.md` if users would notice.
- Nothing that republishes a vendor's documents: metadata, part values and links are
  indexed; PDFs and schematic images stay in the git-ignored cache. The only exception is
  `data/archive/` for stores that have closed.

American spelling in the app and docs, please.
