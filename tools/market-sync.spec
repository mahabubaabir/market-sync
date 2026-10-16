# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Market Sync for Windows 10/11.

Build:  py -3 -m PyInstaller --noconfirm tools/market-sync.spec
Output: dist/MarketSync.exe  (windowed, single file)
"""
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = [(p, "assets") for p in glob.glob(os.path.join(ROOT, "assets", "*.svg"))]
ICON = os.path.join(ROOT, "assets", "icon.ico")

# Derive the Windows version resource from config.APP_VERSION so a version
# bump can never ship a mislabelled exe.
_cfg = open(os.path.join(ROOT, "config.py"), encoding="utf-8").read()
_m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _cfg)
APP_VERSION = _m.group(1) if _m else "0.0.0"
_quad = (APP_VERSION.split(".") + ["0", "0", "0", "0"])[:4]
_quad_s = "(" + ", ".join(str(int(x)) for x in _quad) + ")"
_tpl = open(os.path.join(SPECPATH, "version_info.txt"), encoding="utf-8").read()
VERSION_FILE = os.path.join(SPECPATH, f".version_info_{APP_VERSION}.txt")
with open(VERSION_FILE, "w", encoding="utf-8") as _f:
    _f.write(_tpl.replace("(1, 5, 3, 0)", _quad_s)
                  .replace('"1.5.3.0"', f'"{APP_VERSION}.0"'))

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=ASSETS,
    hiddenimports=["tzdata"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MarketSync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,               # tray app: no console window
    disable_windowed_traceback=False,
    icon=ICON if os.path.exists(ICON) else None,
    version=VERSION_FILE if os.path.exists(VERSION_FILE) else None,
)
