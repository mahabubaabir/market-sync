"""Market Sync — Material UI frosted-glass countdown + news for Linux desktops.

Implements the Market Sync Design System v2.0 (System_Design/DESIGN_SYSTEM.md):
  - Window: 410px, radius 14, Tool + Frameless + StaysOnTop, translucent glass
  - 2-column landmark market cards (82px): badge, name + local time, big signed
    countdown, OPEN/CLOSED pill, mini progress ring
  - Brand bar (32px): logo, MARKET SYNC, drawer toggle, alerts bell, settings
  - Up Next drawer: multi-select impact chips, news rows with impact + currency
    capsules, date bar
  - Cinnamon applet bridge: writes ~/.cache/market-sync/panel_status.json and
    serves IPC (toggle/show/hide/preferences/quit) on QLocalServer.
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
        QSizePolicy,
    )
    from PyQt6.QtGui import (
        QIcon, QPixmap, QPainter, QColor, QFont, QAction, QActionGroup,
        QFontMetrics, QPen, QCursor,
    )
    from PyQt6.QtCore import QTimer, Qt, QRectF, QEvent, pyqtSignal
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
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
    LAUNCHER_PATH, APP_NAME, APP_VERSION, APP_AUTHOR, CACHE_DIR,
    UPDATE_CHECK_HOURS, IPC_SOCKET_NAME, APPLET_UUID, PANEL_STATUS_PATH,
)
import markets as engine
import calendar_api
import updater
from notifier import notify, AlertTracker

GREEN = "#30d158"   # neon active green (dark glass)
RED = "#ef4444"     # high impact / closed accents
CYAN = "#38bdf8"    # brand cyan

ASSETS_DIR = os.path.join(app_dir(), "assets")

# ----------------------------------------------------------------- v2.0 tokens
# Material UI frosted glass: translucent surfaces, neon active highlights,
# crisp silvery muted off-states. Purple/Mint follow the same token shape.
THEMES = {
    "dark": {
        "bg": "rgba(16, 20, 30, 0.88)",
        "border": "rgba(255, 255, 255, 0.08)",
        "card": "rgba(28, 34, 48, 0.70)",
        "card_active": "rgba(20, 42, 30, 0.65)",
        "card_border": "rgba(255, 255, 255, 0.06)",
        "card_border_active": "#30d158",
        "card_border_hover": "rgba(255, 255, 255, 0.16)",
        "text": "#f1f5f9",
        "secondary": "#94a3b8",
        "muted": "#64748b",
        "green": "#30d158",
        "cyan": "#38bdf8",
        "closed": "#cbd5e1",
        "divider": "rgba(255, 255, 255, 0.08)",
        "ring_track": "rgba(255, 255, 255, 0.12)",
        "row_bg": "rgba(255, 255, 255, 0.03)",
        "row_border": "rgba(255, 255, 255, 0.04)",
        "input_bg": "rgba(255, 255, 255, 0.06)",
        "input_hover": "rgba(255, 255, 255, 0.10)",
        "input_selected": "rgba(56, 189, 248, 0.22)",
        "input_border": "rgba(255, 255, 255, 0.12)",
        "input_border_selected": "#38bdf8",
        "badge_bg": "rgba(34, 40, 58, 0.85)",
        "solid_bg": "#12161f",
        "tray_text": "#ffffff",
        "pill_open_bg": "rgba(48, 209, 88, 0.18)", "pill_open_text": "#30d158",
        "pill_closed_bg": "rgba(203, 213, 225, 0.10)", "pill_closed_text": "#cbd5e1",
    },
    "light": {
        "bg": "rgba(250, 252, 255, 0.88)",
        "border": "rgba(0, 0, 0, 0.08)",
        "card": "rgba(255, 255, 255, 0.85)",
        "card_active": "rgba(236, 253, 245, 0.90)",
        "card_border": "rgba(0, 0, 0, 0.06)",
        "card_border_active": "#16a34a",
        "card_border_hover": "rgba(0, 0, 0, 0.14)",
        "text": "#0f172a",
        "secondary": "#475569",
        "muted": "#94a3b8",
        "green": "#16a34a",
        "cyan": "#0284c7",
        "closed": "#334155",
        "divider": "rgba(0, 0, 0, 0.08)",
        "ring_track": "rgba(0, 0, 0, 0.10)",
        "row_bg": "rgba(0, 0, 0, 0.03)",
        "row_border": "rgba(0, 0, 0, 0.05)",
        "input_bg": "rgba(0, 0, 0, 0.04)",
        "input_hover": "rgba(0, 0, 0, 0.07)",
        "input_selected": "rgba(2, 132, 199, 0.16)",
        "input_border": "rgba(0, 0, 0, 0.12)",
        "input_border_selected": "#0284c7",
        "badge_bg": "rgba(241, 245, 249, 0.90)",
        "solid_bg": "#f7f9fc",
        "tray_text": "#0f172a",
        "pill_open_bg": "rgba(22, 163, 74, 0.14)", "pill_open_text": "#16a34a",
        "pill_closed_bg": "rgba(51, 65, 85, 0.10)", "pill_closed_text": "#334155",
    },
    "dark_purple": {
        "bg": "rgba(24, 19, 36, 0.88)",
        "border": "rgba(255, 255, 255, 0.08)",
        "card": "rgba(38, 31, 54, 0.70)",
        "card_active": "rgba(28, 44, 34, 0.65)",
        "card_border": "rgba(255, 255, 255, 0.06)",
        "card_border_active": "#35c48d",
        "card_border_hover": "rgba(255, 255, 255, 0.16)",
        "text": "#ece7f6",
        "secondary": "#a99fc4",
        "muted": "#7d7396",
        "green": "#35c48d",
        "cyan": "#a78bfa",
        "closed": "#cfc7e2",
        "divider": "rgba(255, 255, 255, 0.08)",
        "ring_track": "rgba(255, 255, 255, 0.12)",
        "row_bg": "rgba(255, 255, 255, 0.03)",
        "row_border": "rgba(255, 255, 255, 0.04)",
        "input_bg": "rgba(255, 255, 255, 0.06)",
        "input_hover": "rgba(255, 255, 255, 0.10)",
        "input_selected": "rgba(167, 139, 250, 0.22)",
        "input_border": "rgba(255, 255, 255, 0.12)",
        "input_border_selected": "#a78bfa",
        "badge_bg": "rgba(46, 36, 66, 0.85)",
        "solid_bg": "#1a1428",
        "tray_text": "#ece7f6",
        "pill_open_bg": "rgba(53, 196, 141, 0.18)", "pill_open_text": "#35c48d",
        "pill_closed_bg": "rgba(207, 199, 226, 0.10)", "pill_closed_text": "#cfc7e2",
    },
    "mint_light": {
        "bg": "rgba(244, 251, 247, 0.88)",
        "border": "rgba(16, 43, 35, 0.08)",
        "card": "rgba(255, 255, 255, 0.85)",
        "card_active": "rgba(226, 250, 238, 0.90)",
        "card_border": "rgba(16, 43, 35, 0.06)",
        "card_border_active": "#10b981",
        "card_border_hover": "rgba(16, 43, 35, 0.14)",
        "text": "#0f2a1f",
        "secondary": "#3f6b58",
        "muted": "#7fa392",
        "green": "#10b981",
        "cyan": "#0d9488",
        "closed": "#33594a",
        "divider": "rgba(16, 43, 35, 0.08)",
        "ring_track": "rgba(16, 43, 35, 0.10)",
        "row_bg": "rgba(16, 43, 35, 0.03)",
        "row_border": "rgba(16, 43, 35, 0.05)",
        "input_bg": "rgba(16, 43, 35, 0.05)",
        "input_hover": "rgba(16, 43, 35, 0.08)",
        "input_selected": "rgba(16, 185, 129, 0.18)",
        "input_border": "rgba(16, 43, 35, 0.12)",
        "input_border_selected": "#10b981",
        "badge_bg": "rgba(226, 245, 234, 0.90)",
        "solid_bg": "#f2faf5",
        "tray_text": "#0f2a1f",
        "pill_open_bg": "rgba(16, 185, 129, 0.14)", "pill_open_text": "#059669",
        "pill_closed_bg": "rgba(51, 89, 74, 0.10)", "pill_closed_text": "#33594a",
    },
    "mint_dark": {
        "bg": "rgba(18, 29, 24, 0.88)",
        "border": "rgba(255, 255, 255, 0.08)",
        "card": "rgba(31, 45, 38, 0.70)",
        "card_active": "rgba(22, 48, 36, 0.65)",
        "card_border": "rgba(255, 255, 255, 0.06)",
        "card_border_active": "#35c48d",
        "card_border_hover": "rgba(255, 255, 255, 0.16)",
        "text": "#e3f0e9",
        "secondary": "#9fc0af",
        "muted": "#6f8f7f",
        "green": "#35c48d",
        "cyan": "#2dd4bf",
        "closed": "#c6dccf",
        "divider": "rgba(255, 255, 255, 0.08)",
        "ring_track": "rgba(255, 255, 255, 0.12)",
        "row_bg": "rgba(255, 255, 255, 0.03)",
        "row_border": "rgba(255, 255, 255, 0.04)",
        "input_bg": "rgba(255, 255, 255, 0.06)",
        "input_hover": "rgba(255, 255, 255, 0.10)",
        "input_selected": "rgba(53, 196, 141, 0.22)",
        "input_border": "rgba(255, 255, 255, 0.12)",
        "input_border_selected": "#35c48d",
        "badge_bg": "rgba(36, 54, 44, 0.85)",
        "solid_bg": "#121d18",
        "tray_text": "#e3f0e9",
        "pill_open_bg": "rgba(53, 196, 141, 0.18)", "pill_open_text": "#35c48d",
        "pill_closed_bg": "rgba(198, 220, 207, 0.10)", "pill_closed_text": "#c6dccf",
    },
}
THEMES["system"] = THEMES["dark"]  # placeholder; resolve_theme() maps it

THEME_ORDER = ["system", "light", "dark", "dark_purple", "mint_light", "mint_dark"]
THEME_LABELS = {
    "system": "System", "light": "Light", "dark": "Dark",
    "dark_purple": "Dark Purple", "mint_light": "Mint Light", "mint_dark": "Mint Dark",
}
THEME_ICON = {
    "system": "🖥️", "light": "☀️", "dark": "🌙",
    "dark_purple": "🟣", "mint_light": "🌿", "mint_dark": "🍃",
}

# v2.0 news-impact capsules (dark + light variants)
IMPACT_STYLE = {
    "High": {
        "dark": ("#ef4444", "rgba(239, 68, 68, 0.18)", "rgba(239, 68, 68, 0.40)"),
        "light": ("#b91c1c", "#fee2e2", "#fca5a5"),
    },
    "Medium": {
        "dark": ("#f97316", "rgba(249, 115, 22, 0.18)", "rgba(249, 115, 22, 0.40)"),
        "light": ("#c2410c", "#ffedd5", "#fdba74"),
    },
    "Low": {
        "dark": ("#eab308", "rgba(234, 179, 8, 0.18)", "rgba(234, 179, 8, 0.40)"),
        "light": ("#854d0e", "#fef9c3", "#fde047"),
    },
    "Holiday": {
        "dark": ("#a1a1aa", "rgba(161, 161, 170, 0.15)", "rgba(161, 161, 170, 0.30)"),
        "light": ("#52525b", "#f4f4f5", "#d4d4d8"),
    },
}
IMPACT_SHORT = {"High": "HIGH", "Medium": "MED", "Low": "LOW", "Holiday": "HOL"}
PILL_DOT = {"High": "🔴", "Medium": "🟠", "Low": "🟡", "Holiday": "🟣"}

# v2.0 currency accent palette
CURRENCY_COLORS = {
    "USD": "#38bdf8", "EUR": "#10b981", "GBP": "#c084fc", "JPY": "#f87171",
    "AUD": "#fb923c", "CAD": "#e879f9", "CHF": "#e2e8f0", "NZD": "#34d399",
}

_UNSET = object()


def resolve_theme(want: str) -> str:
    if want in THEMES and want != "system":
        return want
    if HAS_QT:
        try:
            app = QApplication.instance()
            if app is not None:
                scheme = app.styleHints().colorScheme()
                if scheme == Qt.ColorScheme.Dark:
                    return "dark"
                if scheme == Qt.ColorScheme.Light:
                    return "light"
        except Exception:
            pass
    return "dark"


def qcolor(s: str) -> "QColor":
    """Parse '#rrggbb' or 'rgba(r, g, b, a)' (float or int alpha) to QColor.

    Note: QColor() rejects float-alpha rgba() strings that QSS accepts,
    silently producing black — this normalises them.
    """
    try:
        if s.startswith("rgba"):
            inside = s[s.index("(") + 1:s.index(")")]
            parts = [p.strip() for p in inside.split(",")]
            r, g, b = int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
            a = float(parts[3])
            if a <= 1.0:
                a = int(round(a * 255))
            return QColor(r, g, b, int(a))
        return QColor(s)
    except Exception:
        return QColor("#808080")


def app_font(px: int, weight: QFont.Weight = QFont.Weight.Normal) -> "QFont":
    """Design-system font stack: Inter -> Noto Sans -> Ubuntu -> Sans."""
    f = QFont("Inter")
    try:
        f.setFamilies(["Inter", "Noto Sans", "Ubuntu", "DejaVu Sans", "Sans"])
    except Exception:
        pass
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def mono_font(px: int, weight: QFont.Weight = QFont.Weight.Bold) -> "QFont":
    f = QFont("JetBrains Mono")
    try:
        f.setFamilies(["JetBrains Mono", "Fira Code", "DejaVu Sans Mono", "monospace"])
    except Exception:
        pass
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def stylesheet(t: dict) -> str:
    return f"""
