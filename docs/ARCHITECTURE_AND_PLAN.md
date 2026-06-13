# AnimeAgent 架构与 MVP 实施规划

> 本文件记录项目架构共识与 2 周 MVP 实施计划，供最终确认后执行。
>
> **文档状态**：本文档为原始规划；下方已追加「实际实现对照」章节。当前代码与规划存在差距，具体以 `anime_agent/` 实际文件为准。

---

## 实际实现对照与已知问题

> 更新时间：2026-06-13。本节依据当前代码库盘点实现程度与明显缺陷，便于后续迭代时对齐。

### 实现概览

| 组件 | 规划状态 | 实际状态 | 备注 |
|------|----------|----------|------|
| Tool 层（Bangumi、AniList、TMDB、RSS、qB、Emby、Notify、FS、LLM） | ✅ 包含 | ✅ 已实现 | 10 个工具均存在，单元测试覆盖较好。 |
| AnimeGardenTool（老番/全集 fallback） | 后续设计 | ✅ 已实现 | 见 `docs/OLD_ANIME_DOWNLOAD_DESIGN.md`；但缺少缓存与配置项。 |
| Service 层（MetadataResolver、TorrentSelector、ContentFilter、EpisodePlanner、CompletionChecker、HealthCheck、TorrentHealth、DiscoveryService） | ✅ 包含 | ✅ 已实现 | 业务逻辑下沉到 `services/`，可独立测试。 |
| Episode Agent（Episode Graph） | ✅ 核心 | ✅ 已串联 | `fetch_rss → match_torrent → reflect_match → send_download → poll_download → organize_files → refresh_emby`，含 `schedule_resume` / `handle_error` / `human_review`。 |
| Scheduler | ✅ 包含 | ✅ 已实现 | 启动预检、定时 tick、每周新番发现。 |
| Web 面板 | ✅ 原生 HTML/JS | ✅ React/Vite/Tailwind CSS SPA | 功能等效，API 与页面已实现。 |
| 人工断点（human_review） | ✅ 包含 | ✅ 已实现 | `reflect_match` 在持续低置信度或 LLM 失败时最终路由到 `human_review`。 |
| 对话层（Conversational Agent） | ✅ MVP | ❌ 未实现 | `anime_agent/agents/conversational/` 为空；无 NLU / 多轮澄清 / 聊天 API。 |
| 调度层 LangGraph（Orchestrator Graph） | ✅ 保留 | ❌ 未实现 | 调度以 `services/discovery.py` + `services/scheduler.py` 函数实现，非 LangGraph。 |
| `process_metadata` 节点 | ✅ 合并节点 | ❌ 未实现 | 内容分类与 TMDB 验证未落地， organize_files 默认季数为 1。 |
| `notify_user` 节点 | ✅ 包含 | ❌ 未实现 | 仅工具存在，Graph 未调用。 |
| `metrics.py` / `utils/folder.py` | ✅ 预留 | ❌ 未实现 | 计数器、目录规范化均未落地。 |

### 测试现状

- **pytest**：`271 passed, 1 skipped, 14 deselected`（含新增强化 RSS、reflect_match、torrent_health 用例；`test_web/test_frontend.py` 在 `frontend/dist` 不存在时跳过）。
- **Ruff**：通过，无 lint 错误。
- **MyPy**：通过，无类型错误。
- CI 当前为绿色。

### 明显 Bug 与代码问题

1. ~~**`match_torrent` 低置信度 / 无匹配处理未实现**~~ ✅ **已修复**
   - 位置：`anime_agent/agents/episode/nodes/match_torrent.py` + `reflect_match.py`
   - 修复：
     - 置信度 0.5~0.8 时返回 `low_confidence`，进入 `reflect_match`。
     - 有候选但无法匹配时返回 `no_match`，同样进入 `reflect_match` 由 agent 决策是否搜索 AnimeGarden、等待 RSS 或人工审查。
   - 验证：相关 pytest 用例通过。

2. ~~**RSS 查询过于宽泛导致匹配不到任何种子**~~ ✅ **已修复**
   - 位置：`anime_agent/agents/episode/nodes/fetch_rss.py`
   - 修复：`FetchRSSNode` 在调用 Nyaa / AnimeGarden 源时，自动把番剧标题注入到搜索参数中（Nyaa 的 `q`、AnimeGarden 的 `keyword`），缩小候选范围。
   - 验证：新增 URL 构建单元测试。

3. ~~**100% 进度但状态卡在 `downloading` 不进入整理**~~ ✅ **已修复**
   - 位置：`anime_agent/services/torrent_health.py`
   - 修复：只要 `progress >= 1.0` 且不是错误/元数据状态，即视为 `completed`，不再依赖 qBittorrent 的 `uploading/pausedUP/queuedUP` 状态。
   - 验证：新增单元测试。

4. **Episode 模型存在 `torrent_hash` 与 `torrent_info_hash` 双字段**
   - 位置：`anime_agent/memory/models.py:69,72`
   - 现象：`send_download` 写入 `torrent_hash`，`poll_download` 读取 `torrent_hash`，`runner.py` 读取/写入 `torrent_info_hash`。两个字段可能不一致，导致状态混乱。
   - 建议：统一字段名并迁移数据。

5. **`OrganizeFilesNode` 硬编码 `season=1`**
   - 位置：`anime_agent/agents/episode/nodes/organize_files.py:101`
   - 现象：多季番剧全部被整理到 `S01E##`，与架构 §8.9 的 TMDB 季度验证不符。

6. **Scheduler 每 tick 处理所有非终态 Episode**
   - 位置：`anime_agent/services/scheduler.py:140-161`
   - 现象：未根据 `expected_airing_weekday` 与播出时间判断是否已播出，也无错峰调度。与架构 §5.6 Step 7 / §8.2 的"按播出周几智能触发"不符。

7. **Discovery 服务与 Web 端点实现不一致**
   - 位置：`anime_agent/services/discovery.py:48` / `anime_agent/services/metadata_resolver.py:79-87` / `anime_agent/web.py:412-484`
   - 现象：`DiscoveryService` 直接调用 AniList，无 Bangumi fallback；而 Web 发现端点使用 Bangumi calendar 优先，AniList 作为 fallback。两者未统一为"Bangumi 优先"。与架构 §5.2 / §5.6 Step 2 的决策不符。

8. ~~**`PollDownloadNode` 未使用 `TorrentHealth` 服务**~~ ✅ **已修复**
   - 位置：`anime_agent/agents/episode/nodes/poll_download.py:24,53`
   - 修复：节点已实例化 `TorrentHealth` 并调用 `health.evaluate(status)` 辅助判定；轮询间隔仍统一使用 `check_interval_seconds`，自适应间隔尚未实现。

9. **`ScheduleResumeNode` 未区分 RSS 等待与下载轮询间隔**
   - 位置：`anime_agent/agents/episode/nodes/schedule_resume.py:18`
   - 现象：统一使用 `check_interval_seconds`（默认 600 秒），而架构 §8.7 要求 RSS 等待 6 小时、§8.8 要求自适应轮询。

10. **`CompletionChecker` 外部状态分支不可达**
    - 位置：`anime_agent/services/completion_checker.py:44-50`
    - 现象：`all_completed` 已在前面提前返回，导致 `external_status == "FINISHED" and all_completed` 分支永远不会执行。

11. ~~**Web 创建订阅时 `total_episodes=None` 生成 0 集**~~ ✅ **已修复**
    - 位置：`anime_agent/web.py:102`
    - 修复：`total_episodes = payload.total_episodes or details.get("total_episodes") or 12`，缺失时默认按 12 集创建。

12. **`DiscoveryService._create_subscription` 硬编码 12 集兜底**
    - 位置：`anime_agent/services/discovery.py:93`
    - 现象：当 `total_episodes` 缺失时直接按 12 集创建，未在文档中说明。

13. **配置项缺失**
    - `config.py` / `.env.example` 未包含 `OLD_ANIME_DOWNLOAD_DESIGN.md` 规划的 `ANIME_GARDEN_*`、`RESOURCE_FALLBACK_*`、`RESOURCE_SEARCH_MAX_PAGES`。
    - `AnimeGardenTool` 未实现 1 小时关键词缓存。

14. ~~**前端构建产物缺失导致 `test_root_serves_frontend_index` 失败**~~ ✅ **已修复**
    - 位置：`tests/test_web/test_frontend.py:7`
    - 修复：当 `frontend/dist` 不存在时，`test_root_serves_frontend_index` 使用 `@pytest.mark.skipif` 跳过，避免后端测试依赖前端构建产物。
    - 说明：生产/本地使用 Web 面板前仍需执行 `npm run build` 生成 `frontend/dist`。

15. ~~**MyPy / Ruff 失败项**~~ ✅ **已修复**
    - Ruff：清理了 lint 错误（未使用导入、导入排序、`SIM110` 循环改写等）。
    - MyPy：修复了类型错误（`llm_tool.py` 内容类型、`web.py` SQLAlchemy Column 传递、`runner.py` `rss_source_id` 类型等）。`AnimeGardenTool.invoke` 签名与 `BaseTool.invoke` 兼容。

### 与文档规划的主要偏差

| 规划点 | 偏差说明 |
|--------|----------|
| 三层 LangGraph（对话/调度/Episode） | 仅 Episode Graph 实现；对话层、调度层 LangGraph 未实现。 |
| Bangumi 优先 | `MetadataResolver.get_seasonal` 已实现 Bangumi 优先、AniList fallback；DiscoveryService 与 Web 发现端点均走该逻辑。 |
| 按播出周几智能调度 | 未实现播出时间门控；每 tick 扫描所有活跃 Episode。 |
| 人工断点 | `match_torrent` 已实现低置信度计数，`reflect_match` 节点在多次低置信度后路由到 `human_review`；状态与 API 可用。 |
| `process_metadata` 节点 | 未实现； organize_files 直接整理。 |
| 通知用户节点 | 未实现。 |
| 对话查询统计 | 未实现。 |

### 后续建议优先级

- **P0**：~~修复 `match_torrent` 低置信度逻辑；处理前端测试失败；清理 lint/type 错误~~ ✅ **已完成**。
- **P1**：统一 `torrent_hash` / `torrent_info_hash`；`OrganizeFilesNode` 使用 Subscription 真实季数；`PollDownloadNode` 实现自适应轮询间隔。
- **P2**：~~Discovery 改为 Bangumi 优先~~ ✅ **已完成**；Scheduler 增加播出时间门控与错峰调度；实现 `process_metadata` 与 `notify_user` 节点。
- **P3**：实现最小对话层；按 OLD 设计补齐 Anime Garden 缓存、配置项与 StatusQueryService。

---

## 1. 项目定位

**AnimeAgent** 是一个基于 LangGraph 的事件驱动动漫追番自动化系统，目标是将"播出检测 → RSS 智能匹配 → 下载 → 内容分类 → 硬链接整理 → 媒体库刷新 → 消息推送"全流程自动化。

本次交付为 **3 周 MVP**，作为可公开的简历实战项目，优先保证：
1. 架构清晰、可运行、可展示；
2. 中文场景优化：Bangumi 作为优先元数据源；
3. 工作流分层：对话层与调度层解耦；
4. 代码质量与测试覆盖；
5. 文档完整（README + 架构说明 + 部署指南）。

---

## 2. 核心架构决策

