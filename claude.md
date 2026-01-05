# GitHub Trending Tracker - 开发规范

## 项目概述

轻量化 GitHub Trending 追踪器，抓取 trending repos/developers 并发送到 Discord。

## 技术栈

- Python 3.12+
- requests + BeautifulSoup4（网页抓取）
- schedule（定时调度）
- SQLite（本地数据库）

## 环境

- Python 解释器: `.venv/bin/python`
- 依赖安装: `.venv/bin/pip install -r requirements.txt`

## 核心模块

### main.py

单文件架构，包含以下模块：

1. **Database** (init_db, update_repo, update_developer)
   - SQLite 存储，文件路径: `trending_history.db`
   - 记录 trending 历史次数

2. **GitHub Scraper** (fetch_trending_repos, fetch_trending_developers)
   - 抓取 `github.com/trending` 和 `github.com/trending/developers`
   - 解析 HTML 获取 repo/developer 信息

3. **Discord** (send_discord_message, format_repos_embed, format_devs_embed)
   - 格式化为 Discord embed 消息
   - 发送到配置的 webhook

4. **Scheduler** (job, run_scheduler, main)
   - 支持单次执行和守护进程模式
   - 使用 schedule 库实现定时

## 关键选择器（GitHub HTML）

### Trending Repos
- Repo 名称: `article.Box-row h2 a[href]`
- 描述: `article.Box-row p`
- 语言: `[itemprop='programmingLanguage']`
- Stars/Forks: `a.Link--muted.d-inline-block.mr-3`
- Stars today: `span.d-inline-block.float-sm-right`

### Trending Developers
- Display name: `h1.h3 a`
- Username: `p.f4 a`
- Popular repo: `article h1.h4 a`
- Repo description: `article div.f6.color-fg-muted.mt-1`

## 运行命令

```bash
# 单次执行
.venv/bin/python main.py

# 守护进程（每天 09:00）
.venv/bin/python main.py --daemon

# 自定义时间
.venv/bin/python main.py --daemon --time 18:30
```

## 注意事项

1. GitHub 页面结构可能变化，需要更新选择器
2. Discord embed 限制 25 条记录
3. 数据库文件不应提交到 git（已在 .gitignore）
4. Webhook URL 包含敏感信息，生产环境应使用环境变量
