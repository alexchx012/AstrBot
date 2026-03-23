# 01 Product Scope

## 项目定位

- `[Fact]` 根 README 将 AstrBot 定义为“open-source all-in-one Agent chatbot platform”，目标是把对话式 AI 能力接到主流即时通信平台里。Evidence: `README.md:39-40`
- `[Fact]` README 的功能列表直接写到了 LLM 对话、多模态、Agent、MCP、Skills、知识库、人格设定、上下文压缩、插件市场、Agent Sandbox、WebUI、Web ChatUI 和 i18n。Evidence: `README.md:43-53`
- `[Inference + Evidence]` 从默认配置项、控制面板路由和数据库实体看，AstrBot 的“产品面”不只是一个聊天机器人运行时，还包含配置管理、平台接入、会话/项目管理、文件上传、知识库、Cron、备份、Open API 和运维观察面。Evidence: `astrbot/core/config/default.py:21-248`, `astrbot/dashboard/server.py:100-141`, `astrbot/core/db/__init__.py:10-27`

## 用户可见入口

- `[Fact]` 项目至少暴露三类用户入口：`main.py` 直接运行入口、`astrbot` CLI 入口，以及默认监听 `6185` 的 Dashboard/API 服务器。Evidence: `main.py:104-141`, `pyproject.toml:78-80`, `astrbot/cli/__main__.py:20-59`, `astrbot/dashboard/server.py:303-421`
- `[Fact]` Dashboard 前端主路由覆盖欢迎页、扩展、平台、Provider、配置、会话、人格、SubAgent、Cron、控制台、Trace、知识库、聊天、设置和 About。Evidence: `dashboard/src/router/MainRoutes.ts:3-170`
- `[Fact]` Open API 路由至少包含聊天、聊天会话列表、配置列表、文件上传、IM 发信和机器人列表。Evidence: `astrbot/dashboard/routes/open_api.py:39-49`

## 内建能力范围

- `[Fact]` 默认配置中显式包含平台设置、Provider 设置、STT/TTS、长时记忆、内容安全、T2I、Dashboard、SubAgent orchestrator、知识库、插件集、Cron 相关能力开关。Evidence: `astrbot/core/config/default.py:21-248`
- `[Fact]` 内置 Star（即插件）目录中至少有 `astrbot`、`builtin_commands`、`session_controller`、`web_searcher` 四组内置能力。Evidence: `astrbot/builtin_stars/astrbot/metadata.yaml`, `astrbot/builtin_stars/builtin_commands/metadata.yaml`, `astrbot/builtin_stars/session_controller/metadata.yaml`, `astrbot/builtin_stars/web_searcher/metadata.yaml`
- `[Fact]` WebChat 是内建平台，而不是单独的外部插件；`PlatformManager.initialize()` 会无条件附加 `WebChatAdapter`。Evidence: `astrbot/core/platform/manager.py:97-100`

## 内建平台与模型接入

- `[Fact]` README 列出了官方支持的 QQ/OneBot/Telegram/Wecom/公众号/Lark/DingTalk/Slack/Discord/LINE/Satori/Misskey 等平台。Evidence: `README.md:139-160`
- `[Fact]` 当前源码里的内建平台适配器目录包含 `aiocqhttp`、`dingtalk`、`discord`、`kook`、`lark`、`line`、`misskey`、`qqofficial`、`qqofficial_webhook`、`satori`、`slack`、`telegram`、`webchat`、`wecom`、`wecom_ai_bot`、`weixin_oc`、`weixin_official_account`。Evidence: `astrbot/core/platform/manager.py`, `astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py`, `astrbot/core/platform/sources/kook/kook_adapter.py:23-27`, `astrbot/core/platform/sources/weixin_oc/weixin_oc_adapter.py`
- `[Fact]` 当前源码里的 Provider 适配器覆盖聊天模型、STT、TTS、Embedding、Rerank 五类，并有对应 source 文件。Evidence: `astrbot/core/provider/manager.py:273-344`, `astrbot/core/provider/manager.py:346-458`, `astrbot/core/provider/sources/openai_source.py`, `astrbot/core/provider/sources/whisper_api_source.py`, `astrbot/core/provider/sources/openai_tts_api_source.py`, `astrbot/core/provider/sources/openai_embedding_source.py`, `astrbot/core/provider/sources/vllm_rerank_source.py`

## 数据与持久化边界

- `[Fact]` 项目根目录默认是当前工作目录，或由 `ASTRBOT_ROOT` 指定；`data/` 是所有运行时数据的根。Evidence: `astrbot/core/utils/astrbot_path.py:28-39`
- `[Fact]` 运行时数据目录下预留了 `config`、`plugins`、`plugin_data`、`t2i_templates`、`webchat`、`temp`、`skills`、`site-packages`、`knowledge_base`、`backups` 等路径。Evidence: `astrbot/core/utils/astrbot_path.py:42-89`
- `[Fact]` 主数据库默认是 `data/data_v4.db`，知识库元数据库是 `data/knowledge_base/kb.db`。Evidence: `astrbot/core/config/default.py:8-10`, `astrbot/core/knowledge_base/kb_mgr.py:17-20`

## 已知冲突

- `[Conflict]` Python 版本要求存在三处不一致：README badge 写 `python-3.10+`，`main.py` 的 `check_env()` 也只检查 `3.10+`，但 `pyproject.toml` 已声明 `requires-python = ">=3.12"`。Evidence: `README.md:20-23`, `main.py:43-46`, `pyproject.toml:1-7`
- `[Conflict]` README 把 KOOK 标成社区集成，但当前源码树里存在内建 `kook` 平台适配器并通过 `@register_platform_adapter("kook", ...)` 注册。Evidence: `README.md:158-160`, `astrbot/core/platform/sources/kook/kook_adapter.py:23-27`

## 当前不能下结论的部分

- `[Don't know]` README 中“1000+ plugins”是否与当前线上插件市场真实数量一致，这个工作树里没有离线证据能核定。Evidence: `README.md:49-50`
- `[Don't know]` “Coming Soon”的 WhatsApp 是否已有未合并实现，当前源码树里没有对应内建适配器目录。Evidence: `README.md:157`, `astrbot/core/platform/manager.py:128-187`
