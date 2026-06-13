# AnimeAgent 前端与功能改进计划

> 状态：待确认  
> 目标：解决当前 UI 体验问题、补齐关键交互能力、为自动订阅与 LLM 辅助决策留出扩展点。

---

## 1. 目标与范围

本轮改进聚焦**前端体验与必要后端支撑**，不涉及对话层大重构。完成后应达到：

- 剧集页可实时看到下载进度。
- 各页面支持自动刷新，同时避免无意义的健康检查轮询。
- 首页加载明显变快。
- 所有状态标签中文展示，交互模块可直接跳转。
- 剧集支持多选筛选与详情弹窗。
- 发现页支持多语言搜索与自动订阅规则。
- RSS 源管理改为弹窗 CRUD，布局更合理。

---

## 2. 任务拆分（建议执行顺序）

### Phase A：性能与基础体验（先做，影响面小）

| # | 任务 | 改动点 | 验收标准 |
|---|------|--------|----------|
| A1 | 修复首页 `/api/subscriptions` N+1 查询 | `anime_agent/memory/store.py`、`anime_agent/web.py` | 100 条订阅时响应 < 300ms（当前可能秒级） |
| A2 | 服务健康检查改为首次加载 + 手动刷新 | `frontend/src/pages/Dashboard.tsx`、`frontend/src/api/client.ts` | 进入首页只调用一次 `/api/tools/health`；提供手动刷新按钮 |
| A3 | 全站自动刷新 | `frontend/src/hooks/usePolling.ts` 或页面级 `setInterval` | Dashboard/Episodes/Subscriptions 每 5s 刷新；Discovery/Logs/RSS 保持手动 |
| A4 | 状态标签中文化 | `frontend/src/i18n/zh-CN.json` / `en.json`、各页面 `Badge` 渲染 | Subscription 状态显示"追番中/已完结/已放弃"；Episode 状态显示"待下载/下载中/已完成/失败/人工审核"等 |

### Phase B：剧集与下载进度

| # | 任务 | 改动点 | 验收标准 |
|---|------|--------|----------|
| B1 | 后端返回更多下载字段 | `anime_agent/web_schemas.py:EpisodeResponse`、`anime_agent/web.py:list_episodes` | 返回 `torrent_status`、`torrent_last_speed`、`torrent_added_at`、`torrent_checked_at`、`torrent_candidates_count` |
| B2 | 后端可选主动同步 qBittorrent 进度 | `anime_agent/services/qb_sync_service.py`（新增）+ Scheduler tick 中调用 | 每轮 tick 同步一次正在下载的进度到 Episode |
| B3 | 前端展示下载进度条/速度 | `frontend/src/pages/Episodes.tsx` | `downloading` 状态显示进度条、速度、已用时间；卡片可刷新 |
| B4 | 剧集状态多选筛选 | 后端 `status` 支持逗号分隔；前端 `Select` 改多选 | 可同时勾选"下载中+失败" |
| B5 | 剧集详情弹窗 | 新增 `GET /api/episodes/{id}`；前端详情抽屉 | 展示种子名称、hash、候选数、失败 hash、下载路径、整理路径、错误日志等 |

### Phase C：订阅与发现增强

| # | 任务 | 改动点 | 验收标准 |
|---|------|--------|----------|
| C1 | 概览模块可点击跳转 | `frontend/src/pages/Dashboard.tsx` | 统计卡片点击后路由到对应页面（订阅/剧集/失败） |
| C2 | 订阅管理新增订阅改为弹窗向导 | `frontend/src/pages/Subscriptions.tsx` | 删除顶部 inline 表单，改为"新增订阅"按钮 → 弹窗搜索/填写；支持 Bangumi/AniList ID 搜索回填 |
| C3 | 发现页多语言搜索 | `frontend/src/pages/Discovery.tsx`、后端 `discovery_season` 增加 `search` 参数 | 输入中文/日文/罗马音/英文均能命中，后端在 `title_chinese/natvie/romaji/english` 中模糊匹配 |
| C4 | 自动订阅规则（基础版） | 新增 `AutoSubscribeRule` 模型/表/Store/API；`DiscoveryService` 应用规则 | 可创建规则：包含/排除 genre、format、关键词、最低评分；命中时自动订阅 |
| C5 | LLM 辅助决策（可选扩展） | `anime_agent/services/auto_subscribe_llm_filter.py` | 规则命中后把番剧元数据发给 LLM，返回"订阅/跳过/人工"建议；默认关闭 |

