# 老番/全集下载 fallback 与对话统计功能设计

> 本文档描述：当用户请求的番剧无法通过现有 RSS 源找到种子时，如何通过 `api.animes.garden/resources` 进行兜底搜索，并支持用户通过对话查询下载状态、季数集数等统计信息。
>
> 状态：**部分实现**（2026-06-13 更新）。`AnimeGardenTool`、统一候选格式、`search_resources` 节点、缓存、配置项已落地；`StatusQueryService` 尚未实现。详见下方「实现状态」章节。

---

## 实现状态（新增）

### 已实现

| 组件 | 位置 | 说明 |
|------|------|------|
| `AnimeGardenTool` | `anime_agent/tools/animes_garden_tool.py` | 已实现搜索、磁力 hash 提取、size 单位转换、失败处理。 |
| 统一候选格式 | `anime_agent/tools/base.py` 相关 + `tools/rss_tool.py` | 候选条目统一包含 `info_hash`、`title`、`link`、`source`、`size`、`published`、`fansub`、`publisher`、`detail_url`、`subject_id`。 |
| `search_resources` 节点 | `anime_agent/agents/episode/nodes/search_resources.py` | 在 RSS 无候选时调用 `AnimeGardenTool`，输出通用候选池。 |
| `match_torrent` 接入 | `anime_agent/agents/episode/nodes/match_torrent.py:48-53` | 候选为空且未搜索过资源时，返回 `status="search_resources"`。 |
| 候选池字段 | `anime_agent/memory/models.py:81` | 使用 `torrent_candidates` 字段保存通用候选池（来源可为 rss/animes_garden）。 |
| `torrent_failed_hashes` | `anime_agent/memory/models.py:91` | 失败 hash 记录已存在，用于排除已尝试过的死种。 |

### 尚未实现 / 不完整

| 组件 | 规划位置 | 差距说明 |
|------|----------|----------|
| 关键词缓存 | `AnimeGardenTool` | ✅ 已实现；默认 1 小时 TTL，可通过 `ANIME_GARDEN_CACHE_TTL_SECONDS` 调整。 |
| 配置项 | `config.py` / `.env.example` | 已添加 `ANIME_GARDEN_BASE_URL`、`ANIME_GARDEN_TIMEOUT_SECONDS`、`ANIME_GARDEN_CACHE_TTL_SECONDS`、`RESOURCE_FALLBACK_ENABLED`、`RESOURCE_SEARCH_MAX_PAGES`。 |
| 老番自动判定 | `MetadataResolver` / Subscription 创建逻辑 | §5.1 条件 4 与 §6.2 要求根据完结状态/播出时间自动设置 `fallback_to_resource_search`，当前未实现。 |
| 分页拉取 | `AnimeGardenTool` / `search_resources` | 已支持；`RESOURCE_SEARCH_MAX_PAGES` 控制最大页数，默认 1。 |
| `poll_download` 失败后再匹配 | `anime_agent/agents/episode/nodes/poll_download.py` | §5.2 流程要求失败后回到 `match_torrent`（含资源候选），当前实现进入 `schedule_resume`，未自动重匹配。 |
| `mark_failed_hash` 节点 | §5.2 | 未作为独立节点；失败 hash 由 `send_download` / `poll_download` 自行维护。 |
| `StatusQueryService` | §7 | 未实现；对话层本身也未实现。 |
| `query_*` 意图 | `conversational/intent.py` | 未实现。 |
| 模板回复 | §7.3 | 未实现。 |

### 已知问题

1. ~~**`AnimeGardenTool.invoke` 签名违反 Liskov 替换原则**~~ ✅ **已修复**
   - 位置：`anime_agent/tools/animes_garden_tool.py:66`
   - 当前签名与 `BaseTool.invoke(self, input_data: ToolInput)` 一致；内部通过 `isinstance` 校验具体输入类型，MyPy 通过。

2. ~~**`AnimeGardenTool` 无缓存**~~ ✅ **已修复**
   - 同一关键词 1 小时内缓存，避免重复调用。

3. **候选去重依赖调用方**
   - 规划 §3 提到按 `info_hash` 去重；当前 `search_resources` 与 `fetch_rss` 各自返回候选，去重逻辑在 `runner.py` 中合并，可能不够完善。

