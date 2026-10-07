# Changelog

All notable changes to Akashic. The section for a tagged version becomes the
GitHub Release notes.

## Unreleased

### Added
- Eff Dub Audio: 14 free DIY projects from the blog (The Snitch RAT clone, TweakTone delay, Bodhi
  Zendrive, Box of Hall reverb, DuoVibe, Wahscillator and more). Parts come straight from the Eagle
  schematics in each project's file pack, which are exact; schematics posted only as images were
  transcribed by hand. The file packs are linked.
- Cryptid Effects: this site's own layouts (The Everlasting Tantrum v2, Biggus Dickus, Ground Fault)
  from GitHub, CC BY-NC-SA 4.0. Parts and controls come from each wiki page. The PCB and faceplate gerbers
  and the Tayda drill template are linked, and the circuit page shows the schematic and the finished pedal.
- Datasheets on parts pages: 240 parts (83% of the part uses in the library) link to the manufacturer's
  own datasheet (TI, onsemi, Analog Devices, Renesas, Microchip, Vishay, Nisshinbo, Diodes, Linear
  Systems), every link checked. onsemi no longer has a J201 sheet; Linear Systems still makes the part,
  so the J201 links to its datasheet in their data book (page 62). The BBD chips link to the sheets
  the distributor Cabintech hosts: Panasonic's MN3102, Xvive's MN3005 and MN3007 (in production again), and
  Coolaudio's V3207 and V3205 for the MN3207 and MN3205 they replace. The PT2399 and Electric Druid's
  TAPLFO3 link to the sheets Electric Druid keeps. The site links rather than hosts them, as the manufacturers hold the copyright; a copy is
  cached locally for reference. `pcblib datasheets` finds links for parts added later. Discontinued parts
  with no maker's copy are served from the site: 32 archived files covering 66 part spellings,
  without the archive's ad pages and watermarks and checked for the part number. One sheet serves every
  part it covers (NE570/571, BC182/183/184, 2N1302/1304/1306/1308). Where only a row in a maker's selector table could be found
  (2SC1815, the germanium catalogs), the part page says so. Package suffixes no longer hide a TI datasheet (LF356N,
  OPA604AP, LMC660CN and five more now link).
- PCBWay (Glory to Ukraine): parts lists for the member's boards, read from each project's CC BY-SA
  schematic. The drawings print values but no designators, and the member uploads no BOM (a login adds
  only a PDF of the same drawing and a layout render), so every value label is OCR'd, typed by its shape
  and counted ('×4 470k', '×6 1N914'), ICs once each, with the named knobs and their tapers (Sustain
  A10k). PCBWay is fetched with ten seconds between any two requests, across all its hosts.
- Holy Island Audio: four DIY PCBs from a UK Big Cartel shop (Phantom Coil spring reverb, Sun Swallower
  solar drone synth, EMF Sniffer, Harmonic Percolator), sold as options of one product with their own
  price and stock. Parts come from each board's Google Doc build guide, with named knobs and the Tayda
  drill templates linked.
- An About page (/about, in the header and footer): what the library holds, where the parts lists
  come from and how to read the ocr / sch / fixed markers, how prices and delisted boards work, what
  is linked rather than copied, and how to report an error. Its counts and last-refreshed date come
  from a meta.json the export writes, so they stay current with every weekly refresh.
- Circuit pages mark where a value came from: 'ocr' (read from an image), 'sch' (paired from the
  schematic drawing) and 'fixed' (corrected by hand), with a one-line legend above the parts list,
  so builders know which values to check against the build document. Text tables and interactive
  BOMs are exact and unmarked.
- Scientific Guitarist: 30 open-source DIY projects (delays, reverbs, choruses, a through-zero
  flanger, a MIDI switcher) whose GitHub repositories carry the Eagle project. Parts come from the
  BOM exports, with named knobs and dual-gang pots; boards without one are read from their vector
  schematic or the build document's parts table. Optocouplers such as the 6N138 are filed as
  optocouplers everywhere, not as capacitors.
