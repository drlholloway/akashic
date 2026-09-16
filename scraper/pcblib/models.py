from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class BomRow:
    ref: str                 # R1, C4, IC1, VOLUME ...
    value: str               # 1K5, 4u7, LM308, A100K ...
    part_type: str = ""      # "Resistor, 1/4W", "Film capacitor, 7.2 x 2.5mm"
    notes: str = ""
    category: str = ""       # R C D Q IC POT SW LED L XTAL OTHER  (filled by normalize)
    norm_value: str = ""     # canonical value string, e.g. "1.5k", "4.7u", "LM308"
    sort_key: float = 0.0    # numeric for R/C sorting, 0 otherwise


@dataclass
class Circuit:
    vendor: str              # vendor slug: pedalpcb, aionfx, madbean, guitarpcb, fuzzdog
    slug: str                # vendor-local identifier (pcb038, hexatron-optical-phaser)
    name: str
    url: str                 # canonical product page (the "buy" link)
    subtitle: str = ""       # "Optical Phaser"
    based_on: str = ""       # "ProCo Rat", "Mu-tron Phasor II"
    description: str = ""    # plain text
    category: str = ""       # top-level: Overdrive, Distortion, Fuzz, Modulation, ...
    effect_type: str = ""    # finer: "Optical phaser"
    tags: list[str] = field(default_factory=list)
    enclosure: str = ""      # 125B, 1590B ...
    controls: list[str] = field(default_factory=list)
    difficulty: str = ""
    price: float | None = None
    currency: str = "USD"
    sku: str = ""
    in_stock: bool | None = None
    doc_url: str = ""        # build documentation PDF
    doc_local: str = ""      # cached PDF path (relative to data/)
    extra_docs: dict[str, str] = field(default_factory=dict)  # label -> url
    image_url: str = ""      # product/PCB image
    schematic_local: str = ""  # rendered schematic page PNG (relative to data/)
    schematic_page: int | None = None
    doc_version: str = ""
    bom: list[BomRow] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.vendor}:{self.slug}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d
