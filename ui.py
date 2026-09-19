"""Market Sync — glassmorphism market countdown + news (Cinnamon tray).

Design language ported from Market Sync v0.2: frosted translucent cards,
landmark vector badges (London Eye, Statue of Liberty, Sydney Opera House,
Torii Gate), signed countdowns (+open / -closed), active-session brightening,
and multi-impact news chips [All] [🔴 High] [🟠 Med] [🟡 Low].
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
        QFrame, QCheckBox, QGridLayout,
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
    MARKETS, get_market, ALL_CURRENCIES, is_autostart_enabled,
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
# Tokens follow the v0.2 Material-glass design: translucent panel + cards,
# brighter card + green border while a session is open, dimmed while closed.
THEMES = {
    "light": {
        "bg": "rgba(250, 252, 255, 0.90)",
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
        "tab_checked_bg": "#e8f1fc",
        "tray_text": "#1d1d1f",
    },
    "dark": {
        "bg": "rgba(16, 20, 30, 0.88)",
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
        "tab_checked_bg": "#353b44",
        "tray_text": "#ffffff",
    },
    "dark_purple": {
        "bg": "rgba(23, 18, 34, 0.88)",
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
        "tab_checked_bg": "#322750",
        "tray_text": "#ece7f6",
    },
    "mint_light": {
        "bg": "rgba(242, 250, 245, 0.90)",
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
        "tab_checked_bg": "#e2f5ea",
        "tray_text": "#1c2b23",
    },
    "mint_dark": {
        "bg": "rgba(18, 29, 24, 0.88)",
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
        "tab_checked_bg": "#2a4538",
        "tray_text": "#e3f0e9",
    },
}

# Order used by the cycle button; includes the pseudo-theme "system".
THEME_ORDER = ["system", "light", "dark", "dark_purple", "mint_light", "mint_dark"]
THEME_LABELS = {
    "system": "System",
    "light": "Light",
    "dark": "Dark",
    "dark_purple": "Dark Purple",
    "mint_light": "Mint Light",
    "mint_dark": "Mint Dark",
}
THEME_ICON = {
    "system": "🖥️",
    "light": "☀️",
    "dark": "🌙",
    "dark_purple": "🟣",
    "mint_light": "🌿",
    "mint_dark": "🍃",
}

# v0.2 impact palette: High red, Medium orange, Low yellow, Holiday purple.
IMPACT_COLOR = {"High": "#ff453a", "Medium": "#ff9f0a", "Low": "#ffd60a", "Holiday": "#bf5af2"}
CHIP_COLOR = {"All": None, "Low": "#ffd60a", "Medium": "#ff9f0a", "High": "#ff453a"}
CHIP_LABEL = {"All": "All", "Low": "🟡 Low", "Medium": "🟠 Med", "High": "🔴 High"}

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
QLabel.caption {{ color: {t['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }}
QLabel.cd {{ font-family: monospace; font-weight: 800; }}
QLabel.nextcard {{ background: {t['tint']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 8px 10px; }}
QFrame.card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QPushButton.ghost {{ background: transparent; color: {t['muted']}; border: 1px solid {t['border']}; border-radius: 7px; padding: 4px 10px; font-size: 12px; }}
QPushButton.ghost:hover {{ color: {t['text']}; border-color: {t['accent']}; }}
QPushButton.quitbtn {{ background: #ff453a; color: white; border: none; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 800; }}
QPushButton.quitbtn:hover {{ background: #d70015; }}
QCheckBox {{ color: {t['muted']}; font-size: 11px; background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; }}
"""


# ---------------------------------------------------------------- tray text
# Ultra-compact tray: 3-letter symbol + countdown (LON +02:14:33 …)
def tray_label_text(selected: dict, nxt, settings: dict, now_utc) -> str:
    m = selected["market"]
    parts: list[str] = []
    if settings.get("show_symbol", True):
        parts.append(m["symbol"])
    if settings.get("show_countdown", True):
        parts.append(engine.format_signed_countdown(
            selected["countdown"], selected["is_open"], include_seconds=True).replace(" ", ""))
    if settings.get("show_local_time", True):
        parts.append(selected["now_local"].strftime("%H:%M"))
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


