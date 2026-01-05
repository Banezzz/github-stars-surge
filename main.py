#!/usr/bin/env python3
"""
GitHub Trending Tracker
Fetches trending repos and developers, sends to Discord, tracks history locally.
"""

import argparse
import sqlite3
import time
import requests
import schedule
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# Configuration
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1457746276463542314/VfwiXrVwAjR24oDKj3wfc7jMq8GAUcpTz_KKv-GQdOtl9c0nHQiEHuC_O8GjBw8iiYca"
DB_PATH = Path(__file__).parent / "trending_history.db"
GITHUB_BASE = "https://github.com"
SCHEDULE_TIME = "09:00"  # 每天执行时间（24小时制）

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ============== Database ==============
def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            name TEXT PRIMARY KEY,
            description TEXT,
            trending_count INTEGER DEFAULT 0,
            last_seen DATE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS developers (
            username TEXT PRIMARY KEY,
            trending_count INTEGER DEFAULT 0,
            last_seen DATE
        )
    """)
    conn.commit()
    conn.close()


def update_repo(name: str, description: str):
    """Update repo in database, increment trending count."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    c.execute("SELECT trending_count FROM repos WHERE name = ?", (name,))
    row = c.fetchone()

    if row:
        c.execute(
            "UPDATE repos SET trending_count = trending_count + 1, description = ?, last_seen = ? WHERE name = ?",
            (description, today, name)
        )
        count = row[0] + 1
    else:
        c.execute(
            "INSERT INTO repos (name, description, trending_count, last_seen) VALUES (?, ?, 1, ?)",
            (name, description, today)
        )
        count = 1

    conn.commit()
    conn.close()
    return count