4. **资源搜索触发条件偏保守**
   - 仅在 RSS 完全无候选时触发；规划 §5.1 还建议在 `match_torrent` 连续无匹配、poll 失败、老番预判时触发。

### 实施步骤更新

原 §9 实施步骤可更新为：

- **Phase 1**：✅ 已完成（Tool + 统一候选格式）。
- **Phase 2**：🔄 部分完成（`search_resources` 节点已接入，但 `poll_download` 失败重匹配、候选池语义扩展未完整落地）。
- **Phase 3**：❌ 未开始（老番自动判定）。
- **Phase 4**：❌ 未开始（`StatusQueryService`、对话统计）。
- **Phase 5**：✅ 已完成（配置项与文档同步，`.env.example` 与 `ARCHITECTURE_AND_PLAN.md` 已更新）。

---

## 1. 背景与目标

### 1.1 问题

当前系统依赖 RSS 源做种子发现，但 RSS 通常只保留最近 50~100 条资源。用户可能要求下载：

- 几年前已完结的老番；
- 当季番但某集发布时间较早、已滑出 RSS 列表；
- 非热门番剧，字幕组发布不频繁。

这些情况下 `RSSTool` 会长期无候选，导致 Episode 卡在 `waiting_for_rss`。

### 1.2 目标

1. **兜底搜索能力**：RSS 找不到时，自动通过 `api.animes.garden/resources` 按番剧名搜索资源。
2. **全集/老番下载**：用户说"下载《XXX》全部"时，能够确认季数、集数、播出状态，再为每一集匹配并下载。
3. **失败重匹配**：`qBittorrent` 下载失败（死种、卡元数据、过慢）后，除了换 RSS 候选，还能回到兜底搜索重新匹配。
4. **对话查询能力**：用户可以问"我在下载哪些番""《XXX》下完了吗""《YYY》有多少集"等，系统返回自然语言回答。

---

## 2. 关键外部 API

### 2.1 Anime Garden Resources API

```
GET https://api.animes.garden/resources?search={keyword}
```

返回示例：

```json
{
  "status": "OK",
  "resources": [
    {
      "id": 2436978,
      "title": "[jibaketa合成][...] Sousou no Frieren 2nd Season - 10 END [...]",
      "magnet": "magnet:?xt=urn:btih:M5EQDHT6AVQORG45NHZIHBRYIZ7SR5W7",
      "href": "https://animes.garden/detail/...",
      "size": 854835,
      "fansub": { "name": "jibaketa" },
      "publisher": { "name": "..." },
      "subjectId": 12345,
      "createdAt": "2026-06-05T15:15:00.000Z"
    }
  ]
}
```

字段说明：

| 字段 | 含义 | 内部用途 |
|------|------|----------|
| `title` | 资源标题 | LLM 匹配、展示给用户 |
| `magnet` | 磁力链接 | 交给 qBittorrent 下载 |
| `href` | 源站详情页 | 人工审批时展示 |
| `size` | 文件大小（KB） | 候选排序、去重 |
| `createdAt` | 发布时间 | 候选排序、 aired 校验 |
| `fansub` / `publisher` | 字幕组/发布者 | 展示、偏好过滤 |
| `subjectId` | Bangumi Subject ID | 与 `Subscription.bangumi_id` 交叉验证 |

### 2.2 与现有 Tool 层的关系

`AnimeGardenTool` 与 `RSSTool` 处于同一层，都是**候选发现工具**；它们的输出需要统一成同一种 `candidate` 格式，供 `TorrentSelector` 使用。

---

## 3. 统一候选格式

为了不对 `TorrentSelector` 做大量改动，两种来源返回的候选都规范为：

```python
{
    "info_hash": "M5EQDHT6AVQORG45NHZIHBRYIZ7SR5W7",  # 小写
    "title": "[jibaketa合成]... Sousou no Frieren 2nd Season - 10 END ...",
    "link": "magnet:?xt=urn:btih:M5EQDHT6AVQORG45NHZIHBRYIZ7SR5W7",
    "source": "animes_garden",  # 或 "rss"
    "size": 875548160,          # 统一为 bytes
    "published": "2026-06-05T15:15:00+00:00",
    "fansub": "jibaketa",
    "publisher": "...",
    "detail_url": "https://animes.garden/detail/...",
    "subject_id": 12345,
}
```

`RSSTool` 在现有 `_normalize_entry` 中增加 `source: "rss"`；`AnimeGardenTool` 在解析时直接生成上述结构。

