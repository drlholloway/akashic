"""Hand corrections to parts rows that no parser rule can make, each checked against the source
document by a person. Applied whenever a board is stored (db.upsert_circuit), after every parser has
run, so a rescrape keeps them. A value of None removes the row; a value for a row the parsers missed
adds it, after the nearest lower designator of its kind. Add a line per report, with where it came
from; remove it when a parser learns to read the board right.

    CORRECTIONS[circuit_id][designator] = corrected value, or None to drop the row
    CORRECTIONS[circuit_id][(variant, designator)] = the same, for one build variant only
    (designators match regardless of case: 'CLEAN' corrects a knob stored as 'Clean')

A document no parser can read (values printed on the parts of a wiring drawing) can be transcribed
whole instead: TRANSCRIBED[circuit_id] is its parts list, which replaces whatever the parsers found.
Rows without designators are named by quantity ('×2'), as the shopping-list parser names them. A
five-field row carries its build variant ('DOD \u201977 Grey 250').
"""
from __future__ import annotations

import re

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
    # Experimentalists Anonymous scans: values a wider pairing pass found and lost again, plus pin
    # numbers and pin names paired as values, each read off the drawing (checked 2026-10-01).
    "expanon:vibrato-and-pitch-shift-boss-oc-2": {
        "Q1": None, "Q2": None,  # MC14013 / MC14027 pin names, not transistors
        "R17": "1M", "R18": "1M", "R19": "47K", "R28": "47K", "R30": "47K", "R48": "470K", "R52": "10k",
        "R20": "33K", "R21": "68k", "R24": "10k", "R26": "100R", "R27": "10k",
    },
    "expanon:filters-wahs-and-vcfs-tau-1010-ladder-filter": {
        "R2": "100K", "R6": "100K", "R7": "12K", "R15": "100K", "R18": "6.8K", "R21": "91K", "R29": "26K",
        "R34": "680", "C1": "0.01uF", "C2": "0.01uF", "C3": "0.01uF", "C4": "0.01uF", "C5": "18pF", "C6": "18pF",
        "C7": "0.05uF", "D1": "1N4148", "D2": "1N4148", "U1": "LM301A",
    },
    # A clean CAD drawing of which the pairing read 14 rows, two of them wrong (R16 1100k, R20 122k).
    "expanon:phasers-univox-microphaser": {
        **{f"R{n}": "100k" for n in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 19)},
        "R1": "220k", "R2": "220k", "R3": "470k", "R17": "2k2", "R18": "1k", "R20": "22k", "R22": "47k",
        "R24": "2k7", "R25": "3k3", "R31": "1M",
        **{f"C{n}": "50n" for n in range(1, 6)},
        "C6": "1µ", "C7": "33µ", "C8": "10µ", "C9": "4µ7 Ta", "D1": "ZPD 4V7", "BIAS": "100k trim",  # TP1, labeled BIAS
        **{f"Q{n}": "2SK34D" for n in range(1, 5)}, **{f"OP{n}": "1458" for n in range(1, 7)},
        "RATE": "A1M",
    },
    # Experimentalists Anonymous: values a wider pairing pass proposed (2026-10-01 run with the mutual-nearest
    # pass on every board), each looked up on the drawing; where the pass misread a value, the drawing's value
    # is used. The Nobels CO-2 and PH-D are clean CAD drawings, transcribed in full.
    "expanon:adsr-generators-and-envelope-generators-ems-vcs3-envelope-generator": {"R146": "1k0"},
    "expanon:amplifiers-and-vcas-moog-902": {"Q2": "2N4058"},
    "expanon:chorus-boss-ce-2": {"C16": "100P", "C26": "220p", "C27": "220p"},
    "expanon:chorus-ibanez-pc10": {
        "C17": "100P", "C28": "100P", "R61": "330", "R77": "22K", "R88": "82K", "R107": "620K",
    },
    "expanon:chorus-ibanez-sc10": {"R66": "10K"},
    "expanon:chorus-rocktek-chorus": {"R44": "10K"},
    "expanon:compressors-gates-and-limiters-ibanez-cp10": {"Q2": "2SC2458GR", "Q6": "2SC2458GR"},
    "expanon:compressors-gates-and-limiters-korg-noise-gate": {"IC1": "NJM4558DV"},
    "expanon:compressors-gates-and-limiters-korg-noise-gate-ngt-1": {"IC3": "LM358"},
    "expanon:compressors-gates-and-limiters-nobels-co-2": {
        "R11": "33K", "R21": "22K", "R23": "4K7", "R36": "1M", "R43": "43K", "R44": "56K", "R52": "1M", "R61": "1K",
        "R72": "1M", "R83": "470", "R102": "100K", "R105": "2K2", "C1": "220µF", "C2": "100µF", "C12": "22µF",
        "C31": "2.2µF", "C34": "10N", "C35": "10µF", "C43": "22µF", "C51": "2.2µF", "C61": "2.2µF", "C81": "2.2µF",
        "C82": "2.2µF", "C203": "47µF", "D51": "1N4148", "D102": "3mm Green LED", "Q11": "K222E", "Q31": "C2240BL",
        "Q32": "C2240BL", "Q33": "C2240BL", "Q41": "C2240BL", "Q51": "K30A-Y", "Q61": "C2362G", "Q71": "K30A-Y",
        "Q81": "C2362G", "U101": "4007", "SUSTAIN": "B250K", "ATTACK": "B100K", "VOLUME": "A50K",
    },
    "expanon:delay-echo-and-samplers-boss-dd-2": {"C29": "1µF", "C42": "10P", "R17": "1K", "R51": "1K"},
    "expanon:delay-echo-and-samplers-holtek-echo": {"C2": "10µF", "R2": "120K", "R5": "4.7K"},
    "expanon:delay-echo-and-samplers-ibanez-em5": {"R31": "56K", "R43": "9.1K"},
    "expanon:delay-echo-and-samplers-morley-emerald-echo": {"R10": "8.2K", "R31": "820"},
    "expanon:distortion-boost-and-overdrive-boss-df2": {
        "Q2": "2SC732TM-GR", "Q3": "2SK30A-Y", "Q6": "2SC732TM-GR", "R21": "6.8k",
    },
    "expanon:distortion-boost-and-overdrive-dod-fx54": {
        "D9": "1N4148", "U2": "LM3080", "R6": "220K", "R10": "2k", "R11": "6.8K", "R30": "100K", "R40": "47K",
        "R43": "330K",
    },
    "expanon:distortion-boost-and-overdrive-ibanez-bn5-black-noise": {
        "C1": "0.047uF", "C26": "1000pF", "D4": "1N4148", "R8": "300", "R19": "1M", "R25": "100", "R31": "68K",
        "R46": "22K",
    },
    "expanon:distortion-boost-and-overdrive-marshall-guvnor": {"R6": "680k"},
    "expanon:filters-wahs-and-vcfs-buchla-291-bandpass-vcf": {"C10": "10uF", "R24": "68", "R36": "68K"},
    "expanon:filters-wahs-and-vcfs-ibanez-afl-auto-filter": {"R6": "22K", "R20": "1M", "R53": "1K"},
    "expanon:filters-wahs-and-vcfs-minimoog-ladder-vcf-2": {"R32": "150", "R41": "150", "R46": "68K", "R67": "200"},
    "expanon:filters-wahs-and-vcfs-moog-minimoog-filter": {"R32": "150", "R41": "150", "R46": "68K", "R67": "200"},
    "expanon:flangers-dod-fx75b": {"C11": "15uF NP", "C20": "120pF", "R52": "220K", "R53": "7.5K", "R57": "22K"},
    "expanon:flangers-ibanez-fl301": {"C123": "180P", "R149": "510K"},
    "expanon:flangers-morley-sapphire-flanger": {"R19": "33K"},
    "expanon:full-synths-drum-synths-and-misc-synth-ar-318-sample-and-hold-and-noise-generato": {
        "Q2": "2N3393", "Q10": "2N4870",
    },
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-100": {"R23": "82K", "R134": "100K"},
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-110": {"R23": "82K", "R134": "100K"},
    "expanon:full-synths-drum-synths-and-misc-synth-boss-dr-55": {"IC3": "CD4011UB"},
    "expanon:full-synths-drum-synths-and-misc-synth-korg-ms50": {"R27": "2.2M", "R100": "100K"},
    "expanon:full-synths-drum-synths-and-misc-synth-misc-theremin": {"R17": "680"},
    "expanon:full-synths-drum-synths-and-misc-synth-roland-tb-303": {
        "R61": "10K", "R66": "100K", "R92": "100K", "R96": "10K", "R97": "10K", "R101": "10K", "R113": "100K",
        "R140": "100K", "R143": "10K", "R170": "22",
    },
    "expanon:fuzz-and-fuzzy-noisemakers-bass-brassmaster-bb1": {"R5": "1.5M", "R23": "47K"},
    "expanon:fuzz-and-fuzzy-noisemakers-roger-mayer-octavia-2": {"C11": "10n", "C12": "100n"},
    # The remaining candidates of the wide pass, checked on the drawings (2026-10-02); the Nobels and Ross
    # drawings are clean, so their misreads and missing parts are filled in as well.
    "expanon:delay-echo-and-samplers-danelectro-pbj-dj-17": {"IC3": "LM311", "R6": "220R", "R110": "18k"},
    "expanon:distortion-boost-and-overdrive-carl-martin-heavy-drive": {"R67": "100k", "R68": "100k"},
    "expanon:delay-echo-and-samplers-dod-fx96": {"R19": "10K", "R20": "10K"},
    "expanon:delay-echo-and-samplers-ibanez-ad9": {"U4": "MN3102"},
    "expanon:guitar-synth-and-misc-signal-shapers-ehx-bass-microsynth": {"Q1": "2N5087"},
    "expanon:guitar-synth-and-misc-signal-shapers-electro-harmonix-micro-synthesizer": {"Q1": "2N5087"},
    "expanon:tone-control-and-eqs-ibanez-pql-parametric-eq": {"R51": "15k"},
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
    "expanon:phasers-ross-phaser": {
        "U1": "RC4558P", "U2": "RC4558P", "U3": "RC4558P", "U4": "RC4558P", "R12": "470k", "R40": "82k", "R141": None,
        "Avt": None, "R2": "470k", "R3": "100k", "R4": "100k", "R5": "10k", "R9": "10k", "R11": "10k", "R14": "10k",
        "R22": "470k", "R25": "10k", "C1": "10n", "C2": "47n", "C3": "10n", "C5": "10n", "C6": "47n", "C7": "10n", "C8": "47n",
        "C9": "10n", "C11": "1n", "C12": "1µF tant", "C13": "1µF tant", "C15": "10n", "C16": "10µF tant", "C18": "10n",
        "INTENSITY": "C500K",
    },
    # The .jpg files of titles the archive also holds as .pdf (the plain id; the .pdf is its own board).
    "expanon:full-synths-drum-synths-and-misc-synth-moog-taurus": {
        "R132": "1K", "R134": "22K", "R147": "4.7K", "R202": "1K", "R203": "22K", "R213": "10K", "R304": "33K", "R305": "2.2M",
        "R307": "2.2K", "R308": "10K", "R310": "12K", "R406": "20K", "R523": "330", "R527": "47K", "R707": "10K",
    },
    "expanon:full-synths-drum-synths-and-misc-synth-moog-rogue": {"R57": None, "R7": "20K", "R25": "620K", "R27": "205K", "R79": "62K"},
    "expanon:delay-echo-and-samplers-digitech-pds2020": {"R60": "47K", "R90": "22K", "U22": "LM358"},  # LM958 is no part
    "expanon:guitar-synth-and-misc-signal-shapers-obesifier-waveform-animator": {
        "R12H": "100K", "R5": "100K", "R6": "100K", "R7": "100K", "R9G": "100K", "R9H": "100K", "R10F": "100K", "R10G": "100K",
        "R12G": "100K", "R13G": "100K", "R13H": "100K", "U1": "TL074", "U3": "TL074",
    },
    "expanon:oscillators-lfos-and-signal-generators-ar-317-vco": {"U3": "LM301A"},
    "expanon:oscillators-lfos-and-signal-generators-ar-324-lag-and-lfo": {"R32": "120K"},
    "expanon:oscillators-lfos-and-signal-generators-e-music-vcdo": {"R9": "100k", "R14": "1M5"},
    "expanon:oscillators-lfos-and-signal-generators-ehx-lfo": {"D1": "1N4001", "R9": "27k"},
    "expanon:oscillators-lfos-and-signal-generators-moog-901a": {"R4": "680K", "R5": "4.7M"},
    "expanon:oscillators-lfos-and-signal-generators-moog-901b": {
        "Q10": "2N2646", "R312": None, "R32": "22K", "R29": "13K", "R30": "43K", "R2": None,  # R312 is R32 misread; R2 '4' a fragment
    },
    "expanon:phasers-dod-fx20c": {"R27": "10K"},
    "expanon:phasers-ibanez-pt909": {"C106": "100P", "R134": "4.7K"},
    "expanon:phasers-nobels-ph-d": {
        "R4": "68K", "R5": "33K", "R6": "24K", "R62": "2K7", "R65": "1M", "R71": "12K", "R72": "56K", "R73": "470",
        "C1": "47N", "C2": "2.2µF", "C62": "2.2µF", "C63": "2.2µF", "C72": "10µF", "C81": "47µF", "C82": "4.7µF",
        "C201": "220µF", "C202": "47µF", "C203": "47µF", "D63": "1N4148", "D201": "1N4001", "Q1": "K222E",
        "Q11": "C2362G", "Q21": "C2362G", "Q31": "C2362G", "Q41": "C2362G", "Q61": "K30A-Y", "Q71": "K30A-Y",
        "Q81": "C2240BL", "U101": "4007", "U2": "LM358", "FEEDBACK": "B10K", "VOLUME": "A50K", "SPEED": "C1M",
        "INTENSITY": "B100K", "RANGE": "B10K",
    },
    "expanon:phasers-pearl-phaser": {"R6": "22K"},
    "expanon:tone-control-and-eqs-boss-ge-7": {
        "C10": "1.5µF", "C18": "47µF", "C22": "0.047uF", "U38": "TL022", "R9": "82K", "R52": "470K",
    },
    "expanon:tone-control-and-eqs-elektor-parametric-eq": {
        "C1": "47µF", "C9": "100n", "C11": "47p", "C15": "100n", "R8": "6k1", "R9": "22k",
    },
    "expanon:tone-control-and-eqs-ibanez-be-10-graphic-bass-eq": {"R3": "100K", "R25": "330"},
    "expanon:tone-control-and-eqs-ibanez-graphic-eq": {"R3": "100K", "R25": "330"},
    "expanon:tone-control-and-eqs-korg-parametric-eq": {"R23": "470K"},
    "expanon:tremolos-and-panners-dean-hazelwater-anderton-panner": {"R15": "470K"},
    "expanon:vibrato-and-pitch-shift-korg-oct-1": {"R19": "1K", "R43": "22M"},
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
        bom = [normalize_row(BomRow(ref=ref, value=value, category=cat, notes="; ".join(n for n in (note, _NOTE) if n),
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
        if value is None or (variant, ref) in seen:
            continue
        cat = ""
        if re.fullmatch(r"[A-Z]{3,}\d?", ref) and (re.match(r"^[ABCW]\d", value) or re.search(r"\btrim", value, re.I)):  # VOL2, GAIN1, PRES1; not RPD1 1M
            cat = "TRIM" if re.search(r"\btrim", value, re.I) else "POT"
        row = normalize_row(BomRow(ref=ref, value=value, notes=_NOTE, variant=variant or "", category=cat))
        out.insert(_insert_at(out, row.variant, ref), row)
    return out
