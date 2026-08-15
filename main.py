#!/usr/bin/env python3
"""
GitHub Trending Tracker
Fetches trending repos, stores historical snapshots, and can notify Discord.
"""

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import schedule
from dotenv import load_dotenv

import db
from period import TIME_RANGE_LABELS, TIME_RANGES
from scraper import fetch_trending_repos
from web import run_web

load_dotenv()

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "trending_history.db"))
GITHUB_BASE = os.getenv("GITHUB_BASE", "https://github.com")
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "09:00")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8765"))
DISCORD_DESCRIPTION_LIMIT = 4000

db.configure(DB_PATH)


def validate_discord():
    """Warn when Discord delivery is unavailable."""
    if not DISCORD_WEBHOOK:
        print("Warning: DISCORD_WEBHOOK is not set. Snapshots will still be saved.")
        print("Discord messages will be skipped.")


def send_discord_message(content: str = None, embeds: list = None):
    """Send message to Discord webhook."""
    if not DISCORD_WEBHOOK:
        return

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=30)
    resp.raise_for_status()


def format_repos_embed(snapshot: dict) -> dict | None:
    """Format NEW repos from a stored snapshot as a Discord embed."""
    new_repos = [repo for repo in snapshot["repos"] if repo["is_new"]]
    if not new_repos:
        return None

    time_label = TIME_RANGE_LABELS.get(snapshot["time_range"], snapshot["time_range"])
    lines = []
    for repo in new_repos[:25]:
        desc = repo["description"]
        if len(desc) > 100:
            desc = desc[:100] + "..."

        stats = []
        if repo.get("language"):
            stats.append(repo["language"])
        if repo.get("total_stars") is not None:
            stats.append(f"⭐ {repo['total_stars']:,}")
        if repo.get("forks") is not None:
            stats.append(f"🍴 {repo['forks']:,}")
        if repo.get("stars_period_label"):
            stats.append(f"📈 {repo['stars_period_label']}")
        stats_line = " | ".join(stats)

        line = f"**[{repo['name']}]({repo['url']})**\n{desc}"
        if stats_line:
            line += f"\n`{stats_line}`"
        lines.append(line)

    description = (
        f"*{len(new_repos)} new out of {len(snapshot['repos'])} total*\n\n"
        + "\n\n".join(lines)
    )
    if len(description) > DISCORD_DESCRIPTION_LIMIT:
        description = description[: DISCORD_DESCRIPTION_LIMIT - 1] + "…"

    return {
        "title": f"🔥 New Trending Repositories ({time_label}) - {snapshot['period_key']}",
        "description": description,
        "color": 0x238636,
    }


def process_time_range(time_range: str) -> dict | None:
    """Fetch, store, and optionally notify one time range. Skip empty scrapes."""
    time_label = TIME_RANGE_LABELS[time_range].lower()
    print(f"\n--- Fetching {time_range} trending ---")
    print(f"Fetching trending repositories ({time_label})...")

    repos = fetch_trending_repos(GITHUB_BASE, time_range)
    print(f"  Found {len(repos)} trending repos")
    if not repos:
        print("  Empty result, not overwriting an existing snapshot")
        return None

    snapshot = db.save_snapshot(time_range, repos)
    print(
        f"  Saved {snapshot['period_key']}: "
        f"{snapshot['new_count']} new / {len(snapshot['repos'])} total"
    )

    repos_embed = format_repos_embed(snapshot)
    if not repos_embed:
        print("  No new repos to report")
        return snapshot

    try:
        send_discord_message(embeds=[repos_embed])
        print("  Repos embed sent!" if DISCORD_WEBHOOK else "  Discord skipped (no webhook)")
    except requests.RequestException as exc:
        print(f"  Discord failed: {exc}")
    return snapshot


def job():
    """Fetch trending lists, store snapshots, and optionally notify Discord."""
    print(f"\n[{datetime.now()}] Starting job...")
    db.init_db()
    validate_discord()

    for time_range in TIME_RANGES:
        try:
            process_time_range(time_range)
        except Exception as exc:
            print(f"  {time_range} failed: {exc}")
        if time_range != TIME_RANGES[-1]:
            time.sleep(1)

    print("\nJob completed!")


def safe_job():
    """Keep the daemon alive if a scheduled run fails."""
    try:
        job()
    except Exception as exc:
        print(f"Job failed: {exc}")


def run_scheduler(run_time: str = SCHEDULE_TIME, run_immediately: bool = False):
    """Run scheduler loop."""
    if run_immediately:
        print("Running job immediately...")
        safe_job()
        print()

    schedule.every().day.at(run_time).do(safe_job)

    next_run = schedule.next_run()
    print(f"Scheduler started. Will run daily at {run_time}")
    print(f"Next scheduled run: {next_run}")
    print("Press Ctrl+C to stop.\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


def start_web(host: str, port: int, background: bool = False) -> None:
    if background:
        thread = threading.Thread(
            target=run_web,
            kwargs={"host": host, "port": port},
            daemon=True,
        )
        thread.start()
        return
    run_web(host=host, port=port)


def interactive_menu():
    """Interactive menu for configuration."""
    print("\n=== GitHub Trending Tracker ===\n")

    print("Select mode:")
    print("  1) Run once now")
    print("  2) Start daemon (scheduled daily)")
    print("  3) Start daemon + run once now")
    print("  4) Open history web viewer")
    print("  q) Quit")

    choice = input("\nChoice [1/2/3/4/q]: ").strip().lower()

    if choice == "q":
        print("Bye!")
        sys.exit(0)
    elif choice == "1":
        job()
    elif choice in ("2", "3"):
        default_time = SCHEDULE_TIME
        time_input = input(f"Schedule time (HH:MM) [{default_time}]: ").strip()
        run_time = time_input if time_input else default_time

        try:
            datetime.strptime(run_time, "%H:%M")
        except ValueError:
            print(f"Invalid time format: {run_time}. Use HH:MM (e.g., 09:00)")
            sys.exit(1)

        run_immediately = choice == "3"
        run_scheduler(run_time, run_immediately)
    elif choice == "4":
        start_web(WEB_HOST, WEB_PORT)
    else:
        print("Invalid choice")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="GitHub Trending Tracker")
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon with built-in scheduler",
    )
    parser.add_argument(
        "--time", "-t",
        default=SCHEDULE_TIME,
        help=f"Schedule time in HH:MM format (default: {SCHEDULE_TIME})",
    )
    parser.add_argument(
        "--now", "-n",
        action="store_true",
        help="Run a fetch immediately",
    )
    parser.add_argument(
        "--web", "-w",
        action="store_true",
        help="Serve the historical report viewer",
    )
    parser.add_argument(
        "--host",
        default=WEB_HOST,
        help=f"Web viewer host (default: {WEB_HOST})",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=WEB_PORT,
        help=f"Web viewer port (default: {WEB_PORT})",
    )
    args = parser.parse_args()

    if len(sys.argv) == 1:
        interactive_menu()
        return

    if args.now and not args.daemon:
        job()

    if args.daemon:
        if args.web:
            start_web(args.host, args.port, background=True)
        run_scheduler(args.time, args.now)
        return

    if args.web:
        start_web(args.host, args.port)
        return

    if not args.now:
        parser.print_help()


if __name__ == "__main__":
    main()
