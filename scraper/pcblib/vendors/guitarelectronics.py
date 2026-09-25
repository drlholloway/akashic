"""Guitar-Electronics.eu adapter: a Polish Shoper store (EUR) selling bare PCBs for classic
circuits. Each product page links a short PDF with a parts-placement list ('R1 1M'), a wiring
diagram and a bill of materials by value ('330R 1pcs. "R3"')."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..pdf import pdf_text_pages, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://guitar-electronics.eu"
CATEGORY = f"{BASE}/en_US/c/KITs-PCBs/13"
_SKIP = re.compile(r"PSU|enclosure|kit", re.I)
_BASED_ON = {
    "69-fuzz": "Dallas Arbiter Fuzz Face", "ac-booster": "Xotic AC Booster", "accutronics": "Accutronics spring reverb driver",
    "bassdrive": "Fulltone Bass-Drive", "bb-preamp": "Xotic BB Preamp", "bf2": "Boss BF-2 Flanger", "big-muff": "Electro-Harmonix Big Muff",
    "boogie-drive": "Dr. Boogie", "box-of-rock": "ZVex Box of Rock", "crunch-box": "MI Audio Crunch Box", "decimator": "ISP Decimator G-String",
    "deep-blue": "Mad Professor Deep Blue Delay", "diablo": "Okko Diablo", "distortion-plus": "MXR Distortion+", "dyna-comp": "MXR Dyna Comp",
    "ep-booster": "Xotic EP Booster", "fulldrive": "Fulltone Fulldrive 2 MOSFET", "fuzz-face": "Dallas Arbiter Fuzz Face",
    "fuzz-factory": "ZVex Fuzz Factory", "ge7b": "Boss GEB-7 Bass Equalizer", "ge7": "Boss GE-7 Equalizer", "guvnor": "Marshall Guv'nor",
    "hogs-foot": "Electro-Harmonix Hog's Foot", "hot-cake": "Crowther Hot Cake", "king-of-tone": "Analog Man King of Tone",
    "klon": "Klon Centaur", "lpb-1": "Electro-Harmonix LPB-1", "mark-iv": "Mesa Boogie Mark IV preamp", "mc401": "MXR MC-401 Boost/Line Driver",
    "nf1": "Boss NF-1 Noise Gate", "ocd": "Fulltone OCD", "octavia": "Tycobrahe Octavia", "phase-90": "MXR Phase 90",
    "plexitone": "Carl Martin PlexiTone", "pq3b": "Boss PQ-3B Bass Parametric Equalizer", "pq4": "Boss PQ-4 Parametric Equalizer",
    "pt80": "General Guitar Gadgets PT-80 delay", "rat": "ProCo RAT", "rc-booster": "Xotic RC Booster", "riot": "Suhr Riot",
    "sansamp": "Tech 21 SansAmp GT2", "screaming-bird": "Electro-Harmonix Screaming Bird", "sho": "ZVex Super Hard-On",
    "slow-gear": "Boss SG-1 Slow Gear", "small-clone": "Electro-Harmonix Small Clone", "soldano": "Soldano SLO-100",
    "triple-wreck": "Wampler Triple Wreck", "tube-driver": "Chandler Tube Driver", "tube-screamer": "Ibanez Tube Screamer",
    "univibe": "Shin-ei Uni-Vibe", "woolly-mammoth": "ZVex Woolly Mammoth", "zendrive": "Hermida Zendrive", "zw44": "MXR ZW-44 Wylde Overdrive",
}
_ACRONYMS = {"ABY", "SHO", "LPF", "HPF", "OCD", "RAT", "SLO", "BB", "EP", "AC", "RC", "GT", "OD", "GTOD", "PSU", "IV", "LFO", "II"}
_UTILITY = re.compile(r"aby|mixer|splitter|blender|filter", re.I)
_CATEGORY = {"soldano": "Preamp / Amp-in-a-box", "mark-iv": "Preamp / Amp-in-a-box", "sansamp": "Preamp / Amp-in-a-box", "bass-preamp": "Preamp / Amp-in-a-box",
             "bb-preamp": "Overdrive", "accutronics": "Reverb", "univibe": "Vibrato / Chorus", "slow-gear": "Other", "decimator": "Noise Gate", "nf1": "Noise Gate"}
_PLACE = re.compile(r"^\s*([A-Z]{1,3}\d{1,3})\s+(\S.*?)\s*$")
_PCS = re.compile(r"(\S+(?: \S+)?)\s+(\d+)\s*pcs\.?\s+\"([^\"]+)\"")


def parse_layout_lists(pages: list[str]) -> list[BomRow]:
    """The placement list pairs each designator with a value on its own line; the bill of
    materials repeats them as 'value Npcs. "R1 R2"' with the pots' tapers and the LED resistor."""
    rows: dict[str, BomRow] = {}
    text = "\n".join(pages)
    for m in _PCS.finditer(text):
        value, refs = m.group(1), m.group(3).split()
        value = re.sub(r"^Trimpot\s+", "", value)
        for ref in refs:
            if re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref) and ref not in rows:
                r = normalize_row(BomRow(ref=ref, value=value, notes="trimmer" if "Trimpot" in m.group(1) else ""))
                if is_plausible(r):
                    rows[ref] = r
    for ln in text.splitlines():
        m = _PLACE.match(ln)
        if not m or m.group(1) in rows:
            continue
        value = m.group(2).rstrip("*").strip()
        if len(value) > 24 or re.search(r"\b(?:pcs|and|the|to)\b", value):
            continue
        r = normalize_row(BomRow(ref=m.group(1), value=value))
        if is_plausible(r):
            rows[m.group(1)] = r
    return list(rows.values())


