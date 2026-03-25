# 04 Integrations And Extensions

## 平台适配器

- `[Fact]` 平台适配器通过 `register_platform_adapter()` 注册，注册元数据里包含描述、默认配置模板、logo、流式消息支持和配置元数据。Evidence: `astrbot/core/platform/register.py:11-63`
- `[Fact]` `PlatformManager.load_platform()` 会按 `type` 动态导入平台实现，并对 `id` 做合法性校验与清洗。Evidence: `astrbot/core/platform/manager.py:102-209`
- `[Fact]` 当前源码里明确出现的内建平台类型有 `aiocqhttp`、`qq_official`、`qq_official_webhook`、`lark`、`dingtalk`、`telegram`、`wecom`、`wecom_ai_bot`、`weixin_oc`、`weixin_official_account`、`discord`、`misskey`、`slack`、`satori`、`line`、`kook`，另加初始化时无条件附加的 `webchat`。Evidence: `astrbot/core/platform/manager.py:97-100`, `astrbot/core/platform/manager.py:128-187`, `astrbot/core/platform/sources/weixin_oc/weixin_oc_adapter.py`
- `[Fact]` 默认配置里列出了支持统一 Webhook 的平台类型。Evidence: `astrbot/core/config/default.py:11-20`
- `[Fact]` Lark 流式发送现在会延迟到首个文本 token 才创建 CardKit 卡片；当 Agent 流式输出发出 `type="break"` 的工具调用边界信号时，当前卡片会先关闭，后续文本再懒创建下一张卡片。Evidence: `astrbot/core/platform/sources/lark/lark_event.py:743-874`, `astrbot/core/astr_agent_run_util.py:167-175`

## Provider 适配器

- `[Fact]` Provider 通过 `register_provider_adapter()` 注册，注册元数据里包含 provider type、默认配置模板和展示名。Evidence: `astrbot/core/provider/register.py:14-53`
- `[Fact]` `ProviderManager` 维护聊天 Provider、STT Provider、TTS Provider、Embedding Provider、Rerank Provider 的实例表和默认选择逻辑。Evidence: `astrbot/core/provider/manager.py:31-83`, `astrbot/core/provider/manager.py:143-271`
- `[Fact]` 当前源码动态导入分支至少覆盖这些类型：`openai_chat_completion`、`zhipu_chat_completion`、`groq_chat_completion`、`xai_chat_completion`、`aihubmix_chat_completion`、`openrouter_chat_completion`、`anthropic_chat_completion`、`googlegenai_chat_completion`、`sensevoice_stt_selfhost`、`openai_whisper_api`、`openai_whisper_selfhost`、`xinference_stt`、`openai_tts_api`、`genie_tts`、`edge_tts`、`gsv_tts_selfhost`、`gsvi_tts_api`、`fishaudio_tts_api`、`dashscope_tts`、`azure_tts`、`minimax_tts_api`、`volcengine_tts`、`gemini_tts`、`openai_embedding`、`gemini_embedding`、`vllm_rerank`、`xinference_rerank`、`bailian_rerank`。Evidence: `astrbot/core/provider/manager.py:346-458`
- `[Fact]` Provider 初始化完成后会异步启动 MCP client 初始化任务。Evidence: `astrbot/core/provider/manager.py:334-344`

## 插件 / Star 机制

- `[Fact]` 项目内部把插件称为 `star`。Evidence: `astrbot/core/star/README.md:1-5`
- `[Fact]` `PluginManager` 同时管理用户插件目录 `data/plugins` 和内置插件目录 `astrbot/builtin_stars`。Evidence: `astrbot/core/star/star_manager.py:153-171`
- `[Fact]` 插件管理器负责扫描模块、重载、依赖安装、失败插件恢复、热重载监听等。Evidence: `astrbot/core/star/star_manager.py:153-236`, `astrbot/core/star/star_manager.py:275-334`
- `[Fact]` 当 `ASTRBOT_RELOAD=1` 且装了 `watchfiles` 时，插件目录会被 watch 并自动重载。Evidence: `astrbot/core/star/star_manager.py:51-56`, `astrbot/core/star/star_manager.py:181-236`
- `[Fact]` 插件依赖安装不是盲装；它会先做 requirements 缺失预检查，再决定是安装裁剪后的 requirements 还是完整 requirements。Evidence: `astrbot/core/star/star_manager.py:79-150`
- `[Fact]` 控制面板的插件市场默认从线上 registry 拉取插件清单，并把缓存写到 `data/plugins.json` 或自定义源对应的缓存文件。Evidence: `astrbot/dashboard/routes/plugin.py:157-249`

