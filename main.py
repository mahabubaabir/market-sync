#!/usr/bin/env python3
"""Market Sync — market countdown + news for Linux Mint.

Tray app (PyQt6) with CLI fallback:
  python3 main.py                  -> tray + panel (needs PyQt6)
  python3 main.py --cli            -> text mode, works without Qt
  python3 main.py --cli --market NYSE --news
"""
from __future__ import annotations
import argparse
import sys
import time
import signal
from datetime import datetime, timezone

from config import APP_NAME, APP_VERSION, MARKETS, get_market, load_settings, save_settings, app_dir
import markets as engine
import calendar_api


def run_cli(args) -> int:
    settings = load_settings()
    if args.market:
        settings["selected_market"] = args.market
    events, _cached, note = calendar_api.fetch_events(force_refresh=args.refresh)
    print(f"{APP_NAME} v{APP_VERSION} — CLI mode ({note})")
    print("Markets (live, 1s): Ctrl+C to quit\n")
    try:
        while True:
            now = datetime.now(timezone.utc)
            statuses = engine.get_all_statuses(now)
            sel = next((s for s in statuses if s["market"]["id"] == settings["selected_market"]), statuses[0])
            # clear-ish single block
            lines = []
            for s in statuses:
                mark = "●" if s["market"]["id"] == sel["market"]["id"] else " "
                dot = "🟢" if s["is_open"] else "⚪"
                lines.append(f"{mark} {dot} {s['market']['symbol']:5s} {s['market']['name']:14s} "
                             f"{'OPEN ' if s['is_open'] else 'SHUT '} {s['next_label']:6s} {engine.format_countdown(s['countdown'])}")
            nxt = calendar_api.next_event(events, settings["currencies"], settings["min_impact"], now,
                                          settings.get("active_impacts"))
            print("\033c", end="")
            print(f"{APP_NAME} — {sel['market']['name']} {'OPEN' if sel['is_open'] else 'CLOSED'} "
                  f"{sel['next_label']} in {engine.format_countdown(sel['countdown'])}")
            print("-" * 64)
            print("\n".join(lines))
            print("-" * 64)
            print(calendar_api.event_countdown_line(nxt, now) if args.news else f"tip: --news shows next economic event ({note})")
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nbye.")
    return 0


def _send_ipc(cmd: str, timeout_ms: int = 500) -> bool:
    """Send a command to the running Market Sync daemon (applet bridge)."""
    try:
        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtNetwork import QLocalSocket
        from config import IPC_SOCKET_NAME
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication(sys.argv[:1])
        sock = QLocalSocket()
        sock.connectToServer(IPC_SOCKET_NAME)
        if not sock.waitForConnected(timeout_ms):
            return False
        sock.write((cmd + "\n").encode("utf-8"))
        sock.flush()
        sock.waitForBytesWritten(timeout_ms)
        sock.disconnectFromServer()
        return True
    except Exception:
        return False


def _single_instance_or_exit() -> None:
    """Prevent double-launch (two trays = flicker/hang on Cinnamon).

    Retries briefly when relaunched by the updater so the new version can
    take over the lock while the old process is still shutting down.
    """
    import os
    import time
    from config import LOCK_PATH
    retries = 8 if os.environ.get("MARKET_SYNC_RELAUNCH") == "1" else 1
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        import fcntl
        fh = open(LOCK_PATH, "w")
        for _ in range(retries):
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                time.sleep(0.5)
                continue
            # keep handle open for process lifetime
            globals()["_lock_fh"] = fh
            fh.write(str(os.getpid()))
            fh.flush()
            return
        print("Market Sync is already running (tray icon active).", file=sys.stderr)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass


