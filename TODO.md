# TODO: parse gaps and wrong parses

A running list of documents the pipeline reads wrong or not at all, so they can be fixed
later without re-discovering them. Add an entry whenever a scrape leaves a board thin;
remove it when the parser handles the case. Counts come from `pcblib stats` and the query
at the bottom; re-run them after parser changes.

## Whole-vendor gaps

- **PCBWay (Glory to Ukraine)**: no parts lists at all (337 boards). BOM and gerbers sit
  behind a PCBWay login; only name, original and the CC BY-SA schematic image are indexed.
- **Experimentalists Anonymous**: 519 of 770 schematics have no readable designators
  (hand-drawn or low-resolution scans); 158 more have fewer than 8 rows. Positional OCR
  only works on clean traced drawings.
- **Bent Fishbowl**: 8 of 33 schematics come back thin; busy drawings defeat the
  designator/value pairing.
- **GuitarPCB**: 5 boards with no BOM and 7 thin after the thorough OCR pass; the rest
  are selector and wiring boards with no BOM by design (Roto-Tone, 2 Knob Job, 3PDT
  boards, Easy Order Switching). 18 boards still have no named controls.
- **Madbean**: 8 boards with no BOM: the utility boards (9mmBB, 14mm, MiniJack1, sProbe,
  Strober, TrueSoft) and Flunkee, whose PDF link is a 404. The VFE series docs carry a
  shopping list (qty, value, type) rather than a designator table, so their rows are named
  by quantity.
- **Aion FX**: 8 boards without controls; 7 without a BOM.
- **Fuzz Dog**: 4 boards without a BOM and 13 thin, all utility items (switchers, testers,
  the ProtoBuddy breadboard, tails add-ons) whose docs have no parts table.
- **PCB Guitar Mania**: 14 without a BOM; 25 without controls after the schematic pairing (the rest have
  watermarked or hand-drawn schematics).
- **Five Cats Pedals**: 6 without a BOM after OCR of the older inserts: three 3PDT
  daughterboards and the Transelector (no table), and the Vintage Style Fuzz Face, whose
  insert is a wiring diagram with values printed on the parts.
- **PedalPCB**: complete for circuits. The boards without a parts list are utility items whose
  docs have none (drill templates, the current-meter kit, the test platform, the ProtoBoard).
- **Electronic Audio Experiments**: complete (4 boards); the guides' Qty / Value / Ref tables
  and the spreadsheet BOMs both read in full.
- **C2C Electronics**: complete for parts (16 boards). Ten older docs list quantities without
  designators, so their rows are named by quantity; the schematic pairing names the knobs on
  eight of them (Bassdude and Mirage keep a knob count: OCR reads fewer names than knobs).

- **Tayda (DHEA)**: nine SMD boards come pre-populated, so their component page lists only
  the pot and switches; prices come from the store's category listing, which has no stock
  state, and Amp Eleven and Super Six Stevie are no longer listed there, so they have none.
- **OP Electronics**: three older datasheets (MOSFET Booster, LPB Booster, Distortion+) are
  rotated layout drawings whose text extracts as fragments and whose OCR finds no table;
  the Tap Tempo board and Octaverb have no document. Zip and rar document sets are read
  with bsdtar; the .ods BOMs inside go through the spreadsheet reader.
- **Griffin Effects**: five boards announced as coming soon have no project file and are
  skipped; the SCH-1 Chorus reads from its interactive BOM instead of a project PDF.
  Schematic pages are found by their 'N. Schematic:' heading, but the drawings name pots
  RVn, so controls stay knob counts.
- **delyk PCBs**: six boards have no BOM in the media library (Fussy Valve 809, Lightning
  Bolt, TranqDrive, LB-Fuzz, Buzz Box, Conductor's Hand); named trimpots (DEPTH, RATE) are
  read from their 'Trimpot' note.
- **Schalltechnik_04**: parts pages are quantity / type tables without designators, so rows
  are quantity-named; controls come from the pots named in the intro prose.
- **Guitar-Electronics.eu**: the PDFs name pots only on the wiring drawing (values under the
  pot, names on the next line), so controls stay knob counts; boards are named after their
  originals, so based-on is a slug map.
- **Moody Sounds**: the text layer of Moody's own PDFs is shattered into one-letter lines, so
  their packing lists are OCR'd from the first four pages (psm 6); OCR digit slips (R9 read as
  RQ) lose a row here and there. Kits with no PDF (Moodytron, Hypnodrone, Strange Devil Echo,
  Octafuzz) are listing-only. BYOC checklists have no designators, so those rows are
  quantity-named. The 'PCB' category the issue pointed at is PCB-mount potentiometers.
