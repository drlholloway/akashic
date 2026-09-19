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
  boards, Easy Order Switching). 27 boards still have no named controls.
- **Madbean**: 8 boards with no BOM: the utility boards (9mmBB, 14mm, MiniJack1, sProbe,
  Strober, TrueSoft) and Flunkee, whose PDF link is a 404. The VFE series docs carry a
  shopping list (qty, value, type) rather than a designator table, so their rows are named
  by quantity.
- **Aion FX**: 9 boards without controls; 7 without a BOM.
- **Fuzz Dog**: 4 boards without a BOM and 13 thin, all utility items (switchers, testers,
  the ProtoBuddy breadboard, tails add-ons) whose docs have no parts table.
- **PCB Guitar Mania**: 14 without a BOM; 29 without controls, none of which have pot rows to name them from.
- **Five Cats Pedals**: 6 without a BOM after OCR of the older inserts: three 3PDT
  daughterboards and the Transelector (no table), and the Vintage Style Fuzz Face, whose
  insert is a wiring diagram with values printed on the parts.
- **PedalPCB**: complete for circuits. The boards without a parts list are utility items whose
  docs have none (drill templates, the current-meter kit, the test platform, the ProtoBoard).

## Specific boards

| Vendor | Board | Problem |
|---|---|---|
| Dirt Monger | Multi RAT 1995 | Parts table is an image laid out in a way neither the text parsers nor OCR read; 1 row |
| Dirt Monger | Integrated Preamp | Same; 3 rows |
| On The Road Effects | OmniMuff | Six version blocks parse (38 rows each) but the pots sit outside the blocks, so no named controls |
| On The Road Effects | Guerrero Oro | Same; 0 rows |
| Dead Astronaut | Chasm Reverb, Ebe Delay, Timestream Reverb | Raster docs where thorough OCR still returns nothing |
| Five Cats | Marshall Supa Fuzz, Vintage Style Fuzz Face | Insert is a wiring diagram with values on the parts, not a table; 1 and 0 rows |
| GuitarPCB | G.B.O.F. (16-project fuzz board), NostalgiTone Dual Combo Creator | No parts table: the doc lists sixteen projects to build on one board and points to DIY Layout Creator drawings |
| PedalPCB | LotLizard, SuperStevie | Single-part variants live in the parts-list notes ("Omitted in Nano version"); shown as notes, not as a variant selector. Muffin Fuzz's eight side-by-side versions are parsed |
| Five Cats | Rattus | The four variant columns are OCR'd, but a noisy line drops a column: 16 / 14 / 13 / 12 rows across RAT / RAT2 / Turbo / You Dirty |
| Effects Layouts | Schematic Fuzz | Build doc is drill templates only; the schematic is on the silkscreen |
| Effects Layouts | Lawn Darts | Doc is a single scanned schematic image; thorough and positional OCR at 300 dpi both find nothing |
| Effects Layouts | Melody Malfunction, Cranky Speaker | Doc has only a shopping list (value, type, quantity), so rows are named by quantity (`×2`) and controls are a knob count |
| Effects Layouts | Six Shooter, Strider, Soil Slinger | Only a drill template or a blog post is linked; no parts list |
| Effects Layouts | One-Knobber, Drivestortion | Old blog-era project PDFs with broken font encodings; OCR gives 13 and 18 rows, pots missing |
| JMK PCBs | Big Bass Drive, AC/DC Drive, Level Up, 5 Knob Fuzz, Classic Tremolo, Blue Warbler 2, Super Phaser | Build notes describe the original without naming it; `based_on` left empty |
| JMK PCBs | most boards | Docs rarely state an enclosure (8 of 38 found); drill templates are named by knob count, not size |
| Five Cats | 57 older inserts | No enclosure stamp on the insert (only newer layouts have the "minimum enclosure" badge) |
| Madbean | Flunkee | Doc link returns 404 (`_folders/1590A/pdf/Flunkee.pdf`) |
| PedalPCB | Parentheses (pcb237), Thermionic Deluxe, WarScythe | Control names are read from a doc section that also holds changelog lines ("Updated control layout") and footswitch labels ("Active / Bypass"), so a few non-knobs appear as controls |
| several | Vol / Volume, Pres / Presence | Controls from two sources can name the same knob two ways; exact duplicates are removed, near-duplicates are not |
| Mask Audio | Business Card | Doc says 1590BBM/BBS; the enclosure regex does not know 1590BBM |

## Parser wishes

- Named-pot tables where the taper is a separate column (`LOUD | A | 100k`).
- Docs that put the parts list in an image but the schematic as vectors: pair the schematic
  and fall back to OCR only for pots and switches (Dead End FX does this; generalize).

## Query

```sh
sqlite3 -header -column data/library.sqlite "select vendor, sum(n=0) as no_bom, sum(n>0 and n<8) as thin, count(*) as total from (select c.vendor, (select count(*) from bom b where b.circuit_id=c.id) as n from circuits c) group by vendor"
```
