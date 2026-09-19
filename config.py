# Session Sync — core configuration
"""Market definitions + user settings. DST-aware via IANA timezones."""
from __future__ import annotations
import json
import os
from copy import deepcopy

APP_NAME = "Session Sync"
APP_ID = "session-sync"
APP_VERSION = "1.0.0"

# GitHub repo used by the one-line installer + auto-update checker.
# Change these two lines if you fork / rename the project.
GITHUB_REPO = "mahabubaabir/market-sync"
UPDATE_CHECK_HOURS = 24

# Where the app lives when installed from the .deb. Falls back to the source
# checkout directory when running in development.
SYSTEM_INSTALL_DIR = "/opt/session-sync"


def app_dir() -> str:
    """Directory containing the running application code."""
    if os.path.exists(os.path.join(SYSTEM_INSTALL_DIR, "main.py")):
        return SYSTEM_INSTALL_DIR
    return os.path.dirname(os.path.abspath(__file__))


IS_PACKAGED = os.path.exists(os.path.join(SYSTEM_INSTALL_DIR, "main.py"))

# Local open/close times. Chosen to match the reference app's UTC windows
# (Sydney 21-06 UTC, Tokyo 00-09 UTC, London 07-16 UTC, NY 12-21 UTC,
#  NYSE 13:30-20 UTC) but expressed in market-local time so DST is correct.
MARKETS = [
    {
        "id": "SYDNEY",
        "name": "Sydney",
        "symbol": "SYD",
        "flag": "🇦🇺",
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
        "tz": "Asia/Tokyo",
        "open": "09:00",
        "close": "18:00",
        "type": "fx",
        "utc_hint": "00:00–09:00 UTC",
        "color": "#ff6b6b",
    },
    {
        "id": "LONDON",
        "name": "London",
        "symbol": "LDN",
        "flag": "🇬🇧",
        "tz": "Europe/London",
        "open": "08:00",
        "close": "16:30",
        "type": "fx",
        "utc_hint": "07:00–16:00 UTC",
        "color": "#8ecd76",
    },
    {
        "id": "NEW_YORK",
        "name": "New York (FX)",
        "symbol": "NYC",
        "flag": "🇺🇸",
        "tz": "America/New_York",
        "open": "08:00",
        "close": "17:00",
        "type": "fx",
        "utc_hint": "12:00–21:00 UTC",
        "color": "#c792ea",
    },
    {
        "id": "NYSE",
        "name": "NYSE",
        "symbol": "NYSE",
        "flag": "🗽",
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

IMPACT_LEVELS = ["Low", "Medium", "High"]
ALL_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]

DEFAULT_SETTINGS = {
    "selected_market": "LONDON",
    # "market_local" = hero clock emphasises market tz, "local" = emphasises laptop tz.
    # Both times are ALWAYS shown; this only flips which one is on top.
    "time_mode": "market_local",  # market_local | local
    "currencies": ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"],
    "min_impact": "Low",  # Low | Medium | High
    "alerts_enabled": True,
    "alert_minutes_before": 5,
    "news_refresh_minutes": 15,
    "theme": "system",  # system | light | dark | dark_purple | mint_light | mint_dark
    "show_symbol": True,
    "show_countdown": True,
    "show_local_time": True,
    "show_next_event": True,
    "left_click_action": "panel",  # panel | menu
    "start_hidden": False,         # if True, launch goes to tray only
    "auto_hide_panel": True,       # hide panel when you click another app
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_ID)
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", APP_ID)
LOCK_PATH = os.path.join(CACHE_DIR, "app.lock")
LOG_PATH = os.path.join(CACHE_DIR, "app.log")

# System-wide autostart entry (installed by the .deb, applies to all users).
SYSTEM_AUTOSTART_PATH = "/etc/xdg/autostart/session-sync.desktop"
# Per-user override (XDG spec: a user file with Hidden=true disables the system
# entry; a normal user file or its absence leaves the system entry active).
USER_AUTOSTART_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "autostart", f"{APP_ID}.desktop"
)
# Back-compat alias for code that referenced the old name.
AUTOSTART_PATH = USER_AUTOSTART_PATH

LAUNCHER_PATH = "/usr/bin/session-sync"


def get_market(market_id: str) -> dict:
    for m in MARKETS:
        if m["id"] == market_id:
            return m
    return MARKETS[2]


def load_settings() -> dict:
    settings = deepcopy(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in DEFAULT_SETTINGS:
                    settings[k] = v
            if settings["selected_market"] not in MARKET_IDS:
                settings["selected_market"] = "LONDON"
            if settings.get("min_impact") not in ("Low", "Medium", "High"):
                settings["min_impact"] = "Low"
            if settings.get("theme") not in (
                "system", "light", "dark", "dark_purple", "mint_light", "mint_dark"
            ):
                settings["theme"] = "system"
            if settings.get("time_mode") not in ("market_local", "local", "system"):
                settings["time_mode"] = "market_local"
            # backward-compat: old "system" time_mode means laptop-local
            if settings.get("time_mode") == "system":
                settings["time_mode"] = "local"
            if settings.get("left_click_action") not in ("panel", "menu"):
                settings["left_click_action"] = "panel"
            if not isinstance(settings.get("currencies"), list) or not settings["currencies"]:
                settings["currencies"] = list(DEFAULT_SETTINGS["currencies"])
    except Exception:
        pass
    return settings


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