- Boards a vendor stops listing are kept and marked 'no longer listed' with the date they were last
  seen, on the circuit page and in the results table (and left out of the in-stock filter). A board
  is only marked when its own page is gone too, and a scrape that finds far fewer boards than before
  marks nothing.
- Weekly refresh: scripts/refresh.sh re-fetches every vendor's pages (`scrape --refresh-pages`:
  prices, stock and new boards, keeping cached documents), runs `audit`, and deploys only when the
  audit found no new problems on boards that were already there. scripts/install-refresh.sh
  installs it as a launchd agent (Sundays 04:00). The first refresh added 98 boards (85 PedalPCB,
  8 Sheepylove, 2 GuitarPCB, one each at Five Cats, Fuzz Dog and Other Pedals) and updated 98 prices
  and 34 stock states.
- `pcblib audit`: flags parts rows that do not look like valid parts (values off the standard
  series or out of range, parts filed as the wrong kind, one-off part numbers a character from a
  common one, unknown transistors, mangled designators), writes a filterable report to
  data/cache/audit/ and lists the flags added and cleared since the last run. Run after a rescrape,
  before deploying.
- Gigahearts FX: PIP BOY, a triangle Big Muff after the Fallout Cloud with bass and treble
  controls, a 3-way clipping switch and a clean blend (listing only; the build doc ships with the
  board).
- A changelog page (/changes): what changed each week, built from the commit history at export,
  each change opening to its description and linking to its commit. The footer's Sources list
  now opens and closes, and the colophon links the changelog in place of the GitHub link.
- Gigahearts FX (UK Shopify shop, five boards in GBP): the GIG BUFF versions of the EHX/JHS Big
  Muff 2, a Broadcast with mods and the Full Moon (Moon Rock / Coyote). One build doc is public;
  GIG BUFF v2.0 is read from its schematic image.
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
- Schematic pairing: Experimentalists Anonymous vector PDFs take the wider pass for labels set
  off their part (the PT2399 echo reads 21 rows, not 7); 1N-series diodes read as IN4148 or
  iN34 are repaired; the 3 Vision reads from a resistor's zigzag ('32.2K', '3100K') is dropped;
  and a diode number is no longer taken as a capacitor value ('1N4004' as 1n).
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

### Changed
- Parts cross-reference: each category is listed alphabetically (numbers compared as numbers),
  and pots are grouped by taper (A, B, C, W, none) and ordered by resistance.

### Fixed
- Parts: one entry per IC. Parts lists name the same chip with package and grade suffixes (TL072CP,
  TL072P, LM386N-1, TC1044SCPA) and second-source prefixes (RC/JRC/NJM 4558, MN/V/BL 3207, UA/LM 741),
  and '072' for the TL072, which split each chip across many parts pages. They now share one name and
  page: IC entries went from 528 to 299 (TL072: 744 boards on one page). Chips that only share a number
  stay apart (LM4040 and CD4040, TLC555 and NE555, 7660 and 7660S), and a search for TL072 also finds a
  board whose list says '072'.
- Originals: one name per original circuit. Vendors write the same pedal many ways ('EHX Big Muff',
  'Electro-Harmonix Big Muff Pi', 'Big Muff'), which split it across the Originals list. Brand aliases
  are now spelled one way, the best-known models are matched by pattern with their siblings kept apart
  (Op-Amp Big Muff, Big Muff Pi 2, RAT 2, TS808), a model only one brand makes gets that brand when the
  vendor left it off, and every spelling takes the most common one. Big Muff went from 39 entries to 11
  and the list from 2,567 to 2,304. Pairings ('Fuzz Face into Big Muff') keep their own entry, and
  descriptions that name no single original ('Lots of Big Muff variants') stay on the circuit page but
  off the list. Older links that carry a vendor's spelling open the whole group.