| 议题 | 决策 | 说明 |
|------|------|------|
| 编排框架 | LangGraph StateGraph | 用于展示状态机、循环、断点能力，比简单流水线更有区分度 |
| 中文元数据源 | Bangumi 优先 | 中文番剧名、同义词、播出时间更准，AniList/TMDB 作为 fallback |
| 对话层 | 对话层（独立） | 专门处理自然语言交互、意图解析、多轮澄清，与业务调度解耦 |
| 主控层 | 调度层 | 接收结构化意图，负责任务编排、新番发现、订阅创建、调度 |
| 宣传口径 | "LangGraph 编排的工作流 + LLM 决策节点 + 多工作流协作" | 不强行给每个 Node 贴 Agent 标签，实事求是 |
| LLM 角色 | LLM 主导决策 | 种子匹配、内容分类、元数据冲突由 LLM 决策；对话意图解析也走 LLM |
| LLM 可靠性 | Prompt + JSON Schema 约束 + 置信度阈值 | 测试中 mock LLM，生产用置信度过滤 |
| Tool 失败处理 | 统一重试 3 次 + 返回 `ToolOutput(success=False, error=...)` | 可恢复错误不抛异常，业务层决定下一步 |
| 订阅模型 | 一 Subscription 对应一季/一个作品 | 简化 AniList 查询、RSS 匹配、文件整理 |
| State vs DB | 中间产物持久化到 DB | 便于任务恢复、Web 监控、错误重试 |
| 人机协同 | MVP 仅保留"种子匹配置信度低"一个断点 | 其他歧义由 LLM 决策 + 日志记录 |
| Web 面板 | FastAPI 后端 + React/Vite/Tailwind CSS 前端 | 支持表单订阅、发现页、集数管理、工具健康检查；对话层未实现，暂无 NL 聊天。 |
| 运行环境 | Windows 原生运行为主 | 用户 qB/Emby 均在 Windows，Docker 作为可选项 |
| 新番订阅 | 自动订阅当季新番默认开启 | 调度层 每周发现一次，自动创建 Subscription；用户可在 Web 关闭指定番剧的自动下载 |
| MVP 周期 | 3 周 | 三个工作流 + NL + Bangumi 集成 + 完整 Episode Graph 需要更多时间 |
| LLM 供应商 | OpenAI 为主，Ollama 通过 OpenAI 兼容 API 支持 | 配置 `LLM_PROVIDER` 切换 |
| 文件命名 | 内置 Emby/Plex/Jellyfin 兼容模板，配置可覆盖 | 用 Python `str.format`，不引入模板引擎 |
| 通知 | 默认写入日志/DB，apprise 真实通知通过配置可选 | 不阻塞 MVP 核心流程 |
| Emby 刷新 | MVP 保留 | 整理完文件后调用 Emby API 刷新媒体库 |
| 测试 | pytest + mock 为主，`@pytest.mark.integration` + 环境变量支持真实环境 | CI 只跑 mock，本地可切真实 qB/Emby |
| 安全 | `.env` + `.db` 严格 `.gitignore`，启动时校验必填配置 | MVP 不做数据库加密 |

---

## 3. 技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 工作流引擎 | LangGraph | 状态机、循环、断点原生支持 |
| LLM 调用 | LangChain `ChatOpenAI` | 兼容 OpenAI / Ollama / 其他兼容接口 |
| 数据校验 | Pydantic v2 + pydantic-settings | 配置、状态、API 全类型安全 |
| 数据库 | SQLite + SQLAlchemy 2.0 (async) | 零安装、单文件、足够本项目规模 |
| 定时器 | APScheduler | 无需额外消息队列 |
| HTTP 客户端 | httpx (async) | 全异步 IO |
| 中文元数据 | Bangumi API (bgm.tv) | 中文番剧名、播出时间、标签 |
| 国际元数据 | AniList GraphQL + TMDB REST | fallback / 交叉验证 |
| RSS 解析 | feedparser | 标准 RSS/Atom |
| 通知 | apprise | 一行代码覆盖多平台 |
| 下载器 | qbittorrent-api | 官方维护 |
| Web 框架 | FastAPI | 提供 API + 静态前端 |
| 前端 | React + TypeScript + Tailwind CSS | Vite 构建；生产产物位于 `frontend/dist/` |
| 日志 | loguru | 结构化日志、自动轮转 |
| 测试 | pytest + pytest-asyncio + respx/pytest-vcr + coverage | 异步测试、HTTP mock、覆盖率 |
| 代码质量 | Ruff + MyPy + pre-commit | 格式化、lint、类型检查 |
| CI/CD | GitHub Actions | lint / type-check / test |
| 包管理 | Poetry | Windows 稳定 |
| 容器（可选） | Docker + Docker Compose | 不作为 MVP 主路径 |

---

## 4. 目录结构

```
ani-agent/
├── .github/workflows/ci.yml    # GitHub Actions
├── .pre-commit-config.yaml     # pre-commit hooks
├── .env.example                # 环境变量模板
├── .gitignore
├── .gitattributes              # 换行符规范化
├── LICENSE
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── IMPLEMENTATION_PLAN.md      # 原始实施计划（历史）
├── pyproject.toml
├── uv.lock                     # uv 依赖锁定
├── anime_agent.db              # SQLite（gitignored）
├── logs/                       # 日志目录（gitignored）
│
├── anime_agent/
│   ├── __init__.py
│   ├── main.py                 # 系统主入口：init_db + 启动 scheduler
│   ├── web.py                  # FastAPI 应用 + 静态前端
│   ├── web_schemas.py          # Pydantic API schema
│   ├── config.py               # Pydantic Settings
│   │
│   ├── agents/
│   │   ├── conversational/     # 对话层（占位，未实现）
│   │   │   └── __init__.py
│   │   └── episode/            # Episode Graph
│   │       ├── __init__.py
│   │       ├── graph.py        # LangGraph 构建
│   │       ├── runner.py       # Graph 执行与状态持久化
│   │       ├── state.py        # AgentState TypedDict
│   │       └── nodes/          # Episode Graph 节点
│   │           ├── fetch_rss.py
│   │           ├── match_torrent.py
│   │           ├── reflect_match.py
│   │           ├── send_download.py
│   │           ├── poll_download.py
│   │           ├── organize_files.py
│   │           ├── refresh_emby.py
│   │           ├── search_resources.py
│   │           ├── schedule_resume.py
│   │           ├── human_review.py
│   │           └── handle_error.py
│   │
│   ├── services/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── scheduler.py        # APScheduler 封装与 tick 调度
│   │   ├── discovery.py        # 新番发现
│   │   ├── metadata_resolver.py
│   │   ├── content_filter.py
│   │   ├── torrent_selector.py
│   │   ├── torrent_health.py
│   │   ├── episode_planner.py
│   │   ├── completion_checker.py
│   │   └── healthcheck.py
│   │
│   ├── tools/                  # 外部 IO 工具层
│   │   ├── __init__.py
│   │   ├── base.py             # BaseTool, ToolInput, ToolOutput
│   │   ├── llm_tool.py
│   │   ├── bangumi_tool.py
│   │   ├── anilist_tool.py
│   │   ├── tmdb_tool.py
│   │   ├── rss_tool.py
│   │   ├── animes_garden_tool.py
│   │   ├── qb_tool.py
│   │   ├── emby_tool.py
│   │   ├── notify_tool.py
│   │   └── filesystem_tool.py
│   │
│   ├── memory/                 # SQLite ORM 与数据访问
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── store.py
│   │   └── init_db.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py           # loguru 配置
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fakes/                  # 测试替身
│   ├── test_agents/
│   ├── test_services/
│   ├── test_tools/
│   ├── test_memory/
│   ├── test_integration/
│   ├── test_real_data/         # 真实外部 API 测试（默认跳过）
│   ├── test_web/
│   └── test_config_validation.py
│
├── docs/
│   ├── ARCHITECTURE_AND_PLAN.md
│   ├── OLD_ANIME_DOWNLOAD_DESIGN.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── deployment.md
│   └── adr/
│
└── frontend/                   # React + TypeScript + Tailwind CSS 前端
    ├── index.html
    ├── src/
    ├── public/
    ├── package.json
    ├── vite.config.ts
    └── tsconfig*.json
```

---

## 5. 工作流分层设计

为了降低复杂度并实现关注点分离，系统采用 **三层工作流架构**：

1. **对话层**：负责与用户对话，解析意图，处理多轮澄清。
2. **调度层**：接收 对话层 输出的结构化意图，负责新番发现、过滤、订阅创建、任务调度。
3. **Episode Graph（执行层）**：负责单集下载、整理、通知的完整闭环。

### 5.1 为什么分离对话层与调度层？

| 维度 | 对话层 | 调度层 |
|------|----------------------|---------------------|
| 关注点 | 人机交互、自然语言理解、对话状态 | 业务编排、外部系统调用、任务调度 |
| 输入 | 用户原始文本 / 表单 | `ParsedIntent`（结构化意图） |
| 输出 | 回复文本 / 结构化意图 / 澄清问题 | Subscription + Episode + TaskSchedule |
| 替换成本 | 低（可换成 Telegram Bot、Discord Bot） | 高（系统核心） |
| LLM 使用 | 主要用于 NLU 和回复生成 | 主要用于决策节点（匹配、分类等） |

**推荐边界**：
- 对话层 不知道 qBittorrent、RSS、Emby 等细节。
- 调度层 不知道用户是通过聊天还是表单提交的意图。

### 5.2 元数据获取策略：Bangumi 优先

中文场景下，Bangumi（番组计划）在番剧中文名、同义词、播出时间、标签上通常比 AniList 更准确。因此：

1. **搜索/发现**：优先用 `BangumiTool` 搜索中文名；若无结果或 Bangumi 服务不可用，fallback 到 `AniListTool`。
2. **详情查询**：用 `BangumiTool` 获取中文标题、总集数、播出时间、类型、标签；Bangumi 失败时用 AniList 兜底。
3. **交叉验证**：用 `AniListTool` 获取 `anilist_id`、英文/日文名、季度信息。
4. **TMDB**：用于 Emby 媒体库匹配与元数据补充。
5. **Subscription 存储**：同时保存 `bangumi_id` 和 `anilist_id`。

### 5.3 对话层 职责

| 职责 | 说明 | 对应模块 |
|------|------|----------|
| 意图解析 | 从用户输入提取 action + title + season + episodes | `conversational/intent.py` |
| 候选搜索 | 调用 Bangumi/AniList 搜索候选番剧 | `conversational_nodes/search_candidates.py` |
| 多轮澄清 | 信息缺失时询问用户 | `conversational_nodes/ask_clarification.py` |
| 确认执行 | 汇总信息让用户确认 | `conversational_nodes/confirm_action.py` |
| 调用 Orchestrator | 输出 `ParsedIntent` 给 Orchestrator | `conversational_nodes/invoke_orchestrator.py` |

### 5.4 调度层 职责

| 职责 | 说明 | 对应模块 |
|------|------|----------|
| 接收意图 | 解析 `ParsedIntent` | `orchestrator_nodes/parse_intent.py` |
| 新番发现 | 查询 Bangumi/AniList 当季番剧，锁定播出周几 | `orchestrator/discovery.py` |
| 内容过滤 | 按用户规则过滤 OVA、<5min、R18、非动漫类型 | `orchestrator/filter.py` |
| 订阅创建 | 将确认的番剧转为 Subscription + Episodes | `orchestrator_nodes/create_subscriptions.py` |
| 任务调度 | 为每个 Subscription 生成 check 任务 | `orchestrator_nodes/schedule_checks.py` |
| 完结检测 | 检测番剧是否完结、是否全部集下载完成 | `orchestrator/completion.py` |
| 任务触发 | 按调度时间启动 Episode Graph | `scheduler.py` |

### 5.5 用户交互流程（分离后）

**场景 A：用户说"下载葬送的芙莉莲"**

```
用户输入
  │
  ▼
对话层
  │
  ▼
parse_input：识别 action=subscribe, title=葬送的芙莉莲
  │
  ▼
search_candidates：Bangumi 搜索 → 找到《葬送的芙莉莲》
  │
  ▼
ask_clarification：用户未指定集数，回复"找到第 1 季共 28 集，下载全部还是指定集数？"
  │
  ▼
用户回复："全部"
  │
  ▼
confirm_action：生成 ParsedIntent
  │
  ▼
invoke_orchestrator：调用 调度层
  │
  ▼
调度层
  │
  ▼
create_subscriptions：创建 Subscription + 28 Episodes
  │
  ▼
schedule_checks：按播出周几生成 TaskSchedule
  │
  ▼
Scheduler 到点触发 Episode Graph
```

**场景 B：表单直接订阅**

```
Web 表单提交 {title, season, episodes}
  │
  ▼
直接构造 ParsedIntent，跳过 对话层
  │
  ▼
调度层 执行创建/调度
```

### 5.6 新番发现流程（详细过程）

调度层 每周一 00:00 执行一次新番发现任务。整个流程分为：确定目标季度 → 拉取列表 → 过滤 → 交叉验证 → 创建/更新订阅。

#### Step 1：确定目标季度

1. 根据当前日期计算"当前季度"：
   - 1-3 月：冬季（WINTER）
   - 4-6 月：春季（SPRING）
   - 7-9 月：夏季（SUMMER）
   - 10-12 月：秋季（FALL）
