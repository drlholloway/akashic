# Changelog

All notable changes to Akashic. The section for a tagged version becomes the
GitHub Release notes.

## Unreleased

### Added
- Apple Vision OCR beside tesseract on macOS (`pcblib/vision.py`, a small Swift helper compiled
  on first use). It reads thin, small and coloured type that tesseract garbles, and joins every
  thorough OCR pass, the column-strip reader for per-variant tables and schematic label pairing.
  A page tesseract reads thin but Vision reads well gets the thorough passes. Five Cats' Rattus
  (blue type on a dotted grid) reads 128 rows across its four RATs, where it read 103 with slips;
  327 boards gained rows in all (GuitarPCB's NostalgiTone docs, Dead End FX, Bent Fishbowl,
  Lectric-FX, Dead Astronaut), and OCR slips such as TLC2274, 9V1 and 2SC1815-GR now read right.
- Column tables read strip by strip are cut just before the next column's header, not halfway,
  since headers sit at the left of their columns; a run of values whose designators OCR lost
  (R1-R5 before R6) is numbered when the count fits the gap exactly.
- OCR'd pot names: capacitor types and pot makers (Tantalum, Piher) and words in a sentence are
  no longer read as knob names, and one knob spelled two ways by two engines (Output and
  Qutput) is listed once. A Title-case name with a taper after the value (Suppressor 500KA) counts.