---

## 4. 新 Tool：`AnimeGardenTool`

### 4.1 接口

```python
class AnimeGardenToolInput(ToolInput):
    search: str
    page: int = 1

class AnimeGardenTool(BaseTool):
    name = "animes_garden"
    description = "Search anime torrent resources via Anime Garden API as RSS fallback."

    async def invoke(self, input_data: AnimeGardenToolInput) -> ToolOutput:
        ...
```

### 4.2 关键实现点

1. **关键词生成**：优先使用 `title_chinese`，其次 `title_romaji` / `title_native`。可附加分辨率/字幕组偏好，但 MVP 阶段只传番剧名。
2. **磁力链接转 info_hash**：正则 `urn:btih:([a-fA-F0-9]{40})`，不区分大小写，统一转小写。
3. **size 单位转换**：API 返回 KB，乘以 1024 转成 bytes。
4. **分页**：如果第一页无足够候选，可继续拉取下一页（预留 `page` 参数，MVP 可只拉一页）。
5. **失败处理**：HTTP 失败、JSON 异常、无结果都返回 `ToolOutput(success=False, error=...)`。
6. **缓存**：同一关键词 1 小时内缓存，避免重复调用。

---

## 5. 工作流改动

### 5.1 老番判定策略

不需要用户显式说"这是老番"。Episode Agent 在以下任一情况下触发 `AnimeGardenTool`：

1. `fetch_rss` 返回空候选；
2. `match_torrent` 连续 N 次（如 2 次）无匹配，且 `rss_candidates` 已耗尽；
3. `poll_download` 判定当前种子失败，且 `rss_candidates` 中无其他可用候选；
4. `Subscription` 的 `status == "completed"` 或 `last_airing_at` 距今超过 90 天（可配置）。

> 注意：条件 4 是预判，可在创建 Subscription 时设置 `use_resource_fallback=true`，避免对新番浪费 API 调用。

### 5.2 Episode Graph 新增/调整节点

```text
START
  │
  ▼
check_updates
  │
  ▼
fetch_rss
  │── 有候选 ──▶ match_torrent
  │── 无候选 ──▶ search_resources ──▶ match_torrent
  │
  ▼
match_torrent
  │── 高置信度 ──▶ send_download
  │── 低置信度 ──▶ schedule_wait
  │── 无匹配 ──▶ search_resources（如未搜索过）
  │
  ▼
send_download
  │
  ▼
poll_download
  │── 完成 ──▶ organize_files
  │── 失败 ──▶ mark_failed_hash ──▶ match_torrent（重新匹配，含资源候选）
  │── 健康 ──▶ schedule_poll
```

新增节点说明：

| 节点 | 职责 | 关键输出 |
|------|------|----------|
| `search_resources` | 调用 `AnimeGardenTool` 搜索并合并候选 | `torrent_candidates`（带 source 标记） |
| `mark_failed_hash` | 把失败 hash 加入 `torrent_failed_hashes`，并从候选池移除 | `torrent_failed_hashes` |

### 5.3 `match_torrent` 增强

`MatchTorrentNode` 的输入从 `rss_candidates` 改为 `torrent_candidates`（通用候选池）。流程：

1. 读取候选池；
2. 排除 `torrent_failed_hashes`；
3. 按集数预过滤；
4. 如果候选池为空且未搜索过资源 API：
   - 返回状态 `search_resources`（让 Graph 进入 `search_resources` 节点）；
5. 调用 `TorrentSelector`；
6. 如果 `confidence >= 0.8`：进入 `send_download`；
7. 如果低置信度：累加 `low_confidence_count`；
8. 如果无匹配且已搜索过资源 API：进入 `schedule_wait` 或 `failed`。

### 5.4 `TorrentSelector` 增强

`_prefilter` 已支持集数正则，无需大改。需要：

- 接受 `source` 字段并在 prompt 中展示（帮助 LLM 区分 RSS/资源站）。
- 对于老番全集下载，可一次性传入多个候选，让 LLM 选择最匹配当前集数的条目。

Prompt 微调示例：

```text
Target episode: 10
Known titles: 葬送的芙莉莲, Sousou no Frieren, 葬送のフリーレン

Candidates:
1. [RSS] title=... size=... hash=...
2. [animes_garden] title=... size=... hash=...

Return a JSON object with info_hash, confidence (0.0-1.0), and reason.
```

