# ◉ Market Sync

Free, open-source **market countdown + economic news** for the Linux desktop
(Cinnamon / MATE / Xfce / GNOME tray) — inspired by
[Market Countdown Times & News](https://apps.apple.com/us/app/market-countdown-times-news/id1668967522?platform=mac)
on macOS.

Live 1-second countdown to open/close, market-local clock next to your laptop
clock, next high-impact event at a glance. Click the tray icon for the full
panel: all sessions, news with impact filters, all localised.

![license](https://img.shields.io/badge/license-MIT-green) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![mint](https://img.shields.io/badge/mint-22.x_Cinnamon-87cf3e)

## Install (one command)

```bash
curl -sL https://raw.githubusercontent.com/mahabubaabir/market-sync/main/install.sh | sudo bash
```

That downloads the latest `.deb` release and installs it with `apt` —
dependencies (PyQt6, notifications, etc.) are resolved automatically.

- **Launch:** `market-sync` (or press Super → search "Market Sync")
- **At login:** starts silently in the tray (no popup). Disable anytime from
  the panel's "Start on login" checkbox.
- **Quit:** tray icon → right-click → *Quit Market Sync*, or the red
  **Quit app** button in the panel. Closing the terminal never kills it.
- **Uninstall:** `sudo apt remove market-sync`

<details>
<summary>Manual install / build from source</summary>

```bash
git clone https://github.com/mahabubaabir/market-sync
cd market-sync
./build-deb.sh                       # → dist/market-sync_<version>_all.deb
sudo apt install ./dist/market-sync_*_all.deb
```

Dev run without installing:

```bash
sudo apt install python3-pyqt6 python3-requests libnotify-bin
./run.sh                # background, survives closing the terminal
python3 main.py --cli --news          # text mode, no Qt needed
```
</details>

## Screenshots

| Collapsed (dark) | Expanded (dark) | Light | Mint dark | Dark purple |
|---|---|---|---|---|
| ![collapsed](docs/screenshots/panel-dark-collapsed.png) | ![dark](docs/screenshots/panel-dark.png) | ![light](docs/screenshots/panel-light.png) | ![mint](docs/screenshots/panel-mint_dark.png) | ![purple](docs/screenshots/panel-dark_purple.png) |

Preferences (v0.2 layout with live tray preview and per-market routing):

![preferences](docs/screenshots/preferences.png)

Faithful to **Market Sync v0.2**: a 2-column grid of frosted glass market
cards with landmark vector badges (London Eye, Statue of Liberty, Sydney
Opera House, Torii Gate), signed countdowns (`+ 05:18` open / `- 23:42`
closed), OPEN/CLOSED pills and mini progress rings; a brand bar with alerts
bell and preferences; and a collapsible **Up Next** drawer with
`[All] [🔴 High] [🟠 Med] [🟡 Low]` multi-select chips, relative event times
and impact/currency pills.

## Features

| Feature | Notes |
|---|---|
| 5 markets, DST-correct | London, New York, Sydney, Tokyo, NYSE — IANA timezones, not hardcoded UTC |
| Glass design (v0.2) | Frosted translucent panel + cards, landmark badges, no heavy blur effects — smooth on Cinnamon |
| Market cards grid | Clickable 2-column glass cards: signed countdowns, OPEN/CLOSED pills, mini progress rings |
| Active-session brightening | Open sessions glow neon green; closed ones dim to muted slate (toggleable) |
| Up Next drawer | Collapsible v0.2 news drawer: relative times, impact pills, colored currency pills, date bar |
| Timeline clock | Market-local clocks on every card; your laptop clock in the drawer's date bar |
| Tray text | Old style: `● LON +02:14  ○ NYC -05:02` (open + next, bright/dim) or single market |
| Tray icon | Text countdown or the v0.2 logo + status dot |
| Impact chips | `[All] [🔴 High] [🟠 Med] [🟡 Low]` multi-select + currency filter (8 majors); holidays under All |
| Economic calendar | ForexFactory feed, no API key, cached offline |
| Alerts | Open/close pre-alert + high-impact news notifications; 🔔 toggle in the panel |
| Holiday aware | NYSE holidays + early closes computed locally, no pandas |
| 6 themes | System, Light, Dark, Dark Purple, Mint Light, Mint Dark — all in glass |
| Preferences window | v0.2 layout: segmented Layout / Show-time-as / Format / Sessions controls, **live tray preview**, per-market **None / Popup / + Tray** routing, news, startup, updates, quit |
| Market routing | Hide any market's card (`None`), panel-only (`Popup`), or also in the tray loop (`+ Tray`) |
| One-click updates | Notifies on new GitHub release, installs with a password prompt |
| Crash-resilient | Auto-hide panel, single instance, restart-on-crash launcher, cached tray icon |

## Tray interactions

```
Left-click  → panel (grid of market cards + Up Next drawer; ✕ hides it)
Right-click → markets • Preferences… • impact filter • currencies •
              display toggles • themes • left-click behaviour •
              startup • check updates • quit
```

## Auto-updates

The app checks GitHub Releases once a day (and on demand). When a newer
version exists you get a desktop notification, and the tray menu shows
**⬆ Update to vX.Y.Z** — one click downloads the `.deb` and installs it
through a graphical password prompt, then restarts itself.

## Releasing (maintainer)

```bash
# bump APP_VERSION in config.py, then:
git add -A && git commit -m "release v1.0.1"
git tag v1.0.1 && git push origin main --tags
```

GitHub Actions builds the `.deb` and attaches it to the release automatically.
Every installed copy is notified within 24 hours.

## Settings & data

- `~/.config/market-sync/settings.json` — market, theme, filters, toggles
- `~/.cache/market-sync/calendar.json` — news cache (15 min TTL)
- `~/.cache/market-sync/update.json` — update check cache (24 h)
- `~/.cache/market-sync/app.log` — launcher log (rotates at 1 MB)

## Data & credit

- Session hours modelled on the reference app (Sydney 21–06 UTC, Tokyo 00–09
  UTC, London 07–16 UTC, NY 12–21 UTC, NYSE 13:30–20 UTC) but stored as
  **market-local times** so DST is always right.
- News: `https://nfs.faireconomy.media/ff_calendar_thisweek.json`
  (ForexFactory/FairEconomy, free feed). Not affiliated. Always cross-check
  your broker before trading decisions.

## License

**MIT** — see [LICENSE](LICENSE).
