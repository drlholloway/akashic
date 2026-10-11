"""Dirtbox Layouts adapter: stripboard (vero) layouts, most with a legend of the active parts
and a link to the schematic they were drawn from. See blogger.py."""
from __future__ import annotations

from . import register
from .blogger import BloggerLayouts


@register
class Dirtbox(BloggerLayouts):
    vendor = "dirtbox"
    blog = "dirtboxlayouts.blogspot.com"
    build = "vero"
    not_layouts = frozenset({"back-from-wilderness"})  # news, with photographs
