"""Tayda Electronics adapter: DHEA's DIY guitar-effect PCBs, documented on the Tayda
Instruction Center (taydakits.com). Each instruction has a 'Designators and components' page
listing 'C1 47n <Tayda part>' per line, with named pots ('GAIN 10k-C') and switches. The
store's product page (readable with a browser user agent) gives the price; it is the buy link."""
from __future__ import annotations

import html as _html
import re
from typing import Iterable

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..taxonomy import classify
from . import register
from .base import Adapter, clean_text, html_to_text

BASE = "https://www.taydakits.com"
LISTING = "https://www.taydaelectronics.com/pcbs-breakout-boards-diy-kits/diy-guitar-effects.html?product_list_limit=100"
_STORE_ALIAS = {"linear-power-booster": "lpb", "bass-booster-hogs-foot": "bjtbooster", "treble-booster-brian-may": "treblebooster",
                "treble-booster-screaming-bird": "treblebooster", "distortus-maximums-1590b": "distortusmaximus1590benclosure", "boss-tone": "bosstonefuzz", "rat": "ratdistortion", "tubescreamer": "tubescreameroverdrive"}
_STORE_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
                  "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
CATEGORY = f"{BASE}/categories/diy-guitar-effects"
_SKIP = re.compile(r"enclosure|protoboard|footswitch|smd-transistor|charge-pump$|^looper$|loop-selector|guitar-amp|^champ$", re.I)
_UTILITY = re.compile(r"buffer", re.I)
_BASED_ON = {
    "super-hard-on": "ZVex Super Hard-On", "distortion": "MXR Distortion+", "les-lius": "RunOffGroove Les Lius", "eternity": "Lovepedal Eternity",
    "plexitone": "Carl Martin PlexiTone", "box-of-rock": "ZVex Box of Rock", "linear-power-booster": "Electro-Harmonix LPB-1",
    "bass-booster-hogs-foot": "Electro-Harmonix Hog's Foot", "treble-booster-screaming-bird": "Electro-Harmonix Screaming Bird",
    "treble-booster-brian-may": "Brian May treble booster", "electra-distortion": "Electra distortion", "cot50": "Lovepedal COT 50",
    "ep-booster": "Xotic EP Booster", "purple-plexi-800": "Lovepedal Purple Plexi 800", "fuzz-factory": "ZVex Fuzz Factory",
    "guv-nor": "Marshall Guv'nor", "fuzz-face": "Dallas Arbiter Fuzz Face", "tubescreamer": "Ibanez Tube Screamer", "tube-screamer": "Ibanez Tube Screamer",
    "rat": "ProCo RAT", "klon-buffer": "Klon Centaur buffer", "ocd-overdrive": "Fulltone OCD", "bsiab2": "Brown Sound in a Box 2",
    "shred-master": "Marshall Shred Master", "orange-squeezer": "Dan Armstrong Orange Squeezer", "stratoblaster": "Alembic Stratoblaster",
    "rangemaster": "Dallas Rangemaster", "range-master": "Dallas Rangemaster", "big-muff": "Electro-Harmonix Big Muff", "tone-bender": "Sola Sound Tone Bender",
    "box-of-metal": "ZVex Box of Metal", "od-1": "Boss OD-1", "dr-q": "Electro-Harmonix Doctor Q", "zendrive": "Hermida Zendrive",
    "mesa-boogie-distortion": "Dr. Boogie", "red-llama": "Way Huge Red Llama", "blues-breaker": "Marshall Blues Breaker", "full-drive": "Fulltone Fulldrive 2",
    "timmy": "Paul Cochrane Timmy", "od-eleven": "Lovepedal OD Eleven", "amp-eleven": "Lovepedal Amp Eleven", "woodrow": "Lovepedal Woodrow",
    "super-six-stevie": "Lovepedal Super Six Stevie", "muff-fuzz": "Electro-Harmonix Muff Fuzz", "micro-amp": "MXR Micro Amp",
    "satisfaction-fuzz": "Maestro FZ-1 Fuzz-Tone", "boss-tone": "Jordan Boss Tone", "klon-centaur": "Klon Centaur", "colorsound-tremolo": "Colorsound Tremolo",
    "bazz-fuzz": "Bazz Fuss", "sd-1": "Boss SD-1", "ac-rc-booster": "Xotic AC Booster / RC Booster", "distortus": "Distortus Maximus",
    "ea-tremolo": "EA Tremolo", "one-knob-fuzz": "", "english-man": "", "jfet-preamp": "", "mosfet-booster": "", "bjt-booster": "", "opamp-booster": "",
}
_LINE = re.compile(r"^([A-Z][A-Za-z0-9./]{0,11}(?: \([A-Za-z ]+\))?)\s{2,}(\S(?:.*?\S)?)\s{2,}\[(.*?)\](.*)$")
_SWITCH = re.compile(r"^(S\d|SW\d?|[A-Z]{3,12})\s*(\([^)]*\))?\s{2,}\[(.*?(?:SWITCH|SPDT|DPDT|3PDT).*?)\](.*)$", re.I)


