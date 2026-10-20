"""HotKits adapter: Alex's PCBs (and a few kits and assembled boards) for guitar pedals and tube preamps,
sold by message (Facebook Messenger or email) from a price list that is a PDF on Google Drive. Each
entry of the list is a bold title ('Berzerk Overdrive (MXR ZW-44 Zakk Wylde Overdrive)': the board and,
in brackets, what it is based on), a description with the PCB size and enclosure, the price in USD and
the availability in their own columns, and a Google Drive link to the build document. The build
documents list the parts by type and value with a count ('Metal film resistor 1/4W 4k7 - 2 pcs'), no
designators, so the rows are named by count ('x2'), as for other lists without designators.

Kits and assembled boards of a circuit that is also sold as a PCB are folded into that circuit (their
prices go in the description); one sold only assembled is its own circuit. Full amplifiers, the
headphone amp, the amp's FX loop and the high-voltage converter module are not pedal circuits, and a
board whose build document is not out yet has nothing to list: they are left out."""
from __future__ import annotations

import re
from typing import Iterable

import pymupdf

from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import DATA_DIR
from ..pdf import process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

PRICE_LIST = "https://drive.google.com/file/d/1ygK7SWRpdzh3sskf5sgB9wa6OdG-bmi9/view"
_DL = "https://drive.google.com/uc?export=download&id={}"
FACEBOOK = "https://www.facebook.com/profile.php?id=61574483621561"
GROUP = "https://www.facebook.com/groups/975882099698845"
_SECTIONS = {"Distortion / Overdrive / Booster": "", "Fuzz": "Fuzz", "Delay / Reverb / Modulation": "", "Preamps / Amps": "Preamp / Amp-in-a-box",
             "Other": "", "Kits": "", "Assembled PCBs": ""}
_SKIP = re.compile(r"^(?:Young Rebel Amp|MarshAmp|Warm Tube Sound Headphones Amp|FX Loop Module|HV Converter)\b")
_UTILITY = re.compile(r"^(?:PowerPass|PedalPass)\b")
# Cyrillic letters that look like Latin ones, as typed in some part numbers ('IC МС33178Р').
_CYR = str.maketrans("АВСЕНКМОРТХаеорсху", "ABCEHKMOPTXaeopcxy")
_HARDWARE = re.compile(r"jack|socket(?! for)|foot ?(?:pedal )?switch|3PDT|enclosure|knob|rubber feet|battery|screw|nut\b|washer|wire|"
                       r"standoff|spacer|heat ?shrink|label|sticker|IC socket|DIP socket|panel", re.I)
_ROW = re.compile(r"^(?P<desc>.+?)\s*[-–—]\s*(?P<n>\d+)\s*pcs\.?\s*$", re.I)
_VOLTS = re.compile(r"\s+\d+(?:[.,]\d+)?\s?k?V\b.*$", re.I)


def _slug(title: str) -> str:
    name = re.sub(r"\s*\(.*$", "", title)
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _split_title(title: str) -> tuple[str, str]:
    """'Berzerk Overdrive (MXR ZW-44 Zakk Wylde Overdrive)' -> ('Berzerk Overdrive', 'MXR ZW-44 Zakk Wylde Overdrive');
    the bracket also holds a plain description ('Guitar preamp') or an assembly option, which are not originals."""
    m = re.match(r"^(.+?)\s*\((.+)\)\s*$", title)
    if not m:
        return clean_text(title), ""
    name, inner = clean_text(m.group(1)), clean_text(m.group(2))
    if re.match(r"^(?:JFET booster|Guitar preamp|Tube guitar preamp|Two-channel|Three-channel|Guitar cabinet simulator|Noise Gate|True Bypass)", inner, re.I) \
            or "assembly option" in inner:
        return name, ""
    inner = re.sub(r"^based on\s+", "", inner)
    inner = re.sub(r"(?:\s+based)?,?\s*preamp section(?:\s+emulator)?(?:\s*\(.*\))?$", " preamp", inner)
    inner = re.sub(r"(?:\s+based|\s+emulator|\s*\+ mods|,\s*\w+ channel)$", "", inner).strip(" ,")
    if "/" in inner and " " in inner.removesuffix(" preamp").split("/", 1)[1]:  # 'Dallas Rangemaster/Brian May Treble Booster': the first is the original
        inner = inner.split("/", 1)[0] + (" preamp" if inner.endswith(" preamp") else "")
    inner = {"Omni Drive": "John Hollis Omni Drive"}.get(inner, inner)
    return name, inner


