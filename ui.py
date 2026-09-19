"""Market Sync — glass market countdown + news for the Cinnamon tray.

Design parity with Market Sync v0.2:
  panel  -> 2-column landmark market cards -> brand bar (logo, alerts bell,
            preferences gear) -> collapsible "Up Next" drawer with
            [All] [High] [Med] [Low] multi-select chips, news rows with
            impact + currency pills, and a date bar.
  tray   -> multi-market text (open + next, bright/dim) or logo+dot icon.
"""
from __future__ import annotations
from datetime import datetime, timezone
import os
import subprocess
import threading

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QSystemTrayIcon, QMenu,
        QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
        QFrame, QCheckBox, QGridLayout, QDialog, QComboBox, QButtonGroup,
    )
    from PyQt6.QtGui import (
        QIcon, QPixmap, QPainter, QColor, QFont, QAction, QActionGroup,
        QFontMetrics, QPen, QCursor,
    )
    from PyQt6.QtCore import QTimer, Qt, QRectF, QEvent, pyqtSignal
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QWidget = object  # type: ignore
    QSystemTrayIcon = object  # type: ignore

try:
    from PyQt6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

from config import (
    MARKETS, MARKET_IDS, get_market, ALL_CURRENCIES, is_autostart_enabled,
    USER_AUTOSTART_PATH, autostart_exec_line, app_dir, IS_PACKAGED,
    LAUNCHER_PATH, APP_NAME, APP_VERSION, CACHE_DIR, UPDATE_CHECK_HOURS,
)
import markets as engine
import calendar_api
import updater
from notifier import notify, AlertTracker

ACCENT = "#0071e3"   # fallback accent (themes define their own)
GREEN = "#30d158"    # active session neon green
RED = "#ff453a"      # closed session countdown red

ASSETS_DIR = os.path.join(app_dir(), "assets")

# ------------------------------------------------------------ glass themes
# v0.2 Material-glass tokens: translucent panel + cards, brighter card and
# green border while a session is open, dimmed while closed.
THEMES = {
    "light": {
        "bg": "rgba(250, 252, 255, 0.90)",
        "solid_bg": "#f7f9fc",
        "glass_border": "rgba(255, 255, 255, 0.65)",
        "card": "rgba(255, 255, 255, 0.92)",
        "tint": "rgba(232, 241, 252, 0.90)",
        "border": "rgba(0, 0, 0, 0.08)",
        "text": "#1d1d1f", "muted": "#6e6e73",
        "accent": "#0071e3",
        "card_open": "rgba(255, 255, 255, 0.95)",
        "card_closed": "rgba(243, 246, 250, 0.80)",
        "card_border_open": "rgba(34, 197, 94, 0.60)",
        "card_border_closed": "rgba(0, 0, 0, 0.08)",
        "pill_open_bg": "rgba(34, 197, 94, 0.16)", "pill_open_text": "#16a34a",
        "pill_closed_bg": "rgba(100, 116, 139, 0.12)", "pill_closed_text": "#64748b",
        "ring_track": "rgba(0, 0, 0, 0.08)",
        "badge_bg": "rgba(241, 245, 249, 0.85)",
        "tray_text": "#1d1d1f",
    },
    "dark": {
        "bg": "rgba(16, 20, 30, 0.88)",
        "solid_bg": "#12161f",
        "glass_border": "rgba(255, 255, 255, 0.12)",
        "card": "rgba(26, 34, 52, 0.85)",
        "tint": "rgba(37, 50, 74, 0.85)",
        "border": "rgba(255, 255, 255, 0.10)",
        "text": "#e8eaed", "muted": "#9aa0a6",
        "accent": "#0a84ff",
        "card_open": "rgba(26, 34, 52, 0.90)",
        "card_closed": "rgba(20, 24, 36, 0.65)",
        "card_border_open": "rgba(48, 209, 88, 0.55)",
        "card_border_closed": "rgba(255, 255, 255, 0.08)",
        "pill_open_bg": "rgba(34, 197, 94, 0.22)", "pill_open_text": "#30d158",
        "pill_closed_bg": "rgba(148, 163, 184, 0.12)", "pill_closed_text": "#94a3b8",
        "ring_track": "rgba(255, 255, 255, 0.10)",
        "badge_bg": "rgba(34, 40, 58, 0.85)",
        "tray_text": "#ffffff",
    },
    "dark_purple": {
        "bg": "rgba(23, 18, 34, 0.88)",
        "solid_bg": "#1a1428",
        "glass_border": "rgba(255, 255, 255, 0.12)",
        "card": "rgba(36, 29, 51, 0.85)",
        "tint": "rgba(45, 36, 71, 0.85)",
        "border": "rgba(255, 255, 255, 0.10)",
        "text": "#ece7f6", "muted": "#9d94b8",
        "accent": "#a78bfa",
        "card_open": "rgba(38, 30, 56, 0.92)",
        "card_closed": "rgba(26, 20, 39, 0.65)",
        "card_border_open": "rgba(48, 209, 88, 0.55)",
        "card_border_closed": "rgba(255, 255, 255, 0.08)",
        "pill_open_bg": "rgba(34, 197, 94, 0.22)", "pill_open_text": "#30d158",
        "pill_closed_bg": "rgba(148, 163, 184, 0.12)", "pill_closed_text": "#9d94b8",
        "ring_track": "rgba(255, 255, 255, 0.10)",
        "badge_bg": "rgba(46, 36, 66, 0.85)",
        "tray_text": "#ece7f6",
    },
    "mint_light": {
        "bg": "rgba(242, 250, 245, 0.90)",
        "solid_bg": "#f2faf5",
        "glass_border": "rgba(255, 255, 255, 0.65)",
        "card": "rgba(255, 255, 255, 0.92)",
        "tint": "rgba(226, 245, 234, 0.90)",
        "border": "rgba(16, 43, 35, 0.08)",
        "text": "#1c2b23", "muted": "#5f7a6c",
        "accent": "#10b981",
        "card_open": "rgba(255, 255, 255, 0.95)",
        "card_closed": "rgba(238, 248, 242, 0.80)",
        "card_border_open": "rgba(16, 185, 129, 0.60)",
        "card_border_closed": "rgba(16, 43, 35, 0.08)",
        "pill_open_bg": "rgba(16, 185, 129, 0.16)", "pill_open_text": "#059669",
        "pill_closed_bg": "rgba(100, 116, 139, 0.12)", "pill_closed_text": "#5f7a6c",
        "ring_track": "rgba(16, 43, 35, 0.08)",
        "badge_bg": "rgba(226, 245, 234, 0.85)",
        "tray_text": "#1c2b23",
    },
    "mint_dark": {
        "bg": "rgba(18, 29, 24, 0.88)",
        "solid_bg": "#121d18",
        "glass_border": "rgba(255, 255, 255, 0.12)",
        "card": "rgba(31, 45, 38, 0.85)",
        "tint": "rgba(36, 59, 48, 0.85)",
        "border": "rgba(255, 255, 255, 0.10)",
        "text": "#e3f0e9", "muted": "#8fae9e",
        "accent": "#35c48d",
        "card_open": "rgba(33, 50, 41, 0.92)",
        "card_closed": "rgba(22, 33, 27, 0.65)",
        "card_border_open": "rgba(53, 196, 141, 0.55)",
        "card_border_closed": "rgba(255, 255, 255, 0.08)",
        "pill_open_bg": "rgba(53, 196, 141, 0.22)", "pill_open_text": "#35c48d",
        "pill_closed_bg": "rgba(148, 163, 184, 0.12)", "pill_closed_text": "#8fae9e",
        "ring_track": "rgba(255, 255, 255, 0.10)",
        "badge_bg": "rgba(36, 54, 44, 0.85)",
        "tray_text": "#e3f0e9",
    },
}

THEME_ORDER = ["system", "light", "dark", "dark_purple", "mint_light", "mint_dark"]
THEME_LABELS = {
    "system": "System", "light": "Light", "dark": "Dark",
    "dark_purple": "Dark Purple", "mint_light": "Mint Light", "mint_dark": "Mint Dark",
}
THEME_ICON = {
    "system": "🖥️", "light": "☀️", "dark": "🌙",
    "dark_purple": "🟣", "mint_light": "🌿", "mint_dark": "🍃",
}

# v0.2 news-row pill palette: High red, Medium orange, Low yellow.
PILL_STYLE = {
    "High": ("#ef4444", "rgba(239, 68, 68, 0.20)"),
    "Medium": ("#f97316", "rgba(249, 115, 22, 0.20)"),
    "Low": ("#eab308", "rgba(234, 179, 8, 0.20)"),
    "Holiday": ("#bf5af2", "rgba(191, 90, 242, 0.20)"),
}
PILL_DOT = {"High": "🔴", "Medium": "🟠", "Low": "🟡", "Holiday": "🟣"}
CHIP_BASE = {"High": "#ef4444", "Medium": "#f97316", "Low": "#eab308"}

