# Changelog

## 0.1.0 (MVP)

### Added
- Tool 层：RSS、qBittorrent、Bangumi、AniList、TMDB、Emby、通知、文件系统工具
- Service 层：元数据解析、内容过滤、种子选择、健康检查、完结检测、调度计划
- Episode Graph：使用 LangGraph 串联 RSS 拉取、种子匹配、下载、整理、Emby 刷新
- Scheduler：APScheduler 定时触发 Episode Graph，每周新番发现
- Web 面板：FastAPI + React/Vite/Tailwind CSS，支持订阅管理、发现页、集数状态、工具健康
- 人工断点：低置信度匹配暂停，Web 端点审批后恢复
- 工程：Ruff、MyPy、pytest、GitHub Actions CI、部署文档

### Fixed / Improved
- Scheduler 增加播出时间门控，优先使用 `episode.aired_at`，fallback 到订阅的 expected_airing_weekday/time
- DiscoveryService 移除硬编码 12 集兜底，支持 `discovery_default_total_episodes` 配置与 Movie/OVA/ONA 格式感知默认
- `torrent_hash` / `torrent_info_hash` 字段统一，避免持久化不一致
- `OrganizeFilesNode` 使用 Subscription 真实 `season`
- `ScheduleResumeNode` 区分 RSS 等待间隔与下载轮询间隔
- `AnimeGardenTool` 补齐配置项（base URL、timeout、cache TTL），实现 1 小时内存缓存；`search_resources` 支持 fallback 开关与多页搜索
- Episode Graph 新增 `process_metadata`（内容分类）与 `notify_user`（通知推送）节点

### Known Limitations
- 对话层（自然语言聊天订阅）尚未实现
- 完结检测服务已实现但尚未接入 Scheduler
