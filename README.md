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

### 立即执行一次
```bash
.venv/bin/python main.py
```

### 守护进程模式（内置定时调度）
```bash
# 默认每天 09:00 执行
.venv/bin/python main.py --daemon

# 自定义执行时间（24小时制）
.venv/bin/python main.py --daemon --time 18:30
```

### 后台运行
```bash
nohup .venv/bin/python main.py --daemon > trending.log 2>&1 &
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

修改 `main.py` 中的配置变量：

- `DISCORD_WEBHOOK`: Discord webhook 地址
- `SCHEDULE_TIME`: 每日执行时间（默认 09:00）

## 项目结构

```
github-stars-surge/
├── main.py              # 主程序
├── requirements.txt     # Python 依赖
├── README.md            # 说明文档
├── claude.md            # 开发规范
├── .gitignore           # Git 忽略规则
└── trending_history.db  # SQLite 数据库（自动生成）
```
