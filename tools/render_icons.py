#!/usr/bin/env python3
"""Render market-sync icon PNGs for the .deb.

Usage: QT_QPA_PLATFORM=offscreen python3 tools/render_icons.py <hicolor-root>
Writes <hicolor-root>/<size>x<size>/apps/market-sync.png for common sizes.
"""
from __future__ import annotations
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def draw(size: int):
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtCore import Qt
    from PyQt6.QtSvg import QSvgRenderer

    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    svg_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.svg")
    QSvgRenderer(svg_path).render(p)
    p.end()
    return img


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: render_icons.py <hicolor-root>", file=sys.stderr)
        return 2

    from PyQt6.QtGui import QGuiApplication
    _app = QGuiApplication([])

    root = sys.argv[1]
    sizes = [16, 22, 24, 32, 48, 64, 128, 256]
    for size in sizes:
        out_dir = os.path.join(root, f"{size}x{size}", "apps")
        os.makedirs(out_dir, exist_ok=True)
        img = draw(size)
        path = os.path.join(out_dir, "market-sync.png")
        if not img.save(path, "PNG"):
            print(f"failed to save {path}", file=sys.stderr)
            return 1
        print(f"rendered {size}x{size} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
