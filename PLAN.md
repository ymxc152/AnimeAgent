# AnimeAgent 项目计划与路线图

> 状态：**MVP 已完成，进入质量收尾与扩展准备阶段**  
> 更新时间：2026-06-14  
> 本文件替代并整合了以下旧计划：
> - `IMPLEMENTATION_PLAN.md`（TDD 实施计划）
> - `docs/OLD_ANIME_DOWNLOAD_DESIGN.md`（老番 fallback 与对话统计设计）
> - 原 `PLAN.md`（前端与功能改进计划）
>
> 架构细节仍保留在 `docs/ARCHITECTURE_AND_PLAN.md` 中，作为长期参考。

---

## 1. 项目定位

AnimeAgent 是一个基于 LangGraph 的事件驱动动漫追番自动化系统：

```
播出检测 → RSS/资源搜索 → 种子匹配 → qBittorrent 下载
  → 内容分类 → 硬链接整理 → Emby 刷新 → 通知推送
```

中文场景优先使用 **Bangumi**，AniList / TMDB 作为 fallback；Episode 执行层保留为 LangGraph StateGraph；调度层与对话层按架构建议降级为可测试的服务，避免过度设计。

---

## 2. 已完成功能

### 2.1 后端核心

| 模块 | 实现内容 | 关键文件 |
|------|----------|----------|
| Tool 层 | Bangumi、AniList、TMDB、RSS、qBittorrent、Emby、Notify、Filesystem、LLM、Bash、AnimeGarden 共 11 个工具 | `anime_agent/tools/` |
| 资源兜底 | `AnimeGardenTool` + `search_resources` 节点；老番/完结番自动 fallback | `tools/animes_garden_tool.py`, `agents/episode/nodes/search_resources.py`, `services/metadata_resolver.py` |
| Episode Graph | `fetch_rss → match_torrent → send_download → poll_download → organize_files → refresh_emby → notify_user`；含 `human_review` / `schedule_resume` / `handle_error` | `agents/episode/` |
| 服务层 | MetadataResolver、TorrentSelector、TorrentHealth、ContentFilter、EpisodePlanner、CompletionChecker、DiscoveryService、Scheduler、QBSyncService、StatusQueryService、AutoSubscribeLLMFilter | `services/` |
| 对话层 | 规则意图解析 + LLM 兜底 + 多轮对话上下文 + 自然语言订阅/重试 + `/api/chat` 端点 | `agents/conversational/`, `services/status_query.py`, `web.py` |
| 数据层 | SQLite + SQLAlchemy 2.0 async；Subscription / Episode / RSSSource / AutoSubscribeRule / TaskSchedule / ErrorLog 等 | `memory/` |
| Web API | FastAPI；订阅、剧集、发现、RSS 源、自动订阅规则、聊天、健康检查、日志 | `web.py`, `web_schemas.py` |
| 配置 | Pydantic Settings；AnimeGarden、资源回退、过滤规则、路径映射等 | `config.py`, `.env.example` |

### 2.2 前端与交互

| 能力 | 状态 |
|------|------|
| 首页 `/api/subscriptions` N+1 修复 | ✅ |
| Dashboard 健康检查按需加载 + 手动刷新 | ✅ |
| 页面自动刷新（Dashboard/Subscriptions/Episodes 5s，RSS/Logs 10s） | ✅ |
| 状态标签中文化 | ✅ |
| Chat 对话页面 | ✅ |
| 剧集下载进度条 / 速度 / 详情弹窗 | ✅ |
| 剧集状态多选筛选 | ✅ |
| 发现页多语言搜索 | ✅ |
| 自动订阅规则管理 + LLM 辅助决策 | ✅ |
| RSS 源弹窗 CRUD | ✅ |
| 订阅 Bangumi/AniList ID 查询回填 | ✅ |
| Toast / URL 同步 / 骨架屏 / Vitest 测试 | ✅ |

### 2.3 测试与质量

| 检查项 | 状态 |
|--------|------|
| Ruff lint | ✅ 通过（`anime_agent` + `tests`） |
| MyPy 类型检查 | ✅ 通过（`anime_agent`） |
| 前端 build / lint / test | ✅ 通过 |
| pytest | 约 350 用例，主要模块通过；并发运行时偶发个别失败，单独运行可恢复 |

---

## 3. 当前未解决问题

### 3.1 测试执行时间

- 当前全量收集约 650 个用例，串行执行需 5~8 分钟；按模块分批运行均通过。
- 尚未引入 `pytest-xdist` 等并发加速；单模块运行稳定。

### 3.2 数据与字段债务

- `Episode.torrent_hash` / `torrent_info_hash` 已统一为 `torrent_hash`；
  - `init_db.py` 启动时自动迁移旧数据；
  - 相关 API、前端 types 与详情展示已同步。