def _fmt_event_time(iso_utc: str) -> str:
    try:
        return datetime.fromisoformat(iso_utc).astimezone().strftime("%a %H:%M")
    except Exception:
        return ""


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
    class RingTimer(QWidget):
        """Hero progress ring — neon green while open, red while closed."""

        def __init__(self, size: int = 64):
            super().__init__()
            self._frac = 0.0
            self._open = False
            self.setFixedSize(size, size)

        def set(self, frac: float, is_open: bool):
            self._frac = min(1.0, max(0.0, frac))
            self._open = is_open
            self.update()

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            theme = THEMES.get(getattr(self, "_theme", "dark"), THEMES["dark"])
            w = 7
            rect = QRectF(w, w, self.width() - 2 * w, self.height() - 2 * w)
            p.setPen(QPen(QColor(theme["ring_track"]), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 0, 360 * 16)
            p.setPen(QPen(QColor(GREEN if self._open else RED), w,
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._frac * 360 * 16))
            p.end()
else:
    class RingTimer:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


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
                # fallback: symbol initials inside the circle
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

        def __init__(self, size: int = 16):
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
        """v0.2 Material glass card: bright while open, dimmed while closed.

        Top row:    landmark badge • symbol • local clock
        Bottom row: signed countdown (+open/-closed) • pill • mini ring
        """

        clicked = pyqtSignal(str)

        def __init__(self, market: dict, parent: QWidget | None = None):
            super().__init__(parent)
            self.market = market
            self.setObjectName("MarketCard")
            self.setFixedHeight(58)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 5, 10, 5)
            lay.setSpacing(2)

            top = QHBoxLayout()
            top.setSpacing(6)
            self.badge = LandmarkBadge(market.get("landmark", "london"), market["symbol"], 22)
            top.addWidget(self.badge)
            self.name_label = QLabel(market["symbol"])
            self.name_label.setStyleSheet("font-weight: 800; font-size: 12px;")
            top.addWidget(self.name_label)
            top.addStretch(1)
            self.time_label = QLabel("00:00")
            self.time_label.setStyleSheet("font-size: 11px;")
            top.addWidget(self.time_label)
            lay.addLayout(top)

            bot = QHBoxLayout()
            bot.setSpacing(5)
            self.cd_label = QLabel("+ 00:00")
            self.cd_label.setProperty("class", "cd")
            self.cd_label.setStyleSheet("font-family: monospace; font-size: 14px; font-weight: 800;")
            bot.addWidget(self.cd_label)
            bot.addStretch(1)
            self.pill = QLabel("OPEN")
            self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pill.setFixedSize(54, 17)
            f = QFont("Sans", 8)
            f.setWeight(QFont.Weight.Bold)
            self.pill.setFont(f)
            bot.addWidget(self.pill)
            self.ring = MiniRingTimer(16)
            bot.addWidget(self.ring)
            lay.addLayout(bot)

        def mousePressEvent(self, ev):
            if ev.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self.market["id"])
            super().mousePressEvent(ev)

        def update_data(self, status: dict, t: dict, selected: bool):
            m = self.market
            is_open = bool(status["is_open"])
            self.badge.set_theme(t)
            self.time_label.setText(status["now_local"].strftime("%H:%M"))
            self.time_label.setStyleSheet(f"font-size: 11px; color: {t['muted']};")
            self.cd_label.setText(engine.format_signed_countdown(status["countdown"], is_open))
            # Active-session brightening (v0.2): neon green vs muted slate
            if is_open:
                self.cd_label.setStyleSheet(
                    f"font-family: monospace; font-size: 14px; font-weight: 800; color: {GREEN};")
                self.name_label.setStyleSheet("font-weight: 800; font-size: 12px;")
                self.pill.setText("OPEN")
                self.pill.setStyleSheet(
                    f"background: {t['pill_open_bg']}; color: {t['pill_open_text']};"
                    "border-radius: 5px; font-weight: bold;")
                bg, bd = t["card_open"], t["card_border_open"]
            else:
                self.cd_label.setStyleSheet(
                    f"font-family: monospace; font-size: 14px; font-weight: 800; color: {t['muted']};")
                self.name_label.setStyleSheet(f"font-weight: 800; font-size: 12px; color: {t['muted']};")
                self.pill.setText("CLOSED")
                self.pill.setStyleSheet(
                    f"background: {t['pill_closed_bg']}; color: {t['pill_closed_text']};"
                    "border-radius: 5px; font-weight: bold;")
                bg, bd = t["card_closed"], t["card_border_closed"]
            bw = "1.5px" if selected else ("1.5px" if is_open else "1px")
            bcol = t["accent"] if selected else bd
            self.setStyleSheet(
                f"QFrame#MarketCard {{ background: {bg}; border: {bw} solid {bcol}; border-radius: 12px; }}")
            self.ring.set_state(status.get("progress", 0.0), is_open, t)