---

## 6. 数据模型调整

### 6.1 复用 vs 新增字段

`Episode` 表已有：

```python
rss_candidates = Column(Text)       # JSON
rss_last_checked_at = Column(DateTime)
rss_attempt_count = Column(Integer, default=0)
torrent_failed_hashes = Column(Text)  # JSON
```

建议：**把 `rss_candidates` 改名为 `torrent_candidates`**（或保留字段名但语义扩展为"候选池"），因为候选不再只来自 RSS。

如果避免迁移，可以新增字段：

```python
resource_candidates = Column(Text)      # JSON: Anime Garden 搜索结果
resource_searched_at = Column(DateTime)
resource_search_attempts = Column(Integer, default=0)
```

MVP 推荐：直接复用 `rss_candidates`，但统一称为 **候选池（candidate pool）**，每条候选带 `source` 字段。

### 6.2 Subscription 新增字段（可选）

```python
class Subscription(Base):
    ...
    fallback_to_resource_search = Column(Boolean, default=True)
    # 当创建时检测到番剧已完结/老番，自动设为 true
```

或者在发现阶段由 `MetadataResolver` 判断：

- 如果 `status == "FINISHED"` 且最后一集播出时间距今 > 30 天，则创建 Subscription 时设置 `fallback_to_resource_search=true`。

---

## 7. 对话与统计功能

### 7.1 用户可能的问题

- "我在下载哪些番？"
- "《葬送的芙莉莲》下完了吗？"
- "《鬼灭之刃》有多少集？"
- "《咒术回战》第二季第 5 集播出了吗？"
- "有哪些番还在等种子？"
- "最近失败的任务有哪些？"

### 7.2 设计思路

对话层增加一个 `StatusQueryService`，不直接调外部 API，只读 SQLite：

```python
class StatusQueryService:
    async def summarize(self, query_type: str, title: str | None = None) -> dict:
        ...
```

查询类型：

| query_type | 返回 |
|------------|------|
| `list_active` | 所有进行中的 Subscription + 已下/未下/失败集数 |
| `subscription_detail` | 指定番剧的所有 Episode 状态、总集数、下一集播出时间 |
| `pending_torrents` | 所有 status 为 `waiting_for_rss` / `no_match` / `human_review` 的 Episode |
| `anime_info` | 番剧元数据：季数、总集数、播出时间、完结状态 |
| `failed_tasks` | 最近失败的 Episode 列表 |

### 7.3 回复生成

两种方式：

1. **模板回复**：简单、可控、省 token。适合 MVP。
2. **LLM 总结**：把 `StatusQueryService` 返回的结构化数据交给 `LLMTool` 生成自然语言。适合后续扩展。

MVP 推荐 **模板 + 轻量 LLM 润色**：

```python
def format_subscription_status(sub: Subscription, eps: list[Episode]) -> str:
    total = sub.total_episodes or len(eps)
    completed = sum(1 for e in eps if e.status == "completed")
    failed = sum(1 for e in eps if e.status == "failed")
    pending = total - completed - failed
    return (
        f"《{sub.title_chinese or sub.title_romaji}》共 {total} 集，"
        f"已下载 {completed} 集，待下载 {pending} 集，失败 {failed} 集。"
    )
```

### 7.4 与 Conversational Agent 的集成

意图解析增加新的 `action`：

```python
{
    "action": "query_status",      # 或 query_info / list_downloading
    "title": "葬送的芙莉莲",        # 可选
    "query_type": "subscription_detail"
}
```

- 如果是 `subscribe` / `download`：走 Orchestrator。
- 如果是 `query_*`：直接调用 `StatusQueryService`，不走下载流程。

---

## 8. 关键边界与降级

| 场景 | 处理 |
|------|------|
| Anime Garden API 无结果 | 标记 Episode 为 `no_match`，记录日志，等待用户手动重试或后续周期再试 |
| Anime Garden API 限流/超时 | 返回 `ToolOutput(success=False)`，Episode 进入 `schedule_wait`，避免高频重试 |
| 返回的磁力链接无法解析 hash | 跳过该条候选，记录警告 |
| 同一候选同时出现在 RSS 和资源 API | 按 `info_hash` 去重，保留来源更可靠或发布时间更近的一条 |
| 老番只有合集（如 01-12 合集） | LLM 在 `TorrentSelector` 中判断为"全集包"，可整包下载后由 `process_metadata` / `organize_files` 拆分识别 |
| 多季识别错误 | 依赖 `MetadataResolver` 的季数信息；`TorrentSelector` prompt 中传入 `season_number` 辅助判断 |
| 用户查询的番剧未订阅 | 返回"你还没有订阅这部番，需要我帮你订阅吗？"，并给出发现结果 |

