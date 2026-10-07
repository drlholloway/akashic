"""Eff Dub Audio adapter: a WordPress blog of DIY pedal projects. No board is sold; most posts link a
"file pack" zip (schematic and layout images, a build guide PDF on older ones, Eagle CAD files), and
the rest show the schematic as an image in the post. Parts come from, in order: the pack's Eagle
schematic (exact, read from the XML), its build guide PDF, or OCR of the schematic image. A BOM typed
into the post (the author's own build, which can differ from the pack) becomes an 'As posted' variant."""
from __future__ import annotations

import html as _html
import io
import json
import re
import zipfile
from typing import Iterable

from ..eagle import eagle_bom
from ..models import BomRow, Circuit
from ..normalize import is_plausible, normalize_row
from ..paths import CACHE_DIR, DATA_DIR
from ..pdf import ocr_schematic_bom, process_document
from ..taxonomy import classify, find_enclosure
from . import register
from .base import Adapter, clean_text

BASE = "https://effdubaudio.com"
API = f"{BASE}/wp-json/wp/v2"
CATEGORY = 8  # Effects Projects
_NOT_EFFECT = re.compile(r"charge pump|circuit snippets", re.I)
_BASED_ON = {
    "the-snitch-a-proco-rat-clone-project": "ProCo RAT", "astrotone-fuzz-clone": "Sam Ash Astrotone",
    "shoot-the-moon-tremolo": "4MS Tremulus Lune", "duovibe-optical-vibe-phaser": "Tim Escobedo Wobbletron",
    "pt2399-project-tweak-tone": "Mad Professor Deep Blue Delay", "zen-drive-project": "Hermida Zendrive",
    "onesie-bazz-fuss-project": "Home Wrecker Bazz Fuss", "germanium-bazz-fuss": "Home Wrecker Bazz Fuss",
    "electra-distortion-schematic-and-layouts": "Electra MPC Distortion", "wahscillator": "Run Off Groove Phozer",
}
_CATEGORY = {"wahscillator": "Wah / Envelope", "duovibe-optical-vibe-phaser": "Vibrato / Chorus",
             "electra-distortion-schematic-and-layouts": "Overdrive", "basic-metal-fet": "Distortion",
             "dead-easy-dirt-v2-reboot": "Distortion"}
_POST_ROW = re.compile(r"\b([A-Z]{1,3}\d{1,2}|GAIN|VOL(?:UME)?|TONE|LEVEL|DRIVE|DEPTH|SPEED|RATE|MIX|TIME|BIAS)\s*[–-]\s*"
                       r"([0-9][0-9.]*\s?[kKMRpnuµ]?[0-9]*[A-Za-z]?\d*|[A-Z0-9]{2,}\d[A-Z0-9]*|omit)\b")


