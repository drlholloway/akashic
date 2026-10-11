"""Tagboard Effects adapter: the largest collection of stripboard (vero) layouts for pedals,
with some tag strip layouts, each marked Verified once a reader has built it. See blogger.py."""
from __future__ import annotations

from . import register
from .blogger import BloggerLayouts


@register
class TagboardEffects(BloggerLayouts):
    vendor = "tagboardeffects"
    blog = "tagboardeffects.blogspot.com"
    build = "vero"
    # News, guides and photographs of tools: read by eye, no board among the pictures.
    not_layouts = frozenset({
        "merry-christmas", "a-million-hits", "depressed", "man-cave-back-up-and-running", "who-wants-to-build-this",
        "vero-layout-guide", "fault-finding-build", "third-hand-helping-hand-alternative", "offboard-wiring",
        "negative-and-positive-ground-effects", "test-box-20", "pcb-dpdt-daughter-board-with-millenium",
    })
    split = {
        "and-few-more": [("9V to 18V Charge Pump", "Utility"), ("D*A*M 1966", "Fuzz"), ("LofoMofo", "Distortion"), ("Dallas Rangemaster NPN", "Boost")],
        "few-veros": [("Mosrite Fuzzrite", "Fuzz"), ("Landgraff Boost", "Boost"), ("Electro-Harmonix LPB1", "Boost"),
                      ("Dallas Arbiter Fuzz Face PNP", "Fuzz"), ("Dallas Arbiter Fuzz Face NPN", "Fuzz")],
    }