def parse_component_list(html: str) -> list[BomRow]:
    seg = html
    starts = [seg.find(k) for k in ("COMPONENT LIST", "PCB DESIGNATORS", "COMPONENTS<") if seg.find(k) >= 0]  # SMD boards list only the pot and switches
    if starts:
        seg = seg[min(starts):]
    for stop in ("SCHEMATIC", "MODIFICATIONS", "BIASING"):
        j = seg.find(f"<strong>{stop}", 20)
        if j > 0:
            seg = seg[:j]
    seg = re.sub(r"<a [^>]*>", "[", seg).replace("</a>", "]")
    seg = re.sub(r"<br\s*/?>|</p>", "\n", seg)
    text = _html.unescape(re.sub(r"<[^>]+>", "", seg)).replace("\xa0", " ")
    rows: list[BomRow] = []
    seen: dict[str, BomRow] = {}
    for ln in text.splitlines():
        ln = ln.strip()
        m = _LINE.match(ln)
        if m:
            ref, value, ptype, note = m.groups()
            note = clean_text(note).strip("() ")
            cat = ""
            if re.search(r"POTENTIOMETER", ptype, re.I) and not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref):
                cat, ref = "POT", ref.title()
            elif re.search(r"TRIMMER", ptype, re.I) or re.search(r"trimmer", value, re.I):
                value, note = re.sub(r"\s*Trimmer", "", value, flags=re.I), ("trimmer; " + note).strip("; ")
            elif not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", ref):
                continue
            r = normalize_row(BomRow(ref=ref, value=value, part_type=ptype.title(), notes=note, category=cat))
            if not (cat or is_plausible(r)):
                continue
            key = ref.upper()
            if key in seen:  # a second value for the same designator is a mod, noted on the first row
                if note and not re.search(r"original", note, re.I):
                    seen[key].notes = (seen[key].notes + f"; {value} to {note[0].lower() + note[1:]}").strip("; ")
                continue
            seen[key] = r
            rows.append(r)
            continue
        m = _SWITCH.match(ln)
        if m:
            ref, label, ptype, _ = m.groups()
            name = (label or "").strip("() ").title() or ref
            if name.upper() in seen:
                continue
            kind = re.search(r"SPDT|DPDT|3PDT|SP3T|DP3T", ptype, re.I)
            r = normalize_row(BomRow(ref=name, value=kind.group(0).upper() if kind else "switch", part_type=ptype.title(), category="SW"))
            seen[name.upper()] = r
            rows.append(r)
    return rows


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@register
class Tayda(Adapter):
    vendor = "tayda"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.titles: dict[str, str] = {}
        self.store: list[tuple[set[str], str, float | None]] = []  # (name keys, product url, price)

    def _load_store(self) -> None:
        """The store's category listing: every board's product page and price, keyed by the
        names in its title ('English Man / Les Lius DIY PCB Guitar Effect' names two)."""
        h = self.f.get_text(LISTING, ".html", headers=_STORE_HEADERS) or ""
        prices = {pid: float(amt) for pid, amt in re.findall(r'data-product-id="(\d+)".{0,600}?data-price-amount="([\d.]+)"', h, re.S)}
        for href, label, pid in re.findall(r'class="[^"]*product-item-link[^"]*"\s+href="([^"]+)"[^>]*aria-label="([^"]+)"[^>]*slide-desc-(\d+)', h):
            name = _html.unescape(_html.unescape(label)).replace("\xa0", " ")
            name = re.sub(r"(?i)\b(?:DIY|PCB|Guitar|Effects?|Kit)\b", " ", name)
            keys = {_key(name)} | {_key(part) for part in re.split(r"\s*[/()]\s*", name) if part.strip()}
            self.store.append((keys - {""}, href, prices.get(pid)))

    def list_targets(self) -> Iterable[str]:
        self._load_store()
        h = self.f.get_text(CATEGORY, ".html") or ""
        for slug, title in re.findall(r'<a href="/instructions/([a-z0-9-]+)"[^>]*>\s*([^<]{2,80}?)\s*<', h):
            if slug in self.titles or _SKIP.search(slug):
                continue
            self.titles[slug] = _html.unescape(title)
            yield slug

    def parse(self, slug: str) -> Circuit | None:
        url = f"{BASE}/instructions/{slug}"
        h = self.f.get_text(url, ".html")
        if not h:
            return None
        title = clean_text(self.titles.get(slug) or _html.unescape((re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or [None, slug])[1]))
        name = re.sub(r"\s*\((?:1590B|3 knobs)[^)]*\)\s*$|\s+1590B$", "", title).strip()
        desc = ""
        m = re.search(r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>', h, re.S)
        if m:
            desc = html_to_text(m.group(1))
        if not desc:
            paras = [html_to_text(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", h, re.S)]
            desc = next((x for x in paras if len(x) > 60), "")
        pages = dict(re.findall(r'href="(/instructions/[a-z0-9-]+/pages/([a-z0-9-]+?)(?:--\d+)?)"', h))
        comp = next((p for p, n in pages.items() if "designator" in n or "component" in n), "") or next((p for p, n in pages.items() if n == "pcb"), "")
        store = re.search(r'href="(https?://www\.taydaelectronics\.com/[^"]*(?:pcb|guitar-effect)[^"]*\.html)"', h)
        img = re.search(r'<img[^>]+src="(https://www\.taydaelectronics\.com/media/catalog/product/[^"]+)"', h)
        based_on = next((v for k, v in _BASED_ON.items() if k in slug), "")
        tags = ["SMD"] if re.search(r"smd", slug) else []
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=store.group(1).replace("http://", "https://") if store else url, based_on=based_on,
                    description=desc[:700], currency="USD", doc_url=BASE + comp if comp else url, image_url=img.group(1) if img else "", tags=tags)
        for p, n in pages.items():
            if p != comp:
                c.extra_docs[n.replace("-", " ").capitalize()] = BASE + p
        wanted = {_key(slug), _key(name), _STORE_ALIAS.get(slug, "")} - {""}
        listed = next((e for e in self.store if e[0] & wanted), None) or next((e for e in self.store if any(k.startswith(w) or w.startswith(k) for k in e[0] for w in wanted if len(w) > 4)), None)
        if listed:
            c.url, c.price = listed[1], listed[2]
        if store and c.price is None:
            shop = self.f.get_text(c.url, ".html", headers=_STORE_HEADERS) or ""
            mp = re.search(r'itemprop="price"[^>]*content="([\d.]+)"', shop)
            if mp:
                c.price = float(mp.group(1))
            if not c.image_url:
                mi = re.search(r'property="og:image" content="([^"]+)"', shop)
                c.image_url = mi.group(1) if mi else ""
        if comp:
            page = self.f.get_text(BASE + comp, ".html") or ""
            c.bom = parse_component_list(page)
            if not c.doc_version:
                mv = re.search(r"COMPONENT LIST\s*\(([^)]+)\)", _html.unescape(re.sub(r"<[^>]+>", "", page)))
                c.doc_version = mv.group(1) if mv else ""
        c.category = "Utility" if _UTILITY.search(slug) else classify(name, based_on, desc[:300])
        pots = [r for r in c.bom if r.category == "POT" and "trimmer" not in r.notes]
        named = list(dict.fromkeys(r.ref for r in pots if not re.fullmatch(r"[A-Z]{1,3}\d{1,3}", r.ref)))
        c.controls = named or ([f"{len(pots)} knobs"] if len(pots) > 1 else ["1 knob"] if pots else [])
        c.controls += list(dict.fromkeys(r.ref for r in c.bom if r.category == "SW" and not re.fullmatch(r"S\d|SW\d?", r.ref)))
        return c
