"""Session Sync — macOS Market Countdown clone for Linux Mint (Cinnamon tray).

Faithful to the reference app (Market Countdown Times & News, macOS menu bar):
  menu bar -> Market Symbol + Countdown + Market Local Time (toggle) + Next Event
  popover  -> hero with VISUAL ring timer + countdown, markets list, news list

Layout mirrors the mac screenshots: compact ~340px popover, light by default,
dark mode supported, SF-like system font, blue macOS accent.
"""
from __future__ import annotations
from datetime import datetime, timezone

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QSystemTrayIcon, QMenu,
        QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
        QFrame, QGraphicsDropShadowEffect,
    )
    from PyQt6.QtGui import (
        QIcon, QPixmap, QPainter, QColor, QFont, QAction, QActionGroup,
        QFontMetrics,
    )
    from PyQt6.QtCore import QTimer, Qt, QRectF
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # Dummies so `import ui` works without PyQt6 (CLI mode).
    QWidget = object  # type: ignore
    QSystemTrayIcon = object  # type: ignore

from config import MARKETS, get_market
import markets as engine
import calendar_api
from notifier import notify, AlertTracker

ACCENT = "#0071e3"  # macOS blue
GREEN = "#30d158"   # macOS green
RED = "#ff453a"

THEMES = {
    "light": {
        "bg": "#f5f5f7", "card": "#ffffff", "tint": "#e8f1fc",
        "border": "#e2e2e6", "text": "#1d1d1f", "muted": "#6e6e73",
        "tab_checked_bg": "#e8f1fc", "row_hover": "#f5f5f7",
        "tray_text": "#1d1d1f",
    },
    "dark": {
        "bg": "#23262b", "card": "#2e3238", "tint": "#25324a",
        "border": "#3d434b", "text": "#e8eaed", "muted": "#9aa0a6",
        "tab_checked_bg": "#353b44", "row_hover": "#353b44",
        "tray_text": "#ffffff",
    },
}

IMPACT_COLOR = {"High": "#ff453a", "Medium": "#ff9f0a", "Low": "#8e8e93", "Holiday": "#bf5af2"}


def resolve_theme(want: str) -> str:
    if want in ("light", "dark"):
        return want
    # system: ask Qt when available, else light (matches App Store screenshots)
    if HAS_QT:
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import Qt as _Qt
            app = QApplication.instance()
            if app is not None:
                scheme = app.styleHints().colorScheme()
                if scheme == _Qt.ColorScheme.Dark:
                    return "dark"
        except Exception:
            pass
    return "light"


def stylesheet(t: dict) -> str:
    return f"""
QWidget#PanelRoot {{ background: {t['bg']}; border: 1px solid {t['border']}; border-radius: 14px; }}
QLabel {{ color: {t['text']}; background: transparent; }}
QLabel.muted {{ color: {t['muted']}; font-size: 11px; }}
QLabel.caption {{ color: {t['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 0.6px; }}
QLabel.hero {{ font-size: 30px; font-weight: 800; letter-spacing: 0.5px; }}
QLabel.pill-open {{ background: {GREEN}; color: white; border-radius: 9px; padding: 2px 10px; font-weight: 800; font-size: 11px; }}
QLabel.pill-closed {{ background: #8e8e93; color: white; border-radius: 9px; padding: 2px 10px; font-weight: 800; font-size: 11px; }}
QLabel.nextcard {{ background: {t['tint']}; border: 1px solid {ACCENT}; border-radius: 10px; padding: 8px 10px; }}
QFrame.card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QPushButton.tab {{ background: transparent; color: {t['text']}; border: 1px solid transparent; border-radius: 9px; padding: 6px 2px; font-weight: 700; font-size: 12px; }}
QPushButton.tab:checked {{ background: {t['tab_checked_bg']}; border: 1px solid {ACCENT}; color: {t['text']}; }}
QLabel.mktrow {{ background: transparent; border: none; padding: 4px 6px; font-size: 12px; }}
QPushButton.ghost {{ background: transparent; color: {t['muted']}; border: 1px solid {t['border']}; border-radius: 7px; padding: 4px 10px; font-size: 12px; }}
QPushButton.ghost:hover {{ color: {t['text']}; border-color: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget {{ background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']}; }}
"""


