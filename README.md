# GitHub Trending Tracker

轻量化的 GitHub Trending 追踪器，自动获取 trending repos 和 developers，发送到 Discord，并在本地记录历史。

## 功能

- 抓取 GitHub Trending Repositories（含语言、stars、forks、今日新增）
- 抓取 GitHub Trending Developers（含 popular repo 和简介）
- 发送格式化消息到 Discord Webhook（含超链接）
- SQLite 本地数据库记录每个 repo/developer 出现在 trending 的历史次数
- 显示 `NEW` 或 `x{count}` 标记表示首次/多次上榜
- 内置 Python 定时调度，无需依赖系统 cron

## 安装

```bash
# 创建虚拟环境
python3 -m venv .venv

# 安装依赖
.venv/bin/pip install -r requirements.txt
```

## 使用

### 交互模式（推荐）
```bash
.venv/bin/python main.py
```
会显示菜单让你选择运行模式：
```
=== GitHub Trending Tracker ===

Select mode:
  1) Run once now
  2) Start daemon (scheduled daily)
  3) Start daemon + run once now
  q) Quit
```

### 命令行模式

```bash
# 立即执行一次
.venv/bin/python main.py --now

# 守护进程模式（默认每天 09:00）
.venv/bin/python main.py --daemon

# 自定义时间
.venv/bin/python main.py --daemon --time 18:30

# 启动时先执行一次，然后按计划调度
.venv/bin/python main.py --daemon --now
```

### 后台运行
```bash
nohup .venv/bin/python main.py --daemon --now > trending.log 2>&1 &
```

## Discord 消息格式

### Repositories
```
[owner/repo](url) `NEW`
描述...
`Python | ⭐ 1,234 | 🍴 567 | 📈 123 stars today`
```

### Developers
```
[Display Name](url) `NEW`
📦 [repo-name](url) - repo 简介
```

## 数据库

历史数据存储在 `trending_history.db` (SQLite)：

- `repos` 表：repo 名称、描述、上榜次数、最后出现日期
- `developers` 表：用户名、上榜次数、最后出现日期

## 配置

### 环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 必填：Discord Webhook URL
DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# 可选配置
# DB_PATH=./trending_history.db
# SCHEDULE_TIME=09:00
```

### 配置项说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DISCORD_WEBHOOK` | ✅ | - | Discord webhook URL |
| `DB_PATH` | ❌ | `./trending_history.db` | 数据库文件路径 |
| `SCHEDULE_TIME` | ❌ | `09:00` | 每日执行时间（24小时制） |

> **获取 Discord Webhook**: Discord Server Settings → Integrations → Webhooks → New Webhook

## 项目结构

```
github-stars-surge/
├── main.py              # 主程序
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量模板
├── .env                 # 环境变量配置（需自行创建，已被 gitignore）
├── README.md            # 说明文档
├── claude.md            # 开发规范
├── .gitignore           # Git 忽略规则
└── trending_history.db  # SQLite 数据库（自动生成）
```