def price_list(path) -> list[dict]:
    """Entries of the price list PDF: {title, section, text (lines), side (price and availability)}."""
    doc = pymupdf.open(path)
    out: list[dict] = []
    cur: dict | None = None
    section = ""
    for page in doc:
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"]).strip()
                if t:
                    lines.append((ln["bbox"][0], ln["bbox"][1], "Bold" in ln["spans"][0]["font"], ln["spans"][0]["size"], t))
        lines.sort(key=lambda x: (x[1], x[0]))
        started: list[tuple[float, dict]] = []
        side: list[tuple[float, str]] = []
        for x, y, bold, size, t in lines:
            if bold and size > 13 and t in _SECTIONS:
                section = t
            elif 490 < x < 670:
                side.append((y, t))
            elif bold and 40 < x < 70:
                cur = {"title": t, "section": section, "text": [], "side": []}
                out.append(cur)
                started.append((y, cur))
            elif cur and 40 < x < 490:
                cur["text"].append(t)
        for y, t in side:  # the price sits beside the middle of its entry, which may have begun on the page before
            owner = next((e for ey, e in reversed(started) if ey <= y + 2), None)
            if owner is None and out:
                owner = out[len(out) - len(started) - 1] if len(out) > len(started) else None
            if owner is not None:
                owner["side"].append(t)
    return out


def _part(desc: str, n: str) -> BomRow | None:
    """'Metal film resistor 1/4W 4k7' -> a resistor row of 4k7; hardware (jacks, enclosure, knobs) -> None."""
    d = clean_text(desc.translate(_CYR)).rstrip("*").strip()
    if _HARDWARE.search(d):
        return None
    note, cat, value = "", "", ""
    low = d.lower()
    if m := re.search(r"\(([^)]*)\)\s*$", d):  # '(tantalum)', '(DIP8)', '(1N914)', '(or OP07)'
        if not re.match(r"R=\d", m.group(1)):
            note = m.group(1)
        d = d[:m.start()].strip()
    if "potentiometer" in low or "trimmer" in low:
        cat = "TRIM" if "trimmer" in low else "POT"
        m = re.search(r"([ABCWL]?\d+(?:[.,]\d+)?[kKM]?)\s*$", d) or re.search(r"-([ABCWL]?\d+[kKM]?)\b", d)
        value = m.group(1) if m else ""
    elif re.search(r"photo ?resistor|\bLDR\b|GL55\d\d", d, re.I):
        cat, value = "OPTO", d.split()[-1]
    elif "resistor" in low:
        cat = "R"
        value = re.sub(r"\s*Ohm$", "", d, flags=re.I).split()[-1]  # 'Metal film resistor 1/4W 4k7', 'Resistor 1/4W 470 Ohm'
        if re.search(r"\bR ?LED\b", d, re.I):
            return None  # the LED's resistor, chosen to suit the LED; the documents give no value
    elif "capacitor" in low:
        cat = "C"
        body = re.sub(r"\([^)]*\)", " ", d)  # '(R=5mm)', '(100V)'
        caps = re.findall(r"(?<![\w.,=])(\d+(?:[.,]\d+)?[pnuµ]\d*|[pnuµ]\d+)F?(?![\w])", body)
        if not caps:
            return None
        value = caps[0].replace("µ", "u").replace(",", ".")
        if value[0] in "pnu":  # 'µ22' is 0.22u
            value = f"0.{value[1:]}{value[0]}"
        alts = re.findall(r"\((\d+(?:[.,]\d+)?[pnuµ]\d*)\)", d)  # 'Film capacitor 3n9 (3n3) 63V': the other value that works
        if alts:
            note = "; ".join([note] + [f"or {a.replace('µ', 'u')}" for a in alts])
        kind = re.match(r"^(.*?capacitor)", d, re.I)
        note = "; ".join(x for x in ((kind.group(1) if kind else ""), note) if x)
    elif re.match(r"^(?:diode|zener|schottky)", low):
        cat, value = "D", d.split(None, 1)[1] if " " in d else d
    elif re.match(r"^led\b", low):
        cat, value = "LED", "LED"
        note = "; ".join(x for x in (d[3:].strip(), note) if x)
    elif re.match(r"^(?:transistor|jfet|mosfet)", low):
        cat, value = "Q", d.split(None, 1)[1] if " " in d else d
    elif re.match(r"^(?:ic|chip|op-?amp)\b", low):
        cat, value = "IC", d.split(None, 1)[1] if " " in d else d
    elif re.match(r"^(?:vacuum )?tube\b|^valve\b", low):
        cat, value = "OTHER", d.split(None, 1)[1] if " " in d else d
    elif re.search(r"toggle|switch|relay", low):
        cat, value = ("SW" if "relay" not in low else "OTHER"), d
    elif re.search(r"inductor|choke|ferrite", low):
        cat, value = "L", d
    else:
        cat, value = "", d
    if cat in ("IC", "Q", "D"):  # 'LM308 (or OP07) DIP8', 'TL062 DIP8', 'MMBF 2N5457'
        alt = re.search(r"\(\s*or\s+([^)]+)\)", value)
        value = re.sub(r"\(\s*or\s+[^)]+\)", " ", value)
        value = re.sub(r"\b(?:DIP|SOIC|SOP|SO|TO)-?\d+\b", " ", value)
        if alt:
            note = "; ".join(x for x in (note, f"or {alt.group(1).strip()}") if x)
        if m := re.match(r"^MMBF\s+(\S+)$", value.strip()):
            value, note = m.group(1), "; ".join(x for x in (note, "SMD (MMBF)") if x)
    if re.search(r"BTDR|reverb (?:tank|module|brick)", value, re.I):
        cat, value = "OTHER", re.sub(r"^Module\s+", "", value)  # the Accutronics reverb brick
    value = re.sub(r"\s+", " ", value).strip(" ,")
    if not value:
        return None
    r = normalize_row(BomRow(ref=f"×{n}", value=value, part_type=d, notes=note, category=cat))
    return r if cat or is_plausible(r) else None


