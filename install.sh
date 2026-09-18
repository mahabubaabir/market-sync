#!/bin/bash
# Session Sync — installer for Linux Mint / Ubuntu (Cinnamon)
set -e
cd "$(dirname "$0")"

echo "== Session Sync installer =="
if [ -f /etc/os-release ]; then grep PRETTY_NAME /etc/os-release; fi

echo "[1/3] system packages (PyQt6 tray support)..."
sudo apt update
sudo apt install -y python3-pyqt6 python3-requests libnotify-bin

echo "[2/3] python extras (optional)..."
pip3 install --user -r requirements.txt || pip3 install --user --break-system-packages -r requirements.txt || echo "(pip step skipped — apt packages are enough for core app)"

echo "[3/3] autostart entry..."
mkdir -p ~/.config/autostart
sed "s|__HERE__|$(pwd)|g" autostart/session-sync.desktop > ~/.config/autostart/session-sync.desktop
echo "installed autostart -> ~/.config/autostart/session-sync.desktop"

echo ""
echo "Run:   python3 main.py"
echo "CLI:   python3 main.py --cli --news"
echo "Quit tray via right-click > Quit Session Sync"
