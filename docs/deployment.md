# 部署指南

## 环境要求

- Python 3.11+
- qBittorrent Web UI 已启用
- Emby Server（可选，用于媒体库刷新）
- Bangumi / AniList / TMDB API 密钥（按需）

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd ani-agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装包
pip install -e ".[dev]"
```

## 配置

复制环境变量模板并填写：

```bash
cp .env.example .env
```

必填项：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | LLM API 密钥 |
| `OPENAI_BASE_URL` | LLM API 基础 URL |
| `OPENAI_MODEL` | 模型名称 |
| `QB_HOST` | qBittorrent Web UI 地址 |
| `QB_USERNAME` | qBittorrent 用户名（无认证可留空） |
| `QB_PASSWORD` | qBittorrent 密码（无认证可留空） |
| `QB_SAVE_PATH` | qBittorrent 默认下载路径 |
| `MEDIA_LIBRARY_PATH` | 整理后的媒体库根目录 |
| `EMBY_HOST` | Emby 地址（可选） |
| `EMBY_API_KEY` | Emby API 密钥（可选） |

## 启动

```bash
# 同时启动 Web 面板和后台调度器
python -m anime_agent.main

# 或仅启动 Web 面板
uvicorn anime_agent.web:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 使用 Web 面板。

## 首次运行

1. 打开 Web 面板的 **Discovery** 页，浏览当季新番并订阅。
2. 或在 **Subscriptions** 页手动新增订阅。
3. Scheduler 会自动创建检查计划，按播出周几触发 Episode Graph 下载。
4. 下载完成后文件会自动硬链接到 `MEDIA_LIBRARY_PATH` 并按模板命名。

## 人工断点

当种子匹配置信度低时，Episode 状态会变为 `human_review`。此时：

1. 在 **Episodes** 页找到该集，查看原始候选。
2. 调用 `POST /api/episodes/{id}/human_input`，`action=approve` 通过或提供 `torrent_link` 指定种子。
3. Scheduler 下次 tick 会重新驱动该集进入 `send_download`。

## 日志

日志默认写入 `logs/anime_agent.log`，可通过 Web 面板 **Tools** 页或 `GET /api/logs` 查看。

## 更新

```bash
git pull
pip install -e ".[dev]"
```
