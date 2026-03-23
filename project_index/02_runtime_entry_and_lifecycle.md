# 02 Runtime Entry And Lifecycle

## 入口总览

- `[Fact]` 直接脚本入口是 `main.py`。它先执行 `runtime_bootstrap.initialize_runtime_bootstrap()`，再导入 `astrbot.core` 和各类运行时对象。Evidence: `main.py:8-27`
- `[Fact]` 包安装后的 CLI 入口是 `astrbot = "astrbot.cli.__main__:cli"`。Evidence: `pyproject.toml:78-80`
- `[Fact]` CLI 的 `run` 子命令最终也会走 `InitialLoader.start()`，并在启动前做 Dashboard 检查、单实例锁和环境变量设置。Evidence: `astrbot/cli/commands/cmd_run.py:13-63`

## 启动顺序

1. `[Fact]` `runtime_bootstrap` 会为 `aiohttp` 的 verified SSL context 打补丁，优先加载 system + certifi trust chain。Evidence: `runtime_bootstrap.py:12-50`
2. `[Fact]` `main.py` 的 `check_env()` 会补 `sys.path`，创建配置、插件、临时目录、知识库目录和额外 site-packages 目录，并修正若干 MIME type。Evidence: `main.py:43-66`
3. `[Fact]` `main.py` 在核心生命周期启动前先解析 WebUI 静态资源目录；显式 `--webui-dir` 优先，否则读 `data/dist`，不存在时尝试下载匹配当前版本的 Dashboard。Evidence: `main.py:68-101`
4. `[Fact]` 启动阶段会创建 `LogBroker`，并通过 `LogManager.set_queue_handler()` 将日志接到后续控制面板。Evidence: `main.py:136-141`
5. `[Fact]` `InitialLoader.start()` 先构造 `AstrBotCoreLifecycle`，执行 `initialize()`，再并发运行核心任务和 Dashboard 服务。Evidence: `astrbot/core/initial_loader.py:26-57`

## `AstrBotCoreLifecycle.initialize()` 做了什么

- `[Fact]` 生命周期初始化会先打印版本号并重配 logger；测试环境下会强制 `DEBUG`。Evidence: `astrbot/core/core_lifecycle.py:100-115`
- `[Fact]` 初始化顺序明确包含数据库、HTML renderer、UMOP 配置路由器、AstrBot 配置管理器、迁移逻辑、事件队列、人格管理器、ProviderManager、PlatformManager、ConversationManager、PlatformMessageHistoryManager、KnowledgeBaseManager、CronJobManager、SubAgentOrchestrator、插件上下文、PluginManager、Provider 初始化、知识库初始化、PipelineScheduler、更新器、EventBus 和平台适配器实例化。Evidence: `astrbot/core/core_lifecycle.py:116-233`
- `[Fact]` 生命周期会在启动时创建 `dashboard_shutdown_event`，供 WebUI 优雅退出使用。Evidence: `astrbot/core/core_lifecycle.py:230-233`
- `[Fact]` 生命周期还会异步刷新 LLM 元数据。Evidence: `astrbot/core/core_lifecycle.py:233-233`

## 运行中任务

- `[Fact]` `_load()` 会启动事件总线、Cron 管理器、临时目录清理器，以及插件在上下文中注册的额外协程任务。Evidence: `astrbot/core/core_lifecycle.py:235-269`
- `[Fact]` `start()` 在所有后台任务跑起来后，还会触发 `OnAstrBotLoadedEvent` 类型的插件钩子。Evidence: `astrbot/core/core_lifecycle.py:291-313`
- `[Inference + Evidence]` 运行期的主循环不是一个单独的“消息 while true”，而是 `EventBus.dispatch()`、平台适配器的 `run()`、Cron、临时目录清理器和插件任务的组合。Evidence: `astrbot/core/core_lifecycle.py:235-313`, `astrbot/core/platform/manager.py:49-58`, `astrbot/core/platform/manager.py:87-100`

## 停止与重启

- `[Fact]` `stop()` 会按顺序停止临时目录清理器、取消当前任务、关闭 Cron、终止所有插件、终止 Provider、Platform、KnowledgeBase，并触发 Dashboard shutdown event。Evidence: `astrbot/core/core_lifecycle.py:315-349`
- `[Fact]` `restart()` 会先终止 Provider、Platform、KnowledgeBase，再触发 Dashboard shutdown，并用后台线程调用更新器重启逻辑。Evidence: `astrbot/core/core_lifecycle.py:350-360`
- `[Fact]` `InitialLoader.start()` 对 `asyncio.CancelledError` 做了专门处理，收到取消时会调用 `core_lifecycle.stop()`。Evidence: `astrbot/core/initial_loader.py:53-57`

## 配置路由与会话隔离

- `[Fact]` `UmopConfigRouter` 维护 `UMO/UMOP -> conf_id` 映射，支持通配匹配，并将路由表放进 SharedPreferences。Evidence: `astrbot/core/umop_config_router.py:6-119`
- `[Fact]` `AstrBotConfigManager` 在默认配置之外还能加载额外配置文件，并按会话映射返回某个会话实际使用的配置。Evidence: `astrbot/core/astrbot_config_mgr.py:31-175`
- `[Inference + Evidence]` AstrBot 不是单配置运行模型；它支持默认配置 + 额外配置文件 + 会话路由，这会影响 Provider、平台行为和 Open API 的会话配置。Evidence: `astrbot/core/astrbot_config_mgr.py:124-175`, `astrbot/dashboard/routes/open_api.py:61-108`, `astrbot/dashboard/routes/open_api.py:160-188`

## 数据初始化与数据库

- `[Fact]` `astrbot.core` 模块导入时就会创建 `AstrBotConfig`、`SQLiteDatabase(DB_PATH)`、`SharedPreferences`、`FileTokenService` 和 `PipInstaller`。Evidence: `astrbot/core/__init__.py:28-46`
- `[Fact]` SQLite 初始化会启用 WAL、NORMAL synchronous、cache/mmap 优化，并对历史数据库做若干前向兼容列补齐。Evidence: `astrbot/core/db/sqlite.py:41-62`, `astrbot/core/db/sqlite.py:64-104`

## 已知冲突

- `[Conflict]` 运行时代码仍允许 Python 3.10+，但包元数据已经要求 `>=3.12`；如果按 `uv sync` 或打包安装走，解释器约束应以 `pyproject.toml` 为准。Evidence: `main.py:43-46`, `pyproject.toml:1-7`

## 当前不能下结论的部分

- `[Don't know]` `load_pipeline_scheduler()` 具体如何将平台消息映射到不同 pipeline，在当前索引里没有继续下钻到所有 pipeline stage 实现；这里只能确认初始化点与调度存在。 Evidence: `astrbot/core/core_lifecycle.py:208-220`
