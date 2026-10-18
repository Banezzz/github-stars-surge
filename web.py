"""Local web viewer for historical trending star reports."""

import os
from collections import Counter
from datetime import date as Date, datetime
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, make_response, render_template, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

import api
import db
import i18n
from period import TIME_RANGES, format_period_label

SEARCH_PAGE_SIZE = 50

# GitHub linguist colors for the languages that show up on Trending most often.
LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Shell": "#89e051",
    "Jupyter Notebook": "#DA5B0B",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Dart": "#00B4AB",
    "Lua": "#000080",
    "Zig": "#ec915c",
    "Elixir": "#6e4a7e",
    "Scala": "#c22d40",
    "Haskell": "#5e5086",
    "MDX": "#fcb32c",
    "Nix": "#7e7eff",
    "Objective-C": "#438eff",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "TeX": "#3D6117",
    "Cuda": "#3A4E3A",
    "Solidity": "#AA6746",
    "Clojure": "#db5855",
    "OCaml": "#ef7a08",
    "Julia": "#a270ba",
    "R": "#198CE7",
    "PowerShell": "#012456",
    "Assembly": "#6E4C13",
    "Verilog": "#b2b7f8",
    "Astro": "#ff5a03",
    "Blade": "#f7523f",
}


SCOPE_LABELS = {
    "c++": "C++",
    "c#": "C#",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "jupyter-notebook": "Jupyter Notebook",
    "php": "PHP",
    "html": "HTML",
    "css": "CSS",
}


def scope_label(slug: str) -> str:
    """Display name for a GitHub trending language slug."""
    return SCOPE_LABELS.get(slug) or slug.replace("-", " ").title()


def lang_color(name: str) -> str:
    """Linguist color when known, otherwise a stable hue from the name."""
    if name in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[name]
    hue = sum(ord(char) * (index + 1) for index, char in enumerate(name)) % 360
    return f"hsl({hue}, 45%, 55%)"