2. 默认只发现"当前季度"的新番。未来可扩展为同时发现下一季度（如 7 月时发现 10 月秋季番）。
3. 输出：`target_year` 和 `target_season`。

#### Step 2：拉取 Bangumi 当季番剧列表（含 AniList fallback）

1. **优先尝试 Bangumi**：
   - 调用 `BangumiTool.get_calendar(year, season)` 或搜索 API；
   - Bangumi 返回该季度所有番剧的基础信息：
     - `bangumi_id`
     - 中文名、日文名、英文名
     - 类型（TV/OVA/ONA/Movie）
     - 集数、时长、标签、开播时间。
2. **Bangumi 不可用时的 fallback**：
   - 若 Bangumi 超时/返回错误，自动切换到 `AniListTool.get_seasonal(year, season)`；
   - AniList 返回国际通用数据，缺少中文名，但可作为兜底；
   - 记录日志：`Bangumi 不可用，已 fallback 到 AniList`。
3. 将结果缓存 6 小时，避免同一周内重复调用。

#### Step 3：应用过滤规则

对每部番剧按配置过滤：

| 规则 | 过滤行为 |
|------|----------|
| `exclude_ova=true` | 排除 `format=OVA` |
| `exclude_formats=["ONA"]` | 排除 ONA |
| `min_duration_minutes=5` | 排除单集时长 < 5 分钟 |
| `exclude_genres=["Hentai"]` | 排除 R18/成人向标签 |
| `require_anime_type=true` | 只保留动漫类型 |

**注意**：被过滤的番剧不会创建 Subscription，但会在 Web 面板 Discovery 页的"已过滤"分类中展示，方便用户手动启用。

#### Step 4：交叉验证 AniList

对通过过滤的每部番剧：

1. 用 Bangumi 的日文名/英文名调用 `AniListTool.search()`。
2. 匹配最相似的条目，获取 `anilist_id`、罗马音名、季度信息、`nextAiringEpisode`。
3. 如果 AniList 无结果，仅保存 Bangumi 信息，`anilist_id` 留空。
4. 从开播时间推断播出周几和具体时间，写入 `expected_airing_weekday` / `expected_airing_time`。

#### Step 5：与现有 Subscription 去重（详细）

**目标**：避免同一部番剧被多次订阅，同时保留用户手动设置。

**去重逻辑**：

1. 以 `bangumi_id` 为第一匹配键：
   - 若 Bangumi ID 已存在 → 视为同一番剧；
   - 若 Bangumi ID 不存在但 AniList ID 存在 → 视为同一番剧；
   - 若两者都不存在 → 视为新番剧。

2. **已存在时的处理**：
   - **元数据更新**：
     - 更新 `title_romaji`、`title_native`、`title_chinese`；
     - 更新 `total_episodes`（若 Bangumi/AniList 数据有变化）；
     - 更新 `expected_airing_weekday`、`expected_airing_time`、`airing_timezone`；
     - 更新 `season`、`season_year`。
   - **状态保留**：
     - 不修改 `source` 字段（手动订阅保持 `manual`，自动发现保持 `auto_discover`）；
     - 不修改 `auto_download_enabled`（尊重用户手动开关）；
     - 不删除已有 Episode 记录。
   - **新增集数处理**：
     - 若 `total_episodes` 增加（如 12 → 24 集），为新增集数创建 `pending` 的 Episode；
     - 若 `total_episodes` 减少，不删除已完成 Episode，仅标记超出集数为 `skipped`。

3. **不存在时的处理**：
   - 进入 Step 6 创建新 Subscription。

**示例**：
- 用户手动订阅了《葬送的芙莉莲》并关闭自动下载。
- 一周后 Orchestrator 发现该番剧，因 `bangumi_id` 已存在，仅更新元数据，`auto_download_enabled` 保持 `false`。

#### Step 6：创建 Subscription（自动或仅展示）

**条件判断**：

```python
if settings.filter_auto_subscribe_new_season:
    create_subscription_and_episodes(anime)
else:
    mark_as_discovered_only(anime)
```

**自动创建时（`filter_auto_subscribe_new_season=true`）**：

1. **创建 Subscription 记录**：
   ```python
   subscription = Subscription(
       bangumi_id=anime.bangumi_id,
       anilist_id=anime.anilist_id,
       title_romaji=anime.title_romaji,
       title_native=anime.title_native,
       title_chinese=anime.title_chinese,
       season_year=anime.season_year,
       season=anime.season,
       total_episodes=anime.total_episodes,
       local_folder_name=normalize_folder_name(anime.title_chinese or anime.title_romaji),
       status="ongoing",
       source="auto_discover",
       auto_download_enabled=True,
       expected_airing_weekday=anime.weekday,
       expected_airing_time=anime.air_time,
       airing_timezone=anime.timezone,
   )
   ```

2. **创建 Episode 记录**：
   - 为每一集（1 到 `total_episodes`）创建 `Episode`；
   - 初始状态全部为 `pending`；
   - `episode_number` 按顺序生成；
   - `aired_at` 根据 `expected_airing_weekday` 推算（首播时间 + 7 天 × (episode_number - 1)）。

3. **日志与通知**：
   - 记录：`自动创建订阅《{title}》共 {total_episodes} 集`；
   - 在 Web 面板生成通知。

**仅展示时（`filter_auto_subscribe_new_season=false`）**：

1. 不创建 Subscription 和 Episode；
2. 将番剧信息写入一个临时发现缓存（或直接用 Bangumi 缓存）；
3. Web 面板 Discovery 页展示"未订阅"按钮；
4. 用户点击后调用 `/api/discovery/subscribe` 走手动创建流程。

#### Step 7：生成任务调度（详细）

**目标**：为每个新 Subscription 的 Episode 生成首次检查时间，避免全局轮询浪费资源。

**流程**：

1. 遍历 Step 6 中新建的 Subscription。
2. 对每部 Subscription：
   - 取 `expected_airing_weekday` 和 `expected_airing_time`；
   - 计算"下一个播出日"：
     ```python
     now = datetime.now(tz=target_tz)
     target_weekday = subscription.expected_airing_weekday  # 0=周一
     days_ahead = (target_weekday - now.weekday()) % 7
     if days_ahead == 0 and now.time() > air_time:
         days_ahead = 7  # 今天已过播出时间，安排到下周
     next_air_date = now.date() + timedelta(days=days_ahead)
     next_run_at = datetime.combine(next_air_date, air_time, tz=target_tz)
     ```
3. 为每个 Subscription 创建 `TaskSchedule`：
   ```python
   TaskSchedule(
       subscription_id=subscription.id,
       task_type="check_updates",
       next_run_at=next_run_at,
       is_active=True,
   )
   ```
4. Scheduler 每周扫描 `TaskSchedule`，对 `next_run_at <= now` 且 `is_active=true` 的记录：
   - 触发 Orchestrator 的 `check_updates` 逻辑（或直接触发 Episode Graph）；
   - 完成后更新 `last_run_at`，并根据播出周期计算下一次 `next_run_at`（通常为 7 天后）。

**特殊情况**：
- 若某部番剧已播出多集（如发现时已经播到第 5 集），首次调度会触发所有已播出 Episode 的检查；
- 若 `expected_airing_weekday` 未知（ Bangumi/AniList 都没有播出时间），默认每天检查一次，直到锁定周几。

#### Step 8：已播出多集的处理（追平/补档）

若发现时番剧已播到第 5 集，系统不会只等待第 6 集，而是会补全前 5 集：

1. **计算已播出集数**：
   - 根据当前时间与首播时间推算：
     ```python
     weeks_passed = max(0, (now - first_air_date).days // 7)
     latest_aired_episode = min(weeks_passed + 1, total_episodes)
     ```
   - 或通过 AniList `nextAiringEpisode.episode - 1` 得知最新已播集数。

2. **批量创建 Episode**：
   - 为 1 到 `latest_aired_episode` 创建 Episode；
   - 这些 Episode 的状态均为 `pending`；
   - 为每集创建独立的 `TaskSchedule`，首次检查时间错开（如间隔 10-30 分钟），避免瞬间触发大量 Graph。

3. **执行策略**：
   - Scheduler 依次触发这些 Episode 的 Graph；
   - 每集独立走 `fetch_rss → match_torrent → send_download` 流程；
   - 由于同一字幕组可能发布了多集，RSS 候选池可能包含多集种子，匹配时按集数区分。

4. **用户控制**：
   - 若用户只想追最新集、不补旧集，可在 Web 面板一键跳过 1-5 集；
   - 或在发现页选择"仅从第 X 集开始下载"。

#### Step 9：自动订阅并下载下一集

系统不需要为"下一集"单独订阅，因为 Subscription 已经代表整季：

1. **Episode 粒度追踪**：
   - Subscription 创建时，已为 1 到 `total_episodes` 的所有集创建了 Episode 记录；
   - 每集有自己的状态：`pending → fetching → matched → downloading → completed / failed`。

2. **Scheduler 触发**：
   - 每周触发 Subscription 的检查任务；
   - 检查任务查询 Bangumi/AniList 获取 `nextAiringEpisode`；
   - 若发现新集已播出，将该 Episode 状态从 `pending` 改为待执行，并触发 Episode Graph。

3. **播出周几锁定后**：
   - 首次成功锁定 `expected_airing_weekday` 后，Scheduler 只需按周几检查；
   - 不需要每次查询 API 确认是否有新集。

4. **完结处理**：
   - 当 `nextAiringEpisode` 为空且 `total_episodes` 已知，或所有 Episode 均为 `completed`，将 Subscription.status 改为 `completed`；
   - `completed` 的 Subscription 不再参与常规轮询，但用户可手动触发重试。

#### Step 10：完结检测与全集完成检查

**完结检测**：

1. **主动检测**：
   - 每次 `check_updates` 时查询 AniList/Bangumi 的 `status` 字段；
   - `FINISHED` / `RELEASING` / `NOT_YET_RELEASED` 等状态映射到 Subscription.status。

2. **被动推断**：
   - 若 `total_episodes` 已知且最新已播集数 == `total_episodes` → 视为完结；
   - 若 `nextAiringEpisode` 为空且最近一集已播出超过 14 天 → 视为完结。

**全集完成检查**：

1. **聚合查询**：
   ```sql
   SELECT COUNT(*) FROM episodes
   WHERE subscription_id = ? AND status != 'completed'
   ```
2. **判定**：
   - 若未完成的 Episode 数为 0 且 `total_episodes > 0` → 全集下载完成；
   - 更新 `Subscription.status = "completed"`；
   - 发送通知："《{title}》全部 {total_episodes} 集下载完成"。

3. **定时扫描**：
   - Orchestrator 每周发现任务时，顺便扫描所有 `ongoing` 的 Subscription；
   - 对可能已完结的 Subscription 调用 `check_completion()`；
   - 发现完结后更新状态并通知。

#### API 调用量估算（每周一次）

- Bangumi 当季列表：1 次
- Bangumi subject 详情：N 次（N = 当季番剧数，约 30-60 部）
- AniList 搜索/详情：N 次
- 总计约 60-120 次 API 调用/周，平均 < 1 次/小时，远低于 Bangumi/AniList 限制。

### 5.7 过滤规则配置

```yaml
# config.yaml
filters:
  exclude_ova: true
  exclude_movies: false        # 电影可单独开关
  min_duration_minutes: 5      # 排除 <5 分钟
  exclude_genres: ["Hentai", "Ecchi"]  # R18/成人向
  exclude_formats: ["OVA", "ONA"]      # 格式过滤
  require_anime_type: true     # 只保留 type=ANIME
  auto_subscribe_new_season: true   # 默认自动订阅当季新番
  discovery_cron: "0 0 * * 1"       # 每周一 00:00 执行新番发现
```

### 5.8 Token 与成本节省策略

1. **智能调度**：锁定播出周几后，只在播出当天及之后检查。
2. **中文源优先**：Bangumi 减少中文名歧义，降低 LLM 在匹配时的困惑。
3. **批量查询**：Bangumi/AniList 尽量批量查询，减少 HTTP 请求。
4. **缓存**：
   - Bangumi/AniList 响应缓存 1 小时；
   - TMDB 响应缓存 24 小时；
   - LLM 决策结果缓存（按输入 hash）。
5. **规则预过滤**：RSS 候选先用正则/集数过滤，再交给 LLM。
6. **LLM 分级**：简单 NLU 和规则判断用本地 Ollama，复杂歧义用 GPT-4o。