def build_doc(path) -> tuple[list[BomRow], list[str], str]:
    """The parts, the controls and the notes of a build document."""
    try:
        doc = pymupdf.open(path)
    except Exception:
        return [], [], ""
    text = "\n".join(p.get_text() for p in doc)
    rows: list[BomRow] = []
    lines = [ln.strip() for ln in text.splitlines()]
    heads = [i for i, ln in enumerate(lines) if re.match(r"^\d+\.\s*Parts? list\b(?!\s*\(variable)", ln, re.I)]
    variant, group = "", ""
    for ln in lines[heads[-1] + 1:] if heads else []:
        if re.match(r"^\d+\.\s+[A-Z]", ln):
            break  # the next section
        if m := re.match(r"^\d+\.\d+\.?\s+(.+)$", ln):  # '5.3 Violet Ram`s Head version', '5.1 Option GTO (Soldano Supercharger G.T.O.)'
            opt = re.match(r"^Option\s+(\S+)", m.group(1))
            variant = opt.group(1) if opt else re.sub(r"\s+version$", "", m.group(1)).replace("`", "'").strip()
            group = ""
            continue
        if ln.endswith(":") and "pcs" not in ln:
            group = ln[:-1].strip()  # 'Metal film resistors 0.6W-S (d2.5 L7)', the type of the lines under it
            continue
        m = _ROW.match(ln)
        if not m:
            continue
        desc = m.group("desc")
        if group and re.match(r"^\d", desc) and not re.match(r"^\d+(?:\.\d+)?\s*mm", desc):  # '820 Ohm - 1 pcs' under its type
            desc = re.sub(r"\s*\(d[\d.]+\s*L[\d.]+\)", "", group) + " " + desc
        r = _part(desc, m.group("n"))
        if r:
            r.variant = variant
            rows.append(r)
    if len({r.variant for r in rows}) < 2:
        for r in rows:
            r.variant = ""
    controls = []
    ctl = re.search(r"Controls\s*\n(.+?)\n\s*\d+\.\s", text, re.S)
    for m in re.finditer(r"^\s*-\s*(?:potentiometers?|toggle switch(?:es)?|switch|footswitch|rotary switch|trimmer)\s+([^(\n]+?)\s*(?:\(|[–-]\s)", ctl.group(1) if ctl else "", re.M | re.I):
        name = m.group(1).strip()
        if not re.search(r"trimmer", m.group(0), re.I):
            for n in re.split(r",\s*|\s+and\s+", name):  # 'potentiometers BASS, MIDDLE, TREBLE'
                controls.append(n.title() if n.isupper() else n)
    notes = re.search(r"\n\s*\d+\.\s*Notes\s*\n(.+?)(?:\n\s*\d+\.\s+[A-Z]|\Z)", text, re.S)
    return rows, list(dict.fromkeys(controls)), clean_text(notes.group(1)) if notes else ""


