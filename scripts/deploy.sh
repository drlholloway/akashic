#!/usr/bin/env bash
# Export the library data, build the static site, and publish it to Cloudflare (Workers static assets).
# One-time setup: `cd app && npx wrangler login` (opens the browser).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/scraper" && .venv/bin/pcblib export          # metadata, BOMs and links only; never --images for a public deploy
cd "$ROOT/app" && npm run build
npx wrangler deploy "$@"
