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
        "filter_placeholder": "Filter this board",
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
        "nav_search": "Search",
        "search_title": "Search · GitHub Stars Surge",
        "search_heading": "Search all history",
        "search_subtitle": "Every daily, weekly, and monthly board ever stored, in one index.",
        "search_placeholder": "Search all history: name, acronym, owner, description",
        "search_button": "Search",
        "search_hint": "Try a repo name, an owner, an acronym like REA, or words from the description. Every word must match.",
        "search_results": "{total} repos match “{q}”",
        "browse_results": "{total} repos",
        "search_none": "Nothing in the trending history matches “{q}”.",
        "search_none_hint": "It may never have reached a GitHub Trending board while this tracker was running.",
        "search_suggest": "Did you mean",
        "search_on_github": "Search GitHub for “{q}”",
        "stat_unique_repos": "Unique repos",
        "stat_board_entries": "Board entries",
        "peak_gain": "best period",
        "search_top_languages": "Browse by language",
        "filter_all_ranges": "All boards",
        "filter_all_languages": "All languages",
        "sort_label": "Sort",
        "sort_relevance": "Best match",
        "sort_peak_stars": "Most stars",
        "sort_appearances": "Most appearances",
        "sort_last_seen": "Recently trending",
        "sort_first_seen": "First seen",
        "sort_name": "Name",
        "sort_rank": "Board rank",
        "sort_gain": "Star gain",
        "sort_total": "Total stars",
        "new_only": "NEW only",
        "no_board_match": "No repo on this board matches.",
        "search_everywhere": "Search all history for “{q}” →",
        "seen_times": "on {n} boards",
        "peak_stars": "peak",
        "last_seen": "last seen",
        "first_seen": "first seen",
        "page_prev": "← Previous",
        "page_next": "Next →",
        "page_of": "Page {page} of {pages}",
        "repo_title": "{name} · GitHub Stars Surge",
        "repo_on_github": "Open on GitHub",
        "repo_history": "Board appearances",
        "repo_stat_peak": "Peak stars",
        "repo_stat_best_rank": "Best rank",
        "repo_stat_appearances": "Appearances",
        "repo_stat_first": "First seen",
        "repo_stat_last": "Last seen",
        "repo_star_chart": "Total stars at each snapshot",
        "repo_not_found": "“{name}” is not in the trending history.",
        "col_board": "Board",
        "col_period": "Period",
        "col_rank": "Rank",
        "col_stars": "Stars",
        "col_gain": "Gain",
        "shortcut_hint": "Press / to search",
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
        "docs_boards_note": (
            "First list every stored period, then fetch each board. "
            "GET /snapshots/{range} without a period is only the latest slice, not the full history."
        ),
        "docs_search": "All repos and keyword search",
        "docs_search_note": (
            "Aggregated unique repositories across history. Use limit=1000. "
            "If total is larger than the page, keep requesting with offset until you have every item. "
            "Keyword search matches all tokens against name, description, and language."
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
        "endpoint_/api/v1/search": "Relevance-ranked search across name, acronym, description, language",
        "endpoint_/api/v1/prompts": "Ready-to-paste agent prompts",
        "param_range": "daily | weekly | monthly",
        "param_period": "Period key such as 2026-08-15, 2026-W35, or 2026-08",
        "param_q": "Keyword tokens; all tokens must match (AND)",
        "param_language": "Exact GitHub language label, e.g. Python",
        "param_min_stars": "Minimum peak_stars for aggregated repo lists",
        "param_sort": "peak_stars | appearances | first_seen | last_seen | name. /search also accepts relevance, its default",
        "param_limit": "1-{max_limit}, default {default_limit}. Use {max_limit} for a full page",
        "param_offset": "Skip this many rows and request again until you have total items",
        "param_fields": "Omit for full objects, or card for only name, description, url",
        "prompt_video-generation-harness": "Research a video generation harness",
        "prompt_agent-stack": "Map a coding-agent / harness stack",
        "prompt_period-digest": "Summarize a time window",
        "prompt_keyword-scan": "Scan history for a topic",
        "prompt_body_video-generation-harness": (
            "You are helping me design a video generation harness.\n\n"
            "Use the public GitHub Stars Surge API at https://ghstar.banez.de. "
            "No API key is required. Prefer JSON endpoints under /api/v1.\n\n"
            "Pull the FULL history. Do not stop at the latest week or a 200-item page.\n"
            "- Always use limit=1000. Read `total`. If you received fewer items than "
            "total, request again with offset += 1000 until you have everything.\n"
            "- GET /api/v1/periods (no range filter), then GET "
            "/api/v1/snapshots/{range}/{period} for EVERY period_key. "
            "A URL without a period is only the newest board.\n\n"
            "1. GET https://ghstar.banez.de/api/v1/overview\n"
            "2. GET https://ghstar.banez.de/api/v1/repos?limit=1000\n"
            "3. GET https://ghstar.banez.de/api/v1/search?q=video+generation&limit=1000\n"
            "4. Repeat full search for: diffusion, wan, hunyuan, cogvideo, "
            "animate, ffmpeg, comfyui, ltx, kandinsky\n"
            "5. Fetch every daily, weekly, and monthly snapshot from /api/v1/periods\n"
            "6. For the most relevant repos, GET "
            "https://ghstar.banez.de/api/v1/repos/{owner}/{repo}\n\n"
            "Every repo object includes name, description, and url. "
            "Read the description — names alone rarely explain what a repo does. "
            "Prefer high peak_stars and multiple appearances. "
            "Summarize the strongest tools, language, why they keep trending, "
            "and a short clone-first shortlist. Call out gaps this history "
            "does not cover."
        ),
        "prompt_body_agent-stack": (
            "I am choosing libraries for an AI coding agent.\n\n"
            "Query https://ghstar.banez.de/api/v1 with no authentication. "
            "Use the complete catalog, not the latest week.\n\n"
            "Always pass limit=1000 and page with offset until `data.length === total`.\n\n"
            "1. GET /api/v1/repos?limit=1000\n"
            "2. GET /api/v1/search?q=agent+harness&limit=1000\n"
            "3. Also search the full set for: claude, cursor, mcp, playwright, sandbox, eval\n"
            "4. GET /api/v1/repos?language=TypeScript&min_stars=1000&limit=1000\n"
            "5. GET /api/v1/repos?language=Python&min_stars=1000&limit=1000\n"
            "6. GET /api/v1/periods, then GET /api/v1/snapshots/{range}/{period} "
            "for every listed period — do not only pull the latest weekly snapshot\n\n"
            "Group results into: agent runtimes, tool/MCP servers, eval harnesses, "
            "and browser/sandbox runners. Use each repo's description to decide "
            "the group — do not infer purpose from the name. Return a comparison "
            "table with name, description, url, peak stars, first/last seen, "
            "and one-line fit notes."
        ),
        "prompt_body_period-digest": (
            "Write a digest of GitHub trending history. Cover the full stored window, "
            "not only the newest week.\n\n"
            "Base URL: https://ghstar.banez.de (public API, no key).\n\n"
            "1. GET /api/v1/overview\n"
            "2. GET /api/v1/periods  (all ranges)\n"
            "3. GET /api/v1/periods?range=daily, weekly, and monthly\n"
            "4. For every period_key, GET /api/v1/snapshots/{range}/{period}. "
            "Skipping this and calling /snapshots/weekly gives only the latest board.\n"
            "5. GET /api/v1/repos?limit=1000 and page with offset until complete\n"
            "6. Highlight NEW repos and anything with a large stars_period gain.\n\n"
            "Return: top 10 overall, top 10 new, notable language mix, and 5 repos "
            "worth watching next week. Say how many periods you actually fetched."
        ),
        "prompt_body_keyword-scan": (
            "I want every high-signal trending repo related to this topic: "
            "{TOPIC}.\n\n"
            "Use https://ghstar.banez.de/api/v1/search?q={TOPIC}&limit=1000 "
            "and follow up with related keywords you infer from descriptions. "
            "If `total` is greater than the returned page, continue with offset=1000, "
            "2000, ... until the catalog is complete. "
            "Then GET /api/v1/repos/{owner}/{repo} for the top matches.\n"
            "Also GET /api/v1/periods and walk every snapshot so older hits are not missed.\n\n"
            "Every repo object includes name, description, and url. "
            "Judge relevance from the description, not the repository name. "
            "Deduplicate by name. Rank by peak_stars, then appearances. "
            "Return markdown with name, description, url, language, peak stars, "
            "first/last seen, and why it is relevant to {TOPIC}."
        ),
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
        "filter_placeholder": "筛选本榜单",
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
        "nav_search": "搜索",
        "search_title": "搜索 · GitHub Stars Surge",
        "search_heading": "全库搜索",
        "search_subtitle": "所有已存储的日榜、周榜、月榜，统一检索。",
        "search_placeholder": "全库搜索：仓库名、缩写、作者、简介",
        "search_button": "搜索",
        "search_hint": "可以搜仓库名、作者、REA 这样的缩写，或简介里的词。多个词需要同时匹配。",
        "search_results": "共 {total} 个仓库匹配“{q}”",
        "browse_results": "共 {total} 个仓库",
        "search_none": "历史榜单中没有匹配“{q}”的仓库。",
        "search_none_hint": "它可能在本站开始记录之后从未登上 GitHub Trending。",
        "search_suggest": "你是不是要找",
        "search_on_github": "去 GitHub 搜索“{q}”",
        "stat_unique_repos": "不重复仓库",
        "stat_board_entries": "上榜条目",
        "peak_gain": "单期最高",
        "search_top_languages": "按语言浏览",
        "filter_all_ranges": "全部榜单",
        "filter_all_languages": "全部语言",
        "sort_label": "排序",
        "sort_relevance": "最相关",
        "sort_peak_stars": "星标最多",
        "sort_appearances": "上榜次数最多",
        "sort_last_seen": "最近上榜",
        "sort_first_seen": "最早上榜",
        "sort_name": "名称",
        "sort_rank": "榜单排名",
        "sort_gain": "新增星标",
        "sort_total": "总星标",
        "new_only": "只看 NEW",
        "no_board_match": "本榜单没有匹配的仓库。",
        "search_everywhere": "在全部历史中搜索“{q}” →",
        "seen_times": "上榜 {n} 次",
        "peak_stars": "峰值",
        "last_seen": "最近上榜",
        "first_seen": "首次上榜",
        "page_prev": "← 上一页",
        "page_next": "下一页 →",
        "page_of": "第 {page} / {pages} 页",
        "repo_title": "{name} · GitHub Stars Surge",
        "repo_on_github": "在 GitHub 打开",
        "repo_history": "上榜记录",
        "repo_stat_peak": "峰值星标",
        "repo_stat_best_rank": "最佳排名",
        "repo_stat_appearances": "上榜次数",
        "repo_stat_first": "首次上榜",
        "repo_stat_last": "最近上榜",
        "repo_star_chart": "每次快照时的总星标",
        "repo_not_found": "历史榜单中没有“{name}”。",
        "col_board": "榜单",
        "col_period": "周期",
        "col_rank": "排名",
        "col_stars": "星标",
        "col_gain": "新增",
        "shortcut_hint": "按 / 搜索",
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
        "docs_boards_note": (
            "先列出全部已存储时间段，再逐期拉取榜单。"
            "不带 period 的 GET /snapshots/{range} 只是最新一期，不是全量历史。"
        ),
        "docs_search": "全部仓库与关键词检索",
        "docs_search_note": (
            "跨历史聚合后的去重仓库。请使用 limit=1000。"
            "如果 total 大于本页条数，继续用 offset 请求直到拿全。"
            "关键词检索会用全部词元匹配名称、简介和语言。"
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
        "endpoint_/api/v1/search": "按名称、缩写、简介、语言做相关度排序检索",
        "endpoint_/api/v1/prompts": "可直接粘贴的 Agent 提示词",
        "param_range": "daily | weekly | monthly",
        "param_period": "时间键，例如 2026-08-15、2026-W35 或 2026-08",
        "param_q": "关键词；所有词元都必须匹配（AND）",
        "param_language": "精确的 GitHub 语言标签，例如 Python",
        "param_min_stars": "聚合列表的最低 peak_stars",
        "param_sort": "peak_stars | appearances | first_seen | last_seen | name；/search 另支持 relevance（默认）",
        "param_limit": "1-{max_limit}，默认 {default_limit}。全量请用 {max_limit}",
        "param_offset": "跳过已取到的条数，继续请求直到凑齐 total",
        "param_fields": "省略则返回完整对象；card 只返回 name、description、url",
        "prompt_video-generation-harness": "调研视频生成 harness",
        "prompt_agent-stack": "梳理编程 Agent / harness 技术栈",
        "prompt_period-digest": "汇总某一时间窗口",
        "prompt_keyword-scan": "按主题扫描历史仓库",
        "prompt_body_video-generation-harness": (
            "请帮我设计一套视频生成 harness。\n\n"
            "使用 GitHub Stars Surge 公开 API：https://ghstar.banez.de 。"
            "不需要 API key。优先请求 /api/v1 下的 JSON 接口。\n\n"
            "必须拉全量历史，不要只看最新一周或 limit=200 的一页。\n"
            "- 一律使用 limit=1000。读取 `total`。如果返回条数小于 total，"
            "用 offset += 1000 继续请求直到拿全。\n"
            "- 先 GET /api/v1/periods（不要加 range 过滤），再对每一个 "
            "period_key 请求 /api/v1/snapshots/{range}/{period}。"
            "不带 period 的地址只是最新一期。\n\n"
            "1. GET https://ghstar.banez.de/api/v1/overview\n"
            "2. GET https://ghstar.banez.de/api/v1/repos?limit=1000\n"
            "3. GET https://ghstar.banez.de/api/v1/search?q=video+generation&limit=1000\n"
            "4. 再用这些关键词做全量搜索：diffusion, wan, hunyuan, cogvideo, "
            "animate, ffmpeg, comfyui, ltx, kandinsky\n"
            "5. 根据 /api/v1/periods 拉取全部日榜、周榜、月榜\n"
            "6. 对最相关的仓库再请求 "
            "https://ghstar.banez.de/api/v1/repos/{owner}/{repo}\n\n"
            "每个仓库对象都包含 name、description 和 url。"
            "请阅读简介，不要只靠仓库名判断用途。"
            "优先选择 peak_stars 高、多次上榜的仓库。"
            "总结最强的工具、语言、持续上榜的原因，以及一份可以先 clone 的短名单。"
            "并说明这份历史数据覆盖不到的空白。"
        ),
        "prompt_body_agent-stack": (
            "我在为 AI 编程 Agent 挑选库。\n\n"
            "请求 https://ghstar.banez.de/api/v1 ，无需鉴权。"
            "用完整目录，不要只拉最新一周。\n\n"
            "一律带 limit=1000，并用 offset 翻页直到 data 条数等于 total。\n\n"
            "1. GET /api/v1/repos?limit=1000\n"
            "2. GET /api/v1/search?q=agent+harness&limit=1000\n"
            "3. 再对以下词做全量搜索：claude, cursor, mcp, playwright, sandbox, eval\n"
            "4. GET /api/v1/repos?language=TypeScript&min_stars=1000&limit=1000\n"
            "5. GET /api/v1/repos?language=Python&min_stars=1000&limit=1000\n"
            "6. GET /api/v1/periods，然后对列出的每一期请求 "
            "/api/v1/snapshots/{range}/{period}，不要只拉最新周榜\n\n"
            "把结果分成：Agent 运行时、工具/MCP 服务、评测 harness、"
            "以及浏览器/沙箱执行器。根据每个仓库的 description 归类，"
            "不要从名字推断用途。返回对照表，包含 name、description、url、"
            "peak stars、首次/最近出现时间，以及一句适配说明。"
        ),
        "prompt_body_period-digest": (
            "请写一份 GitHub 热门历史摘要。覆盖全部已存储时间段，不要只看最新一周。\n\n"
            "基址：https://ghstar.banez.de （公开 API，无需密钥）。\n\n"
            "1. GET /api/v1/overview\n"
            "2. GET /api/v1/periods（全部 range）\n"
            "3. 再分别 GET /api/v1/periods?range=daily、weekly、monthly\n"
            "4. 对每一个 period_key 请求 /api/v1/snapshots/{range}/{period}。"
            "如果只调用 /snapshots/weekly，拿到的只是最新一期。\n"
            "5. GET /api/v1/repos?limit=1000，不足 total 就继续 offset 翻页\n"
            "6. 重点标出 NEW 仓库，以及 stars_period 涨幅很大的项目。\n\n"
            "请返回：总榜前 10、新上榜前 10、值得注意的语言分布，"
            "以及下周值得继续观察的 5 个仓库。并写明你实际拉取了多少期。"
        ),
        "prompt_body_keyword-scan": (
            "我想找出和这个主题相关、信号足够强的所有热门仓库：{TOPIC}。\n\n"
            "使用 https://ghstar.banez.de/api/v1/search?q={TOPIC}&limit=1000 ，"
            "再根据简介推断相关关键词继续搜索。"
            "如果 `total` 大于本页条数，继续用 offset=1000、2000… 直到拿全。"
            "对排名靠前的结果再请求 /api/v1/repos/{owner}/{repo}。\n"
            "同时 GET /api/v1/periods 并遍历每一期快照，避免漏掉更早的命中。\n\n"
            "每个仓库对象都包含 name、description 和 url。"
            "相关性请看简介，不要只看仓库名。"
            "按仓库名去重。先按 peak_stars，再按 appearances 排序。"
            "用 markdown 返回 name、description、url、语言、peak stars、"
            "首次/最近出现时间，以及它和 {TOPIC} 的关系。"
        ),
    },
}


PROMPT_IDS = (
    "video-generation-harness",
    "agent-stack",
    "period-digest",
    "keyword-scan",
)


def example_prompts(lang: str) -> list[dict]:
    """Localized agent prompts for the docs page and /api/v1/prompts."""
    return [
        {
            "id": prompt_id,
            "title": translate(lang, f"prompt_{prompt_id}"),
            "prompt": translate(lang, f"prompt_body_{prompt_id}"),
            "lang": lang,
        }
        for prompt_id in PROMPT_IDS
    ]


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
            "href_search": href("/search", lang=lang),
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
