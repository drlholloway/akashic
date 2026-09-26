"""Apple Vision OCR, a second engine beside tesseract on macOS. It reads thin, small and
coloured type that tesseract garbles (Five Cats' blue tables on a dotted grid), so the OCR
passes in pdf.py add it as one more reading when it is available. Elsewhere every function
here returns nothing and tesseract works alone.

The helper is `vision.swift`, compiled on first use into data/cache/_bin. Word boxes are
cached next to the image as `<stem>-vision.tsv`."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from .paths import CACHE_DIR

_SOURCE = Path(__file__).with_name("vision.swift")
_BINARY = CACHE_DIR / "_bin" / "vision-ocr"

Word = tuple[int, int, int, int, str]


@lru_cache(maxsize=1)
def _binary() -> Path | None:
    if sys.platform != "darwin":
        return None
    if _BINARY.exists() and _BINARY.stat().st_mtime >= _SOURCE.stat().st_mtime:
        return _BINARY
    if not shutil.which("swiftc"):
        return None
    _BINARY.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["swiftc", "-O", str(_SOURCE), "-o", str(_BINARY)], capture_output=True, text=True)
    return _BINARY if proc.returncode == 0 and _BINARY.exists() else None


def available() -> bool:
    return _binary() is not None


# Vision's English model still returns Cyrillic look-alikes (470г, 1пF, СБ) and reads the
# micro sign as и, ш, р or h. A micro sign is only a micro sign between a digit and F.
_MICRO = re.compile(r"(?<=\d)[иишрhμнu](?=F\b)")
_LATIN = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "г": "r", "п": "n", "и": "u", "ш": "u",
    "к": "k", "м": "m", "т": "T", "Б": "6", "б": "6", "З": "3", "з": "3", "І": "I", "і": "i", "ј": "j", "Ż": "2", "ż": "2",
    "μ": "µ", "Ω": "Ω", "•": "", "·": "",
})


def latin(text: str) -> str:
    return _MICRO.sub("µ", text).translate(_LATIN)


def _size(png: Path) -> tuple[int, int]:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(png) as im:
        return im.size


def _tsv(png: Path) -> str:
    cache = png.with_name(png.stem + "-vision.tsv")
    if cache.exists() and cache.stat().st_mtime >= png.stat().st_mtime:  # an adapter may rewrite the image under the same name
        return cache.read_text()
    binary = _binary()
    if binary is None or not png.exists():
        return ""
    try:
        proc = subprocess.run([str(binary), str(png)], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return ""
    if proc.returncode != 0:
        return ""
    cache.write_text(proc.stdout)  # an empty result is a real answer (no text), unlike a failed run
    return proc.stdout


def words_by_line(png: Path) -> list[list[Word]]:
    """Word boxes in pixels, grouped by the text line Vision found them in."""
    tsv = _tsv(png)
    if not tsv.strip():
        return []
    width, height = _size(png)
    lines: dict[int, list[Word]] = {}
    for ln in tsv.splitlines():
        f = ln.split("\t")
        if len(f) != 7:
            continue
        text = latin(f[6]).strip()
        if not text:
            continue
        x0, y0, x1, y1 = (float(v) for v in f[1:5])
        lines.setdefault(int(f[0]), []).append((round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height), text))
    # A line cut by a band edge can come back from both bands; drop a word that repeats one
    # already kept with mostly the same box.
    kept: list[Word] = []
    out: list[list[Word]] = []
    for line in lines.values():
        mine = [w for w in line if not any(k[4] == w[4] and _overlap(k, w) > 0.5 for k in kept)]
        kept += mine
        if mine:
            out.append(mine)
    return out


def _overlap(a: Word, b: Word) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1
    return ix * iy / smaller


def words(png: Path) -> list[Word]:
    return [w for line in words_by_line(png) for w in line]


def text(png: Path, layout: bool = False) -> str:
    """Page text, one row per printed line. Vision reports a table row as several pieces
    (one per column), so pieces whose boxes overlap vertically are joined into one row.
    With `layout` the words sit at columns proportional to their x position, like
    tesseract's preserve_interword_spaces, so the text-table parsers can read the result;
    otherwise pieces on a row are separated by ' | ' when far apart and one space when close."""
    pieces = words_by_line(png)
    if not pieces:
        return ""
    heights = sorted(y1 - y0 for line in pieces for _, y0, _, y1, _ in line)
    h = max(1, heights[len(heights) // 2])
    char_w = max(1.0, sorted((x1 - x0) / max(1, len(t)) for line in pieces for x0, _, x1, _, t in line)[len(heights) // 2])
    rows: list[list[Word]] = []
    for line in sorted(pieces, key=lambda ws: sum(w[1] + w[3] for w in ws) / (2 * len(ws))):
        mid = sum(w[1] + w[3] for w in line) / (2 * len(line))
        if rows:
            last = rows[-1]
            last_mid = sum(w[1] + w[3] for w in last) / (2 * len(last))
            if abs(mid - last_mid) < h * 0.5:
                last.extend(line)
                continue
        rows.append(list(line))
    out: list[str] = []
    for row in rows:
        row.sort(key=lambda w: w[0])
        if layout:
            s = ""
            for x0, _, _, _, t in row:
                col = int(x0 / char_w)
                s += " " * max(1 if s else 0, col - len(s)) + t
            out.append(s)
        else:
            s = row[0][4]
            for prev, cur in zip(row, row[1:]):
                s += (" | " if cur[0] - prev[2] > 4 * char_w else " ") + cur[4]
            out.append(s)
    # "1 k": a value split at the unit
    return re.sub(r"(?<=\d) (?=(?:[kKM]|[pnuµ]F)\b)", "", "\n".join(out))
