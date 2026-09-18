# Changelog

All notable changes to Akashic. The section for a tagged version becomes the
GitHub Release notes.

## Unreleased

### Added
- Mask Audio Electronics (Shopify; Word build documents read straight from the .docx tables,
  no converter needed; the freebie bundle is split into its four boards).
- `TODO.md`: a running list of documents that parse wrong or thin, per vendor.
- Effects Layouts (WooCommerce Store API; two-column build docs) and JMK PCBs (sitemap plus
  JSON-LD product pages; multi-column parts tables).

- A per-vendor caution shown on circuit pages next to the buy link; set for PCB Guitar Mania,
  whose board quality builders widely report as inconsistent.

### Fixed
- Older Five Cats inserts without an interactive BOM now get their typeset parts table
  OCR'd (11 more boards with a list); GuitarPCB escalates to the thorough OCR pass when the
  quick one is thin (12 more boards, and 121 of 148 now have named controls); component
  packs sold by GuitarPCB are no longer indexed as circuits.
- OCR repairs: a leading 7 that makes a non-E24 value is a misread 1 (`700uF` -> `100uF`),
  1N-series diodes are rebuilt from look-alike letters (`iNg14` -> `1N914`), and impossible
  designators (`R0`, `C412`) are dropped.
- Add-on boards (daughterboards, clipping selectors) classify as Utility before any effect
  word, so a "rotary clipping daughterboard" is no longer a rotary-speaker effect; a packing
  list mentioning a bypass board no longer makes a fuzz a utility; `Fuzz`-prefixed names,
  Bosstone and Acapulco Gold clones classify.
- Five Cats enclosures: newer inserts stamp "minimum enclosure" as a graphic, so page one is
  OCR'd for the size (with the B this font turns into 6 or 8 repaired); 69 of 126 boards now
  carry one, up from 27.
- Resistor values with a lowercase `r` suffix (`100r`) and capacitor values followed by a
  dielectric word (`100p Silver Mica`) now normalize; `Ge`/`Si` are accepted as diode and
  transistor values.
- Column-layout parts tables: pot names no longer bleed into a preceding `100nF`, comma
  lists of designators (`D1, D2, D5  3mm LED`) expand, lowercase taper units and
  dual-gang suffixes parse, named trimmers without a taper (`BIAS  10K`) are kept, and
  `Version 1.1` in a title block becomes the doc version.
- Docs that give only a shopping list (value, suggested type, quantity) now yield a parts
  list with rows named by quantity, as a last resort when no designator table exists.

## 0.1.0 — 2026-09-17

Initial public release.

### Added
- Scraper with adapters for eighteen sources: PedalPCB, Aion FX, Madbean, GuitarPCB,
  Fuzz Dog, Sheepylove, Dead End FX, Moonn Electronics, Five Cats Pedals, Parasit Studio,
  PCB Guitar Mania, Dead Astronaut FX, General Guitar Gadgets, Lectric-FX, Zero G IOD, the
  Bent Fishbowl schematic blog, the Experimentalists Anonymous schematic archive and one
  PCBWay member's shared projects: 3,824 circuits.
- Parts lists parsed from text build documents in three table layouts, from KiCad
  interactive BOM exports, from vector schematic labels, and by OCR from scanned tables and
  schematic images, with values normalized so `1K5`, `1.5k` and `1k5` match.
- Static SvelteKit PWA: one search box with facets by vendor, category, enclosure, knob
  count, original circuit and part; circuit pages with a faceplate glyph drawn from the
  real controls, the grouped BOM and links to buy and to the build document; a parts
  cross-reference; an originals index; prices selectable in USD, EUR or GBP.
- A slot per circuit for an owner-drawn KiCad fragment (`pcblib attach-kicad`).
- Cloudflare deploy (`npm run deploy`).