else:
    class MarketCardWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


class SessionPanel(QWidget):
    """Market Sync glass popover: brand bar, hero, market cards, news chips."""

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
        self.setFixedWidth(344)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # ---- brand bar: logo + MARKET SYNC + controls (v0.2 BrandBar)
        brand = QHBoxLayout()
        brand.setSpacing(6)
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
        self.theme_btn.setProperty("class", "ghost")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Toggle light / dark / system")
        self.theme_btn.clicked.connect(self.c.cycle_theme)
        brand.addWidget(self.theme_btn)
        self.time_btn = QPushButton("")
        self.time_btn.setProperty("class", "ghost")
        self.time_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.time_btn.setToolTip("Flip which clock is emphasised (both always shown)")
        self.time_btn.clicked.connect(self.c.toggle_time_mode)
        brand.addWidget(self.time_btn)
        refresh = QPushButton("↻")
        refresh.setProperty("class", "ghost")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setToolTip("Refresh news")
        refresh.clicked.connect(lambda: self.c.refresh_news(force=True))
        brand.addWidget(refresh)
        self.close_btn = QPushButton("✕")
        self.close_btn.setProperty("class", "ghost")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Hide panel (app keeps running in tray)")
        self.close_btn.clicked.connect(self.hide)
        brand.addWidget(self.close_btn)
        root.addLayout(brand)

        # ---- hero: ring + landmark + signed countdown + dual clocks
        hero = QFrame()
        hero.setProperty("class", "card")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(12)
        self.ring = RingTimer(64)
        hl.addWidget(self.ring)
        hv = QVBoxLayout()
        hv.setSpacing(2)
        hrow = QHBoxLayout()
        hrow.setSpacing(6)
        self.hero_badge = LandmarkBadge("london", "LON", 30)
        hrow.addWidget(self.hero_badge)
        self.hero_name = QLabel("")
        self.hero_name.setStyleSheet("font-size: 14px; font-weight: 800;")
        hrow.addWidget(self.hero_name)
        self.hero_pill = QLabel("")
        self.hero_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pf = QFont("Sans", 8, QFont.Weight.Bold)
        self.hero_pill.setFont(pf)
        hrow.addWidget(self.hero_pill)
        hrow.addStretch(1)
        hv.addLayout(hrow)
        self.hero_cd = QLabel("+ 00:00:00")
        self.hero_cd.setStyleSheet("font-family: monospace; font-size: 24px; font-weight: 800;")
        hv.addWidget(self.hero_cd)
        self.hero_at = QLabel("")
        self.hero_at.setProperty("class", "muted")
        hv.addWidget(self.hero_at)
        self.hero_clocks = QLabel("")
        self.hero_clocks.setProperty("class", "muted")
        self.hero_clocks.setWordWrap(True)
        hv.addWidget(self.hero_clocks)
        hl.addLayout(hv, 1)
        root.addWidget(hero)

        # ---- market cards grid (v0.2: 2 columns, glass, bright/dim)
        self.cards: dict[str, MarketCardWidget] = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for idx, m in enumerate(MARKETS):
            card = MarketCardWidget(m)
            card.clicked.connect(self.c.select_market)
            self.cards[m["id"]] = card
            r, c = divmod(idx, 2)
            if idx == len(MARKETS) - 1 and len(MARKETS) % 2 == 1:
                grid.addWidget(card, r, 0, 1, 2)  # last card spans full width
            else:
                grid.addWidget(card, r, c)
        root.addLayout(grid)

        # ---- news: UP NEXT + impact chips (v0.2: All / High / Med / Low)
        caprow = QHBoxLayout()
        cap2 = QLabel("UP NEXT")
        cap2.setProperty("class", "caption")
        caprow.addWidget(cap2)
        caprow.addStretch(1)
        self.news_src = QLabel("")
        self.news_src.setProperty("class", "muted")
        caprow.addWidget(self.news_src)
        root.addLayout(caprow)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.impact_btns: dict[str, QPushButton] = {}
        for lvl in ("All", "Low", "Medium", "High"):
            b = QPushButton(CHIP_LABEL[lvl])
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(f"Minimum impact: {lvl}" + (" (includes holidays)" if lvl == "All" else " (holidays hidden)"))
            b.clicked.connect(lambda _=False, lv=lvl: self.c.set_min_impact(lv))
            chips.addWidget(b, 1)
            self.impact_btns[lvl] = b
        root.addLayout(chips)

        self.next_card = QLabel("Loading news…")
        self.next_card.setProperty("class", "nextcard")
        self.next_card.setWordWrap(True)
        root.addWidget(self.next_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(96)
        inner = QWidget()
        self.news_list = QVBoxLayout(inner)
        self.news_list.setSpacing(2)
        self.news_list.setContentsMargins(2, 0, 8, 0)
        scroll.setWidget(inner)
        root.addWidget(scroll)
        self._news_sig: list | None = None
        self._news_labels: list = []

        self.foot = QLabel("")
        self.foot.setProperty("class", "muted")
        self.foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foot.setWordWrap(True)
        root.addWidget(self.foot)

        # ---- bottom action row: Hide + startup + Quit
        actionrow = QHBoxLayout()
        actionrow.setSpacing(6)
        self.hide_btn = QPushButton("Hide")
        self.hide_btn.setProperty("class", "ghost")
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.setToolTip("Close panel, keep running in tray")
        self.hide_btn.clicked.connect(self.hide)
        actionrow.addWidget(self.hide_btn, 1)
        self.autostart_chk = QCheckBox("Start on login")
        self.autostart_chk.setToolTip("Open this app automatically when you log in")
        self.autostart_chk.toggled.connect(self.c.set_autostart_enabled)
        actionrow.addWidget(self.autostart_chk, 1)
        self.quit_btn = QPushButton("Quit app")
        self.quit_btn.setProperty("class", "quitbtn")
        self.quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_btn.setToolTip("Fully close Market Sync")
        self.quit_btn.clicked.connect(self.c.quit_app)
        actionrow.addWidget(self.quit_btn, 1)
        root.addLayout(actionrow)

        self.apply_theme()

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
        self.ring._theme = self._theme  # type: ignore
        want = self.c.settings.get("theme", "system")
        self.theme_btn.setText(THEME_ICON.get(want, "🖥️"))
        self.theme_btn.setToolTip(f"Theme: {THEME_LABELS.get(want, want)} (click to cycle)")
        # chips: semantic colors, tinted when checked (works on light + dark)
        for lvl, b in self.impact_btns.items():
            base = CHIP_COLOR[lvl] or t["accent"]
            c = QColor(base)
            tint = f"rgba({c.red()}, {c.green()}, {c.blue()}, 51)"
            b.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {t['muted']}; "
                f"border: 1px solid {t['border']}; border-radius: 11px; "
                f"padding: 3px 2px; font-size: 11px; font-weight: 700; }}"
                f"QPushButton:checked {{ color: {base}; border-color: {base}; background: {tint}; }}")

    def render(self, statuses, selected, news, news_note, now_utc):
        if resolve_theme(self.c.settings.get("theme", "system")) != self._theme:
            self.apply_theme()
        t = THEMES[self._theme]
        sel_id = self.c.settings["selected_market"]

        # impact chips reflect current minimum (All / Low / Med / High)
        cur = self.c.settings.get("min_impact", "All")
        for lvl, b in self.impact_btns.items():
            b.setChecked(lvl == cur)

        # autostart checkbox reflects real file state
        try:
            self.autostart_chk.blockSignals(True)
            self.autostart_chk.setChecked(is_autostart_enabled())
            self.autostart_chk.blockSignals(False)
        except Exception:
            pass
        tm = self.c.settings.get("time_mode", "market_local")
        self.time_btn.setText("🕒 Market first" if tm == "market_local" else "🕒 Mine first")

        # ---- hero
        m = selected["market"]
        self.hero_badge.set_landmark(m.get("landmark", "london"), m["symbol"])
        self.hero_badge.set_theme(t)
        self.hero_name.setText(m["name"])
        if selected["is_open"]:
            self.hero_pill.setText("OPEN")
            self.hero_pill.setStyleSheet(
                f"background: {t['pill_open_bg']}; color: {t['pill_open_text']};"
                "border-radius: 5px; font-weight: bold; padding: 1px 8px;")
            self.hero_cd.setStyleSheet(
                f"font-family: monospace; font-size: 24px; font-weight: 800; color: {GREEN};")
        else:
            self.hero_pill.setText("CLOSED")
            self.hero_pill.setStyleSheet(
                f"background: {t['pill_closed_bg']}; color: {t['pill_closed_text']};"
                "border-radius: 5px; font-weight: bold; padding: 1px 8px;")
            self.hero_cd.setStyleSheet(
                f"font-family: monospace; font-size: 24px; font-weight: 800; color: {t['text']};")
        self.hero_cd.setText(engine.format_signed_countdown(
            selected["countdown"], selected["is_open"], include_seconds=True))
        self.ring.set(selected["progress"], selected["is_open"])
        at = selected["next_at_local"].strftime("%a %H:%M %Z")
        self.hero_at.setText(f"{'Closes' if selected['is_open'] else 'Opens'} {at}")
        mkt_clock = selected["now_local"].strftime("%H:%M:%S %Z")
        yours = now_utc.astimezone().strftime("%H:%M:%S %Z")
        mkt_tz = m.get("tz", "")
        if tm == "market_local":
            self.hero_clocks.setText(f"🏦 Market ({mkt_tz}): {mkt_clock}<br>💻 Yours (laptop): {yours}")
        else:
            self.hero_clocks.setText(f"💻 Yours (laptop): {yours}<br>🏦 Market ({mkt_tz}): {mkt_clock}")

        # ---- market cards (v0.2 brightening)
        for s in statuses:
            mid = s["market"]["id"]
            if mid in self.cards:
                self.cards[mid].update_data(s, t, selected=(mid == sel_id))

        # ---- news
        self.news_src.setText(news_note)
        nxt = calendar_api.next_event(
            news, self.c.settings["currencies"], self.c.settings["min_impact"], now_utc
        )
        if nxt:
            cdl = calendar_api.event_countdown_line(nxt, now_utc)
            col = IMPACT_COLOR.get(nxt["impact"], "#8e8e93")
            when = _fmt_event_time(nxt["date_utc"])
            self.next_card.setText(
                f"NEXT  <b>{nxt['currency']}</b>  <font color='{col}'>● {nxt['impact']}</font>"
                f"<br><b>{nxt['title']}</b><br>"
                f"<font color='{t['muted']}'>{cdl} • {when}</font>"
            )
        else:
            self.next_card.setText("No upcoming events for this filter.")

        shown = calendar_api.filter_events(
            news, self.c.settings["currencies"], self.c.settings["min_impact"], 72, now_utc
        )[:8]
        sig = [(e["currency"], e["title"], e["date_utc"], e["impact"]) for e in shown]
        if sig != getattr(self, "_news_sig", None):
            self._news_sig = sig
            while self.news_list.count():
                w = self.news_list.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self._news_labels: list[QLabel] = []
            if not shown:
                lab = QLabel("No events — press ↻ or widen the impact / currency filter.")
                lab.setWordWrap(True)
                self.news_list.addWidget(lab)
                self._news_labels.append(lab)
            for e in shown:
                col = IMPACT_COLOR.get(e["impact"], "#8e8e93")
                tt = _fmt_event_time(e["date_utc"])
                lab = QLabel(
                    f"<font color='{col}'>●</font> <b>{e['currency']}</b> {e['title']} "
                    f"<font color='{t['muted']}'>· {tt}</font>"
                )
                lab.setWordWrap(True)
                self.news_list.addWidget(lab)
                self._news_labels.append(lab)
        else:
            for lab, e in zip(getattr(self, "_news_labels", []), shown):
                col = IMPACT_COLOR.get(e["impact"], "#8e8e93")
                tt = _fmt_event_time(e["date_utc"])
                lab.setText(
                    f"<font color='{col}'>●</font> <b>{e['currency']}</b> {e['title']} "
                    f"<font color='{t['muted']}'>· {tt}</font>"
                )

        self.foot.setText(f"{_next_nyse_holiday_line(now_utc)}  •  ForexFactory feed")