def compact_number(value) -> str:
    """12345 -> 12.3k."""
    if value is None:
        return ""
    number = float(value)
    for limit, suffix in ((1_000_000, "m"), (1_000, "k")):
        if abs(number) >= limit:
            return f"{number / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{int(number):,}"


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False
    proxies = int(os.getenv("TRUST_PROXY", "0") or 0)
    if proxies:
        # Behind nginx/caddy: trust X-Forwarded-* from that many hops.
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies
        )
    i18n.register(app)
    api.register(app)
    app.jinja_env.filters["compact"] = compact_number
    app.jinja_env.globals["lang_color"] = lang_color
    app.jinja_env.globals["scope_label"] = scope_label
    css = Path(app.static_folder) / "app.css"
    asset_version = int(css.stat().st_mtime) if css.exists() else 0

    @app.context_processor
    def inject_view_helpers():
        return {"asset_version": asset_version}

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder,
            "favicon.ico",
            mimetype="image/vnd.microsoft.icon",
        )

    @app.route("/")
    def index():
        time_range = request.args.get("range", "weekly")
        if time_range not in TIME_RANGES:
            time_range = "weekly"

        scopes = [item["scope"] for item in db.list_scopes(time_range)]
        scope = (request.args.get("scope") or "").strip().lower()
        if scope not in scopes:
            scope = db.OVERALL

        periods = db.list_periods(time_range, scope)
        selected = request.args.get("period")
        if selected and not any(item["period_key"] == selected for item in periods):
            selected = None
        if not selected and periods:
            selected = periods[0]["period_key"]

        report = db.get_report(time_range, selected, scope) if selected else None
        prev_period, next_period = _neighbors(periods, selected)
        lang = i18n.current_lang()
        periods, report = i18n.localize_period_labels(
            time_range, periods, report, lang
        )
        repos = report["repos"] if report else []
        seen_counts = db.appearance_counts([repo["name"] for repo in repos], time_range)
        gains = [repo["stars_period"] for repo in repos if repo["stars_period"]]
        board_languages = Counter(repo["language"] for repo in repos if repo["language"])

        return render_template(
            "report.html",
            time_range=time_range,
            ranges=TIME_RANGES,
            range_labels=i18n.range_labels(lang),
            periods=periods,
            selected=selected,
            report=report,
            prev_period=prev_period,
            next_period=next_period,
            stars_label=i18n.stars_label(lang, time_range),
            seen_counts=seen_counts,
            max_gain=max(gains) if gains else 0,
            board_languages=board_languages.most_common(),
            scope=scope,
            scopes=scopes,
            feed_href=f"/feed.xml?range={time_range}" + (f"&scope={scope}" if scope else ""),
            active_nav="reports",
        )

    @app.route("/search")
    def search():
        lang = i18n.current_lang()
        query = (request.args.get("q") or "").strip()[:200]
        time_range = request.args.get("range") or None
        if time_range not in TIME_RANGES:
            time_range = None
        language = request.args.get("language") or None
        sort = request.args.get("sort") or "relevance"
        if sort not in db.SEARCH_SORTS:
            sort = "relevance"
        try:
            page = max(1, int(request.args.get("page", 1)))
        except ValueError:
            page = 1

        stats = db.overview()
        results = {"total": 0, "items": []}
        suggestions = []
        browsing = not query and bool(language or time_range)
        if browsing:
            # Filters without keywords list everything that matches them.
            if sort == "relevance":
                sort = "peak_stars"
            results = db.list_unique_repos(
                time_range=time_range,
                language=language,
                sort=sort,
                limit=SEARCH_PAGE_SIZE,
                offset=(page - 1) * SEARCH_PAGE_SIZE,
            )
        elif query:
            results = db.search_repos(
                query,
                time_range=time_range,
                language=language,
                sort=sort,
                limit=SEARCH_PAGE_SIZE,
                offset=(page - 1) * SEARCH_PAGE_SIZE,
            )
            if not results["total"]:
                suggestions = db.suggest_repos(query)
        pages = max(1, -(-results["total"] // SEARCH_PAGE_SIZE))

        return render_template(
            "search.html",
            query=query,
            browsing=browsing,
            search_query=query,
            time_range=time_range,
            language_filter=language,
            sort=sort,
            sorts=db.SEARCH_SORTS,
            page=page,
            pages=pages,
            results=results,
            suggestions=suggestions,
            stats=stats,
            languages=stats["languages"],
            ranges=TIME_RANGES,
            range_labels=i18n.range_labels(lang),
            active_nav="search",
        )

    @app.route("/feed.xml")
    def feed():
        lang = i18n.current_lang()
        time_range = request.args.get("range", "daily")
        if time_range not in TIME_RANGES:
            time_range = "daily"
        scope = (request.args.get("scope") or "").strip().lower()
        query = (request.args.get("q") or "").strip()[:200]
        language = request.args.get("language") or None
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 200))
        except ValueError:
            limit = 50

        entries = []
        for item in db.recent_new_repos(time_range, scope):
            if language and item["language"] != language:
                continue
            if query and not db.matches_query(item, query):
                continue
            entries.append({**item, "updated": _rfc3339(item["seen_at"])})
            if len(entries) >= limit:
                break

        base = api.public_base()
        params = {
            key: value
            for key, value in (("range", time_range), ("scope", scope), ("q", query), ("language", language))
            if value
        }
        title_bits = [i18n.range_labels(lang)[time_range]]
        if scope:
            title_bits.append(scope)
        if language:
            title_bits.append(language)
        if query:
            title_bits.append(f"“{query}”")
        response = make_response(render_template(
            "feed.xml",
            feed_title=f"{t_site(lang)} · NEW · {' · '.join(title_bits)}",
            self_url=f"{base}/feed.xml" + (f"?{urlencode(params)}" if params else ""),
            html_url=f"{base}/?range={time_range}" + (f"&scope={scope}" if scope else ""),
            base_url=base,
            updated=entries[0]["updated"] if entries else _rfc3339(datetime.now().isoformat()),
            entries=entries,
        ))
        response.headers["Content-Type"] = "application/atom+xml; charset=utf-8"
        response.headers["Cache-Control"] = "public, max-age=600"
        return response

    @app.route("/repo/<path:name>")
    def repo_detail(name: str):
        lang = i18n.current_lang()
        repo = db.get_repo_history(name)
        status = 200 if repo else 404
        best_rank = None
        chart = None
        if repo:
            for item in repo["history"]:
                item["label"] = format_period_label(
                    item["time_range"], item["period_key"], lang=lang
                )
            ranks = [item["rank"] for item in repo["history"] if item["rank"]]
            best_rank = min(ranks) if ranks else None
            chart = _star_chart(repo["history"], repo.get("star_history") or [])
        return render_template(
            "repo.html",
            name=name,
            repo=repo,
            best_rank=best_rank,
            chart=chart,
            search_query="",
            range_labels=i18n.range_labels(lang),
            active_nav="search",
        ), status

    return app


