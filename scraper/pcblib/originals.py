"""One name per original circuit. Vendors write the same original many ways: 'EHX Big Muff',
'Electro-Harmonix Big Muff Pi', 'Big Muff', 'Electro Harmonics Big Muff Pi'. original() returns
a canonical display name: brand aliases are spelled one way, the best-known models are matched by
pattern (sibling models such as the Op-Amp Big Muff or RAT 2 kept apart), and a model that one
brand owns gets that brand when the vendor left it off. Combinations ('Fuzz Face into Big Muff')
and descriptions that name no single original ('Lots of Big Muff Pi variants') are left alone, so
they never merge into an original they only mention."""
from __future__ import annotations

import re

# Canonical brand -> pattern of the spellings vendors use, matched at the start of the text.
_BRANDS: list[tuple[str, str]] = [
    ("Electro-Harmonix", r"e\.?h\.?x\.?|exh|electro[- ]?harmoni[cx]s?"),
    ("EarthQuaker Devices", r"eqd|earth ?quaker(?: devices)?"),
    ("ProCo", r"pro ?co"),
    ("Dallas Arbiter", r"dallas[- ]arbiter|arbiter|dallas"),
    ("Z.Vex", r"z\.? ?vex"),
    ("Way Huge", r"way ?huge"),
    ("Mu-Tron", r"mu[- ]?tron|musitronics"),
    ("Death By Audio", r"death by audio|dba"),
    ("Shin-ei", r"shin[- ]?ei"),
    ("Analogman", r"analog ?man"),
    ("Run Off Groove", r"run ?off ?groove|rog"),
    ("Mr. Black", r"mr\.? ?black"),
    ("Devi Ever", r"devi ever"),
    ("Dunlop", r"(?:jim )?dunlop"),
    ("Colorsound", r"colou?r ?sound"),
    ("Sola Sound", r"sola ?sound"),
    ("Fulltone", r"full ?tone"),
    ("Lovepedal", r"love ?pedal"),
    ("Catalinbread", r"catalin ?bread"),
    ("Mad Professor", r"mad professor"),
    ("Xotic", r"xotic"),
    ("Keeley", r"(?:robert )?keeley"),
    ("Boss", r"boss"),
    ("Ibanez", r"ibanez"),
    ("MXR", r"mxr"),
    ("DOD", r"dod"),
    ("Maestro", r"maestro"),
    ("Univox", r"univox"),
    ("Marshall", r"marshall"),
    ("JHS", r"jhs"),
    ("Klon", r"klon"),
    ("Paul Cochrane", r"paul cochrane"),
    ("Interfax", r"interfax"),
]
_BRAND_RE = [(name, re.compile(rf"^(?:{pat})\b[\s:/-]*", re.I)) for name, pat in _BRANDS]

# (pattern over the whole text, brand, model). Order matters: siblings before the general name.
_MODELS: list[tuple[str, str, str]] = [
    (r"\b(?:op[- ]?amp|ic)\s+big muff|big muff(?: pi)?\s*(?:\(\s*)?op[- ]?amp", "Electro-Harmonix", "Op-Amp Big Muff Pi"),
    (r"big muff(?: pi)?\s*2\b", "Electro-Harmonix", "Big Muff Pi 2"),
    (r"little big muff", "Electro-Harmonix", "Little Big Muff"),
    (r"double muff", "Electro-Harmonix", "Double Muff"),
    (r"germanium 4 big muff", "Electro-Harmonix", "Germanium 4 Big Muff"),
    (r"big muff(?: pi)?\b", "Electro-Harmonix", "Big Muff Pi"),
    (r"\bmuff fuzz\b", "Electro-Harmonix", "Muff Fuzz"),
    (r"small stone", "Electro-Harmonix", "Small Stone"),
    (r"(?:deluxe )?memory man", "Electro-Harmonix", "Memory Man"),
    (r"\bts[- ]?808\b|tube ?screamer\s*(?:ts)?[- ]?808", "Ibanez", "TS808 Tube Screamer"),
    (r"\bts[- ]?9\b|tube ?screamer\s*(?:ts)?[- ]?9\b", "Ibanez", "TS9 Tube Screamer"),
    (r"tube ?screamer", "Ibanez", "Tube Screamer"),
    (r"turbo ?rat", "ProCo", "Turbo RAT"),
    (r"\brat ?2\b", "ProCo", "RAT 2"),
    (r"(?:^|pro ?co\s+)\brat\b(?! ?2)", "ProCo", "RAT"),
    (r"fuzz ?face", "Dallas Arbiter", "Fuzz Face"),
    (r"range ?master", "Dallas Arbiter", "Rangemaster"),
    (r"\bklon\b|centaur", "Klon", "Centaur"),
    (r"distortion ?(?:\+|plus)", "MXR", "Distortion+"),
    (r"phase ?90", "MXR", "Phase 90"),
    (r"dyna ?comp", "MXR", "Dyna Comp"),
    (r"\bds-?1\b", "Boss", "DS-1"),
    (r"\bsd-?1\b", "Boss", "SD-1"),
    (r"blues ?driver|\bbd-?2\b", "Boss", "BD-2 Blues Driver"),
    (r"\bce-?2\b", "Boss", "CE-2"),
    (r"\bdm-?2\b", "Boss", "DM-2"),
    (r"blues ?breaker", "Marshall", "Bluesbreaker"),
    (r"uni-?vibe", "Shin-ei", "Uni-Vibe"),
    (r"octavia", "Roger Mayer", "Octavia"),
    (r"harmonic percolator", "Interfax", "Harmonic Percolator"),
    (r"orange squeezer", "Dan Armstrong", "Orange Squeezer"),
    (r"king of tone", "Analogman", "King of Tone"),
    (r"zen ?drive", "Hermida", "Zendrive"),
    (r"super ?fuzz", "Univox", "Super-Fuzz"),
    (r"tone ?machine", "Foxx", "Tone Machine"),
    (r"guv'?nor", "Marshall", "Guv'nor"),
    (r"\btimmy\b", "Paul Cochrane", "Timmy"),
    (r"morning glory", "JHS", "Morning Glory"),
    (r"fuzz ?factory", "Z.Vex", "Fuzz Factory"),
    (r"\bdod\b.*\b250\b|\b250\b.*overdrive", "DOD", "250 Overdrive Preamp"),
]
_MODEL_RE = [(re.compile(p, re.I), b, m) for p, b, m in _MODELS]

