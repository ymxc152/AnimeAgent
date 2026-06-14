# AnimeAgent 完整实施计划（TDD）

> 最新进度（2026-06-14）：阶段四（老番判定）、阶段五（对话统计）已完成；阶段一 1.3（日志增强）与 1.4（配置验证）测试已补齐并通过。阶段二、三已在前期落地。

## 执行顺序

### 阶段一：MVP 问题修复（基础稳固）

#### 1.1 状态键冲突修复
**目标**：确保节点状态不会互相覆盖

**测试先行**：
- 测试每个节点返回的状态字段正确
- 测试 Graph 路由函数正确读取状态
- 测试多节点连续执行时状态不丢失

**实现**：
- 在 `EpisodeAgentState` 中定义清晰的状态字段职责
- 每个节点只更新自己负责的状态字段
- 路由函数使用正确的状态字段判断

**文件**：
- `tests/test_agents/test_episode/test_state.py`（新建）
- `anime_agent/agents/episode/state.py`（修改）
- `anime_agent/agents/episode/nodes/*.py`（修改）
- `anime_agent/agents/episode/graph.py`（修改）

#### 1.2 错误处理统一
**目标**：所有节点统一错误处理模式

**测试先行**：
- 测试每个节点在错误时返回 `errors` 列表
- 测试错误信息格式一致

**实现**：
- 所有节点统一返回 `errors: list[str]`
- 使用 `loguru` 记录错误

**文件**：
- `tests/test_agents/test_episode/test_error_handling.py`（新建）
- `anime_agent/agents/episode/nodes/*.py`（修改）

#### 1.3 日志记录增强
**目标**：关键操作有日志记录

**测试先行**：
- 测试关键操作触发日志（mock logger）

**实现**：
- 每个节点入口记录 `logger.info`
- 每个节点出口记录状态变化
- 错误时记录 `logger.error`

**文件**：
- `tests/test_agents/test_episode/test_logging.py`（新建）
- `anime_agent/agents/episode/nodes/*.py`（修改）

#### 1.4 配置验证增强
**目标**：启动时验证配置有效性

**测试先行**：
- 测试无效 URL 抛出 ValidationError
- 测试无效数值范围抛出 ValidationError

**实现**：
- 使用 Pydantic `field_validator` 验证配置
- URL 格式验证
- 数值范围验证

**文件**：
- `tests/test_config.py`（新建）
- `anime_agent/config.py`（修改）

#### 1.5 数据库会话管理
**目标**：事务正确回滚

**测试先行**：
- 测试异常时事务回滚
- 测试正常时事务提交

**实现**：
- 使用 `try/except` 包裹数据库操作
- 异常时调用 `rollback()`

**文件**：
- `tests/test_web/test_session_management.py`（新建）
- `anime_agent/web.py`（修改）

---

### 阶段二：AnimeGardenTool 实现（Phase 1）

#### 2.1 创建 AnimeGardenTool
**目标**：实现资源搜索工具

**测试先行**：
- 测试 API 调用成功
- 测试磁力链接解析
- 测试 size 单位转换
- 测试缓存机制
- 测试错误处理

**实现**：
- 创建 `AnimeGardenTool` 类
- 实现 `invoke` 方法
- 实现缓存机制（1 小时 TTL）
- 实现磁力 hash 提取
- 实现 size KB 转 bytes

**文件**：
- `tests/test_tools/test_animes_garden_tool.py`（新建）
- `anime_agent/tools/animes_garden_tool.py`（新建）

#### 2.2 统一候选格式
**目标**：RSS 和 AnimeGarden 输出统一格式

**测试先行**：
- 测试 RSSTool 输出包含 `source: "rss"`
- 测试 AnimeGardenTool 输出包含 `source: "animes_garden"`
- 测试两种输出格式一致

**实现**：
- 修改 `RSSTool._normalize_entry` 添加 `source: "rss"`
- AnimeGardenTool 直接生成统一格式
- 统一候选格式包含：`info_hash`, `title`, `link`, `source`, `size`, `published`, `fansub`, `publisher`, `detail_url`, `subject_id`