# ---------------------------------------------------------------- tray text
# macOS shows TEXT in the menu bar ("LDN 02:14:33"), not an icon — we render
# the same text into a wide transparent pixmap for the Cinnamon tray.

def tray_label_text(selected: dict, nxt, settings: dict, now_utc) -> str:
    m = selected["market"]
    parts: list[str] = []
    if settings.get("show_symbol", True):
        parts.append(m["symbol"])
    if settings.get("show_countdown", True):
        parts.append(engine.format_countdown(selected["countdown"]))
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
    p.drawEllipse(2, 8, 12, 12)  # status dot like the mac status indicator
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
    # simple scan using NY calendar
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


# ---------------------------------------------------------------- panel

if HAS_QT:
    class RingTimer(QWidget):
        """Visual representation of the timer — circular progress ring (mac style)."""

        def __init__(self, size: int = 104):
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
            theme = THEMES.get(getattr(self, "_theme", "light"), THEMES["light"])
            rect = QRectF(8, 8, self.width() - 16, self.height() - 16)
            p.setPen(QColor(theme["border"]))
            # need width on pen: use QPen
            from PyQt6.QtGui import QPen
            p.setPen(QPen(QColor(theme["border"]), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 0, 360 * 16)
            col = ACCENT if self._open else QColor(theme["muted"])
            p.setPen(QPen(QColor(col) if isinstance(col, str) else col, 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rect, 90 * 16, -int(self._frac * 360 * 16))
            p.setPen(QColor(theme["text"]))
            p.setFont(QFont("Sans", 13, QFont.Weight.Bold))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(self._frac * 100)}%")
            p.end()
else:
    class RingTimer:  # type: ignore
        def __init__(self, *a, **k):
            raise RuntimeError("PyQt6 required for UI")


class SessionPanel(QWidget):
    """Compact macOS-popover clone (~340px). Sections mirror the App Store text:
    hero (symbol + countdown + market local time) / markets / news + next event."""

    def __init__(self, controller: "TrayController"):
        super().__init__()
        self.c = controller
        self._theme = "light"
        self.setObjectName("PanelRoot")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(344)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # — top bar: title + display controls (the "Market's Local Time Option")
        top = QHBoxLayout()
        self.title = QLabel("Market Countdown")
        self.title.setStyleSheet("font-weight:800; font-size:13px;")
        top.addWidget(self.title)
        top.addStretch(1)
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setProperty("class", "ghost")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setToolTip("Toggle light / dark")
        self.theme_btn.clicked.connect(self.c.cycle_theme)
        top.addWidget(self.theme_btn)
        self.time_btn = QPushButton("")
        self.time_btn.setProperty("class", "ghost")
        self.time_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.time_btn.clicked.connect(self.c.toggle_time_mode)
        top.addWidget(self.time_btn)
        refresh = QPushButton("↻")
        refresh.setProperty("class", "ghost")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.setToolTip("Refresh news")
        refresh.clicked.connect(lambda: self.c.refresh_news(force=True))
        top.addWidget(refresh)
        root.addLayout(top)

        # — market tabs (the "Market Symbols" row)
        tabs = QHBoxLayout()
        tabs.setSpacing(4)
        self.mkt_btns: dict[str, QPushButton] = {}
        for m in MARKETS:
            b = QPushButton(f"{m['flag']} {m['symbol']}")
            b.setCheckable(True)
            b.setProperty("class", "tab")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, mid=m["id"]: self.c.select_market(mid))
            tabs.addWidget(b, 1)
            self.mkt_btns[m["id"]] = b
        root.addLayout(tabs)

        # — hero: ring + countdown + dual clocks (mac "visual timer")
        hero = QFrame()
        hero.setProperty("class", "card")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(12, 10, 12, 10)
        hl.setSpacing(10)
        self.ring = RingTimer(88)
        hl.addWidget(self.ring)
        hv = QVBoxLayout()
        hv.setSpacing(2)
        self.hero_name = QLabel("")
        self.hero_name.setStyleSheet("font-size:14px; font-weight:800;")
        hv.addWidget(self.hero_name)
        self.hero_pill = QLabel("")
        prow = QHBoxLayout()
        prow.setContentsMargins(0, 0, 0, 0)
        prow.addWidget(self.hero_pill)
        prow.addStretch(1)
        hv.addLayout(prow)
        self.hero_cd = QLabel("--:--:--")
        self.hero_cd.setProperty("class", "hero")
        self.hero_cd.setStyleSheet("font-family: monospace; font-size: 26px; font-weight: 800;")
        hv.addWidget(self.hero_cd)
        self.hero_at = QLabel("")
        self.hero_at.setProperty("class", "muted")
        self.hero_at.setWordWrap(True)
        hv.addWidget(self.hero_at)
        self.hero_clocks = QLabel("")
        self.hero_clocks.setProperty("class", "muted")
        self.hero_clocks.setWordWrap(True)
        hv.addWidget(self.hero_clocks)
        hl.addLayout(hv, 1)
        root.addWidget(hero)

        # — markets section (open/close hours per market; QLabel renders rich text)
        cap1 = QLabel("MARKETS")
        cap1.setProperty("class", "caption")
        root.addWidget(cap1)
        self.sess_card = QFrame()
        self.sess_card.setProperty("class", "card")
        self.sess_box = QVBoxLayout(self.sess_card)
        self.sess_box.setContentsMargins(6, 4, 6, 4)
        self.sess_box.setSpacing(1)
        self.sess_rows: dict[str, QLabel] = {}
        for m in MARKETS:
            row = QLabel("")
            row.setProperty("class", "mktrow")
            row.setWordWrap(True)
            self.sess_box.addWidget(row)
            self.sess_rows[m["id"]] = row
        root.addWidget(self.sess_card)

        # — news section ("Up-to-date Market Events" + "Next Event")
        caprow = QHBoxLayout()
        cap2 = QLabel("UPCOMING EVENTS")
        cap2.setProperty("class", "caption")
        caprow.addWidget(cap2)
        caprow.addStretch(1)
        self.news_src = QLabel("")
        self.news_src.setProperty("class", "muted")
        caprow.addWidget(self.news_src)
        root.addLayout(caprow)

        self.next_card = QLabel("Loading news…")
        self.next_card.setProperty("class", "nextcard")
        self.next_card.setWordWrap(True)
        root.addWidget(self.next_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(132)
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

        self.apply_theme()

    def apply_theme(self):
        self._theme = resolve_theme(self.c.settings.get("theme", "system"))
        self.setStyleSheet(stylesheet(THEMES[self._theme]))
        self.ring._theme = self._theme  # type: ignore
        self.theme_btn.setText("☀️" if self._theme == "dark" else "🌙")

    def render(self, statuses, selected, news, news_note, now_utc):
        if resolve_theme(self.c.settings.get("theme", "system")) != self._theme:
            self.apply_theme()
        sel_id = self.c.settings["selected_market"]
        for mid, b in self.mkt_btns.items():
            b.setChecked(mid == sel_id)
        self.time_btn.setText(
            "🕒 Market time" if self.c.settings["time_mode"] == "market_local" else "🕒 Your time"
        )

        m = selected["market"]
        cd = engine.format_countdown(selected["countdown"])
        self.hero_name.setText(f"{m['flag']}  {m['name']}")
        if selected["is_open"]:
            self.hero_pill.setText("● OPEN")
            self.hero_pill.setProperty("class", "pill-open")
        else:
            self.hero_pill.setText("○ CLOSED")
            self.hero_pill.setProperty("class", "pill-closed")
        self.hero_pill.style().unpolish(self.hero_pill)
        self.hero_pill.style().polish(self.hero_pill)
        self.hero_cd.setText(cd)
        self.ring.set(selected["progress"], selected["is_open"])
        at = selected["next_at_local"].strftime("%a %H:%M %Z")
        self.hero_at.setText(f"{'Closes' if selected['is_open'] else 'Opens'} {at}")
        mkt_clock = selected["now_local"].strftime("%H:%M:%S")
        yours = now_utc.astimezone().strftime("%H:%M:%S %Z")
        self.hero_clocks.setText(f"Market {mkt_clock}<br>Yours {yours}")

        for s in statuses:
            mm = s["market"]
            dot = "🟢" if s["is_open"] else "⚪"
            mini = engine.format_countdown(s["countdown"])
            verb = "Closes" if s["is_open"] else "Opens"
            hours = f"{mm['open']}–{mm['close']}"
            sel = "  ←" if mm["id"] == sel_id else ""
            self.sess_rows[mm["id"]].setText(
                f"{dot}  <b>{mm['symbol']}</b> {mm['name']}{sel}"
                f"<br><font color='{THEMES[self._theme]['muted']}'>&nbsp;&nbsp;&nbsp;&nbsp;"
                f"{hours} • {verb} in {mini}</font>"
            )

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
                f"<font color='{THEMES[self._theme]['muted']}'>{cdl} • {when}</font>"
            )
        else:
            self.next_card.setText("No upcoming events for this filter.")

        # news list: rebuild only when content changes (avoids flicker/garbage
        # from deleteLater churn on every 1s tick while the panel is open)
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
                lab = QLabel("No events — press ↻ or widen the currency filter.")
                lab.setWordWrap(True)
                self.news_list.addWidget(lab)
                self._news_labels.append(lab)
            for e in shown:
                col = IMPACT_COLOR.get(e["impact"], "#8e8e93")
                t = _fmt_event_time(e["date_utc"])
                lab = QLabel(
                    f"<font color='{col}'>●</font> <b>{e['currency']}</b> {e['title']} "
                    f"<font color='{THEMES[self._theme]['muted']}'>· {t}</font>"
                )
                lab.setWordWrap(True)
                self.news_list.addWidget(lab)
                self._news_labels.append(lab)
        else:
            # same events: just refresh relative times in place
            for lab, e in zip(getattr(self, "_news_labels", []), shown):
                col = IMPACT_COLOR.get(e["impact"], "#8e8e93")
                t = _fmt_event_time(e["date_utc"])
                lab.setText(
                    f"<font color='{col}'>●</font> <b>{e['currency']}</b> {e['title']} "
                    f"<font color='{THEMES[self._theme]['muted']}'>· {t}</font>"
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
        self.statuses = engine.get_all_statuses()
        self.selected = engine.market_status(get_market(settings["selected_market"]))

        self.tray = QSystemTrayIcon()
        self.tray.setVisible(True)
        self.tray.activated.connect(self._on_activated)
        self.menu = QMenu()
        self._build_menu()
        self.tray.setContextMenu(self.menu)

        self.panel = SessionPanel(self)
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

        self.news_timer = QTimer()
        self.news_timer.timeout.connect(lambda: self.refresh_news(force=False))
        self.news_timer.start(max(5, settings.get("news_refresh_minutes", 15)) * 60 * 1000)

        self.refresh_news(force=True)
        self.tick()

    # -- menu (market list + Display toggles + theme + actions)
    def _build_menu(self):
        self.menu.clear()
        grp = QActionGroup(self.menu)
        grp.setExclusive(True)
        for m in MARKETS:
            a = QAction(f"{m['flag']}  {m['name']}", self.menu, checkable=True)
            a.setChecked(m["id"] == self.settings["selected_market"])
            a.triggered.connect(lambda _=False, mid=m["id"]: self.select_market(mid))
            grp.addAction(a)
            self.menu.addAction(a)
        self.menu.addSeparator()
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
        for t in ("system", "light", "dark"):
            a = QAction(t.capitalize(), self.menu, checkable=True)
            a.setChecked(self.settings.get("theme", "system") == t)
            a.triggered.connect(lambda _=False, tv=t: self.set_theme(tv))
            tgrp.addAction(a)
            theme_m.addAction(a)
        self.menu.addSeparator()
        tm = QAction(
            "Show market-local time" if self.settings["time_mode"] != "market_local"
            else "Show your time",
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
        self.menu.addSeparator()
        q = QAction("Quit Session Sync", self.menu)
        q.triggered.connect(self.app.quit)
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
        order = ["system", "light", "dark"]
        cur = self.settings.get("theme", "system")
        self.set_theme(order[(order.index(cur) + 1) % len(order)] if cur in order else "system")

    def toggle_time_mode(self):
        self.settings["time_mode"] = (
            "system" if self.settings["time_mode"] == "market_local" else "market_local"
        )
        self._save()
        self._build_menu()
        self.tick()

    def refresh_news(self, force=False):
        import threading

        def _work():
            try:
                ev, _cached, note = calendar_api.fetch_events(
                    force_refresh=force,
                    cache_ttl_min=self.settings.get("news_refresh_minutes", 15),
                )
                self.events = ev
                self.news_note = note
            except Exception:
                pass

        if not self.events or force:
            _work()  # synchronous on launch so first paint has data
        else:
            threading.Thread(target=_work, daemon=True).start()

    def tick(self):
        now_utc = datetime.now(timezone.utc)
        self.statuses = engine.get_all_statuses(now_utc)
        sel = [s for s in self.statuses if s["market"]["id"] == self.settings["selected_market"]]
        self.selected = sel[0] if sel else self.statuses[0]
        nxt = calendar_api.next_event(
            self.events, self.settings["currencies"], self.settings["min_impact"], now_utc
        )
        label = tray_label_text(self.selected, nxt, self.settings, now_utc)
        self.tray.setIcon(make_tray_icon(label, self.selected["is_open"], self.settings.get("theme", "system")))
        m = self.selected["market"]
        cd = engine.format_countdown(self.selected["countdown"])
        tip = f"{m['flag']} {m['name']} {'● OPEN' if self.selected['is_open'] else '○ CLOSED'}\n"
        tip += f"{'Closes' if self.selected['is_open'] else 'Opens'} in {cd}\n"
        tip += f"Market {self.selected['now_local'].strftime('%H:%M:%S %Z')}"
        if nxt and nxt.get("_dt"):
            tip += f"\nNext: {calendar_api.event_countdown_line(nxt, now_utc)}"
        self.tray.setToolTip(tip)
        if self.panel.isVisible():
            self.panel.render(self.statuses, self.selected, self.events, self.news_note, now_utc)
        self._maybe_alert(nxt, now_utc)

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

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.MiddleClick):
            self.toggle_panel()

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
            return
        self.panel.render(
            self.statuses, self.selected, self.events, self.news_note, datetime.now(timezone.utc)
        )
        # macOS-popover placement: just under the cursor, clamped on-screen
        from PyQt6.QtGui import QCursor
        self.panel.adjustSize()
        avail = self.app.primaryScreen().availableGeometry()
        c = QCursor.pos()
        w, h = self.panel.width(), self.panel.height()
        x = min(max(c.x() - w // 2, avail.x() + 8), avail.x() + avail.width() - w - 8)
        y = min(max(c.y() + 16, avail.y() + 8), avail.y() + avail.height() - h - 8)
        self.panel.move(max(x, 8), max(y, 8))
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
