<div align="center">

# 🎌 AnimeAgent

**基于 LangGraph 的多 Agent 动漫追番自动化系统**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![CI](https://github.com/ymxc152/AnimeAgent/actions/workflows/ci.yml/badge.svg)](https://github.com/ymxc152/AnimeAgent/actions/workflows/ci.yml)

</div>

AnimeAgent 将「播出检测 → RSS 智能匹配 → 下载 → 内容分类 → 硬链接整理 → 媒体库刷新 → 消息推送」全流程自动化，中文场景优先使用 **Bangumi** 作为元数据源，并通过 **LangGraph** 编排可观测、可回滚、可人工介入的 Episode 工作流。

> 当前为 MVP（v0.1.0），核心调度与 Web 面板已可用，对话层将在后续版本迭代。当前实现与原始架构规划存在偏差，详见 [`docs/ARCHITECTURE_AND_PLAN.md`](./docs/ARCHITECTURE_AND_PLAN.md) 的「实际实现对照与已知问题」。

---

## ✨ 核心特性

- **LangGraph 编排**：Episode 全生命周期以状态图驱动，支持循环、重试、人工审批断点。
- **中文元数据优先**：Bangumi 为主源，AniList / TMDB 作为 fallback / 交叉验证。
- **智能种子匹配**：规则预过滤 + LLM 语义选择 + 置信度评分，低置信度自动进入人工审批。
- **完整追番流水线**：RSS 抓取 → 种子匹配 → qBittorrent 下载 → 文件硬链接整理 → Emby 刷新 → 通知推送。
- **Web 管理面板**：React 19 + TypeScript + Tailwind CSS，支持订阅管理、发现新番、失败重试、人工审批。
- **定时调度**：APScheduler 驱动，启动预检、定时 tick、每周新番发现。
- **可测试、可扩展**：严格分层（Tool / Service / Node / Memory），默认使用 mock 测试，真实 API 测试可选。

---

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│  Trigger Layer  │ CLI / APScheduler / Web API / Webhook     │
├─────────────────────────────────────────────────────────────┤
│  LangGraph      │ Episode StateGraph                         │
│                 │ fetch_rss → match_torrent → send_download │
│                 │ → poll_download → organize_files          │
│                 │ → refresh_emby → notify                   │
├─────────────────────────────────────────────────────────────┤
│  Tool Layer     │ RSS / qBittorrent / Emby / Bangumi /      │
│                 │ AniList / TMDB / Notify / Filesystem / LLM │
├─────────────────────────────────────────────────────────────┤
│  Memory Layer   │ SQLite + SQLAlchemy 2.0 (async)           │
└─────────────────────────────────────────────────────────────┘
```

详细架构与实施规划见 [`docs/ARCHITECTURE_AND_PLAN.md`](./docs/ARCHITECTURE_AND_PLAN.md)。

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/ymxc152/AnimeAgent.git
cd anime-agent
```

### 2. 创建虚拟环境并安装依赖

推荐使用 `uv`（项目使用 `uv.lock` 锁定依赖）：

```bash
# uv 方式
uv venv
uv sync

# 或 pip 方式
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` / `OPENAI_MODEL` | LLM 用于种子匹配与元数据决策 |
| `QB_HOST` / `QB_USERNAME` / `QB_PASSWORD` | qBittorrent Web UI |
| `EMBY_HOST` / `EMBY_API_KEY` | 媒体库刷新（可选） |
| `MEDIA_LIBRARY_PATH` | 整理后的动漫媒体库根目录 |
| `RSS_DEFAULT_URL` | 默认 RSS 源（如 Nyaa） |

### 4. 启动服务

```bash
# 同时启动 scheduler + Web 面板
python -m anime_agent.main
```

或单独启动 Web 面板：

```bash
uvicorn anime_agent.web:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 打开管理面板。

---

## 🖥️ Web 面板

前端位于 [`frontend/`](./frontend/)，使用 React + Vite + Tailwind CSS：

```bash
cd frontend
npm install
npm run dev      # 开发服务器
npm run build    # 生产构建
npm run test     # Vitest 测试
```

主要页面：

- **Dashboard**：订阅、集数、任务状态统计
- **Subscriptions**：新增 / 编辑 / 删除 / 开关自动下载
- **Episodes**：查看各集状态、重试失败任务、审批低置信度匹配
- **Discovery**：按年份 + 季度浏览新番，一键订阅
- **Tools**：外部工具健康检查

---

## 🛠️ 开发

```bash
# 代码格式化
ruff format

# 代码检查
ruff check anime_agent tests

# 类型检查
mypy anime_agent

# 运行全部 mock 测试（含覆盖率）
pytest

# 运行真实外部 API 测试
pytest -m real_data

# 安装 pre-commit hooks
pre-commit install
```

---

## 📁 项目结构

```
anime-agent/
├── anime_agent/          # 后端主包
│   ├── agents/           # LangGraph 工作流
│   ├── tools/            # 外部工具封装
│   ├── services/         # 业务逻辑
│   ├── memory/           # SQLite ORM 与数据访问
│   ├── utils/            # 日志等工具
│   ├── web.py            # FastAPI 应用
│   ├── main.py           # 入口
│   └── config.py         # Pydantic Settings
├── frontend/             # React + TypeScript 前端
├── tests/                # 测试
├── docs/                 # 架构文档与 ADR
├── .github/workflows/    # CI
├── .env.example          # 环境变量模板
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## 🗺️ 路线图

- [x] Tool / Service / Node 分层架构
- [x] Episode Graph 全流水线串联
- [x] APScheduler 定时调度
- [x] FastAPI + React Web 面板
- [x] 人工审批断点（UI 已就绪，`match_torrent` 触发逻辑待修复）
- [x] Anime Garden 老番/全集 fallback（基础实现，缓存与配置项待补齐）
- [ ] 对话层（自然语言订阅、意图解析、多轮澄清）
- [ ] `process_metadata` 节点（内容分类 + TMDB 验证）
- [ ] `notify_user` 节点与真实通知推送
- [ ] 更多下载器支持（Transmission、Aria2 等）
- [ ] Docker 部署模板
- [ ] 更丰富的通知渠道

---

## ⚠️ 已知问题

- **pytest**：`247 selected, 244 passed, 3 failed`，失败集中在 `match_torrent` 低置信度/人工审批逻辑。
- **Ruff**：27 个 lint 错误，主要在测试文件。
- **MyPy**：10 个类型错误，集中在 `animes_garden_tool.py`、`llm_tool.py`、`web.py`、`runner.py`。
- 完整 Bug 清单与修复优先级见 [`docs/ARCHITECTURE_AND_PLAN.md`](./docs/ARCHITECTURE_AND_PLAN.md)。

## 🤝 贡献

欢迎 Issue 与 PR！请阅读 [`CONTRIBUTING.md`](./CONTRIBUTING.md) 了解代码规范与提交要求。

---

## 📄 许可证

本项目采用 [MIT License](./LICENSE) 开源。

---

## 🙏 致谢

- [Bangumi](https://bgm.tv/)：中文动漫元数据
- [AniList](https://anilist.co/) / [TMDB](https://www.themoviedb.org/)：国际元数据
- [LangGraph](https://langchain-ai.github.io/langgraph/) / [LangChain](https://python.langchain.com/)：Agent 编排
- [FastAPI](https://fastapi.tiangolo.com/) / [React](https://react.dev/)：Web 技术栈