### 5.9 工作流数量与自定义工具

#### 目前使用了多少个 Agent？

严格来说，系统使用 **3 个 LangGraph StateGraph**（可称为 3 个 Agent/工作流）：

1. **对话层**：处理自然语言对话
2. **调度层**：处理订阅发现、过滤、调度
3. **Episode Agent（Episode Graph）**：处理单集下载执行

如果按"调用 LLM 做决策的节点"来数，则有更多：
- 对话层 的 `parse_input`
- Episode Graph 的 `match_torrent`
- Episode Graph 的 `process_metadata`

但宣传口径建议统一为 **"三层工作流架构"**。

#### 工作流节点能调用我写的工具吗？

**可以，这是核心设计。**

每个 Node 都是通过调用 Tool 来完成外部 IO 的。添加自定义工具的步骤：

1. **继承 BaseTool**：
   ```python
   # anime_agent/tools/my_custom_tool.py
   from .base import BaseTool, ToolInput, ToolOutput

   class MyCustomInput(ToolInput):
       param: str

   class MyCustomTool(BaseTool):
       name = "my_custom"
       description = "我的自定义工具"

       async def invoke(self, input_data: MyCustomInput) -> ToolOutput:
           # 你的逻辑
           return ToolOutput(success=True, data={"result": "ok"})
   ```

2. **在 Node 中调用**：
   ```python
   # anime_agent/nodes/my_node.py
   from ..tools.my_custom_tool import MyCustomTool, MyCustomInput

   async def my_node(state, config):
       tool = MyCustomTool()
       result = await tool.invoke(MyCustomInput(param="value"))
       if not result.success:
           return Command(update={"errors": [result.error]}, goto="handle_error")
       return Command(update={"my_data": result.data}, goto="next_node")
   ```

3. **注册到 Graph**：在 `graph.py` 或对应 Agent 的 graph 文件中加入该 Node。

4. **测试**：在 `tests/test_tools/test_my_custom_tool.py` 中按 BaseTool 接口测试。

**最佳实践**：
- Tool 只负责 IO，不处理业务逻辑；
- Tool 应该是无状态的，便于 mock 和测试；
- 所有外部系统调用（包括你自己写的服务）都应该封装成 Tool。

### 5.10 组件职责再梳理（工作流 / Agent / Tool / Module）

为了避免过度设计，下面重新梳理每个组件应该属于 **工作流 / Agent**、**Tool** 还是 **Module**，并给出优化建议。

#### 当前工作流层（3 个 StateGraph）

| 组件 | 职责 | 是否必须作为 LangGraph | 建议 |
|-------|------|------------------------|------|
| **对话层** | NLU、多轮对话、意图补全 | 是 | 保留。对话状态、断点、恢复天然适合 Graph。 |
| **调度层** | 新番发现、过滤、订阅创建、调度 | 可保留但可简化 | 保留作为 Graph，但内部 Node 可以合并，很多步骤用函数即可。 |
| **Episode Agent** | 单集下载、整理、通知 | 是 | 保留。这是系统核心价值，状态机复杂。 |

**建议**：如果 3 周时间紧张，调度层 可以降级为 **一组函数/模块**，只把对话工作流 + Episode Agent 保留为 LangGraph。简历里仍可以说 "多 Agent 协作"，因为 Episode Graph 内部有多个 LLM 决策节点。

#### Tool 层（建议保持不变）

| Tool | 职责 | 说明 |
|------|------|------|
| `BangumiTool` | 中文元数据 | 优先源，fallback AniList |
| `AniListTool` | 国际元数据 | `nextAiringEpisode`、季度信息 |
| `TMDBTool` | Emby 媒体库匹配 | 需要 API Key/Read Token |
| `RSSTool` | RSS 拉取 | 共享缓存 |
| `qBTool` | 下载器 | add/poll/delete torrent |
| `EmbyTool` | 媒体库刷新 | REST API |
| `NotifyTool` | 通知 | apprise / 日志 |
| `FileSystemTool` | 硬链接/移动/创建目录 | Windows 路径处理 |
| `LLMTool` | LLM 调用 | OpenAI / Ollama |

#### 应该抽取为独立 Module 的业务逻辑

以下逻辑目前分散在 Node 中，建议抽取为可测试的 Module：

| 模块 | 职责 | 当前位置 | 建议新文件 |
|------|------|----------|-----------|
| **MetadataResolver** | 统一 Bangumi/AniList/TMDB 查询 + fallback | `orchestrator/discovery.py` + `nodes/check_updates.py` | `anime_agent/services/metadata_resolver.py` |
| **TorrentSelector** | 规则预过滤 + LLM 匹配 + 置信度判定 | `nodes/match_torrent.py` | `anime_agent/services/torrent_selector.py` |
| **EpisodePlanner** | 根据播出周几计算 `next_run_at` | `orchestrator/planner.py` | 保留并强化 |
| **TorrentHealthMonitor** | 死种/慢种/卡元数据判定 | `nodes/poll_download.py` | `anime_agent/services/torrent_health.py` |
| **CompletionChecker** | 完结检测 + 全集完成检查 | `orchestrator/completion.py` | 保留并强化 |
| **ContentFilter** | 过滤 OVA、R18、<5min 等 | `orchestrator/filter.py` | 保留 |
| **FolderNormalizer** | 本地目录名规范化 | `nodes/organize_files.py` | `anime_agent/utils/folder.py` |

#### 可以合并的 Node

| 当前 Node | 建议 | 理由 |
|-----------|------|------|
| `schedule_wait_rss` + `schedule_poll` | 合并为 `schedule_resume` | 都是"更新 TaskSchedule.next_run_at 后结束 Graph" |
| `refresh_emby` + `notify_user` | 可合并为 `finalize` | 都是收尾动作，失败不影响核心结果 |
| `classify_content` + `validate_metadata` | 已合并为 `process_metadata` | 已完成 |

#### 应该移出 Graph 的逻辑

| 当前位置 | 建议 | 理由 |
|----------|------|------|
| `nodes/check_tool_health.py` | 移到 Scheduler 作为 pre-flight check | Graph 内部不需要这个 Node，失败直接不启动 Graph |
| `orchestrator/discovery.py` 中的批量查询 | 移到 `MetadataResolver` Module | 减少 Graph 节点数量 |

#### 新增一个工具：HealthCheckTool？

**不建议**。每个 Tool 已经有 `healthcheck()` 方法，Scheduler 可以直接调用各 Tool 的 `healthcheck()` 做 pre-flight，无需新增 Tool。

#### 简化后的目录结构建议

```
anime_agent/
├── agents/                     # 只有真正的 LangGraph Agent
│   ├── conversational/         # 对话层
│   ├── orchestrator.py         # 调度层（简化版，内部调用 services）
│   └── episode/                # Episode Agent
├── services/                   # 业务逻辑模块
│   ├── metadata_resolver.py
│   ├── torrent_selector.py
│   ├── torrent_health.py
│   ├── episode_planner.py
│   ├── completion_checker.py
│   └── content_filter.py
├── tools/                      # 外部 IO
│   ├── bangumi_tool.py
│   ├── anilist_tool.py
│   ├── tmdb_tool.py
│   ├── rss_tool.py
│   ├── qb_tool.py
│   ├── emby_tool.py
│   ├── notify_tool.py
│   ├── filesystem_tool.py
│   └── llm_tool.py
├── memory/                     # 数据层
├── utils/                      # 通用工具
└── scheduler.py                # 调度器 + pre-flight health check
```

#### 最终建议

1. **保留 3 个工作流**（简历价值），但让 调度层 尽量薄，业务逻辑下沉到 `services/`。
2. **Episode Graph 保持完整**，但把 `check_tool_health` 提到 Scheduler。
3. **新增 `services/` 目录**，把元数据解析、种子选择、健康监控等核心算法独立出来，方便单元测试。
4. **合并 `schedule_wait_rss` + `schedule_poll`**，减少 Graph 复杂度。
5. **不新增 HealthCheckTool**，复用各 Tool 的 `healthcheck()`。

---

## 6. 数据模型

### 6.1 Subscription（订阅）

一个 Subscription 代表一季/一个作品。

```python
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    bangumi_id = Column(Integer, unique=True, index=True)
    anilist_id = Column(Integer, unique=True, index=True)
    title_romaji = Column(String, nullable=False)
    title_native = Column(String)
    title_chinese = Column(String)
    season_year = Column(Integer)
    season = Column(String)  # WINTER/SPRING/SUMMER/FALL
    total_episodes = Column(Integer)
    local_folder_name = Column(String)  # 媒体库目录名
    status = Column(String, default="ongoing")  # ongoing/completed/dropped
    source = Column(String, default="manual")  # manual / auto_discover
    auto_download_enabled = Column(Boolean, default=True)  # 是否自动下载新集
    rss_source_id = Column(Integer, ForeignKey("rss_sources.id"))

    # 播出时间推断：首次从 AniList 解析后锁定周几
    expected_airing_weekday = Column(Integer)  # 0=周一, ..., 6=周日
    expected_airing_time = Column(String)      # 例如 "23:00"
    airing_timezone = Column(String, default="Asia/Tokyo")

    created_at = Column(DateTime, default=datetime.utcnow)

    episodes = relationship("Episode", back_populates="subscription", cascade="all, delete-orphan")
    rss_source = relationship("RSSSource")
```

**约束**：`bangumi_id` 和 `anilist_id` 至少有一个。创建订阅时 Orchestrator 会尽量同时解析两者。

### 6.2 Episode（集）

```python
class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), index=True)
    episode_number = Column(Integer, nullable=False)
    title = Column(String)
    aired_at = Column(DateTime)
    status = Column(String, default="pending", index=True)
    # pending/fetching/matched/downloading/completed/failed/human_review

    torrent_hash = Column(String, index=True)
    torrent_name = Column(String)
    torrent_title = Column(String)      # RSS 原始标题
    torrent_info_hash = Column(String, index=True)
    content_type = Column(String, default="TV")  # TV/SP/OVA/Movie
    download_path = Column(String)
    organized_path = Column(String)
    metadata_verified = Column(Boolean, default=False)
    error_log = Column(Text)
    human_input = Column(Text)          # 人工审批输入

    # RSS 轮询追踪
    rss_candidates = Column(Text)       # JSON: 候选种子列表
    rss_last_checked_at = Column(DateTime)
    rss_attempt_count = Column(Integer, default=0)
    low_confidence_count = Column(Integer, default=0)

    # 下载健康追踪
    torrent_added_at = Column(DateTime)
    torrent_last_speed = Column(Float, default=0.0)        # bytes/s
    torrent_last_speed_at = Column(DateTime)
    torrent_status = Column(String)     # qB 状态：stalledDL/downloading/queuedUP 等
    torrent_checked_at = Column(DateTime)
    torrent_failed_hashes = Column(Text)  # JSON: 已失败/放弃的 hash 列表

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="episodes")
```

### 6.3 MetadataMapping（元数据映射）

```python
class MetadataMapping(Base):
    __tablename__ = "metadata_mappings"

    id = Column(Integer, primary_key=True)
    bangumi_id = Column(Integer, unique=True, index=True)
    anilist_id = Column(Integer, unique=True, index=True)
    tmdb_id = Column(Integer)
    tmdb_season = Column(Integer, default=1)
    anidb_id = Column(Integer)
    imdb_id = Column(String)
    confidence = Column(Float)
    verified_by = Column(String, default="agent")  # agent/human
    mapping_data = Column(Text)  # JSON 特殊规则
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 6.4 RSSSource（RSS 源）

```python
class RSSSource(Base):
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    parser_rules = Column(Text)  # JSON: include/exclude regex
    is_active = Column(Boolean, default=True)
```

### 6.5 SystemConfig（系统配置）

```python
class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(Text)
```

### 6.6 UserRequest（用户请求）

用于记录用户通过 Web/CLI 发起的智能助手请求，以及等待用户补全信息的状态。

```python
class UserRequest(Base):
    __tablename__ = "user_requests"

    id = Column(Integer, primary_key=True)
    request_type = Column(String, nullable=False)
    # discover / subscribe / download_range / unknown

    raw_input = Column(Text, nullable=False)        # 用户原始输入
    parsed_title = Column(String)                   # 解析出的番剧名
    parsed_season = Column(Integer)                 # 季
    parsed_episodes = Column(String)                # 集数范围，如 "1,3,5-10" 或 "all"

    anilist_candidates = Column(Text)               # JSON: AniList 查询候选
    selected_anilist_id = Column(Integer)

    status = Column(String, default="pending")
    # pending / awaiting_user_input / processing / completed / cancelled

    system_message = Column(Text)                   # 给用户的提示/问题
    response_to_user = Column(Text)                 # 系统回复
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 6.7 TaskSchedule（任务调度）