- Ten sources from GitHub issue #6: Guitar-Electronics.eu, OP Electronics, Griffin Effects,
  Coda Effects, delyk PCBs, Tayda Electronics (DHEA's Instruction Center pages), Schalltechnik_04
  (discontinued kits whose instructions stay online), Electric Druid, Zeppelin Design Labs and
  Moody Sounds (kits in SEK, including the BYOC kits it still sells and its archive of
  discontinued kits). Tayda prices come from the store's category listing.
- Pot values with a dashed taper ('10K-A', '2M-B') or a taper word ('500K REV LOG', '10K Lin')
  now normalize for every vendor; the column parser reads 'RVn' designators.
- OCR pass for image-only parts tables: tesseract runs with the word gaps preserved and the
  text-table parsers read the result, so per-variant tables (Effects Layouts One-Knobber, five
  builds), side-by-side Qty / Value / Parts lists (Dirt Monger) and Tonepad's image layouts
  parse. Scanned documents with no schematic heading are searched for their schematic page
  and paired (Lectric-FX, Effects Layouts Lawn Darts); OCR word boxes are cached. 363 boards
  gained rows, 245 of them Experimentalists Anonymous schematics.
- Mask Audio Electronics (Shopify; Word build documents read straight from the .docx tables,
  no converter needed; the freebie bundle is split into its four boards).
- `TODO.md`: a running list of documents that parse wrong or thin, per vendor.
- Effects Layouts (WooCommerce Store API; two-column build docs) and JMK PCBs (sitemap plus
  JSON-LD product pages; multi-column parts tables).

- A per-vendor caution shown on circuit pages next to the buy link; set for PCB Guitar Mania,
  whose board quality builders widely report as inconsistent.

- Build variants: a parts table with one value column per version (Effects Layouts' Crempog
  1977 / 2003 and Horde Howler's eight Tube Screamer specs, Mask Audio's Big Clang blocks, Five
  Cats' Rattus RAT / RAT2 / Turbo / You Dirty columns, PedalPCB's Muffin Fuzz with eight Big Muff
  versions side by side) keeps every column, and the circuit page gets a variant selector.
  Counts and the parts cross-reference use the first variant. Headers may start with a
  part-type word and repeat per side-by-side group (the Damnation Audio Parallel Drive's
  Guitar Mod / Bass Mod table, Effects Layouts' Light Land), or be the label group alone
  repeated per part type (PCB Guitar Mania's Germanium Percolator Stock / Albini and Universal
  Revolution II / III / IV).
- Controls are deduplicated when a board is stored; a pot listed twice was two knobs before.
- Named pots on vector schematics (DRIVE next to 500kA) are paired like designators.
- Effects Layouts products that link a build-doc web page are followed to the PDF that page
  links (Black & Tan, Transmogrifying Repeater).

- Transistor substitutes on part pages: material, polarity or channel and the key limits from a
  transistor parameter database, ranked by closeness; parts other boards in the library use are
  listed first, then the closest by the numbers. `pcblib import-transistors` loads the database.

- Footer: a "Something wrong?" section linking the GitHub issue forms, and a colophon naming
  Cryptid Effects with a link to the main site and the source. Each circuit page has a
  "Report a wrong parse" link that opens the issue form with that page filled in.

- Fuzz Dog builds: a doc with a BOM page per version (the Big Muff docs, PIG and BELLS, the
  four Fuzz Face builds) yields one variant per page named from the page title, and a table
  whose parenthesized values make a second named build (Southern Drive / 186,282Mps) splits
  in two. Parenthesized alternates are kept as notes; pot names one space from their value
  are read.

- Electronic Audio Experiments (Squarespace DIY collection; spreadsheet BOMs read by column
  name, controls from the builder's guide).

- C2C Electronics (Conspiracy to Commit Electronics): WooCommerce Store API, build documents
  read from wrapped Comment / Description / Designator / Quantity tables; quantity-only lists
  become ×n shopping-list rows with a knob count.

- Schematic pairing for every vendor (`enrich.py`): a board whose parts list is thin,
  quantity-only or names no controls gets its pot and switch names, and if need be its
  designators, from the schematic page: vector text first, then OCR at two resolutions and
  three orientations. Named pots replace knob counts when the schematic names them all.

- Variant notes become variants: a parts-list note such as "Omitted in Nano version",
  "B1M for High Gain version" or "220n in Bass Fuzz variant" now yields per-build rows and
  a variant selector on the page. Notes phrased as mods keep a Standard build; notes
  phrased as builds name the builds themselves.

- Side charts in build notes become variants: a small "Part | DC | AC" or "Part | Standard |
  Bass" table gives the parts it names one row per build, with the builds as the cross product
  of the charts (JMK's AC/DC Drive: DC, AC, DC Bass, AC Bass). A Standard column adds nothing
  to a build's name; "none" omits the part and "jumper" keeps it as one.

- Dead Air Studios (Big Cartel; Google Doc build guides with one part per paragraph, a
  Google Sheet keyed on PART #).

- A shipping caution on Moonn Electronics: a one-person shop that can be slow to ship but
  does ship everything.

- RWL Pedals: a GitHub repository of KiCad layouts with gerbers, the first source of the new
  `repo` kind ("Get the gerbers at"). Parts from the README tables, else the interactive BOM.

- Sheepylove on GitHub: twelve layouts of dylan159 designs with gerbers, nine of them not in
  the Sheepylove shop.

- Other Pedals (Other* DIY): parts lists are images read by OCR in two columns; the two PDF
  build docs use an EasyEDA-style Name / Designator / Footprint / Quantity table, which the
  shared parsers now read for every vendor.

- Eight sources at once: God City Instruments, 1776 Effects, Rullywow Industries, MAS Effects,
  Tonepad, WRAA Labs, Frog Pedals and TH Custom Effects. Frog publishes no build documents, so
  it is listing-only; TH Custom's shop table links HTML build documentation per board.
- Shared parsers learned three layouts on the way: Word tables exported one cell per line, a
  table that continues onto the next page without its header, and a grouped
  Designator / Qty / Name export; spreadsheet readers accept a Name column as the value.

### Fixed
- Dirt Monger Integrated Preamp: its two-column 'value - refs' parts list ('100K - R7, R20',
  'C50K anti log - Treble, Bass') is read from the text layer: 47 rows with the three pots named,
  where OCR had read 11 wrong ones.
- Transistor substitutes: a part the database knows only by a longer maker's spelling (BS250 as
  BS250P, 2SK30A as 2SK30ATM, LND150 as LND150K1) is now found, so those boards get substitutes. Three parts the database
  lacks are anchored to a listed equivalent and say so on the page: CV7351 to the 2N1308 (its
  commercial number), 1T308A to the GT308A (its Latin spelling), OC139 to the ASY29.
- JMK PCBs: the seven boards whose notes describe the original without naming it now name
  it (Fuzz Factory, Xotic AC/RC Booster, Darkglass B3K, EA Tremolo, Ampeg Scrambler, Phase 90,
  Jon Patton's Blue Warbler); descriptions no longer start with the tab's HTML attributes.
- OCR designators with a stray digit (R111 for R11, C141 for C14) are renamed at upsert when
  the number sits far outside the board's range and one dropped digit lands on an unused
  designator inside it; the note keeps what was read. 28 boards had one.
- The column parser reads no notes, so when it wins over the table parser the matching
  rows' notes are carried across (Super Stevie's variant notes were lost this way).
- Prose words that OCR paired with a nearby value ("Install", "Shown", "Such") no longer
  appear as controls; pot values on schematics need a taper suffix (A2 was a pin).
- OCR'd parts lists keep pots whose name ends in a digit (SEN1, SEN2) and switch rows
  (SW1 SPDT ON-ON, BYPASS 3PDT); Dead End FX's 'Zilla names its four knobs and its toggle.
- Lectric-FX boards whose parts list lives in a Google Sheet (Countdown Phaser, Disdis,
  Dandy Horse) read it from the workbook's xlsx export: every tab, designator and value per
  row, pots and trimmers and switches named. Adds openpyxl to the scraper.
- An original's name is stored without the adjectives a description wraps it in ("rare Last
  Gasp Arts Green Monster", "old version of the Caroline Wave Cannon") or a trailing clause.
- The price currency selector moved from the header to the results bar beside Sort.
- Parts lists laid out as PART / QTY / TYPE / NOTES with no designators (Aion FX's 18V
  voltage doubler, whose values are printed on the PCB) are read as quantity-named rows; a
  designator in the value column takes its value from the notes (LEDR, "recommended value is
  4.7k").
- Designator ranges (`Q1-Q5  2N5088`, `R5-R8  47k`) expand to one row per part whichever table
  parser wins; 24 Sheepylove and Aion FX boards had them stored as a single "other" part.
- OCR'd tables with one column per variant (Five Cats' Rattus) are also read as vertical
  strips cut between the header words, so a noisy line can no longer drop a column; a stray
  digit before a 1N diode number is removed.
- Controls: a knob named two ways by two sources (Vol and Volume) keeps the longer name;
  PedalPCB's bold list no longer contributes changelog lines or footswitch labels; version
  blocks read Title-case pots written one space from their value (OmniMuff's Vol, Tone, Sus).
- The 1590BBM enclosure is recognized (Mask Audio's Business Card).
- Scanned parts tables drawn as a ruled grid (Lectric-FX's Mongrel) are read cell by cell:
  the rules give the cell boundaries, each cell is OCR'd on its own, and an unreadable
  designator is inferred from its column's sequence. The Mongrel went from 3 junk rows to 45
  of 47 parts. Value repairs learned a serifed 1 read as T, a 7 read as / or i, and
  upper-case capacitor units (2U2).
- Pot values read by OCR keep their taper letter and have only the digits repaired
  (`ASOOK` -> `A500K`, `BSOK` -> `B50K`, `8100K` -> `B100K`): 143 more pot rows across the OCR
  vendors, most on Dead End FX, GuitarPCB and Dead Astronaut, and 16 more boards with named
  controls.
- GuitarPCB parses the build doc rather than the faceplate-art PDF listed beside it, which
  restores the NostalgiTone 60s and 60s Tremolo boards; Fuzz Dog's Astrotone doc link, which
  wraps across a line break on the product page, is fetched.
- PedalPCB: the older `qty  value  ref` three-column parts list (Amentum Boost) parses, and
  faceplate products are no longer indexed as circuits.
- Fuzz Dog: the parts table is read from whichever page holds it (the 2023 doc layout puts
  it a few pages after the schematic) and the circuit's own doc is preferred over the shared
  FuzzPup guide; boards without a parts list fell from 32 to 4, and 451 boards now name their
  knobs instead of counting them.
- Madbean's VFE docs carry a shopping list (qty, value, type) instead of a designator table;
  the shopping-list parser now reads the column order from the header, so 16 more boards
  have parts and the VFE "Level (100kA): ..." control lines are read too.
- Madbean controls come from the doc's "Controls" section (bulleted or plain `NAME: what it
  does` lines, trimmers and switches filtered out) or from the named pots in the parts table:
  101 of 120 boards, up from none. The parts table is no longer cut at column 66, which
  hid the pots and semiconductors columns: 18% more rows. Legacy Aion FX docs without a
  USAGE section take their controls from the parts table: 261 of 270 boards, up from 215.
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
