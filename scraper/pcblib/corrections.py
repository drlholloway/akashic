"""Hand corrections to parts rows that no parser rule can make, each checked against the source
document by a person. Applied whenever a board is stored (db.upsert_circuit), after every parser has
run, so a rescrape keeps them. A value of None removes the row; a value for a row the parsers missed
adds it, after the nearest lower designator of its kind. Add a line per report, with where it came
from; remove it when a parser learns to read the board right.

    CORRECTIONS[circuit_id][designator] = corrected value, or None to drop the row
    CORRECTIONS[circuit_id][(variant, designator)] = the same, for one build variant only
    (designators match regardless of case: 'CLEAN' corrects a knob stored as 'Clean')
    CORRECTIONS[circuit_id]['=' + value] = the same, for a row whose designator others share ('×1')

A document no parser can read (values printed on the parts of a wiring drawing) can be transcribed
whole instead: TRANSCRIBED[circuit_id] is its parts list, which replaces whatever the parsers found.
Rows without designators are named by quantity ('×2'), as the shopping-list parser names them. A
five-field row carries its build variant ('DOD \u201977 Grey 250').

Schematic images read whole by eye (the OCR got most of a drawing wrong or missed it) live one per file
in transcribed/<circuit id, ':' as '__'>.json, with the reading's date, a comment on the drawing, the
values that stayed uncertain and the rows. An empty list drops wrong OCR rows when the drawing gives
no values to read.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import BomRow
from .normalize import normalize_row

Key = str | tuple[str, str]

CORRECTIONS: dict[str, dict[Key, str | None]] = {
    # Dead End FX Zuul: OCR reads IC3 as 'LhI3Z24' (reported 2026-09-29).
    "deadendfx:zuul": {"IC3": "LM324"},
    # Dead End FX 2952: the schematic prints CLEAN A15K, the parts table A20K; A20K is right (reported 2026-09-29).
    "deadendfx:2952": {"CLEAN": "A20K"},
    # Moonn Kloppe Gerät: the build doc itself prints 1A34A, a typo for the 1N34A germanium diode (reported 2026-09-30).
    "moonn:kloppe-gerat": {"D1": "1N34A**", "D2": "1N34A**"},
    # Lectric-FX Mongrel: grid OCR misreads D1, R18 and C10 and pairs two junk IC rows (checked 2026-10-01).
    "lectricfx:mongrel": {"D1": "1N4002", "R18": "4K7", "C10": "100uF", "IC6": None, "IC16": None},
    # Lectric-FX Double*Take: the scanned grid reads cell by cell, with misreads, junk designators and
    # skipped cells (checked against the parts grid 2026-10-01).
    "lectricfx:doubletake-dual-overdrive": {
        "R5": "27K", "R24": "6K8", "R27": None, "R72": None,
        "C1": "10n", "C6": "10n", "C9": "1uF NP", "C20": "1uF NP",
        "D2": "1N914", "D3": "1N914", "D6": "1N4001", "D113": None,
        "IC1": "JRC4580", "IC2": "JRC4580", "IC1B": None,
        "VOL": None, "VOL2": "100KA", "GAIN1": "100KB", "PRES1": "50K trim", "PRES2": "50K trim",
    },
    # Lectric-FX Betty Boost: the scanned grid misreads four values and invents R0 and C0 (checked 2026-10-02).
    "lectricfx:betty-boost": {"R1": "10M", "R2": "10K", "R7": "18k", "R9": "18k", "R0": None, "C0": None},
    # PCBWay Fuzz Face (Silicon): 'Asc' is a garbled second reading of the Volume A500K label (checked 2026-10-02).
    "pcbway-gtu:arbiter-fuzz-face-silicon-5ffff957": {"Asc": None},
    # Dirt Monger American Metal: OCR loses the capacitors whose unit drops ('10', '1'); from the list page (2026-10-02).
    "dirtmonger:american-metal-thrash-master-combo-diy-pcb": {
        "C18": "10n", "C20": "150n", "C31": "150n", "C3": "1u", "C13": "1u", "C15": "1u", "C25": "1u",
        "C9": "10u", "C23": "10u", "C2": "100u", "C4": "47u", "C6": "47u",
    },
    # Gigahearts GIG BUFF v2.0: a clean KiCad schematic image; OCR missed the vertical labels and pots (2026-10-02).
    "gigahearts:gig-buff-v2-0": {
        "R2": "10r", "R4": "470K", "R9": "47K", "R10": "470K", "R14": "47K", "R15": "470K", "R18": "27K", "R20": "10K",
        "R21": "10K", "RPD1": "1M", "LEDR1": "220r", "C1": "47p", "C2": "100n", "C3": "470p", "C5": "4n7", "C6": "4u7",
        "C7": "470p", "C8": "4n7", "C9": "4u7", "C10": "470p", "C11": "4n7", "C13": "10n", "C14": "100n", "C16": "47u",
        "C21": "100n", "C22": "47u", "D2": "LED", "D3": "1N4148", "D4": "1N4148", "D5": "1N4148", "D6": "1N4148",
        "D7": "1N4148", "D8": "1N4148", "U1": "4558", "U2": "TL071", "U3": "4558", "LEDR2": "10K trim",
        "SUSTAIN": "B100K", "TONE": "B100K", "VOLUME": "B10K",
    },
    # GuitarPCB boards whose docs list knobs as 'DRIVE 100k Lin' / 'VOL 100k Log', which no parser reads (2026-10-02).
    "guitarpcb:3-time-champ": {"DRIVE": "B100k", "VOL": "A100k"},
    "guitarpcb:after-blaster": {"VOL": "100k", "BIAS": "20k trim"},
    "guitarpcb:morc": {"LEVEL": "C500k", "VOL": "A100k"},
    "guitarpcb:xx-double-shot-dual-boost": {"VOL1": "A100k", "VOL2": "A100k"},
    # PCB Guitar Mania pots written 'A 500k' / 'A- 100K' / '500k Log', which no parser reads (2026-10-02).
    "pcbguitarmania:pineapple-drive": {"GAIN": "A500k", "CONTOUR": "C50k", "TONE": "B100k", "VOL": "A100k"},
    "pcbguitarmania:tv-channel-dual-channel-overdrive": {"VOL": "A100k", "VOL1": "A100k", "GAIN": "B1M", "GAIN1": "B1M"},
    "pcbguitarmania:no-noise-gate": {"THRESHOLD": "A500k"},
    "pcbguitarmania:no-noise-gate-smd": {"THRESHOLD": "A500k"},
    "pcbguitarmania:noise-terminator": {"THRESHOLD": "B10k"},
    # Fuzz Dog Duo Boost: the build doc prints LT0154, a typo for the LT1054 charge pump (reported 2026-10-06).
    "fuzzdog:duoboost": {"IC2": "7660SEPA*/LT1054"},
    # GuitarPCB NostalgiTone Space Modulator: OCR drops IC2's last digit (PT239); the build doc prints PT2399 (reported 2026-10-06).
    "guitarpcb:nostalgitone-space-modulator": {"IC2": "PT2399"},
    # Madbean Wavelord24: the doc spells Electric Druid's TAPLFO3 as TAPFLO3 (2026-10-07).
    "madbean:wavelord24": {"IC2": "TAPLFO3"},
    # Five Cats Rattus: Vision reads the RAT's C13 1µF as 1pF and skips cells that are not plain
    # values: RAT2 R1, Turbo RAT C7, C9 and its LED clippers (checked 2026-10-01).
    "fivecats:rattus-rat-rat2-you-dirty-rat-turbo-rat-clone": {
        ("RAT", "C13"): "1µF",
        ("RAT2", "R1"): "47r or 100r",
        ("Turbo RAT", "C7"): "2.2µF",
        ("Turbo RAT", "C9"): "4.7µF",
        ("Turbo RAT", "D2"): "5mm Red LED",
        ("Turbo RAT", "D3"): "5mm Red LED",
    },
    # Experimentalists Anonymous: values a wider pairing pass proposed (2026-10-01 run with the mutual-nearest
    # pass on every board), each looked up on the drawing; where the pass misread a value, the drawing's value
    # is used. The Nobels CO-2 and PH-D are clean CAD drawings, transcribed in full.
    "expanon:adsr-generators-and-envelope-generators-ems-vcs3-envelope-generator": {"R146": "1k0"},
    "expanon:amplifiers-and-vcas-moog-902": {"Q2": "2N4058"},
    "expanon:chorus-ibanez-pc10": {
        "C17": "100P", "C28": "100P", "R61": "330", "R77": "22K", "R88": "82K", "R107": "620K",
    },
    "expanon:chorus-ibanez-sc10": {"R66": "10K"},
    "expanon:chorus-rocktek-chorus": {"R44": "10K"},
    "expanon:compressors-gates-and-limiters-nobels-co-2": {
        "R11": "33K", "R21": "22K", "R23": "4K7", "R36": "1M", "R43": "43K", "R44": "56K", "R52": "1M", "R61": "1K",
        "R72": "1M", "R83": "470", "R102": "100K", "R105": "2K2", "C1": "220µF", "C2": "100µF", "C12": "22µF",
        "C31": "2.2µF", "C34": "10N", "C35": "10µF", "C43": "22µF", "C51": "2.2µF", "C61": "2.2µF", "C81": "2.2µF",
        "C82": "2.2µF", "C203": "47µF", "D51": "1N4148", "D102": "3mm Green LED", "Q11": "K222E", "Q31": "C2240BL",
        "Q32": "C2240BL", "Q33": "C2240BL", "Q41": "C2240BL", "Q51": "K30A-Y", "Q61": "C2362G", "Q71": "K30A-Y",
        "Q81": "C2362G", "U101": "4007", "SUSTAIN": "B250K", "ATTACK": "B100K", "VOLUME": "A50K",
    },
    "expanon:delay-echo-and-samplers-boss-dd-2": {"C29": "1µF", "C42": "10P", "R17": "1K", "R51": "1K"},
    "expanon:distortion-boost-and-overdrive-boss-df2": {
        "Q2": "2SC732TM-GR", "Q3": "2SK30A-Y", "Q6": "2SC732TM-GR", "R21": "6.8k",
    },
    "expanon:distortion-boost-and-overdrive-marshall-guvnor": {"R6": "680k"},
    "expanon:filters-wahs-and-vcfs-buchla-291-bandpass-vcf": {"C10": "10uF", "R24": "68", "R36": "68K"},
    "expanon:flangers-ibanez-fl301": {"C123": "180P", "R149": "510K"},
    "expanon:full-synths-drum-synths-and-misc-synth-ar-318-sample-and-hold-and-noise-generato": {
        "Q2": "2N3393", "Q10": "2N4870", "Q7": "2N3393",  # Q7 read 2N3383 (2026-10-09)
    },
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-100": {"R23": "82K", "R134": "100K"},
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-110": {"R23": "82K", "R134": "100K"},
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-55": {"IC3": "CD4011UB"},
    "expanon:full-synths-drum-synths-and-misc-synth-misc-theremin": {"R17": "680"},
    "expanon:full-synths-drum-synths-and-misc-synth-roland-tb-303": {
        "R61": "10K", "R66": "100K", "R92": "100K", "R96": "10K", "R97": "10K", "R101": "10K", "R113": "100K",
        "R140": "100K", "R143": "10K", "R170": "22",
    },
    # The remaining candidates of the wide pass, checked on the drawings (2026-10-02); the Nobels and Ross
    # drawings are clean, so their misreads and missing parts are filled in as well.
    "expanon:delay-echo-and-samplers-danelectro-pbj-dj-17": {"IC3": "LM311", "R6": "220R", "R110": "18k"},
    "expanon:distortion-boost-and-overdrive-carl-martin-heavy-drive": {"R67": "100k", "R68": "100k"},
    "expanon:delay-echo-and-samplers-ibanez-ad9": {"U4": "MN3102"},
    "expanon:distortion-boost-and-overdrive-nobels-dt-1": {
        "R14": "390K", "R105": "1K5", "C1": "0.22µF", "C11": "0.68µF", "C23": "1µF", "C24": "1µF", "C31": "1µF", "C40": "1µF",
        "C41": "3.3µF", "C201": "220µF", "C202": "220µF", "C203": "47µF", "D1": "1N4148", "D2": "Red LED", "D3": "Red LED",
        "D4": "1N4148", "D5": "1N4148", "D6": "1N4148", "D7": "1N4148", "D8": "1N4148", "D101": "1N4148", "D201": "1N4001",
        "Q2": "K222E", "Q3": "K222E", "Q4": "C1571G", "Q5": "K222E", "Q6": "K30A-Y", "Q7": "K30A-Y", "U101": "4007",
    },
    "expanon:distortion-boost-and-overdrive-nobels-distortion-xtreme": {
        "R12": "33K", "R14": "430K", "R15": "330", "R33": "1K8", "R36": "2K0", "R62": "15K", "R64": "750K", "R65": "2K2",
        "R71": "3K3", "R73": "200K", "R203": "100", "C31": "0.1µF",
    },
    "expanon:fuzz-and-fuzzy-noisemakers-nobels-fu-z": {
        "R6": "1K", "R11": "10K", "R44": "470", "R108": "1M", "C2": "1µF", "C11": "0.1µF", "C12": "1µF", "C21": "0.1µF",
        "C31": "0.1µF", "C33": "1µF", "C34": "27N", "C41": "1µF", "C42": "1µF", "C43": "2.2µF", "C201": "220µF",
        "C202": "100µF", "C203": "47µF", "Q1": "K222E", "Q2": "K30A-Y", "Q4": "K30A-Y", "Q5": "K30A-Y", "Q11": "C2240BL",
        "Q21": "C2240BL", "Q31": "C2240BL", "Q41": "C2240BL", "ATTACK": "A30K", "TONE": "A30K",
    },
    # The .jpg files of titles the archive also holds as .pdf (the plain id; the .pdf is its own board).
    "expanon:full-synths-drum-synths-and-misc-synth-moog-taurus": {
        "R132": "1K", "R134": "22K", "R203": "22K", "R213": "10K", "R304": "33K", "R305": "2.2M",
        "R307": "2.2K", "R308": "10K", "R310": "12K", "R406": "20K", "R523": "330", "R527": "47K",  # R147 is 47.5K MF as drawn; R202 and R707 are the Sustain and Osc B Tune pots (2026-10-09)
    },
    "expanon:delay-echo-and-samplers-digitech-pds2020": {"R60": "47K", "R90": "22K", "U22": "LM358", "D16": "1N4148"},  # LM958 is no part; D16 drawn 1N414B
    "expanon:oscillators-lfos-and-signal-generators-ar-317-vco": {"U3": "LM301A"},
    "expanon:oscillators-lfos-and-signal-generators-ar-324-lag-and-lfo": {"R32": "120K"},
    "expanon:oscillators-lfos-and-signal-generators-e-music-vcdo": {"R9": "100k", "R14": "1M5"},
    "expanon:oscillators-lfos-and-signal-generators-ehx-lfo": {"D1": "1N4001", "R9": "27k"},
    "expanon:oscillators-lfos-and-signal-generators-moog-901a": {"R4": "680K", "R5": "4.7M"},
    "expanon:oscillators-lfos-and-signal-generators-moog-901b": {
        "Q10": "2N2646", "R312": None, "R32": "22K", "R29": "13K", "R30": "43K",  # R312 is R32 misread (R2 is 330, read by eye 2026-10-09)
    },
    "expanon:phasers-dod-fx20c": {"R27": "10K"},
    "expanon:phasers-ibanez-pt909": {"C106": "100P", "R134": "4.7K", "Q104": "2SK30AY"},  # Q104: legend 'Q101~104: 2SK30AY (SELECTED)' (2026-10-09)
    "expanon:phasers-nobels-ph-d": {
        "R4": "68K", "R5": "33K", "R6": "24K", "R62": "2K7", "R65": "1M", "R71": "12K", "R72": "56K", "R73": "470",
        "C1": "47N", "C2": "2.2µF", "C62": "2.2µF", "C63": "2.2µF", "C72": "10µF", "C81": "47µF", "C82": "4.7µF",
        "C201": "220µF", "C202": "47µF", "C203": "47µF", "D63": "1N4148", "D201": "1N4001", "Q1": "K222E",
        "Q11": "C2362G", "Q21": "C2362G", "Q31": "C2362G", "Q41": "C2362G", "Q61": "K30A-Y", "Q71": "K30A-Y",
        "Q81": "C2240BL", "U101": "4007", "U2": "LM358", "FEEDBACK": "B10K", "VOLUME": "A50K", "SPEED": "C1M",
        "INTENSITY": "B100K", "RANGE": "B10K",
    },
    "expanon:tone-control-and-eqs-ibanez-be-10-graphic-bass-eq": {"R3": "100K", "R25": "330"},
    "expanon:tone-control-and-eqs-ibanez-graphic-eq": {"R3": "100K", "R25": "330"},
    # Part numbers that do not exist, typos for the 1N4148 and 2N2222A in the documents or their reading;
    # found while linking datasheets (2026-10-09). The 2N5008 (Dunwich Cthulhu, Whippoorwill) and NP4124
    # (DOD 280) are printed that way in the originals and stay.
    "bentfishbowl:pelota-2-pt2399-delay": {"D1": "1N4148"},
    "fuzzdog:emperor": {"D5": "1N4148", "D6": "1N4148"},
    "rwlpedal:yellow-rumped-fuzz": {"D1": "1N4148"},
    "fivecats:the-m-drive-emerson-custom-em-drive-transparent-overdrive-clone": {"Q1": "2N2222A"},
    "fivecats:scorpion-boost": {"Q1": "2N2222A"},
    "madbean:freeloader": {"Q1": "2N2222A", "Q3": "2N2222A"},
    "otrfx:warm-fuzzies": {("Ritual Fuzz", "C"): "2N2222A"},
    # Transistor audit (checked against each document 2026-10-09).
    # Typos printed in the docs themselves:
    "moonn:powerlifter": {"Q1": "2N3904"},  # parts list prints 1N3904
    "parasit:higgsparticle": {"Q1": "2N3904"},  # prints 3N3904
    "fuzzdog:rattlecrow": {("RATTLE CROW", "Q1"): "2SC1815**"},  # the Rattle Crow table prints 2NC1815; the Dirty Bird one 2SC1815
    "deadendfx:flange-a-rama": {"Q1": "2SC2458BL", "Q2": "2SC2458BL",  # prints 2SC24588L: the BL grade of the 2SC2458
                                "C45": None, "IC6": "MN3204"},  # 'C45 706' is OCR of the IC1 C4570C row; MIN3204 a slip
    "opelectronics:hot-tubes": {"C5": "4.7u", "C6": "4.7u", "C15": "4.7u", "C16": "4.7u"},  # read .7u: the 4 taken for the quantity
    "fuzzdog:scrambler": {"R12": None},  # '*': a jumper in place of the R12 trimmer, not a part
    "deadendfx:kakehashi-s-nightmare": {"Q6": "BS170"},  # the schematic prints bs1707
    "deadendfx:redstone": {"Q6": "MPF102", "Q7": "J201", "Q8": "J201"},  # the doc's own 2019 erratum: MPF201 and J102 were typos
    "fuzzdog:tweed55": {f"Q{i}": "MPF4393/MMBF4393*" for i in range(1, 6)},  # prints MBF4393
    # OCR misreads of clean print:
    "deadendfx:trahald": {"Q6": "BS250"},  # read B5250
    "deadendfx:fugu": {"Q3": "PN2222A"},  # read PN22234
    "deadendfx:by-eck": {"Q6": "J113"},  # read 3113
    "guitarpcb:nostalgitone-doom-prophet": {"Q1": "J113"},  # read 4113; the notes name the J113 at Q1
    "zerogiod:vitarium-fuzz-pcb-and-faceplate": {"Q5": "2N1711"},  # read 2Nt711
    "otherpedals:super-murid-64-pcb": {"Q2": "2N5458"},  # read '7 2N5458'
    "tayda:ea-tremolo": {"Q3": "2N5457"},  # a stray '31' from the next column
    "deadastronaut:nano-8-midi-drums": {"Q5": None},  # 'Qs 2.1mm DC sockets': no transistor
    # Rows shifted or split by the table parsers:
    "dirtmonger:fuzz-face-diy-pcb": {"Q1": "NPN Germanium (BC108C, BC109 etc.)", "Q2": "NPN Germanium (BC108C, BC109 etc.)", "D1": "coloured LED"},
    "lectricfx:bloozehound-overdrive": {"Q1": "JFET*", "Q2": "JFET*", "Q4": "JFET*", "Q5": "JFET*"},  # '*' in the table: matched JFETs, 2SK117 suggested; Q5 had 6k8 from the quantities table
    "guitarelectronics:bassdrive": {"Q1": "2N3904", "Q2": "2N7000"},  # the shopping list's quoted designators were read as values
    "effects1776:britannia": {"Q2": None, "Q4": None, "TRIMQ2": "50k trimmer", "TRIMQ4": "50k trimmer"},  # 'Trim Q2  50k': the bias trimmers
    "effectslayouts:earthbender": {"Q1": "Low gain NPN silicon", "Q2": "Low gain NPN silicon", "Q3": "Low gain NPN silicon"},
    "fuzzdog:utilface": {"Q1": "Low-medium gain BJT***", "Q2": "Low-medium gain BJT***"},  # *** any low-medium gain NPN or PNP
    "tayda:fuzz-face": {"Q1": "2N3906 / BC108 / BC109", "Q2": "2N3906 / BC108 / BC109"},  # PNP 2N3906, or NPN BC108 or BC109
    "moody:tremolito-kit": {"=2N5809": "2N5089"},  # a typo for the 2N5089 (confirmed by Lane, 2026-10-09)
    "tayda:fuzz-face-with-inverter": {"Q1": "2N3906 / BC108 / BC109", "Q2": "2N3906 / BC108 / BC109"},
    # Experimentalists Anonymous: a legend or note value paired with the wrong designator (each label viewed, 2026-10-09).
    "expanon:distortion-boost-and-overdrive-ibanez-ts-10": {**{f"Q{i}": "2SC1815" for i in range(1, 7)}, "Q7": "2SK118", "Q8": "2SK118", "D1": "1N4001"},  # the drawing's note: 'Q1 to Q6 are 2SC1815, Q7 and Q8 are 2SK118'
}

# circuit_id -> [(ref, value, category, note)], read off the document by a person.
_FIVE_CATS_FUZZ_FACE = [
    ("Q1", "BC108", "Q", "hFE 250-300; collector 1.35V"), ("Q2", "BC108", "Q", "hFE 250-300; collector 5.75V"),
    ("×1", "1N5817", "D", ""), ("×1", "47pF", "C", ""), ("×1", "100nF", "C", ""), ("×1", "2.2uF", "C", ""),
    ("×1", "22uF", "C", ""), ("×1", "100uF", "C", ""), ("×1", "10R", "R", ""), ("×1", "330R", "R", "1K for more volume"),
    ("×1", "3.1K", "R", ""), ("×1", "4.7K", "R", "LED"), ("×1", "20K", "R", ""), ("×1", "82K", "R", ""),
    ("Fuzz", "B1K", "POT", "or C1K"), ("Vol", "A500K", "POT", ""),
]
def _variant_table(variants: list[str], rows: list[tuple]) -> list[tuple]:
    """A per-variant chart written as (ref, category, value per variant...); 'omit' or 'jumper' leaves the
    part out, and 'value|note' carries a note for that cell."""
    out = []
    for v_i, v in enumerate(variants):
        for ref, cat, *vals in rows:
            note = ""
            val = vals[v_i]
            if val.lower() in ("omit", "jumper"):
                continue
            if "|" in val:
                val, note = val.split("|", 1)
            elif val.endswith("*"):
                val, note = val.rstrip("*"), "1N34A are good replacements"
            out.append((ref, val, cat, note, v))
    return out


_DRIVESTORTION = _variant_table(
    ["DOD '77 Grey 250", "MXR '80 Distortion+", "DOD '82 Yellow 250", "Ross Tan Distortion", "DeArmond Square Wave", "DOD YJM308"],
    [("R1", "R", "1M", "1M", "1M", "1M", "1M", "1M"), ("R2", "R", "10k", "10k", "10k", "10k", "10k", "10k"),
     ("R3", "R", "510k", "1M", "470k", "1M", "1M", "470k"), ("R4", "R", "20k", "1M", "22k", "1M", "1M", "22k"),
     ("R5", "R", "20k", "1M", "22k", "1M", "1M", "22k"), ("R6", "R", "4.7k", "4.7k", "4.7k", "4.7k", "5.6k", "4.7k"),
     ("R7", "R", "1M", "1M", "1M", "1M", "1M", "1M"), ("R8", "R", "10k", "10k", "10k", "10k", "10k", "10k"),
     ("C1", "C", "omit", "1n", "omit", "1n", "1.5n", "omit"), ("C2", "C", "10n", "10n", "10n", "10n", "10n", "1n"),
     ("C3", "C", "10u", "1u", "10u", "10u", "1u", "10u"), ("C4", "C", "47u", "47u", "47u", "47u", "47u", "47u"),
     ("C5", "C", "47n", "47n", "47n", "47n", "47n", "47n"), ("C6", "C", "omit", "omit", "25p", "omit", "15p", "25p"),
     ("C7", "C", "4.7u", "1u", "4.7u", "1u", "1u", "4.7u"), ("C8", "C", "1n", "1n", "1n", "1n", "1.5n", "1n"),
     ("D1", "D", "1N4001", "1N4001", "1N4001", "1N4001", "1N4001", "1N4001"),
     ("D2", "D", "1N4001", "1N270*", "1N4148", "1N4148", "1N34A", "1N4148"),
     ("D3", "D", "1N4001", "1N270*", "1N4148", "1N4148", "1N34A", "1N4148"),
     ("D4", "D", "jumper", "jumper", "jumper", "1N4148", "jumper", "jumper"),
     ("IC1", "IC", "LM741", "UA741CP", "LF351N", "RC4558P", "UA741C", "KA4558"),
     ("Gain", "POT", "C500k", "C1M", "C1M", "C500k", "C500k", "C500k"),
     ("Level", "POT", "A100k", "A10k", "A10k", "B50k", "A10k", "W100k")])

_EL_REY_II = _variant_table(
    ["Blues Breaker", "Morning Glory", "King of Tone", "Ultimate King of Tone"],
    [("RPD", "R", *["1M|1M to 2M2"] * 4), ("R1", "R", *["1M"] * 4), ("R2", "R", "3k3", "3k3", "33k", "33k"),
     ("R3", "R", "4k7", "4k7", "27k", "27k"), ("R4", "R", *["10k"] * 4), ("R5", "R", *["220k"] * 4),
     ("R6", "R", *["6k8"] * 4), ("R7", "R", *["1k"] * 4), ("R8", "R", *["6k8"] * 4), ("R9", "R", *["1M"] * 4),
     ("R10", "R", *["47k"] * 4), ("R11", "R", *["47k"] * 4), ("RX1", "R", "omit", "68k", "omit", "68k"),
     ("RX2", "R", "omit", "1M", "omit", "1M"), ("RX3", "R", "omit", "22k", "omit", "22k"),
     ("RX4", "R", "omit", "12k", "omit", "12k"), ("RX5", "R", "omit", "12k", "omit", "12k"),
     ("RX6", "R", "omit", "100k", "omit", "100k"),
     *[(d, "D", "1N914", "1N4148", "MA856|BA282 a suggested sub", "MA856|BA282 a suggested sub") for d in ("D1", "D2", "D3", "D4")],
     ("D9", "D", "omit", "omit", "1S1588", "1S1588"), ("D10", "D", "omit", "omit", "1S1588", "1S1588"),
     ("D11", "D", *["1N4001|polarity protection; any 1N400x"] * 4),
     ("C1", "C", "10nF", "47nF", "10nF", "10nF"), ("C2", "C", "47pF", "47pF", "100pF", "100pF"),
     ("C3", "C", *["10nF"] * 4), ("C4", "C", *["10nF"] * 4), ("C5", "C", *["100nF"] * 4), ("C6", "C", *["10nF"] * 4),
     ("C7", "C", *["10nF"] * 4), ("C8", "C", "100nF", "jumper", "1uF", "1uF"), ("C10", "C", *["100uF"] * 4),
     ("C11", "C", *["100uF"] * 4), ("CX1", "C", "omit", "100pF", "omit", "100pF"), ("CX2", "C", "omit", "470pF", "omit", "470pF"),
     ("CX3", "C", "omit", "100nF", "omit", "100nF"), ("CX4", "C", "omit", "10uF", "omit", "10uF"),
     ("CX5", "C", "omit", "omit", "1uF", "1uF"), ("CX6", "C", "jumper", "2u2", "jumper", "jumper"),
     ("IC1", "IC", "TL072", "LM833N", "JRC4580", "JRC4580"), ("Q1", "Q", "omit", "2N5457", "omit", "2N5457"),
     ("Gain", "POT", *["B100k"] * 4), ("Pres", "TRIM", *["50k|trimpot"] * 4), ("Tone", "POT", *["B25k"] * 4),
     ("Vol", "POT", *["A100k"] * 4), ("Bright Cut", "SW", "omit", "SPDT on-off-on", "omit", "SPDT on-off-on"),
     ("Hard Clip", "SW", "omit", "omit", "SPDT on-on", "SPDT on-on"), ("Clip", "SW", "omit", "omit", "omit", "SPDT on-off-on")])

TRANSCRIBED: dict[str, list[tuple]] = {
    # delyk El Rey de la Gloria Azul II: four versions over tables whose wrapped headers and multi-word
    # cells defeat the column parsers (checked 2026-10-05). D5-D8 on the Ultimate KoT are the builder's
    # pick of clipping diodes (see the doc's modifications), so they are left out.
    "delyk:el-rey-de-la-gloria-azul-ii": _EL_REY_II,
    # Effects Layouts Lawn Darts: a single scanned schematic; OCR read 8 junk-ridden labels (checked 2026-10-02).
    "effectslayouts:lawn-darts": [
        ("R1", "1M", "R", ""), ("R2", "100R", "R", ""), ("R3", "10M", "R", ""), ("R4", "1.3k", "R", ""), ("R5", "100k", "R", ""),
        ("CLR", "4.7k", "R", "LED"), ("C1", "100p", "C", ""), ("C2", "4.7n", "C", ""), ("C3", "10n", "C", ""),
        ("C4", "100u", "C", ""), ("D1", "1N4001", "D", ""), ("Q1", "2N5089", "Q", ""), ("Level", "B10k", "POT", ""),
    ],
    # Effects Layouts Drivestortion: a six-version chart whose text layer is a broken font (checked 2026-10-02).
    "effectslayouts:drivestortion": _DRIVESTORTION,
    # Five Cats inserts that are wiring diagrams with the values printed on the parts (checked 2026-10-02).
    "fivecats:marshall-supa-fuzz-replica-vintage": [
        ("Q1", "Germanium PNP", "Q", "hFE about 174"), ("Q2", "Germanium PNP", "Q", "hFE about 208"),
        ("Q3", "Germanium PNP", "Q", "hFE about 194"), ("×1", "10nF", "C", ""), ("×1", "100nF", "C", ""),
        ("×2", "10uF", "C", ""), ("×1", "47uF", "C", ""), ("×1", "470R", "R", "1K for more volume"),
        ("×1", "8.2K", "R", ""), ("×2", "10K", "R", ""), ("×1", "47K", "R", ""), ("×1", "100K", "R", ""),
        ("Fuzz", "B1K", "POT", ""), ("Vol", "A100K", "POT", ""),
    ],
    # Eff Dub Audio posts whose only schematic is an image; transcribed from it (checked 2026-10-07).
    # Parts the drawing leaves without a value (Dead Easy Dirt D2/D3, SmallBazz D1/D2 and C3) are
    # the builder's pick and left out.
    "effdub:wahscillator": [
        ("R1", "2M2", "R", ""), ("R2", "2K2", "R", ""), ("R3", "470K", "R", ""), ("R4", "1M", "R", ""), ("R5", "1M", "R", ""),
        ("R6", "1M", "R", ""), ("R7", "10K", "R", ""), ("R8", "10K", "R", ""), ("R9", "470K", "R", ""), ("R10", "2M2", "R", ""),
        ("R11", "220K", "R", ""), ("R12", "220K", "R", ""), ("R13", "220K", "R", ""), ("R14", "220K", "R", ""), ("R15", "2K2", "R", ""),
        ("R16", "1K", "R", ""), ("R17", "1K", "R", ""), ("R18", "470R", "R", ""), ("R19", "100R", "R", ""), ("R20", "100R", "R", ""),
        ("R21", "100K", "R", ""), ("R22", "100K", "R", ""), ("C1", "100n", "C", ""), ("C2", "220p", "C", ""), ("C3", "1u", "C", ""),
        ("C4", "22u", "C", ""), ("C5", "680p", "C", ""), ("C6", "6n8", "C", ""), ("C7", "22u", "C", ""), ("C8", "100n", "C", ""),
        ("C9", "1u", "C", ""), ("C10", "10n", "C", ""), ("C11", "10u", "C", ""), ("C12", "47u", "C", ""), ("C13", "47u", "C", ""),
        ("C14", "47u", "C", ""), ("D1", "1N4148", "D", ""), ("Q1", "MPSA13", "Q", ""), ("IC1", "TL072", "IC", ""), ("IC2", "4558", "IC", ""),
        ("OK1", "H11F1M", "OPTO", ""), ("Bias", "1M", "TRIM", ""), ("Speed", "A250K", "POT", ""), ("Depth", "B2K", "POT", ""),
    ],
    "effdub:cmos-eisley-cd4049-tremolo": [
        ("R1", "100K", "R", ""), ("R2", "100K", "R", ""), ("R3", "100K", "R", ""), ("R4", "100K", "R", ""), ("R5", "100K", "R", ""),
        ("R6", "220K", "R", ""), ("R7", "220K", "R", ""), ("R8", "470R", "R", ""), ("R9", "2K2", "R", ""), ("R10", "100R", "R", ""),
        ("C1", "47p", "C", ""), ("C2", "47n", "C", ""), ("C3", "47n", "C", ""), ("C4", "220n", "C", ""), ("C5", "4u7", "C", ""),
        ("C6", "4u7", "C", ""), ("C7", "4u7", "C", ""), ("C8", "100u", "C", ""), ("D2", "LED", "LED", "rate indicator"),
        ("D3", "BAT41", "D", ""), ("IC1", "CD4049", "IC", ""), ("VACT1", "LED + LDR", "OPTO", "vactrol (VACT 1A / 1B)"),
        ("Speed", "B50K", "POT", ""), ("Depth", "B500K", "POT", ""), ("Vol", "B100K", "POT", ""),
    ],
    "effdub:shoot-the-moon-tremolo": [
        ("R1", "220K", "R", ""), ("R2", "220K", "R", ""), ("R3", "220K", "R", ""), ("R4", "220K", "R", ""), ("R5", "2K2", "R", ""),
        ("R6", "1K", "R", ""), ("R7", "1K", "R", ""), ("R8", "470R", "R", ""), ("R9", "1K", "R", ""), ("R10", "1K", "R", ""),
        ("R11", "1M", "R", ""), ("R12", "220K", "R", ""), ("R13", "220K", "R", ""), ("R14", "100K", "R", ""), ("R15", "100K", "R", ""),
        ("R16", "100R", "R", ""), ("C1", "10n", "C", ""), ("C2", "10u", "C", ""), ("C3", "1u", "C", ""), ("C4", "330p", "C", ""),
        ("C5", "1u", "C", ""), ("C6", "100u", "C", ""), ("C7", "47u", "C", ""), ("C8", "47u", "C", ""), ("D1", "LED", "LED", ""),
        ("D2", "LED", "LED", ""), ("D3", "1N4001", "D", ""), ("IC1", "4558", "IC", ""), ("IC2", "TL072", "IC", ""),
        ("LDR1", "LDR", "OPTO", ""), ("Speed", "B100K", "POT", ""), ("Wave", "B500K", "POT", ""), ("Depth", "B1K", "POT", ""),
        ("Gain", "B10K", "POT", ""),
    ],
    "effdub:dead-easy-dirt-v2-reboot": [
        ("R2", "1M", "R", ""), ("C2", "47n", "C", ""), ("C3", "100n", "C", ""), ("C4", "100u", "C", ""), ("D1", "BAT41", "D", ""),
        ("IC1", "LM386", "IC", ""), ("Vol", "A100K", "POT", ""),
    ],
    "effdub:electra-distortion-schematic-and-layouts": [
        ("×1", "2M2", "R", ""), ("×1", "47K", "R", ""), ("×1", "680R", "R", ""), ("×2", "100n", "C", ""), ("×1", "2N3904", "Q", ""),
        ("×1", "1N4148", "D", ""), ("×1", "1N34A", "D", ""), ("Volume", "A100K", "POT", ""),
    ],
    "effdub:germanium-bazz-fuss": [
        ("R1", "1M", "R", ""), ("R2", "470R", "R", ""), ("R3", "1K", "R", ""), ("R4", "1K", "R", ""), ("C1", "100p", "C", ""),
        ("C2", "100n", "C", ""), ("C4", "1u", "C", ""), ("C5", "47u", "C", ""), ("C6", "100n", "C", ""), ("D3", "BAT41", "D", ""),
        ("Q1", "2N1101", "Q", ""), ("Q2", "2N1101", "Q", ""), ("SW1", "SPDT", "SW", "Si / Ge clipping diode select"),
        ("Bias", "10K", "TRIM", ""), ("Fuzz", "B1K", "POT", ""), ("Vol", "A100K", "POT", ""),
    ],
    # Experimentalists Anonymous Basic Saw VCO (Ian Fritz): OCR read U2's CA3140 as D1's value. Read by eye
    # from the schematic 2026-10-08; D1 and D11 are drawn with no part number. R13 is half hidden by the
    # tempco's dashed outline and reads as 56K.
    "expanon:oscillators-lfos-and-signal-generators-basic-saw-vco": [
        ("R1", "10K", "R", "1%"), ("R2", "100K", "R", "1%"), ("R3", "100K", "R", "1%"), ("R4", "180K", "R", ""),
        ("R5", "6.8K", "R", ""), ("R6", "100K", "R", "1%"), ("R7", "301K", "R", "1%"), ("R8", "680K", "R", ""),
        ("R9", "180K", "R", ""), ("R11", "910", "R", ""), ("R12", "150", "R", ""), ("R13", "56K", "R", "partly hidden on the schematic"),
        ("R15", "15K", "R", ""), ("R18", "1K", "R", ""), ("R19", "2.2K", "R", ""), ("R66", "100K", "R", "1%"),
        ("RTC1", "1K", "R", "tempco resistor"), ("C1", "0.47uF", "C", ""), ("C2", "2200pF", "C", ""), ("C3", "100pF", "C", ""),
        ("C4", "43pF", "C", ""), ("C5", "360pF", "C", ""), ("D1", "Diode", "D", "no part number given"),
        ("D11", "Diode", "D", "no part number given"), ("Q1", "MAT04", "Q", "Q1 and Q2 are one MAT04 quad matched pair"),
        ("Q2", "MAT04", "Q", ""), ("Q3", "2N4391", "Q", ""), ("U1", "TL084", "IC", ""), ("U2", "CA3140", "IC", ""),
        ("U3", "LM319", "IC", ""), ("RANGE1", "SPDT", "SW", "range"), ("V/Oct", "10K", "TRIM", "10-turn"),
        ("Freq", "B10K", "POT", ""), ("FM Level", "A10K", "POT", ""),
    ],
    "fivecats:vintage-style-fuzz-face": _FIVE_CATS_FUZZ_FACE,
    "fivecats:vintage-style-fuzz-face-1590b": _FIVE_CATS_FUZZ_FACE,
}

# circuit_id -> control names, for a board whose document names its knobs but gives no values to
# list them as parts rows with (the DVF schematic labels P1-P6; the parts page leaves them out).
CONTROLS: dict[str, list[str]] = {
    "guitarpcb:dvf-dual-voice-filter-tonal-shifter-cocked-wah-w-switchable-overdrive":
        ["Gain", "Freq 1", "Freq 1 Level", "Freq 2", "Freq 2 Level", "Clean Level"],
}

_NOTE = "corrected by hand"
_READ_NOTE = "read from the schematic by eye"
_READ: set[str] = set()
for _f in sorted((Path(__file__).parent / "transcribed").glob("*.json")):
    _d = json.loads(_f.read_text())
    TRANSCRIBED[_d["id"]] = [tuple(r) for r in _d["rows"]]
    _READ.add(_d["id"])


def _split(ref: str) -> tuple[str, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref.upper())
    return (m.group(1), int(m.group(2))) if m else (ref.upper(), -1)


def _insert_at(bom: list[BomRow], variant: str, ref: str) -> int:
    """Index after the nearest lower designator of the same kind in the variant, else after the
    variant's last row, else at the end."""
    prefix, num = _split(ref)
    best, last = -1, -1
    for i, r in enumerate(bom):
        if r.variant != variant:
            continue
        last = i
        p, n = _split(r.ref)
        if p == prefix and n < num:
            best = i
    return (best if best >= 0 else last) + 1 if last >= 0 else len(bom)


