"""Substitutes for ICs, diodes and optocouplers, from figures read off the datasheets the library
links (datasheets.json). partspecs.json holds one entry per distinct part: the spellings that are
the same part (`same`), the socket it fits (`group`: same function, package and pinout, so one drops
into the other's place) and the datasheet's figures with the page they came from. Transistors have
their own parameter database (transistors.py); this table is read by hand from the sheets, so a
part without a sheet in hand has no entry and no substitutes.

A part's substitutes are the other entries of its group, ranked by how close the figures that
matter for that kind of part are, and each carries the differences a builder should know about
(a JFET input for a bipolar one, a supply range that stops short of 18 V)."""
from __future__ import annotations

import json
import math
from pathlib import Path

TABLE = Path(__file__).with_name("partspecs.json")
CATEGORY = {"ic": "IC", "diode": "D", "opto": "OPTO"}
# Figures shown on the parts page, per kind of socket; the export keeps only these.
FIELDS = ("vmin", "vmax", "gbw", "slew", "noise", "iq", "ib", "input", "rr", "single", "amps", "pins158", "comp",
          "vout", "iout", "vdrop", "fosc", "stages", "clock",
          "vf", "vf_if", "vf_hi", "vf_hi_if", "ifmax", "vr", "trr", "cj", "ir", "ir_vr", "pd", "package", "vz",
          "ron", "ron_if", "roff", "rise", "fall", "iled")


def load() -> list[dict]:
    return json.loads(TABLE.read_text()) if TABLE.exists() else []


def _log(a, b) -> float:
    if not a or not b or a <= 0 or b <= 0:
        return 0.0
    return abs(math.log(a / b))


def _opamp(group: str) -> bool:
    return group.startswith(("opamp", "ota", "cmp"))


def _vf_apart(a: dict, b: dict) -> float | None:
    """Difference in forward drop, only when the two sheets measured it at comparable currents:
    a germanium sheet's 0.1 mA figure and a silicon sheet's 10 mA one say nothing about each other."""
    if not a.get("vf") or not b.get("vf"):
        return None
    ia, ib = a.get("vf_if"), b.get("vf_if")
    if ia and ib and not 1 / 3 <= ia / ib <= 3:
        return None
    return b["vf"] - a["vf"]


def distance(a: dict, b: dict) -> float:
    """How far b is from a, for parts in the same group: 0 is the same part on paper."""
    g = a["group"]
    if _opamp(g):
        d = 1.0 * _log(a.get("gbw"), b.get("gbw")) + 1.0 * _log(a.get("slew"), b.get("slew")) \
            + 0.5 * _log(a.get("noise"), b.get("noise")) + 0.3 * _log(a.get("iq"), b.get("iq"))
        d += 1.0 if a.get("input") != b.get("input") else 0.0
        d += 0.5 if bool(a.get("single")) != bool(b.get("single")) or a.get("rr") != b.get("rr") else 0.0
        d += 1.5 if a.get("comp") != b.get("comp") else 0.0  # an external compensation capacitor, or none
        return d
    if g.startswith(("signal", "rect", "schottky", "germanium", "led")):
        d = 10.0 * abs(v) if (v := _vf_apart(a, b)) is not None else 1.0
        d += 0.3 * _log(a.get("ifmax"), b.get("ifmax")) + 0.3 * _log(a.get("vr"), b.get("vr"))
        d += 0.3 * _log(a.get("trr"), b.get("trr")) + 0.2 * _log(a.get("cj"), b.get("cj"))
        return d
    if g.startswith("vactrol") or g == "ldr":
        return _log(a.get("ron"), b.get("ron")) + 0.5 * _log(a.get("roff"), b.get("roff")) \
            + 0.5 * _log(a.get("rise"), b.get("rise")) + 0.5 * _log(a.get("fall"), b.get("fall"))
    # regulators, charge pumps, logic, timers: same socket, rank by current and supply
    return _log(a.get("iout"), b.get("iout")) + 0.5 * _log(a.get("vmax"), b.get("vmax")) \
        + (1.0 if a.get("pins158") != b.get("pins158") else 0.0) + (0.5 if a.get("input") != b.get("input") else 0.0)


