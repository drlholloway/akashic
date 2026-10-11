"""Effects Layouts blog adapter (storyboardist): perfboard layouts, each drawn beside a
single-sided PCB of the same circuit to etch at home. Not the Effects Layouts shop
(effectslayouts.py), which sells fabricated boards. See blogger.py."""
from __future__ import annotations

from . import register
from .blogger import BloggerLayouts


@register
class EffectsLayoutsBlog(BloggerLayouts):
    vendor = "effectslayouts-blog"
    blog = "effectslayouts.blogspot.com"
    build = "perfboard"