@register
class GuitarElectronics(Adapter):
    vendor = "guitarelectronics"

    def list_targets(self) -> Iterable[str]:
        seen: set[str] = set()
        for page in range(1, 12):
            h = self.f.get_text(f"{CATEGORY}/{page}", ".html") or ""
            links = sorted(set(re.findall(r'href="(/en_US/p/[^"/]+/\d+)"', h)))
            if not links or all(l in seen for l in links):
                break
            for l in links:
                seen.add(l)
                slug = l.split("/")[3]
                if "PCB" in slug and not _SKIP.search(slug):
                    yield BASE + l

    def parse(self, url: str) -> Circuit | None:
        h = self.f.get_text(url, ".html")
        if not h:
            return None
        slug = url.split("/")[-2].lower()
        title = clean_text(_html.unescape(re.sub(r"<[^>]+>", "", (re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [None, ""])[1])))
        name = re.sub(r"\s*\(?\bPCB\b(?:\s*set)?\)?\s*$|\s+PCB\s+set$", "", title, flags=re.I).strip()
        name = " ".join(w if re.search(r"\d", w) or all(part in _ACRONYMS for part in re.split(r"[^A-Za-z0-9]+", w) if part) else "-".join(x.capitalize() for x in w.split("-")) for w in name.split())
        name = re.sub(r"\bOf\b", "of", name).replace("Hog's", "Hog's").replace("Sansamp", "SansAmp").replace("Univibe", "Uni-Vibe")
        price = re.search(r'class="main-price">\s*€\s*([\d.,]+)', h)
        stock = re.search(r'<span class="second">\s*([^<]+?)\s*</span>', h)
        desc = html_to_text((re.search(r'itemprop="description"[^>]*>(.*?)</div>\s*</div>', h, re.S) or [None, ""])[1])
        img = re.search(r'property="og:image" content="([^"]+)"', h)
        pdfs = re.findall(r'href="(/en_US/p/file/[^"]+\.pdf)"', h, re.I)
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), "")
        c = Circuit(vendor=self.vendor, slug=slug.replace("-pcb", "").replace("-set", ""), name=name, url=url, based_on=based_on, description=desc[:700],
                    price=float(price.group(1).replace(",", ".")) if price else None, currency="EUR",
                    in_stock=None if not stock else "in stock" in stock.group(1).lower(), doc_url=BASE + pdfs[0] if pdfs else url,
                    image_url=img.group(1) if img else "", enclosure=find_enclosure(desc))
        for p in pdfs[1:]:
            c.extra_docs[_html.unescape(p.rsplit("/", 1)[-1]).replace("-", " ")[:40]] = BASE + p
        if pdfs:
            pdf = self.f.get_file(BASE + pdfs[0], ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                pages = pdf_text_pages(pdf)
                res = process_document(pdf, self.vendor, c.slug)
                c.bom = max(res["bom"], parse_layout_lists(pages), key=len)
                c.schematic_local, c.schematic_page = res["schematic_local"], res["schematic_page"]
                mv = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", pages[0] if pages else "")
                c.doc_version = mv.group(1) if mv else ""
                c.enclosure = c.enclosure or find_enclosure("\n".join(pages))
        c.category = next((v for k, v in _CATEGORY.items() if k in slug), "") or ("Utility" if _UTILITY.search(slug) else classify(name, based_on, desc[:300]))
        pots = [r for r in c.bom if r.category == "POT" and "trim" not in r.notes]
        c.controls = [f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else []
        return c