### Phase D：RSS 源管理重构

| # | 任务 | 改动点 | 验收标准 |
|---|------|--------|----------|
| D1 | 弹窗新增/编辑 RSS 源 | `frontend/src/pages/RSSSources.tsx` + 新增 `RSSSourceModal.tsx` | 列表上方只有"+"按钮；新增/编辑均弹窗；表单字段不变 |
| D2 | 列表项优化 | 同上 | 每个源一行展示名称/URL/关键词/开关；编辑删除图标按钮 |

### Phase E：UI 美化（贯穿以上各阶段）

- 统一 Card 间距、阴影、hover 动效。
- 表格/列表增加空状态、loading 骨架屏。
- 关键操作按钮固定位置，减少滚动。
- 颜色语义：失败用红色、下载中用蓝色、完成用绿色。

---

## 3. 技术方案要点

### 3.1 首页性能优化

当前 `GET /api/subscriptions` 对每个 subscription 调用 `store.episodes.list_by_subscription()`，产生 N+1。

方案：
- 在 `Store.subscriptions` 新增 `list_with_episode_stats()`，使用单个 SQLAlchemy 查询：
  ```sql
  SELECT s.*,
         COUNT(e.id) FILTER (WHERE e.status='completed') AS ep_completed,
         ...
  FROM subscriptions s LEFT JOIN episodes e ON s.id = e.subscription_id
  GROUP BY s.id
  ```
- `/api/subscriptions` 改用该查询。

### 3.2 自动刷新策略

新增 `usePolling(fetchFn, interval, enabled)` hook：
- Dashboard/Subscriptions/Episodes: 5s
- 页面不可见时暂停（`document.visibilityState`）
- 用户手动操作后延迟下一次轮询，避免抖动

### 3.3 健康检查

Dashboard 组件内：
```ts
const [health, setHealth] = useState(null);
const [lastChecked, setLastChecked] = useState(null);
// 只在 mount 时调用一次
useEffect(() => { loadHealth(); }, []);
// 提供"重新检测"按钮
```

### 3.4 剧集详情

新增后端端点：
```python
@app.get("/api/episodes/{episode_id}", response_model=EpisodeDetailResponse)
async def get_episode_detail(episode_id: int, db: ...)
```

`EpisodeDetailResponse` 包含全部 Episode 字段 + subscription_title + candidates 反序列化后的列表。

前端使用抽屉（Drawer）或弹窗（Modal）展示。

### 3.5 发现页多语言搜索

后端 `discovery_season` 增加可选 `search: str` 参数。过滤逻辑：
```python
if search:
    s = search.lower()
    candidates = [
        c for c in candidates
        if s in (c.get("title_chinese") or "").lower()
        or s in (c.get("title_native") or "").lower()
        or s in (c.get("title_romaji") or "").lower()
        or s in (c.get("title_english") or "").lower()
    ]
```

前端搜索框 placeholder 改为"搜索中文/日文/罗马音/英文..."。

### 3.6 自动订阅规则

新增模型 `AutoSubscribeRule`：
- `id`, `name`, `include_genres`, `exclude_genres`, `include_formats`, `exclude_formats`, `include_keywords`, `exclude_keywords`, `min_score`, `enabled`, `use_llm`, `created_at`

API：
- `GET/POST/PATCH/DELETE /api/auto-subscribe-rules`

`DiscoveryService.run()` 在过滤后、创建订阅前检查规则：
```python
for rule in enabled_rules:
    if rule.matches(anime):
        if rule.use_llm:
            decision = await llm_filter.decide(anime)
            if decision != "subscribe": continue
        await self._create_subscription(anime)
```

默认 `filter_auto_subscribe_new_season` 仍控制是否自动订阅，新增规则作为更细粒度补充。

---

## 4. 文件变更清单（预计）

