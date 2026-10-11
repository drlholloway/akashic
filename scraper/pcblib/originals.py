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


# Makers learned from the library itself (see learn_brands): alias key -> the spelling most used.
_LEARNED: dict[str, str] = {}
_LEARNED_RE: re.Pattern | None = None
# What a maker calls itself after its name: 'VFE Pedals' and 'VFE', 'Spaceman Effects' and 'Spaceman' are one maker.
_COMPANY_WORDS = {"fx", "effects", "effect", "pedals", "pedal", "electronics", "electronic", "audio", "amps", "amplification",
                  "amplifiers", "devices", "customs", "custom", "labs", "laboratories", "music", "sound", "sounds"}
_NOT_A_MAKER = {"mask", "analog", "black", "dead", "big", "the", "mini", "bass", "fuzz", "super", "tone", "blue", "red", "green", "king"}


def _core(label: str) -> str:
    """'VFE Pedals' -> 'VFE': the maker's name without the company words it ends in ('' when nothing usable is left)."""
    words = label.split()
    while len(words) > 1 and key(words[-1]) in _COMPANY_WORDS:
        words.pop()
    core = " ".join(words)
    k = key(core)
    return core if core != label and (len(words) >= 2 or (len(k) >= 3 and k not in _NOT_A_MAKER)) else ""


def learn_brands(named: list[tuple[str, list[str]]]) -> None:
    """Makers the layout sites label their posts with. A post titled 'One Control Honey Bee Overdrive'
    and labelled 'One Control' says One Control is a maker, which no fixed list of brands would know;
    with it, a board based on the 'Honey Bee OD' finds its original. Takes (name, labels) pairs and
    keeps the labels that start a name. A maker is known by its label and by the label without its
    company words ('Spaceman Effects', 'Spaceman'), and shown under the spelling most used."""
    global _LEARNED_RE
    from collections import Counter
    seen: dict[str, Counter] = {}  # maker key (of the core name) -> label spellings
    for name, labels in named:
        low = name.lower()
        for lab in labels:
            lab = lab.strip()
            if len(lab) >= 2 and low.startswith(lab.lower()) and len(name) > len(lab) and not name[len(lab)].isalnum():
                seen.setdefault(key(_core(lab) or lab), Counter())[lab] += 1
    known = {key(n) for n, _ in _BRANDS}
    _LEARNED.clear()
    aliases: set[str] = set()
    for k, c in seen.items():
        if not k or k in known or k in _TYPE_WORDS or k in _NOT_A_MAKER:
            continue
        best = c.most_common(1)[0][0]
        for lab in c:
            for alias in {lab, _core(lab)} - {""}:
                _LEARNED[key(alias)] = best
                aliases.add(alias)
    alts = sorted((re.escape(a) for a in aliases), key=len, reverse=True)
    _LEARNED_RE = re.compile(rf"^({'|'.join(alts)})(?![A-Za-z0-9])(?:['’]s\b)?[\s:/-]*", re.I) if alts else None


def _brand(text: str) -> tuple[str, str]:
    """(canonical brand, rest of the text) when the text starts with a brand alias, else ('', text)."""
    for name, rx in _BRAND_RE:
        m = rx.match(text)
        if m and m.end() < len(text):
            return name, text[m.end():].strip()
    if _LEARNED_RE and (m := _LEARNED_RE.match(text)) and m.end() < len(text) and key(m.group(1)) in _LEARNED:
        rest = text[m.end():].strip()
        # 'Spaceman Effects Nebula' read through the alias 'Spaceman': the company word belongs to the maker
        words = rest.split()
        while len(words) > 1 and key(words[0]) in _COMPANY_WORDS:
            words.pop(0)
        return _LEARNED[key(m.group(1))], " ".join(words)
    return "", text


def original(based_on: str) -> str:
    """The canonical name of the original a board is based on ('' when there is none)."""
    t = re.sub(r"[®™]", "", based_on or "").strip(" .,;:\"'")
    t = re.sub(r"\s+", " ", t)
    if not t:
        return ""
    if (m := re.fullmatch(r"(.+?) by ([A-Z][^,()]{2,40})", t)) and not re.search(r"\b(?:inspired|designed|drawn|layout|schematic|traced|modded|built)$", m.group(1), re.I):
        if _brand(m.group(2) + " x")[0]:  # 'Supersonic Fuzz Gun by Death By Audio': the maker written last
            t = f"{m.group(2)} {m.group(1)}"
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


