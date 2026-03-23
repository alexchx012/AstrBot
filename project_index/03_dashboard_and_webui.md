# 03 Dashboard And WebUI

## 后端承载方式

- `[Fact]` 控制面板后端是 `astrbot.dashboard.server.AstrBotDashboard`，技术栈是 Quart + Hypercorn。Evidence: `astrbot/dashboard/server.py:13-16`, `astrbot/dashboard/server.py:60-421`
- `[Fact]` 静态资源目录优先级是：显式 `webui_dir` 参数 > `data/dist/` > 打包进 wheel 的 `astrbot/dashboard/dist/`。Evidence: `astrbot/dashboard/server.py:72-88`
- `[Fact]` Dashboard 默认读 `dashboard.host`/`dashboard.port`，默认值分别是 `0.0.0.0` 和 `6185`，也支持通过环境变量覆盖与 SSL 配置。Evidence: `astrbot/core/config/default.py:198-211`, `astrbot/dashboard/server.py:303-421`

## 认证与访问控制

- `[Fact]` `/api` 请求统一走 `auth_middleware()`；`/api/v1/*` 使用 API key 认证，其余 API 默认使用 JWT。Evidence: `astrbot/dashboard/server.py:162-240`
- `[Fact]` API key scope 至少包含 `chat`、`config`、`file`、`im`。Evidence: `astrbot/dashboard/server.py:243-253`
- `[Fact]` 登录接口直接对比 `dashboard.username` 和 `dashboard.password`；JWT 默认 7 天过期。Evidence: `astrbot/dashboard/routes/auth.py:22-48`, `astrbot/dashboard/routes/auth.py:82-91`
- `[Inference + Evidence]` 控制面板默认登录凭据很可能是 `astrbot / astrbot`：默认用户名就是 `astrbot`，默认密码存的是 `77b90590a8945a7d36c963981a307dc9`，登录前端会把输入密码做 MD5，且该哈希值正好对应 `astrbot`，服务端启动日志也提示“默认用户名和密码: astrbot”。 Evidence: `astrbot/core/config/default.py:198-205`, `dashboard/src/views/authentication/authForms/AuthLogin.vue:20-30`, `astrbot/dashboard/server.py:358-362`

## 控制面板后端功能面

- `[Fact]` `AstrBotDashboard` 初始化时挂载了更新、统计、插件、命令、配置、日志、静态文件、认证、API key、聊天、Open API、ChatUI 项目、Tools、SubAgent、Skills、会话管理、人格、Cron、T2I、知识库、平台、备份和 Live Chat 路由。Evidence: `astrbot/dashboard/server.py:99-141`
- `[Fact]` 平台 Webhook 入口统一挂在 `/api/platform/webhook/<webhook_uuid>`，并由平台实例决定是否支持 unified webhook。Evidence: `astrbot/dashboard/routes/platform.py:29-87`
- `[Fact]` 插件市场路由支持安装、上传安装、更新、批量更新、卸载、热重载、README/Changelog 读取、自定义源和失败插件查看；默认线上 registry 带本地缓存和远程 MD5 校验。Evidence: `astrbot/dashboard/routes/plugin.py:46-76`, `astrbot/dashboard/routes/plugin.py:157-249`
- `[Fact]` 插件市场前端现在额外支持按插件 `category` 聚合计数并筛选市场列表，相关状态由 `useExtensionPage()` 维护，`MarketPluginsTab` 渲染分类选择器。Evidence: `dashboard/src/views/extension/useExtensionPage.js:240-337`, `dashboard/src/views/extension/useExtensionPage.js:526-540`, `dashboard/src/views/extension/MarketPluginsTab.vue:172-177`, `dashboard/src/views/extension/MarketPluginsTab.vue:310-315`
- `[Fact]` Skills 路由支持列表、ZIP 上传、批量上传、下载、更新、删除，以及 Neo 候选版本、发布、回滚和同步。Evidence: `astrbot/dashboard/routes/skills.py:47-121`, `astrbot/dashboard/routes/skills.py:122-260`
- `[Fact]` Open API 还提供 WebSocket 聊天接口 `/api/v1/chat/ws`。Evidence: `astrbot/dashboard/routes/open_api.py:39-49`, `astrbot/dashboard/routes/open_api.py:193-260`

## 前端技术栈

- `[Fact]` Dashboard 前端使用 Vue 3、Vite、Pinia、Vuetify、Vue Router、Vue I18n、ApexCharts、Monaco Editor 等依赖。Evidence: `dashboard/package.json:6-77`
- `[Fact]` 前端启动时会先 `setupI18n()`，再挂载 Pinia、Router、Vuetify、确认弹窗插件、打印插件和图表插件。Evidence: `dashboard/src/main.ts:16-82`
- `[Fact]` 前端统一为 axios 和 `window.fetch` 自动附加 JWT 与 `Accept-Language`。Evidence: `dashboard/src/main.ts:85-113`

## 前端路由与页面结构

- `[Fact]` 鉴权页面路由是 `/auth/login`。Evidence: `dashboard/src/router/AuthRoutes.ts:1-16`
- `[Fact]` 主路由 `/main` 下包含扩展、平台、Provider、配置、会话管理、人格、SubAgent、Cron、控制台、Trace、知识库、聊天、设置、About 等页面。Evidence: `dashboard/src/router/MainRoutes.ts:3-170`
- `[Fact]` 当前源码里的页面和组件命名也反映了控制面板职责，例如扩展页、平台页、Provider 页、配置页、会话管理页、SubAgent 页和知识库页都有独立视图文件。Evidence: `dashboard/src/views/ExtensionPage.vue`, `dashboard/src/views/PlatformPage.vue`, `dashboard/src/views/ProviderPage.vue`, `dashboard/src/views/ConfigPage.vue`, `dashboard/src/views/SessionManagementPage.vue`, `dashboard/src/views/SubAgentPage.vue`, `dashboard/src/views/knowledge-base/index.vue`

## 构建与分发

- `[Fact]` 前端本地开发命令是 `vite --host`，生产构建命令是 `vue-tsc --noEmit && vite build`。Evidence: `dashboard/package.json:6-14`
- `[Fact]` Python wheel 在 `ASTRBOT_BUILD_DASHBOARD=1` 时会触发自定义 Hatch 构建钩子：先在 `dashboard/` 执行 `npm install`/`npm run build`，再把 `dashboard/dist` 复制到 `astrbot/dashboard/dist`。Evidence: `pyproject.toml:117-123`, `scripts/hatch_build.py:1-75`
- `[Fact]` GitHub Actions 有独立的 Dashboard CI，会执行 `pnpm install`、`pnpm run build`，然后打包 `dashboard/dist.zip` 并上传。Evidence: `.github/workflows/dashboard_ci.yml:9-55`

## 当前不能下结论的部分

- `[Don't know]` 当前工作树里没有实际运行后的浏览器截图或端到端录屏，因此这里只能索引页面与路由，不能替用户断言所有页面在本地现环境都能成功渲染。 Evidence: `dashboard/src/router/MainRoutes.ts:3-170`