- delyk PCBs stopped selling online and replaced its WooCommerce shop with a static catalog, so the
  adapter now reads the catalog's product pages: their Downloads section for the build document and
  drill template, and the spec list for difficulty, original and enclosure. Boards keep their pages;
  prices are gone, and in stock means the maker still has copies (ask through the site). Buzz Box,
  Conductor's Hand and Lightning Bolt now have parts lists, and El Rey de la Gloria Azul II is
  transcribed as its four versions (Blues Breaker, Morning Glory, King of Tone, Ultimate King of Tone).
- Weekly refresh: the vendor loop failed on macOS before scraping anything (an xargs -I command longer
  than 255 bytes), so a scheduled run audited and deployed unchanged data. Each vendor now goes to the
  loop as an argument.
- Scraper on selectolax 1.0: the vendor adapters parse HTML with LexborHTMLParser, as 1.0 removed the old
  Modest parser. Re-scraping all twelve affected vendors from cache gave the same boards, fields and parts
  rows, with one fix: Madbean's Snarkdoodle row, whose malformed table cell the old parser dropped, now
  reads its 1590A enclosure. CI installs the scraper from uv.lock, so a dependency release cannot break it.
- Hand transcriptions for documents no parser reads: Five Cats' Supa Fuzz and both Vintage Style Fuzz
  Face inserts (wiring diagrams with values on the parts), Effects Layouts' Drivestortion (six versions
  side by side: DOD Grey and Yellow 250, MXR Distortion+, Ross, DeArmond Square Wave, YJM308) and
  Lawn Darts; Dirt Monger American Metal's missing capacitors, the GIG BUFF v2.0's vertical labels and
  pots, and the Moog 901B's phantom R312 (R32).
- Controls: when a board's controls are empty or only a knob count and every pot in its parts list has
  a name, the names are used: 132 boards, 49 of them PedalPCB boards whose product page lists none. A name
  read off a scan must be a word knobs are called, so OCR slips like "Volumel" keep the knob count.
  Knobs written 'DRIVE 100k Lin' or 'GAIN A 500k' on GuitarPCB and PCB Guitar Mania boards are added
  by hand; the DVF names its six controls without values.
- OCR word boxes: a word tesseract reads as a quote mark no longer swallows the words after it. The
  reader took the quote for the start of a quoted field, so 31% of cached schematic and table scans
  (1,801 of 5,842; most of them Experimentalists Anonymous) lost every label after their first quote.
- The last Experimentalists Anonymous candidates checked on their drawings: Danelectro PBJ, Carl Martin Heavy
  Drive, DOD FX96, Ibanez AD9 and PQL, both EHX Micro Synths; the Nobels DT-1, Distortion Xtreme and Fu-Z and
  the Ross Phaser are clean drawings and have their misreads (R14 '4148', R64 '062', U1 AM9709CN for RC4558P)
  and missing parts filled in. Lectric-FX Betty Boost's grid misreads (R1 10M, R2 10K, R7 and R9 18k) and its
  phantom R0 and C0 are corrected.
- GuitarPCB reads a document's text layer before OCR. Most NostalgiTone docs carry their parts tables as
  text, so their values are now exact (about 47 parts per board, from 40); OCR only adds parts the text
  does not list. The MUFF'N's ten-variant chart (Ram, Violet Ram, Triangle, 3rd Edition, Creamy Dreamer,
  Foxy Lady, Green Russian, Black Russian, Civil War, Mayo) reads every column: a header whose long
  names wrap onto the lines above and below is rebuilt by position, and grouped designators
  ('D1,D2,D5,D6', 'Q1-Q4') and named pots ('P1-Sus/Fuzz') in a variant table expand to their parts. Dual-combo
  docs with one 'Bill of Materials <pedal>:' table per pedal keep the two boards apart as variants
  (Doomstortion / Harbinger Fuzz, Phaser / PlexAmp and 14 more). PedalPCB Muffin Fuzz's 'SUFMascis Muff'
  reads as 'SUF Mascis Muff'.