# Near-duplicates no rule can settle, read one by one: {key(spelling): the original's name}. See original_aliases.json.
ALIASES: dict[str, str] = {}
_ALIASES_FILE = __import__("pathlib").Path(__file__).with_name("original_aliases.json")


def _load_aliases() -> None:
    import json
    if _ALIASES_FILE.exists():
        for canon, spellings in json.loads(_ALIASES_FILE.read_text()).items():
            for sp in spellings:
                ALIASES[key(sp)] = canon


# What an effect is, not what it is called: 'Honey Bee Overdrive' and 'Honey Bee OD' are one pedal.
_TYPE_WORDS = {"overdrive", "od", "distortion", "dist", "fuzz", "boost", "booster", "pedal", "preamp", "compressor", "tremolo",
               "delay", "reverb", "chorus", "phaser", "flanger", "vibrato", "drive", "effect", "fx"}
# Left alone as the only word of a model: 'Bass Fuzz' is not 'Bass', 'Super Fuzz' is not 'Super'.
_WEAK_WORDS = {"bass", "super", "mini", "micro", "big", "hot", "fat", "classic", "vintage", "tube", "metal", "blues", "mega",
               "ultra", "turbo", "hyper", "dual", "double", "twin", "little", "clean", "dirty", "treble", "power", "tone", "octave"}


def model_key(rest: str, loose: bool = True) -> str:
    """Grouping key of a model name within one maker: the key without the effect-type words it ends in
    ('honey bee overdrive' -> 'honey bee'), when a real name is left: two words, or one word of four
    letters or more that is not a mere adjective. `loose=False` asks for two words, for matching a
    name written without its maker."""
    words = key(rest).split()
    cut = list(words)
    while cut and cut[-1] in _TYPE_WORDS:
        cut.pop()
    if cut == words or not cut:
        return " ".join(words)
    if len(cut) >= 2 or (loose and len(cut[0]) >= 4 and cut[0] not in _WEAK_WORDS and cut[0] not in _TYPE_WORDS):
        return " ".join(cut)
    return " ".join(words)


_load_aliases()


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
            for k in {key(rest), model_key(rest, loose=False)}:
                brands_of[k].add(brand)
                branded[(brand, k)][n] += c
    out: dict[str, str] = {}
    for n in counts:
        brand, rest = _brand(n)
        out[n] = n
        if brand:
            continue
        for k in (key(rest), model_key(rest, loose=False)):
            if len(brands_of.get(k, ())) == 1 and len(k) > 3 and not set(k.split()) <= _TYPE_WORDS | _WEAK_WORDS:
                b = next(iter(brands_of[k]))
                out[n] = branded[(b, k)].most_common(1)[0][0]
                break
    # Every spelling of an original takes the group's most common one. Within a maker, the effect-type
    # word a name ends in does not split it ('One Control Honey Bee Overdrive', 'One Control Honey Bee OD'),
    # nor does spacing ('FX86', 'FX-86') or word order ('DOD 440 Reissue Envelope Filter', 'DOD Envelope
    # Filter 440 Reissue'): names sharing any of these keys are one group.
    def own_keys(name: str) -> list[str]:
        brand, rest = _brand(name)
        words = (model_key(rest) if brand else model_key(name, loose=False)).split()
        pre = key(brand) + "|" if brand else "|"
        return [pre + "".join(words), pre + "~" + " ".join(sorted(words))]

    def keys(name: str) -> list[str]:
        alias = ALIASES.get(key(name))
        return own_keys(name) + (own_keys(alias) if alias else [])
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for f in set(out.values()):
        ks = keys(f)
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
    spelled: dict[str, Counter] = defaultdict(Counter)
    for n, c in counts.items():
        shown = ALIASES.get(key(out[n]), out[n])
        spelled[find(keys(out[n])[0])][shown] += c + (10_000 if shown != out[n] else 0)  # a hand-settled name wins
    return {n: spelled[find(keys(f)[0])].most_common(1)[0][0] for n, f in out.items()}