def _text(html: str) -> str:
    t = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", html, flags=re.S)
    t = re.sub(r"</(?:p|h\d|li|div)>", "\n", t)
    return re.sub(r"[ \t]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _full_size(url: str) -> str:
    return re.sub(r"-\d+x\d+(\.\w+)$", r"\1", url)  # WordPress thumbnail -> the uploaded file


def _post_bom(text: str) -> list[BomRow]:
    """'R1 – 2M2 R2 – 33K ... GAIN – B250K' typed into the post."""
    rows, seen = [], set()
    for ref, value in _POST_ROW.findall(text):
        if value.lower() == "omit" or ref in seen:
            continue
        seen.add(ref)
        knob = not re.match(r"[A-Z]{1,3}\d", ref)
        r = normalize_row(BomRow(ref=ref.title() if knob else ref, value=value.replace("µ", "u"),
                                 category="POT" if knob else "", part_type="Potentiometer" if knob else ""))
        if knob or is_plausible(r):
            rows.append(r)
    return rows if len(rows) >= 5 else []


@register
class EffDub(Adapter):
    vendor = "effdub"

    def __init__(self, fetcher):
        super().__init__(fetcher)
        self.posts: dict[str, dict] = {}

    def list_targets(self) -> Iterable[str]:
        page = 1
        while True:
            raw = self.f.get_text(f"{API}/posts?categories={CATEGORY}&per_page=100&page={page}", ".json")
            posts = json.loads(raw) if raw and raw.lstrip().startswith("[") else []
            for p in posts:
                self.posts[p["slug"]] = p
                yield p["slug"]
            if len(posts) < 100:
                break
            page += 1

    def _pack(self, html: str) -> str:
        """The post's file pack zip: linked directly, or through a WordPress attachment page."""
        m = re.search(r'href="(https://effdubaudio\.com/wp-content/uploads/[^"]+\.zip)"', html)
        if m:
            return m.group(1)
        m = re.search(r'href="https://effdubaudio\.com/\?attachment_id=(\d+)"', html)
        if m:
            raw = self.f.get_text(f"{API}/media/{m.group(1)}?_fields=source_url,mime_type", ".json")
            media = json.loads(raw) if raw else {}
            if str(media.get("source_url", "")).endswith(".zip"):
                return media["source_url"]
        return ""

    def parse(self, slug: str) -> Circuit | None:
        post = self.posts.get(slug)
        if not post:
            return None
        title = clean_text(_html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"])))
        if _NOT_EFFECT.search(title):
            return None
        bits = [b.strip() for b in re.split(r"\s+[–-]\s+|:\s+", title)]
        name = bits[-1] if bits[0].endswith("Project") else bits[0]  # 'Zen Drive Project – Bodhi' is the Bodhi
        page = self.f.get_text(post["link"]) or ""
        article = page[page.find("<article"):page.find("</article>")] if "<article" in page else post["content"]["rendered"]
        html = post["content"]["rendered"] + article
        text = _text(post["content"]["rendered"])
        c = Circuit(vendor=self.vendor, slug=slug, name=name, url=post["link"], doc_url=post["link"],
                    description=text[:1500], based_on=_BASED_ON.get(slug, ""), price=None, currency="USD",
                    doc_version=(post.get("modified") or post.get("date") or "")[:10],
                    enclosure=find_enclosure(re.sub(r"(?i)(?:larger|bigger) than (?:a )?\w+", "", text)))  # 'fits any box larger than 1590A' 
        c.category = _CATEGORY.get(slug) or classify(title, c.based_on, text[:400])
        images = list(dict.fromkeys(_full_size(u) for u in re.findall(
            r'(?:src|href)="(https://effdubaudio\.com/wp-content/uploads/[^"]+\.(?:png|jpe?g))"', html, re.I)))
        c.image_url = next((u for u in images if not re.search(r"sch", u, re.I)), images[0] if images else "")
        schem_img = next((u for u in images if re.search(r"sch", u, re.I)), "")
        if not schem_img and not self._pack(html):  # no pack: the post's drawing is the schematic (Wahscillator)
            schem_img = next((u for u in images if not re.search(r"pcb|layout|etch|eyelet|ptp|perf", u, re.I)), "")

        file_bom: list[BomRow] = []
        schem_png = None
        pack = self._pack(html)
        if pack:
            c.extra_docs["File pack (schematic, layout, Eagle CAD)"] = pack
            path = self.f.get_file(pack, ".zip")
            if path and zipfile.is_zipfile(path):
                files: dict[str, bytes] = {}

                def walk(zf: zipfile.ZipFile) -> None:
                    for n in zf.namelist():
                        data = zf.read(n)
                        if n.lower().endswith(".zip") and zipfile.is_zipfile(io.BytesIO(data)):
                            walk(zipfile.ZipFile(io.BytesIO(data)))
                        else:
                            files[n] = data
                walk(zipfile.ZipFile(path))
                for n, data in files.items():
                    if n.lower().endswith(".sch") and not file_bom:
                        file_bom = eagle_bom(data)
                guide = next((n for n in files if n.lower().endswith(".pdf")), "")
                if guide:
                    pdf = CACHE_DIR / self.vendor / f"{slug}-guide.pdf"
                    pdf.parent.mkdir(parents=True, exist_ok=True)
                    pdf.write_bytes(files[guide])
                    c.doc_local = str(pdf.relative_to(DATA_DIR))
                    if not file_bom:
                        file_bom = process_document(pdf, self.vendor, slug)["bom"]
                png = next((n for n in files if re.search(r"sch", n, re.I) and n.lower().endswith((".png", ".jpg"))), "")
                if png:
                    schem_png = CACHE_DIR / self.vendor / f"{slug}-schematic{png[png.rfind('.'):].lower()}"
                    schem_png.parent.mkdir(parents=True, exist_ok=True)
                    schem_png.write_bytes(files[png])
        if schem_img:
            c.extra_docs["Schematic image"] = schem_img
            if not schem_png:
                got = self.f.get_file(schem_img, schem_img[schem_img.rfind("."):].lower())
                if got:
                    schem_png = CACHE_DIR / self.vendor / f"{slug}-schematic{got.suffix}"
                    schem_png.parent.mkdir(parents=True, exist_ok=True)
                    schem_png.write_bytes(got.read_bytes())
        if schem_png:
            c.schematic_local, c.schematic_page = str(schem_png.relative_to(DATA_DIR)), 1
            if not file_bom:
                file_bom = [BomRow(ref=r.ref, value=r.value, part_type=r.part_type, notes="OCR from schematic",
                                   category=r.category, norm_value=r.norm_value, sort_key=r.sort_key)
                            for r in ocr_schematic_bom(schem_png)]
        posted = _post_bom(text)
        if posted and file_bom:
            c.bom = [_v(r, "As posted") for r in posted] + [_v(r, "File pack") for r in file_bom]
        else:
            c.bom = posted or file_bom
        first = [r for r in c.bom if r.variant in ("", "As posted")]
        c.controls = [r.ref for r in first if r.category == "POT"]
        return c


def _v(r: BomRow, variant: str) -> BomRow:
    return BomRow(ref=r.ref, value=r.value, part_type=r.part_type, notes=r.notes, category=r.category,
                  norm_value=r.norm_value, sort_key=r.sort_key, variant=variant)
