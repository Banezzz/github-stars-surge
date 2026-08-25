"""English / Chinese UI strings for the history viewer and API docs."""

from urllib.parse import urlencode

from flask import request

from period import TIME_RANGES, format_period_label

LANGS = ("en", "zh")
COOKIE = "lang"
COOKIE_MAX_AGE = 366 * 24 * 60 * 60

STRINGS = {
    "en": {
        "site_title": "GitHub Stars Surge",
        "docs_title": "API · GitHub Stars Surge",
        "nav_reports": "Reports",
        "nav_api": "API",
        "nav_site": "Site",
        "lang_en": "EN",
        "lang_zh": "中文",
        "report_subtitle": "Full daily / weekly / monthly trending boards. NEW means first time on that board.",
        "range_daily": "Daily",
        "range_weekly": "Weekly",
        "range_monthly": "Monthly",
        "older": "← Older",
        "newer": "Newer →",
        "filter_placeholder": "Filter name or language",
        "meta_repos": "repos",
        "meta_new": "new",
        "meta_fetched": "fetched",
        "partial_archive": "partial archive",
        "discord_note": "reconstructed from Discord (only first-seen repos were recorded)",
        "badge_new": "NEW",
        "stars_daily": "stars today",
        "stars_weekly": "stars this week",
        "stars_monthly": "stars this month",
        "empty_snapshots": "No {range} snapshots yet.",
        "empty_hint": "Collect a report first:",
        "docs_heading": "Public API",
        "docs_subtitle": "No key. CORS open. Historical GitHub Trending snapshots for people and agents.",
        "docs_lead": (
            "New visitors cannot scrape every past trending board, and a repo name often "
            "hides what the project actually does. This API returns stored snapshots so "
            "an agent can pull the catalog, then read each repo's name, description, and url."
        ),
        "docs_base_url": "Base URL",
        "docs_auth_none": "authentication: none",
        "docs_json_catalog": "JSON catalog",
        "docs_repo_fields": "What every repo object contains",
        "docs_repo_fields_note": "These three fields are always first. Use the description; do not guess from the name.",
        "docs_field": "Field",
        "docs_meaning": "Meaning",
        "docs_field_name": "owner/repo",
        "docs_field_description": "GitHub about text captured with the snapshot",
        "docs_field_url": "Canonical GitHub link",
        "docs_fields_card": "Pass fields=card to return only those three fields.",
        "docs_endpoints": "Endpoints",
        "docs_method": "Method",
        "docs_path": "Path",
        "docs_returns": "Returns",
        "docs_boards": "Time-segmented boards",
        "docs_boards_note": "List stored periods, then fetch one daily / weekly / monthly board.",
        "docs_search": "All repos and keyword search",
        "docs_search_note": (
            "Aggregated unique repositories across history. Keyword search matches "
            "all tokens against name, description, and language."
        ),
        "docs_params": "Query parameters",
        "docs_prompts": "Example agent prompts",
        "docs_prompts_note": "Paste the prompt, the docs URL, and the base URL into an agent. Prompts are also at",
        "copy_prompt": "Copy prompt",
        "copied": "Copied",
        "endpoint_/api": "This catalog",
        "endpoint_/api/v1/overview": "Dataset stats",
        "endpoint_/api/v1/periods": "Time-segmented snapshot index",
        "endpoint_/api/v1/snapshots/{range}": "Latest board for a range",
        "endpoint_/api/v1/snapshots/{range}/{period}": "One stored board",
        "endpoint_/api/v1/repos": "Aggregated unique repositories",
        "endpoint_/api/v1/repos/{owner}/{repo}": "One repo plus appearance history",
        "endpoint_/api/v1/search": "Keyword search across name, description, language",
        "endpoint_/api/v1/prompts": "Ready-to-paste agent prompts",
        "param_range": "daily | weekly | monthly",
        "param_period": "Period key such as 2026-08-15, 2026-W35, or 2026-08",
        "param_q": "Keyword tokens; all tokens must match (AND)",
        "param_language": "Exact GitHub language label, e.g. Python",
        "param_min_stars": "Minimum peak_stars for aggregated repo lists",
        "param_sort": "peak_stars | appearances | first_seen | last_seen | name",
        "param_limit": "1-{max_limit}, default {default_limit}",
        "param_offset": "Pagination offset, default 0",
        "param_fields": "Omit for full objects, or card for only name, description, url",
        "prompt_video-generation-harness": "Research a video generation harness",
        "prompt_agent-stack": "Map a coding-agent / harness stack",
        "prompt_period-digest": "Summarize a time window",
        "prompt_keyword-scan": "Scan history for a topic",
    },
    "zh": {
        "site_title": "GitHub Stars Surge",
        "docs_title": "API · GitHub Stars Surge",
        "nav_reports": "报告",
        "nav_api": "API",
        "nav_site": "站点",
        "lang_en": "EN",
        "lang_zh": "中文",
        "report_subtitle": "完整的日榜 / 周榜 / 月榜。NEW 表示该仓库第一次出现在对应榜单。",
        "range_daily": "日榜",
        "range_weekly": "周榜",
        "range_monthly": "月榜",
        "older": "← 更早",
        "newer": "更新 →",
        "filter_placeholder": "按名称或语言筛选",
        "meta_repos": "个仓库",
        "meta_new": "个新仓库",
        "meta_fetched": "抓取于",
        "partial_archive": "部分归档",
        "discord_note": "从 Discord 还原（当时只记录了首次出现的仓库）",
        "badge_new": "NEW",
        "stars_daily": "今日新增星标",
        "stars_weekly": "本周新增星标",
        "stars_monthly": "本月新增星标",
        "empty_snapshots": "还没有{range}快照。",
        "empty_hint": "先采集一份报告：",
        "docs_heading": "公开 API",
        "docs_subtitle": "无需密钥，开放 CORS。面向人和 Agent 的历史 GitHub Trending 快照。",
        "docs_lead": (
            "新用户很难把过去所有榜单重新扫一遍，仓库名也常常看不出项目在做什么。"
            "这个 API 返回已存储的快照，Agent 可以直接拉取目录，并阅读每个仓库的 "
            "name、description 和 url。"
        ),
        "docs_base_url": "基址",
        "docs_auth_none": "鉴权：无",
        "docs_json_catalog": "JSON 目录",
        "docs_repo_fields": "每个仓库对象包含什么",
        "docs_repo_fields_note": "这三个字段始终排在最前。请阅读简介，不要只靠仓库名猜测用途。",
        "docs_field": "字段",
        "docs_meaning": "含义",
        "docs_field_name": "owner/repo",
        "docs_field_description": "快照时记录的 GitHub 简介",
        "docs_field_url": "GitHub 仓库链接",
        "docs_fields_card": "加上 fields=card 时只返回这三个字段。",
        "docs_endpoints": "接口",
        "docs_method": "方法",
        "docs_path": "路径",
        "docs_returns": "返回",
        "docs_boards": "按时间分段的榜单",
        "docs_boards_note": "先列出已存储的时间段，再拉取某一日 / 周 / 月的完整榜单。",
        "docs_search": "全部仓库与关键词检索",
        "docs_search_note": (
            "跨历史聚合后的去重仓库。关键词检索会用全部词元匹配名称、简介和语言。"
        ),
        "docs_params": "查询参数",
        "docs_prompts": "Agent 示例提示词",
        "docs_prompts_note": "把提示词、文档地址和基址一起交给 Agent。提示词也在",
        "copy_prompt": "复制提示词",
        "copied": "已复制",
        "endpoint_/api": "本目录",
        "endpoint_/api/v1/overview": "数据集统计",
        "endpoint_/api/v1/periods": "按时间分段的快照索引",
        "endpoint_/api/v1/snapshots/{range}": "某时间范围的最新榜单",
        "endpoint_/api/v1/snapshots/{range}/{period}": "指定一期榜单",
        "endpoint_/api/v1/repos": "聚合后的去重仓库",
        "endpoint_/api/v1/repos/{owner}/{repo}": "单个仓库及其上榜历史",
        "endpoint_/api/v1/search": "按名称、简介、语言做关键词检索",
        "endpoint_/api/v1/prompts": "可直接粘贴的 Agent 提示词",
        "param_range": "daily | weekly | monthly",
        "param_period": "时间键，例如 2026-08-15、2026-W35 或 2026-08",
        "param_q": "关键词；所有词元都必须匹配（AND）",
        "param_language": "精确的 GitHub 语言标签，例如 Python",
        "param_min_stars": "聚合列表的最低 peak_stars",
        "param_sort": "peak_stars | appearances | first_seen | last_seen | name",
        "param_limit": "1-{max_limit}，默认 {default_limit}",
        "param_offset": "分页偏移，默认 0",
        "param_fields": "省略则返回完整对象；card 只返回 name、description、url",
        "prompt_video-generation-harness": "调研视频生成 harness",
        "prompt_agent-stack": "梳理编程 Agent / harness 技术栈",
        "prompt_period-digest": "汇总某一时间窗口",
        "prompt_keyword-scan": "按主题扫描历史仓库",
    },
}


