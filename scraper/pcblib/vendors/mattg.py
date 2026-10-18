"""Matt Garman (MattG on the PedalPCB forum): microcontroller bypass modules, shared as two GitHub
repositories that go together. mcu-bypass-hardware holds one KiCad project per module in projects/
(README.adoc, schematic, PCB, a PDF of the schematic; no gerbers), CERN-OHL-P-2.0; mcu-bypass-firmware
holds the MIT-licensed firmware that runs on the module's microcontroller, released as one .hex image
per microcontroller and switching scheme. Each module is a circuit (a "quasi-IC" that plugs into the
effect's PCB and handles the buffers, the switching, the footswitch and the LED); its parts are read
from the placed symbols of the KiCad schematic, and it links the firmware image that it takes. The
forum thread follows the design from the CD40106/CD4053 prototype to the ATtiny modules."""
from __future__ import annotations

import json
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import normalize_row
from . import register
from .base import Adapter, clean_text

USER = "https://github.com/matt-garman"
HW = "matt-garman/mcu-bypass-hardware"
FW = "matt-garman/mcu-bypass-firmware"
RAW = f"https://raw.githubusercontent.com/{HW}/main"
THREAD = "https://forum.pedalpcb.com/threads/buffer-bypass-quasi-ic-module.29247/"
# What each module is, in a sentence the READMEs give across several sections; a module added later
# falls back to its README's first paragraph.
_ABOUT = {
    "attiny13a-buffered-electrical-bypass-quasi-ic":
        "A plug-in module (two rows of five pins) that does a pedal's bypass the way a Boss compact does: an OPA1678 "
        "input and output buffer, a TMUX4053 analog switch, and an ATtiny13A that debounces the footswitch, keeps the "
        "state and lights the LED. It is wired for the firmware's 4053-with-mute scheme: a 5 ms mute between bypass and "
        "engage to keep the switching quiet. Surface-mount, made to be assembled by the fab; the first version of the module.",
    "attiny202-buffered-electrical-bypass-quasi-ic":
        "The same circuit as the ATtiny13A quasi-IC (OPA1678 buffers, TMUX4053 switching with the 5 ms mute, footswitch "
        "debounce, state and LED), shrunk to a 43 x 16 mm four-layer board around an ATtiny202, with a single row of nine "
        "pins so it can stand vertically on right-angle headers. Surface-mount, made to be assembled by the fab.",
    "attiny13a-relay-bypass-quasi-ic":
        "A true-bypass version of the quasi-IC: no buffers, a Panasonic TQ2-L2-5V latching relay switched by an ATtiny13A, "
        "ATtiny45 or ATtiny85 running the same firmware. Through-hole, so it is larger; its middle nine pins match the "
        "ATtiny202 module, and extra pins (9 V after the protection, 5 V, ground, LED) let it drive off-the-shelf boards "
        "such as PedalPCB or AionFX.",
}
_FOOTPRINT = [(r"^R_(\d{4})_", r"SMD \1"), (r"^C_(\d{4})_", r"SMD \1"), (r"^L_(\d{4})_", r"SMD \1"), (r"^R_Axial", "axial"),
              (r"^C_Rect", "box film"), (r"^CP_Radial", "radial electrolytic"), (r"^D_DO-35", "DO-35"), (r"^D_(SOD-\d+F?)", r"\1"),
              (r"^SOT-?23", "SOT-23"), (r"^(TO-92|SOIC-8|DIP-8|WSON-8|TSOT-23-16)", r"\1"), (r"Texas_DYY", "TSOT-23-16"),
              (r"^Relay", "relay")]


def _adoc_text(s: str) -> str:
    s = re.sub(r"link:\S+?\[([^\]]*)\]", r"\1", s)
    s = re.sub(r"https?://\S+?\[([^\]]*)\]", r"\1", s)
    return clean_text(re.sub(r"[_*`]", "", s))


def _symbols(sch: str) -> list[tuple[str, str, str, str]]:
    """(reference, value, lib_id, footprint) for each placed symbol of a .kicad_sch file, units of one
    part once; power flags and DNP parts left out."""
    start = sch.find("(lib_symbols")
    depth, end = 0, start
    for end in range(start, len(sch)):  # skip the embedded symbol library
        depth += {"(": 1, ")": -1}.get(sch[end], 0)
        if depth == 0:
            break
    out, seen = [], set()
    for m in re.finditer(r'\(symbol\s*\(lib_id "([^"]+)"(.*?)\(instances', sch[end:], re.S):
        lib, body = m.groups()
        p = dict(re.findall(r'\(property "([^"]+)" "([^"]*)"', body))
        ref = p.get("Reference", "")
        if not ref or ref.startswith("#") or ref in seen or "(dnp yes)" in body or "(in_bom no)" in body:
            continue
        seen.add(ref)
        out.append((ref, p.get("Value", ""), lib, p.get("Footprint", "").split(":")[-1]))
    return out


def _package(fp: str) -> str:
    for pat, rep in _FOOTPRINT:
        m = re.search(pat, fp)
        if m:
            return m.expand(rep)
    return ""