## Skills

- `[Fact]` `SkillManager` 默认把技能目录放在运行时 `data/skills` 下，并维护 `data/skills.json` 和沙箱技能缓存文件。Evidence: `astrbot/core/skills/skill_manager.py:16-27`, `astrbot/core/skills/skill_manager.py:225-270`
- `[Fact]` `SkillManager` 现在会把技能目录里的旧 `skill.md` 原地规范化重命名为 `SKILL.md`，并统一按 `SKILL.md` 作为技能入口文件识别。Evidence: `astrbot/core/skills/skill_manager.py:40-59`, `astrbot/core/skills/skill_manager.py:389-389`, `astrbot/core/skills/skill_manager.py:472-472`, `astrbot/core/skills/skill_manager.py:586-586`
- `[Fact]` Skill 条目由技能目录里的技能说明文件驱动，并能解析 frontmatter 描述。Evidence: `astrbot/core/skills/skill_manager.py:51-87`, `astrbot/core/skills/skill_manager.py:339-360`
- `[Fact]` 技能 ZIP 安装现在同时支持两种归档结构：根目录直接包含 `SKILL.md`，或 ZIP 里只有一个顶层技能目录；安装时还会对技能名做归一化并校验，支持中文技能名，同时拒绝多顶层目录、绝对路径和 `..` 路径。Evidence: `astrbot/core/skills/skill_manager.py:538-649`
- `[Fact]` 控制面板支持从 ZIP 上传单个或多个 skills，并在成功后尝试同步到活跃 sandbox；批量上传还会把重复技能归类为 `skipped`，而不是一律算失败。Evidence: `astrbot/dashboard/routes/skills.py:147-191`, `astrbot/dashboard/routes/skills.py:193-367`
- `[Fact]` Skills 路由还内建了面向 Shipyard Neo 的候选版本、发布、回滚、同步能力。Evidence: `astrbot/dashboard/routes/skills.py:47-121`

## SubAgent、Tools 与 MCP

- `[Fact]` `SubAgentOrchestrator` 会从 `subagent_orchestrator.agents` 配置里读取启用的 subagent，构造成 `HandoffTool` 并注册到工具系统。Evidence: `astrbot/core/subagent_orchestrator.py:12-98`, `astrbot/core/config/default.py:146-160`
- `[Fact]` 生命周期初始化时会调用 `_init_or_reload_subagent_orchestrator()`，因此 SubAgent 不是只存在于前端页面，而是实际挂到运行时工具链里。Evidence: `astrbot/core/core_lifecycle.py:82-99`, `astrbot/core/core_lifecycle.py:178-195`
- `[Inference + Evidence]` AstrBot 当前的“工具系统”由 Provider 管理器里的 `llm_tools`、MCP client、SubAgent handoff 和插件注入工具共同组成，而不是单一来源。Evidence: `astrbot/core/provider/register.py:6-12`, `astrbot/core/provider/manager.py:67-83`, `astrbot/core/provider/manager.py:334-344`, `astrbot/core/subagent_orchestrator.py:77-98`

## 知识库与会话附加能力

- `[Fact]` `KnowledgeBaseManager` 负责知识库元数据库初始化、知识库实例装载、文档切块、稀疏检索、融合排序和终止清理。Evidence: `astrbot/core/knowledge_base/kb_mgr.py:23-80`, `astrbot/core/knowledge_base/kb_mgr.py:208-295`
- `[Fact]` 创建知识库时必须提供 `embedding_provider_id`，并可选配置 rerank provider、chunk 参数和 top-k 参数。Evidence: `astrbot/core/knowledge_base/kb_mgr.py:82-129`
- `[Fact]` 生命周期里还会初始化 `CronJobManager`、`ConversationManager` 和 `PlatformMessageHistoryManager`，说明扩展面不只落在插件，还覆盖系统级计划任务和会话持久化。Evidence: `astrbot/core/core_lifecycle.py:166-177`

## 已知冲突

- `[Conflict]` README 把 KOOK 作为社区维护接入列出，但源码里已经存在内建 KOOK 适配器。Evidence: `README.md:158-160`, `astrbot/core/platform/sources/kook/kook_adapter.py:23-27`

## 当前不能下结论的部分

- `[Don't know]` 社区插件市场的线上真实可用性、镜像源健康度和实际可安装数量无法从离线源码树直接证明。Evidence: `astrbot/dashboard/routes/plugin.py:243-248`