def t_site(lang: str) -> str:
    return i18n.translate(lang, "site_title")


def _rfc3339(value: str) -> str:
    """Stored timestamps are naive local time; Atom wants an explicit offset."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = datetime.now()
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec="seconds")


def _neighbors(periods: list[dict], selected: str | None) -> tuple[str | None, str | None]:
    """Return older / newer period keys around the selected period."""
    if not selected:
        return None, None
    keys = [item["period_key"] for item in periods]
    try:
        index = keys.index(selected)
    except ValueError:
        return None, None
    newer = keys[index - 1] if index > 0 else None
    older = keys[index + 1] if index + 1 < len(keys) else None
    return older, newer


def _star_chart(history: list[dict], api_series: list[dict] | None = None) -> dict | None:
    """SVG geometry for total stars over time; None when there is no trend to draw.

    Board snapshots and daily GitHub API counts are merged by date; the API
    count wins on days that have both.
    """
    by_date: dict[str, int] = {}
    for item in history:
        if item["total_stars"] is None:
            continue
        date = (item["fetched_at"] or item["period_key"])[:10]
        by_date[date] = max(by_date.get(date, 0), item["total_stars"])
    for item in api_series or []:
        by_date[item["date"]] = item["stars"]
    if len(by_date) < 2:
        return None

    dates = sorted(by_date)
    values = [by_date[date] for date in dates]
    width, height = 640, 200
    left, right, top, bottom = 52, 12, 10, 24
    low, high = min(values), max(values)
    if low == high:
        low, high = low - 1, high + 1
    pad = (high - low) * 0.08
    low, high = max(0, low - pad), high + pad
    plot_w, plot_h = width - left - right, height - top - bottom

    day0 = Date.fromisoformat(dates[0])
    span = max(1, (Date.fromisoformat(dates[-1]) - day0).days)

    def x_of(date: str) -> float:
        return round(left + plot_w * (Date.fromisoformat(date) - day0).days / span, 1)

    def y_of(value: float) -> float:
        return round(top + plot_h * (1 - (value - low) / (high - low)), 1)

    points = [
        {"x": x_of(date), "y": y_of(value), "date": date, "value": value}
        for date, value in zip(dates, values)
    ]
    line = "M" + " L".join(f"{p['x']},{p['y']}" for p in points)
    baseline = top + plot_h
    area = f"{line} L{points[-1]['x']},{baseline} L{points[0]['x']},{baseline} Z"
    y_ticks = [
        {"y": y_of(value), "label": compact_number(round(value))}
        for value in (low + (high - low) * step / 3 for step in range(4))
    ]
    return {
        "width": width,
        "height": height,
        "left": left,
        "right": right,
        "top": top,
        "baseline": baseline,
        "points": points,
        "line": line,
        "area": area,
        "y_ticks": y_ticks,
        "x_first": dates[0],
        "x_last": dates[-1],
        "has_api": bool(api_series),
    }


def run_web(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Serve with waitress when installed; Flask's dev server is the fallback."""
    db.init_db()
    app = create_app()
    print(f"History viewer: http://127.0.0.1:{port}")
    try:
        from waitress import serve
    except ImportError:
        print("waitress is not installed; using Flask's development server.")
        app.run(host=host, port=port, debug=False)
        return
    serve(app, host=host, port=port, threads=8)
