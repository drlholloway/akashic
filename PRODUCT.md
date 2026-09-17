# Product
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
SvelteKit static PWA (user's choice), data as a prebuilt JSON bundle with client-side search (MiniSearch). Python scraper pipeline under `scraper/` builds `data/library.sqlite` and exports to `app/static/data/`.

## Users
Primary: the owner, a DIY guitar-pedal builder and KiCad user, at the bench or desk while designing, choosing, or building a circuit. Secondary (later): the wider DIY pedal community browsing for what to build next. Personal use is optimized first; the result should stay presentable enough to share.

## Product Purpose
A searchable reference library of guitar-pedal circuits aggregated from DIY PCB vendors (PedalPCB, Aion FX, Madbean, GuitarPCB, Fuzz Dog). For each circuit: what commercial pedal it clones, the vendor, price and buy link, the build document, controls, enclosure, a schematic preview (local only), and a fully parsed, value-normalized bill of materials. Success: any circuit or part can be found in seconds, and the cross-reference "which circuits use part X" answers questions no vendor site can.

## Positioning
The only place that unifies BOMs across vendors with normalized part values, so "every Rat derivative", "everything using an LM308", and "125B three-knob boards" are one query each. Vendors can each only show their own catalog.

## Operating Context
Data is scraped on the owner's machine, cached, and exported as static JSON. Circuit records link out to vendor product pages (purchase) and vendor build-document PDFs. Vendor schematic images are cached locally and are not redistributed publicly; the public build shows metadata, BOM, and links. Each circuit has an optional KiCad schematic fragment slot (owner-drawn), rendered with `kicad-cli`, which is the redistributable schematic. Roughly 1,500 circuits across five vendors; BOMs of 20 to 110 rows.

## Capabilities and Constraints
- One search box leads: it matches circuit names, cloned originals, part values and part numbers, categories, vendors, and enclosures together.
- Drill-downs must exist for: by cloned original, by part, by effect category (plus vendor and enclosure filters).
- Circuit detail: metadata, controls, BOM table with normalized values, schematic preview when available, links to buy and to the build doc.
- Parts cross-reference page: part value or number -> every circuit using it.
- Static output, offline-capable, installable on macOS, Linux, Android, iOS via PWA.
- Prices are vendor list prices in vendor currency (USD or GBP); no live pricing yet.
- GuitarPCB BOMs are raster-only in the source and are empty unless OCR is run.
- Terminology: "circuit" (a vendor PCB project), "based on" (the commercial original), "BOM" (parts list), "ref" (designator).

## Brand Commitments
Name: Akashic, subtitle Guitar Effects PCB Lookup (formerly PCB Schematic Library). No logo yet. Voice: plain, technical, terse.

## Evidence on Hand
Real scraped data in `data/library.sqlite` and `app/static/data/`. No testimonials, no user counts; do not fabricate any.

## Product Principles
- Density over chrome: it should read like a tool or a datasheet, never like a marketing site.
- Never hide the data: full BOMs, full lists, large previews.
- Search first, then drill down; every list is filterable and every filter is a URL.
- Every record links back to its vendor: the vendor gets the sale, the library gets the index.
- Offline and fast: the bundle loads once and everything after is instant.
