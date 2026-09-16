from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # cached vendor HTML / PDFs, keyed by vendor
CACHE_DIR = DATA_DIR / "cache"      # extracted images and rendered previews
DB_PATH = DATA_DIR / "library.sqlite"
EXPORT_DIR = REPO_ROOT / "app" / "static" / "data"

for _d in (RAW_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