def apply(circuit_id: str, bom: list[BomRow]) -> list[BomRow]:
    if circuit_id in TRANSCRIBED:
        how = _READ_NOTE if circuit_id in _READ else _NOTE
        bom = [normalize_row(BomRow(ref=ref, value=value, category=cat, notes="; ".join(n for n in (note, how) if n),
                                    part_type="Potentiometer" if cat == "POT" else "", variant=(rest or [""])[0]))
               for ref, value, cat, note, *rest in TRANSCRIBED[circuit_id]]
    fixes: dict[tuple[str | None, str], str | None] = {}
    for k, v in (CORRECTIONS.get(circuit_id) or {}).items():
        variant, ref = k if isinstance(k, tuple) else (None, k)
        fixes[(variant, ref.upper())] = v
    if not fixes:
        return bom
    seen: set[tuple[str | None, str]] = set()
    out: list[BomRow] = []
    for r in bom:
        key = (r.variant, r.ref.upper()) if (r.variant, r.ref.upper()) in fixes else (None, r.ref.upper())
        if key not in fixes and (None, "=" + r.value.upper()) in fixes:
            key = (None, "=" + r.value.upper())  # a shopping-list row ('×1') named by its value
        if key in fixes:
            seen.add(key)
            value = fixes[key]
            if value is None:
                continue
            if r.value != value:
                r.value, r.category, r.norm_value = value, "", ""
                r.notes = "; ".join(n for n in (r.notes, _NOTE) if n)
                normalize_row(r)
        out.append(r)
    for (variant, ref), value in fixes.items():
        if value is None or (variant, ref) in seen or ref.startswith("="):
            continue
        cat = ""
        if re.fullmatch(r"[A-Z]{3,}\d?", ref) and (re.match(r"^[ABCW]\d", value) or re.search(r"\btrim", value, re.I)):  # VOL2, GAIN1, PRES1; not RPD1 1M
            cat = "TRIM" if re.search(r"\btrim", value, re.I) else "POT"
        row = normalize_row(BomRow(ref=ref, value=value, notes=_NOTE, variant=variant or "", category=cat))
        out.insert(_insert_at(out, row.variant, ref), row)
    return out
