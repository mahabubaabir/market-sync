#!/usr/bin/env python3
"""Render assets/icon.svg into a multi-size assets/icon.ico for Windows.

Each size is rendered natively from the SVG and stored as a PNG-compressed
ICO frame (Vista+), so Explorer/taskbar get crisp small icons instead of a
downscaled 256px frame. Build-time only (PyQt6).
"""
from __future__ import annotations
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtCore import Qt, QRectF, QBuffer, QByteArray, QIODevice
    from PyQt6.QtSvg import QSvgRenderer

    QApplication([])
    src = os.path.join(ROOT, "assets", "icon.svg")
    if not os.path.exists(src):
        print("missing", src, file=sys.stderr)
        return 1

    frames: list[tuple[int, bytes]] = []
    for size in SIZES:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        QSvgRenderer(src).render(p, QRectF(0, 0, size, size))
        p.end()
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        frames.append((size, bytes(ba)))

    # Assemble the ICO container: header + directory + PNG payloads.
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = b""
    payload = b""
    for size, png in frames:
        dim = 0 if size >= 256 else size  # 256 is encoded as 0
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                               len(png), offset)
        payload += png
        offset += len(png)

    out = os.path.join(ROOT, "assets", "icon.ico")
    with open(out, "wb") as f:
        f.write(header + entries + payload)
    print(f"wrote {out} ({os.path.getsize(out)} bytes, {count} native frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
