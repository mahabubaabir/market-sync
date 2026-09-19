# Market Sync — core configuration
"""Market definitions + user settings. DST-aware via IANA timezones."""
from __future__ import annotations
import json
import os
from copy import deepcopy

APP_NAME = "Market Sync"
APP_ID = "market-sync"
APP_VERSION = "1.4.0"
APP_AUTHOR = "Mahabub H. Aabir"
APP_EMAIL = "maha_bub@outlook.com"

# GitHub repo used by the one-line installer + auto-update checker.
GITHUB_REPO = "mahabubaabir/market-sync"
UPDATE_CHECK_HOURS = 24

# Where the app lives when installed from the .deb.
SYSTEM_INSTALL_DIR = "/opt/market-sync"
LAUNCHER_PATH = "/usr/bin/market-sync"

# IPC socket name (applet <-> app): market-sync --toggle / --preferences / ...
IPC_SOCKET_NAME = "market_sync_ipc"

# Cinnamon applet uuid (kept for the panel integration)
APPLET_UUID = "market-sync@cinnamon"


def app_dir() -> str:
    """Directory of the *running* code (dev checkout or /opt install)."""
    return os.path.dirname(os.path.abspath(__file__))


IS_PACKAGED = os.path.exists(os.path.join(SYSTEM_INSTALL_DIR, "main.py"))

# Market order matches Market Sync v0.2: London, New York, Sydney, Tokyo, NYSE.
# Open/close times are stored market-local so DST is always correct.
MARKETS = [
    {
        "id": "LONDON",
        "name": "London",
        "symbol": "LON",
        "flag": "🇬🇧",
        "landmark": "london",
        "tz": "Europe/London",
        "open": "08:00",
        "close": "16:30",
        "type": "fx",
        "utc_hint": "07:00–16:00 UTC",
        "color": "#8ecd76",
    },
    {
        "id": "NEW_YORK",
        "name": "New York",
        "symbol": "NYC",
        "flag": "🇺🇸",
        "landmark": "new_york",
        "tz": "America/New_York",
        "open": "08:00",
        "close": "17:00",
        "type": "fx",
        "utc_hint": "12:00–21:00 UTC",
        "color": "#c792ea",
    },
    {
        "id": "SYDNEY",
        "name": "Sydney",
        "symbol": "SYD",
        "flag": "🇦🇺",
        "landmark": "sydney",
        "tz": "Australia/Sydney",
        "open": "07:00",
        "close": "16:00",
        "type": "fx",
        "utc_hint": "21:00–06:00 UTC",
        "color": "#4da3ff",
    },
    {
        "id": "TOKYO",
        "name": "Tokyo",
        "symbol": "TYO",
        "flag": "🇯🇵",
        "landmark": "tokyo",
        "tz": "Asia/Tokyo",
        "open": "09:00",
        "close": "18:00",
        "type": "fx",
        "utc_hint": "00:00–09:00 UTC",
        "color": "#ff6b6b",
    },
    {
        "id": "NYSE",
        "name": "NYSE",
        "symbol": "NYSE",
        "flag": "🗽",
        "landmark": "new_york",
        "tz": "America/New_York",
        "open": "09:30",
        "close": "16:00",
        "type": "equity",
        "utc_hint": "13:30–20:00 UTC",
        "color": "#ffcb6b",
        "calendar": "NYSE",  # holiday-aware
    },
]

MARKET_IDS = [m["id"] for m in MARKETS]

IMPACT_LEVELS = ["All", "Low", "Medium", "High"]
ALL_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