# A description that names no single original: no original at all, so it stays off the Originals list.
_DESCRIPTION = re.compile(r"\bvariants\b|\bany\b|\blots of\b|\bshitload\b|\bcircuit\b|\bside of\b|\btwo effects\b", re.I)
# A pairing or a family resemblance: kept as written (brand spelled one way), never folded into a model.
_NOT_ONE = re.compile(r"\binto\b|\s\+\s|\band\b|\bor\b|\bmeets\b|\bstyle\b|\binspired\b", re.I)
_BRAND_PAIR = re.compile(r"^(?:e\.?h\.?x|electro[- ]?harmoni[cx]s?)\s*/\s*jhs\b", re.I)  # EHX/JHS Big Muff 2: one pedal


def _brand(text: str) -> tuple[str, str]:
    """(canonical brand, rest of the text) when the text starts with a brand alias, else ('', text)."""
    for name, rx in _BRAND_RE:
        m = rx.match(text)
        if m and m.end() < len(text):
            return name, text[m.end():].strip()
    return "", text


def original(based_on: str) -> str:
    """The canonical name of the original a board is based on ('' when there is none)."""
    t = re.sub(r"[®™]", "", based_on or "").strip(" .,;:\"'")
    t = re.sub(r"\s+", " ", t)
    if not t:
        return ""
    if _DESCRIPTION.search(t):
        return ""
    if _NOT_ONE.search(t) or re.search(r"\S\s*/\s*\S", t) and not _BRAND_PAIR.match(t):
        brand, rest = _brand(t)
        return f"{brand} {rest}" if brand else t
    for rx, brand, model in _MODEL_RE:
        if rx.search(t):
            return f"{brand} {model}"
    brand, rest = _brand(t)
    return f"{brand} {rest}" if brand else t


def key(name: str) -> str:
    """Grouping key: case, punctuation and articles do not split an original."""
    s = re.sub(r"\b(the|a|an)\b", "", name.lower())
    return re.sub(r"[^a-z0-9+]+", " ", s).strip()


def harmonize(names: list[str]) -> dict[str, str]:
    """Settle the originals of the whole library at once: a model written without its brand gets
    the brand when exactly one brand has that model in the library ('Woolly Mammoth' -> 'Z.Vex Woolly
    Mammoth'; 'Les Lius', under two brands, stays), and every spelling of an original takes the
    group's most common one ('Box Of Rock' and 'Box of Rock'). Returns {name: final name}."""
    from collections import Counter, defaultdict
    counts = Counter(n for n in names if n)
    brands_of: dict[str, set[str]] = defaultdict(set)
    branded: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for n, c in counts.items():
        brand, rest = _brand(n)
        if brand:
            brands_of[key(rest)].add(brand)
            branded[(brand, key(rest))][n] += c
    out: dict[str, str] = {}
    for n in counts:
        brand, rest = _brand(n)
        k = key(rest)
        if not brand and len(brands_of.get(k, ())) == 1 and len(k) > 3:
            b = next(iter(brands_of[k]))
            out[n] = branded[(b, k)].most_common(1)[0][0]
        else:
            out[n] = n
    spelled: dict[str, Counter] = defaultdict(Counter)
    for n, c in counts.items():
        spelled[key(out[n])][out[n]] += c
    return {n: spelled[key(f)].most_common(1)[0][0] for n, f in out.items()}