可选表，用于记录每个 Subscription 下一次检查时间。如果逻辑简单，可以直接从 `Subscription.expected_airing_weekday` 推导，不单独建表。

```python
class TaskSchedule(Base):
    __tablename__ = "task_schedules"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), unique=True)
    task_type = Column(String, default="check_updates")  # check_updates / discover
    next_run_at = Column(DateTime, index=True)
    last_run_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
```

---

## 7. LangGraph 状态机

系统由 **三个独立的工作流** 组成：

1. **对话工作流**：负责用户对话、意图解析、多轮澄清。
2. **调度工作流**：接收结构化意图，负责新番发现、过滤、订阅创建、任务调度。
3. **Episode Graph**：负责单集下载、整理、通知的完整闭环。

三者通过 SQLite 共享状态。对话工作流 输出 `ParsedIntent` 给 调度工作流；调度工作流 创建 `Episode` 后，由外部 Scheduler 触发 Episode Graph。

### 7.1 ConversationalState

```python
from typing import TypedDict, Annotated, List, Optional
from operator import add

class ConversationalState(TypedDict):
    request_id: int                     # UserRequest.id
    raw_input: str                      # 用户原始输入

    # 解析结果
    parsed_intent: Optional[dict]       # {action, title, season, episodes}
    missing_fields: List[str]           # 缺失需要询问的字段

    # 候选结果（Bangumi 优先）
    search_candidates: List[dict]       # Bangumi/AniList 搜索候选
    selected_bangumi_id: Optional[int]
    selected_anilist_id: Optional[int]

    # 控制流
    status: str
    errors: Annotated[List[str], add]
    requires_human: bool                # 是否需要用户回复
    human_input: Optional[str]
    response_to_user: Optional[str]     # 回复用户的消息
```

### 7.2 OrchestratorState

```python
class OrchestratorState(TypedDict):
    request_id: int
    parsed_intent: dict                 # 来自 对话层

    # 发现结果
    discovered_anime: List[dict]        # Bangumi 当季番剧
    filtered_anime: List[dict]          # 过滤后结果

    # 创建结果
    created_subscription_ids: List[int]
    created_episode_ids: List[int]

    # 控制流
    status: str
    errors: Annotated[List[str], add]
    response_to_user: Optional[str]
```

### 7.3 EpisodeAgentState

```python
class EpisodeAgentState(TypedDict):
    # 身份标识
    goal_id: str
    subscription_id: int
    episode_number: int

    # 元数据
    title_romaji: str
    title_native: str
    title_chinese: Optional[str]
    bangumi_data: dict                  # Bangumi 详情
    anilist_data: dict
    tmdb_data: Optional[dict]

    # 执行中间产物
    rss_candidates: List[dict]
    matched_torrent: Optional[dict]   # {hash, title, confidence}
    torrent_hash: Optional[str]
    download_files: List[str]
    classification: Optional[dict]    # {content_type, confidence}
    organized_path: Optional[str]

    # 控制流
    status: str
    errors: Annotated[List[str], add]
    requires_human: bool
    human_input: Optional[str]
```

### 7.4 对话工作流 拓扑

```
START
  │
  ▼
parse_input                  # 正则/LLM 解析用户意图
  │── 无法解析 ──▶ generate_reply ──▶ END（询问用户重新描述）
  │
  ▼
search_candidates            # Bangumi 优先搜索番剧
  │── 无结果 ──▶ generate_reply ──▶ END
  │
  ▼
evaluate_completeness        # 检查是否缺失 season/episodes
  │── 信息完整 ──▶ confirm_action ──▶ invoke_orchestrator ──▶ END
  │── 信息缺失 ──▶ generate_question ──▶ END（等待用户回复）

用户回复 ──▶ parse_input（从 checkpoint 恢复，保留上下文）
```

**优化点**：
- `parse_input` 先用正则/规则处理常见模式（"下载 XXX"、"第 X 季第 Y 集"、"全部"），复杂情况才调用 LLM。
- `search_candidates` 优先 Bangumi，无结果 fallback AniList。
- `generate_question` 会给出最可能的候选列表，让用户选择而非开放式追问。
- 多轮对话通过 LangGraph checkpoint + `UserRequest` 表恢复上下文。

### 7.5 调度工作流 拓扑

```
START
  │
  ▼
parse_intent                 # 解析 ParsedIntent
  │
  ▼
discover_season              # Bangumi 当季番剧列表
  │
  ▼
apply_filters                # 过滤 OVA、<5min、R18 等
  │── 全部被过滤 ──▶ notify_filtered ──▶ END
  │
  ▼
resolve_metadata             # Bangumi + AniList 交叉验证，锁定 anilist_id/bangumi_id
  │
  ▼
create_subscriptions         # 创建 Subscription + Episodes
  │
  ▼
schedule_checks              # 按播出周几写入 TaskSchedule
  │
  ▼
notify_user ──▶ END
```

**与 对话工作流 的关系**：
- Web 聊天请求：对话工作流 → 调度工作流
- Web 表单请求：直接构造 ParsedIntent → 调度工作流
- 每日新番发现：Scheduler 直接触发 调度工作流（无用户输入）

### 7.6 Episode Graph 拓扑（优化版）

```
START
  │
  ▼
check_tool_health            # 快速失败：AniList/RSS/qB 不可用直接 handle_error
  │
  ▼
check_updates
  │── 未到播出时间 ──▶ END（Scheduler 按周几再触发）
  │── 已播出 ──▶ fetch_rss
  │
  ▼
fetch_rss                    # 拉取 RSS，更新候选池
  │── 无候选 ──▶ schedule_wait_rss ──▶ END
  │
  ▼
match_torrent                # LLM 匹配 + 规则预过滤
  │── 无匹配 ──▶ schedule_wait_rss ──▶ END
  │── 匹配成功 ──▶ send_download
  │── 置信度低 ──▶ reflect_match
  │
  ▼
reflect_match                # 二次审查 + 决策
  │── 自动批准 ──▶ send_download
  │── 搜索更多 ──▶ search_resources ──▶ match_torrent
  │── 等待 ──▶ schedule_wait_rss ──▶ END
  │── 人工审查 ──▶ human_review
  │
  ▼
send_download
  │
  ▼
poll_download
  │── 健康未完成 ──▶ schedule_poll ──▶ END
  │── stalled / no speed 1H / metaDL 1H / 12H 未完成
  │    └── 还有候选 ──▶ send_download（换种）
  │    └── 无候选 ──▶ schedule_wait_rss ──▶ END
  │── 完成 ──▶ process_metadata
  │── 失败 ──▶ send_download（换种）或 schedule_wait_rss
  │
  ▼
process_metadata             # classify_content + validate_metadata 合并
  │
  ▼
organize_files
  │
  ▼
refresh_emby
  │
  ▼
notify_user ──▶ END

human_review ──用户确认──▶ send_download
            ──用户跳过──▶ END

handle_error ──▶ notify_user ──▶ END
```

### 7.7 关键优化说明

1. **合并 `classify_content` + `validate_metadata`**
   - 两个节点都依赖 LLM + 元数据，合并为 `process_metadata` 可减少一次状态转换和一次 LLM 调用。
   - 输出：`{content_type, tmdb_id, confidence, verified}`。

2. **外部 Scheduler 替代 Graph 内部循环**
   - `schedule_wait_rss`、`schedule_poll` 不直接返回自身，而是更新 DB 中的 `next_run_at`，由 APScheduler 在指定时间重新 invoke Graph。
   - 优点：Graph 无长 sleep，不阻塞；系统重启后任务不丢失；Web 面板可实时看到"下次检查时间"。

3. **快速失败 `check_tool_health`**
   - Episode Graph 启动时先检查相关 Tool 健康状态，避免无意义执行。

4. **候选池共享**
   - `fetch_rss` 获取的候选写入 `episode.rss_candidates`，`match_torrent` 和 `send_download` 都从中读取，换种时无需重新拉 RSS。

5. **Human-in-the-Loop 用 LangGraph Checkpoint**
   - `human_review` 节点设置 `requires_human=True` 并返回 `Command(goto=END)`。
   - 用户通过 Web API 提交 `human_input` 后，使用 `graph.ainvoke(state, config)` 从 checkpoint 恢复，直接进入 `human_review` 后的分支。

---

## 8. 关键节点行为详解

> 以下 8.1-8.10 属于 **Episode Graph**。对话工作流 与 调度工作流 的节点行为在 5.3-5.5 节已描述。

### 8.1 check_tool_health

**目标**：Episode Graph 启动时快速检查外部依赖，避免无意义执行。

**逻辑**：
1. 并行检查 `AniListTool`、`RSSTool`、`qBTool`、`EmbyTool` 健康状态。
2. 任一关键 Tool 不健康 → 更新 `error_log`，进入 `handle_error`。
3. 全部健康 → 进入 `check_updates`。

### 8.2 check_updates

**目标**：判断目标集数是否已经播出，并创建/更新对应的 `Episode`。

**逻辑**：
1. 优先读取本地 `Subscription.expected_airing_weekday`，若已锁定则按周几判断。
2. 若未锁定：
   - 调用 `BangumiTool` 查询 `subscription.bangumi_id` 获取播出信息；
   - Bangumi 无结果则 fallback 到 `AniListTool` 查询 `nextAiringEpisode`。
3. 如果目标集数已播出（允许 30min 缓冲），判定"已播出"。
4. **周几推断**：首次成功匹配后，从播出时间提取星期几和时间，写入 `subscription.expected_airing_weekday` 和 `expected_airing_time`。
4. 后续 check 优先使用锁定的周几：计算"本周该周几的播出时间"，如果当前时间已过该时间点，则视为已播出。
5. 创建 `Episode`（状态 `pending`）或更新已有 episode 的 `aired_at`。
6. 如果目标集数已经存在于 DB 且状态不是 `pending`，则跳过。

**示例**：
- 首播：`airingAt = 2024-01-09 23:00 JST` → 推断为"每周二 23:00 JST"。
- 后续：每周二 23:00 JST 之后视为下一集已播出。

### 8.3 fetch_rss

**目标**：获取候选种子列表，等待字幕组发布。

**逻辑**：
1. 调用 `RSSTool` 拉取订阅对应的 RSS 源（使用共享缓存，同一源每小时只拉一次）。
2. 用标题关键词过滤条目（romaji/native/chinese）。
3. 与已有 `rss_candidates` 合并并去重（按 info_hash）。
4. 保存候选到 `episode.rss_candidates`（JSON）。
5. **无候选时**：
   - 若 `rss_attempt_count == 0`，记录首次检查时间。
   - 进入 `schedule_wait_rss`。

### 8.4 match_torrent

**目标**：从候选中选出最匹配当前集数的种子。

**逻辑**：
1. 取 `episode.rss_candidates` 作为输入。
2. **规则预过滤**：
   - 集数明显不匹配剔除；
   - 发布日期早于播出时间剔除；
   - 已在 `torrent_failed_hashes` 中的 hash 剔除。
3. LLM 输出：`{hash, title, confidence}` 或 `{matched: false}`。
4. **分支**：
   - `confidence >= 0.8`：进入 `send_download`。
   - `0.5 <= confidence < 0.8`：`low_confidence_count += 1`，进入 `reflect_match` 进行二次审查。
   - `confidence < 0.5` 或 `matched: false`：视为无匹配，进入 `schedule_wait_rss`。

### 8.5 reflect_match

**目标**：在首次匹配置信度不足时，通过 LLM 重新评估候选并决定最佳下一步，减少不必要的人工干预。

**逻辑**：
1. 接收 `match_torrent` 返回的候选池、失败 hash、标题变体、集数、低置信度次数。
2. 若候选池为空，优先进入 `search_resources` 扩大搜索范围。
3. 调用 LLM 进行结构化推理，输出 `{action, info_hash, confidence, reason}`。
4. **分支**：
   - `auto_approve` 且 `confidence >= 0.75`：将候选写入 `matched_torrent`，进入 `send_download`。
   - `search_resources` 且尚未搜索过：进入 `search_resources`，完成后回到 `match_torrent`。
   - `wait`：进入 `schedule_wait_rss`，等待 RSS 更新。
   - `human_review` 或 LLM 调用失败：进入 `human_review`。

