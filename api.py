"""Public JSON API for historical trending snapshots."""

import os
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

import db
from period import TIME_RANGE_LABELS, TIME_RANGES

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://ghstar.banez.de").rstrip("/")
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000

EXAMPLE_PROMPTS = [
    {
        "id": "video-generation-harness",
        "title": "Research a video generation harness",
        "prompt": (
            "You are helping me design a video generation harness.\n\n"
            "Use the public GitHub Stars Surge API at https://ghstar.banez.de. "
            "No API key is required. Prefer JSON endpoints under /api/v1.\n\n"
            "1. GET https://ghstar.banez.de/api/v1/overview\n"
            "2. GET https://ghstar.banez.de/api/v1/search?q=video+generation&limit=200\n"
            "3. Repeat search for these keywords: diffusion, wan, hunyuan, cogvideo, "
            "animate, ffmpeg, comfyui, ltx, kandinsky\n"
            "4. GET https://ghstar.banez.de/api/v1/snapshots/weekly\n"
            "5. GET https://ghstar.banez.de/api/v1/snapshots/monthly\n"
            "6. For the most relevant repos, GET "
            "https://ghstar.banez.de/api/v1/repos/{owner}/{repo}\n\n"
            "Every repo object includes name, description, and url. "
            "Read the description — names alone rarely explain what a repo does. "
            "Prefer high peak_stars and multiple appearances. "
            "Summarize the strongest tools, language, why they keep trending, "
            "and a short clone-first shortlist. Call out gaps this history "
            "does not cover."
        ),
    },
    {
        "id": "agent-stack",
        "title": "Map a coding-agent / harness stack",
        "prompt": (
            "I am choosing libraries for an AI coding agent.\n\n"
            "Query https://ghstar.banez.de/api/v1 with no authentication.\n\n"
            "1. GET /api/v1/search?q=agent+harness&limit=200\n"
            "2. Also search: claude, cursor, mcp, playwright, sandbox, eval\n"
            "3. GET /api/v1/repos?language=TypeScript&min_stars=1000&limit=100\n"
            "4. GET /api/v1/repos?language=Python&min_stars=1000&limit=100\n"
            "5. GET /api/v1/periods?range=weekly to see which weeks exist, "
            "then pull a few /api/v1/snapshots/weekly/{period}\n\n"
            "Group results into: agent runtimes, tool/MCP servers, eval harnesses, "
            "and browser/sandbox runners. Use each repo's description to decide "
            "the group — do not infer purpose from the name. Return a comparison "
            "table with name, description, url, peak stars, first/last seen, "
            "and one-line fit notes."
        ),
    },
    {
        "id": "period-digest",
        "title": "Summarize a time window",
        "prompt": (
            "Write a digest of GitHub trending history for a specific window.\n\n"
            "Base URL: https://ghstar.banez.de (public API, no key).\n\n"
            "1. GET /api/v1/periods?range=weekly\n"
            "2. GET /api/v1/periods?range=monthly\n"
            "3. Fetch /api/v1/snapshots/{range}/{period} for the periods I care about. "
            "If I do not name a period, use the latest weekly and monthly snapshots.\n"
            "4. Highlight NEW repos and anything with a large stars_period gain.\n\n"
            "Return: top 10 overall, top 10 new, notable language mix, and 5 repos "
            "worth watching next week."
        ),
    },
    {
        "id": "keyword-scan",
        "title": "Scan history for a topic",
        "prompt": (
            "I want every high-signal trending repo related to this topic: "
            "{TOPIC}.\n\n"
            "Use https://ghstar.banez.de/api/v1/search?q={TOPIC}&limit=200 "
            "and follow up with related keywords you infer from descriptions. "
            "Then GET /api/v1/repos/{owner}/{repo} for the top matches.\n\n"
            "Every repo object includes name, description, and url. "
            "Judge relevance from the description, not the repository name. "
            "Deduplicate by name. Rank by peak_stars, then appearances. "
            "Return markdown with name, description, url, language, peak stars, "
            "first/last seen, and why it is relevant to {TOPIC}."
        ),
    },
]


api_bp = Blueprint("api", __name__)
docs_bp = Blueprint("docs", __name__)


