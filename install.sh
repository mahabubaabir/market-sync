#!/bin/bash
# Session Sync — one-line installer for Linux Mint / Ubuntu (and derivatives).
#
#   curl -sL https://raw.githubusercontent.com/mahabubaabir/market-sync/main/install.sh | sudo bash
#
# It downloads the latest release .deb from GitHub and installs it with apt,
# so dependencies (PyQt6 etc.) are resolved automatically.
set -e

REPO="mahabubaabir/market-sync"
APP="session-sync"
TMP="/tmp/${APP}-install.deb"

echo "== Session Sync installer =="

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer needs root. Run:" >&2
  echo "  curl -sL https://raw.githubusercontent.com/$REPO/main/install.sh | sudo bash" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required. Install it first: sudo apt install curl" >&2
  exit 1
fi

echo "[1/3] fetching latest release from github.com/$REPO ..."
JSON="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" || true)"
URL="$(printf '%s' "$JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for a in d.get("assets", []):
    if str(a.get("name", "")).endswith(".deb"):
        print(a.get("browser_download_url", ""))
        break
')"
TAG="$(printf '%s' "$JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(d.get("tag_name", ""))
')"

if [ -n "$URL" ]; then
  echo "[2/3] downloading $TAG ..."
  curl -fL "$URL" -o "$TMP"
else
  # No release yet? If this script sits inside a source checkout, build locally.
  HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"
  if [ -f "$HERE/build-deb.sh" ]; then
    echo "[2/3] no GitHub release found — building locally from $HERE ..."
    bash "$HERE/build-deb.sh"
    DEB="$(ls -1 "$HERE"/dist/${APP}_*_all.deb 2>/dev/null | head -n1)"
    if [ -z "$DEB" ]; then
      echo "ERROR: local build produced no .deb." >&2
      exit 1
    fi
    cp -f "$DEB" "$TMP"
  else
    echo "ERROR: no .deb asset in the latest release of $REPO." >&2
    echo "The maintainer must publish a release first (see README: Releasing)." >&2
    exit 1
  fi
fi

echo "[3/3] installing with apt (dependencies resolved automatically) ..."
apt-get install -y "$TMP"
rm -f "$TMP"

echo ""
echo "✓ Session Sync installed."
echo ""
echo "  Launch now:        session-sync"
echo "  Menu:              press Super, search \"Session Sync\""
echo "  It also starts automatically (silent, in tray) on your next login."
echo "  Quit:              tray icon → right-click → Quit  (or panel → Quit app)"
echo "  Uninstall:         sudo apt remove session-sync"
