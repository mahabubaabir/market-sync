#!/usr/bin/env python3
"""Render session-sync icon PNGs for the .deb (pure PyQt6 — no SVG tools needed).

Usage: QT_QPA_PLATFORM=offscreen python3 tools/render_icons.py <hicolor-root>
Writes <hicolor-root>/<size>x<size>/apps/session-sync.png for common sizes.
"""
from __future__ import annotations
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def draw(size: int):
    from PyQt6.QtGui import QImage, QPainter, QColor, QPen
    from PyQt6.QtCore import Qt, QRectF

    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 64.0  # design grid is 64x64 (matches assets/icon.svg)
    p.scale(s, s)

    # rounded dark square
    p.setPen(QPen(QColor("#3d434b"), 2))
    p.setBrush(QColor("#23262b"))
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)

    # status dot (top-left, like the tray indicator)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#8ecd76"))
    p.drawEllipse(QRectF(10, 10, 12, 12))

    # clock face
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#e8eaed"), 3))
    p.drawEllipse(QRectF(14, 18, 36, 36))

    # hands
    p.setPen(QPen(QColor("#8ecd76"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(32, 36, 32, 24)
    p.setPen(QPen(QColor("#ffcb6b"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(32, 36, 41, 40)

    # hub
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#e8eaed"))
    p.drawEllipse(QRectF(29.4, 33.4, 5.2, 5.2))

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
        path = os.path.join(out_dir, "session-sync.png")
        if not img.save(path, "PNG"):
            print(f"failed to save {path}", file=sys.stderr)
            return 1
        print(f"rendered {size}x{size} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