- **Das Musikding** (issue #6): its own kits are mostly other indexed vendors' boards
  (Griffin, Parasit, TH Custom, GCI, Schalltechnik) and every documentation link on
  musikding.de returns the shop home page (404 behind a 200), so nothing to parse.
- **Sushi Box FX** (issue #6): the shop sells finished pedals only; the DIY tube boards moved
  to C2C Electronics, which is indexed. **ToneHeroPCB**: one out-of-stock board, no document.
  **ElectroSmash** and **Carcharias Effects**: the domains no longer resolve.
  **EffectPedalKits**: the site times out (502).

## Specific boards

| Vendor | Board | Problem |
|---|---|---|
| On The Road Effects | Guerrero Oro | The build-guide link is a 'Build Guide Coming Soon' placeholder; nothing to parse until the guide is published |
| Dead Astronaut | Chasm Reverb, Ebe Delay, Timestream Reverb | Raster docs where thorough OCR still returns nothing |
| Five Cats | Marshall Supa Fuzz, Vintage Style Fuzz Face | Insert is a wiring diagram with values on the parts, not a table; 1 and 0 rows |
| GuitarPCB | G.B.O.F. (16-project fuzz board), NostalgiTone Dual Combo Creator | No parts table: the doc lists sixteen projects to build on one board and points to DIY Layout Creator drawings |
| Five Cats | Rattus | Read as four column strips: 23 to 26 rows per variant of 35, with slips. The table is thin blue type on a dotted grid that tesseract misreads however it is scaled; macOS Vision reads nearly every row |
| Effects Layouts | Schematic Fuzz | Build doc is drill templates only; the schematic is on the silkscreen |
| Effects Layouts | Lawn Darts | Doc is a single scanned schematic image; the schematic-page search pairs 8 of its 10 labels, no pot name |
| Effects Layouts | Melody Malfunction, Cranky Speaker | Doc has only a shopping list (value, type, quantity), so rows are named by quantity (`×2`) and controls are a knob count |
| Effects Layouts | Six Shooter, Strider, Soil Slinger | Only a drill template or a blog post is linked; no parts list |
| Effects Layouts | Drivestortion | Old blog-era project PDF with a broken font encoding; the aligned OCR gives 23 rows but two pot names come out as 'Cim' and 'Ccim' (the One-Knobber now reads its five-build table in full) |
| Lectric-FX | Double*Take, Betty Boost | Scanned grids read cell by cell, but the Double*Take's diode cells come out as junk (`INS1T4Z`). The scanned, sideways schematics are found and paired now, but OCR reads only a third of their labels, so Betty Boost gets its Tone and not its Level |
| Lectric-FX | Mongrel | Grid OCR reads 45 of 47 parts; C8 and C21 cells are unreadable, R18 reads 1K for 4K7, D1 reads 1N40602 for 1N4002 |
| JMK PCBs | most boards | Docs rarely state an enclosure (8 of 38 found). The drill templates draw only the board and its pots, and the shop's categories carry no size, so there is no source to read one from |
| Five Cats | 57 older inserts | No enclosure stamp on the insert (only newer layouts have the "minimum enclosure" badge) |
| Sheepylove on GitHub | Katahdin, Sarda, Shorn Sheep | No parts list in the repository and the board render's labels do not OCR, so no controls; the schematics are on the Bent Fishbowl blog |
| Frog Pedals | all boards | No build documents are published (Frog sends them to buyers), so the listing carries no parts |
| TH Custom Effects | ROG Umble | Its build-instructions link is a PNG sheet rather than the HTML documentation the other boards have; no parts read from it |
| Tonepad | MXR Noise Gate, Purple Peaker, Tremulus Lune, DOD 250, Ross Phaser | No file on the project page, or (Ross Phaser) a layout whose values sit only in the drawing. Image-only layouts with a parts box (EA Tremolo, Rebote 3, Speaker Simulator) are OCR'd now |
| WRAA Labs | Retroflect, Inkcap II | The Retroflect guide has no parts list; the Inkcap page's description is cut before its pots, so no controls |
| Madbean | Flunkee | Doc link returns 404 (`_folders/1590A/pdf/Flunkee.pdf`) |
| transistor subs | 2N6027, 2N2646 | A PUT and a UJT, which the database lists without parameters, so no substitutes. OC139, 1T308A and CV7351 are anchored to listed equivalents (ASY29, GT308A, 2N1308). Placeholders like `NPN`, `GE`, `your choice` are skipped on purpose |

## Parser wishes

- Schematic pairing now runs for every board whose parts list is thin, quantity-only or
  names no controls (`enrich.py`): vector text first, then OCR at two resolutions, three
  orientations and two segmentation modes. A scanned document with no schematic heading is
  searched page by page for the one that pairs the most labels. It reads clean KiCad and
  Altium exports; hand-drawn or watermarked schematics and boards whose pots are
  designators (VR1) still get nothing from it, and scanned Eagle schematics (Lectric-FX) give
  up only a third of their labels.
- OCR of a parts table now also runs with the word gaps preserved, so the same table parsers
  that read text PDFs read the OCR (per-variant tables, side-by-side Qty / Value / Parts
  lists, Part / Value columns). Tables printed white-on-colour on a PCB render (Five Cats
  wiring diagrams) still defeat tesseract.

## Query

```sh
sqlite3 -header -column data/library.sqlite "select vendor, sum(n=0) as no_bom, sum(n>0 and n<8) as thin, count(*) as total from (select c.vendor, (select count(*) from bom b where b.circuit_id=c.id) as n from circuits c) group by vendor"
```
