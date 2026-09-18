# ◉ Session Sync

Free, open-source **market countdown + economic news** for **Linux Mint (Cinnamon)** — inspired by [Market Countdown Times & News](https://apps.apple.com/us/app/market-countdown-times-news/id1668967522?platform=mac) on macOS.

Stays in your panel: live 1-second countdown to open/close, market-local clock, next high-impact event. Click for the dropdown panel with all sessions + news.

![license](https://img.shields.io/badge/license-MIT-green) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![mint](https://img.shields.io/badge/mint-22.x_Cinnamon-87cf3e)

## Features (macOS parity + better)

macOS menu-bar parity, per the [reference app](https://apps.apple.com/us/app/market-countdown-times-news/id1668967522?platform=mac):

| macOS app | Session Sync |
|---|---|
| Menu bar: market symbol | Tray text icon: `LDN 02:14:33` (rendered text, like macOS) |
| Menu bar: countdown to the second | Same, 1 s tick |
| Menu bar: market-local time option | 🕒 toggle: market time ↔ your time (tray + panel) |
| Menu bar: next event at a glance | `• JPY 45m` appended to tray text + tooltip |
| Dropdown: visual timer | Circular progress ring + big mono countdown |
| Dropdown: up-to-date market events | Markets list with hours + per-market countdown |
| Economic news calendar + countdown | News list, each row with local time; NEXT card |
| Bank holidays with details | Footer shows next NYSE closure |
| Dark mode | Light / dark / system themes (🌙 button or tray menu) |
| Real-time notifications | Open/close + high-impact news alerts |

- 🕒 **Customisable tray**: right-click → *Display in tray* toggles symbol / countdown / local time / next event — same four blocks as the mac app.
- 🌍 **5 markets, DST-correct** (better than hardcoded UTC): Sydney, Tokyo, London, New York FX, NYSE (holiday-aware incl. Good Friday, half-days)
- 📰 **Economic calendar, no API key** — ForexFactory weekly feed, cached offline, impact badges, next-event in tray
- 🔔 **Alerts** — market open/close + high-impact news within 15 min (via `notify-send`/`plyer`)
- 🌙 **Weekend/holiday aware** — counts down to next real open, not just midnight
- 🎨 **Mint-Y dark** styling, autostart `.desktop`, CLI fallback

## Quick start (Mint 22)

```bash
chmod +x install.sh
./install.sh
python3 main.py
# text mode (no Qt needed):
python3 main.py --cli --news
python3 main.py --cli --market NYSE --once --news
```

Manual:

```bash
sudo apt install python3-pyqt6 python3-requests libnotify-bin
pip install --user -r requirements.txt   # plyer optional
python3 main.py
```

Right-click tray → switch market / toggle market-local vs system time / refresh news / quit.

## Files

```
main.py          entry (tray + --cli fallback)
config.py        market defs + ~/.config/session-sync/settings.json
markets.py       DST-aware engine + NYSE holidays (stdlib only)
calendar_api.py  ForexFactory feed + ~/.cache/session-sync cache
ui.py            PyQt6 tray + Mint-Y panel
notifier.py      notify-send / plyer alerts
assets/icon.svg  app icon
autostart/       Cinnamon autostart entry
```

## Settings

`~/.config/session-sync/settings.json` — `selected_market`, `time_mode` (`market_local`|`system`), `currencies`, `min_impact`, `alerts_enabled`, `alert_minutes_before`, `news_refresh_minutes`.

## Data & credit

- Session hours modelled on the reference app (Sydney 21–06 UTC, Tokyo 00–09 UTC, London 07–16 UTC, NY 12–21 UTC, NYSE 13:30–20 UTC) but stored as **market-local times** so DST is right.
- News: `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (ForexFactory/FairEconomy). Not affiliated. For trading decisions always cross-check your broker.

## Contributing / License

PRs welcome. **MIT** — see [LICENSE](LICENSE).
