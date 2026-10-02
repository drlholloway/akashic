"""Hand corrections to parts rows that no parser rule can make, each checked against the source
document by a person. Applied whenever a board is stored (db.upsert_circuit), after every parser has
run, so a rescrape keeps them. A value of None removes the row; a value for a row the parsers missed
adds it, after the nearest lower designator of its kind. Add a line per report, with where it came
from; remove it when a parser learns to read the board right.

    CORRECTIONS[circuit_id][designator] = corrected value, or None to drop the row
    CORRECTIONS[circuit_id][(variant, designator)] = the same, for one build variant only
    (designators match regardless of case: 'CLEAN' corrects a knob stored as 'Clean')
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
    "expanon:oscillators-lfos-and-signal-generators-moog-901b": {"Q10": "2N2646"},
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
        if re.fullmatch(r"[A-Z]{3,}\d?", ref) and re.search(r"\d", value):  # a named knob: VOL2, GAIN1, PRES1
            cat = "TRIM" if re.search(r"\btrim", value, re.I) else "POT"
        row = normalize_row(BomRow(ref=ref, value=value, notes=_NOTE, variant=variant or "", category=cat))
        out.insert(_insert_at(out, row.variant, ref), row)
    return out