---

## 9. 实施步骤

### Phase 1：新增 Tool 与候选统一（1~2 天）

- [ ] 创建 `anime_agent/tools/animes_garden_tool.py`
- [ ] 实现磁力 hash 提取、size 转换、失败处理、缓存
- [ ] 统一 `RSSTool` 与 `AnimeGardenTool` 输出格式（加 `source` 字段）
- [ ] 单元测试：`test_animes_garden_tool.py`

### Phase 2：Episode Graph 接入 fallback（2~3 天）

- [ ] 新增 `search_resources` node
- [ ] 修改 `match_torrent`：候选池为空时触发资源搜索
- [ ] 修改 `poll_download`：失败后重新匹配（含资源候选）
- [ ] 把 `Episode.rss_candidates` 语义扩展为通用候选池（或新增 `torrent_candidates`）
- [ ] 单元测试：`test_nodes/test_search_resources.py`、`test_match_torrent_fallback.py`

### Phase 3：老番/全集自动判定（1 天）

- [ ] 在 `MetadataResolver` 或 Subscription 创建逻辑中判断是否为老番/完结番
- [ ] 设置 `fallback_to_resource_search=true`
- [ ] 集成测试：老番完整下载链路

### Phase 4：对话统计功能（2 天）

- [ ] 实现 `StatusQueryService`
- [ ] 扩展意图解析，支持 `query_*` action
- [ ] 模板回复 + 可选 LLM 润色
- [ ] Web 面板增加"我的下载"统计页（可选）
- [ ] 单元测试 + 集成测试

### Phase 5：文档与配置（0.5 天）

- [ ] 更新 `.env.example`：是否需要配置 Anime Garden API（当前为公开 API，可能无需 key，但预留开关）
- [ ] 更新 `ARCHITECTURE_AND_PLAN.md` 相关章节
- [ ] 更新 README：说明老番下载 fallback

---

## 10. 配置项建议

```bash
# .env
ANIME_GARDEN_ENABLED=true
ANIME_GARDEN_BASE_URL=https://api.animes.garden
ANIME_GARDEN_CACHE_TTL_SECONDS=3600
RESOURCE_FALLBACK_AFTER_RSS_EMPTY=true
RESOURCE_FALLBACK_OLD_ANIME_DAYS=90
RESOURCE_SEARCH_MAX_PAGES=2
```

对应 `config.py`：

```python
anime_garden_enabled: bool = True
anime_garden_base_url: str = "https://api.animes.garden"
anime_garden_cache_ttl_seconds: int = 3600
resource_fallback_after_rss_empty: bool = True
resource_fallback_old_anime_days: int = 90
resource_search_max_pages: int = 2
```

---

## 11. 对外描述（可放入 README）

> AnimeAgent 不仅支持通过 RSS 追新番，还内置了 Anime Garden 资源搜索作为兜底。当用户请求下载老番、完结番，或 RSS 源中找不到对应集数时，系统会自动切换到资源搜索引擎，按番剧名检索磁力链接并继续完成下载。同时，用户可以通过自然语言查询当前下载进度、等待种子、未播出集数等信息。

---

## 12. 待确认问题

1. 是否需要为 Anime Garden API 设置 API Key？（当前看起来是公开接口）
2. `Episode.rss_candidates` 是改名为 `torrent_candidates`，还是保留字段名仅扩展语义？
3. 资源搜索是一次性按番剧名搜索后本地按集数过滤，还是按"番剧名 + 集数"搜索每一集？
4. 老番判定阈值 90 天是否合适？是否需要按"完结状态"优先判定？
5. 对话统计功能 MVP 用模板回复即可，还是直接上 LLM 总结？

---

**确认后下一步**：按本文档修改 `ARCHITECTURE_AND_PLAN.md`、创建 `AnimeGardenTool`、扩展 Episode Graph、实现 `StatusQueryService`。