**文件**：
- `tests/test_tools/test_unified_candidate.py`（新建）
- `anime_agent/tools/rss_tool.py`（修改）
- `anime_agent/tools/animes_garden_tool.py`（修改）

#### 2.3 注册工具
**目标**：AnimeGardenTool 注册到工具系统

**测试先行**：
- 测试 `get_all_tools()` 包含 AnimeGardenTool
- 测试工具健康检查

**实现**：
- 更新 `tools/__init__.py`
- 实现 `healthcheck` 方法

**文件**：
- `tests/test_tools/test_tool_registry.py`（修改）
- `anime_agent/tools/__init__.py`（修改）
- `anime_agent/tools/animes_garden_tool.py`（修改）

---

### 阶段三：Episode Graph Fallback（Phase 2）

#### 3.1 数据模型调整
**目标**：`rss_candidates` 改名为 `torrent_candidates`

**测试先行**：
- 测试 Episode 模型有 `torrent_candidates` 字段
- 测试旧数据迁移（如果需要）

**实现**：
- 修改 Episode 模型，`rss_candidates` → `torrent_candidates`
- 更新所有引用该字段的代码

**文件**：
- `tests/test_memory/test_models.py`（新建）
- `anime_agent/memory/models.py`（修改）
- `anime_agent/agents/episode/nodes/*.py`（修改）
- `anime_agent/web.py`（修改）

#### 3.2 新增 search_resources 节点
**目标**：实现资源搜索节点

**测试先行**：
- 测试节点调用 AnimeGardenTool
- 测试候选合并逻辑
- 测试状态更新

**实现**：
- 创建 `SearchResourcesNode`
- 调用 AnimeGardenTool 搜索
- 合并到 `torrent_candidates`
- 更新状态

**文件**：
- `tests/test_agents/test_episode/test_search_resources.py`（新建）
- `anime_agent/agents/episode/nodes/search_resources.py`（新建）

#### 3.3 修改 match_torrent 节点
**目标**：候选池为空时触发资源搜索

**测试先行**：
- 测试候选池为空时返回 `search_resources` 状态
- 测试有候选时正常匹配

**实现**：
- 检查 `torrent_candidates` 是否为空
- 为空且未搜索过资源 API 时返回 `search_resources`
- 否则正常匹配

**文件**：
- `tests/test_agents/test_episode/test_match_torrent_fallback.py`（新建）
- `anime_agent/agents/episode/nodes/match_torrent.py`（修改）

#### 3.4 修改 poll_download 节点
**目标**：下载失败后重新匹配

**测试先行**：
- 测试下载失败时返回 `match_torrent` 状态
- 测试失败 hash 记录

**实现**：
- 下载失败时记录 hash 到 `torrent_failed_hashes`
- 返回状态触发重新匹配

**文件**：
- `tests/test_agents/test_episode/test_poll_download_fallback.py`（新建）
- `anime_agent/agents/episode/nodes/poll_download.py`（修改）

#### 3.5 更新 Episode Graph
**目标**：添加 search_resources 节点和路由

**测试先行**：
- 测试 Graph 包含 search_resources 节点
- 测试路由逻辑正确

**实现**：
- 添加 `search_resources` 节点
- 更新路由函数
- 更新 `_status_router`

**文件**：
- `tests/test_agents/test_episode/test_graph_fallback.py`（新建）
- `anime_agent/agents/episode/graph.py`（修改）

---

### 阶段四：老番判定（Phase 3）

#### 4.1 Subscription 字段扩展
**目标**：添加 `fallback_to_resource_search` 字段

**测试先行**：
- 测试 Subscription 模型有新字段
- 测试默认值为 True

**实现**：
- 添加 `fallback_to_resource_search` 字段
- 更新创建逻辑

**文件**：
- `tests/test_memory/test_subscription.py`（新建）
- `anime_agent/memory/models.py`（修改）

#### 4.2 MetadataResolver 增强
**目标**：判断是否为老番/完结番

