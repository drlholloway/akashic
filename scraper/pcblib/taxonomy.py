"""Map vendor-specific category / effect-type strings onto one shared taxonomy."""
from __future__ import annotations

import re

CATEGORIES = [
    "Overdrive", "Distortion", "Fuzz", "Boost", "Preamp / Amp-in-a-box",
    "Compressor", "EQ / Filter", "Wah / Envelope", "Tremolo", "Vibrato / Chorus",
    "Phaser", "Flanger", "Delay", "Reverb", "Octave / Pitch", "Ring Mod / Synth",
    "Noise Gate", "Utility", "Bass", "DSP", "Other",
]

_RULES: list[tuple[re.Pattern, str]] = [(re.compile(p, re.I), c) for p, c in [
    (r"\bfuzz\b|muff|tone ?bender|fuzz ?face|octavia", "Fuzz"),
    (r"\bdistortion\b|\bdist\b|\brat\b|metal|high ?gain", "Distortion"),
    (r"overdrive|\bod\b|screamer|klon|blues ?breaker|tube ?screamer|drive\b", "Overdrive"),
    (r"\bboost(er)?\b|\bclean\b", "Boost"),
    (r"preamp|amp[- ]?in[- ]a[- ]box|amp emul|amp sim|cab sim", "Preamp / Amp-in-a-box"),
    (r"compress|limiter|sustain|\bcomp\b", "Compressor"),
    (r"\bwah\b|envelope|auto[- ]?wah|touch", "Wah / Envelope"),
    (r"\beq\b|equali[sz]er|\bfilter\b|tone ?control", "EQ / Filter"),
    (r"tremolo|trem\b", "Tremolo"),
    (r"vibrato|vibe|chorus|uni-?vibe|rotary|leslie", "Vibrato / Chorus"),
    (r"phase|phasor|phaser", "Phaser"),
    (r"flang", "Flanger"),
    (r"delay|echo", "Delay"),
    (r"reverb|spring", "Reverb"),
    (r"octave|pitch|harmoni[sz]er|whammy", "Octave / Pitch"),
    (r"ring ?mod|synth|oscillator", "Ring Mod / Synth"),
    (r"noise ?gate|\bgate\b", "Noise Gate"),
    (r"\bbass\b", "Bass"),
    (r"fv-?1|dsp|spin\b|digital", "DSP"),
    (r"bypass|buffer|splitter|switch|utility|looper|power|voltage|charge pump|breakout|tap tempo|expression|a/b|mixer|blend", "Utility"),
    (r"modulation", "Vibrato / Chorus"),
]]


def classify_within(allowed: set[str], *hints: str, default: str = "Other") -> str:
    """Like classify() but only accept categories in `allowed`."""
    for h in hints:
        if not h:
            continue
        for rx, cat in _RULES:
            if cat in allowed and rx.search(h):
                return cat
    return default


def classify(*hints: str) -> str:
    """Return the first taxonomy category matched across the given hint strings
    (most specific hints should be passed first)."""
    for h in hints:
        if not h:
            continue
        for rx, cat in _RULES:
            if rx.search(h):
                return cat
    return "Other"


# Hammond die-cast sizes builders actually specify, longest names first so 1590BB2 wins over 1590B.
_ENCLOSURE_RE = re.compile(
    r"\b(1590BB2|1590BBS|1590XX|1590DD|1590N1|1590P1|1590R1|1590B2|1590BS|1590LB|1590BB|1590A2|"
    r"1590A|1590B|1590C|1590D|1590E|1590G|1590J|1590Q|1590S|1590T|1590X|1590Y|1590Z|125B|1032L|1550B)\b", re.I)


def find_enclosure(*texts: str) -> str:
    for t in texts:
        if not t:
            continue
        m = _ENCLOSURE_RE.search(t)
        if m:
            return m.group(1).upper()
    return ""