### 8.6 send_download

**目标**：将种子推送给 qBittorrent。

**逻辑**：
1. 从 `episode.matched_torrent` 获取 hash/url。
2. 检查该 hash 是否已在 `torrent_failed_hashes` 中，避免重复尝试。
3. 调用 `qBTool.add_torrent()`，保存路径为 `QB_SAVE_PATH`。
4. 记录 `torrent_added_at`、`torrent_hash`。
5. 状态改为 `downloading`。

### 8.6 poll_download

**目标**：轮询下载状态，识别死种/慢种并切换。

**轮询频率**：
- 健康下载：由 `schedule_poll` 安排 30 分钟后检查。
- 疑似 stalled：5 分钟后检查。
- 元数据阶段：2 分钟后检查。

**健康判断**：
1. 获取 qBittorrent 状态：下载速度、进度、状态字段。
2. 写入 `torrent_last_speed`、`torrent_last_speed_at`、`torrent_status`。
3. **异常判定**：
   - 1 小时内下载速度持续为 0（且进度 < 100%）→ 视为 stalled。
   - 1 小时内状态停留在 `metaDL`（元数据下载）→ 视为元数据失败。
   - 12 小时内未完成下载 → 视为过慢。
4. **处理异常**：
   - 若 `rss_candidates` 还有其他未尝试的种子 → 将当前 hash 加入 `torrent_failed_hashes`，换下一个候选，回到 `send_download`。
   - 若无更多候选 → 进入 `schedule_wait_rss`。
5. **完成**：进度 100% 且状态为 `uploading`/`pausedUP` → 进入 `process_metadata`。

### 8.7 schedule_wait_rss

**目标**：在无候选/低置信度/无可用种子时，安排 6 小时后重试。

**逻辑**：
1. `rss_attempt_count += 1`。
2. 更新 `episode.status = "waiting_for_rss"`。
3. 计算 `next_run_at = now + 6H`，写入 `TaskSchedule`。
4. 返回 `Command(goto="END")`。
5. Scheduler 在 `next_run_at` 重新 invoke Episode Graph，从 `fetch_rss` 开始。
6. 若距首次检查 ≥ 7 天仍未解决 → 进入 `handle_error`。

### 8.8 schedule_poll

**目标**：健康下载时安排下一次轮询，避免 Graph 内部长 sleep。

**逻辑**：
1. 根据当前下载状态决定下次检查时间：
   - 健康：30 分钟后
   - 元数据阶段：2 分钟后
   - 疑似异常：5 分钟后
2. 更新 `TaskSchedule.next_run_at`。
3. 返回 `Command(goto="END")`。

### 8.9 process_metadata

**目标**：合并内容分类与元数据验证，减少一次 LLM 调用和状态转换。

**逻辑**：
1. 基于文件名、AniList 数据、TMDB 查询判断 `content_type`（TV/SP/OVA/Movie）。
2. 对 TV 类型，交叉验证 TMDB 季度与集数映射。
3. 输出：`{content_type, tmdb_id, tmdb_season, confidence, verified}`。
4. 低置信度时记录日志，但不暂停（MVP 阶段由 organize_files 使用默认规则）。

### 8.10 human_review

**目标**：种子匹配置信度连续 3 次过低时，暂停等待用户确认。

**逻辑**：
1. 设置 `requires_human=True`，展示候选种子列表和 LLM 推荐理由。
2. 返回 `Command(goto="END")`，Graph 进入 checkpoint 等待。
3. 用户通过 Web 选择"确认"/"跳过"/"选另一个"，提交 `human_input`。
4. Graph 从 checkpoint 恢复，根据 `human_input` 走向 `send_download` 或 `END`。

---

## 9. Tool 层设计

### 9.1 基类

```python
class ToolInput(BaseModel):
    pass

class ToolOutput(BaseModel):
    success: bool
    data: dict = {}
    error: str = ""

class BaseTool(ABC):
    name: str = "base_tool"
    description: str = ""

    @abstractmethod
    async def invoke(self, input_data: ToolInput) -> ToolOutput:
        pass

    async def healthcheck(self) -> ToolOutput:
        return ToolOutput(success=True, data={"status": "unknown"})
```

### 9.2 Tool 清单

| Tool | 输入 | 输出 | 说明 |
|------|------|------|------|
| `llm_tool` | prompt / system_msg / json_schema | text / json | OpenAI/Ollama 封装 |
| `bangumi_tool` | search_term / subject_id | subject info / calendar | Bangumi 中文元数据 |
| `anilist_tool` | search_term / media_id | media list | GraphQL |
| `tmdb_tool` | query / year / tmdb_id | search/season info | REST |
| `rss_tool` | rss_url / filters | entry list | feedparser |
| `qb_tool` | torrent_url / save_path / hash | hash / status | qbittorrent-api |
| `emby_tool` | library_name / item_path | success | REST API 刷新 |
| `notify_tool` | message / channel | success | apprise 或日志 |
| `filesystem_tool` | src / dst / mode | dst_path | hardlink/move/symlink/copy |

### 9.3 重试策略

- 所有 Tool 使用 `tenacity` 进行最多 3 次指数退避重试。
- 重试后仍失败返回 `ToolOutput(success=False, error=...)`。
- 配置缺失、参数错误等不可恢复问题直接抛异常。

---

## 10. FastAPI Web 面板

### 10.1 页面

| 页面 | 功能 |
|------|------|
| `/` | 前端单页应用入口 |
| Dashboard | pending/completed/failed 统计、最近活动 |
| Subscriptions | 新增/查看/删除订阅、开关自动下载、编辑本地目录名 |
| Tasks | 任务队列、状态、错误日志、重试按钮 |
| Human Review | 种子匹配置信度低的审批界面 |
| Assistant | 自然语言交互："下载葬送的芙莉莲" |
| Discovery | 按年份+季度浏览新番（如 2026 春季/夏季）、一键订阅、过滤预览 |
| System | Tool healthcheck、配置查看 |

### 10.2 API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stats` | 任务统计 |
| GET | `/api/subscriptions` | 订阅列表 |
| POST | `/api/subscriptions` | 新增订阅 |
| PATCH | `/api/subscriptions/{id}` | 更新订阅（如切换 auto_download_enabled） |
| DELETE | `/api/subscriptions/{id}` | 删除订阅 |
| GET | `/api/episodes` | 集列表（支持状态过滤） |
| POST | `/api/episodes/{id}/retry` | 重试失败/人工任务 |
| POST | `/api/episodes/{id}/human_input` | 提交人工审批 |
| POST | `/api/assistant/chat` | 用户与 对话层 对话 |
| GET | `/api/assistant/requests/{id}` | 查询请求状态 |
| GET | `/api/discovery/season?year=2026&season=spring` | 按年份+季度浏览新番 |
| POST | `/api/discovery/subscribe` | 从发现页订阅 |
| POST | `/api/discovery/{id}/enable` | 启用已过滤/已禁用番剧的自动下载 |
| GET | `/api/tools/health` | 各 Tool 健康状态 |
| GET | `/api/logs` | 最近日志 |

---

## 11. 配置管理

### 11.1 环境变量（.env）

```bash
# LLM
LLM_PROVIDER=openai          # openai / ollama
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:7b

# qBittorrent
QB_HOST=http://localhost:8080
QB_USERNAME=admin
QB_PASSWORD=adminadmin
QB_SAVE_PATH=C:\Downloads\Anime

# TMDB
TMDB_API_KEY=xxx
TMDB_READ_ACCESS_TOKEN=xxx

# Emby
EMBY_HOST=http://localhost:8096
EMBY_API_KEY=xxx
EMBY_LIBRARY_NAME=Anime

# 媒体库
MEDIA_LIBRARY_PATH=C:\Media\Anime
ORGANIZE_TEMPLATE="{title}\{title} S{season:02d}E{episode:02d}.{ext}"

# 系统
CHECK_INTERVAL_SECONDS=600
LOG_LEVEL=INFO
DATABASE_URL=sqlite+aiosqlite:///anime_agent.db

# Agent 过滤规则
FILTER_EXCLUDE_OVA=true
FILTER_EXCLUDE_MOVIES=false
FILTER_MIN_DURATION_MINUTES=5
FILTER_EXCLUDE_GENRES=Hentai,Ecchi
FILTER_EXCLUDE_FORMATS=OVA,ONA
FILTER_REQUIRE_ANIME_TYPE=true
FILTER_AUTO_SUBSCRIBE_NEW_SEASON=false

# 通知（可选）
APPRISE_URLS=
```

### 11.2 Pydantic Settings

```python
class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"

    qb_host: str = "http://localhost:8080"
    qb_username: str = "admin"
    qb_password: str = "adminadmin"
    qb_save_path: str = "C:\\Downloads\\Anime"

    tmdb_api_key: str | None = None
    tmdb_read_access_token: str | None = None

    emby_host: str = "http://localhost:8096"
    emby_api_key: str | None = None
    emby_library_name: str = "Anime"

    media_library_path: str = "C:\\Media\\Anime"
    organize_template: str = "{title}\\{title} S{season:02d}E{episode:02d}.{ext}"

    check_interval_seconds: int = 600
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///anime_agent.db"

    # Agent 过滤规则
    filter_exclude_ova: bool = True
    filter_exclude_movies: bool = False
    filter_min_duration_minutes: int = 5
    filter_exclude_genres: list[str] = ["Hentai", "Ecchi"]
    filter_exclude_formats: list[str] = ["OVA", "ONA"]
    filter_require_anime_type: bool = True
    filter_auto_subscribe_new_season: bool = True
    discovery_cron: str = "0 0 * * 1"  # 每周一 00:00

    apprise_urls: str = ""
```

---

## 12. 测试策略

### 12.1 单元测试

- 每个 Tool 独立测试，外部 HTTP 用 `respx` 或 `pytest-vcr` mock。
- 每个 Node 用 mock Tool 测试分支逻辑。

### 12.2 集成测试

```python
@pytest.mark.integration
async def test_full_happy_path_with_real_qb():
    ...
```

- 默认不运行，通过 `pytest -m integration` 或 `TEST_USE_REAL_QB=1` 启用。
- 真实环境测试前检查配置是否完整，不完整则 skip。

### 12.3 CI

GitHub Actions 运行：
- `ruff check .`
- `mypy anime_agent`
- `pytest --cov=anime_agent --cov-report=xml`

---

## 13. MVP 范围

### 13.1 包含

- [x] LangGraph 工作流核心闭环
- [x] 对话层：自然语言意图解析 + 多轮澄清
- [x] 调度层：当季新番发现 + 过滤 + 订阅创建
- [x] 调度层：按播出周几智能调度任务
- [x] Bangumi / AniList / TMDB / RSS / qBittorrent / Emby / 通知 Tool
- [x] SQLite 数据持久化
- [x] LLM 种子匹配、内容分类、元数据验证
- [x] 人工审批断点（种子匹配置信度低）
- [x] FastAPI + 原生 JS Web 面板
- [x] 错误日志与重试
- [x] Windows 原生运行支持
- [x] OpenAI + Ollama 切换
- [x] Emby 媒体库刷新
- [x] pytest 单元测试 + 集成测试标记
- [x] Ruff + MyPy + pre-commit
- [x] GitHub Actions CI
- [x] README + 部署文档

### 13.2 明确不包含（进 Roadmap）

- [ ] Prometheus/Grafana 指标（只预留简单计数）
- [ ] 多轮对话上下文记忆
- [ ] 基于 Webhook 的事件驱动（替代部分轮询）
- [ ] SQLite 自动备份脚本
- [ ] 多用户/权限系统
- [ ] Telegram/Discord 等真实通知渠道（只留 apprise 入口）
- [ ] Docker 作为主要运行方式（作为可选项）
- [ ] 复杂前端构建（React/Vue 后续再升级）

---

## 14. 实施计划（加入 Conversational + 调度层 后建议 3 周）

> 注意：对话层 + 调度层 的加入会显著增加 MVP 工作量。如果进度紧张，优先保证 Orchestrator + Episode Graph 闭环，对话层 可先实现一个最小版本（只支持"下载 XXX"和"全部/指定集数"）。

