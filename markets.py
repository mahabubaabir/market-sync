"""DST-aware market open/close + countdown engine.

No third-party deps — stdlib only (zoneinfo + datetime).
NYSE holidays are computed locally (no pandas needed).
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone, time as dtime
from zoneinfo import ZoneInfo
from config import MARKETS


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
    days = monthrange(year, month)[1]
    last = datetime(year, month, days)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


# NYSE's published 2028 calendar explicitly has no observed New Year's Day
# holiday when Jan 1, 2028 falls on Saturday.
_NO_NEW_YEAR_OBSERVED = {2028}


def _add_observed_holiday(out: set, holiday: datetime, year: int) -> None:
    """Add an observed holiday only when its observed date falls in year."""
    if holiday.month == 1 and holiday.day == 1 and holiday.year in _NO_NEW_YEAR_OBSERVED:
        observed = holiday
    else:
        observed = _observed(holiday)
    if observed.year == year:
        out.add(observed.date())


def nyse_holidays(year: int) -> set:
    """Return NYSE full-closure dates that fall within the requested year."""
    good_friday = _easter_sunday(year) - timedelta(days=2)
    holidays = (
        datetime(year, 1, 1),                      # New Year's
        _nth_weekday(year, 1, 0, 3),              # MLK
        _nth_weekday(year, 2, 0, 3),              # Washington's Birthday
        good_friday,                               # Good Friday
        _nth_weekday(year, 5, 0, -1),             # Memorial
        datetime(year, 6, 19),                     # Juneteenth
        datetime(year, 7, 4),                     # Independence
        _nth_weekday(year, 9, 0, 1),              # Labor
        _nth_weekday(year, 11, 3, 4),             # Thanksgiving
        datetime(year, 12, 25),                    # Christmas
    )
    out: set = set()
    for holiday in holidays:
        _add_observed_holiday(out, holiday, year)

    # Carry an observed New Year's Day from the following year into the
    # requested year, except for NYSE's explicit 2028 exception.
    next_new_year = datetime(year + 1, 1, 1)
    if next_new_year.year not in _NO_NEW_YEAR_OBSERVED:
        observed = _observed(next_new_year)
        if observed.year == year:
            out.add(observed.date())
    return out


def is_nyse_holiday(day_ny) -> bool:
    return day_ny.date() in nyse_holidays(day_ny.year)


def nyse_early_close(day_ny) -> str | None:
    """Return 1pm ET early close for NYSE half-days, else None."""
    y, m, d, wd = day_ny.year, day_ny.month, day_ny.day, day_ny.weekday()
    if is_nyse_holiday(day_ny):
        return None

    # Day after Thanksgiving (4th Friday of November).
    thanksgiving = _nth_weekday(y, 11, 3, 4).day
    if m == 11 and d == thanksgiving + 1 and wd == 4:
        return "13:00"

    # July 3rd is an early close only when it is a Monday-Thursday trading day.
    if m == 7 and d == 3 and wd in (0, 1, 2, 3):
        return "13:00"

    # Christmas Eve, when it is a weekday trading day.
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


def _countdown(target_local: datetime, now_utc: datetime) -> timedelta:
    """Return absolute elapsed time, not a wall-clock difference."""
    return target_local.astimezone(timezone.utc) - now_utc


def market_status(market: dict, now_utc: datetime | None = None) -> dict:
    """Return open state, next transition, countdown, progress, local time."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    tz = ZoneInfo(market["tz"])
    now_local = now_utc.astimezone(tz)

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
                "countdown": _countdown(close_dt, now_utc),
                "progress": min(1.0, max(0.0, elapsed / total)) if total else 0,
                "now_local": now_local,
                "now_utc": now_utc,
            }
        if now_local < open_dt:
            return {
                "market": market,
                "is_open": False,
                "next_label": "opens",
                "next_at_utc": open_dt.astimezone(timezone.utc),
                "next_at_local": open_dt,
                "countdown": _countdown(open_dt, now_utc),
                "progress": 0.0,
                "now_local": now_local,
                "now_utc": now_utc,
            }

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
            "countdown": _countdown(open_dt, now_utc),
            "progress": 0.0,
            "now_local": now_local,
            "now_utc": now_utc,
        }

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


def format_signed_countdown(td: timedelta, is_open: bool, include_seconds: bool = False) -> str:
    """Design System v2.0 style: '+04:05' while open, '-00:35' while closed."""
    secs = max(0, int(td.total_seconds()))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    sign = "+" if is_open else "-"
    if include_seconds:
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"
    return f"{sign}{h:02d}:{m:02d}"


def format_local_clock(dt: datetime, is_12h: bool = False) -> str:
    """Market Sync card clock: '14:32' (24h) or '2:32 PM' (12h)."""
    if is_12h:
        return dt.strftime("%I:%M %p").lstrip("0")
    return dt.strftime("%H:%M")
