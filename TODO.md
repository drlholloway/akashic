# TODO: parse gaps and wrong parses

A running list of documents the pipeline reads wrong or not at all, so they can be fixed
later without re-discovering them. Add an entry whenever a scrape leaves a board thin;
remove it when the parser handles the case. Counts come from `pcblib stats` and the query
at the bottom; re-run them after parser changes.

## Whole-vendor gaps

- **PCBWay (Glory to Ukraine)**: the drawings carry no designators and the member uploads no BOM,
  so parts were read by eye from the schematic and grouped by value ('×4 470k'). 10 of 337 boards
  have no parts: utility boards (jack, switch, control and 3PDT breakout boards, the AMT M1 EQ,
  controls and switch boards) and four clones (SD9, TS 808 V2, Distortion +, Rat) for which no
  schematic image was fetched; worth a look on the project pages.
- **Experimentalists Anonymous**: 485 of 781 schematics were read by eye (October 2026; the Saw
  Waveshaper, EMS VCS3 oscillator and both Minimoog filter copies joined after the transistor audit). 45
  have no parts: 43 of them were looked at and hold nothing to list (wiring diagrams, circuit-bending
  photos, articles, PCB layouts, continuation pages). 187 more came from positional OCR with fewer than
  8 rows and were not read by eye (the Ibanez TS-10 among them: only its transistors and D1 are right,
  from the drawing's note); 39 small circuits read by eye also have fewer than 8. The transistor audit
  found the OCR boards' usual fault: a legend or note value ('All diodes are 1S1555', 'IC is a
  NJZ4558') paired with the nearest designator, so a thin OCR board's transistors deserve a look.
- **Bent Fishbowl**: 8 of 33 schematics come back thin; busy drawings defeat the
  designator/value pairing.
- **GuitarPCB**: most NostalgiTone docs carry their tables in the text layer and read exactly; OCR fills
  only parts the text does not list. 5 boards with no BOM and 7 thin after the thorough OCR pass; the rest
  are selector and wiring boards with no BOM by design (Roto-Tone, 2 Knob Job, 3PDT
  boards, Easy Order Switching); those and the knobless Emerald Ring are the only boards with no controls.
- **Madbean**: 8 boards with no BOM: the utility boards (9mmBB, 14mm, MiniJack1, sProbe,
  Strober, TrueSoft) and Flunkee, whose PDF link is a 404. The VFE series docs carry a
  shopping list (qty, value, type) rather than a designator table, so their rows are named
  by quantity.
- **Aion FX**: 7 boards without a BOM; the boards without controls are bypass and utility modules.
- **Fuzz Dog**: 4 boards without a BOM and 13 thin, all utility items (switchers, testers,
  the ProtoBuddy breadboard, tails add-ons) whose docs have no parts table.
- **PCB Guitar Mania**: 14 without a BOM. Controls are named on every circuit board except the knobless
  Green Octaver; the rest without are switching and buffer boards.
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
- **delyk PCBs**: stopped selling online in October 2026; the site is now a static catalog with no
  prices. Three boards have no document in their Downloads section (Fussy Valve 809, TranqDrive,
  LB-Fuzz); named trimpots (DEPTH, RATE) are read from their 'Trimpot' note.
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
- **Gigahearts FX**: only GIG BUFF v1.3 links its build doc; the others ship the doc with the
  board. GIG BUFF v2.0 is read from the product page's schematic image and completed by hand; GIG BUFF v3.0, Broadcast, Full Moon and PIP BOY show only
  board renders, so they are listing-only.
- **Dirt Monger**: PW-2, HMT-2 and American Metal use a font whose text layer drops letters; their
  resistors and capacitors are read from the list page's image instead (PW-2 and HMT-2 in full).
  American Metal's capacitors whose unit OCR drops ('10', '1') are filled in by hand.
- **Scientific Guitarist**: TBR has only its build document's shopping list (no designators); EchoWreck,
  Alternate Dimension, T60, KDLA and Wobble Box are paired from the schematic PDF, so their pots
  show as a knob count. Some trimmers and pots have no value in the Eagle export.
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
| GuitarPCB | G.B.O.F. (16-project fuzz board), NostalgiTone Dual Combo Creator | No parts table: the doc lists sixteen projects to build on one board and points to DIY Layout Creator drawings |
| Experimentalists Anonymous | Scans in general | Junk pairs survive: bare one-digit resistor values ('R38 = 8'), mangled designators (the Obesifier's are fixed by hand) |
| Effects Layouts | Schematic Fuzz | Build doc is drill templates only; the schematic is on the silkscreen |
| Effects Layouts | Melody Malfunction, Cranky Speaker | Doc has only a shopping list (value, type, quantity), so rows are named by quantity (`×2`) and controls are a knob count |
| Effects Layouts | Six Shooter, Strider, Soil Slinger | Only a drill template or a blog post is linked; no parts list |
| JMK PCBs | most boards | Docs rarely state an enclosure (8 of 38 found). The drill templates draw only the board and its pots, and the shop's categories carry no size, so there is no source to read one from |
| Five Cats | 57 older inserts | No enclosure stamp on the insert (only newer layouts have the "minimum enclosure" badge) |
| Sheepylove on GitHub | Katahdin, Sarda, Shorn Sheep | No parts list in the repository and the board render's labels do not OCR, so no controls; the schematics are on the Bent Fishbowl blog |
| Frog Pedals | all boards | No build documents are published (Frog sends them to buyers), so the listing carries no parts |
| TH Custom Effects | ROG Umble | Its build-instructions link is a PNG sheet rather than the HTML documentation the other boards have; no parts read from it |
| Tonepad | MXR Noise Gate, Purple Peaker, Tremulus Lune, DOD 250, Ross Phaser | No file on the project page, or (Ross Phaser) a layout whose values sit only in the drawing. Image-only layouts with a parts box (EA Tremolo, Rebote 3, Speaker Simulator) are OCR'd now |
| WRAA Labs | Retroflect, Inkcap II | The Retroflect guide has no parts list; the Inkcap page's description is cut before its pots, so no controls |
| Madbean | Flunkee | Doc link returns 404 (`_folders/1590A/pdf/Flunkee.pdf`) |
| transistor subs | 2N6027, 2N2646 | A PUT and a UJT, which the database lists without parameters, so no substitutes. OC139, 1T308A/B, CV7351, FS36999, TR1623, CV10805 and A02650 are anchored to listed equivalents (ASY29, GT308A/B, 2N1308, 2N5133, 2SC1623, BC108, OC71). Placeholders like `NPN`, `GE`, `your choice` are skipped on purpose |
| Experimentalists Anonymous | EMS VCS3 oscillator, Minimoog ladder filter | Read by eye with three readings left open: VCS3 Q63's polarity is not legible (2N5172 or 2N4288), its 'sot' resistor is chosen on test; the Minimoog's third ladder pair reads Q9 or Q19 (taken as Q19) and R54 prints 410 (taken as 470) |
| Dead End FX | Pompei | Read by eye from its parts-list pages (three boards: bottom as printed, UPPER- and PRE- prefixes). The doc leaves PRE-R10 (LED resistor) to taste and does not list IC6, IC12-17, IC23, IC30, Q11 or Q15 |

## Transistors

Audit of October 9, 2026: 9,059 transistor rows name 461 distinct part numbers; 415 match the transistor
database (`data/transistors.sqlite`) and 257 rows are generic ('NPN', 'Low gain BJT', '?'). Every
mismatch was traced to its source and 55+ boards corrected (doc typos, OCR misreads, legend values on
the wrong designator, shifted rows). The 46 still unmatched are real parts the database lacks: unijunctions
(2N2646, 2N4870, 2N6027), Soviet KP303A/E/ZH and KR504NT3V, BC264A/D, the 2N4302, 2N5103, 2N5863, Japanese
JFETs the lookup used to match to the wrong part (2SK34D, 2SK381/B, 2SK44C/SP, 3SK30), TI and Siliconix
oddities (TIS-59, TIX882, E112, E212, U3078, P1069C, AD3958, MAT04), house numbers (Moog 991-002298/873,
ARP TZ-81/TZ-581, Maestro P-2356, Heathkit X29A829, Korg TX-429D, Motorola HEP-50/801, NP4124, CV7353)
and replacement lines (NTE466, SK3005, SK3020), plus InterFET's SMPJ201. `pcblib audit` flags a new one
as 'Transistor not in the transistor database'; a part the database lacks but that has a close listed
equivalent goes in `transistors._ALIASES`.

## Datasheets

Counts from `pcblib datasheets` as of October 9, 2026: 562 of 1,176 part numbers link a datasheet. Every
current part used more than once was searched by hand in early October (`"<part> datasheet pdf"`, maker's
own site only); the counts below are since then.

- **Discontinued (hosted)**: 67 of the 237 sheets in `datasheets.DISCONTINUED` are hosted, 13 have
  only a selector or catalog row (mostly germanium: AC176, OC139, 2N5308, OC71, OC75, AC127), and
  157 are still to download. The most used: 1S1555, SAD1024, 2SK118, 2SC945, 2SK184, 2N4302,
  1T308, NKT275, 2SC2785, KP303, CA3094. `pcblib datasheets` writes the worklist to
  `data/cache/datasheets/discontinued.html`.
- **Current parts still without a link**: 439, of which 41 are used more than once. A grade or package
  spelling now takes its base part's sheet (`datasheets.base_spellings`: 2SC2240BL <- 2SC2240, HD14011BF
  <- CD4011, MMBF201 <- J201, UPC4558C <- 4558), and a grade of a discontinued part links its hosted
  sheet as soon as that sheet is downloaded.
  - **No sheet to find**: generic LDRs (GL5516, GL5537-1, KE-10720, LDR1, Morley's M79-211564-000), house
    numbers (Maestro P-2356, DOD RCY568, TI592, A02650, Boss FD24006BP, the Korg 35 module, EHX 1048), the CEM3310
    and CEM3360 (Alfa reissues with no sheet on Alfa's site), zener voltages off the E24 series (9V, 5V3)
    and odd diode marks (51E, ZL9M3, GL32AR).
  - **Searched October 9**: Belton's own BTDR-2/2H and BTDR-3/3H sheets, Spin's FV-1, TI's MC3403,
    RC4559, RC4136, LM319-N and LM79 (7912, 7915) are linked. The TIS92/TIS97 (TI, not on TIS93's sheet)
    and the Soviet D9 family (D9B, D9E, D9K, D9V) joined the discontinued list. No sheet: the THAT 2159
    (THAT's 2150-series sheet names only the 2150, 2150A, 2151 and 2155), EHX's 1048 (a house number)
    and the 2764 (a programmed EPROM). NTE's own NTE102/NTE103 sheet is served from the site
    (nteinc.com refuses scripts, so it cannot be linked or checked). Still open: the 2N3965 (Central
    lists the part but publishes no PDF).
  - 2N5008 (RWL Whippoorwill, Dunwich Cthulhu) and NP4124 (DOD 280) are printed that way in their
    sources and are not misreads. The other 398 are used once; not yet searched.
- **Panasonic BBDs**: MN3204 and MN3001 have no maker copy online. The others link to the copies
  that the distributor Cabintech hosts, named after the new production where there is one (MN3207
  -> Coolaudio V3207, MN3101 -> Cabintech CT3101, BL3208 -> Coolaudio V3208).
- Generic entries (GE, NPN, a bare zener voltage, LED colours) cannot have one.

## Parser wishes

- Schematic pairing now runs for every board whose parts list is thin, quantity-only or
  names no controls (`enrich.py`): vector text first, then OCR at two resolutions, three
  orientations and two segmentation modes. A scanned document with no schematic heading is
  searched page by page for the one that pairs the most labels. It reads clean KiCad and
  Altium exports; hand-drawn or watermarked schematics and boards whose pots are
  designators (VR1) still get nothing from it, and scanned Eagle schematics (Lectric-FX) give
  up only a third of their labels.
- Apple Vision OCR (macOS only) runs beside tesseract. It drops some short designators in
  multi-column tables and reads µ as p now and then (a machine-read capacitor under 2pF is taken as
  µF; '100p' for 100µ cannot be told from a real 100pF and needs a hand fix); a table with one designator column is
  numbered from the readable ones, but a multi-column table still leans on tesseract for the
  labels Vision misses. Off macOS the library would lose the Vision readings on a rescrape.
- OCR of a parts table now also runs with the word gaps preserved, so the same table parsers
  that read text PDFs read the OCR (per-variant tables, side-by-side Qty / Value / Parts
  lists, Part / Value columns). Tables printed white-on-colour on a PCB render (Five Cats
  wiring diagrams) still defeat tesseract.

## Query

```sh
sqlite3 -header -column data/library.sqlite "select vendor, sum(n=0) as no_bom, sum(n>0 and n<8) as thin, count(*) as total from (select c.vendor, (select count(*) from bom b where b.circuit_id=c.id) as n from circuits c) group by vendor"
```