def normalize_lang(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().lower().replace("_", "-")
    if raw in {"zh", "zh-cn", "zh-hans", "cn"}:
        return "zh"
    if raw in {"en", "en-us", "en-gb"}:
        return "en"
    if raw.startswith("zh"):
        return "zh"
    if raw.startswith("en"):
        return "en"
    return None


def current_lang() -> str:
    for candidate in (
        request.args.get("lang"),
        request.cookies.get(COOKIE),
    ):
        lang = normalize_lang(candidate)
        if lang:
            return lang
    accept = request.headers.get("Accept-Language") or ""
    for part in accept.split(","):
        lang = normalize_lang(part.split(";")[0])
        if lang:
            return lang
    return "en"


def translate(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(lang) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key) or key
    return text.format(**kwargs) if kwargs else text


def href(path: str, lang: str | None = None, **params) -> str:
    """Build an internal URL that keeps the current UI language."""
    query = {key: value for key, value in params.items() if value not in (None, "")}
    query["lang"] = lang or current_lang()
    return f"{path}?{urlencode(query)}"


def switch_href(lang: str) -> str:
    params = request.args.to_dict(flat=True)
    params["lang"] = lang
    encoded = urlencode(params)
    return f"{request.path}?{encoded}" if encoded else f"{request.path}?lang={lang}"


def range_labels(lang: str) -> dict[str, str]:
    return {name: translate(lang, f"range_{name}") for name in TIME_RANGES}


def stars_label(lang: str, time_range: str) -> str:
    return translate(lang, f"stars_{time_range}")


def localize_period_labels(
    time_range: str,
    periods: list[dict],
    report: dict | None,
    lang: str,
) -> tuple[list[dict], dict | None]:
    """Relabel period chrome for the UI without changing stored repo text."""
    localized = [
        {**item, "label": format_period_label(time_range, item["period_key"], lang=lang)}
        for item in periods
    ]
    if report:
        report = {
            **report,
            "label": format_period_label(time_range, report["period_key"], lang=lang),
        }
    return localized, report


def register(app) -> None:
    @app.context_processor
    def inject_i18n():
        lang = current_lang()
        return {
            "lang": lang,
            "html_lang": "zh-CN" if lang == "zh" else "en",
            "t": lambda key, **kwargs: translate(lang, key, **kwargs),
            "href_reports": href("/", lang=lang),
            "href_docs": href("/docs", lang=lang),
            "href_lang_en": switch_href("en"),
            "href_lang_zh": switch_href("zh"),
            "page_href": lambda path, **params: href(path, lang=lang, **params),
        }

    @app.after_request
    def persist_lang(response):
        if not request.path.startswith("/api"):
            response.set_cookie(
                COOKIE,
                current_lang(),
                max_age=COOKIE_MAX_AGE,
                path="/",
                samesite="Lax",
            )
        return response
