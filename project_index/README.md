# AstrBot Project Index

本目录是在当前工作树上重新建立的项目索引。恢复原因是当前仓库内缺少 `project_index/`，而 `AGENTS.md` 明确要求先读这一组索引文件再讨论项目现状。

## 使用方式

- 先读 [01_product_scope.md](./01_product_scope.md)，确认产品边界、用户面和已知冲突。
- 再读 [02_runtime_entry_and_lifecycle.md](./02_runtime_entry_and_lifecycle.md)，确认入口、初始化顺序、核心任务和停机路径。
- 涉及 WebUI、控制面板和对外 API 时读 [03_dashboard_and_webui.md](./03_dashboard_and_webui.md)。
- 涉及平台接入、Provider、插件、Skills、MCP、知识库时读 [04_integrations_and_extensions.md](./04_integrations_and_extensions.md)。
- 涉及本地开发、测试、构建、打包和 CI 时读 [05_development_and_build.md](./05_development_and_build.md)。

## 证据约定

- `[Fact]` 直接来自当前源码、配置、测试或工作流文件。
- `[Inference + Evidence]` 是根据多个文件拼接出的行为结论。
- `[Conflict]` 表示源码、文档、测试或元数据之间存在不一致，需要在继续判断前先点明来源。
- `[Don't know]` 表示当前工作树里没有足够证据，不能擅自补全。

## 当前索引锚点

- `[Fact]` 当前仓库是 AstrBot，版本号在 `pyproject.toml` 和默认配置里都写成 `4.22.0`。Evidence: `pyproject.toml:1-7`, `astrbot/core/config/default.py:8-10`
- `[Fact]` 仓库同时包含 Python 主体、内置 Dashboard 前端、内置控制面板后端、文档站、测试集与发布工作流。Evidence: `pyproject.toml:1-127`, `dashboard/package.json:1-77`, `docs/package.json:1-13`, `.github/workflows/coverage_test.yml:1-45`, `.github/workflows/dashboard_ci.yml:1-55`, `.github/workflows/build-docs.yml:1-43`
- `[Don't know]` 被删除的旧 `project_index/` 具体措辞和细节在当前工作树中不可恢复；本次重建仅保证文件名结构与 `AGENTS.md` 要求一致，并以当前源码为准。

## 本次重建覆盖面

- `[Fact]` 本索引覆盖 `AGENTS.md` 里声明的 6 个文件名和 5 个主题分册。Evidence: `AGENTS.md:1-33`
- `[Fact]` 索引内容优先引用当前源码、配置、测试和工作流；当 README 与源码冲突时，冲突会被单独标明，而不是直接替某一方“拍板”。 Evidence: `README.md:39-197`, `main.py:43-141`, `pyproject.toml:1-127`, `astrbot/core/platform/sources/kook/kook_adapter.py:23-27`