### Week 1：骨架 + 工作流分层 + 数据层

**Day 1-2：工程骨架**
- [ ] `pyproject.toml` + Poetry 依赖
- [ ] `.gitignore`、`.env.example`、`README.md` 基础
- [ ] Ruff、MyPy、pre-commit 配置
- [ ] GitHub Actions CI 基础
- [ ] `config.py` Pydantic Settings（含 filter 配置）
- [ ] `utils/logger.py` loguru 配置

**Day 3-4：数据层**
- [ ] `memory/database.py` aiosqlite engine
- [ ] `memory/models.py` 数据模型（含 bangumi_id, UserRequest）
- [ ] `memory/init_db.py` 建表
- [ ] `memory/store.py` 高层 CRUD

**Day 5-6：对话层**
- [ ] `conversational/intent.py` 意图解析（正则 + LLM 兜底）
- [ ] `conversational/dialogue.py` 对话状态管理
- [ ] `conversational/response.py` 回复生成
- [ ] `conversational_state.py`
- [ ] `conversational_graph.py`
- [ ] `conversational_nodes/parse_input.py`
- [ ] `conversational_nodes/search_candidates.py`
- [ ] `conversational_nodes/ask_clarification.py`
- [ ] `conversational_nodes/confirm_action.py`
- [ ] `conversational_nodes/invoke_orchestrator.py`

**Day 7：调度层 骨架**
- [ ] `orchestrator/discovery.py` Bangumi 按 year+season 查询 + 周几推断
- [ ] `orchestrator/filter.py` 过滤规则实现
- [ ] `orchestrator/planner.py` 生成 check 任务计划
- [ ] `orchestrator_state.py`
- [ ] `orchestrator_graph.py`
- [ ] `scheduler.py` 集成 Orchestrator 调度（每周一 00:00 发现新番）

### Week 2：Tool 层 + LangGraph 核心闭环

**Day 8-9：Tool 层**
- [ ] `tools/base.py` 基类
- [ ] `tools/llm_tool.py` OpenAI/Ollama
- [ ] `tools/bangumi_tool.py` 中文元数据查询（含缓存 + 限流）
- [ ] `tools/anilist_tool.py`（含批量查询 + 限流）
- [ ] `tools/tmdb_tool.py`（支持 API Key / Read Access Token）
- [ ] `tools/rss_tool.py`
- [ ] `tools/qb_tool.py`
- [ ] `tools/emby_tool.py`
- [ ] `tools/notify_tool.py`
- [ ] `tools/filesystem_tool.py`
- [ ] 各 Tool 单元测试

**Day 10-12：LangGraph 节点**
- [ ] `state.py` EpisodeAgentState
- [ ] `conversational_state.py` ConversationalState
- [ ] `orchestrator_state.py` OrchestratorState
- [ ] `conversational_graph.py` 对话工作流 构建
- [ ] `orchestrator_graph.py` 调度工作流 构建
- [ ] `graph.py` Episode Graph 构建
- [ ] `orchestrator_nodes/parse_intent.py`
- [ ] `orchestrator_nodes/discover_season.py`
- [ ] `orchestrator_nodes/apply_filters.py`
- [ ] `orchestrator_nodes/resolve_metadata.py`
- [ ] `orchestrator_nodes/create_subscriptions.py`
- [ ] `orchestrator_nodes/schedule_checks.py`
- [ ] `orchestrator/completion.py` 完结检测与全集完成检查
- [ ] `nodes/check_tool_health.py`
- [ ] `nodes/check_updates.py`
- [ ] `nodes/fetch_rss.py`
- [ ] `nodes/match_torrent.py`
- [ ] `nodes/send_download.py`
- [ ] `nodes/poll_download.py`
- [ ] `nodes/schedule_wait_rss.py`
- [ ] `nodes/schedule_poll.py`
- [ ] `nodes/process_metadata.py`
- [ ] `nodes/organize_files.py`
- [ ] `nodes/refresh_emby.py`
- [ ] `nodes/notify_user.py`
- [ ] `nodes/handle_error.py`
- [ ] `nodes/human_review.py`
- [ ] Node 单元测试

**Day 13-14：缓存、限流与优化**
- [ ] 统一 API 限流器（semaphore + tenacity）
- [ ] Bangumi/AniList/TMDB/LLM 缓存层
- [ ] TMDB API Key / Read Access Token 配置与认证
- [ ] RSS 共享缓存
- [ ] 智能调度按周几触发
- [ ] 规则预过滤减少 LLM 调用

### Week 3：Web 面板 + 测试 + 文档

**Day 15-17：FastAPI Web 面板**
- [ ] `web.py` FastAPI 应用
- [ ] 前端 `frontend/index.html` + `app.js` + `style.css`
- [ ] Dashboard / Subscriptions / Tasks / Human Review 页面
- [ ] Assistant 聊天页面（可选降级为表单）
- [ ] Discovery 当季新番页面
- [ ] API 联调

**Day 18-19：集成测试与真实环境**
- [ ] happy path 集成测试（mock）
- [ ] Conversational + 调度层 流程测试
- [ ] 真实环境测试配置与标记
- [ ] 覆盖率报告

**Day 20-21：文档与收尾**
- [ ] 完善 `README.md`
- [ ] `docs/deployment.md`
- [ ] `docs/adr/` 初始 ADR
- [ ] 架构图
- [ ] 生成首次 CHANGELOG
- [ ] 本地端到端验证

---

## 15. 简历描述（建议）

> **AnimeAgent — 基于 LangGraph 的动漫自动化系统**
>
> - 采用 LangGraph StateGraph 编排事件驱动工作流，实现播出检测 → RSS 智能匹配 → 下载 → 内容分类 → 硬链接整理 → 媒体库刷新 → 消息推送全链路自动化。
> - 设计三层工作流架构：对话层 负责自然语言交互与意图解析，调度层 负责新番发现、过滤与任务调度，Episode Graph 负责单集执行，实现关注点分离与可插拔替换。
> - 中文场景优化：优先使用 Bangumi（番组计划）作为元数据源，AniList/TMDB 作为交叉验证与 fallback，提升中文番剧识别与播出时间准确性。
> - 构建独立的 Tool Layer，将 Bangumi/AniList/TMDB/qBittorrent/Emby 等外部系统抽象为可插拔、可 Mock 的工具，工作流节点聚焦决策逻辑，实现 IO 与业务解耦。
> - 设计基于 LLM 的 TorrentMatcher、ContentClassifier、MetadataValidation，通过 Prompt 约束与置信度阈值降低幻觉风险，低置信度自动触发 Human-in-the-Loop 断点。
> - 基于 SQLite 单文件构建零安装记忆层，支持元数据映射持久化与任务状态全生命周期追踪；提供 FastAPI + 原生 JS Web 面板进行任务监控、订阅管理、人工审批与自然语言交互。
> - 工程化：Ruff + MyPy + pytest 代码质量与测试覆盖、GitHub Actions CI、结构化日志、.env 配置管理，支持 OpenAI / Ollama 双 LLM 后端切换。

---

## 16. 额外风险与边界情况

基于你的补充，以下是还需要考虑或已在设计里处理的问题：

### 16.1 Bangumi 作为中文优先源

- 搜索时优先调用 `BangumiTool`，利用其中文名、同义词、标签优势。
- Bangumi 无结果或信息不全时，fallback 到 AniList。
- 订阅创建时同时保存 `bangumi_id` 和 `anilist_id`。
- 注意 Bangumi API 的请求频率限制，需要缓存和重试。
- Bangumi 的"播出时间"可能比 AniList 更适合中文用户习惯，但 AniList 的 `nextAiringEpisode` 更便于判断未来集数，两者可互补。

### 16.2 候选种子持久化与去重

- `episode.rss_candidates` 保存 JSON 列表，包含 hash、title、pub_date、size、link。
- 每次 `fetch_rss` 后做去重（按 info_hash），并更新候选列表。
- 已失败/放弃的 hash 写入 `torrent_failed_hashes`，避免反复尝试同一死种。

### 16.3 集数编号边界

- 番剧可能存在 Episode 0、总集篇、SP、OVA、剧场版，命名不一定按顺序。
- LLM 匹配时传入目标 `episode_number`，让 LLM 判断候选标题中的集数是否对应。
- SP/OVA/Movie 的 `episode_number` 可设为特殊值（如 0 或负数），由 `process_metadata` 输出 `content_type` 后决定整理路径。

### 16.4 字幕组与质量偏好

- MVP 阶段不引入复杂质量偏好排序。
- 可在 `RSSSource.parser_rules` 中配置 `include`/`exclude` 正则（如只保留 1080p、排除 HEVC）。
- 后续可在 `match_torrent` 中加入优先级规则：发布时间新 > 大小适中 > 知名字幕组。

### 16.5 时区处理

- AniList 返回的 `airingAt` 是 Unix 时间戳（UTC）。
- `subscription.airing_timezone` 默认 `"Asia/Tokyo"`。
- 锁定周几时，统一按播出地时区计算，再与当前 UTC 时间比较。

### 16.6 磁盘空间检查

- `send_download` 前可调用 `filesystem_tool` 检查 `QB_SAVE_PATH` 可用空间。
- MVP 阶段可只做日志警告，不阻塞下载；后续可改为硬性拒绝。

### 16.7 已存在文件跳过

- `organize_files` 前检查目标路径是否已存在同名文件。
- 若存在且大小一致，直接标记完成；若不一致，按策略覆盖或重命名。

### 16.8 qBittorrent 清理

- 整理完成后，可选择从 qBittorrent 删除种子和文件（仅保留硬链接后的媒体库文件）。
- MVP 阶段默认不自动删除，避免误删；在配置中增加 `QB_DELETE_AFTER_ORGANIZE` 开关。

### 16.9 并发下载数控制

- 避免同时下载过多任务导致带宽/磁盘压力过大。
- 在 `send_download` 前检查当前 qBittorrent 正在下载的任务数，超过阈值则排队等待。
- MVP 阶段可先不实现，作为 Roadmap 项。

### 16.10 网络抖动导致的误判定

- qBittorrent 偶尔会出现短暂 0 速度，1 小时无速度判定已较宽松。
- 可增加"连续 N 次检查都 0 速度"才判定 stalled，MVP 阶段 1 小时足矣。

### 16.11 RSS 源失效

- 如果 `RSSTool` 连续多次无法拉取某个 RSS 源，标记 `RSSSource.is_active = False`。
- Web 面板显示源状态，用户可手动重新启用。

### 16.12 API 限流与调用成本控制

系统涉及多个外部 API，需要统一限流和缓存策略：

| API | 大致限制 | 应对策略 |
|-----|----------|----------|
| Bangumi | 无官方严格限流，但部分地区/网络可能无法访问 | 缓存 6H，发现任务每周一次，详情批量/串行 + 随机延迟；不可用时 fallback AniList |
| AniList | 约 90 req/min（未认证 30/min） | 批量查询 `id_in`，缓存 1H，异常时指数退避 |
| TMDB | 40 req/10s | 缓存 24H，元数据验证时才调用 |
| qBittorrent | 本地服务，限制宽松 | 健康下载 30min 轮询，避免高频 poll |
| OpenAI | 按 token 计费 | 规则预过滤减少调用，轻量任务用 Ollama，结果缓存 |

**统一措施**：
1. **全局 HTTP 客户端**：所有 Tool 共用带限流器的 `httpx.AsyncClient` 实例（通过 `limits` + `tenacity`）。
2. **缓存层**：使用 SQLite 或内存字典缓存 API 响应，按数据源设置 TTL。
3. **请求队列**：对 Rate Limit 严格的服务，使用 async semaphore 控制并发数。
4. **失败降级**：AniList 限流时 fallback 到 Bangumi；LLM 不可用时 fallback 到规则匹配。
5. **日志监控**：记录每个 Tool 的调用次数、延迟、失败率，便于后续优化。

---

## 17. 重大优化方向

除了你已经提到的点，以下优化能显著提升系统效率、成本和鲁棒性。建议按优先级逐步加入：

### 17.1 智能调度与中文源优化

