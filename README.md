# GitHub Stars Surge

Lightweight GitHub Trending tracker. It snapshots daily / weekly / monthly trending repositories, can send **new** entries to Discord, and serves a local web page for browsing historical ⭐ reports.

## What it does

- Scrapes GitHub Trending repositories for `daily`, `weekly`, and `monthly`
- Stores each period as a snapshot in SQLite (stars, forks, language, rank, first-seen flag)
- Optional Discord webhook for newly seen repos in each time range
- Local web viewer to flip through historical weeks and months

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

`DISCORD_WEBHOOK` is optional. Without it, fetches still write snapshots you can open in the web viewer.

## Usage

```bash
# Fetch current daily / weekly / monthly lists once
.venv/bin/python main.py --now

# Browse stored history (default http://127.0.0.1:8765)
.venv/bin/python main.py --web

# Daily scheduler, then keep the viewer running
.venv/bin/python main.py --daemon --web --now
```

Interactive menu:

```bash
.venv/bin/python main.py
```

```
=== GitHub Trending Tracker ===

Select mode:
  1) Run once now
  2) Start daemon (scheduled daily)
  3) Start daemon + run once now
  4) Open history web viewer
  q) Quit
```

## History web viewer

The viewer reads snapshots from SQLite. Use the Daily / Weekly / Monthly tabs, then pick a stored period or use Older / Newer.

- Weekly keys look like `2026-W33` (ISO week)
- Monthly keys look like `2026-08`
- Re-fetching the same week or month updates that period's snapshot instead of duplicating it
- `NEW` means the repo had not appeared in an earlier snapshot of that same time range
- Filter the open report by repository name or language
- An empty scrape does not overwrite that week or month

History only exists after the tracker has been run. GitHub does not expose past trending pages, so older weeks/months cannot be backfilled.

## Database

`trending_history.db` (gitignored):

- `snapshots`: one row per `(time_range, period_key)`
- `snapshot_repos`: rank, name, description, language, star/fork counts, period star gain, `is_new`

## Configuration

| Variable | Required | Default | Description |
|------|------|------|------|
| `DISCORD_WEBHOOK` | no | - | Discord webhook URL |
| `DB_PATH` | no | `./trending_history.db` | SQLite file path |
| `SCHEDULE_TIME` | no | `09:00` | Daily fetch time (24h) |
| `WEB_HOST` | no | `0.0.0.0` | History viewer bind address |
| `WEB_PORT` | no | `8765` | History viewer port |

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```