def differences(a: dict, b: dict) -> list[str]:
    """What a builder should know before putting b where a was, from the two sheets' figures."""
    out = []
    g = a["group"]
    if a.get("input") and b.get("input") and a["input"] != b["input"]:
        out.append(f'{"bipolar" if b["input"] == "bipolar" else b["input"].upper()} input')
    if _opamp(g):
        if b.get("comp") and b["comp"] != a.get("comp"):
            out.append(f'needs a compensation capacitor across pins {b["comp"].replace("-", " and ")}')
        elif a.get("comp") and not b.get("comp"):
            out.append(f"internally compensated: the board's capacitor across pins {a["comp"].replace("-", " and ")} no longer shapes the tone"
                       + (f'; pins 1, 5, 8 are {b["pins158"]}' if b.get("pins158") else ""))
    elif a.get("pins158") and b.get("pins158") and a["pins158"] != b["pins158"]:
        out.append(f'pins 1, 6, 7: {b["pins158"]}')
    if b.get("vmax") and b["vmax"] < 18 <= (a.get("vmax") or 0):
        out.append(f'{b["vmax"]:g} V max, not for 18 V')
    if b.get("vmin") and b["vmin"] > 9 >= (a.get("vmin") or 0):
        out.append(f'rated from {b["vmin"]:g} V')
    if _opamp(g):
        if bool(b.get("single")) != bool(a.get("single")) and b.get("single"):
            out.append("input range reaches the negative rail")
        if b.get("rr") and b.get("rr") != a.get("rr"):
            out.append(f'rail-to-rail {"in and out" if b["rr"] == "in-out" else b["rr"] + "put"}')
        if a.get("iq") and b.get("iq") and b["iq"] > 2.5 * a["iq"]:
            out.append(f'draws {b["iq"]:g} mA per amplifier')
        if a.get("gbw") and b.get("gbw") and b["gbw"] > 4 * a["gbw"]:
            out.append("much faster, may oscillate in a slow part's place")
        if a.get("slew") and b.get("slew") and b["slew"] < a["slew"] / 4:
            out.append("much slower")
    if g.startswith(("signal", "rect", "schottky", "germanium")):
        if (v := _vf_apart(a, b)) is not None and abs(v) >= 0.08:
            out.append(f'{"higher" if v > 0 else "lower"} forward drop')
        # A clipping diode never sees more than the supply backward or more than a few mA forward:
        # the ratings matter for a rectifier on the power input, or when one is low enough to reach.
        rect = g.startswith("rect")
        if a.get("vr") and b.get("vr") and b["vr"] < a["vr"] * 0.8 and (rect or b["vr"] < 25):
            out.append(f'{b["vr"]:g} V reverse')
        if rect and a.get("ifmax") and b.get("ifmax") and b["ifmax"] < a["ifmax"] * 0.8:
            out.append(f'{b["ifmax"]:g} A forward')
        if a.get("package") and b.get("package") and a["package"] != b["package"]:
            out.append(b["package"])
    if g.startswith("zener"):
        if a.get("package") and b.get("package") and a["package"] != b["package"]:
            out.append(f'{b["package"]} body')
        if a.get("pd") and b.get("pd") and b["pd"] < a["pd"] * 0.8:
            out.append(f'{b["pd"]:g} W')
    if g.startswith("vactrol") or g == "ldr":
        for k, what in (("ron", "on resistance"), ("roff", "dark resistance"), ("fall", "decay")):
            if a.get(k) and b.get(k) and not 0.5 <= b[k] / a[k] <= 2:
                out.append(f'{"higher" if b[k] > a[k] else "lower"} {what}' if k != "fall" else f'{"slower" if b[k] > a[k] else "faster"} decay')
    return out


def substitutes(entries: list[dict], popularity: dict[str, int], limit: int = 10) -> dict[str, dict]:
    """For every library part with a spec entry: its own figures and the other parts of its group,
    closest first, keyed by the entry's part key ('IC:TL072'); aliases() maps the other spellings
    to it. popularity is boards per part key."""
    def boards(e: dict) -> int:
        cat = CATEGORY[e["kind"]]
        return sum(popularity.get(f"{cat}:{v}", 0) for v in {e["key"].split(":", 1)[1], *e.get("same", [])})

    def row(e: dict) -> dict:
        return {"pn": e["key"].split(":", 1)[1], **{k: e[k] for k in FIELDS if e.get(k) is not None}}

    by_group: dict[str, list[dict]] = {}
    for e in entries:
        by_group.setdefault(e["group"], []).append(e)
    out = {}
    for e in entries:
        others = [o for o in by_group[e["group"]] if o is not e]
        ranked = sorted(others, key=lambda o: (round(distance(e, o), 2), -boards(o), o["key"]))[:limit]
        entry = {"kind": e["kind"], "group": e["group"], "spec": row(e), "boards": boards(e),
                 **({"notes": e["notes"]} if e.get("notes") else {}),
                 **({"page": e["page"]} if e.get("page") else {}),
                 "subs": [{**row(o), "boards": boards(o), "score": round(distance(e, o), 2),
                           **({"diff": d} if (d := differences(e, o)) else {}),
                           **({"notes": o["notes"]} if o.get("notes") else {})} for o in ranked]}
        out[e["key"]] = entry
    return out


def aliases(entries: list[dict]) -> dict[str, str]:
    """Each library spelling that is the same part as an entry ('IC:TL072CP') -> the entry's key."""
    return {f'{CATEGORY[e["kind"]]}:{v}': e["key"] for e in entries for v in e.get("same", [])}
