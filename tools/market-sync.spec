# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Market Sync for Windows 10/11.

Build:  py -3 -m PyInstaller --noconfirm tools/market-sync.spec
Output: dist/MarketSync.exe  (windowed, single file)
"""
import glob
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = [(p, "assets") for p in glob.glob(os.path.join(ROOT, "assets", "*.svg"))]
ICON = os.path.join(ROOT, "assets", "icon.ico")
VERSION_FILE = os.path.join(SPECPATH, "version_info.txt")

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
