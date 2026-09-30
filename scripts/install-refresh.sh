#!/usr/bin/env bash
# Install (or reinstall) the weekly refresh as a launchd agent for this user.
# Remove it with: launchctl bootout gui/$(id -u)/com.cryptideffects.akashic-refresh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/Library/LaunchAgents/com.cryptideffects.akashic-refresh.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data/cache/refresh"
sed "s#__ROOT__#$ROOT#g" "$ROOT/scripts/akashic-refresh.plist" > "$DEST"
launchctl bootout "gui/$(id -u)/com.cryptideffects.akashic-refresh" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "installed: $DEST (Sundays 04:00; logs in $ROOT/data/cache/refresh/)"
