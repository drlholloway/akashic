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

## Specific boards

| Vendor | Board | Problem |
|---|---|---|
| Dirt Monger | Multi RAT 1995 | Parts table is an image laid out in a way neither the text parsers nor OCR read; 1 row |
| Dirt Monger | Integrated Preamp | Same; 3 rows |
| On The Road Effects | Guerrero Oro | Same; 0 rows |
| Dead Astronaut | Chasm Reverb, Ebe Delay, Timestream Reverb | Raster docs where thorough OCR still returns nothing |
| Five Cats | Marshall Supa Fuzz, Vintage Style Fuzz Face | Insert is a wiring diagram with values on the parts, not a table; 1 and 0 rows |
| GuitarPCB | G.B.O.F. (16-project fuzz board), NostalgiTone Dual Combo Creator | No parts table: the doc lists sixteen projects to build on one board and points to DIY Layout Creator drawings |
| Five Cats | Rattus | Read as four column strips: 23 to 26 rows per variant of about 27 |
| Effects Layouts | Schematic Fuzz | Build doc is drill templates only; the schematic is on the silkscreen |
| Effects Layouts | Lawn Darts | Doc is a single scanned schematic image; thorough and positional OCR at 300 dpi both find nothing |
| Effects Layouts | Melody Malfunction, Cranky Speaker | Doc has only a shopping list (value, type, quantity), so rows are named by quantity (`×2`) and controls are a knob count |
| Effects Layouts | Six Shooter, Strider, Soil Slinger | Only a drill template or a blog post is linked; no parts list |
| Effects Layouts | One-Knobber, Drivestortion | Old blog-era project PDFs with broken font encodings; OCR gives 13 and 18 rows, pots missing |
| Lectric-FX | Double*Take, Betty Boost | Scanned grids read cell by cell, but the Double*Take's diode cells come out as junk (`INS1T4Z`) and Betty Boost's pot cells read as noise (`LEGKB`, `56EKC`), so no controls |
| Lectric-FX | Mongrel | Grid OCR reads 45 of 47 parts; C8 and C21 cells are unreadable, R18 reads 1K for 4K7, D1 reads 1N40602 for 1N4002 |
| JMK PCBs | most boards | Docs rarely state an enclosure (8 of 38 found). The drill templates draw only the board and its pots, and the shop's categories carry no size, so there is no source to read one from |
| JMK PCBs | AC/DC Drive | The DC / AC and Standard / Bass builds are side tables in the build notes (`Part DC AC`), not row notes, so no variant selector yet |
| Five Cats | 57 older inserts | No enclosure stamp on the insert (only newer layouts have the "minimum enclosure" badge) |
| Madbean | Flunkee | Doc link returns 404 (`_folders/1590A/pdf/Flunkee.pdf`) |
| transistor subs | BS250, 2SK30A, 2N6027, OC139, LND150, CV7351, 1T308A, 2N2646 | Named in parts lists but absent from the transistor parameter database, so no substitutes; placeholders like `NPN`, `GE`, `your choice` are skipped on purpose |

## Parser wishes

- Schematic pairing now runs for every board whose parts list is thin, quantity-only or
  names no controls (`enrich.py`): vector text first, then OCR at two resolutions and three
  orientations. It reads clean KiCad and Altium exports; hand-drawn or watermarked
  schematics and boards whose pots are designators (VR1) still get nothing from it.

## Query

```sh
sqlite3 -header -column data/library.sqlite "select vendor, sum(n=0) as no_bom, sum(n>0 and n<8) as thin, count(*) as total from (select c.vendor, (select count(*) from bom b where b.circuit_id=c.id) as n from circuits c) group by vendor"
```
