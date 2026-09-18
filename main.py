#!/usr/bin/env python3
"""Session Sync — market countdown + news for Linux Mint.

Tray app (PyQt6) with CLI fallback:
  python3 main.py                  -> tray + panel (needs PyQt6)
  python3 main.py --cli            -> text mode, works without Qt
  python3 main.py --cli --market NYSE --news
"""
from __future__ import annotations
import argparse
import sys
import time
from datetime import datetime, timezone

from config import APP_NAME, APP_VERSION, MARKETS, get_market, load_settings, save_settings
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
            nxt = calendar_api.next_event(events, settings["currencies"], settings["min_impact"], now)
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

    settings = load_settings()
    if args.market:
        settings["selected_market"] = args.market
        save_settings(settings)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    if not __import__("PyQt6.QtWidgets", fromlist=["QSystemTrayIcon"]).QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: no system tray detected — panel will still work.", file=sys.stderr)
    ctl = TrayController(app, settings)
    ctl.toggle_panel()  # show panel on launch like the reference app's dropdown
    return app.exec()


def main() -> int:
    ap = argparse.ArgumentParser(prog="session-sync", description="Market countdown + news for Linux Mint")
    ap.add_argument("--market", choices=[m["id"] for m in MARKETS], help="market to track")
    ap.add_argument("--cli", action="store_true", help="text mode (no Qt needed)")
    ap.add_argument("--once", action="store_true", help="with --cli: print once and exit")
    ap.add_argument("--news", action="store_true", help="with --cli: show next news event")
    ap.add_argument("--refresh", action="store_true", help="force-refresh news cache")
    ap.add_argument("--version", action="store_true", help="print version")
    args = ap.parse_args()
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if args.cli or args.once:
        return run_cli(args)
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
