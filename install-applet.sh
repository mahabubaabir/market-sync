#!/bin/bash
# Market Sync — Cinnamon panel applet installer / restorer.
#
#   ./install-applet.sh          # install (or reinstall) on the Cinnamon panel
#   ./install-applet.sh --remove # remove it from the panel entirely
#
# The applet shows the live session countdowns in your top bar and opens the
# same glass panel as the tray icon (left-click), with a right-click menu.
set -e
cd "$(dirname "$0")"
HERE="$(pwd)"

APPLET_UUID="market-sync@cinnamon"
LEGACY_UUID="market-countdown@cinnamon"
TARGET_DIR="$HOME/.local/share/cinnamon/applets/${APPLET_UUID}"
SRC_DIR="${HERE}/cinnamon-applet/${APPLET_UUID}"

remove_from_panel() {
    python3 - <<'EOF'
import ast, subprocess
uuid = "market-sync@cinnamon"
legacy = "market-countdown@cinnamon"
try:
    res = subprocess.run(["gsettings", "get", "org.cinnamon", "enabled-applets"],
                         capture_output=True, text=True, timeout=2)
    applets = ast.literal_eval(res.stdout.strip())
    applets = [a for a in applets if uuid not in a and legacy not in a]
    subprocess.run(["gsettings", "set", "org.cinnamon", "enabled-applets", str(applets)],
                   check=True, timeout=2)
    print("✓ Removed from the Cinnamon panel")
except Exception as e:
    print("Note: could not update panel automatically:", e)
EOF
}

enable_on_panel() {
    python3 - <<'EOF'
import ast, subprocess
uuid = "market-sync@cinnamon"
legacy = "market-countdown@cinnamon"
try:
    res = subprocess.run(["gsettings", "get", "org.cinnamon", "enabled-applets"],
                         capture_output=True, text=True, timeout=2)
    applets = ast.literal_eval(res.stdout.strip())
    applets = [a for a in applets if legacy not in a]
    if not any(uuid in a for a in applets):
        ids = []
        for p in applets:
            parts = p.split(":")
            if len(parts) >= 5 and parts[4].isdigit():
                ids.append(int(parts[4]))
        next_id = (max(ids) + 1) if ids else 1
        applets.append(f"panel1:right:1:{uuid}:{next_id}")
        subprocess.run(["gsettings", "set", "org.cinnamon", "enabled-applets", str(applets)],
                       check=True, timeout=2)
        print("✓ Market Sync applet added to the Cinnamon panel!")
    else:
        # re-save to force Cinnamon to reload the applet code
        subprocess.run(["gsettings", "set", "org.cinnamon", "enabled-applets", str(applets)],
                       check=True, timeout=2)
        print("✓ Market Sync applet already enabled — reloaded")
except Exception as e:
    print("Note: could not update the panel automatically:", e)
    print("      Add it manually: Right-click panel → Applets → Market Sync")
EOF
}

if [ "$1" = "--remove" ]; then
    echo "== Removing Market Sync Cinnamon applet =="
    remove_from_panel
    rm -rf "$TARGET_DIR"
    echo "✓ Applet files removed. (The Market Sync app itself is untouched.)"
    exit 0
fi

echo "== Installing / restoring Market Sync Cinnamon applet =="

if [ ! -d "$SRC_DIR" ]; then
    echo "ERROR: applet sources not found at $SRC_DIR" >&2
    echo "Run this script from the Market Sync source folder." >&2
    exit 1
fi

# 1. clean legacy applet, copy the current one
rm -rf "$HOME/.local/share/cinnamon/applets/${LEGACY_UUID}" 2>/dev/null || true
mkdir -p "$TARGET_DIR"
cp -r "$SRC_DIR"/* "$TARGET_DIR/"

# 2. patch the fallback app directory (used only when 'market-sync' is not
#    on PATH, e.g. running straight from a source checkout)
python3 - "$HERE" "$TARGET_DIR/applet.js" <<'EOF'
import sys
here, applet_file = sys.argv[1], sys.argv[2]
try:
    with open(applet_file, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace('const PATCHED_APP_DIR = "__APP_DIR__";',
                              f'const PATCHED_APP_DIR = {here!r};')
    with open(applet_file, "w", encoding="utf-8") as f:
        f.write(content)
    print("✓ Applet patched with app dir:", here)
except Exception as e:
    print("Note: patch skipped:", e)
EOF

# 3. enable on the panel
enable_on_panel

echo ""
echo "---------------------------------------------------------------"
echo "DONE! Market Sync now lives on your Cinnamon top panel."
echo ""
echo "  • Top bar:  ● LON +04:05   ○ NYC -00:35   (bright open / dim closed)"
echo "  • Left-click: opens the same glass panel as the tray icon"
echo "  • Right-click: Toggle / Preferences… / Quit"
echo ""
echo "  The standalone tray icon stays too (both-in-one). To hide it:"
echo "  Preferences → uncheck \"Show standalone tray icon alongside panel applet\""
echo ""
echo "  Remove later with: ./install-applet.sh --remove"