def register(app) -> None:
    """Attach API routes, docs page, and CORS headers."""
    app.register_blueprint(api_bp)
    app.register_blueprint(docs_bp)

    @app.after_request
    def add_cors(response):
        if request.path.startswith("/api"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Content-Type"
            response.headers.setdefault("Cache-Control", "public, max-age=60")
        return response


def public_base() -> str:
    configured = os.getenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL).rstrip("/")
    return configured or request.host_url.rstrip("/")


def _ok(**payload):
    return jsonify({
        "ok": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
    })


def _error(message: str, status: int = 400):
    return jsonify({
        "ok": False,
        "error": message,
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }), status


def _parse_limit(default: int = DEFAULT_LIMIT) -> int | tuple:
    raw = request.args.get("limit", default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _error("limit must be an integer")
    return max(1, min(value, MAX_LIMIT))


def _parse_offset() -> int | tuple:
    raw = request.args.get("offset", 0)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _error("offset must be an integer")
    return max(0, value)


def _parse_min_stars() -> int | None | tuple:
    raw = request.args.get("min_stars")
    if raw is None or raw == "":
        return None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return _error("min_stars must be an integer")


def _optional_range() -> str | None | tuple:
    time_range = request.args.get("range")
    if not time_range:
        return None
    if time_range not in TIME_RANGES:
        return _error(
            f"unknown range '{time_range}'. Use {', '.join(TIME_RANGES)}."
        )
    return time_range


def _failed(result) -> bool:
    return isinstance(result, tuple)


def _wants_card() -> bool:
    return (request.args.get("fields") or "").strip().lower() == "card"


def _maybe_cards(items: list[dict]) -> list[dict]:
    if _wants_card():
        return db.as_repo_cards(items)
    return items


def _catalog() -> dict:
    base = public_base()
    return {
        "name": "GitHub Stars Surge API",
        "version": "1.0",
        "base_url": base,
        "docs_url": f"{base}/docs",
        "openapi_url": f"{base}/api/openapi.json",
        "authentication": "none",
        "description": (
            "Public read-only API over stored GitHub Trending snapshots. "
            "Use it to list every seen repo, pull daily/weekly/monthly boards, "
            "and search by keyword without scraping GitHub yourself. "
            "Every repository object always includes name, description, and url "
            "so agents can tell what a repo does without guessing from the name."
        ),
        "repo_fields": {
            "name": "owner/repo",
            "description": "GitHub about/blurb captured with the snapshot",
            "url": "Canonical GitHub link",
        },
        "endpoints": [
            {"method": "GET", "path": "/api", "description": "This catalog"},
            {"method": "GET", "path": "/api/v1/overview", "description": "Dataset stats"},
            {"method": "GET", "path": "/api/v1/periods", "description": "Time-segmented snapshot index"},
            {"method": "GET", "path": "/api/v1/snapshots/{range}", "description": "Latest board for a range"},
            {"method": "GET", "path": "/api/v1/snapshots/{range}/{period}", "description": "One stored board"},
            {"method": "GET", "path": "/api/v1/repos", "description": "Aggregated unique repositories"},
            {"method": "GET", "path": "/api/v1/repos/{owner}/{repo}", "description": "One repo plus appearance history"},
            {"method": "GET", "path": "/api/v1/search", "description": "Keyword search across name, description, language"},
            {"method": "GET", "path": "/api/v1/prompts", "description": "Ready-to-paste agent prompts"},
        ],
        "query_parameters": {
            "range": "daily | weekly | monthly",
            "period": "Period key such as 2026-08-15, 2026-W35, or 2026-08",
            "q": "Keyword tokens; all tokens must match (AND)",
            "language": "Exact GitHub language label, e.g. Python",
            "min_stars": "Minimum peak_stars for aggregated repo lists",
            "sort": "peak_stars | appearances | first_seen | last_seen | name",
            "limit": f"1-{MAX_LIMIT}, default {DEFAULT_LIMIT}",
            "offset": "Pagination offset, default 0",
            "fields": "Omit for full objects, or card for only name, description, url",
        },
    }


def _openapi() -> dict:
    base = public_base()
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "GitHub Stars Surge API",
            "version": "1.0.0",
            "description": _catalog()["description"],
        },
        "servers": [{"url": base}],
        "paths": {
            "/api": {"get": {"summary": "API catalog"}},
            "/api/v1/overview": {"get": {"summary": "Dataset overview"}},
            "/api/v1/periods": {"get": {"summary": "List stored periods"}},
            "/api/v1/snapshots/{range}": {"get": {"summary": "Latest snapshot for a range"}},
            "/api/v1/snapshots/{range}/{period}": {"get": {"summary": "One snapshot"}},
            "/api/v1/repos": {"get": {"summary": "Aggregated unique repositories"}},
            "/api/v1/repos/{name}": {"get": {"summary": "Repository history"}},
            "/api/v1/search": {"get": {"summary": "Keyword search"}},
            "/api/v1/prompts": {"get": {"summary": "Example agent prompts"}},
        },
    }