DEFAULT_SETTINGS = {
    "selected_market": "LONDON",
    "time_mode": "market_local",  # market_local | local
    "currencies": ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"],
    # v0.2-style multi-select impact chips (All = every level ticked).
    "active_impacts": ["High", "Medium", "Low"],
    "min_impact": "All",  # legacy fallback kept for compatibility
    "alerts_enabled": True,
    "alert_minutes_before": 5,
    "news_refresh_minutes": 15,
    "theme": "system",  # system | light | dark | dark_purple | mint_light | mint_dark
    "time_format": "24h",   # 24h | 12h
    "active_brighten": True,  # brighten open markets, dim closed ones
    "news_drawer_expanded": True,
    # Tray + top panel presentation (v0.2 parity)
    "tray_mode": "multi",           # multi (open + next) | single (selected market)
    "tray_icon_style": "text",      # text | logo
    "tray_layout": "compact",       # compact (symbols) | standard (names)
    "tray_time_as": "countdown",    # countdown | local_time
    "tray_sessions": "active_and_next",  # active_only | active_and_next | all
    # Both-in-one: keep the standalone tray icon while the Cinnamon applet runs.
    "show_standalone_tray": True,
    # v0.2 per-market routing: none = hide card; popup = panel only; panel = + tray
    "market_display": {
        "LONDON": "panel", "NEW_YORK": "panel", "SYDNEY": "panel",
        "TOKYO": "panel", "NYSE": "panel",
    },
    "show_symbol": True,
    "show_countdown": True,
    "show_local_time": True,
    "show_next_event": True,
    "left_click_action": "panel",  # panel | menu
    "start_hidden": False,
    "auto_hide_panel": True,
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_ID)
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", APP_ID)
LOCK_PATH = os.path.join(CACHE_DIR, "app.lock")
LOG_PATH = os.path.join(CACHE_DIR, "app.log")
# Written every tick for the Cinnamon applet (spec: panel_status.json)
PANEL_STATUS_PATH = os.path.join(CACHE_DIR, "panel_status.json")
# Economic calendar cache (spec: news_events.json; legacy: calendar.json)
NEWS_CACHE_PATH = os.path.join(CACHE_DIR, "news_events.json")
LEGACY_NEWS_CACHE_PATH = os.path.join(CACHE_DIR, "calendar.json")

# System-wide autostart entry (installed by the .deb, applies to all users).
SYSTEM_AUTOSTART_PATH = "/etc/xdg/autostart/market-sync.desktop"
# Per-user override (XDG spec: a user file with Hidden=true disables the system
# entry; a normal user file or its absence leaves the system entry active).
USER_AUTOSTART_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "autostart", f"{APP_ID}.desktop"
)
AUTOSTART_PATH = USER_AUTOSTART_PATH


def get_market(market_id: str) -> dict:
    for m in MARKETS:
        if m["id"] == market_id:
            return m
    return MARKETS[0]