### 3.3 架构债务

- `CompletionChecker` 外部状态分支已修复并精简。
- `process_metadata` 节点为最小实现，未接入 TMDB 季度验证。
- `metrics.py` / `utils/folder.py` 仍未落地（原预留）。
- 调度层 LangGraph 未实现；按架构建议保持服务化，但对外描述需统一。

### 3.4 文档

- `README.md` 已部分更新，但「对话层将在后续版本迭代」等表述已过时，需刷新。
- `CHANGELOG.md` 需补充近几个迭代的变更摘要。

---

## 4. 下一步行动清单

### P0：质量收尾（1-2 天）

1. **验证 pytest 全量通过并优化执行时间**
   - 当前按模块分批运行均通过；
   - 全量串行运行约 5~8 分钟，建议引入 `pytest-xdist` 或按模块拆分 CI job；
   - 检查是否有慢测试可优化。
2. **统一 `torrent_hash` / `torrent_info_hash`** ✅ 已完成
   - 删除 `Episode.torrent_info_hash` 模型字段；
   - `init_db.py` 启动时自动迁移旧数据；
   - 更新 `runner.py`、`qb_sync_service.py`、`web.py`、`web_schemas.py`、前端 types 与详情展示；
   - 验证：相关测试通过。
3. **刷新 README / CHANGELOG**
   - 更新对话层状态；
   - 补充 Anime Garden、自动订阅规则、LLM 决策等特性描述；
   - 更新路线图。

### P1：核心体验加固（3-5 天）

1. **自适应轮询间隔** ✅
   - `PollDownloadNode` / `schedule_resume` 根据下载健康状态动态调整下次检查时间（健康 30min、stalled 5min、metaDL 2min）。
2. **修复 `CompletionChecker` 不可达分支** ✅
   - 重构完结判定逻辑，确保外部状态 `FINISHED` 与全集完成能同时触发通知。
3. **TMDB 季度验证接入 `process_metadata`**
   - 当配置 `TMDB_API_KEY` 时，交叉验证季数与集数映射。
4. **Episode 唯一约束与去重** ✅
   - 在 `Episode.subscription_id + episode_number` 上确保唯一约束已生效；
   - `SendDownloadNode` 添加前查询 `EpisodeStore.get_by_torrent_hash`，跨订阅全局按 `info_hash` 去重；
   - 添加失败时返回 `retry_match` 以便重新匹配其他候选。

### P2：扩展能力（可选，1-2 周）

1. **多轮对话上下文** ✅（基础版已落地）
   - `ChatMessage` 表按 `session_id` 维护对话历史；
   - 支持候选选择、订阅确认等状态机。
2. **自然语言订阅** ✅（基础版已落地）
   - 对话层识别 `subscribe` / `select_candidate` 意图后调用 `MetadataResolver` 搜索并创建 Subscription。
3. **通知渠道**
   - 接入 apprise 真实通知（Telegram / Discord / Bark 等）。
4. **Webhook / 事件驱动**
   - 接入 qBittorrent 完成事件，减少轮询延迟。
5. **指标与可观测性**
   - 落地 `metrics.py` 计数器；
   - 可选 Prometheus / Grafana 导出。

### P3：工程化与部署

1. Docker / Docker Compose 支持。
2. SQLite 自动备份脚本。
3. GitHub Actions CI 重新启用全量检查（Ruff + MyPy + pytest + 前端 build）。

---

## 5. 验收标准

- [ ] pytest 全量稳定通过（含并发运行）。
- [x] `torrent_hash` / `torrent_info_hash` 统一。
- [ ] README / CHANGELOG 反映当前功能。
- [ ] CI 绿色。
- [x] 自适应轮询落地。
- [x] `CompletionChecker` 逻辑修复。

---

## 6. 相关文档

| 文档 | 说明 |
|------|------|
| `docs/ARCHITECTURE_AND_PLAN.md` | 架构决策、数据模型、工作流拓扑、术语修订 |
| `README.md` | 项目简介、快速开始、核心特性 |
| `CHANGELOG.md` | 版本变更记录 |
| `.env.example` | 环境变量模板 |

---

## 7. 决策记录

1. **调度层未使用 LangGraph**：按 `docs/ARCHITECTURE_AND_PLAN.md` §19 建议，将调度层服务化，降低认知负担与测试成本。
2. **对话层轻量实现**：先使用规则意图解析 + 模板回复，LLM 润色层预留；多轮上下文延后。
3. **老番判定**：同时依据 AniList `status == FINISHED` 与播出时间 > 90 天；阈值可配置。
4. **候选池统一**：`Episode.torrent_candidates` 同时承载 RSS 与 AnimeGarden 候选，带 `source` 标记。
