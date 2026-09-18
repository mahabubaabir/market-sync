# Session Sync — core configuration
"""Market definitions + user settings. DST-aware via IANA timezones."""
from __future__ import annotations
import json
import os
from copy import deepcopy

APP_NAME = "Session Sync"
APP_ID = "session-sync"
APP_VERSION = "0.1.0"

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

DEFAULT_SETTINGS = {
    "selected_market": "LONDON",
    "time_mode": "market_local",  # or "system"
    "currencies": ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"],
    "min_impact": "Low",  # Low | Medium | High
    "alerts_enabled": True,
    "alert_minutes_before": 5,
    "news_refresh_minutes": 15,
    "theme": "system",  # system | light | dark (macOS-style, follows system by default)
    # macOS "customise your display" — menu-bar (tray) building blocks:
    "show_symbol": True,      # Market Symbols
    "show_countdown": True,   # Trading Hours Countdown Timer
    "show_local_time": True,  # Market's Local Time Option
    "show_next_event": True,  # Next Event
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_ID)
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")


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
                if k in settings:
                    settings[k] = v
            if settings["selected_market"] not in MARKET_IDS:
                settings["selected_market"] = "LONDON"
    except Exception:
        pass
    return settings


def save_settings(settings: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
