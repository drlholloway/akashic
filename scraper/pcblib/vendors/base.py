from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Iterable

from ..fetch import Fetcher
from ..models import Circuit


class Adapter(ABC):
    vendor: str = ""

    def __init__(self, fetcher: Fetcher):
        self.f = fetcher

    @abstractmethod
    def list_targets(self) -> Iterable[str]:
        """Yield every candidate identifier (usually a URL) to parse."""

    @abstractmethod
    def parse(self, target: str) -> Circuit | None:
        """Parse one target into a Circuit, or None if it is not a PCB project."""


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("®", "").replace("™", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def html_to_text(html: str) -> str:
    """Very small HTML -> text conversion that keeps paragraph/list breaks."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    html = re.sub(r"</(p|div|li|h\d|tr|br)\s*>|<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<li[^>]*>", "• ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    import html as _h
    return clean_text(_h.unescape(html))
