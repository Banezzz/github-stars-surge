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
- Re-fetching the same week or month **merges** into that period's snapshot: repos on the latest scrape come first, and repos that trended earlier in the period but have since dropped off stay listed below them (marked "off board · best #N"). Every raw scrape is also kept in `scrape_runs`
- **Language boards**: besides the main board, the tracker scrapes GitHub's per-language trending pages (`TRENDING_LANGUAGES`). Pick one from the board menu; search and repo history cover all of them, which is how niche repos that never reach the main top 25 still turn up
- `NEW` means the repo had not appeared in an earlier snapshot of that same time range
- Filter the open report by name, language, or NEW only, and re-sort it by rank, star gain, or total stars
- **Search all history** (header box or `/search`, press `/` to focus): one index over every daily / weekly / monthly board. Results are ranked by relevance: exact name, name words across `-`/`_`/camelCase, acronyms (`REA` finds `reverse-engineering-anything`), owner, then description words. CJK descriptions match by substring. Misses suggest close spellings and link to GitHub search
- **Repo history** at `/repo/{owner}/{repo}`: peak stars, best rank, a total-stars chart, and every board appearance linked back to its report
- **Atom feeds** of NEW repos at `/feed.xml` (`range`, `scope`, `q`, `language`), linked from every board and search
- **Star history after trending**: once a day the tracker records star counts from the GitHub API for repos seen in the last 90 days, so the repo chart keeps going after a repo leaves the boards. Set `GITHUB_TOKEN` for 5,000 requests/hour instead of 60
- Light / dark theme follows the OS setting
- An empty scrape does not overwrite that week or month
- Public JSON API and docs are at `/docs` (top-right **API** link)

History only exists after the tracker has been run. GitHub does not expose past trending pages, so older weeks/months cannot be backfilled.

## Public API

No key. CORS is open. Canonical host: `https://ghstar.banez.de`.

Human docs and copy-paste agent prompts: [https://ghstar.banez.de/docs](https://ghstar.banez.de/docs)

Every repository object always includes **name**, **description**, and **url**, in that order. Agents should read the description instead of guessing from the repository name.

```bash
curl https://ghstar.banez.de/api
curl https://ghstar.banez.de/api/v1/overview
curl https://ghstar.banez.de/api/v1/periods
curl "https://ghstar.banez.de/api/v1/search?q=video+generation&limit=1000"
curl "https://ghstar.banez.de/api/v1/repos?fields=card&limit=1000"
```

`GET /api/v1/snapshots/{range}` without a period is only the newest board. For the full history, list `/api/v1/periods` and fetch every `{range}/{period}`. Repo and search lists default to `limit=1000`; if `total` is larger, continue with `offset`.

| Endpoint | Purpose |
|------|------|
| `GET /api` | Catalog, field list, query parameters |
| `GET /api/v1/overview` | Snapshot counts, period span, languages |
| `GET /api/v1/periods` | Time-segmented index (`?range=daily\|weekly\|monthly`) |
| `GET /api/v1/snapshots/{range}` | Latest board for that range |
| `GET /api/v1/snapshots/{range}/{period}` | One stored board |
| `GET /api/v1/repos` | Aggregated unique repositories |
| `GET /api/v1/repos/{owner}/{repo}` | One repo plus appearance history |
| `GET /api/v1/search?q=` | Relevance-ranked search over name, acronym, owner, description, language (`sort=relevance` default) |
| `GET /api/v1/prompts` | Example prompts for AI agents |
| `GET /feed.xml` | Atom feed of NEW repos (`range`, `scope`, `q`, `language`) |

Board endpoints (`periods`, `snapshots`) take `?scope=python` for a language board and default to the main board. `repos` and `search` cover every board unless `scope` is given (`scope=` with no value means the main board only). `overview.scopes` lists the stored language boards.

`fields=card` returns only `name`, `description`, and `url`.

## Database

`trending_history.db` (gitignored):

- `snapshots`: one row per `(time_range, period_key, scope)`; `scope` is `''` for the main board or a language slug
- `snapshot_repos`: rank, name, description, language, star/fork counts, period star gain, `is_new`, plus `best_rank`, `seen_count` and `in_latest` from merging the period's scrapes
- `scrape_runs` / `scrape_run_repos`: every scrape exactly as fetched
- `repo_stars` / `repo_refresh`: daily GitHub API star counts and when each repo was last checked

Older databases are migrated automatically on start.

## Configuration

| Variable | Required | Default | Description |
|------|------|------|------|
| `DISCORD_WEBHOOK` | no | - | Discord webhook URL |
| `DB_PATH` | no | `./trending_history.db` | SQLite file path |
| `SCHEDULE_TIME` | no | `09:00` | Daily fetch time (24h) |
| `WEB_HOST` | no | `0.0.0.0` | History viewer bind address |
| `WEB_PORT` | no | `8765` | History viewer port |
| `PUBLIC_BASE_URL` | no | `https://ghstar.banez.de` | Canonical public API / docs URL |
| `TRENDING_LANGUAGES` | no | `python,typescript,javascript,go,rust,java,c++,jupyter-notebook` | GitHub trending language slugs to scrape as extra boards; empty for the main board only |
| `REQUEST_DELAY` | no | `1.5` | Seconds between trending page requests |
| `GITHUB_TOKEN` | no | - | Token for the star refresh (no scopes needed); raises the API limit from 60 to 5,000/hour |
| `STAR_REFRESH` | no | `1` | `0` turns off the daily GitHub API star refresh |
| `STAR_REFRESH_DAYS` | no | `90` | Refresh repos seen on a board within this many days |
| `STAR_REFRESH_LIMIT` | no | 50 without token, 1000 with | Max repos checked per run |
| `TRUST_PROXY` | no | `0` | Number of reverse proxies whose `X-Forwarded-*` headers to trust |

## Failures and alerts

Trending pages are fetched with exponential backoff (2s, 4s, 8s; `Retry-After` is honoured for 429). A page that loads but parses to zero repos raises an error instead of counting as a quiet day, since that usually means GitHub changed its markup. Failed boards never overwrite stored data. At the end of a run, failures are posted to `DISCORD_WEBHOOK` as one alert, and `main.py --now` exits with status 1 so cron can notice. Only the main boards post NEW repos to Discord, and a repo is announced once per period rather than on every re-scrape.

## Deploy

Run the web app and the scheduler as two processes; both share the SQLite file (WAL mode).

```bash
# web (waitress is in requirements; gunicorn works too on Linux)
.venv/bin/waitress-serve --listen=127.0.0.1:8765 --threads=8 wsgi:app
# or: .venv/bin/gunicorn -w 2 -b 127.0.0.1:8765 wsgi:app

# scheduler: daily scrape + star refresh
.venv/bin/python main.py --daemon

# star refresh on its own
.venv/bin/python main.py --stars
```

`deploy/` has systemd units for both processes and a minimal nginx config. Behind a proxy, set `TRUST_PROXY=1` so links and feeds use the public scheme and host. `main.py --web` also serves with waitress; `--daemon --web` still works for a single box but shares one process.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -t .
```