- Experimentalists Anonymous: about 200 part values on 54 schematics restored or corrected by hand, each read
  off the drawing: candidates from a pairing pass that searches farther from each label, which is right about
  two times in three, so its proposals were checked one by one rather than switched on. The Nobels CO-2 and PH-D
  are transcribed in full (knobs included). Where the archive holds two files under one title ('Moog
  Taurus.jpg' and 'Moog Taurus.pdf', 11 titles), each is now its own board with its own image; before, the second
  overwrote the first and was read from the first one's image.
- A capacitor under 2pF read by OCR or from a schematic is taken as µF: OCR reads the micro sign as a
  p, and no pedal uses a 1pF part (MUFF'N C9 and C13, the SSM2166's C3, the panner's C2 and the EA
  Tremolo's NP caps were all 1µF or 0.1µF). Hand corrections now run last, after designator repairs,
  so a correction meets the designator as stored. Lectric-FX Double*Take's scanned grid is corrected
  by hand (67 rows: misread values, junk diodes and designators, nine missed cells), and so are the
  MUFF'N's C1 and C15.
- Hand corrections can target one build variant and add rows the parsers missed, not only change
  or drop them. Used for Five Cats Rattus (the RAT's C13 is 1µF, not 1pF; RAT2 R1 and the Turbo
  RAT's C7, C9 and LED clippers added), Lectric-FX Mongrel (D1 1N4002, R18 4K7, C10 100uF, two
  junk IC rows dropped) and three Experimentalists Anonymous drawings: the BOSS OC-2 (R48 470K,
  R52 10k, and pin numbers and pin names read as values), the Tau 1010 (R7 12K, the ladder caps)
  and the Univox Microphaser (14 rows to its full 54).
- PedalPCB: its product sitemap leaves out part of the catalogue, a different part each time, so
  boards already in the library are also read from their own pages.
- Dirt Monger PW-2, HMT-2 and American Metal: where the doc's font drops the units from the text
  layer, the resistors and capacitors are read from the parts list's image (PW-2 21 -> 87 rows,
  HMT-2 29 -> 58, American Metal 62 -> 81).
- Audio transformers (42TM022, TY-141P, LT44, OEP1200) have their own Transformers category instead
  of being filed as trimmers, pots or 'other' (40 rows); European docs number them T1 or TR1.
- A 4-digit resistor code reads as its value (1002 -> 10k, 2201 -> 2k2) when the plain number is not
  a standard value; 4700 stays 4700.
- Pot and trimmer rows whose value is a bare small number or a taper with no unit ('A5', '16', '1')
  are dropped: OCR prose ('WORKS  A5') or schematic pin numbers. Zero-width characters copied from web
  pages are stripped, and Guitar-Electronics' 'BC550  1pcs. "Q1"' lines are no longer also read the
  wrong way round.
- Semiconductor rows that carry a word or placeholder instead of a part ('for', 'Clipping',
  'empty or your choice', 'Jumper', '(optional)') are dropped (about 200 rows); descriptions such
  as 'Germanium', 'NPN JFET' or 'Dual op amp' stay.
- OCR and typing slips in well-known parts are repaired where the slip spells no real part:
  TLO72/TLQ72 -> TL072, ZN3904 -> 2N3904, 14001 -> 1N4001, BAT-41 -> BAT41, CO4047 -> CD4047,
  LM9324/XM324 -> LM324, RCY558 -> RC4558, WA741 -> uA741, pt2395 -> PT2399 (31 rows), and a
  diode read as 1M34A -> 1N34A (Guitar-Electronics OCD).
- A knob read twice (Level from the schematic, LEVEL from the parts-table OCR) is listed once,
  keeping the reading whose value parses and, between two, the text table over the schematic over
  OCR (332 rows on 92 Dead End FX boards and a few others).
- OCR's '25K30A-Y' reads 2SK30A-Y (no part number starts 25K or 28C), and a jack's pin label read
  as a pot ('MONO 5W', 'STEREO 5W' for MONO_SW) is not a knob.
- Hand corrections (scraper/pcblib/corrections.py) for what no rule can read, checked against the
  source and marked 'corrected by hand': Dead End FX Zuul IC3 is an LM324, and the 2952's Clean
  knob is A20K (its schematic prints A15K), and Moonn's Kloppe Gerät D1/D2 are 1N34A (the doc prints
  1A34A).
