#!/bin/bash
# Session Sync — background launcher (dev checkout).
# Closing the terminal will NOT kill the app when you use this.
# Usage:
#   ./run.sh            # tray + panel once
#   ./run.sh --hidden   # tray only (what autostart uses)
cd "$(dirname "$0")"
LOG_DIR="$HOME/.cache/session-sync"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/app.log"
# rotate at 1 MB so it never grows unbounded
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 1048576 ]; then
  mv -f "$LOG" "$LOG.1"
fi
setsid nohup python3 main.py "$@" >>"$LOG" 2>&1 < /dev/null &
echo "Session Sync launched in background (log: $LOG)"
echo "Left-click tray icon: panel (has Hide + Quit). Right-click: full menu."
