# 05 Development And Build

## Python 开发面

- `[Fact]` Python 包元数据定义在 `pyproject.toml`；项目名是 `AstrBot`，当前版本是 `4.22.0`，包脚本入口是 `astrbot`。Evidence: `pyproject.toml:1-80`
- `[Fact]` 当前包元数据要求 `requires-python = ">=3.12"`。Evidence: `pyproject.toml:1-7`
- `[Fact]` 开发依赖至少包含 `pytest`、`pytest-asyncio`、`pytest-cov`、`ruff`、`commitizen`。Evidence: `pyproject.toml:69-76`
- `[Fact]` `ruff` 规则、`pyright`、Hatch 构建和 wheel artifact 也都在 `pyproject.toml` 中声明。Evidence: `pyproject.toml:81-127`

## CLI 与本地初始化

- `[Fact]` `astrbot init` 会创建 `.astrbot` 标记文件、`data/`、`data/config/`、`data/plugins/`、`data/temp/`，并下载或检查 Dashboard 资源。Evidence: `astrbot/cli/commands/cmd_init.py:10-55`
- `[Fact]` `astrbot run` 会设置 `ASTRBOT_CLI=1`、补 `ASTRBOT_ROOT`、可选覆盖 Dashboard 端口、可选开启插件热重载，并用 `astrbot.lock` 做单实例锁。Evidence: `astrbot/cli/commands/cmd_run.py:29-63`
- `[Fact]` CLI 还内建 `plug` 与 `conf` 子命令，可用于插件脚手架/安装/更新/删除以及少量核心配置键的修改。Evidence: `astrbot/cli/__main__.py:52-56`, `astrbot/cli/commands/cmd_plug.py:17-253`, `astrbot/cli/commands/cmd_conf.py:67-212`

## Dashboard 与 Docs 的前端工程

- `[Fact]` Dashboard 是单独的 Node 工程，使用 `pnpm`/`vite`/`vue-tsc`。Evidence: `dashboard/package.json:6-77`
- `[Fact]` 文档站也是单独的 Node 工程，使用 `vitepress`。Evidence: `docs/package.json:1-13`
- `[Fact]` 仓库根 `AGENTS.md` 给出的本地开发命令是 `uv sync`、`uv run main.py`，Dashboard 侧则是 `cd dashboard && pnpm install && pnpm dev`。Evidence: `AGENTS.md:1-20`

## 构建与打包

- `[Fact]` Python wheel 可在开启 `ASTRBOT_BUILD_DASHBOARD=1` 时把 Dashboard 打进包内；否则 `uv sync` / editable install 不会触发 npm 构建。Evidence: `scripts/hatch_build.py:1-75`
- `[Fact]` `astrbot/dashboard/dist/**` 被声明为 wheel artifact。Evidence: `pyproject.toml:117-123`
- `[Fact]` Dashboard CI 会构建 `dashboard/dist` 并生成 `dist.zip`；Docs workflow 会构建 `docs/.vitepress/dist` 并发布到远端服务器。Evidence: `.github/workflows/dashboard_ci.yml:21-55`, `.github/workflows/build-docs.yml:19-43`

## 测试与 CI

- `[Fact]` Python 侧存在完整测试目录，覆盖主入口、Dashboard、插件、技能、Provider、知识库、运行时环境、安全修复、单元测试等。Evidence: `tests/test_main.py:1-150`, `tests/test_dashboard.py`, `tests/test_plugin_manager.py`, `tests/test_skill_manager_sandbox_cache.py`, `tests/unit/test_core_lifecycle.py`
- `[Fact]` Dashboard 也有独立的前端测试文件。Evidence: `dashboard/tests/hashRouteTabs.test.mjs`, `dashboard/tests/routerReadiness.test.mjs`
- `[Fact]` Docs 目录下也有脚本测试。Evidence: `docs/tests/test_sync_docs_to_wiki.py`
- `[Fact]` CI 至少包含 Python coverage 测试、Smoke Test、Dashboard CI、Docs build、格式检查、Docker 镜像和 release 工作流。Evidence: `.github/workflows/coverage_test.yml:14-45`, `.github/workflows/smoke_test.yml:14-57`, `.github/workflows/dashboard_ci.yml:9-55`, `.github/workflows/build-docs.yml:9-43`
- `[Fact]` Smoke Test 的验收方式是 `uv run main.py` 后轮询 `http://localhost:6185` 是否成功响应。Evidence: `.github/workflows/smoke_test.yml:31-57`

## 仓库辅助脚本与运维文件

- `[Fact]` 根目录提供 `compose.yml`、`compose-with-shipyard.yml`、`Dockerfile`、`k8s/`、`scripts/astrbot.service` 等部署材料。Evidence: `Dockerfile`, `compose.yml`, `compose-with-shipyard.yml`, `k8s/astrbot`, `scripts/astrbot.service`
- `[Fact]` `Makefile` 主要提供 worktree 和 PR 测试环境快捷命令，而不是通用 build 入口。Evidence: `Makefile:1-41`

## 已知冲突

- `[Conflict]` README badge 和 `main.py` 的运行时检查仍然指向 Python 3.10+，但 `pyproject.toml` 已经要求 3.12+。如果要判断“官方支持版本”，必须先决定以包元数据还是脚本守卫为准。Evidence: `README.md:20-23`, `main.py:43-46`, `pyproject.toml:1-7`

## 当前不能下结论的部分

- `[Don't know]` 当前本地环境是否已经完整满足 `uv sync`、`pnpm install`、Dashboard build 和全部测试运行条件，这需要实际执行命令验证，而不是只看文件。 Evidence: `AGENTS.md:1-29`, `.github/workflows/coverage_test.yml:27-40`, `.github/workflows/dashboard_ci.yml:21-27`
