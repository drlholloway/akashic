"""turretboard.org (now kept at turretboard.knucklehead.dk): stripboard, perfboard, tagboard and turret
layouts of vintage fuzzes, boosters and wahs by Sinner and b.man, posted 2011-2012 on WordPress. Most
posts link the layout as a DIY Layout Creator PDF ('project file') whose labels are text, so the parts
are read from it (layouts.diylc_pdf); the earliest posts have only the drawing as a PNG. Titles give the
build in brackets ('[0.1" pitch stripboard] Ibanez - Standard Fuzz'). A family page ('Tone Bender
Family') holds many circuits, split here by hand; versions of one circuit in a post (Version I, II, III)
become parts-list variants, and the same circuit drawn for another board is listed as an alternate build."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from ..layouts import controls, diylc_pdf, legend_rows
from ..models import BomRow, Circuit
from ..taxonomy import classify, classify_within, find_enclosure
from . import register
from .base import Adapter, clean_text, html_to_text

SITE = "https://turretboard.knucklehead.dk"
API = SITE + "/wp-json/wp/v2/posts?per_page=100&page={page}"
UPLOADS = SITE + "/wp-content/uploads/"

_CATS = {4: {"Boost", "Utility"}, 6: {"Fuzz"}, 10: {"Tremolo", "Vibrato / Chorus", "Ring Mod / Synth"},
         12: {"Overdrive", "Distortion"}, 20: {"Wah / Envelope", "EQ / Filter"}}
_DEFAULT = {4: "Boost", 6: "Fuzz", 10: "Tremolo", 12: "Overdrive", 20: "Wah / Envelope"}
_NOT_PEDALS = {3, 19}  # amp layouts and chassis plans; the gallery of original units (photos, no layout)
# Old layouts the site redrew in a later post (the Fuzz Face and Big Muff families), and a build photo.
_SKIP = {"0-1-pitch-perf-dunlop-ej-f1-eric-johnson-signature-fuzz-face", "0-1-pitch-perf-dunlop-jbf-3-joe-bonamassa-fuzz-face",
         "vero-fuzz-face-bc183l", "vero-74-big-muff-pi-rams-head"}
# How the board is built, from the title's brackets or the drawing's own notes.
_BUILDS = [(r"turret", "turret"), (r"eyelet", "turret"), (r"tag ?board|\btag\b|terminal", "tagboard"),
           (r"perf|pref", "perfboard"), (r"strip ?board|vero", "vero"), (r"point to point", "p2p"), (r"\bpcb\b", "pcb")]

# Posts with several circuits or versions, by post slug: each circuit's name, original and category, its
# drawings as (variant label, file under uploads/, build), and the same circuit drawn for another board.
_SPLIT: dict[str, list[dict]] = {
    "rangemaster-treble-booster-family": [
        {"name": "Dallas Rangemaster", "based_on": "Dallas Rangemaster", "category": "Boost",
         "files": [("Rangemaster", "2012/06/rangemaster.pdf", "vero"), ("With input cap blend", "2012/06/rangemaster_input_cap_blend.pdf", "vero")]}],
    "tube-screamer-page": [
        {"name": "Ibanez TS808 Tube Screamer", "based_on": "Ibanez TS808 Tube Screamer", "files": [("", "2012/05/808.pdf", "vero")], "images": ["2012/05/808.png"]},
        {"name": "Ibanez TS9 Tube Screamer", "based_on": "Ibanez TS9 Tube Screamer", "files": [("", "2012/05/TS9.pdf", "vero")]},
        {"name": "Son of Tube Screamer", "based_on": "Ibanez Tube Screamer", "files": [("", "2012/05/sots.pdf", "vero")]},
        {"name": "Son of Clay Jones Overdrive", "based_on": "Clay Jones Overdrive",
         "files": [("Standard", "2012/05/socj.pdf", "vero"), ("Bass knob and clipping switch", "2012/05/socj_bass.pdf", "vero")]}],
    "0-1-stripboard-and-0-15-pitch-veroboard-ibanez-double-sound-fuzz": [
        {"name": "Ibanez Double Sound Fuzz", "based_on": "Ibanez Double Sound",
         "files": [("Small (fits a 1590B)", "2012/05/IBZdoubleSOUNDfuzzBSIZE.pdf", "vero"), ("Large, 0.15\" pitch", "2012/05/IBZdoubleSOUNDfuzzBIG.pdf", "vero")]}],
    "fuzz-face-family": [
        {"name": "Dunlop EJ-F1 Eric Johnson Fuzz Face", "based_on": "Dunlop EJ-F1 Eric Johnson Fuzz Face",
         "files": [("", "2012/05/EJF1revision1.pdf", "perfboard")], "also": [("2012/05/EJF1-15pitchvero.pdf", "vero")]},
        {"name": "Dunlop JBF-3 Joe Bonamassa Fuzz Face", "based_on": "Dunlop JBF-3 Joe Bonamassa Fuzz Face",
         "files": [("", "2012/05/JBF-3-revision2.pdf", "perfboard")]},
        {"name": "Dallas Arbiter Fuzz Face (BC183L)", "based_on": "Dallas Arbiter Fuzz Face",
         "files": [("", "2012/05/Fuzz-Face-NPN-BC183L-revision1.pdf", "vero")]},
        {"name": "John Hollis RockFace", "based_on": "John Hollis RockFace", "files": [("", "2012/05/rockfacestripboard.pdf", "vero")]}],
    "0-15-pitch-veroboard-colorsound-power-boost-overdriver": [
        {"name": "Colorsound Power Boost (early)", "based_on": "Colorsound Power Boost", "category": "Boost",
         "files": [("Stock", "2012/05/powerboostearlyrev1.pdf", "vero"), ("Monkeyxx mods", "2012/05/powerboostearlyMonkeyxx.pdf", "vero")]},
        {"name": "Colorsound Power Boost (later)", "based_on": "Colorsound Power Boost", "category": "Boost",
         "files": [("Stock", "2012/05/powerboostlaterrev1.pdf", "vero"), ("Monkeyxx mods", "2012/05/powerboostlaterMonkeyxxmods.pdf", "vero")]},
        {"name": "Colorsound Overdriver", "based_on": "Colorsound Overdriver", "category": "Overdrive",
         "files": [("Stock", "2012/05/overdriverrev1.pdf", "vero"), ("Monkeyxx mods", "2012/05/overdriverremonkeyxxmods.pdf", "vero")],
         "images": ["2012/05/overdriverrev1.png"]}],
    "0-1-pitch-stripboard-sam-ash-fuzz-stainer": [
        {"name": "Sam Ash Fuzz-Stainer", "based_on": "Sam Ash Fuzz-Stainer",
         "files": [("Stock", "2012/04/torgfuzzstainer.pdf", "vero"), ("External bias pot", "2012/04/xtrnlbiastainrer.pdf", "vero")]}],
    "tagboard-os-mutantes-fuzz-deadpool": [
        {"name": "Os Mutantes Fuzz", "based_on": "Os Mutantes Fuzz", "files": [("", "2012/04/os_mutantes.pdf", "tagboard")]},
        {"name": "Madbean Deadpool", "based_on": "Madbean Deadpool", "files": [("", "2012/04/deadpool.pdf", "tagboard")]}],
    "various-maestro-fz-1-fuzz-tone": [
        {"name": "Maestro FZ-1 Fuzz-Tone", "based_on": "Maestro FZ-1 Fuzz-Tone",
         "files": [("Version I", "2012/04/fuzztonefz1v1.pdf", "vero"), ("Version II", "2012/04/fuzztonefz1v2.pdf", "vero")],
         "also": [("2012/04/fuzztonefz1v3.pdf", "perfboard")], "images": ["2012/04/fuzztonefz1v3.png"]}],
    "point-to-point-pigdog-driver": [
        {"name": "Pigdog Driver", "based_on": "Pigdog Driver", "category": "Boost",
         "files": [("Pigdog Driver", "2012/03/driver.pdf", "tagboard"), ("Kick-Ass (input cap blend)", "2012/03/kick-ass_pigdog_driver_specs.pdf", "tagboard")]}],
    "0-1-pitch-perf-guild-foxey-lady": [
        {"name": "Guild Foxey Lady (grey)", "based_on": "Guild Foxey Lady", "files": [("", "2011/12/Grey-Foxey-rev1.pdf", "perfboard")]},
        {"name": "Guild Foxey Lady (silver, 2 knobs)", "based_on": "Guild Foxey Lady", "files": [("", "2011/12/Silver-2knob-Foxey.pdf", "perfboard")]}],
    "0-15-pitch-vero-wilsic-sound-wah-wah": [
        {"name": "Wilsic Sound Wah Wah", "based_on": "Wilsic Sound Wah Wah",
         "files": [("PNP (original)", "2011/12/Wilsic-Sound-Wah-Wah-project.pdf", "vero"), ("NPN", "2011/12/Wilsic-Sound-Wah-Wah-project-NPN.pdf", "vero"),
                   ("NPN, E-B-C pinout", "2011/12/Wilsic-Sound-Wah-Wah-project-NPN-C-B-E.pdf", "vero")]}],
    "vero-big-muff-%cf%80-family-and-clones": [
        {"name": "Electro-Harmonix Big Muff Pi Ram's Head", "based_on": "Electro-Harmonix Big Muff Pi",
         "files": [("'47' Ram's Head", "2011/10/47-Rams-Head.pdf", "vero"), ("Ram's Head 73#18", "2011/10/Rams-Head-7318.pdf", "vero"),
                   ("1973 Violet, 1st version", "2011/10/1973-Violet-Rams-Head-1st-Version.pdf", "vero"),
                   ("1973 Violet, 2nd version", "2011/10/1973-Violet-Rams-Head-2nd-Version.pdf", "vero")]},
        {"name": "J Mascis Red & Black Big Muff", "based_on": "Electro-Harmonix Big Muff Pi", "files": [("", "2011/10/J-Mascis-RedBlack.pdf", "vero")]},
        {"name": "Big Muff Pi with AMZ presence control", "based_on": "Electro-Harmonix Big Muff Pi", "files": [("", "2011/10/BMPAMZ.pdf", "vero")]}],
    "vero-wem-rush-pepbox": [
        {"name": "WEM Rush Pepbox", "based_on": "WEM Rush Pepbox",
         "files": [("Germanium (PNP)", "2011/09/WEM-Rush-Pepbox-PNP-GE.pdf", "vero"), ("Silicon (NPN)", "2011/09/WEM-Rush-Pepbox-NPN-Si.pdf", "vero")]}],
    "vero-vox-repeat-percussion": [
        {"name": "VOX Repeat Percussion", "based_on": "VOX Repeat Percussion", "category": "Tremolo",
         "files": [("Stock", "2011/09/VOX-Repeat-Percussion.pdf", "vero"), ("Ring mod", "2011/09/VOX-Repeat-Percussion-ring-mod.pdf", "vero"),
                   ("Ring mod with LED", "2011/09/VOX-Repeat-Percussion-ring-mod-LED.pdf", "vero")],
         "also": [("2011/09/VOX-Repeat-Percussion-Tagboard.pdf", "tagboard")]}],
    "tone-bender-mk1-34-stfu": [
        {"name": "VOX Tone Bender (JEN Fuzz)", "based_on": "VOX Tone Bender", "files": [("", "2011/09/voxtbjenfuzz.pdf", "vero")],
         "also": [("2011/09/vox_tag.pdf", "tagboard")]},
        {"name": "Sola Sound Tone Bender MK1", "based_on": "Sola Sound Tone Bender MKI", "files": [("", "2011/09/mk1.pdf", "perfboard")],
         "also": [("2011/09/mk1-ghurst-spec-vero.pdf", "vero")]},
        {"name": "Sola Sound Tone Bender MK1.5", "based_on": "Sola Sound Tone Bender MK1.5", "files": [("", "2011/09/Tone-Bender-15rev3.pdf", "vero")],
         "also": [("2011/09/mk15tag.pdf", "tagboard")]},
        {"name": "Sola Sound Tone Bender MKII STFU (short circuit board)", "based_on": "Sola Sound Tone Bender MKII",
         "files": [("1960s original", "2011/09/Tonebender-Vintage-STFU-short-circuit-board-transitional-fuzz-unit.pdf", "vero"),
                   ("D*A*M reissue (Blue Meanie)", "2011/09/Tonebender-SCB-Blue-Meanie.pdf", "vero"),
                   ("Reissue with 100R limiting resistor", "2011/09/Tonebender-SCB-Blue-Meanie-+-100R.pdf", "vero")]},
        {"name": "Sola Sound Tone Bender Professional MKII", "based_on": "Sola Sound Tone Bender MKII",
         "files": [("Standard", "2011/09/tbmk2profinal.pdf", "vero"), ("15000pF input and output caps", "2011/09/tbmk2damacarisrevfinal.pdf", "vero")],
         "also": [("2011/09/turretbender.pdf", "tagboard")]},
        {"name": "Pocket Bender", "based_on": "Sola Sound Tone Bender MKII", "files": [("", "2011/09/professionakmkiismall.pdf", "vero")]},
        {"name": "Sola Sound Tone Bender MKIII (early)", "based_on": "Sola Sound Tone Bender MKIII", "files": [("", "2011/09/MKIIIearly.pdf", "vero")]},
        {"name": "Sola Sound Tone Bender MKIV (1970-72)", "based_on": "Sola Sound Tone Bender MKIV", "files": [("", "2011/09/MK4-70-72.pdf", "vero")]},
        {"name": "Sola Sound Tone Bender MKIV (1972-76, Batman logo)", "based_on": "Sola Sound Tone Bender MKIV",
         "files": [("", "2011/09/MK4-72-76-Batman-Logo.pdf", "vero")]},
        {"name": "Tone Bender MKIII / MKIV universal layout", "based_on": "Sola Sound Tone Bender MKIII", "files": [("", "2012/03/mkiii.pdf", "vero")],
         "images": ["2012/03/mkiii.png"]},
        {"name": "D*A*M Fuzz Sound MK3", "based_on": "D*A*M Fuzz Sound", "files": [("", "2011/09/DAM-FS-MK3.pdf", "vero")]},
        {"name": "D*A*M Fuzz Sound Black On Black", "based_on": "D*A*M Fuzz Sound", "files": [("", "2011/09/DAM-FS-Black.pdf", "vero")]},
        {"name": "D*A*M The Mother Fucker", "based_on": "D*A*M The Mother Fucker",
         "files": [("Grease", "2011/09/DAM-MF-Grease.pdf", "vero"), ("Smoke", "2011/09/DAM-MF-Smoke.pdf", "vero")]},
        {"name": "Prescription Electronics Yard Box", "based_on": "Prescription Electronics Yard Box", "files": [("", "2011/09/Yard-Box.pdf", "vero")]}],
    # The universal MKIII/MKIV file is listed on the Tone Bender page; this post's own drawing is the PNG.
    "0-15-pitch-vero-mad-fuzz-sound": [
        {"name": "D*A*M Fuzz Sound", "based_on": "D*A*M Fuzz Sound", "files": [], "images": ["2012/03/fs.png"]}],
    "veroboard-hornby-skewes-jhs-zonk-machine": [
        {"name": "Hornby Skewes Zonk Machine", "based_on": "Hornby Skewes Zonk Machine",
         "files": [("Version I", "2011/03/zonkv1.pdf", "vero"), ("Version II", "2011/03/zonkv2.pdf", "vero"),
                   ("Version III (early prototype)", "2011/03/zonkv3.pdf", "vero")]}],
    "vero-1968-marshall-supa-fuzz-mk2": [
        {"name": "Marshall Supa Fuzz MK2", "based_on": "Marshall Supa Fuzz",
         "files": [("Stock", "2011/02/Marshall-Supa-Fuzz-MK2.pdf", "vero"), ("With 100R limiting resistor", "2011/02/Marshall-Supa-Fuzz-MK2-+-100R.pdf", "vero")],
         "images": ["2011/02/supamk2vero.png"]},
        {"name": "Marshall Supa Fuzz", "based_on": "Marshall Supa Fuzz", "files": [("", "2011/02/Marshall-Supa-Fuzz.pdf", "vero")],
         "images": ["2011/02/Supafuzz.png"]},
        {"name": "Marshall Supa Fuzz Proto", "based_on": "Marshall Supa Fuzz", "files": [("", "2011/02/Marshall-Supa-Fuzz-Proto.pdf", "vero")]}],
    "tagboard-baldwin-burns-buzzaround": [
        {"name": "Baldwin-Burns Buzzaround", "based_on": "Baldwin-Burns Buzzaround",
         "files": [("Replica", "2011/10/buzzaround.pdf", "tagboard"), ("Small tagboard", "2011/10/buzz_tag.pdf", "tagboard")],
         "also": [("2011/10/buzz.pdf", "vero")]}],
    "0-1-pitch-stripboard-elka-dizzy-tone": [
        {"name": "Elka Dizzy Tone", "based_on": "Elka Dizzy Tone", "files": [("", "2012/03/elka.pdf", "vero")],
         "also": [("2012/03/elka_tag.pdf", "tagboard")]}],
    "perfboard-vox-grey-wah-wah": [
        {"name": "VOX Grey Wah-Wah", "based_on": "VOX Grey Wah-Wah",
         "files": [("Production (rev. 3)", "2011/02/GreyWahProductionRev3.pdf", "perfboard"), ("Pre-production prototype", "2011/02/VOX-Grey-Wah-Wah-Proto.pdf", "perfboard")],
         "docs": {"Drilling template": "2011/02/Template-Grey-Wah-Wah.pdf"}}],
}

# Single-circuit posts whose title is not the original as the library names it: (name, original).
_NAMES = {
    "vero-exh-lpb-1-linear-power-booster": ("Electro-Harmonix LPB-1 Linear Power Booster", "Electro-Harmonix LPB-1"),
    "vero-exh-screaming-bird-treble-booster": ("Electro-Harmonix Screaming Bird Treble Booster", "Electro-Harmonix Screaming Bird"),
    "vero-cornishs-g2-buffer": ("Pete Cornish G2 Buffer", "Pete Cornish G2"),
    "stripboard-klon-buffer": ("Klon Buffer", "Klon Centaur buffer"),
    "veroboard-madbean-fatpants-ep-3-pre-with-bonus": ("Madbean Fatpants (EP-3 preamp)", "Madbean Fatpants"),
    "tagboard-eternity-burst": ("Lovepedal Eternity Burst", "Lovepedal Eternity Burst"),
    "tagboard-eternity-v3": ("Lovepedal Eternity V3", "Lovepedal Eternity"),
    "terminal-npn-rangemaster-with-mods": ("Dallas Rangemaster (NPN, Peter Davidoff mods)", "Dallas Rangemaster"),
    "tagboard-1977-op-amp-big-muff-pi": ("Electro-Harmonix Op-Amp Big Muff Pi (1977)", "Electro-Harmonix Op-Amp Big Muff Pi"),
    "tagboard-1966-germanium-fuzz-face": ("Dallas Arbiter Fuzz Face (1966, germanium)", "Dallas Arbiter Fuzz Face"),
    "tagboard-uproar-based-on-the-suhr-riot": ("Uproar", "Suhr Riot"),
    "tagboard-pro-co-rat-landgraff-mod": ("ProCo Rat (Landgraff MOD)", "ProCo Rat"),
    "tag-orange-squeezer": ("Dan Armstrong Orange Squeezer", "Dan Armstrong Orange Squeezer"),
    "tag-anal-mans-cock-of-joy": ("Analogman King of Tone", "Analogman King of Tone"),
    "tag-paul-c-timmy": ("Paul Cochrane Timmy", "Paul Cochrane Timmy"),
    "tag-mp-little-green-wonder-yats-knock-off": ("Mad Professor Little Green Wonder", "Mad Professor Little Green Wonder"),
    "tag-dod-250-by-gaussmarkov": ("DOD 250 Overdrive Preamp", "DOD 250"),
    "tag-zendrive": ("Hermida Zendrive", "Hermida Zendrive"),
    "tag-srv-special-ts808": ("SRV Special TS808", "Ibanez TS808 Tube Screamer"),
    "vero-ep-3-preamp-section": ("Echoplex EP-3 Preamp", "Maestro Echoplex EP-3 preamp"),
    "tag-yaff-69-70-fuller-mods": ("YAFF (Fulltone '69 and '70 mods)", "Fulltone '69"),
    "vero-1966-triangle-big-muff-pi": ("Electro-Harmonix Big Muff Pi (Triangle)", "Electro-Harmonix Big Muff Pi"),
    "vero-fuzz-friendly-wah-wah-buffer": ("Fuzz Friendly Wah-Wah Buffer", ""),
    "0-1-pitch-perf-wah-wah": ("Wah-Wah", "VOX Wah-Wah"),
    "396": ("Marshall Supa Wah", "Marshall Supa Wah"),
    "perfboard-vox-cry-baby": ("VOX Cry Baby", "Thomas Organ Cry Baby"),
}
# Where the site's category is too broad: wahs among the old layouts, a compressor under Other, octave fuzzes.
_CATEGORY = {"perfboard-vox-v847": "Wah / Envelope", "perfboard-vox-mccoy": "Wah / Envelope", "perfboard-vox-cry-baby": "Wah / Envelope",
             "tag-orange-squeezer": "Compressor", "0-1-pitch-stripboard-colorsound-octivider": "Octave / Pitch",
             "vero-dunlop-octavio": "Octave / Pitch", "0-1-pitch-perf-wind-machine": "Other", "vero-ep-3-preamp-section": "Boost"}
_BUILD_NAME = {"vero": "Stripboard", "tagboard": "Tagboard", "perfboard": "Perfboard", "turret": "Turret board", "pcb": "PCB"}
_THUMB = re.compile(r"-\d{2,4}x\d{2,4}\.(?:png|jpe?g)$", re.I)


def _build(text: str) -> str:
    text = re.sub(r"(?:www\.)?turretboard\.?org", "", text, flags=re.I)
    return next((b for rx, b in _BUILDS if re.search(rx, text, re.I)), "")


def _uploads(content: str) -> list[str]:
    """Files under uploads/ the post links or shows, in order, as 'YYYY/MM/name'."""
    return list(dict.fromkeys(_html.unescape(u) for u in re.findall(r'(?:href|src)="https?://turretboard\.knucklehead\.dk/wp-content/uploads/([^"]+)"', content)))


@register
class Turretboard(Adapter):
    vendor = "turretboard"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.posts: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page = 1
        while True:
            raw = self.f.get_text(API.format(page=page), ".json")
            posts = json.loads(raw) if raw else []
            for p in posts:
                self.posts[p["slug"]] = p
                parts = _SPLIT.get(p["slug"], [None])
                yield from ([p["slug"]] if len(parts) == 1 else [f'{p["slug"]}#{i + 1}' for i in range(len(parts))])
            if len(posts) < 100:
                return
            page += 1

    def _pdf(self, path: str) -> dict | None:
        pdf = self.f.get_file(UPLOADS + path, ".pdf")
        if not pdf or pdf.read_bytes()[:5] != b"%PDF-":
            return None  # a few project files are gone: the site answers with its 404 page
        return diylc_pdf(pdf)

    def _image(self, path: str) -> dict:
        """A drawing posted only as an image: the notes under the board, by Vision OCR (cached, never exported)."""
        from .. import vision
        img = self.f.get_file(UPLOADS + path, "." + path.rsplit(".", 1)[-1].lower())
        text = vision.text(img) if img and vision.available() else ""
        return {"rows": legend_rows(text), "controls": controls(text), "text": text, "board": ""}

    def parse(self, target: str) -> Circuit | None:
        slug, _, nth = target.partition("#")
        p = self.posts.get(slug)
        if p is None or slug in _SKIP or set(p["categories"]) & _NOT_PEDALS:
            return None
        content = p["content"]["rendered"]
        title = clean_text(_html.unescape(p["title"]["rendered"]))
        files = _uploads(content)
        pngs = [f for f in files if re.search(r"\.png$", f, re.I) and not _THUMB.search(f)]
        bracket = (re.match(r"\[([^\]]+)\]", title) or [None, ""])[1]
        name = re.sub(r"\s+[-–]\s+", " ", re.sub(r"^\[[^\]]*\]\s*(?:[-–]\s*)?", "", title)).strip()
        spec = (_SPLIT.get(slug) or [None])[int(nth) - 1 if nth else 0]
        if spec is None:
            pdfs = [f for f in files if f.lower().endswith(".pdf")]
            name, based_on = _NAMES.get(slug, (name, name))
            spec = {"name": name, "based_on": based_on, "files": [("", f, "") for f in pdfs], "images": pngs}
        build = next((b for _, _, b in spec["files"] if b), "") or _build(bracket) or "vero"

        variants: list[tuple[str, dict]] = []
        also: list[dict] = []
        docs: dict[str, str] = {}
        for label, path, b in spec["files"]:
            read = self._pdf(path)
            if read is None:
                continue
            b = b or _build(read["text"]) or build
            stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if b != build:
                also.append({"build": b, "url": UPLOADS + path})
                docs[f"{_BUILD_NAME.get(b, b.title())} layout"] = UPLOADS + path
                continue
            variants.append((label or stem, read))
            docs[f"Layout: {label or stem}" if len(spec["files"]) > 1 else "Layout (PDF)"] = UPLOADS + path
        for b_path, b in spec.get("also", []):
            if self._pdf(b_path) is not None:
                also.append({"build": b, "url": UPLOADS + b_path})
                docs[f"{_BUILD_NAME.get(b, b.title())} layout"] = UPLOADS + b_path
        for k, path in spec.get("docs", {}).items():
            docs[k] = UPLOADS + path
        stems = {path.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() for _, path, _ in spec["files"]}
        images = spec.get("images") or [f for f in pngs if f.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() in stems]
        if not variants:
            if not images:
                return None  # a post whose layout was taken down (the D*A*M posts) or a page of links
            variants = [("", self._image(images[0]))]

        rows: list[BomRow] = []
        if len(variants) == 1:
            rows = variants[0][1]["rows"]
        else:
            for label, read in variants:
                for r in read["rows"]:
                    r.variant = label
                    rows.append(r)
        first = variants[0][1]
        layout = {"build": build, "images": [UPLOADS + f for f in images[:6]]}
        if first["board"] and build in ("vero", "perfboard"):
            layout["board"] = first["board"]
        if also:
            layout["also"] = list({a["build"]: a for a in also}.values())

        body = html_to_text(content)
        if len(_SPLIT.get(slug) or []) > 1:
            # The paragraph that links this circuit's first drawing, else a pointer to the post.
            key = spec["files"][0][1] if spec["files"] else (images[0] if images else "")
            para = next((html_to_text(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", content, re.S) if key and key in x), "")
            body = para if len(para) > 60 else f"One of {len(_SPLIT[slug])} circuits on the post '{name}'."
        cats = [c for c in p["categories"] if c in _CATS]
        allowed = set().union(*(_CATS[c] for c in cats)) if cats else set()
        category = spec.get("category") or _CATEGORY.get(slug) or (
            classify_within(allowed, spec["name"], spec["based_on"], body[:300], default=_DEFAULT[cats[0]]) if allowed
            else classify(spec["name"], body[:300]))
        # One circuit of a family page goes by its own name ('2011-09-sola-sound-tone-bender-mk1'), the rest by the post's.
        circuit_slug = p["date"][:7] + "-" + re.sub(r"[^a-z0-9]+", "-", (spec["name"].lower() if nth else re.sub(r"%[0-9a-f]{2}", "", slug))).strip("-")
        return Circuit(
            vendor=self.vendor, slug=circuit_slug, name=spec["name"], url=p["link"], based_on=spec["based_on"],
            description=body[:3000], category=category, tags=[t for t in [bracket] if t],
            price=None, currency="USD", doc_url=p["link"], doc_version=p["date"][:10], extra_docs=docs,
            enclosure=find_enclosure(body), layout=layout, controls=[k for k in first["controls"] if not re.fullmatch(r"[A-Z]{1,2}", k)], bom=rows,
        )