# v0.2 per-currency pill colors.
CURRENCY_COLORS = {
    "USD": ("#f97316", "rgba(249, 115, 22, 0.16)"),
    "EUR": ("#16a34a", "rgba(22, 163, 74, 0.16)"),
    "GBP": ("#0d9488", "rgba(13, 148, 136, 0.16)"),
    "JPY": ("#e11d48", "rgba(225, 29, 72, 0.16)"),
    "AUD": ("#2563eb", "rgba(37, 99, 235, 0.16)"),
    "CAD": ("#9333ea", "rgba(147, 51, 234, 0.16)"),
    "CHF": ("#dc2626", "rgba(220, 38, 38, 0.16)"),
    "NZD": ("#0284c7", "rgba(2, 132, 199, 0.16)"),
}

# Sentinel: distinguishes "update check not finished yet" from "no update".
_UNSET = object()


def resolve_theme(want: str) -> str:
    if want in THEMES:
        return want
    # system: ask Qt when available, else dark (v0.2 default)
    if HAS_QT:
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt as _Qt
            app = QApplication.instance()
            if app is not None:
                scheme = app.styleHints().colorScheme()
                if scheme == _Qt.ColorScheme.Dark:
                    return "dark"
                if scheme == _Qt.ColorScheme.Light:
                    return "light"
        except Exception:
            pass
    return "dark"


def stylesheet(t: dict) -> str:
    return f"""
QWidget#PanelRoot {{
    background: {t['bg']};
    border: 1px solid {t['glass_border']};
    border-radius: 18px;
}}
QLabel {{ color: {t['text']}; background: transparent; }}
QLabel.muted {{ color: {t['muted']}; font-size: 11px; }}
QLabel.caption {{ color: {t['muted']}; font-size: 10px; font-weight: 700; letter-spacing: 1.0px; }}
QFrame.card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QPushButton.ghost {{ background: transparent; color: {t['muted']}; border: 1px solid {t['border']}; border-radius: 7px; padding: 4px 10px; font-size: 12px; }}
QPushButton.ghost:hover {{ color: {t['text']}; border-color: {t['accent']}; }}
QPushButton.bar {{ background: transparent; color: {t['muted']}; border: none; border-radius: 6px; padding: 2px 6px; font-size: 13px; }}
QPushButton.bar:hover {{ color: {t['text']}; background: {t['tint']}; }}
QPushButton.quitbtn {{ background: #ff453a; color: white; border: none; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 800; }}
QPushButton.quitbtn:hover {{ background: #d70015; }}
QPushButton.primary {{ background: {t['accent']}; color: white; border: none; border-radius: 7px; padding: 6px 18px; font-weight: 800; font-size: 12px; }}
QCheckBox {{ color: {t['text']}; font-size: 12px; background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QDialog {{ background: {t['solid_bg']}; }}
QPushButton[seg="1"] {{ background: transparent; color: {t['muted']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 3px 10px; font-size: 11px; font-weight: 700; }}
QPushButton[seg="1"]:checked {{ background: {t['tint']}; border-color: {t['accent']}; color: {t['text']}; }}
QComboBox {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 3px 10px; min-width: 110px; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {t['card']}; color: {t['text']}; selection-background-color: {t['accent']}; }}
"""


# ---------------------------------------------------------------- tray helpers