- **按播出周几调度**：锁定 `expected_airing_weekday` 后，只在播出当天 00:00 之后启动检查，而非每 10 分钟轮询。
- **Bangumi 优先**：中文名搜索和播出时间优先走 Bangumi，减少 AniList 在中文场景下的歧义查询。
- **Bangumi 缓存**：搜索结果和 subject 详情缓存 2-6 小时，降低 API 压力。
- **按集数进度调度**：若上一集已下载完成，下一集理论上在 7 天后播出，不必提前多天频繁检查。
- **休眠期**：已完结的 Subscription 标记为 `completed`，不再参与轮询。

### 17.2 批量与缓存

- **Bangumi/AniList 批量查询**：尽量合并多个 subject/media 查询，减少 HTTP 请求数。
- **RSS 共享缓存**：同一 RSS 源每分钟/每小时只拉取一次，结果分发给所有等待该源的 Subscription。
- **TMDB 缓存**：按查询 key 缓存 24 小时，减少重复调用。
- **LLM 决策缓存**：对相同候选集 hash 的结果缓存，避免重复推理。

### 17.3 规则预过滤（省 LLM Token）

- 先用正则从 RSS 标题中提取集数、字幕组、分辨率、格式。
- 集数明显不匹配、发布日期早于播出时间、已被 `torrent_failed_hashes` 标记的候选直接剔除。
- 只有经过预过滤仍 ambiguous 的候选才交给 LLM。

### 17.4 下载健康自适应轮询

- 健康下载：每 30 分钟检查一次。
- 疑似 stalled：每 5 分钟检查一次，尽快判定并换种。
- 元数据下载阶段：每 2 分钟检查一次，避免长时间卡 metadata。

### 17.5 候选种子排序策略

在没有 LLM 时，先用启发式规则排序：
1. 发布时间越近越好（但不过早于播出时间）；
2. 文件大小在合理区间（排除过小/过大）；
3. 匹配用户偏好字幕组（可选）；
4. 分辨率匹配（如 1080p）。
LLM 在此基础上做最终选择或给出置信度。

### 17.6 跨订阅去重

- 若用户同时订阅了"系列"和"单季"（虽然 MVP 一 Subscription 一季），避免为同一文件下载两次。
- 按 `info_hash` 全局去重。

### 17.7 增量更新与事件驱动

- 当前是轮询式，未来可接入 AniList Webhook（如果有）或第三方播出提醒 API，从轮询转事件驱动。
- RSS 也可用 Webhook 或 pubsubhubbub 加速发现。

### 17.8 降级策略

- LLM 服务不可用或超时时，回退到规则匹配 + 最高置信度候选。
- AniList 不可用时，使用本地缓存的元数据继续工作（可能错过新番）。
- qBittorrent 不可用时，暂停下载类任务，只保留 check/update。

### 17.9 智能助手交互优化

- 用户输入模糊时，先给出最可能的 3 个候选，让用户选择，而不是直接追问。
- 支持多轮对话上下文，允许用户说"刚才那个，下载全部"。
- 支持自然语言集数范围："第 3 到 8 集"、"跳过第 5 集"、"全部"。

### 17.10 数据与模型层面的优化

- `Episode` 表按 `subscription_id + episode_number` 加唯一约束，避免重复创建。
- `rss_candidates` 和 `torrent_failed_hashes` 用 JSON 存储，避免过度范式化。
- 定期清理已完成 Episode 的历史 RSS 候选，控制 DB 大小。

---

## 18. 需要你最终确认

请确认以上架构与实施规划无误。如无调整，我将按此文档开始编码。

主要变更确认：
1. **MVP 周期**：从 2 周调整为 **3 周**；
2. **工作流分层**：对话工作流 + 调度工作流 + Episode Graph（执行）；
3. **中文源优先**：Bangumi 作为首选元数据源，AniList/TMDB 作为 fallback；
4. **Episode Graph 优化**：
   - 新增 `check_tool_health` 快速失败；
   - `classify_content` + `validate_metadata` 合并为 `process_metadata`；
   - `wait_rss_retry` / `poll_download` 自循环改为外部 Scheduler 调度（`schedule_wait_rss` / `schedule_poll`），Graph 不阻塞、重启不丢任务；
5. **自动订阅**：`FILTER_AUTO_SUBSCRIBE_NEW_SEASON=true` 默认开启；用户可在 Web 关闭指定 Subscription 的 `auto_download_enabled`；
6. **发现频率**：Orchestrator 新番发现从每天一次改为 **每周一 00:00**；
7. **前端按年+季度浏览**：Discovery 页支持 2026 春季/夏季/秋季/冬季等维度切换；
8. **API 限流**：增加统一限流器、缓存层、降级策略；
9. **TMDB 配置**：支持 `TMDB_API_KEY` 和 `TMDB_READ_ACCESS_TOKEN`；
10. **已播出多集处理**：发现时若已播到第 N 集，会为 1-N 集创建 Episode 并错开调度补档；
11. **自动下载下一集**：Subscription 已包含整季所有 Episode，Scheduler 按周几触发新集检查；
12. **完结检测**：通过 AniList/Bangumi status + 已播集数 == total_episodes 判定；
13. **全集完成检查**：聚合所有 Episode 状态，全为 `completed` 时标记 Subscription 完结并通知；
14. **工作流数量**：3 个 LangGraph StateGraph（Conversational / Orchestrator / Episode）；
15. **自定义工具**：支持用户按 `BaseTool` 接口编写工具并在 Node 中调用；
16. **交互方式**：Web 面板同时支持自然语言聊天 + 表单订阅；
17. **Token 节省**：按播出周几调度 + 批量查询 + 缓存 + 规则预过滤。

主要风险点提醒：
1. **3 周仍然紧张**，如果 对话层 的 NL 交互复杂度超预期，优先保证表单订阅 + Orchestrator + Episode Graph 闭环；
2. **Bangumi API 限制/可用性**：需要处理请求频率限制、无结果 fallback 到 AniList，以及部分地区网络不可达；
3. **API 调用成本**：虽然每周发现一次量不大，但需确保缓存和限流在代码中落地；
4. **Windows 路径与 Docker 跨平台**需要特别处理；
5. **LLM 主导决策**可能导致测试结果不稳定，需要通过 mock 和置信度阈值控制；
6. **外部 Scheduler 调度模式**需要小心处理并发：同一 Episode 在被调度前不应被重复触发；
7. **补档场景**：发现时已播多集会瞬间创建多个 Episode，需要错峰调度避免 API/下载压力；
8. **Token 节省策略**需要在代码中显式实现缓存和批量查询，否则容易变成"每个 episode 都调 LLM"的高成本系统。


---

## 19. 术语修订与架构建议（Agent vs 工作流 vs 服务）

> 本章节是对全文术语的修正说明。

### 19.1 为什么不再把每个 LangGraph 节点都叫 Agent？

在 LangGraph 语境里，**Agent** 通常指一个能“感知状态 → 用 LLM 推理 → 选择并调用工具 → 循环直到完成目标”的自治实体。它必须具备：

1. 明确的角色 / system prompt；
2. 可观察的状态；
3. 自主决策下一步动作的能力（ReAct / Tool-calling 循环）。

按这个标准，本项目里：

- `fetch_rss`、`send_download`、`organize_files` 等只是**工具调用节点**，不是 Agent。
- `Orchestrator` 主要做规则过滤、数据转换、写数据库，是**调度服务**，不是 Agent。
- `Conversational` 可以是 Agent，也可以只是一个带 JSON Schema 的 LLM 意图解析函数，取决于是否需要多轮澄清。
- 只有 **Episode 执行层** 符合 Agent 特征：它要观察 RSS 候选、用 LLM 判断匹配、监控下载、决定重试/换种/整理，具备感知-决策-行动的循环。

因此，全文把“LangGraph StateGraph / Node”统称为 Agent 会误导读者，也会让你在面试/简历中被追问“多 Agent 怎么协作”时难以自圆其说。

### 19.2 推荐的最小架构（MVP 阶段）

**不要硬凑多 Agent**。MVP 最稳的架构是：

```
用户输入
  │
  ├─ 自然语言 ──▶ 对话层（意图解析函数 / 小型 LLM Agent）
  │                    │
  │                    ▼
  │              结构化意图 ParsedIntent
  │                    │
  └─ Web 表单 ────────┘
                      │
                      ▼
              调度服务（Orchestrator Service）
              - 搜索/发现番剧
              - 应用过滤规则
              - 创建 Subscription / Episode
              - 写入 TaskSchedule
                      │
                      ▼
              外部 Scheduler（APScheduler）
                      │
                      ▼
              Episode Agent（唯一 LangGraph Agent）
              - fetch_rss
              - match_torrent（LLM）
              - send_download
              - poll_download
              - organize_files
              - refresh_emby / notify
```

优点：

- **认知负担小**：开发者只需要理解一个 LangGraph Agent。
- **测试简单**：对话层、调度层都是纯函数/服务，Episode Agent 的每个 Node 独立可测。
- **扩展清晰**：后续如果要做“自动追新番 vs 手动订阅”等复杂协商，再引入 Supervisor Agent 也不迟。

### 19.3 什么时候才需要真正的多 Agent 协作？

如果未来出现以下需求，才值得引入多个 Agent：

1. **Discovery Agent 与 Episode Agent 需要协商**：比如 Discovery Agent 发现一部番有多个 RSS 源、多种字幕组偏好，需要和 Episode Agent 讨价还价选哪个源。
2. **用户意图极度开放**：对话层不仅要解析“下载 XXX”，还要处理“我最近很忙，先帮我排着，周末再下”“这部番只要 1080p 的”等复杂上下文，需要对话 Agent 长期维护用户偏好记忆。
3. **自动修复和自愈**：下载失败时，一个专门的“Diagnosis Agent”能自主分析日志、调用不同工具尝试修复，而不是走固定重试分支。
4. **需要不同模型/成本策略**：简单 NLU 用本地 Ollama，复杂决策用 GPT-4o，可以把它们封装成不同 Agent，由 Supervisor 动态分配任务。

### 19.4 如果一定要做多 Agent，建议采用 Supervisor 模式

Supervisor 是最适合本项目的多 Agent 协作模式：

```
Supervisor（路由 Agent / 规则路由器）
    │
    ├─▶ 对话 Agent（UserIntentAgent）
    │       工具：BangumiTool / AniListTool
    │       输出：ParsedIntent
    │
    ├─▶ 订阅管理 Agent（SubscriptionManagerAgent）
    │       工具：BangumiTool / AniListTool / ContentFilter / EpisodePlanner
    │       输出：Subscription + TaskSchedule
    │
    └─▶ 执行 Agent（EpisodeExecutionAgent）
            工具：RSSTool / QBTool / EmbyTool / NotifyTool / LLMTool
            输出：Episode 状态更新
```

协作方式：

- **消息契约**：Agent 之间不直接操作对方内存，而是通过 Pydantic 消息对象传递结果（如 `ParsedIntent`、`SubscriptionCreated`、`EpisodeCompleted`）。
- **共享持久化**：结果写入 SQLite，Supervisor 读取后再决定下一步。
- **调用方式**：Supervisor 把子 Agent 当作可调用的 subgraph / 函数；子 Agent 执行完返回结果，Supervisor 再决定路由。

### 19.5 简历/对外描述建议

如果你想强调 Agent，可以这样说：

> AnimeAgent 采用 LangGraph 编排事件驱动工作流，核心是一个 **Episode Agent**：它通过 LLM 完成种子智能匹配、下载健康监控与失败自愈，并调用 qBittorrent、Emby、RSS 等工具完成单集下载到媒体库整理的全闭环。对话层和调度层以可测试的服务/工作流形式存在，避免过度设计。

这比“三个 Agent 协作”更经得起追问。

### 19.6 落地建议

1. **立即Rename**：把代码目录 `agents/conversational/`、`agents/orchestrator/` 改为 `intents/` 或 `services/`，只保留 `agents/episode/`。
2. **先跑通 Episode Agent**：用 `StateGraph` 把现有 `fetch_rss → match_torrent → send_download` 连起来，补齐轮询、整理、通知节点。
3. **对话层最小化**：先用一个 LLM 函数输出 `ParsedIntent`，支持 3-5 种意图即可。
4. **调度层服务化**：`Orchestrator` 实现为 `services/discovery_service.py` + `services/subscription_service.py`，由 APScheduler 调用。
5. **保留扩展点**：在 `EpisodeAgentState` 或消息契约里预留 Agent ID / 消息通道，未来改 Supervisor 时不重构核心。
