# Changelog

All notable changes to Akashic. The section for a tagged version becomes the
GitHub Release notes.

## Unreleased

### Added
- Mask Audio Electronics (Shopify; Word build documents read straight from the .docx tables,
  no converter needed; the freebie bundle is split into its four boards).
- `TODO.md`: a running list of documents that parse wrong or thin, per vendor.

### Fixed
- Resistor values with a lowercase `r` suffix (`100r`) and capacitor values followed by a
  dielectric word (`100p Silver Mica`) now normalize; `Ge`/`Si` are accepted as diode and
  transistor values.

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