def tray_label_text(selected: dict, nxt, settings: dict, now_utc) -> str:
    """Single-market tray text: 'LON +02:14:33 14:32' (+ next event badge)."""
    m = selected["market"]
    is_12h = settings.get("time_format", "24h") == "12h"
    parts: list[str] = []
    if settings.get("show_symbol", True):
        parts.append(m["symbol"])
    if settings.get("show_countdown", True):
        parts.append(engine.format_signed_countdown(
            selected["countdown"], selected["is_open"], include_seconds=True).replace(" ", ""))
    if settings.get("show_local_time", True):
        parts.append(engine.format_local_clock(selected["now_local"], is_12h))
    text = " ".join(parts) or m["symbol"]
    if settings.get("show_next_event", True) and nxt and nxt.get("_dt"):
        mins = int((nxt["_dt"] - now_utc).total_seconds() // 60)
        if 0 <= mins < 60:
            text += f"  •  {nxt['currency']} {mins}m"
        elif 60 <= mins < 60 * 24:
            text += f"  •  {nxt['currency']} {mins // 60}h"
    return text


def make_tray_icon(text: str, is_open: bool, theme: str) -> "QIcon":
    t = THEMES[resolve_theme(theme)]
    font = QFont("Sans", 11, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    w = max(60, fm.horizontalAdvance(text) + 30)
    pm = QPixmap(w, 28)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font)
    p.setBrush(QColor(GREEN if is_open else "#8e8e93"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 8, 12, 12)  # status dot
    p.setPen(QColor(t["tray_text"]))
    p.drawText(20, 0, w - 20, 28, Qt.AlignmentFlag.AlignVCenter, text)
    p.end()
    return QIcon(pm)


def make_tray_icon_multi(segments: list, theme: str) -> "QIcon":
    """v0.2 applet style: '● LON +02:14  ○ NYC -05:02' (bright/dim)."""
    t = THEMES[resolve_theme(theme)]
    font = QFont("Sans", 11, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    labels = [f"{'●' if o else '○'} {txt}" for txt, o in segments]
    sep = "  "
    joined = sep.join(labels)
    w = max(60, fm.horizontalAdvance(joined) + 14)
    pm = QPixmap(w, 28)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(font)
    x = 7
    for label, (_, is_open) in zip(labels, segments):
        p.setPen(QColor(t["tray_text"] if is_open else t["muted"]))
        adv = fm.horizontalAdvance(label)
        p.drawText(x, 0, adv + 4, 28, Qt.AlignmentFlag.AlignVCenter, label)
        x += adv + fm.horizontalAdvance(sep)
    p.end()
    return QIcon(pm)


def make_tray_logo_icon(any_open: bool, size: int = 24) -> "QIcon":
    """v0.2 square icon: brand logo + green/gray status dot."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo_path = os.path.join(ASSETS_DIR, "logo.svg")
    if HAS_SVG and os.path.exists(logo_path):
        r = QSvgRenderer(logo_path)
        r.render(p, QRectF(2, 2, size - 4, size - 4))
    else:
        p.setBrush(QColor("#23262b"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, size - 4, size - 4)
    p.setBrush(QColor(GREEN if any_open else "#71717a"))
    p.setPen(QPen(QColor("#0f121a"), 1.2))
    p.drawEllipse(size - 9, size - 9, 7, 7)
    p.end()
    return QIcon(pm)


def _next_nyse_holiday_line(now_utc=None) -> str:
    """Bank-holiday parity: next NYSE full closure."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    from markets import nyse_holidays
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        ny = ZoneInfo("America/New_York")
        base = now_utc.astimezone(ny)
        for i in range(0, 370):
            cand = base + timedelta(days=i)
            if cand.weekday() < 5 and cand.date() in nyse_holidays(cand.year):
                return f"NYSE holiday: {cand.strftime('%a %b %d')} — closed"
        return "NYSE: no upcoming holiday this year"
    except Exception:
        return ""


def _svg_path(landmark: str) -> str:
    return os.path.join(ASSETS_DIR, f"{landmark}.svg")


def landmark_menu_icon(market: dict, size: int = 16) -> "QIcon":
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    path = _svg_path(market.get("landmark", "london"))
    if HAS_SVG and os.path.exists(path):
        r = QSvgRenderer(path)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r.render(p)
        p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- widgets

if HAS_QT:
    class LandmarkBadge(QWidget):
        """Circular glass badge with the market's landmark SVG (v0.2 style)."""

        def __init__(self, landmark: str, symbol: str, size: int = 26):
            super().__init__()
            self._landmark = landmark
            self._symbol = symbol
            self._size = size
            self.setFixedSize(size, size)
            self._bg = QColor("rgba(241, 245, 249, 0.85)")

        def set_landmark(self, landmark: str, symbol: str):
            if landmark != self._landmark or symbol != self._symbol:
                self._landmark, self._symbol = landmark, symbol
                self.update()

        def set_theme(self, t: dict):
            self._bg = QColor(t["badge_bg"])
            self.update()

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._bg)
            p.drawEllipse(1, 1, self._size - 2, self._size - 2)
            path = _svg_path(self._landmark)
            if HAS_SVG and os.path.exists(path):
                r = QSvgRenderer(path)
                inset = max(4, self._size // 6)
                r.render(p, QRectF(inset, inset, self._size - 2 * inset, self._size - 2 * inset))
            else:
                p.setPen(QColor("#ffffff"))
                f = QFont("Sans", max(7, self._size // 3), QFont.Weight.Bold)
                p.setFont(f)
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._symbol[:3])
            p.end()
else:
    class LandmarkBadge:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class MiniRingTimer(QWidget):
        """Small progress ring beside the OPEN/CLOSED pill on market cards."""

        def __init__(self, size: int = 18):
            super().__init__()
            self.setFixedSize(size, size)
            self._frac = 0.0
            self._open = False
            self._track = QColor("rgba(255, 255, 255, 0.1)")

        def set_state(self, frac: float, is_open: bool, t: dict):
            self._frac = min(1.0, max(0.0, frac))
            self._open = is_open
            self._track = QColor(t["ring_track"])
            self.update()

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = 2.5
            rect = QRectF(w, w, self.width() - 2 * w, self.height() - 2 * w)
            p.setPen(QPen(self._track, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 0, 360 * 16)
            p.setPen(QPen(QColor(GREEN if self._open else RED), w,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            span = int(-self._frac * 360 * 16)
            if abs(span) > 16:
                p.drawArc(rect, 90 * 16, span)
            p.end()
else:
    class MiniRingTimer:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class MarketCardWidget(QFrame):
        """v0.2 Material glass card (88px): landmark + name + local clock on
        top; signed countdown + OPEN/CLOSED pill + mini ring below. Bright
        while open, dimmed while closed (unless brighten is disabled)."""

        clicked = pyqtSignal(str)

        def __init__(self, market: dict, parent: QWidget | None = None):
            super().__init__(parent)
            self.market = market
            self.setObjectName("MarketCard")
            self.setFixedHeight(88)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(4)

            top = QHBoxLayout()
            top.setSpacing(6)
            self.badge = LandmarkBadge(market.get("landmark", "london"), market["symbol"], 26)
            top.addWidget(self.badge)
            self.name_label = QLabel(market["name"])
            nf = QFont("Sans", 11)
            nf.setWeight(QFont.Weight.DemiBold)
            self.name_label.setFont(nf)
            top.addWidget(self.name_label)
            top.addStretch(1)
            self.time_label = QLabel("00:00")
            tf = QFont("Sans", 11)
            tf.setWeight(QFont.Weight.Medium)
            self.time_label.setFont(tf)
            top.addWidget(self.time_label)
            lay.addLayout(top)

            bot = QHBoxLayout()
            bot.setSpacing(5)
            self.cd_label = QLabel("+ 00:00")
            cf = QFont("Sans", 15)
            cf.setWeight(QFont.Weight.Bold)
            self.cd_label.setFont(cf)
            bot.addWidget(self.cd_label)
            bot.addStretch(1)
            self.pill = QLabel("OPEN")
            self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pill.setFixedSize(54, 18)
            pf = QFont("Sans", 8)
            pf.setWeight(QFont.Weight.Bold)
            self.pill.setFont(pf)
            bot.addWidget(self.pill)
            self.ring = MiniRingTimer(18)
            bot.addWidget(self.ring)
            lay.addLayout(bot)

        def mousePressEvent(self, ev):
            if ev.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self.market["id"])
            super().mousePressEvent(ev)

        def update_data(self, status: dict, t: dict, selected: bool,
                        is_12h: bool, brighten: bool):
            is_open = bool(status["is_open"])
            self.badge.set_theme(t)
            self.time_label.setText(engine.format_local_clock(status["now_local"], is_12h))
            self.cd_label.setText(engine.format_signed_countdown(status["countdown"], is_open))

            bright = is_open and brighten
            if bright:
                self.time_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px;")
                self.name_label.setStyleSheet("font-weight: 800; font-size: 12px;")
                self.cd_label.setStyleSheet(
                    f"font-family: monospace; font-size: 15px; font-weight: 800; color: {GREEN};")
                bg, bd = t["card_open"], t["card_border_open"]
            elif brighten:
                self.time_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px;")
                self.name_label.setStyleSheet(f"font-weight: 800; font-size: 12px; color: {t['muted']};")
                self.cd_label.setStyleSheet(
                    f"font-family: monospace; font-size: 15px; font-weight: 800; color: {t['muted']};")
                bg, bd = t["card_closed"], t["card_border_closed"]
            else:
                # brighten disabled: uniform cards, state only via the pill
                self.time_label.setStyleSheet(f"color: {t['muted']}; font-size: 11px;")
                self.name_label.setStyleSheet("font-weight: 800; font-size: 12px;")
                self.cd_label.setStyleSheet(
                    f"font-family: monospace; font-size: 15px; font-weight: 800; color: {t['text']};")
                bg, bd = t["card"], t["card_border_closed"]

            if is_open:
                self.pill.setText("OPEN")
                self.pill.setStyleSheet(
                    f"background: {t['pill_open_bg']}; color: {t['pill_open_text']};"
                    "border-radius: 5px; font-weight: bold;")
            else:
                self.pill.setText("CLOSED")
                self.pill.setStyleSheet(
                    f"background: {t['pill_closed_bg']}; color: {t['pill_closed_text']};"
                    "border-radius: 5px; font-weight: bold;")
            bcol = t["accent"] if selected else bd
            bw = "1.5px" if (selected or is_open) else "1px"
            self.setStyleSheet(
                f"QFrame#MarketCard {{ background: {bg}; border: {bw} solid {bcol}; border-radius: 12px; }}")
            self.ring.set_state(status.get("progress", 0.0), is_open, t)
else:
    class MarketCardWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class NewsRowWidget(QFrame):
        """v0.2 news row: relative time • impact pill • currency pill • title."""

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(8, 3, 8, 3)
            lay.setSpacing(8)

            self.rel_label = QLabel("--")
            rf = QFont("Sans", 11)
            rf.setWeight(QFont.Weight.Bold)
            self.rel_label.setFont(rf)
            self.rel_label.setFixedWidth(52)
            self.rel_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(self.rel_label)

            self.imp_pill = QLabel("LOW")
            ipf = QFont("Sans", 8)
            ipf.setWeight(QFont.Weight.Bold)
            self.imp_pill.setFont(ipf)
            self.imp_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.imp_pill.setFixedSize(36, 17)
            lay.addWidget(self.imp_pill)

            self.cur_pill = QLabel("USD")
            cpf = QFont("Sans", 9)
            cpf.setWeight(QFont.Weight.Bold)
            self.cur_pill.setFont(cpf)
            self.cur_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cur_pill.setFixedSize(36, 17)
            lay.addWidget(self.cur_pill)

            self.title_label = QLabel("")
            ttf = QFont("Sans", 11)
            self.title_label.setFont(ttf)
            lay.addWidget(self.title_label, 1)

        def update_data(self, ev: dict, theme: dict, now_utc):
            dt = ev.get("_dt")
            self.rel_label.setText(calendar_api.relative_time(dt, now_utc) if dt else "--")
            self.rel_label.setStyleSheet(f"color: {theme['text']};")

            imp = ev.get("impact", "Low")
            fg, bg = PILL_STYLE.get(imp, PILL_STYLE["Low"])
            self.imp_pill.setText(imp[:3].upper())
            self.imp_pill.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 1px solid {fg};"
                "border-radius: 4px; font-weight: bold;")

            cur = (ev.get("currency") or ev.get("country") or "").upper()
            self.cur_pill.setText(cur[:3])
            c_fg, c_bg = CURRENCY_COLORS.get(cur, (ACCENT, "rgba(56, 189, 248, 0.16)"))
            self.cur_pill.setStyleSheet(
                f"background: {c_bg}; color: {c_fg}; border-radius: 4px; font-weight: bold;")

            self.title_label.setText(ev.get("title", "Event"))
            self.title_label.setStyleSheet(f"color: {theme['text']};")
else:
    class NewsRowWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class UpNextDrawer(QFrame):
        """Collapsible v0.2 news drawer: trigger bar • chips • rows • date bar."""

        def __init__(self, controller: "TrayController"):
            super().__init__()
            self.c = controller
            self._sig: list | None = None
            self._rows: list = []

            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

            # collapsed trigger bar
            self.trigger = QFrame()
            self.trigger.setFixedHeight(34)
            self.trigger.setCursor(Qt.CursorShape.PointingHandCursor)
            tl = QHBoxLayout(self.trigger)
            tl.setContentsMargins(12, 0, 12, 0)
            tl.setSpacing(8)
            self.trigger_label = QLabel("Upcoming Events…")
            self.trigger_label.setStyleSheet("font-size: 11px;")
            tl.addWidget(self.trigger_label, 1)
            self.trigger_chevron = QLabel("⌃")
            self.trigger_chevron.setStyleSheet("font-size: 13px;")
            tl.addWidget(self.trigger_chevron)
            self.trigger.mousePressEvent = lambda e: self.toggle()
            lay.addWidget(self.trigger)

            # expanded area
            self.expanded = QWidget()
            el = QVBoxLayout(self.expanded)
            el.setContentsMargins(0, 0, 0, 0)
            el.setSpacing(0)

            header = QFrame()
            header.setFixedHeight(30)
            hl = QHBoxLayout(header)
            hl.setContentsMargins(12, 2, 12, 2)
            hl.setSpacing(5)
            cap = QLabel("UP NEXT")
            cap.setProperty("class", "caption")
            hl.addWidget(cap)
            hl.addStretch(1)
            self.chips: dict[str, QPushButton] = {}
            self.chip_all = QPushButton("All")
            self.chip_all.setCheckable(True)
            self.chip_all.setCursor(Qt.CursorShape.PointingHandCursor)
            self.chip_all.clicked.connect(self._on_all)
            hl.addWidget(self.chip_all)
            for lvl, label in (("High", "🔴 High"), ("Medium", "🟠 Med"), ("Low", "🟡 Low")):
                b = QPushButton(label)
                b.setCheckable(True)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(self._on_chip)
                hl.addWidget(b)
                self.chips[lvl] = b
            el.addWidget(header)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(150)
            inner = QWidget()
            self.rows_layout = QVBoxLayout(inner)
            self.rows_layout.setSpacing(2)
            self.rows_layout.setContentsMargins(8, 2, 8, 4)
            self.rows_layout.addStretch(1)
            scroll.setWidget(inner)
            el.addWidget(scroll)

            datebar = QFrame()
            datebar.setFixedHeight(26)
            dl = QHBoxLayout(datebar)
            dl.setContentsMargins(14, 0, 10, 0)
            self.date_label = QLabel(datetime.now().strftime("%d %b"))
            self.date_label.setStyleSheet("font-size: 10px;")
            dl.addWidget(self.date_label)
            dl.addStretch(1)
            self.collapse_btn = QPushButton("⌄")
            self.collapse_btn.setProperty("class", "bar")
            self.collapse_btn.setFixedSize(24, 20)
            self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.collapse_btn.clicked.connect(self.toggle)
            dl.addWidget(self.collapse_btn)
            el.addWidget(datebar)

            lay.addWidget(self.expanded)
            self.set_expanded(bool(controller.settings.get("news_drawer_expanded", True)))

        # -- chips (v0.2 multi-select)
        def _on_all(self):
            state = self.chip_all.isChecked()
            for b in self.chips.values():
                b.setChecked(state)
            self._emit()

        def _on_chip(self):
            self.chip_all.setChecked(all(b.isChecked() for b in self.chips.values()))
            self._emit()

        def _emit(self):
            active = [lvl for lvl, b in self.chips.items() if b.isChecked()]
            self.c.set_active_impacts(active)

        def sync_chips(self, active: list):
            for lvl, b in self.chips.items():
                b.blockSignals(True)
                b.setChecked(lvl in active)
                b.blockSignals(False)
            self.chip_all.blockSignals(True)
            self.chip_all.setChecked(len(active) == 3)
            self.chip_all.blockSignals(False)

        # -- expand/collapse
        def toggle(self):
            self.set_expanded(not self.expanded.isVisible())

        def set_expanded(self, expanded: bool):
            self.expanded.setVisible(expanded)
            self.trigger.setVisible(not expanded)
            self.c.settings["news_drawer_expanded"] = expanded
            self.c._save()

        # -- content
        def update_events(self, shown: list, nxt, now_utc):
            t = THEMES[self.c.panel._theme]
            self.date_label.setText(
                datetime.now().strftime("%d %b") + "  •  💻 " +
                engine.format_local_clock(now_utc.astimezone(),
                                          self.c.settings.get("time_format") == "12h"))
            self.date_label.setStyleSheet(f"color: {t['muted']}; font-size: 10px;")
            self.trigger_label.setStyleSheet(f"color: {t['text']}; font-size: 11px;")
            self.trigger_chevron.setStyleSheet(f"color: {t['muted']}; font-size: 13px;")
            if nxt and nxt.get("_dt"):
                rel = calendar_api.relative_time(nxt["_dt"], now_utc)
                dot = PILL_DOT.get(nxt.get("impact", "Low"), "🟡")
                self.trigger_label.setText(
                    f"{rel} To next event ({dot} {nxt.get('currency', '')} "
                    f"{nxt.get('title', '')[:22]})")
            else:
                self.trigger_label.setText("Upcoming Events…")

            sig = [(e.get("currency"), e.get("title"), e.get("date_utc"), e.get("impact"))
                   for e in shown]
            if sig != self._sig:
                self._sig = sig
                while self.rows_layout.count() > 1:
                    item = self.rows_layout.takeAt(0)
                    w = item.widget()
                    if w:
                        w.deleteLater()
                self._rows = []
                if not shown:
                    lab = QLabel("No upcoming economic events")
                    lab.setProperty("class", "muted")
                    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.rows_layout.insertWidget(0, lab)
                    self._rows = [lab]
                for e in shown:
                    row = NewsRowWidget()
                    row.update_data(e, t, now_utc)
                    self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
                    self._rows.append(row)
            else:
                for row, e in zip(self._rows, shown):
                    if hasattr(row, "update_data"):
                        row.update_data(e, t, now_utc)
else:
    class UpNextDrawer:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


class SessionPanel(QWidget):
    """Market Sync v0.2 glass popover: market grid -> brand bar -> Up Next."""

    def __init__(self, controller: "TrayController"):
        super().__init__()
        self.c = controller
        self._theme = "dark"
        self.setObjectName("PanelRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(410)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(7)

        # ---- 1. market cards grid (v0.2 order & look)
        self.cards: dict[str, MarketCardWidget] = {}
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(7)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        for m in MARKETS:
            card = MarketCardWidget(m)
            card.clicked.connect(self.c.select_market)
            self.cards[m["id"]] = card
        root.addLayout(self.grid)
        self.rebuild_grid()

        # ---- 2. brand bar: logo + title + theme/alerts/preferences/close
        brand = QHBoxLayout()
        brand.setSpacing(4)
        self.logo = QLabel()
        self.logo.setFixedSize(20, 20)
        logo_pm = QPixmap(20, 20)
        logo_pm.fill(Qt.GlobalColor.transparent)
        logo_path = os.path.join(ASSETS_DIR, "logo.svg")
        if HAS_SVG and os.path.exists(logo_path):
            r = QSvgRenderer(logo_path)
            p = QPainter(logo_pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r.render(p)
            p.end()
        self.logo.setPixmap(logo_pm)
        brand.addWidget(self.logo)
        self.title = QLabel("MARKET SYNC")
        tf = QFont("Sans", 9, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        self.title.setFont(tf)
        self.title.setStyleSheet("font-weight: 800;")
        brand.addWidget(self.title)
        brand.addStretch(1)
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setProperty("class", "bar")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Theme (click to cycle)")
        self.theme_btn.clicked.connect(self.c.cycle_theme)
        brand.addWidget(self.theme_btn)
        self.bell_btn = QPushButton("🔔")
        self.bell_btn.setProperty("class", "bar")
        self.bell_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bell_btn.setToolTip("Notifications on / off")
        self.bell_btn.clicked.connect(self.c.toggle_alerts)
        brand.addWidget(self.bell_btn)
        self.gear_btn = QPushButton("⚙️")
        self.gear_btn.setProperty("class", "bar")
        self.gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.gear_btn.setToolTip("Preferences")
        self.gear_btn.clicked.connect(self.c.open_preferences)
        brand.addWidget(self.gear_btn)
        self.close_btn = QPushButton("✕")
        self.close_btn.setProperty("class", "bar")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Hide panel (app keeps running in tray)")
        self.close_btn.clicked.connect(self.hide)
        brand.addWidget(self.close_btn)
        root.addLayout(brand)

        # ---- 3. Up Next drawer
        self.drawer = UpNextDrawer(controller)
        root.addWidget(self.drawer)

        self.apply_theme()

    def rebuild_grid(self):
        """v0.2 market routing: 'none' hides the card, others show it."""
        md = self.c.settings.get("market_display", {})
        enabled = [m for m in MARKETS if md.get(m["id"], "panel") != "none"]
        while self.grid.count():
            self.grid.takeAt(0)
        for m in MARKETS:
            self.cards[m["id"]].hide()
        for idx, m in enumerate(enabled):
            card = self.cards[m["id"]]
            card.show()
            r, col = divmod(idx, 2)
            if idx == len(enabled) - 1 and len(enabled) % 2 == 1:
                self.grid.addWidget(card, r, 0, 1, 2)  # last card spans full width
            else:
                self.grid.addWidget(card, r, col)

    # Panel must NOT stick over other apps: hide when it loses focus
    def changeEvent(self, ev):
        try:
            if ev.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
                if self.isVisible() and self.c.settings.get("auto_hide_panel", True):
                    self.hide()
        except Exception:
            pass
        super().changeEvent(ev)

    def focusOutEvent(self, ev):
        try:
            if self.isVisible() and self.c.settings.get("auto_hide_panel", True):
                self.hide()
        except Exception:
            pass
        super().focusOutEvent(ev)

    def apply_theme(self):
        self._theme = resolve_theme(self.c.settings.get("theme", "system"))
        t = THEMES[self._theme]
        self.setStyleSheet(stylesheet(t))
        try:
            self.c.menu.setStyleSheet(stylesheet(t))
        except Exception:
            pass
        want = self.c.settings.get("theme", "system")
        self.theme_btn.setText(THEME_ICON.get(want, "🖥️"))
        self.theme_btn.setToolTip(f"Theme: {THEME_LABELS.get(want, want)} (click to cycle)")
        # v0.2 chips: semantic colors, tinted when checked
        for lvl, b in self.drawer.chips.items():
            base = CHIP_BASE[lvl]
            c = QColor(base)
            tint = f"rgba({c.red()}, {c.green()}, {c.blue()}, 51)"
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {t['muted']}; "
                f"border: 1px solid {t['border']}; border-radius: 10px; "
                f"padding: 2px 7px; font-size: 10px; font-weight: 700; }}"
                f"QPushButton:checked {{ color: {base}; border-color: {base}; background: {tint}; }}")
        c = QColor(t["accent"])
        tint = f"rgba({c.red()}, {c.green()}, {c.blue()}, 51)"
        self.drawer.chip_all.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {t['muted']}; "
            f"border: 1px solid {t['border']}; border-radius: 10px; "
            f"padding: 2px 10px; font-size: 10px; font-weight: 700; }}"
            f"QPushButton:checked {{ color: {t['accent']}; border-color: {t['accent']}; background: {tint}; }}")

    def render(self, statuses, selected, news, news_note, now_utc):
        if resolve_theme(self.c.settings.get("theme", "system")) != self._theme:
            self.apply_theme()
        t = THEMES[self._theme]
        sel_id = self.c.settings["selected_market"]
        is_12h = self.c.settings.get("time_format", "24h") == "12h"
        brighten = bool(self.c.settings.get("active_brighten", True))

        # market cards
        for s in statuses:
            mid = s["market"]["id"]
            if mid in self.cards:
                self.cards[mid].update_data(s, t, mid == sel_id, is_12h, brighten)

        # alerts bell state
        self.bell_btn.setText("🔔" if self.c.settings.get("alerts_enabled", True) else "🔕")

        # drawer: chips + events
        active = list(self.c.settings.get("active_impacts", ["High", "Medium", "Low"]))
        self.drawer.sync_chips(active)
        shown = calendar_api.filter_events(
            news, self.c.settings["currencies"], None, 72, now_utc,
            active_impacts=active)
        nxt = calendar_api.next_event(
            news, self.c.settings["currencies"], None, now_utc,
            active_impacts=active)
        self.drawer.update_events(shown[:16], nxt, now_utc)


if HAS_QT:
    class PreferencesDialog(QDialog):
        """v0.2-style preferences: segmented display controls, live tray
        preview, per-market routing (none / popup / tray), news, startup,
        updates and a Quit button."""

        def __init__(self, controller: "TrayController"):
            super().__init__()
            self.c = controller
            s = controller.settings
            self._check_result = _UNSET
            self._t = THEMES[resolve_theme(s.get("theme", "system"))]
            self.setWindowTitle(f"{APP_NAME} — Preferences")
            self.setFixedSize(460, 620)
            self.setStyleSheet(stylesheet(self._t))

            root = QVBoxLayout(self)
            root.setContentsMargins(14, 12, 14, 12)
            root.setSpacing(8)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            form = QVBoxLayout(content)
            form.setSpacing(6)
            scroll.setWidget(content)
            root.addWidget(scroll, 1)

            def section(text):
                lab = QLabel(text.upper())
                lab.setProperty("class", "caption")
                form.addSpacing(6)
                form.addWidget(lab)

            def row(label, widget):
                h = QHBoxLayout()
                lab = QLabel(label)
                lab.setFixedWidth(110)
                h.addWidget(lab)
                h.addWidget(widget)
                h.addStretch(1)
                form.addLayout(h)

            # ---- live tray preview
            self.preview = QLabel("")
            self.preview.setWordWrap(True)
            self.preview.setStyleSheet(
                f"background: {self._t['tint']}; border: 1px solid {self._t['border']};"
                "border-radius: 10px; padding: 8px 10px; font-size: 12px;")
            form.addWidget(self.preview)

            # ---- Menu & Tray Display (v0.2 segmented controls)
            section("Menu & Tray Display")
            self.seg_layout = self._seg(
                [("compact", "Compact Symbols"), ("standard", "Standard Names")],
                s.get("tray_layout", "compact"))
            row("Layout", self.seg_layout)
            self.seg_timeas = self._seg(
                [("local_time", "Local Time"), ("countdown", "Countdown")],
                s.get("tray_time_as", "countdown"))
            row("Show time as", self.seg_timeas)
            self.seg_format = self._seg(
                [("12h", "12h"), ("24h", "24h")], s.get("time_format", "24h"))
            row("Format", self.seg_format)
            self.seg_sessions = self._seg(
                [("active_only", "Active Only"), ("active_and_next", "Active + Next"),
                 ("all", "All")], s.get("tray_sessions", "active_and_next"))
            row("Tray sessions", self.seg_sessions)
            self.seg_icon = self._seg(
                [("text", "Text"), ("logo", "Logo + dot")],
                s.get("tray_icon_style", "text"))
            row("Tray icon", self.seg_icon)
            self.brighten_chk = QCheckBox("Active markets brighten; off sessions are dimmed")
            self.brighten_chk.setChecked(bool(s.get("active_brighten", True)))
            self.brighten_chk.toggled.connect(self._refresh_preview)
            form.addWidget(self.brighten_chk)

            # ---- Market List (v0.2 routing: none / popup / tray)
            section("Market List")
            self.route_segs: dict = {}
            md = s.get("market_display", {})
            for m in MARKETS:
                h = QHBoxLayout()
                lab = QLabel(f"{m['name']} ({m['symbol']})")
                lab.setFixedWidth(150)
                h.addWidget(lab)
                seg = self._seg(
                    [("none", "None"), ("popup", "Popup"), ("panel", "+ Tray")],
                    md.get(m["id"], "panel"), preview=False)
                h.addWidget(seg)
                h.addStretch(1)
                form.addLayout(h)
                self.route_segs[m["id"]] = seg

            # ---- News
            section("News")
            active = set(s.get("active_impacts", ["High", "Medium", "Low"]))
            improw = QHBoxLayout()
            self.imp_chks: dict = {}
            for lvl, label in (("High", "🔴 High"), ("Medium", "🟠 Med"), ("Low", "🟡 Low")):
                chk = QCheckBox(label)
                chk.setChecked(lvl in active)
                self.imp_chks[lvl] = chk
                improw.addWidget(chk)
            improw.addStretch(1)
            form.addLayout(improw)
            currow = QHBoxLayout()
            self.cur_chks: dict = {}
            cur_active = set(s.get("currencies", ALL_CURRENCIES))
            for cur in ALL_CURRENCIES:
                chk = QCheckBox(cur)
                chk.setChecked(cur in cur_active)
                self.cur_chks[cur] = chk
                currow.addWidget(chk)
            currow.addStretch(1)
            form.addLayout(currow)
            self.refresh_cb = QComboBox()
            for minutes in (5, 10, 15, 30, 60):
                self.refresh_cb.addItem(f"{minutes} minutes", minutes)
            cur_min = int(s.get("news_refresh_minutes", 15))
            idx = [i for i, mm in enumerate((5, 10, 15, 30, 60)) if mm == cur_min]
            self.refresh_cb.setCurrentIndex(idx[0] if idx else 2)
            row("Refresh news", self.refresh_cb)
            self.alerts_chk = QCheckBox("Desktop notifications (market + high-impact news)")
            self.alerts_chk.setChecked(bool(s.get("alerts_enabled", True)))
            form.addWidget(self.alerts_chk)

            # ---- Window & Startup
            section("Window & Startup")
            self.theme_cb = QComboBox()
            for key in THEME_ORDER:
                self.theme_cb.addItem(f"{THEME_ICON[key]}  {THEME_LABELS[key]}", key)
            self.theme_cb.setCurrentIndex(THEME_ORDER.index(s.get("theme", "system")))
            row("Theme", self.theme_cb)
            self.sel_cb = QComboBox()
            for m in MARKETS:
                self.sel_cb.addItem(f"{m['flag']}  {m['name']}", m["id"])
            self.sel_cb.setCurrentIndex(MARKET_IDS.index(s.get("selected_market", "LONDON")))
            row("Default market", self.sel_cb)
            self.drawer_chk = QCheckBox("Open news drawer by default")
            self.drawer_chk.setChecked(bool(s.get("news_drawer_expanded", True)))
            form.addWidget(self.drawer_chk)
            self.autohide_chk = QCheckBox("Hide panel when clicking another app")
            self.autohide_chk.setChecked(bool(s.get("auto_hide_panel", True)))
            form.addWidget(self.autohide_chk)
            self.leftclick_cb = QComboBox()
            self.leftclick_cb.addItem("Open panel", "panel")
            self.leftclick_cb.addItem("Open menu", "menu")
            self.leftclick_cb.setCurrentIndex(
                0 if s.get("left_click_action", "panel") == "panel" else 1)
            row("Left-click icon", self.leftclick_cb)
            self.autostart_chk = QCheckBox("Start on login (silent, in tray)")
            self.autostart_chk.setChecked(is_autostart_enabled())
            form.addWidget(self.autostart_chk)
            self.hidden_chk = QCheckBox("Start hidden in tray when launched manually")
            self.hidden_chk.setChecked(bool(s.get("start_hidden", False)))
            form.addWidget(self.hidden_chk)

            # ---- Updates
            section("Updates")
            up_row = QHBoxLayout()
            self.update_status = QLabel(f"Current version: v{APP_VERSION}")
            up_row.addWidget(self.update_status, 1)
            self.check_btn = QPushButton("Check now")
            self.check_btn.setProperty("class", "ghost")
            self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.check_btn.clicked.connect(self._check_now)
            up_row.addWidget(self.check_btn)
            self.install_btn = QPushButton("Install update")
            self.install_btn.setProperty("class", "primary")
            self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.install_btn.clicked.connect(self._install_now)
            self.install_btn.setVisible(False)
            up_row.addWidget(self.install_btn)
            form.addLayout(up_row)

            foot = QLabel(f"Market Sync v{APP_VERSION}  •  Developed by Mahabub H. Aabir")
            foot.setProperty("class", "muted")
            foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            form.addSpacing(4)
            form.addWidget(foot)
            form.addStretch(1)

            # ---- bottom buttons
            bottom = QHBoxLayout()
            quit_btn = QPushButton("Quit app")
            quit_btn.setProperty("class", "quitbtn")
            quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            quit_btn.clicked.connect(self.c.quit_app)
            bottom.addWidget(quit_btn)
            bottom.addStretch(1)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setProperty("class", "ghost")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.clicked.connect(self.reject)
            bottom.addWidget(cancel_btn)
            save_btn = QPushButton("Save")
            save_btn.setProperty("class", "primary")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.clicked.connect(self._save)
            bottom.addWidget(save_btn)
            root.addLayout(bottom)

            self._poll = QTimer(self)
            self._poll.timeout.connect(self._poll_check)
            self._refresh_preview()

        # -- segmented control helper (v0.2 pills)
        def _seg(self, options, current, preview: bool = True):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            grp = QButtonGroup(w)
            grp.setExclusive(True)
            buttons = []
            for val, label in options:
                b = QPushButton(label)
                b.setCheckable(True)
                b.setProperty("seg", "1")
                b.setProperty("segValue", val)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setChecked(val == current)
                if preview:
                    b.clicked.connect(self._refresh_preview)
                grp.addButton(b)
                h.addWidget(b)
                buttons.append(b)
            w._buttons = buttons  # type: ignore[attr-defined]
            return w

        def _seg_value(self, w, fallback: str = "panel"):
            for b in w._buttons:  # type: ignore[attr-defined]
                if b.isChecked():
                    return b.property("segValue")
            return fallback

        def _refresh_preview(self):
            t = self._t
            layout_mode = self._seg_value(self.seg_layout, "compact")
            time_as = self._seg_value(self.seg_timeas, "countdown")
            fmt12 = self._seg_value(self.seg_format, "24h") == "12h"
            sessions = self._seg_value(self.seg_sessions, "active_and_next")
            icon = self._seg_value(self.seg_icon, "text")
            if icon == "logo":
                self.preview.setText(
                    f'<span style="color:{t["muted"]}">Logo icon + green/gray status dot in the tray</span>')
                return
            sample = [
                ("LON", "London", "+02:14", "14:32", True),
                ("NYC", "New York", "-05:02", "09:02", False),
                ("SYD", "Sydney", "-12:40", "23:40", False),
            ]
            if sessions == "active_only":
                shown = sample[:1]
            elif sessions == "active_and_next":
                shown = sample[:2]
            else:
                shown = sample
            parts = []
            for sym, full, cd, clock, is_open in shown:
                name = sym if layout_mode == "compact" else full
                val = clock if time_as == "local_time" else cd
                col = GREEN if is_open else t["muted"]
                dot = "●" if is_open else "○"
                parts.append(f'<span style="color:{col};">{dot} {name} {val}</span>')
            self.preview.setText(
                "&nbsp;&nbsp;".join(parts)
                + f'<br><span style="color:{t["muted"]}; font-size:10px;">'
                + ("12-hour clock &nbsp;•&nbsp; " if fmt12 else "")
                + "open markets bright, closed dimmed</span>")

        # -- updates
        def _check_now(self):
            self.update_status.setText("Checking…")
            self._check_result = _UNSET
            self.check_btn.setEnabled(False)

            def work():
                try:
                    self._check_result = updater.check_for_update(force=True)
                except Exception:
                    self._check_result = None

            threading.Thread(target=work, daemon=True).start()
            self._poll.start(400)

        def _poll_check(self):
            if self._check_result is _UNSET:
                return
            self._poll.stop()
            self.check_btn.setEnabled(True)
            res = self._check_result
            if res and res.get("version"):
                self.update_status.setText(f"Update available: v{res['version']}")
                self.install_btn.setVisible(True)
            else:
                self.update_status.setText(f"Up to date (v{APP_VERSION})")

        def _install_now(self):
            self.c._update_info = self._check_result if self._check_result is not _UNSET else None
            self.c._do_update()

        # -- save
        def _save(self):
            s = self.c.settings
            s["tray_layout"] = self._seg_value(self.seg_layout, "compact")
            s["tray_time_as"] = self._seg_value(self.seg_timeas, "countdown")
            s["time_format"] = self._seg_value(self.seg_format, "24h")
            s["tray_sessions"] = self._seg_value(self.seg_sessions, "active_and_next")
            s["tray_icon_style"] = self._seg_value(self.seg_icon, "text")
            s["active_brighten"] = self.brighten_chk.isChecked()
            s["market_display"] = {
                mid: self._seg_value(seg, "panel") for mid, seg in self.route_segs.items()}
            s["theme"] = self.theme_cb.currentData()
            s["alerts_enabled"] = self.alerts_chk.isChecked()
            s["start_hidden"] = self.hidden_chk.isChecked()
            s["selected_market"] = self.sel_cb.currentData()
            s["news_refresh_minutes"] = self.refresh_cb.currentData()
            s["news_drawer_expanded"] = self.drawer_chk.isChecked()
            s["auto_hide_panel"] = self.autohide_chk.isChecked()
            s["left_click_action"] = self.leftclick_cb.currentData()
            impacts = [lvl for lvl, chk in self.imp_chks.items() if chk.isChecked()]
            s["active_impacts"] = impacts or ["High", "Medium", "Low"]
            curs = [cur for cur, chk in self.cur_chks.items() if chk.isChecked()]
            s["currencies"] = curs or list(ALL_CURRENCIES)
            if self.autostart_chk.isChecked() != is_autostart_enabled():
                self.c.set_autostart_enabled(self.autostart_chk.isChecked())
            self.c._save()
            self.c._build_menu()
            self.c.panel.apply_theme()
            self.c.panel.rebuild_grid()
            self.c.panel.drawer.set_expanded(bool(s["news_drawer_expanded"]))
            self.c.tick()
            self.accept()
else:
    class PreferencesDialog:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


class TrayController:
    def __init__(self, app: "QApplication", settings: dict):
        self.app = app
        self.settings = settings
        self.tracker = AlertTracker()
        self._alerted_key: str | None = None
        self.events: list[dict] = []
        self.news_note = "news: …"
        self._news_lock = threading.Lock()
        self._last_tray_key = None
        self.statuses = engine.get_all_statuses()
        self.selected = engine.market_status(get_market(settings["selected_market"]))

        # --- auto-update state (must exist before _build_menu reads it)
        self._update_result = _UNSET
        self._update_info: dict | None = None
        self._update_notified_tag: str | None = None
        self._update_status: tuple | None = None
        self._update_busy = False
        self._prefs: PreferencesDialog | None = None

        self.tray = QSystemTrayIcon()
        self.tray.setVisible(True)
        self.tray.activated.connect(self._on_activated)
        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)

        self.panel = SessionPanel(self)
        try:
            th = resolve_theme(self.settings.get("theme", "system"))
            self.menu.setStyleSheet(stylesheet(THEMES[th]))
        except Exception:
            pass
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

        self.news_timer = QTimer()
        self.news_timer.timeout.connect(lambda: self.refresh_news(force=False))
        self.news_timer.start(max(5, settings.get("news_refresh_minutes", 15)) * 60 * 1000)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(lambda: self._check_updates(force=True))
        self.update_timer.start(max(1, UPDATE_CHECK_HOURS) * 3600 * 1000)
        QTimer.singleShot(12000, lambda: self._check_updates(force=False))

        self.refresh_news(force=True)
        self.tick()

    # -- right-click menu
    def _build_menu(self):
        self.menu.clear()

        ui = self._update_info
        if ui:
            up = QAction(f"⬆️  Update to v{ui.get('version', '?')}", self.menu)
            up.triggered.connect(self._do_update)
            self.menu.addAction(up)
            if ui.get("html_url"):
                vl = QAction("📄  Release notes", self.menu)
                vl.triggered.connect(
                    lambda _=False, u=ui.get("html_url", ""): updater.open_in_browser(u))
                self.menu.addAction(vl)
            self.menu.addSeparator()

        grp = QActionGroup(self.menu)
        grp.setExclusive(True)
        for m in MARKETS:
            a = QAction(f"  {m['name']}", self.menu, checkable=True)
            a.setIcon(landmark_menu_icon(m))
            a.setChecked(m["id"] == self.settings["selected_market"])
            a.triggered.connect(lambda _=False, mid=m["id"]: self.select_market(mid))
            grp.addAction(a)
            self.menu.addAction(a)
        self.menu.addSeparator()

        pref_a = QAction("⚙️  Preferences…", self.menu)
        pref_a.triggered.connect(self.open_preferences)
        self.menu.addAction(pref_a)

        # v0.2 multi-select impact filter
        active = set(self.settings.get("active_impacts", ["High", "Medium", "Low"]))
        filt = self.menu.addMenu("News: impact filter")
        a_all = QAction("🌐 Select all (incl. holidays)", self.menu)
        a_all.triggered.connect(lambda: self.set_active_impacts(["High", "Medium", "Low"]))
        filt.addAction(a_all)
        filt.addSeparator()
        for lvl, label in (("High", "🔴 High"), ("Medium", "🟠 Medium"), ("Low", "🟡 Low")):
            a = QAction(label, self.menu, checkable=True)
            a.setChecked(lvl in active)
            a.triggered.connect(lambda _=False, lv=lvl: self.toggle_impact(lv))
            filt.addAction(a)

        curm = self.menu.addMenu("News: currencies")
        for cur in ALL_CURRENCIES:
            a = QAction(cur, self.menu, checkable=True)
            a.setChecked(cur in self.settings.get("currencies", []))
            a.triggered.connect(lambda _=False, c=cur: self.toggle_currency(c))
            curm.addAction(a)

        disp = self.menu.addMenu("Display in tray")
        for key, label in (
            ("show_symbol", "Market symbol"),
            ("show_countdown", "Countdown timer"),
            ("show_local_time", "Market local time"),
            ("show_next_event", "Next event"),
        ):
            a = QAction(label, self.menu, checkable=True)
            a.setChecked(bool(self.settings.get(key, True)))
            a.triggered.connect(lambda _=False, k=key: self.toggle_display(k))
            disp.addAction(a)
        theme_m = self.menu.addMenu("Theme")
        tgrp = QActionGroup(self.menu)
        tgrp.setExclusive(True)
        for t in THEME_ORDER:
            a = QAction(f"{THEME_ICON[t]}  {THEME_LABELS[t]}", self.menu, checkable=True)
            a.setChecked(self.settings.get("theme", "system") == t)
            a.triggered.connect(lambda _=False, tv=t: self.set_theme(tv))
            tgrp.addAction(a)
            theme_m.addAction(a)

        lcm = self.menu.addMenu("Left-click icon")
        lgrp = QActionGroup(self.menu)
        lgrp.setExclusive(True)
        for val, label in (("panel", "Open panel"), ("menu", "Open menu")):
            a = QAction(label, self.menu, checkable=True)
            a.setChecked(self.settings.get("left_click_action", "panel") == val)
            a.triggered.connect(lambda _=False, v=val: self.set_left_click(v))
            lgrp.addAction(a)
            lcm.addAction(a)

        self.menu.addSeparator()
        rn = QAction("Refresh news", self.menu)
        rn.triggered.connect(lambda: self.refresh_news(force=True))
        self.menu.addAction(rn)
        pn = QAction("Show / hide panel", self.menu)
        pn.triggered.connect(self.toggle_panel)
        self.menu.addAction(pn)

        st = QAction("Open on startup (login)", self.menu, checkable=True)
        st.setChecked(is_autostart_enabled())
        st.triggered.connect(lambda checked: self.set_autostart_enabled(bool(checked)))
        self.menu.addAction(st)

        cu = QAction("Check for updates now", self.menu)
        cu.triggered.connect(lambda: self._check_updates(force=True, announce=True))
        self.menu.addAction(cu)

        self.menu.addSeparator()
        q = QAction("❌ Quit Market Sync", self.menu)
        q.triggered.connect(self.quit_app)
        self.menu.addAction(q)

    def _save(self):
        from config import save_settings
        save_settings(self.settings)

    # -- settings mutators
    def select_market(self, mid: str):
        self.settings["selected_market"] = mid
        self._alerted_key = None
        self._save()
        self.tick()

    def toggle_display(self, key: str):
        self.settings[key] = not self.settings.get(key, True)
        self._save()
        self._build_menu()
        self.tick()

    def set_theme(self, t: str):
        self.settings["theme"] = t
        self._save()
        self._build_menu()
        self.panel.apply_theme()
        self.tick()

    def cycle_theme(self):
        cur = self.settings.get("theme", "system")
        self.set_theme(
            THEME_ORDER[(THEME_ORDER.index(cur) + 1) % len(THEME_ORDER)]
            if cur in THEME_ORDER else "system"
        )

    def toggle_alerts(self):
        self.settings["alerts_enabled"] = not self.settings.get("alerts_enabled", True)
        self._save()
        self._build_menu()
        self.tick()

    # -- v0.2 impact chips
    def set_active_impacts(self, impacts: list):
        imp = [lvl for lvl in ("High", "Medium", "Low") if lvl in impacts]
        self.settings["active_impacts"] = imp or ["High", "Medium", "Low"]
        self._save()
        self._build_menu()
        self.tick()

    def toggle_impact(self, lvl: str):
        active = list(self.settings.get("active_impacts", ["High", "Medium", "Low"]))
        if lvl in active:
            active.remove(lvl)
        else:
            active.append(lvl)
        self.set_active_impacts(active)

    def toggle_currency(self, cur: str):
        cur = cur.upper()
        lst = list(self.settings.get("currencies", []))
        if cur in lst:
            if len(lst) > 1:  # keep at least one
                lst.remove(cur)
        else:
            lst.append(cur)
        self.settings["currencies"] = lst
        self._save()
        self._build_menu()
        self.tick()

    def set_left_click(self, val: str):
        self.settings["left_click_action"] = val
        self._save()
        self._build_menu()
        self.tick()

    def open_preferences(self):
        try:
            self.panel.hide()
        except Exception:
            pass
        try:
            dlg = PreferencesDialog(self)
            screen = self.app.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                dlg.move(geo.center().x() - dlg.width() // 2,
                         geo.center().y() - dlg.height() // 2)
            self._prefs = dlg
            dlg.exec()
        except Exception:
            pass

    def set_autostart_enabled(self, on: bool):
        """Toggle login autostart (system entry + Hidden=true user override)."""
        from config import SYSTEM_AUTOSTART_PATH
        try:
            os.makedirs(os.path.dirname(USER_AUTOSTART_PATH), exist_ok=True)
            if on:
                try:
                    os.remove(USER_AUTOSTART_PATH)
                except FileNotFoundError:
                    pass
                if not os.path.exists(SYSTEM_AUTOSTART_PATH):
                    icon = os.path.join(app_dir(), "assets", "icon.svg")
                    with open(USER_AUTOSTART_PATH, "w", encoding="utf-8") as f:
                        f.write("[Desktop Entry]\nType=Application\nName=Market Sync\n"
                                "Comment=Market countdown + news\n"
                                f"Exec={autostart_exec_line()}\n"
                                f"Path={app_dir()}\nIcon={icon}\nTerminal=false\n"
                                "Categories=Finance;Office;\nX-GNOME-Autostart-enabled=true\n"
                                "X-GNOME-Autostart-Delay=5\nStartupNotify=false\n")
            else:
                if os.path.exists(SYSTEM_AUTOSTART_PATH):
                    with open(USER_AUTOSTART_PATH, "w", encoding="utf-8") as f:
                        f.write("[Desktop Entry]\nType=Application\nName=Market Sync\n"
                                "Hidden=true\n")
                else:
                    try:
                        os.remove(USER_AUTOSTART_PATH)
                    except FileNotFoundError:
                        pass
        except Exception:
            pass
        self._build_menu()
        if self.panel.isVisible():
            self.tick()

    def refresh_news(self, force=False):
        def _work():
            try:
                ev, _cached, note = calendar_api.fetch_events(
                    force_refresh=force,
                    cache_ttl_min=self.settings.get("news_refresh_minutes", 15),
                )
                with self._news_lock:
                    self.events = ev
                    self.news_note = note
            except Exception:
                pass

        with self._news_lock:
            empty = not self.events
        if empty or force:
            _work()  # synchronous on launch so first paint has data
        else:
            threading.Thread(target=_work, daemon=True).start()

    # ---------------- auto-update plumbing (threads only write state; tick reads)
    def _check_updates(self, force: bool = False, announce: bool = False):
        if self._update_busy:
            return
        self._update_busy = True
        self._update_announce = bool(announce)

        def _work():
            try:
                res = updater.check_for_update(force=force)
            except Exception:
                res = None
            self._update_result = res

        threading.Thread(target=_work, daemon=True).start()

    def _consume_updates(self):
        if self._update_result is not _UNSET:
            res, self._update_result = self._update_result, _UNSET
            self._update_busy = False
            old_tag = (self._update_info or {}).get("tag")
            new_tag = (res or {}).get("tag")
            self._update_info = res
            if res and new_tag != old_tag:
                self._build_menu()
                if self._update_notified_tag != new_tag:
                    self._update_notified_tag = new_tag
                    notify(f"{APP_NAME} v{res.get('version')} available",
                           "Right-click the tray icon → Update to install (one click).")
            elif getattr(self, "_update_announce", False):
                self._update_announce = False
                if not res:
                    notify(APP_NAME, f"You're up to date (v{APP_VERSION}).")

        if self._update_status is not None:
            kind, ui = self._update_status
            self._update_status = None
            if kind == "installing":
                notify(APP_NAME, "Installing update… (a password prompt will appear)")
            elif kind == "installed":
                notify(APP_NAME, "Update installed — restarting…")
                QTimer.singleShot(1200, self._relaunch)
            elif kind == "error":
                notify(APP_NAME, "Update failed — opening download page")
                if ui.get("html_url"):
                    updater.open_in_browser(ui.get("html_url", ""))

    def _do_update(self):
        ui = self._update_info or {}
        if not ui:
            return
        url = ui.get("deb_url") or ""
        if not url:
            if ui.get("html_url"):
                updater.open_in_browser(ui["html_url"])
            return
        if getattr(self, "_update_installing", False):
            return
        self._update_installing = True
        notify(APP_NAME, f"Downloading v{ui.get('version')}…")

        def _work():
            dest = os.path.join(CACHE_DIR, "update.deb")
            try:
                if not updater.download_deb(url, dest):
                    self._update_status = ("error", ui)
                    return
                self._update_status = ("installing", ui)
                ok = updater.install_deb(dest)
                self._update_status = ("installed", ui) if ok else ("error", ui)
            finally:
                self._update_installing = False

        threading.Thread(target=_work, daemon=True).start()

    def _relaunch(self):
        try:
            if IS_PACKAGED and os.path.exists(LAUNCHER_PATH):
                cmd = f"sleep 2; SESSION_SYNC_RELAUNCH=1 exec {LAUNCHER_PATH}"
            else:
                cmd = (f"sleep 2; SESSION_SYNC_RELAUNCH=1 exec /usr/bin/python3 "
                       f"{os.path.join(app_dir(), 'main.py')}")
            subprocess.Popen(
                ["setsid", "bash", "-c", cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass
        self.quit_app()

    # ---------------- tray text/icon (v0.2 parity)
    def _multi_segments(self):
        """Build tray text tokens per v0.2 prefs: layout, time-as, sessions."""
        md = self.settings.get("market_display", {})
        sessions = self.settings.get("tray_sessions", "active_and_next")
        layout_mode = self.settings.get("tray_layout", "compact")
        time_as = self.settings.get("tray_time_as", "countdown")
        is_12h = self.settings.get("time_format", "24h") == "12h"

        def eligible(s):
            return md.get(s["market"]["id"], "panel") == "panel"

        def token(s):
            m = s["market"]
            name = m["symbol"] if layout_mode == "compact" else m["name"]
            if time_as == "local_time":
                val = engine.format_local_clock(s["now_local"], is_12h)
            else:
                val = engine.format_signed_countdown(
                    s["countdown"], s["is_open"]).replace(" ", "")
            return (f"{name} {val}", bool(s["is_open"]))

        opens = [s for s in self.statuses if s["is_open"] and eligible(s)]
        closed = sorted(
            [s for s in self.statuses if not s["is_open"] and eligible(s)],
            key=lambda x: x["countdown"].total_seconds())
        if sessions == "active_only":
            chosen = opens if opens else closed[:1]
        elif sessions == "active_and_next":
            chosen = opens + closed[:1]
        else:  # all
            chosen = opens + closed
        segs = [token(s) for s in chosen]
        if not segs:
            segs = [token(self.selected)]
        any_open = any(s["is_open"] for s in self.statuses)
        return segs, any_open

    def tick(self):
        now_utc = datetime.now(timezone.utc)
        try:
            self.statuses = engine.get_all_statuses(now_utc)
        except Exception:
            return
        sel = [s for s in self.statuses if s["market"]["id"] == self.settings["selected_market"]]
        self.selected = sel[0] if sel else self.statuses[0]
        with self._news_lock:
            events = list(self.events)
            note = self.news_note
        active = self.settings.get("active_impacts", ["High", "Medium", "Low"])
        nxt = calendar_api.next_event(
            events, self.settings["currencies"], None, now_utc, active_impacts=active)

        # -- tray icon + tooltip
        theme = self.settings.get("theme", "system")
        mode = self.settings.get("tray_mode", "multi")
        style = self.settings.get("tray_icon_style", "text")
        any_open = any(s["is_open"] for s in self.statuses)
        try:
            if mode == "multi":
                segs, multi_open = self._multi_segments()
                key = ("m", tuple(segs), style, theme)
                if key != self._last_tray_key:
                    if style == "logo":
                        self.tray.setIcon(make_tray_logo_icon(multi_open))
                    else:
                        self.tray.setIcon(make_tray_icon_multi(segs, theme))
                    self._last_tray_key = key
            else:
                label = tray_label_text(self.selected, nxt, self.settings, now_utc)
                is_open = bool(self.selected["is_open"])
                key = ("s", label, style, theme, is_open)
                if key != self._last_tray_key:
                    if style == "logo":
                        self.tray.setIcon(make_tray_logo_icon(any_open))
                    else:
                        self.tray.setIcon(make_tray_icon(label, is_open, theme))
                    self._last_tray_key = key
        except Exception:
            pass

        is_12h = self.settings.get("time_format", "24h") == "12h"
        lines = []
        for s in self.statuses:
            m = s["market"]
            state = "OPEN" if s["is_open"] else "CLOSED"
            cd = engine.format_signed_countdown(s["countdown"], s["is_open"])
            loc = engine.format_local_clock(s["now_local"], is_12h)
            lines.append(f"{m['name']} ({m['symbol']}): {state} ({cd}) • {loc}")
        tip = "\n".join(lines)
        if nxt and nxt.get("_dt"):
            try:
                tip += f"\nNext: {calendar_api.event_countdown_line(nxt, now_utc)}"
            except Exception:
                pass
        holiday = _next_nyse_holiday_line(now_utc)
        if holiday:
            tip += f"\n{holiday}"
        try:
            self.tray.setToolTip(tip)
        except Exception:
            pass

        if self.panel.isVisible():
            try:
                self.panel.render(self.statuses, self.selected, events, note, now_utc)
            except Exception:
                pass
        try:
            self._consume_updates()
        except Exception:
            pass
        try:
            self._maybe_alert(nxt, now_utc)
        except Exception:
            pass

    def _maybe_alert(self, nxt, now_utc):
        if not self.settings.get("alerts_enabled"):
            return
        s = self.selected
        key = f"{s['market']['id']}:{'o' if s['is_open'] else 'c'}:{s['next_at_utc'].isoformat()}"
        secs = s["countdown"].total_seconds()
        if secs <= self.settings.get("alert_minutes_before", 5) * 60:
            if self._alerted_key != key:
                self._alerted_key = key
                notify(
                    f"{s['market']['name']} {s['next_label']} soon",
                    f"{s['market']['symbol']} {s['next_label']} in {engine.format_countdown(s['countdown'])}",
                )
        if nxt and nxt.get("_dt") and nxt["impact"] == "High":
            mins = (nxt["_dt"] - now_utc).total_seconds() / 60
            if 0 <= mins <= 15:
                eid = nxt["date_utc"] + nxt["title"]
                if self.tracker.should_fire_news(eid):
                    notify(
                        f"High impact: {nxt['currency']} {nxt['title']}",
                        calendar_api.event_countdown_line(nxt, now_utc),
                    )

    def quit_app(self):
        try:
            self.timer.stop()
        except Exception:
            pass
        try:
            self.news_timer.stop()
        except Exception:
            pass
        try:
            self.panel.hide()
        except Exception:
            pass
        try:
            self.tray.setVisible(False)
        except Exception:
            pass
        self.app.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.settings.get("left_click_action", "panel") == "menu":
                try:
                    self.menu.popup(QCursor.pos())
                except Exception:
                    self.toggle_panel()
            else:
                self.toggle_panel()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.toggle_panel()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            pass  # right-click menu handled by Qt via setContextMenu

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
            return
        with self._news_lock:
            events = list(self.events)
            note = self.news_note
        self.panel.render(
            self.statuses, self.selected, events, note, datetime.now(timezone.utc)
        )
        try:
            self.panel.adjustSize()
            screen = self.app.primaryScreen()
            avail = screen.availableGeometry() if screen else self.app.primaryScreen().geometry()
            c = QCursor.pos()
            w, h = max(self.panel.width(), 410), max(self.panel.height(), 200)
            x = min(max(c.x() - w // 2, avail.x() + 8), avail.x() + avail.width() - w - 8)
            y = min(max(c.y() + 16, avail.y() + 8), avail.y() + avail.height() - h - 8)
            self.panel.move(max(x, 8), max(y, 8))
        except Exception:
            pass
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
        try:
            self.panel.setFocus()
        except Exception:
            pass