### 后端
- `anime_agent/memory/models.py`：新增 `AutoSubscribeRule`
- `anime_agent/memory/store.py`：新增 rule store；`subscriptions.list_with_episode_stats`
- `anime_agent/web_schemas.py`：`EpisodeResponse` 扩展；新增 `EpisodeDetailResponse`、`AutoSubscribeRule*` schemas
- `anime_agent/web.py`：
  - `/api/subscriptions` 改 stats 查询
  - 新增 `/api/episodes/{id}`
  - `list_episodes` status 支持多选
  - `discovery_season` 支持 search
  - 新增 `/api/auto-subscribe-rules` CRUD
- `anime_agent/services/discovery.py`：集成规则自动订阅
- `anime_agent/services/auto_subscribe_llm_filter.py`（新增，可选）
- `anime_agent/services/qb_sync_service.py`（新增，可选）

### 前端
- `frontend/src/api/client.ts`：新增/修改 API 函数
- `frontend/src/hooks/usePolling.ts`（新增）
- `frontend/src/components/ui/Modal.tsx` / `Drawer.tsx`（新增或扩展）
- `frontend/src/components/ui/MultiSelect.tsx`（新增）
- `frontend/src/i18n/zh-CN.json` / `en.json`：标签中文化
- `frontend/src/pages/Dashboard.tsx`：健康检查缓存、可点击卡片、美化
- `frontend/src/pages/Episodes.tsx`：自动刷新、进度展示、多选筛选、详情弹窗
- `frontend/src/pages/Subscriptions.tsx`：弹窗新增、自动刷新、中文标签
- `frontend/src/pages/Discovery.tsx`：多语言搜索、自动订阅规则入口
- `frontend/src/pages/RSSSources.tsx` + `RSSSourceModal.tsx`：弹窗 CRUD

### 测试
- 后端：补充 subscription stats、episode detail、discovery search、auto-subscribe rules 测试
- 前端：新增 Modal/Drawer、usePolling、Episodes 筛选测试

### 文档
- `docs/ARCHITECTURE_AND_PLAN.md`
- `README.md` 路线图更新
- `CHANGELOG.md`

---

## 5. 验收标准（整体）

- [ ] 首页 `/api/subscriptions` 100 条订阅响应 < 300ms
- [ ] 健康检查仅在首次加载和手动刷新时调用
- [ ] Dashboard/Subscriptions/Episodes 每 5 秒自动刷新
- [ ] 剧集"下载中"状态显示实时速度与进度条
- [ ] 所有状态标签中文展示
- [ ] 剧集状态支持多选筛选
- [ ] 点击剧集卡片弹出详情抽屉，展示种子/hash/路径/日志
- [ ] 发现页搜索可同时命中中文/日文/罗马音/英文
- [ ] 可创建自动订阅规则并生效
- [ ] RSS 源管理使用弹窗新增/编辑，无顶部 inline 表单
- [ ] 全量测试通过：`pytest` 绿，`npm run test`（Vitest）通过

---

## 6. 风险与备注

1. **LLM 辅助决策** 是可选扩展；不实现不影响主流程，建议作为 Phase C 最后做。
2. **qBittorrent 进度同步** 可选；若 Scheduler tick 间隔短（10min），进度刷新可能不够实时，可改为前端直接调 qB API，但会暴露后端地址。建议先由后端同步。
3. **自动订阅规则** 需要新增数据库表，需确认是否需要迁移脚本（当前使用 `create_all`，自动建表）。
4. **前端 UI 美化** 较主观，建议先确定 1-2 个页面风格后复用组件。
5. 本次改动较大，建议分 3-4 个 commit：
   - commit 1：性能 + 健康检查 + 自动刷新 + 中文化
   - commit 2：剧集进度 + 多选 + 详情
   - commit 3：订阅弹窗 + 发现多语言搜索 + 自动订阅规则
   - commit 4：RSS 弹窗 + UI 美化 + 文档

---

## 7. 需要你确认的问题

1. 自动刷新间隔：Dashboard/Subscriptions/Episodes 每 **5 秒** 是否合适？
2. 剧集详情弹窗需要展示哪些字段？（计划包含：种子名、info_hash、候选数、下载路径、整理路径、错误日志、各状态时间）
3. 自动订阅规则第一批支持哪些条件？（genre/format/keywords/min_score）是否还需要工作室/来源平台？
4. LLM 辅助决策是否在本次实现，还是后续再做？
5. 是否需要前端 Vitest 测试覆盖新增组件？（当前测试很少）

请确认后我将按 Phase 顺序执行。