**测试先行**：
- 测试完结番自动设置 `fallback_to_resource_search=true`
- 测试新番保持默认值

**实现**：
- 在 MetadataResolver 中判断番剧状态
- 自动设置 fallback 标志

**文件**：
- `tests/test_services/test_metadata_resolver_old_anime.py`（新建）
- `anime_agent/services/metadata_resolver.py`（修改）

---

### 阶段五：对话统计功能（Phase 4）

#### 5.1 StatusQueryService
**目标**：实现状态查询服务

**测试先行**：
- 测试 `list_active` 查询
- 测试 `subscription_detail` 查询
- 测试 `pending_torrents` 查询
- 测试 `anime_info` 查询
- 测试 `failed_tasks` 查询

**实现**：
- 创建 `StatusQueryService` 类
- 实现各种查询方法
- 返回结构化数据

**文件**：
- `tests/test_services/test_status_query.py`（新建）
- `anime_agent/services/status_query.py`（新建）

#### 5.2 意图解析扩展
**目标**：支持 `query_*` action

**测试先行**：
- 测试解析 "我在下载哪些番" → `list_active`
- 测试解析 "《XXX》下完了吗" → `subscription_detail`
- 测试解析 "有哪些番还在等种子" → `pending_torrents`

**实现**：
- 扩展 Conversational Agent 的意图解析
- 添加 `query_*` action 类型

**文件**：
- `tests/test_agents/test_conversational/test_intent.py`（新建）
- `anime_agent/agents/conversational/`（修改）

#### 5.3 LLM 回复生成
**目标**：使用 LLM 生成自然语言回复

**测试先行**：
- 测试 LLM 收到正确的上下文
- 测试回复格式正确

**实现**：
- 将查询结果传给 LLM
- 生成自然语言回复

**文件**：
- `tests/test_agents/test_conversational/test_reply.py`（新建）
- `anime_agent/agents/conversational/`（修改）

---

### 阶段六：配置与文档（Phase 5）

#### 6.1 配置更新
**目标**：添加 AnimeGarden 相关配置

**测试先行**：
- 测试新配置项有默认值
- 测试配置验证

**实现**：
- 添加 `anime_garden_enabled`
- 添加 `anime_garden_base_url`
- 添加 `anime_garden_cache_ttl_seconds`
- 添加 `resource_fallback_after_rss_empty`
- 添加 `resource_fallback_old_anime_days`
- 添加 `resource_search_max_pages`

**文件**：
- `tests/test_config_anime_garden.py`（新建）
- `anime_agent/config.py`（修改）
- `.env.example`（修改）

#### 6.2 文档更新
**目标**：更新架构文档和 README

**实现**：
- 更新 `docs/ARCHITECTURE_AND_PLAN.md`
- 更新 `README.md`

**文件**：
- `docs/ARCHITECTURE_AND_PLAN.md`（修改）
- `README.md`（修改）

---

## 执行顺序总结

```
阶段一（MVP 修复）→ 阶段二（AnimeGardenTool）→ 阶段三（Graph Fallback）
→ 阶段四（老番判定）→ 阶段五（对话统计）→ 阶段六（配置文档）
```

每个阶段内部按子任务顺序执行，每个子任务遵循 TDD 流程：
1. 写测试
2. 运行测试（失败）
3. 实现代码
4. 运行测试（通过）
5. 重构

## 预计工作量

- 阶段一：约 2-3 小时
- 阶段二：约 2-3 小时
- 阶段三：约 3-4 小时
- 阶段四：约 1-2 小时
- 阶段五：约 3-4 小时
- 阶段六：约 1 小时

**总计**：约 12-17 小时

---

## 已确认决策

1. **AnimeGarden API**：公开接口，不需要 API Key
2. **字段命名**：`rss_candidates` 改名为 `torrent_candidates`，语义扩展为通用候选池
3. **资源搜索策略**：按番剧名搜索，本地按集数过滤（减少 API 调用）
4. **老番判定阈值**：90 天
5. **对话统计功能**：使用 LLM 总结（更自然）
