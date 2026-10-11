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