@api_bp.route("/api", methods=["GET", "OPTIONS"])
def api_index():
    if request.method == "OPTIONS":
        return ("", 204)
    return _ok(**_catalog())


@api_bp.route("/api/openapi.json")
def openapi_spec():
    return jsonify(_openapi())


@api_bp.route("/api/v1/overview")
def api_overview():
    return _ok(data=db.overview())


@api_bp.route("/api/v1/periods")
def api_periods():
    time_range = _optional_range()
    if _failed(time_range):
        return time_range
    return _ok(range=time_range, data=db.list_all_periods(time_range))


@api_bp.route("/api/v1/snapshots/<time_range>", defaults={"period": None})
@api_bp.route("/api/v1/snapshots/<time_range>/<period>")
def api_snapshot(time_range: str, period: str | None):
    if time_range not in TIME_RANGES:
        return _error(f"unknown range '{time_range}'. Use {', '.join(TIME_RANGES)}.")
    report = db.get_report(time_range, period)
    if not report:
        label = period or "latest"
        return _error(f"no snapshot for {time_range}/{label}", 404)
    if _wants_card():
        report = {**report, "repos": db.as_repo_cards(report["repos"])}
    return _ok(data=report)


@api_bp.route("/api/v1/repos")
def api_repos():
    time_range = _optional_range()
    if _failed(time_range):
        return time_range
    limit = _parse_limit()
    if _failed(limit):
        return limit
    offset = _parse_offset()
    if _failed(offset):
        return offset
    min_stars = _parse_min_stars()
    if _failed(min_stars):
        return min_stars

    sort = request.args.get("sort", "peak_stars")
    if sort not in db.REPO_SORTS:
        return _error(f"unknown sort '{sort}'. Use {', '.join(db.REPO_SORTS)}.")

    try:
        result = db.list_unique_repos(
            keyword=request.args.get("q"),
            time_range=time_range,
            period=request.args.get("period"),
            language=request.args.get("language"),
            min_stars=min_stars,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        return _error(str(exc))

    return _ok(
        total=result["total"],
        limit=limit,
        offset=offset,
        sort=sort,
        data=_maybe_cards(result["items"]),
    )


@api_bp.route("/api/v1/repos/<path:name>")
def api_repo_detail(name: str):
    report = db.get_repo_history(name)
    if not report:
        return _error(f"repository '{name}' not found", 404)
    if _wants_card():
        report = db.repo_card(report)
    return _ok(data=report)


@api_bp.route("/api/v1/search")
def api_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return _error("q is required")

    time_range = _optional_range()
    if _failed(time_range):
        return time_range
    limit = _parse_limit()
    if _failed(limit):
        return limit
    offset = _parse_offset()
    if _failed(offset):
        return offset
    min_stars = _parse_min_stars()
    if _failed(min_stars):
        return min_stars

    sort = request.args.get("sort", "peak_stars")
    if sort not in db.REPO_SORTS:
        return _error(f"unknown sort '{sort}'. Use {', '.join(db.REPO_SORTS)}.")

    result = db.list_unique_repos(
        keyword=query,
        time_range=time_range,
        period=request.args.get("period"),
        language=request.args.get("language"),
        min_stars=min_stars,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return _ok(
        q=query,
        total=result["total"],
        limit=limit,
        offset=offset,
        sort=sort,
        data=_maybe_cards(result["items"]),
    )


@api_bp.route("/api/v1/prompts")
def api_prompts():
    return _ok(data=EXAMPLE_PROMPTS)


@docs_bp.route("/docs")
def docs_page():
    return render_template(
        "api.html",
        base_url=public_base(),
        ranges=TIME_RANGES,
        range_labels=TIME_RANGE_LABELS,
        prompts=EXAMPLE_PROMPTS,
        default_limit=DEFAULT_LIMIT,
        max_limit=MAX_LIMIT,
        catalog=_catalog(),
    )
