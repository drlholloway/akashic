"""Polite HTTP fetching with an on-disk cache.

Every response is cached under data/raw/<vendor>/ keyed by a hash of the URL,
so re-running a scraper never re-hits the vendor unless --refresh is passed.
Requests to the same host are spaced out by `min_interval` seconds.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .paths import RAW_DIR

USER_AGENT = (
    "Akashic/0.1 (personal DIY pedal reference; "
    "contact via github.com/laneholloway)"
)


@dataclass
class Fetcher:
    vendor: str
    min_interval: float = 1.5
    refresh: bool = False
    timeout: float = 60.0
    _last_hit: dict[str, float] = field(default_factory=dict)
    _client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=self.timeout,
            )
        return self._client

    def _cache_path(self, url: str, ext: str) -> Path:
        digest = hashlib.sha1(url.encode()).hexdigest()[:16]
        d = RAW_DIR / self.vendor
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{digest}{ext}"

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        last = self._last_hit.get(host, 0.0)
        wait = self.min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def get_bytes(self, url: str, ext: str = ".bin") -> bytes | None:
        """Fetch a URL, returning bytes (cached). Returns None on 404/errors."""
        path = self._cache_path(url, ext)
        meta = path.with_suffix(path.suffix + ".json")
        if path.exists() and not self.refresh:
            return path.read_bytes()
        if meta.exists() and not self.refresh:
            # A previous attempt recorded a permanent failure (e.g. 404).
            info = json.loads(meta.read_text())
            if info.get("status") in (404, 410):
                return None
        self._throttle(url)
        try:
            r = self.client.get(url)
        except httpx.HTTPError as exc:
            meta.write_text(json.dumps({"url": url, "error": str(exc)}))
            return None
        meta.write_text(json.dumps({"url": url, "status": r.status_code,
                                    "content_type": r.headers.get("content-type")}))
        if r.status_code != 200:
            return None
        path.write_bytes(r.content)
        return r.content

    def get_text(self, url: str, ext: str = ".html") -> str | None:
        data = self.get_bytes(url, ext)
        return data.decode("utf-8", errors="replace") if data is not None else None

    def get_file(self, url: str, ext: str) -> Path | None:
        """Fetch and return the cached file path (for PDFs / images)."""
        if self.get_bytes(url, ext) is None:
            return None
        return self._cache_path(url, ext)