- Dirt Monger parts lists read from the text layer in both of their layouts, 'value - refs' and
  value beside its designators in two columns, with or without a 'Parts List' title: Distortion H,
  Bigger Muff, XT-2, Bass Grunge, Dual Octave and American Metal no longer carry OCR rows that paired
  each designator with the wrong column (R1 = 100n). Knob names are kept (L, ML, M, MH, H), a
  'Trimmer' entry is a trimmer, and the bypass-buffer board printed below the list is left out.
  Where a doc's font drops letters (PW-2, HMT-2), values that lost their units are left out rather
  than listed wrong, and '2 5088' reads 2N5088.
- Table parsers: prose after a parts table no longer turns into parts ('accommod = ate surface-'),
  a running page footer with a digit in the title is skipped ('DZ4 PREAMP  6'), and a second
  table's header row ('BRAND  PART #') is not a part (Aion FX, God City, PedalPCB).
- An all-caps name is a knob only when its value is a pot value: 'CUI  PQMC3-D1' is a DC jack and a
  'MODE  ON/OFF/ON' or 'MIDS  DP3T' entry is a switch. Vactrols (VTL5C3) are optocouplers.
- Moody kit shopping lists: an 'IC's:' or 'IC's and IC sockets:' heading is read, so ICs no
  longer inherit the Diodes or Transistors heading above them (Spring Reverb, Flanger, Analog
  Delay and about 50 more kits). Sockets are skipped, a part number keeps its 'or' alternatives
  and drops the description after it ('78L05 5volt regulator' -> 78L05), a transistor or
  regulator listed under the wrong heading is filed by its value, and 'Dual Gang' pots keep
  their type.
- 'Lysdiod' (Swedish for LED) in Moody's own kit lists is filed as an LED, not a diode.
- KiCad interactive BOMs whose designer typed the part into the reference ('U1 - LM386') keep
  the designator, so Five Cats' Not So Clear lists its LM386 and PT2399 as ICs, not sockets.
- Resistors written '2m2' read as 2.2M, not 2.2 milliohms (143 rows).
- Transistors numbered T1, T2 in European docs (Moody's Carlin and BJF kits) are transistors,
  not trimmers (87 rows).
- Pot values carry their type: 'B100K DUAL' is a B100K dual-gang pot, '100K Trim' a trimmer, and
  footnote marks, lower-case or trailing tapers ('c100K', '25kb', '1m C') parse (about 200 rows).
- Designator ranges ('Q1-4', 'D1-2') become one row per part for every parser, per build variant
  (Fuzz Dog, 145 rows).
- Five Cats One Knob Fuzz: its insert's five-build table (ColorSound, 1996, Meathead, Dark
  Meathead, Ritual) reads as five variants, 77 rows, where a flat list of 20 with junk stood. Vision
  now also reads a copy of the page with a grey dot grid whitened, which had made it drop cells.
  Five Cats boards listed once per pack size (One Knob Fuzz x1 and x5, 3PDT daughter board x1, x5
  and x10) are one circuit each, and a generic 'Pot' line in a variant table is kept as the knob.
- OCR'd variant tables: a line of knob labels (a board's FUZZ / TONE / BOOST silkscreen) is no
  longer taken for build names, which had split GuitarPCB's Guitar/Bass Driver into bogus 'GAIN',
  'BASS', 'TREB' and 'BOOST' variants.
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
