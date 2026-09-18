"""Free economic-calendar feed (ForexFactory via FairEconomy, no API key).

Feed: https://nfs.faireconomy.media/ff_calendar_thisweek.json
Cache: ~/.cache/session-sync/calendar.json (TTL 15 min default)
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone, timedelta

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

APP_ID = "session-sync"
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", APP_ID)
CACHE_PATH = os.path.join(CACHE_DIR, "calendar.json")

IMPACT_RANK = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0, "": 0}


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        s = raw.strip()
        # Feed format is usually "2026-09-18T12:30:00-04:00" or "...Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize(item: dict) -> dict | None:
    title = (item.get("title") or "").strip()
    country = (item.get("country") or item.get("currency") or "").strip().upper()
    if not title:
        return None
    dt = _parse_date(item.get("date") or "")
    impact = (item.get("impact") or "").strip().capitalize()
    if impact not in ("High", "Medium", "Low", "Holiday"):
        impact = "Low" if impact else "Low"
    return {
        "title": title,
        "country": country,
        "currency": country,
        "date_utc": dt.isoformat() if dt else "",
        "impact": impact,
        "forecast": str(item.get("forecast") or "").strip(),
        "previous": str(item.get("previous") or "").strip(),
        "actual": str(item.get("actual") or "").strip(),
    }


def _read_cache(max_age_min: int = 60 * 24) -> list[dict]:
    try:
        if not os.path.exists(CACHE_PATH):
            return []
        age = (datetime.now().timestamp() - os.path.getmtime(CACHE_PATH)) / 60
        if age > max_age_min:
            return []
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_cache(events: list[dict]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=1)
    except Exception:
        pass


def fetch_events(force_refresh: bool = False, cache_ttl_min: int = 15) -> tuple[list[dict], bool, str]:
    """Returns (events, from_cache, note). Never raises."""
    cached = _read_cache(max_age_min=60 * 24 * 8)
    # Use fresh cache without network if within TTL and not forced
    if cached and not force_refresh:
        try:
            age = (datetime.now().timestamp() - os.path.getmtime(CACHE_PATH)) / 60
            if age < cache_ttl_min:
                return cached, True, f"cache {int(age)}m old"
        except Exception:
            pass
    if not HAS_REQUESTS:
        note = "requests not installed — using cache" if cached else "requests not installed"
        return cached, True, note
    try:
        r = requests.get(FF_URL, timeout=15, headers={"User-Agent": "session-sync/0.1"})
        r.raise_for_status()
        raw = r.json()
        events = [e for e in (_normalize(x) for x in raw) if e]
        events.sort(key=lambda e: e["date_utc"])
        _write_cache(events)
        return events, False, f"live • {len(events)} events"
    except Exception as ex:
        note = f"offline ({type(ex).__name__}) — using cache" if cached else f"offline: {ex}"
        return cached, True, note


def _event_dt(e: dict) -> datetime | None:
    return _parse_date(e.get("date_utc") or "")


def filter_events(events: list[dict], currencies: list[str] | None = None,
                  min_impact: str = "Low", hours_ahead: int = 72,
                  now_utc: datetime | None = None) -> list[dict]:
    now_utc = now_utc or datetime.now(timezone.utc)
    min_rank = IMPACT_RANK.get(min_impact, 0)
    cur = {c.upper() for c in (currencies or [])}
    out = []
    for e in events:
        dt = _event_dt(e)
        if dt is None:
            continue
        if dt < now_utc - timedelta(hours=2):
            continue
        if dt > now_utc + timedelta(hours=hours_ahead):
            continue
        if cur and e.get("currency", "").upper() not in cur:
            continue
        if IMPACT_RANK.get(e.get("impact", ""), 0) < min_rank:
            continue
        out.append({**e, "_dt": dt})
    out.sort(key=lambda e: e["_dt"])
    return out


def next_event(events: list[dict], currencies: list[str] | None = None,
               min_impact: str = "Low",
               now_utc: datetime | None = None) -> dict | None:
    upcoming = filter_events(events, currencies, min_impact, hours_ahead=24 * 7, now_utc=now_utc)
    return upcoming[0] if upcoming else None


def event_countdown_line(event: dict | None, now_utc: datetime | None = None) -> str:
    if not event:
        return "No upcoming events"
    now_utc = now_utc or datetime.now(timezone.utc)
    dt = event.get("_dt") or _parse_date(event.get("date_utc") or "")
    if dt is None:
        return event.get("title", "Event")
    delta = dt - now_utc
    secs = max(0, int(delta.total_seconds()))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    d, h = divmod(h, 24)
    cd = f"{d}d {h:02d}:{m:02d}:{s:02d}" if d else f"{h:02d}:{m:02d}:{s:02d}"
    return f"{event['currency']} {event['title']} in {cd}"