QFrame#PanelRoot {{
    background: {t['bg']};
    border: 1px solid {t['border']};
    border-radius: 14px;
}}
QLabel {{ color: {t['text']}; background: transparent; }}
QLabel.caption {{ color: {t['secondary']}; font-size: 10px; font-weight: 700; letter-spacing: 1.0px; }}
QFrame#MarketCard {{ border-radius: 10px; }}
QPushButton.bar {{ background: transparent; color: {t['secondary']}; border: none; border-radius: 6px; padding: 2px 6px; font-size: 13px; }}
QPushButton.bar:hover {{ color: {t['text']}; background: {t['input_hover']}; }}
QPushButton.ghost {{ background: transparent; color: {t['secondary']}; border: 1px solid {t['input_border']}; border-radius: 7px; padding: 4px 10px; font-size: 12px; }}
QPushButton.ghost:hover {{ color: {t['text']}; border-color: {t['input_border_selected']}; }}
QPushButton.quitbtn {{ background: #ef4444; color: white; border: none; border-radius: 7px; padding: 5px 12px; font-size: 12px; font-weight: 800; }}
QPushButton.quitbtn:hover {{ background: #dc2626; }}
QPushButton.primary {{ background: {t['cyan']}; color: white; border: none; border-radius: 7px; padding: 6px 18px; font-weight: 800; font-size: 12px; }}
QPushButton[seg="1"] {{ background: {t['input_bg']}; color: {t['secondary']}; border: 1px solid {t['input_border']}; border-radius: 7px; padding: 3px 10px; font-size: 11px; font-weight: 600; }}
QPushButton[seg="1"]:hover {{ background: {t['input_hover']}; }}
QPushButton[seg="1"]:checked {{ background: {t['input_selected']}; border-color: {t['input_border_selected']}; color: {t['text']}; }}
QCheckBox {{ color: {t['text']}; font-size: 12px; background: transparent; spacing: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['input_hover']}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMenu {{ background: {t['solid_bg']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QMenu::item:selected {{ background: {t['input_selected']}; }}
QDialog {{ background: {t['solid_bg']}; }}
QComboBox {{ background: {t['input_bg']}; color: {t['text']}; border: 1px solid {t['input_border']}; border-radius: 6px; padding: 3px 10px; min-width: 100px; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {t['solid_bg']}; color: {t['text']}; selection-background-color: {t['input_selected']}; }}
"""


# ---------------------------------------------------------------- tray helpers

def _panel_markup(statuses, settings, now_utc) -> tuple[str, str, bool]:
    """Build the applet payload: (plain_label, pango_markup, any_open).

    Follows the spec: bright bold green ● for open sessions, silvery ○ for
    closed sessions, compact signed countdowns (+04:05 / -00:35).
    """
    layout = settings.get("tray_layout", "compact")
    time_as = settings.get("tray_time_as", "countdown")
    sessions = settings.get("tray_sessions", "active_and_next")
    is_12h = settings.get("time_format", "24h") == "12h"
    md = settings.get("market_display", {})

    def eligible(s):
        return md.get(s["market"]["id"], "panel") == "panel"

    def token(s):
        m = s["market"]
        name = m["symbol"] if layout == "compact" else m["name"]
        if time_as == "local_time":
            val = engine.format_local_clock(s["now_local"], is_12h)
        else:
            val = engine.format_signed_countdown(s["countdown"], s["is_open"])
        return name, val, s["is_open"]

    opens = [s for s in statuses if s["is_open"] and eligible(s)]
    closed = sorted(
        [s for s in statuses if not s["is_open"] and eligible(s)],
        key=lambda x: x["countdown"].total_seconds())
    if sessions == "active_only":
        chosen = opens if opens else closed[:1]
    elif sessions == "active_and_next":
        chosen = opens + closed[:1]
    else:
        chosen = opens + closed

    toks = [token(s) for s in chosen]
    if not toks:
        toks = [token(s) for s in statuses[:1]]
    plain = "  ".join(f"{sym} {val}" for sym, val, _ in toks)
    parts = []
    for sym, val, op in toks:
        if op:
            parts.append(f'<span weight="bold" foreground="#30d158">● {sym} {val}</span>')
        else:
            parts.append(f'<span foreground="#cbd5e1">○ {sym} {val}</span>')
    markup = "  ".join(parts)
    any_open = any(s["is_open"] for s in statuses)
    return plain, markup, any_open


def _write_panel_status(statuses, settings, now_utc, last: dict) -> dict:
    """Write ~/.cache/market-sync/panel_status.json for the Cinnamon applet."""
    plain, markup, any_open = _panel_markup(statuses, settings, now_utc)
    is_12h = settings.get("time_format", "24h") == "12h"
    lines = []
    for s in statuses:
        m = s["market"]
        state = "OPEN" if s["is_open"] else "CLOSED"
        cd = engine.format_signed_countdown(s["countdown"], s["is_open"])
        loc = engine.format_local_clock(s["now_local"], is_12h)
        lines.append(f"{m['name']} ({m['symbol']}): {state} ({cd}) • {loc}")
    payload = {
        "label": plain or APP_NAME,
        "markup": markup or APP_NAME,
        "tooltip": "\n".join(lines),
        "is_open": any_open,
    }
    if payload != last:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = PANEL_STATUS_PATH + ".tmp"
            import json as _json
            with open(tmp, "w", encoding="utf-8") as f:
                _json.dump(payload, f)
            os.replace(tmp, PANEL_STATUS_PATH)
        except Exception:
            pass
    return payload


def tray_label_text(selected: dict, nxt, settings: dict, now_utc) -> str:
    """Single-market tray text: 'LON +02:14:33 14:32' (+ next event badge)."""
    m = selected["market"]
    is_12h = settings.get("time_format", "24h") == "12h"
    parts: list[str] = []
    if settings.get("show_symbol", True):
        parts.append(m["symbol"])
    if settings.get("show_countdown", True):
        parts.append(engine.format_signed_countdown(
            selected["countdown"], selected["is_open"], include_seconds=True))
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
    p.setBrush(QColor(GREEN if is_open else "#71717a"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 8, 12, 12)
    p.setPen(QColor(t["tray_text"]))
    p.drawText(20, 0, w - 20, 28, Qt.AlignmentFlag.AlignVCenter, text)
    p.end()
    return QIcon(pm)


def make_tray_icon_multi(segments: list, theme: str) -> "QIcon":
    """Top panel style: '● LON +04:05  ○ NYC -00:35' (bright/dim)."""
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
        p.setPen(QColor(t["tray_text"] if is_open else t["closed"]))
        adv = fm.horizontalAdvance(label)
        p.drawText(x, 0, adv + 4, 28, Qt.AlignmentFlag.AlignVCenter, label)
        x += adv + fm.horizontalAdvance(sep)
    p.end()
    return QIcon(pm)


def make_tray_logo_icon(any_open: bool, size: int = 24) -> "QIcon":
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo_path = os.path.join(ASSETS_DIR, "icon.svg")
    if HAS_SVG and os.path.exists(logo_path):
        r = QSvgRenderer(logo_path)
        r.render(p, QRectF(2, 2, size - 4, size - 4))
    else:
        p.setBrush(QColor(CYAN))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, size - 4, size - 4)
    p.setBrush(QColor(GREEN if any_open else "#71717a"))
    p.setPen(QPen(QColor("#0f121a"), 1.2))
    p.drawEllipse(size - 9, size - 9, 7, 7)
    p.end()
    return QIcon(pm)


def _next_nyse_holiday_line(now_utc=None) -> str:
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
        """Circular badge with the market's landmark vector (26px in cards)."""

        def __init__(self, landmark: str, symbol: str, size: int = 26):
            super().__init__()
            self._landmark = landmark
            self._symbol = symbol
            self._size = size
            self.setFixedSize(size, size)
            self._bg = QColor("rgba(34, 40, 58, 0.85)")
            self._fg = QColor("#f1f5f9")

        def set_landmark(self, landmark: str, symbol: str):
            if landmark != self._landmark or symbol != self._symbol:
                self._landmark, self._symbol = landmark, symbol
                self.update()

        def set_theme(self, t: dict):
            self._bg = qcolor(t["badge_bg"])
            self._fg = QColor(t["text"])
            self.update()

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._bg)
            p.drawEllipse(0, 0, self._size, self._size)
            path = _svg_path(self._landmark)
            if HAS_SVG and os.path.exists(path):
                r = QSvgRenderer(path)
                inset = max(5, self._size // 5)
                r.render(p, QRectF(inset, inset, self._size - 2 * inset, self._size - 2 * inset))
            else:
                p.setPen(self._fg)
                p.setFont(app_font(max(8, self._size // 3), QFont.Weight.Bold))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._symbol[:3])
            p.end()
else:
    class LandmarkBadge:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class MiniRingTimer(QWidget):
        """20px progress ring: neon green arc while open, faint track closed."""

        def __init__(self, size: int = 20):
            super().__init__()
            self.setFixedSize(size, size)
            self._frac = 0.0
            self._open = False
            self._track = QColor("rgba(255, 255, 255, 0.12)")
            self._arc = QColor(GREEN)

        def set_state(self, frac: float, is_open: bool, t: dict):
            self._frac = min(1.0, max(0.0, frac))
            self._open = is_open
            self._track = qcolor(t["ring_track"])
            self._arc = qcolor(t["green"])
            self.update()

        def paintEvent(self, _ev):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            w = 2.8
            rect = QRectF(w, w, self.width() - 2 * w, self.height() - 2 * w)
            p.setPen(QPen(self._track, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 0, 360 * 16)
            if self._open:
                p.setPen(QPen(self._arc, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        """Design System v2.0 market card (82px).

        Upper row: landmark badge • name • local time.
        Lower row: big signed countdown • OPEN/CLOSED pill • 20px ring.
        Active card: green illuminated border + green-tinted glass.
        """

        clicked = pyqtSignal(str)

        def __init__(self, market: dict, parent: QWidget | None = None):
            super().__init__(parent)
            self.market = market
            self.setObjectName("MarketCard")
            self.setFixedHeight(82)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            lay = QVBoxLayout(self)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(4)

            top = QHBoxLayout()
            top.setSpacing(6)
            self.badge = LandmarkBadge(market.get("landmark", "london"), market["symbol"], 26)
            top.addWidget(self.badge)
            self.name_label = QLabel(market["name"])
            self.name_label.setFont(app_font(13, QFont.Weight.DemiBold))
            top.addWidget(self.name_label)
            top.addStretch(1)
            self.time_label = QLabel("00:00")
            self.time_label.setFont(app_font(11, QFont.Weight.Medium))
            top.addWidget(self.time_label)
            lay.addLayout(top)

            bot = QHBoxLayout()
            bot.setSpacing(6)
            self.cd_label = QLabel("+00:00")
            self.cd_label.setFont(mono_font(22))
            bot.addWidget(self.cd_label)
            bot.addStretch(1)
            self.pill = QLabel("OPEN")
            self.pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.pill.setFixedSize(56, 18)
            self.pill.setFont(app_font(9, QFont.Weight.Bold))
            bot.addWidget(self.pill)
            self.ring = MiniRingTimer(20)
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
            self.time_label.setStyleSheet(f"color: {t['secondary']};")
            self.cd_label.setText(engine.format_signed_countdown(status["countdown"], is_open))

            if is_open and brighten:
                self.cd_label.setStyleSheet(
                    f"color: {t['green']}; font-family: monospace; font-weight: 800;")
                self.name_label.setStyleSheet(f"color: {t['text']};")
                bg, bd, bw = t["card_active"], t["card_border_active"], "1.5px"
            elif is_open:
                self.cd_label.setStyleSheet(f"color: {t['text']}; font-family: monospace;")
                self.name_label.setStyleSheet(f"color: {t['text']};")
                bg, bd, bw = t["card"], t["card_border_hover"], "1px"
            elif brighten:
                # muted off-state: readable silvery slate, not dead gray
                self.cd_label.setStyleSheet(f"color: {t['closed']}; font-family: monospace;")
                self.name_label.setStyleSheet(f"color: {t['text']};")
                bg, bd, bw = t["card"], t["card_border"], "1px"
            else:
                self.cd_label.setStyleSheet(f"color: {t['text']}; font-family: monospace;")
                self.name_label.setStyleSheet(f"color: {t['text']};")
                bg, bd, bw = t["card"], t["card_border"], "1px"

            if is_open:
                self.pill.setText("OPEN")
                self.pill.setStyleSheet(
                    f"background: {t['pill_open_bg']}; color: {t['pill_open_text']};"
                    "border-radius: 9px; font-weight: bold;")
            else:
                self.pill.setText("CLOSED")
                self.pill.setStyleSheet(
                    f"background: {t['pill_closed_bg']}; color: {t['pill_closed_text']};"
                    "border-radius: 9px; font-weight: bold;")

            if selected:
                bd, bw = t["input_border_selected"], "1.5px"
            self.setStyleSheet(
                f"QFrame#MarketCard {{ background: {bg};"
                f" border: {bw} solid {bd}; border-radius: 10px; }}"
                f"QFrame#MarketCard:hover {{ border: 1px solid {t['card_border_hover']}; }}")
            self.ring.set_state(status.get("progress", 0.0), is_open, t)
else:
    class MarketCardWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class NewsRowWidget(QFrame):
        """Design System v2.0 news row: relative time • impact • currency • title."""

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self.setFixedHeight(30)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(8, 2, 8, 2)
            lay.setSpacing(7)

            self.rel_label = QLabel("--")
            self.rel_label.setFont(mono_font(11))
            self.rel_label.setFixedWidth(56)
            self.rel_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(self.rel_label)

            self.imp_pill = QLabel("LOW")
            self.imp_pill.setFont(app_font(8, QFont.Weight.Bold))
            self.imp_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.imp_pill.setFixedSize(40, 17)
            lay.addWidget(self.imp_pill)

            self.cur_pill = QLabel("USD")
            self.cur_pill.setFont(app_font(9, QFont.Weight.Bold))
            self.cur_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cur_pill.setFixedSize(40, 17)
            lay.addWidget(self.cur_pill)

            self.title_label = QLabel("")
            self.title_label.setFont(app_font(11))
            lay.addWidget(self.title_label, 1)

        def update_data(self, ev: dict, theme: dict, theme_name: str, now_utc):
            is_dark = theme_name not in ("light", "mint_light")
            self.setStyleSheet(
                f"QFrame {{ background: {theme['row_bg']};"
                f" border: 1px solid {theme['row_border']}; border-radius: 6px; }}")
            dt = ev.get("_dt")
            self.rel_label.setText(calendar_api.relative_time(dt, now_utc) if dt else "--")
            self.rel_label.setStyleSheet(f"color: {theme['secondary']};")

            imp = ev.get("impact", "Low")
            variant = IMPACT_STYLE.get(imp, IMPACT_STYLE["Low"])["dark" if is_dark else "light"]
            fg, bg, border = variant
            self.imp_pill.setText(IMPACT_SHORT.get(imp, imp[:3].upper()))
            self.imp_pill.setStyleSheet(
                f"background: {bg}; color: {fg}; border: 1px solid {border};"
                "border-radius: 4px; font-weight: bold;")

            cur = (ev.get("currency") or ev.get("country") or "").upper()
            c_fg = CURRENCY_COLORS.get(cur, theme["cyan"])
            self.cur_pill.setText(cur[:3])
            self.cur_pill.setStyleSheet(
                f"background: {theme['input_bg']}; color: {c_fg};"
                "border: 1px solid " + theme["row_border"] + ";" "border-radius: 4px; font-weight: bold;")

            self.title_label.setText(ev.get("title", "Event"))
            self.title_label.setStyleSheet(f"color: {theme['text']};")
else:
    class NewsRowWidget:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


if HAS_QT:
    class UpNextDrawer(QFrame):
        """Up Next drawer: header + impact chips + rows + date bar (v2.0)."""

        def __init__(self, controller: "TrayController"):
            super().__init__()
            self.c = controller
            self._sig: list | None = None
            self._rows: list = []

            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

            # header: UP NEXT + chips
            header = QFrame()
            header.setFixedHeight(30)
            hl = QHBoxLayout(header)
            hl.setContentsMargins(4, 2, 4, 2)
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
            lay.addWidget(header)

            # scrollable rows (spec: 175px)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(175)
            inner = QWidget()
            self.rows_layout = QVBoxLayout(inner)
            self.rows_layout.setSpacing(4)
            self.rows_layout.setContentsMargins(4, 2, 4, 4)
            self.rows_layout.addStretch(1)
            scroll.setWidget(inner)
            lay.addWidget(scroll)

            # bottom bar: date pill + collapse
            datebar = QFrame()
            datebar.setFixedHeight(28)
            dl = QHBoxLayout(datebar)
            dl.setContentsMargins(8, 2, 4, 2)
            self.date_label = QLabel(datetime.now().strftime("%d %b"))
            self.date_label.setFont(app_font(10, QFont.Weight.DemiBold))
            dl.addWidget(self.date_label)
            dl.addStretch(1)
            self.collapse_btn = QPushButton("▴")
            self.collapse_btn.setProperty("class", "bar")
            self.collapse_btn.setFixedSize(24, 20)
            self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.collapse_btn.setToolTip("Collapse Up Next")
            self.collapse_btn.clicked.connect(lambda: self.c.set_drawer_expanded(False))
            dl.addWidget(self.collapse_btn)
            lay.addWidget(datebar)

        # -- chips (multi-select)
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

        # -- content
        def update_events(self, shown: list, now_utc):
            t = THEMES[self.c.panel._theme]
            name = self.c.panel._theme
            self.date_label.setText(
                datetime.now().strftime("%d %b") + "  •  " +
                engine.format_local_clock(now_utc.astimezone(),
                                          self.c.settings.get("time_format") == "12h"))
            self.date_label.setStyleSheet(f"color: {t['secondary']};")
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
                    lab.setStyleSheet(f"color: {t['muted']}; font-size: 11px;")
                    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.rows_layout.insertWidget(0, lab)
                    self._rows = [lab]
                for e in shown:
                    row = NewsRowWidget()
                    row.update_data(e, t, name, now_utc)
                    self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
                    self._rows.append(row)
            else:
                for row, e in zip(self._rows, shown):
                    if hasattr(row, "update_data"):
                        row.update_data(e, t, name, now_utc)
else:
    class UpNextDrawer:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


class SessionPanel(QWidget):
    """Market Sync v2.0 frosted-glass dropdown (410px, radius 14).

    Shell is a QFrame#PanelRoot container (QSS backgrounds paint reliably on
    QFrame — a bare custom QWidget would silently skip them).
    """

    def __init__(self, controller: "TrayController"):
        super().__init__()
        self.c = controller
        self._theme = "dark"
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(410)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.root = QFrame()
        self.root.setObjectName("PanelRoot")
        outer.addWidget(self.root)

        root = QVBoxLayout(self.root)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 1. market cards grid (2 columns, v0.2 order)
        self.cards: dict[str, MarketCardWidget] = {}
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        for m in MARKETS:
            card = MarketCardWidget(m)
            card.clicked.connect(self.c.select_market)
            self.cards[m["id"]] = card
        root.addLayout(self.grid)
        self.rebuild_grid()

        # 2. brand bar (32px): logo + MARKET SYNC + drawer + bell + gear + close
        brand = QHBoxLayout()
        brand.setSpacing(4)
        self.logo = QLabel()
        self.logo.setFixedSize(20, 20)
        logo_pm = QPixmap(20, 20)
        logo_pm.fill(Qt.GlobalColor.transparent)
        logo_path = os.path.join(ASSETS_DIR, "icon.svg")
        if HAS_SVG and os.path.exists(logo_path):
            r = QSvgRenderer(logo_path)
            p = QPainter(logo_pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r.render(p)
            p.end()
        self.logo.setPixmap(logo_pm)
        brand.addWidget(self.logo)
        self.title = QLabel("MARKET SYNC")
        tf = app_font(9, QFont.Weight.Bold)
        try:
            tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        except Exception:
            pass
        self.title.setFont(tf)
        brand.addWidget(self.title)
        brand.addStretch(1)

        self.drawer_btn = QPushButton("▾")
        self.drawer_btn.setProperty("class", "bar")
        self.drawer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drawer_btn.setToolTip("Expand / collapse Up Next")
        self.drawer_btn.clicked.connect(self.toggle_drawer)
        brand.addWidget(self.drawer_btn)

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
        self.close_btn.setToolTip("Hide panel (app keeps running)")
        self.close_btn.clicked.connect(self.hide)
        brand.addWidget(self.close_btn)
        root.addLayout(brand)

        # 3. Up Next drawer
        self.drawer = UpNextDrawer(controller)
        self.drawer.setVisible(bool(controller.settings.get("news_drawer_expanded", True)))
        root.addWidget(self.drawer)
        self._sync_drawer_btn()

        self.apply_theme()

    # -- grid routing (none hides a card, popup keeps it panel-only)
    def rebuild_grid(self):
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
                self.grid.addWidget(card, r, 0, 1, 2)
            else:
                self.grid.addWidget(card, r, col)

    # -- drawer state
    def toggle_drawer(self):
        self.c.set_drawer_expanded(not self.drawer.isVisible())

    def set_drawer_expanded(self, expanded: bool):
        self.drawer.setVisible(expanded)
        self._sync_drawer_btn()

    def _sync_drawer_btn(self):
        self.drawer_btn.setText("▴" if self.drawer.isVisible() else "▾")

    # -- focus behaviour (hide when clicking another app)
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
        # chips: impact colors tinted when checked
        base_colors = {"High": "#ef4444", "Medium": "#f97316", "Low": "#eab308"}
        for lvl, b in self.drawer.chips.items():
            base = base_colors[lvl]
            c = QColor(base)
            tint = f"rgba({c.red()}, {c.green()}, {c.blue()}, 46)"
            b.setStyleSheet(
                f"QPushButton {{ background: {t['input_bg']}; color: {t['secondary']};"
                f" border: 1px solid {t['input_border']}; border-radius: 10px;"
                " padding: 2px 8px; font-size: 10px; font-weight: 700; }"
                f"QPushButton:checked {{ color: {base}; border-color: {base}; background: {tint}; }}")
        c = QColor(t["cyan"])
        tint = f"rgba({c.red()}, {c.green()}, {c.blue()}, 46)"
        self.drawer.chip_all.setStyleSheet(
            f"QPushButton {{ background: {t['input_bg']}; color: {t['secondary']};"
            f" border: 1px solid {t['input_border']}; border-radius: 10px;"
            " padding: 2px 10px; font-size: 10px; font-weight: 700; }"
            f"QPushButton:checked {{ color: {t['cyan']}; border-color: {t['cyan']}; background: {tint}; }}")

    def render(self, statuses, selected, news, news_note, now_utc):
        if resolve_theme(self.c.settings.get("theme", "system")) != self._theme:
            self.apply_theme()
        t = THEMES[self._theme]
        sel_id = self.c.settings["selected_market"]
        is_12h = self.c.settings.get("time_format", "24h") == "12h"
        brighten = bool(self.c.settings.get("active_brighten", True))

        for s in statuses:
            mid = s["market"]["id"]
            if mid in self.cards:
                self.cards[mid].update_data(s, t, mid == sel_id, is_12h, brighten)

        self.bell_btn.setText("🔔" if self.c.settings.get("alerts_enabled", True) else "🔕")

        active = list(self.c.settings.get("active_impacts", ["High", "Medium", "Low"]))
        self.drawer.sync_chips(active)
        shown = calendar_api.filter_events(
            news, self.c.settings["currencies"], None, 72, now_utc,
            active_impacts=active)
        self.drawer.update_events(shown[:16], now_utc)


if HAS_QT:
    class PreferencesDialog(QDialog):
        """Design System v2.0 preferences (380px): display card with live
        preview, segments, market routing table, startup, updates, footer."""

        def __init__(self, controller: "TrayController"):
            super().__init__()
            self.c = controller
            s = controller.settings
            self._check_result = _UNSET
            self._t = THEMES[resolve_theme(s.get("theme", "system"))]
            self.setWindowTitle(f"{APP_NAME} — Preferences")
            self.setFixedSize(380, 640)
            self.setStyleSheet(stylesheet(self._t))

            root = QVBoxLayout(self)
            root.setContentsMargins(12, 12, 12, 12)
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
                lab.setFixedWidth(96)
                lab.setFont(app_font(11, QFont.Weight.DemiBold))
                h.addWidget(lab)
                h.addWidget(widget)
                h.addStretch(1)
                form.addLayout(h)

            # ---- launch at login
            self.autostart_chk = QCheckBox("Launch at Login (silent, in tray)")
            self.autostart_chk.setChecked(is_autostart_enabled())
            form.addWidget(self.autostart_chk)

            # ---- display card with live preview
            section("Menu Bar & Top Panel Display")
            self.preview = QLabel("")
            self.preview.setWordWrap(True)
            self.preview.setStyleSheet(
                f"background: {self._t['input_bg']}; border: 1px solid {self._t['input_border']};"
                "border-radius: 10px; padding: 8px 10px; font-size: 12px;")
            form.addWidget(self.preview)

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
            row("Panel Sessions", self.seg_sessions)

            self.standalone_chk = QCheckBox(
                "Show standalone tray icon alongside panel applet")
            self.standalone_chk.setChecked(bool(s.get("show_standalone_tray", True)))
            form.addWidget(self.standalone_chk)

            self.brighten_chk = QCheckBox("Active markets brighten; off sessions dim")
            self.brighten_chk.setChecked(bool(s.get("active_brighten", True)))
            self.brighten_chk.toggled.connect(self._refresh_preview)
            form.addWidget(self.brighten_chk)

            # ---- market tracking table
            section("Market Tracking")
            self.route_segs: dict = {}
            md = s.get("market_display", {})
            for m in MARKETS:
                h = QHBoxLayout()
                lab = QLabel(f"{m['name']} ({m['symbol']})")
                lab.setFixedWidth(130)
                h.addWidget(lab)
                seg = self._seg(
                    [("none", "none"), ("popup", "popup"), ("panel", "+ panel")],
                    md.get(m["id"], "panel"), preview=False)
                h.addWidget(seg)
                h.addStretch(1)
                form.addLayout(h)
                self.route_segs[m["id"]] = seg

            # ---- news
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
            self.alerts_chk = QCheckBox("Desktop notifications")
            self.alerts_chk.setChecked(bool(s.get("alerts_enabled", True)))
            form.addWidget(self.alerts_chk)

            # ---- window & startup
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
            self.drawer_chk = QCheckBox("Open Up Next drawer by default")
            self.drawer_chk.setChecked(bool(s.get("news_drawer_expanded", True)))
            form.addWidget(self.drawer_chk)
            self.autohide_chk = QCheckBox("Hide panel when clicking another app")
            self.autohide_chk.setChecked(bool(s.get("auto_hide_panel", True)))
            form.addWidget(self.autohide_chk)
            self.hidden_chk = QCheckBox("Start hidden in tray when launched manually")
            self.hidden_chk.setChecked(bool(s.get("start_hidden", False)))
            form.addWidget(self.hidden_chk)

            # ---- updates
            section("Updates")
            up_row = QHBoxLayout()
            self.update_status = QLabel(f"Current version: v{APP_VERSION}")
            self.update_status.setFont(app_font(11))
            up_row.addWidget(self.update_status, 1)
            self.check_btn = QPushButton("Check now")
            self.check_btn.setProperty("class", "ghost")
            self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.check_btn.clicked.connect(self._check_now)
            up_row.addWidget(self.check_btn)
            self.install_btn = QPushButton("Install")
            self.install_btn.setProperty("class", "primary")
            self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.install_btn.clicked.connect(self._install_now)
            self.install_btn.setVisible(False)
            up_row.addWidget(self.install_btn)
            form.addLayout(up_row)

            # ---- footer: logo + version/author + quit
            foot = QHBoxLayout()
            foot_logo = QLabel()
            foot_logo.setFixedSize(18, 18)
            fpm = QPixmap(18, 18)
            fpm.fill(Qt.GlobalColor.transparent)
            lp = os.path.join(ASSETS_DIR, "icon.svg")
            if HAS_SVG and os.path.exists(lp):
                r = QSvgRenderer(lp)
                pp = QPainter(fpm)
                pp.setRenderHint(QPainter.RenderHint.Antialiasing)
                r.render(pp)
                pp.end()
            foot_logo.setPixmap(fpm)
            foot.addWidget(foot_logo)
            foot_info = QLabel(f"Market Sync v{APP_VERSION}  •  {APP_AUTHOR}")
            foot_info.setFont(app_font(10))
            foot_info.setStyleSheet(f"color: {self._t['muted']};")
            foot.addWidget(foot_info)
            foot.addStretch(1)
            quit_btn = QPushButton("Quit app")
            quit_btn.setProperty("class", "quitbtn")
            quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            quit_btn.clicked.connect(self.c.quit_app)
            foot.addWidget(quit_btn)
            form.addSpacing(4)
            form.addLayout(foot)
            form.addStretch(1)

            # ---- bottom buttons
            bottom = QHBoxLayout()
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

        # -- segmented control helper
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
            sessions = self._seg_value(self.seg_sessions, "active_and_next")
            sample = [
                ("LON", "London", "+04:05", "13:18", True),
                ("NYC", "New York", "-00:35", "08:18", False),
                ("SYD", "Sydney", "-57:35", "22:18", False),
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
                col = "#30d158" if is_open else "#cbd5e1"
                dot = "●" if is_open else "○"
                weight = ' font-weight="800"' if is_open else ""
                parts.append(f'<span style="color:{col};{weight}">{dot} {name} {val}</span>')
            self.preview.setText(
                "&nbsp;&nbsp;".join(parts)
                + f'<br><span style="color:{t["muted"]}; font-size:10px;">'
                + "open sessions bright green, closed silvery — exactly like the panel applet</span>")

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
                self.update_status.setText(f"Update: v{res['version']}")
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
            s["show_standalone_tray"] = self.standalone_chk.isChecked()
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
            self.c.panel.set_drawer_expanded(bool(s["news_drawer_expanded"]))
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
        self._status_payload: dict = {}
        self._applet_active = False
        self.statuses = engine.get_all_statuses()
        self.selected = engine.market_status(get_market(settings["selected_market"]))

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

        # IPC server so the Cinnamon applet (and --toggle CLI) drives the panel
        self._ipc = QLocalServer()
        try:
            QLocalServer.removeServer(IPC_SOCKET_NAME)
        except Exception:
            pass
        try:
            self._ipc.listen(IPC_SOCKET_NAME)
            self._ipc.newConnection.connect(self._on_ipc)
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

        # applet detection keeps the both-in-one behaviour honest
        self.applet_timer = QTimer()
        self.applet_timer.timeout.connect(self._refresh_tray_visibility)
        self.applet_timer.start(15000)
        QTimer.singleShot(1500, self._refresh_tray_visibility)

        self.refresh_news(force=True)
        self.tick()

    # ---------------- IPC
    def _on_ipc(self):
        while self._ipc.hasPendingConnections():
            conn = self._ipc.nextPendingConnection()
            try:
                if conn.waitForReadyRead(400):
                    cmd = bytes(conn.readAll()).decode("utf-8", "ignore").strip().lower()
                    self._handle_ipc_command(cmd)
            finally:
                try:
                    conn.disconnectFromServer()
                except Exception:
                    pass

    def _handle_ipc_command(self, cmd: str):
        if cmd in ("toggle", "--toggle"):
            self.toggle_panel()
        elif cmd in ("show", "--show"):
            if not self.panel.isVisible():
                self.toggle_panel()
        elif cmd in ("hide", "--hide"):
            self.panel.hide()
        elif cmd in ("preferences", "--preferences"):
            self.open_preferences()
        elif cmd in ("quit", "--quit"):
            self.quit_app()

    # ---------------- applet / tray coordination
    def _detect_applet(self) -> bool:
        try:
            import ast
            res = subprocess.run(
                ["gsettings", "get", "org.cinnamon", "enabled-applets"],
                capture_output=True, text=True, timeout=2)
            applets = ast.literal_eval(res.stdout.strip())
            return any(APPLET_UUID in a for a in applets)
        except Exception:
            return False

    def _refresh_tray_visibility(self):
        self._applet_active = self._detect_applet()
        show = True
        if self._applet_active and not self.settings.get("show_standalone_tray", True):
            show = False  # user opted into applet-only
        try:
            self.tray.setVisible(show)
        except Exception:
            pass

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
            if len(lst) > 1:
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

    def set_drawer_expanded(self, expanded: bool):
        self.settings["news_drawer_expanded"] = bool(expanded)
        self._save()
        self.panel.set_drawer_expanded(bool(expanded))
        if self.panel.isVisible():
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
            _work()
        else:
            threading.Thread(target=_work, daemon=True).start()

    # ---------------- auto-update plumbing
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
                cmd = f"sleep 2; MARKET_SYNC_RELAUNCH=1 exec {LAUNCHER_PATH}"
            else:
                cmd = (f"sleep 2; MARKET_SYNC_RELAUNCH=1 exec /usr/bin/python3 "
                       f"{os.path.join(app_dir(), 'main.py')}")
            subprocess.Popen(
                ["setsid", "bash", "-c", cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass
        self.quit_app()

    # ---------------- tray text/icon
    def _multi_segments(self):
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
                val = engine.format_signed_countdown(s["countdown"], s["is_open"])
            return (f"{name} {val}", bool(s["is_open"]))

        opens = [s for s in self.statuses if s["is_open"] and eligible(s)]
        closed = sorted(
            [s for s in self.statuses if not s["is_open"] and eligible(s)],
            key=lambda x: x["countdown"].total_seconds())
        if sessions == "active_only":
            chosen = opens if opens else closed[:1]
        elif sessions == "active_and_next":
            chosen = opens + closed[:1]
        else:
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

        # -- Cinnamon applet status file
        try:
            self._status_payload = _write_panel_status(
                self.statuses, self.settings, now_utc, self._status_payload)
        except Exception:
            pass

        # -- tray icon
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
            self._ipc.close()
            QLocalServer.removeServer(IPC_SOCKET_NAME)
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
