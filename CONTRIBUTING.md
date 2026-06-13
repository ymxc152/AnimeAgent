# Contributing

感谢你对 AnimeAgent 的关注！

## 开发环境

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## 代码规范

- 使用 `ruff` 进行格式化和 lint
- 使用 `mypy` 进行类型检查
- 使用 `pytest` 运行测试

```bash
ruff check anime_agent tests
mypy anime_agent
pytest
```

## 提交 PR

1. Fork 本仓库
2. 创建功能分支
3. 确保测试通过
4. 提交 Pull Request

## 设计原则

- Tool 只负责外部 IO，不处理业务逻辑
- 业务逻辑下沉到 `services/`
- LangGraph 节点只负责状态编排和 Tool 调用
- 保持测试可 mock，避免真实网络请求
