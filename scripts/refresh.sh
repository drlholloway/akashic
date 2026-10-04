#!/usr/bin/env bash
# Weekly refresh of the live site: re-fetch every vendor's pages (prices, stock, new boards; cached
# build documents are kept), audit the parts lists, and deploy only when the audit found no new flags
# on boards that were already there. Boards a vendor no longer lists are kept and marked delisted.
# Run by launchd (scripts/akashic-refresh.plist); safe to run by hand. Logs: data/cache/refresh/.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
LOG_DIR="$ROOT/data/cache/refresh"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%F).log"
exec >>"$LOG" 2>&1

notify() { osascript -e "display notification \"$1\" with title \"Akashic refresh\"" >/dev/null 2>&1 || true; }
echo "=== refresh started $(date)"

cd "$ROOT/scraper"
FAILED="$LOG_DIR/failed.txt"
: >"$FAILED"
export LOG_DIR FAILED
# Each vendor goes to sh as an argument (-n 1), not substituted into the command with -I{}: macOS
# xargs refuses an -I command longer than 255 bytes ("command line cannot be assembled, too long").
.venv/bin/python -c "from pcblib.vendors import REGISTRY, load_all; load_all(); print('\n'.join(sorted(REGISTRY)))" |
  xargs -P 4 -n 1 sh -c '
    for try in 1 2 3; do
      .venv/bin/pcblib scrape "$1" --refresh-pages > "$LOG_DIR/$1.log" 2>&1 && exit 0
      sleep 20
    done
    echo "$1" >> "$FAILED"' sh
grep -h "no longer listed\|far fewer than the library" "$LOG_DIR"/*.log 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | sort -u

.venv/bin/pcblib stats | tail -3
.venv/bin/pcblib audit --fail-on-added
status=$?
if [ "$status" -eq 3 ]; then
  echo "=== audit added flags on existing boards: not deploying; see data/cache/audit/parts-audit.html"
  notify "Not deployed: the audit found new problems on existing boards. See data/cache/refresh/$(date +%F).log"
  exit 3
elif [ "$status" -ne 0 ]; then
  echo "=== audit failed ($status): not deploying"
  notify "Not deployed: the audit failed. See the refresh log."
  exit "$status"
fi

cd "$ROOT/app"
if npm run deploy; then
  msg="Deployed."
  [ -s "$FAILED" ] && msg="Deployed; these vendors failed to refresh and kept last week's data: $(tr '\n' ' ' <"$FAILED")"
  echo "=== $msg $(date)"
  notify "$msg"
else
  echo "=== deploy failed $(date)"
  notify "The deploy failed. See the refresh log."
  exit 1
fi
