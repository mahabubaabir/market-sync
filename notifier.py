"""Desktop notifications: plyer if available, else notify-send / zenity fallback."""
from __future__ import annotations
import shutil
import subprocess


def _via_notify_send(title: str, message: str) -> bool:
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(["notify-send", "-a", "Session Sync", title, message])
            return True
        except Exception:
            return False
    return False


def notify(title: str, message: str) -> None:
    try:
        from plyer import notification  # type: ignore
        notification.notify(title=title, message=message, app_name="Session Sync", timeout=8)
        return
    except Exception:
        pass
    _via_notify_send(title, message)


class AlertTracker:
    """Fire once per transition to avoid spam."""

    def __init__(self):
        self._last_key: str | None = None
        self._news_ids: set[str] = set()

    def market_key(self, market_id: str, is_open: bool, next_at: str) -> str:
        return f"{market_id}:{'open' if is_open else 'closed'}:{next_at}"

    def should_fire_market(self, key: str) -> bool:
        if key == self._last_key:
            return False
        self._last_key = key
        return True

    def should_fire_news(self, event_id: str) -> bool:
        if event_id in self._news_ids:
            return False
        self._news_ids.add(event_id)
        # keep bounded
        if len(self._news_ids) > 200:
            self._news_ids = set(list(self._news_ids)[-100:])
        return True
