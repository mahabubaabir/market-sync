"""DST-aware market open/close + countdown engine.

No third-party deps — stdlib only (zoneinfo + datetime).
NYSE holidays are computed locally (no pandas needed).
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone, time as dtime
from zoneinfo import ZoneInfo
from config import MARKETS, get_market


# ---------------------------------------------------------------- holidays

def _easter_sunday(year: int) -> datetime:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)


def _observed(dt: datetime) -> datetime:
    # US market observance: Sat -> Fri before, Sun -> Mon after
    if dt.weekday() == 5:
        return dt - timedelta(days=1)
    if dt.weekday() == 6:
        return dt + timedelta(days=1)
    return dt


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime:
    """n-th weekday (Mon=0). n=-1 means last."""
    from calendar import monthrange
    if n > 0:
        first = datetime(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))
    else:
        days = monthrange(year, month)[1]
        last = datetime(year, month, days)
        offset = (last.weekday() - weekday) % 7
        return last - timedelta(days=offset)


def nyse_holidays(year: int) -> set:
    """Return set of date objects when NYSE is fully closed."""
    from datetime import date
    good_friday = (_easter_sunday(year) - timedelta(days=2)).date()
    fixed = [
        _observed(datetime(year, 1, 1)).date(),    # New Year's
        _nth_weekday(year, 1, 0, 3).date(),        # MLK
        _nth_weekday(year, 2, 0, 3).date(),        # Presidents
        good_friday,                               # Good Friday
        _nth_weekday(year, 5, 0, -1).date(),       # Memorial
        _observed(datetime(year, 6, 19)).date(),   # Juneteenth
        _observed(datetime(year, 7, 4)).date(),    # Independence
        _nth_weekday(year, 9, 0, 1).date(),        # Labor
        _nth_weekday(year, 11, 3, 4).date(),       # Thanksgiving
        _observed(datetime(year, 12, 25)).date(),  # Christmas
    ]
    return set(fixed)


def is_nyse_holiday(day_ny) -> bool:
    return day_ny.date() in nyse_holidays(day_ny.year)


def nyse_early_close(day_ny) -> str | None:
    """Return early close HH:MM if known half-day, else None."""
    y, m, d, wd = day_ny.year, day_ny.month, day_ny.day, day_ny.weekday()
    # Day after Thanksgiving (4th Fri of Nov)
    thanksgiving = _nth_weekday(y, 11, 3, 4).day
    if m == 11 and d == thanksgiving + 1:
        return "13:00"
    # July 3rd early close (if Mon-Thu) + Christmas Eve
    if m == 7 and d == 3 and wd in (0, 1, 2, 3):
        return "13:00"
    if m == 12 and d == 24 and wd in (0, 1, 2, 3, 4):
        return "13:00"
    return None


# ---------------------------------------------------------------- core

def _parse_hm(s: str) -> dtime:
    h, mi = s.split(":")
    return dtime(int(h), int(mi))


def _is_fx_trading_day(local_dt: datetime) -> bool:
    return local_dt.weekday() < 5  # Mon-Fri


def market_day_bounds(market: dict, local_day: datetime) -> tuple[datetime, datetime]:
    """Open/close datetimes for a given local calendar day."""
    tz = ZoneInfo(market["tz"])
    o = _parse_hm(market["open"])
    c = _parse_hm(market["close"])
    open_dt = local_day.replace(hour=o.hour, minute=o.minute, second=0, microsecond=0)
    close_dt = local_day.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)
    if market.get("id") == "NYSE":
        early = nyse_early_close(local_day)
        if early:
            e = _parse_hm(early)
            close_dt = local_day.replace(hour=e.hour, minute=e.minute, second=0, microsecond=0)
    # ensure tz-aware
    if open_dt.tzinfo is None:
        open_dt = open_dt.replace(tzinfo=tz)
        close_dt = close_dt.replace(tzinfo=tz)
    return open_dt, close_dt


def _is_trading_day(market: dict, local_dt: datetime) -> bool:
    if local_dt.weekday() >= 5:
        return False
    if market.get("calendar") == "NYSE" and is_nyse_holiday(local_dt):
        return False
    return True


def market_status(market: dict, now_utc: datetime | None = None) -> dict:
    """Return open state, next transition, countdown, progress, local time."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    tz = ZoneInfo(market["tz"])
    now_local = now_utc.astimezone(tz)

    # Find today's bounds
    day_cursor = now_local
    if _is_trading_day(market, now_local):
        open_dt, close_dt = market_day_bounds(market, now_local)
        if open_dt <= now_local < close_dt:
            total = (close_dt - open_dt).total_seconds()
            elapsed = (now_local - open_dt).total_seconds()
            return {
                "market": market,
                "is_open": True,
                "next_label": "closes",
                "next_at_utc": close_dt.astimezone(timezone.utc),
                "next_at_local": close_dt,
                "countdown": close_dt - now_local,
                "progress": min(1.0, max(0.0, elapsed / total)) if total else 0,
                "now_local": now_local,
                "now_utc": now_utc,
            }
        if now_local < open_dt:
            total = (close_dt - open_dt).total_seconds()
            return {
                "market": market,
                "is_open": False,
                "next_label": "opens",
                "next_at_utc": open_dt.astimezone(timezone.utc),
                "next_at_local": open_dt,
                "countdown": open_dt - now_local,
                "progress": 0.0,
                "now_local": now_local,
                "now_utc": now_utc,
            }
    # After close or non-trading day -> scan forward (max 10 days)
    for i in range(1, 11):
        cand = (now_local + timedelta(days=i)).replace(hour=12, minute=0, second=0, microsecond=0)
        if not _is_trading_day(market, cand):
            continue
        open_dt, close_dt = market_day_bounds(market, cand)
        return {
            "market": market,
            "is_open": False,
            "next_label": "opens",
            "next_at_utc": open_dt.astimezone(timezone.utc),
            "next_at_local": open_dt,
            "countdown": open_dt - now_local,
            "progress": 0.0,
            "now_local": now_local,
            "now_utc": now_utc,
        }
    # Fallback (should never hit)
    return {
        "market": market, "is_open": False, "next_label": "opens",
        "next_at_utc": now_utc + timedelta(days=1),
        "next_at_local": now_local + timedelta(days=1),
        "countdown": timedelta(days=1), "progress": 0.0,
        "now_local": now_local, "now_utc": now_utc,
    }


def get_all_statuses(now_utc: datetime | None = None) -> list[dict]:
    return [market_status(m, now_utc) for m in MARKETS]


def format_countdown(td: timedelta) -> str:
    secs = max(0, int(td.total_seconds()))
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d > 0:
        return f"{d}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_clock(dt: datetime, time_mode: str = "market_local") -> str:
    # time_mode handled by caller for system tz; here just HH:MM:SS
    return dt.strftime("%H:%M:%S")


def overlap_count(statuses: list[dict] | None = None) -> int:
    if statuses is None:
        statuses = get_all_statuses()
    return sum(1 for s in statuses if s["is_open"])


def summary_line(status: dict, time_mode: str = "market_local") -> str:
    m = status["market"]
    state = "OPEN" if status["is_open"] else "CLOSED"
    cd = format_countdown(status["countdown"])
    if time_mode == "market_local":
        clock = status["now_local"].strftime("%H:%M:%S") + f" {m['symbol']}-local"
    else:
        clock = datetime.now().astimezone().strftime("%H:%M:%S") + " local"
    return f"{m['symbol']} {state} {status['next_label']} in {cd}  •  {clock}"
