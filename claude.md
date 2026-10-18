# GitHub Stars Surge - Development Notes

## Overview

Lightweight GitHub Trending tracker. Snapshots daily / weekly / monthly repo lists, optionally notifies Discord, and serves a local history viewer.

## Stack

- Python 3.12+
- requests + BeautifulSoup4 (scrape)
- schedule (daemon)
- SQLite (snapshots)
- Flask (history viewer)

## Interpreter

- `.venv/bin/python`
- `.venv/bin/pip install -r requirements.txt`

## Modules

- `period.py`: ISO period keys and labels (`2026-08-15`, `2026-W33`, `2026-08`)
- `db.py`: snapshot upsert / query
- `scraper.py`: GitHub trending fetch + HTML parse
- `web.py`: Flask app for historical reports
- `api.py`: public JSON API, CORS, docs page, example prompts
- `i18n.py`: English / Chinese UI strings and language cookie
- `main.py`: job, Discord, CLI, scheduler
- `templates/base.html`: shared layout (sticky header, global search, `/` shortcut); `static/app.css` holds all shared styles
- `templates/_macros.html`: repo title / language dot / icon macros (import `with context`)
- `templates/report.html`: day/week/month report page
- `templates/search.html`: global search across all boards (`db.search_repos`)
- `templates/repo.html`: one repo's appearance history and star chart
- `templates/api.html`: public API docs and agent prompts

## Data model

One snapshot per `(time_range, period_key)`. Re-fetching the same week or month replaces that snapshot. A repo is `NEW` when it has not appeared in an earlier period of the same time range.

## Search

`db.search_repos` scores every unique repo in Python (name words, acronym, owner, description words) and caches the candidate list until `_data_version` changes. `/api/v1/repos?q=` keeps the older SQL `LIKE` filter.

Period keys from different ranges (`2026-W40`, `2026-10-08`) do not sort chronologically as strings; order by `fetched_at` when mixing ranges.

## Commands

```bash
.venv/bin/python main.py --now
.venv/bin/python main.py --web
.venv/bin/python main.py --daemon --web --now
.venv/bin/python -m unittest discover -s tests -t .
```

## Notes

1. GitHub HTML selectors can change
2. Discord embeds cap at 25 items
3. Do not commit the SQLite file or `.env`
4. Discord webhook is optional; the web viewer only needs snapshots