def run_gui(args) -> int:
    try:
        from PyQt6.QtWidgets import QApplication
        from ui import TrayController, HAS_QT
        assert HAS_QT
    except Exception:
        print("PyQt6 not found. Install it for the full tray app:", file=sys.stderr)
        print("  sudo apt install python3-pyqt6        # Mint/Ubuntu (recommended)", file=sys.stderr)
        print("  pip install -r requirements.txt      # or via pip", file=sys.stderr)
        print("\nFalling back to CLI mode. Run with --cli for text output.", file=sys.stderr)
        return run_cli(args)

    _single_instance_or_exit()

    settings = load_settings()
    if args.market:
        settings["selected_market"] = args.market
        save_settings(settings)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    # Application logo: use the squircle app icon for taskbar/window lists
    try:
        import os as _os
        from PyQt6.QtGui import QIcon as _QIcon
        _icon = _os.path.join(app_dir(), "assets", "icon.svg")
        if _os.path.exists(_icon):
            app.setWindowIcon(_QIcon(_icon))
    except Exception:
        pass

    if not __import__("PyQt6.QtWidgets", fromlist=["QSystemTrayIcon"]).QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: no system tray detected — panel will still work.", file=sys.stderr)

    ctl = TrayController(app, settings)

    def handle_signal(signum, frame):
        ctl.quit_app()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Normal launch -> show panel once.
    # --hidden (autostart/background) or saved start_hidden -> tray only.
    # Note: we do NOT persist --hidden into settings, so manual launches
    # stay visible unless the user explicitly ticks "Start hidden in tray".
    hidden_launch = bool(getattr(args, "hidden", False)) or settings.get("start_hidden", False)
    if not hidden_launch:
        ctl.toggle_panel()
    if getattr(args, "open_prefs", False):
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(600, ctl.open_preferences)
    return app.exec()


def main() -> int:
    ap = argparse.ArgumentParser(prog="market-sync", description="Market countdown + news for Linux Mint")
    ap.add_argument("--market", choices=[m["id"] for m in MARKETS], help="market to track")
    ap.add_argument("--cli", action="store_true", help="text mode (no Qt needed)")
    ap.add_argument("--once", action="store_true", help="with --cli: print once and exit")
    ap.add_argument("--news", action="store_true", help="with --cli: show next news event")
    ap.add_argument("--refresh", action="store_true", help="force-refresh news cache")
    ap.add_argument("--hidden", action="store_true", help="start hidden in tray (for autostart/background)")
    ap.add_argument("--check-update", action="store_true", help="check GitHub for a newer release and exit")
    ap.add_argument("--version", action="store_true", help="print version")
    # IPC commands (used by the Cinnamon applet and panel buttons)
    ap.add_argument("--toggle", action="store_true", help="toggle the glass panel (IPC)")
    ap.add_argument("--show", action="store_true", help="show the glass panel (IPC)")
    ap.add_argument("--hide", action="store_true", help="hide the glass panel (IPC)")
    ap.add_argument("--preferences", action="store_true", help="open Preferences (IPC)")
    ap.add_argument("--quit", action="store_true", help="quit the background daemon (IPC)")
    args = ap.parse_args()
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if args.check_update:
        import updater
        res = updater.check_for_update(force=True)
        if res:
            print(f"Update available: v{res.get('version')} ({res.get('tag')})")
            if res.get("deb_url"):
                print(f"  deb:   {res['deb_url']}")
            if res.get("html_url"):
                print(f"  notes: {res['html_url']}")
        else:
            print(f"Up to date (v{APP_VERSION}).")
        return 0
    if args.toggle or args.show or args.hide or args.preferences or args.quit:
        cmd = ("toggle" if args.toggle else
               "show" if args.show else
               "hide" if args.hide else
               "preferences" if args.preferences else "quit")
        if _send_ipc(cmd):
            return 0
        # No daemon running: quit is a no-op; other commands launch the app.
        if cmd == "quit":
            return 0
        args.hidden = False
        args.open_prefs = (cmd == "preferences")
        return run_gui(args)
    if args.cli or args.once:
        return run_cli(args)
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