@register
class MattG(Adapter):
    vendor = "mattg"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.files: list[str] = []
        self.release: dict = {}

    def list_targets(self) -> Iterable[str]:
        tree = self.f.get_text(f"https://api.github.com/repos/{HW}/git/trees/main?recursive=1", ".json") or ""
        self.files = re.findall(r'"path":\s*"([^"]+)"', tree)
        rel = self.f.get_text(f"https://api.github.com/repos/{FW}/releases/latest", ".json")
        try:
            self.release = json.loads(rel) if rel else {}
        except ValueError:
            self.release = {}
        projects = sorted({f.split("/")[1] for f in self.files if re.fullmatch(r"projects/[^/]+/[^/]+\.kicad_sch", f)})
        yield from projects

    def parse(self, project: str) -> Circuit | None:
        folder = f"projects/{project}"
        files = [f for f in self.files if f.startswith(folder + "/")]
        sch_file = next((f for f in files if f.endswith(".kicad_sch")), "")
        readme = self.f.get_text(f"{RAW}/{folder}/README.adoc", ".adoc") or ""
        sch = self.f.get_text(f"{RAW}/{sch_file}", ".kicad_sch") or "" if sch_file else ""
        if not sch:
            return None
        title = re.search(r"^= (.+)$", readme, re.M)
        name = clean_text(title.group(1)) if title else project.replace("-", " ").title()
        name = re.sub(r"\s+Module and Quasi-IC$", " Quasi-IC", name)
        about = _ABOUT.get(project)
        if not about:
            paras = [p for p in re.split(r"\n\s*\n", readme.split("== ", 2)[1] if "== " in readme else readme)[1:]
                     if p.strip() and not p.strip().startswith(("=", "//", "image::", "link:", "....", "|"))]
            about = _adoc_text(paras[0]) if paras else ""
        tree = f"https://github.com/{HW}/tree/main/{folder}"
        c = Circuit(vendor=self.vendor, slug=project, name=f"{name}", url=tree, doc_url=tree, based_on=f"Matt Garman {name}",
                    description=about, category="Utility", effect_type="Bypass module", price=None, currency="USD", in_stock=None,
                    tags=["MCU bypass", "KiCad", "CERN-OHL-P-2.0"])
        relay = False
        mcu = ""
        for ref, value, lib, fp in _symbols(sch):
            if re.match(r"(?:J|TP|H|MH)\d", ref) or lib.startswith(("power:", "Mechanical:")):
                continue  # the module's pins, test points, mounting holes
            note = ""
            if lib.startswith("MCU_"):
                chip = re.match(r"(ATtiny\d+A?|PIC\d+F\d+)", value, re.I)
                mcu = chip.group(1).lower() if chip else ""
                if mcu == "attiny13a" and fp.startswith("DIP"):
                    value, note = "ATtiny13A", "DIP-8; ATtiny45 or ATtiny85 also run the firmware"
            if ref.startswith("K") and re.search(r"TQ2", value):
                relay, value, note = True, "TQ2-L2-5V", "Panasonic latching DPDT relay"  # the symbol is named 'TQ2-2L'
            value = re.sub(r"_(?:TO92|SOT23|SOIC8?)$", "", value)  # 'LP2950-5.0_TO92': KiCad's symbol name
            pkg = _package(fp)
            r = normalize_row(BomRow(ref=ref, value=value, part_type=pkg, notes=note,
                                     category="L" if ref.startswith("FB") else ("IC" if lib.startswith(("MCU_", "Analog_Switch", "Regulator", "Amplifier")) else "")))
            c.bom.append(r)
        c.bom.sort(key=lambda r: (re.sub(r"\d.*", "", r.ref), int(re.sub(r"\D", "", r.ref) or 0)))
        smd = sum(1 for r in c.bom if r.part_type.startswith("SMD"))
        c.tags.append("SMD assembly" if smd > len(c.bom) / 2 else "through-hole")
        if f"{folder}/{sch_file.rsplit('/', 1)[-1][:-10]}.pdf" in files:
            c.extra_docs["Schematic PDF"] = f"https://github.com/{HW}/blob/main/{sch_file[:-10]}.pdf"
        c.extra_docs["Firmware (mcu-bypass-firmware)"] = f"https://github.com/{FW}"
        tag = self.release.get("tag_name", "")
        assets = {a["name"]: a["browser_download_url"] for a in self.release.get("assets", [])}
        scheme = "tq2_l2_5v_relay" if relay else "cd4053_with_mute"
        for chip in ([mcu] + (["attiny45", "attiny85"] if mcu == "attiny13a" and relay else [])):
            image = f"bypass-{chip}-{scheme}.hex"
            if image in assets:
                c.extra_docs[f"Firmware image {tag}: {image}"] = assets[image]
        if tag:
            c.doc_version = f"firmware {tag}"
        c.extra_docs["Flashing the firmware"] = f"https://github.com/{FW}/blob/main/FLASHING.md"
        c.extra_docs["Forum thread (PedalPCB)"] = THREAD
        for url, label in re.findall(r"link:(https://forum\.pedalpcb\.com/threads/\S+?)\[([^\]]+)\]", readme):
            c.extra_docs.setdefault(f"Build report: {_adoc_text(label)}", url)
        return c