@register
class HotKits(Adapter):
    vendor = "hotkits"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.boards: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        url = _DL.format(PRICE_LIST.split("/d/")[1].split("/")[0])
        self.f.get_bytes(url, ".pdf", page=True)  # the list is the shop: --refresh-pages re-reads it
        pdf = self.f.get_file(url, ".pdf")
        if not pdf:
            return
        extra: dict[str, list[tuple[str, dict]]] = {}
        for e in price_list(pdf):
            name, _ = _split_title(e["title"])
            if _SKIP.match(name):
                continue
            slug = _slug(e["title"])
            if e["section"] in ("Kits", "Assembled PCBs"):
                extra.setdefault(slug, []).append((e["section"], e))
                continue
            if slug in self.boards:
                continue
            self.boards[slug] = {"entry": e, "extra": []}
        for slug, items in extra.items():
            if slug in self.boards:
                self.boards[slug]["extra"] = items
            else:  # sold only as a kit or assembled board
                self.boards[slug] = {"entry": items[0][1], "extra": items[1:], "only": items[0][0]}
        yield from self.boards

    def parse(self, slug: str) -> Circuit | None:
        b = self.boards.get(slug)
        if not b:
            return None
        e = b["entry"]
        text = " ".join(e["text"])
        doc = re.search(r"Build Doc:\s*(https://drive\.google\.com/\S+)", text)
        if not doc:
            print(f"  hotkits: no build document yet for {e['title']!r} ({' '.join(e['side'])})")
            return None
        name, based_on = _split_title(e["title"])
        price = next((float(t) for t in e["side"] if re.fullmatch(r"\d+(?:\.\d+)?", t)), None)
        status = " ".join(t for t in e["side"] if not re.fullmatch(r"\d+(?:\.\d+)?", t))
        about = re.split(r"\s(?:Sound samples?|Sound example|Build Doc|Pedal review)\b[^:]{0,30}:", text)[0]
        about = clean_text(re.sub(r"\s+", " ", about))
        offers = []
        for section, x in b["extra"]:
            what = "an assembled PCB" if section == "Assembled PCBs" else "a kit"
            opt = re.search(r"\(([^()]+?) assembly option\)", x["title"])  # 'Datura Tube Overdrive (Diezel VH4 assembly option)'
            price = _price(x)
            offers.append(f"{what}{f' ({opt.group(1)} option)' if opt else ''}" + (price if price.startswith(":") else f" {price}").rstrip())
        lines = []
        if b.get("only"):
            lines.append(f"Sold as {'an assembled PCB' if b['only'] == 'Assembled PCBs' else 'a kit'} only.")
            if offers:
                lines.append("Also as " + "; ".join(offers) + ".")
        elif offers:
            lines.append("Also sold as " + "; ".join(offers) + ".")
        description = " ".join([about] + lines)
        doc_url = doc.group(1).split("?")[0]
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=PRICE_LIST, based_on=based_on, description=description,
                    price=price, currency="USD", in_stock=bool(re.search(r"in stock", status, re.I)), doc_url=doc_url,
                    enclosure=find_enclosure(text))
        c.category = "Utility" if _UTILITY.match(name) else "EQ / Filter" if name == "Organica" else \
            "Preamp / Amp-in-a-box" if re.search(r"cab ?sim", name + e["title"], re.I) else _SECTIONS.get(e["section"]) or classify(name, based_on, about[:300])
        if c.category == "Other" and e["section"] == "Delay / Reverb / Modulation":
            c.category = classify(name + " " + about[:200], "", "")
        if not c.in_stock and status:
            c.tags.append(status.rstrip(".").capitalize())
        if b.get("only"):
            c.tags.append("assembled PCB" if b["only"] == "Assembled PCBs" else "kit")
        elif b["extra"]:
            c.tags.extend(sorted({"assembled PCB available" if s == "Assembled PCBs" else "kit available" for s, _ in b["extra"]}))
        samples = re.search(r"Sound (?:samples?|example)\b[^:]{0,30}:\s*(https://\S+)", text)
        if samples and "youtube" not in samples.group(1):
            c.extra_docs["Sound samples"] = samples.group(1)
        c.extra_docs["Price list (Google Drive)"] = PRICE_LIST
        c.extra_docs["Order: HotKits on Facebook"] = FACEBOOK
        c.extra_docs["HotKITs DIY community (Facebook group)"] = GROUP
        file_id = re.search(r"/d/([^/]+)|id=([^&]+)", doc_url)
        if file_id:
            pdf = self.f.get_file(_DL.format(file_id.group(1) or file_id.group(2)), ".pdf")
            if pdf and pdf.read_bytes()[:5] == b"%PDF-":
                c.doc_local = str(pdf.relative_to(DATA_DIR))
                res = process_document(pdf, self.vendor, c.slug)  # the schematic page, rendered for local use
                c.schematic_local, c.schematic_page = res["schematic_local"], res["schematic_page"]
                c.bom, controls, notes = build_doc(pdf)
                c.controls = controls
                if notes:
                    c.description += " Build notes: " + notes
        return c


def _price(e: dict) -> str:
    p = next((t for t in e["side"] if re.fullmatch(r"\d+(?:\.\d+)?", t)), "")
    status = " ".join(t for t in e["side"] if t != p)
    status = "" if re.fullmatch(r"in stock", status, re.I) else status.lower()
    return f": ${p}" + (f" ({status})" if status else "") if p else f"({status})" if status else ""