def _migrate_old_config() -> None:
    """One-time: carry settings over from the pre-1.1 'session-sync' name."""
    old_dir = os.path.join(os.path.expanduser("~"), ".config", "session-sync")
    old_path = os.path.join(old_dir, "settings.json")
    try:
        if os.path.exists(SETTINGS_PATH) or not os.path.exists(old_path):
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(old_path, "r", encoding="utf-8") as src, \
                open(SETTINGS_PATH, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    except Exception:
        pass


# Keys written by the retired Market Sync v0.2 app, which used the same
# settings path (~/.config/market-sync/settings.json). We translate them
# instead of trusting them, so v0.2 defaults like NYSE "none" cannot hide
# cards in the new app.
_OLD_V02_KEYS = ("menu_layout", "show_time_as", "panel_session_filter",
                 "show_system_tray", "glass_blur", "market_order", "launch_at_login")
_OLD_MARKET_DISPLAY = {"+ menu bar": "panel", "panel": "panel",
                       "popup": "popup", "none": "popup"}


def _adopt_old_v02(settings: dict, user: dict) -> bool:
    """Translate a v0.2 settings file into our format. Returns True if it
    looked like v0.2 (and makes a backup next to it)."""
    if not any(k in user for k in _OLD_V02_KEYS):
        return False
    try:
        import shutil
        shutil.copyfile(SETTINGS_PATH, SETTINGS_PATH + ".v0.2-backup")
    except Exception:
        pass
    md = user.get("market_display")
    if isinstance(md, dict):
        settings["market_display"] = {
            mid: _OLD_MARKET_DISPLAY.get(str(md.get(mid, "")), "panel")
            for mid in MARKET_IDS
        }
    for new_key, old_key, valid in (
        ("tray_layout", "menu_layout", ("compact", "standard")),
        ("tray_time_as", "show_time_as", ("countdown", "local_time")),
        ("tray_sessions", "panel_session_filter",
         ("active_only", "active_and_next", "all")),
    ):
        val = user.get(old_key)
        if val in valid:
            settings[new_key] = val
    # never inherit a silent start from the old app
    settings["start_hidden"] = False
    return True


def load_settings() -> dict:
    _migrate_old_config()
    settings = deepcopy(DEFAULT_SETTINGS)
    adopted = False
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in DEFAULT_SETTINGS:
                    settings[k] = v
            adopted = _adopt_old_v02(settings, user)
            # migration: old min_impact -> active_impacts (only if unticked)
            if "active_impacts" not in user and user.get("min_impact"):
                settings["active_impacts"] = _impacts_from_min(user["min_impact"])
            if settings["selected_market"] not in MARKET_IDS:
                settings["selected_market"] = "LONDON"
            if settings.get("theme") not in (
                "system", "light", "dark", "dark_purple", "mint_light", "mint_dark"
            ):
                settings["theme"] = "system"
            if settings.get("time_mode") not in ("market_local", "local", "system"):
                settings["time_mode"] = "market_local"
            if settings.get("time_mode") == "system":
                settings["time_mode"] = "local"
            if settings.get("time_format") not in ("12h", "24h"):
                settings["time_format"] = "24h"
            if settings.get("tray_mode") not in ("multi", "single"):
                settings["tray_mode"] = "multi"
            if settings.get("tray_icon_style") not in ("text", "logo"):
                settings["tray_icon_style"] = "text"
            if settings.get("left_click_action") not in ("panel", "menu"):
                settings["left_click_action"] = "panel"
            if not isinstance(settings.get("currencies"), list) or not settings["currencies"]:
                settings["currencies"] = list(DEFAULT_SETTINGS["currencies"])
            imp = settings.get("active_impacts")
            if not isinstance(imp, list) or not set(imp) <= {"High", "Medium", "Low"} or not imp:
                settings["active_impacts"] = ["High", "Medium", "Low"]
            if not isinstance(settings.get("market_display"), dict):
                settings["market_display"] = {}
            md = settings.get("market_display") or {}
            settings["market_display"] = {
                mid: (md.get(mid) if md.get(mid) in ("none", "popup", "panel") else "panel")
                for mid in MARKET_IDS
            }
            if settings.get("tray_layout") not in ("compact", "standard"):
                settings["tray_layout"] = "compact"
            if settings.get("tray_time_as") not in ("countdown", "local_time"):
                settings["tray_time_as"] = "countdown"
            if settings.get("tray_sessions") not in ("active_only", "active_and_next", "all"):
                settings["tray_sessions"] = "active_and_next"
    except Exception:
        pass
    if adopted:
        save_settings(settings)  # rewrite in the new format
    return settings


def _impacts_from_min(min_impact: str) -> list[str]:
    """Map legacy minimum-impact setting to v0.2 multi-select defaults."""
    if min_impact == "High":
        return ["High"]
    if min_impact == "Medium":
        return ["Medium", "High"]
    return ["High", "Medium", "Low"]


def autostart_exec_line() -> str:
    """Command line used in autostart + launcher entries."""
    if IS_PACKAGED and os.path.exists(LAUNCHER_PATH):
        return f"{LAUNCHER_PATH} --hidden"
    return f"/usr/bin/python3 {os.path.join(app_dir(), 'main.py')} --hidden"


def is_autostart_enabled() -> bool:
    """True unless the user explicitly disabled it via Hidden=true override."""
    if os.path.exists(USER_AUTOSTART_PATH):
        try:
            with open(USER_AUTOSTART_PATH, "r", encoding="utf-8") as f:
                body = f.read()
            if "Hidden=true" in body.replace(" ", ""):
                return False
            return True
        except Exception:
            return False
    return os.path.exists(SYSTEM_AUTOSTART_PATH)


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