def update_developer(username: str):
    """Update developer in database, increment trending count."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    c.execute("SELECT trending_count FROM developers WHERE username = ?", (username,))
    row = c.fetchone()

    if row:
        c.execute(
            "UPDATE developers SET trending_count = trending_count + 1, last_seen = ? WHERE username = ?",
            (today, username)
        )
        count = row[0] + 1
    else:
        c.execute(
            "INSERT INTO developers (username, trending_count, last_seen) VALUES (?, 1, ?)",
            (username, today)
        )
        count = 1

    conn.commit()
    conn.close()
    return count


# ============== GitHub Scraper ==============
def fetch_trending_repos(time_range: str = "daily") -> list:
    """Fetch trending repositories from GitHub."""
    url = f"{GITHUB_BASE}/trending?since={time_range}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    repos = []

    for article in soup.select("article.Box-row"):
        # Get repo name (owner/repo)
        h2 = article.select_one("h2 a")
        if not h2:
            continue

        name = h2.get("href", "").strip("/")
        if not name:
            continue

        # Get description
        desc_elem = article.select_one("p")
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Get language
        lang_elem = article.select_one("[itemprop='programmingLanguage']")
        language = lang_elem.get_text(strip=True) if lang_elem else ""

        # Get total stars and forks from the link elements
        links = article.select("a.Link--muted.d-inline-block.mr-3")
        total_stars = ""
        forks = ""
        for link in links:
            href = link.get("href", "")
            text = link.get_text(strip=True).replace(",", "")
            if "/stargazers" in href:
                total_stars = text
            elif "/forks" in href:
                forks = text

        # Get stars today
        stars_today_elem = article.select_one("span.d-inline-block.float-sm-right")
        stars_today = stars_today_elem.get_text(strip=True) if stars_today_elem else ""

        repos.append({
            "name": name,
            "description": description,
            "language": language,
            "total_stars": total_stars,
            "forks": forks,
            "stars_today": stars_today,
            "url": f"{GITHUB_BASE}/{name}"
        })

    return repos


def fetch_trending_developers(time_range: str = "daily") -> list:
    """Fetch trending developers from GitHub."""
    url = f"{GITHUB_BASE}/trending/developers?since={time_range}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    developers = []

    for article in soup.select("article.Box-row"):
        # Get display name from h1.h3
        name_elem = article.select_one("h1.h3 a")
        if not name_elem:
            continue
        display_name = name_elem.get_text(strip=True)
        profile_href = name_elem.get("href", "").strip("/")

        # Get username from p.f4
        username_elem = article.select_one("p.f4 a")
        username = username_elem.get_text(strip=True) if username_elem else profile_href

        # Get popular repo from inner article
        inner_article = article.select_one("article")
        popular_repo = ""
        repo_desc = ""
        if inner_article:
            repo_link = inner_article.select_one("h1.h4 a")
            if repo_link:
                popular_repo = repo_link.get("href", "").strip("/")
            desc_elem = inner_article.select_one("div.f6.color-fg-muted.mt-1")
            if desc_elem:
                repo_desc = desc_elem.get_text(strip=True)

        developers.append({
            "username": username,
            "display_name": display_name,
            "popular_repo": popular_repo,
            "repo_description": repo_desc,
            "url": f"{GITHUB_BASE}/{profile_href}"
        })

    return developers


# ============== Discord ==============
def send_discord_message(content: str = None, embeds: list = None):
    """Send message to Discord webhook."""
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=30)
    resp.raise_for_status()


def format_repos_embed(repos: list) -> dict:
    """Format repos as Discord embed."""
    today = datetime.now().strftime("%Y-%m-%d")

    lines = []
    for repo in repos[:25]:  # Discord embed limit
        count = update_repo(repo["name"], repo["description"])
        desc = repo["description"][:100] + "..." if len(repo["description"]) > 100 else repo["description"]
        badge = f" `x{count}`" if count > 1 else " `NEW`"

        # Build stats line: language | stars | forks | stars today
        stats = []
        if repo.get("language"):
            stats.append(repo["language"])
        if repo.get("total_stars"):
            stats.append(f"⭐ {repo['total_stars']}")
        if repo.get("forks"):
            stats.append(f"🍴 {repo['forks']}")
        if repo.get("stars_today"):
            stats.append(f"📈 {repo['stars_today']}")
        stats_line = " | ".join(stats)

        line = f"**[{repo['name']}]({repo['url']})**{badge}\n{desc}"
        if stats_line:
            line += f"\n`{stats_line}`"
        lines.append(line)

    return {
        "title": f"🔥 Trending Repositories - {today}",
        "description": "\n\n".join(lines) if lines else "No trending repos found",
        "color": 0x238636,  # GitHub green
    }


def format_devs_embed(developers: list) -> dict:
    """Format developers as Discord embed."""
    today = datetime.now().strftime("%Y-%m-%d")

    lines = []
    for dev in developers[:25]:  # Discord embed limit
        count = update_developer(dev["username"])
        badge = f" `x{count}`" if count > 1 else " `NEW`"

        line = f"**[{dev['display_name']}]({dev['url']})**{badge}"
        if dev["popular_repo"]:
            repo_name = dev["popular_repo"].split("/")[-1] if "/" in dev["popular_repo"] else dev["popular_repo"]
            repo_url = f"{GITHUB_BASE}/{dev['popular_repo']}"
            repo_desc = dev["repo_description"][:80] + "..." if len(dev["repo_description"]) > 80 else dev["repo_description"]
            line += f"\n📦 [{repo_name}]({repo_url})"
            if repo_desc:
                line += f" - {repo_desc}"
        lines.append(line)

    return {
        "title": f"👨‍💻 Trending Developers - {today}",
        "description": "\n\n".join(lines) if lines else "No trending developers found",
        "color": 0x6e40c9,  # Purple
    }


# ============== Main ==============
def job():
    """Execute trending fetch and send job."""
    print(f"\n[{datetime.now()}] Starting job...")
    init_db()

    print("Fetching trending repositories...")
    repos = fetch_trending_repos()
    print(f"  Found {len(repos)} trending repos")

    print("Fetching trending developers...")
    devs = fetch_trending_developers()
    print(f"  Found {len(devs)} trending developers")

    print("Sending to Discord...")

    if repos:
        repos_embed = format_repos_embed(repos)
        send_discord_message(embeds=[repos_embed])
        print("  Repos embed sent!")

    if devs:
        devs_embed = format_devs_embed(devs)
        send_discord_message(embeds=[devs_embed])
        print("  Developers embed sent!")

    print("Job completed!")


def run_scheduler(run_time: str = SCHEDULE_TIME):
    """Run scheduler loop."""
    print(f"Scheduler started. Will run daily at {run_time}")
    print("Press Ctrl+C to stop.\n")

    schedule.every().day.at(run_time).do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description="GitHub Trending Tracker")
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon with built-in scheduler"
    )
    parser.add_argument(
        "--time", "-t",
        default=SCHEDULE_TIME,
        help=f"Schedule time in HH:MM format (default: {SCHEDULE_TIME})"
    )
    args = parser.parse_args()

    if args.daemon:
        run_scheduler(args.time)
    else:
        job()


if __name__ == "__main__":
    main()
