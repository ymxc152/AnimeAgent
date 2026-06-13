# ADR 001: Episode Graph 状态机设计

## 状态

已接受

## 背景

AnimeAgent 的核心流程是单集下载自动化：从 RSS 候选到种子匹配、下载、整理、媒体库刷新。该流程包含分支（低置信度等待 RSS、人工审批、失败重试）和恢复（按 resume_after 重新调度），适合用 LangGraph StateGraph 建模。

## 决策

使用 LangGraph `StateGraph` 实现 Episode Graph，节点为纯编排函数，业务逻辑下沉到 `services/` 和 `tools/`。

### 状态字段

- `status`：驱动条件边的核心字段
- `rss_candidates`：候选种子池，支持多次 RSS 拉取合并
- `matched_torrent` / `torrent_hash`：匹配结果
- `download_files` / `organized_path`：文件路径
- `resume_after`：Scheduler 恢复时间
- `errors`：累积错误信息
- `requires_human` / `human_input`：人工断点

### 节点与分支

```
pending/fetching → fetch_rss → match_torrent
match_torrent 分支：
  - matched → send_download
  - waiting_for_rss → schedule_resume → END
  - human_review → human_review → END（等待输入）
  - failed → handle_error → END
send_download → poll_download
poll_download 分支：
  - downloading → schedule_resume → END
  - downloaded → organize_files → refresh_emby → completed → END
  - failed → handle_error → END
```

## 后果

- 优点：状态清晰、可恢复、便于 Web 监控和人工介入
- 缺点：需要维护状态字段与条件边的映射，新增状态时要同步更新 `graph.py`