class TrayController:
    def __init__(self, app: "QApplication", settings: dict):
        self.app = app
        self.settings = settings
        self.tracker = AlertTracker()
        self._alerted_key: str | None = None
        self.events: list[dict] = []
        self.news_note = "news: …"
        self._news_lock = threading.Lock()
        self._last_tray_label: str | None = None
        self._last_tray_state: bool | None = None
        self._last_tray_theme: str | None = None
        self.statuses = engine.get_all_statuses()
        self.selected = engine.market_status(get_market(settings["selected_market"]))

        # --- auto-update state (must exist before _build_menu reads it)
        self._update_result = _UNSET
        self._update_info: dict | None = None
        self._update_notified_tag: str | None = None
        self._update_status: tuple | None = None
        self._update_busy = False

        self.tray = QSystemTrayIcon()
        self.tray.setVisible(True)
        self.tray.activated.connect(self._on_activated)
        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)

        self.panel = SessionPanel(self)
        # keep menu + panel on the same resolved theme from the first paint
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
        # first check shortly after launch so startup stays instant
        QTimer.singleShot(12000, lambda: self._check_updates(force=False))

        self.refresh_news(force=True)
        self.tick()

    # -- right-click menu: markets + news filter + left-click + startup + quit
    def _build_menu(self):
        self.menu.clear()

        # update banner (only when a newer release exists)
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

        # News filter: minimum impact (All includes holidays)
        filt = self.menu.addMenu("News: min impact")
        igrp = QActionGroup(self.menu)
        igrp.setExclusive(True)
        for lvl, dot in (("All", "🌐 All (incl. holidays)"),
                         ("Low", "🟡 Low+"),
                         ("Medium", "🟠 Med+"),
                         ("High", "🔴 High only")):
            a = QAction(dot, self.menu, checkable=True)
            a.setChecked(self.settings.get("min_impact", "All") == lvl)
            a.triggered.connect(lambda _=False, lv=lvl: self.set_min_impact(lv))
            igrp.addAction(a)
            filt.addAction(a)

        # News filter: currencies
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

        # Left-click behaviour: panel (with Close + Quit buttons) or menu
        lcm = self.menu.addMenu("Left-click icon")
        lgrp = QActionGroup(self.menu)
        lgrp.setExclusive(True)
        for val, label in (("panel", "Open panel (has Close + Quit)"),
                           ("menu", "Open menu")):
            a = QAction(label, self.menu, checkable=True)
            a.setChecked(self.settings.get("left_click_action", "panel") == val)
            a.triggered.connect(lambda _=False, v=val: self.set_left_click(v))
            lgrp.addAction(a)
            lcm.addAction(a)

        self.menu.addSeparator()
        tm = QAction(
            "Emphasise: market time" if self.settings.get("time_mode") != "market_local"
            else "Emphasise: my laptop time",
            self.menu,
        )
        tm.triggered.connect(self.toggle_time_mode)
        self.menu.addAction(tm)
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

        hd = QAction("Start hidden in tray", self.menu, checkable=True)
        hd.setChecked(bool(self.settings.get("start_hidden", False)))
        hd.triggered.connect(lambda checked: self.set_start_hidden(bool(checked)))
        self.menu.addAction(hd)

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

    def select_market(self, mid: str):
        self.settings["selected_market"] = mid
        self._alerted_key = None
        self._save()
        self._build_menu()
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

    def toggle_time_mode(self):
        # Both clocks always shown; this flips emphasis only.
        self.settings["time_mode"] = (
            "local" if self.settings.get("time_mode") == "market_local" else "market_local"
        )
        self._save()
        self._build_menu()
        self.tick()

    def set_min_impact(self, lvl: str):
        self.settings["min_impact"] = lvl
        self._save()
        self._build_menu()
        self.tick()

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

    def set_start_hidden(self, on: bool):
        self.settings["start_hidden"] = bool(on)
        self._save()
        self._build_menu()

    def set_autostart_enabled(self, on: bool):
        """Toggle login autostart.

        Packaged install: a system entry in /etc/xdg/autostart is ON by
        default; switching off writes a per-user Hidden=true override
        (XDG spec — no sudo needed). Dev checkout: writes a real user entry.
        """
        from config import SYSTEM_AUTOSTART_PATH
        try:
            os.makedirs(os.path.dirname(USER_AUTOSTART_PATH), exist_ok=True)
            if on:
                # Remove any Hidden=true override so the entry applies again.
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
                    # Disable the system entry for this user only.
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
        # 1) finished version check
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

        # 2) install progress
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
        nxt = calendar_api.next_event(
            events, self.settings["currencies"], self.settings["min_impact"], now_utc
        )
        label = tray_label_text(self.selected, nxt, self.settings, now_utc)
        theme = self.settings.get("theme", "system")
        is_open = bool(self.selected["is_open"])
        # Cache icon: rebuilding the pixmap every second causes flicker + CPU
        # spikes that can hang Cinnamon. Only rebuild when something changed.
        if (label != self._last_tray_label or is_open != self._last_tray_state
                or theme != self._last_tray_theme):
            try:
                self.tray.setIcon(make_tray_icon(label, is_open, theme))
                self._last_tray_label, self._last_tray_state, self._last_tray_theme = label, is_open, theme
            except Exception:
                pass
        m = self.selected["market"]
        cd = engine.format_signed_countdown(
            self.selected["countdown"], is_open, include_seconds=True)
        yours = now_utc.astimezone().strftime("%H:%M %Z")
        tip = (f"{m['name']} {'● OPEN' if is_open else '○ CLOSED'}\n"
               f"{cd} until {'close' if is_open else 'open'}\n"
               f"Market {self.selected['now_local'].strftime('%H:%M %Z')} • Yours {yours}")
        if nxt and nxt.get("_dt"):
            try:
                tip += f"\nNext: {calendar_api.event_countdown_line(nxt, now_utc)}"
            except Exception:
                pass
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
        # fire ONCE per transition when entering the pre-alert window
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
        """Clean shutdown: stop timers, remove tray icon, quit event loop."""
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
        # Left-click = user setting (panel by default; panel has Close + Quit).
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
            pass  # right-click menu is handled by Qt via setContextMenu

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
        # Place near cursor but always fully on-screen (never off-edge).
        try:
            self.panel.adjustSize()
            screen = self.app.primaryScreen()
            avail = screen.availableGeometry() if screen else self.app.primaryScreen().geometry()
            c = QCursor.pos()
            w, h = max(self.panel.width(), 344), max(self.panel.height(), 200)
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
