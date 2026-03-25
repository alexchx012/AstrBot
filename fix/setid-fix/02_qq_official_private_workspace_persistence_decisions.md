# QQ Official 私聊工作区持久化实现决策记录

## 目的

本文件用于记录那些原本应该由用户确认、但为了在无人值守场景下持续执行而采用了保守实现的细节决策。

## 决策

### 2026-03-23：隔离工作树位置

- 原本需要确认的选择：工作树应创建在仓库内（`.worktrees/` 或 `worktrees/`）还是仓库外。
- 保守实现：使用仓库外工作树 `/home/snight/.config/superpowers/worktrees/AstrBot/qq-official-workspace-persistence`。
- 原因：这样可以避免额外改动仓库忽略规则，只依赖用户本地已经存在的 `.gitignore` 改动，同时避免直接在 `master` 上实施变更。

### 2026-03-23：在基线不干净时继续执行

- 原本需要确认的选择：在开始实现前，是否应先停下来处理已有的相关测试失败。
- 保守实现：继续执行，但把该基线明确记为“非全绿”，并保留验证证据。
- 证据：
  - `uv run pytest tests/unit/test_qqofficial_message_event.py tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_computer.py -q`
  - 改动前已有失败：
    - `tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard`
    - `tests/unit/test_computer.py::TestComputerClient::test_get_booter_unknown_type`
    - `tests/unit/test_computer.py::TestComputerClient::test_get_booter_rebuild_unavailable`
- 原因：用户要求不中断地执行 `plan.md`；这些失败是现有 `get_booter()` runtime 默认行为带来的存量问题，不是本次工作区持久化功能引入的问题。

### 2026-03-23：Shipyard metadata fallback 契约

- 原本需要确认的选择：在没有拿到真实 `ship_mnt_data/<ship_id>/metadata/*` 样本前，是否暂停实现 fallback 解析。
- 保守实现：继续实现，但 fallback 解析器必须保持严格，只有在信息唯一且可验证时才解析成功，否则一律标记为 `unresolved`。
- 已掌握证据：
  - `compose-with-shipyard.yml` 把 `${PWD}/data/shipyard/bay_data` 和 `${PWD}/data/shipyard/ship_mnt_data` 绑定到容器
  - 本地 `bay.db` schema 包含 `session_ships(session_id, ship_id, ...)`
  - 运行中的 `astrbot_shipyard` 容器会创建 `<ship_id>/home` 和 `<ship_id>/metadata`，并将 metadata 挂载到 `/app/metadata`
  - 本地 `ship_mnt_data` 当时为空，因此没有现成的 live metadata 样本
- 原因：这能在信息不充分时保持最安全行为，也符合计划里“宁可 unresolved，也不要猜路径”的约束。

### 2026-03-23：路径工具范围

- 原本需要确认的选择：是否顺便引入更完整的新路径工具层。
- 保守实现：新代码统一使用 `pathlib.Path`，并复用现有的 `astrbot.core.utils.astrbot_path` 入口，不额外扩展新的通用路径基础设施。
- 原因：当前仓库存在 `astrbot/core/utils/astrbot_path.py`，但并没有 `astrbot/core/utils/path_utils.py`；如果顺手扩展路径基础设施，会把本次任务扩大成无关重构。

### 2026-03-23：alias 不可变后的冲突返回

- 原本需要确认的选择：当同一个 `workspace_identity` 在第一次 `/setid` 成功后再次尝试绑定另一个 alias，应返回什么。
- 保守实现：直接拒绝，并返回 `你已经绑定过 ID，暂不支持修改。`
- 原因：v1 scope 已冻结为首次成功后 alias 不可修改；在没有显式迁移和 rename 设计前，拒绝修改比尝试支持改绑更安全。

### 2026-03-23：worktree 中的部署验证命令

- 原本需要确认的选择：当 worktree 下执行 Compose 命令撞到现有 `container_name` 冲突时，是否停止或删除已有运行中的类生产容器。
- 保守实现：保持现有依赖容器不动，只更新 `astrbot` 服务本身，使用：
  - `docker compose -f compose-with-shipyard.yml -p astrbot up -d --build --no-deps astrbot`
- 原因：直接在 worktree 目录运行原命令时，Compose 会试图在另一个 project context 下重新创建 `milvus-*` 和 `astrbot_shipyard`，从而撞上既有 `container_name`。复用现有 project name 并加 `--no-deps`，可以只更新目标服务而不碰依赖栈。

### 2026-03-23：上游同步后的本地项目索引刷新

- 原本需要确认的选择：即使 `project_index/` 不是 upstream 跟踪文件，是否仍应在 worktree 中同步刷新。
- 保守实现：将本地已有 `project_index/` 基线复制进 worktree，并只做最小刷新以匹配合并后的源码状态：
  - 版本锚点从 `4.21.0` 更新到 `4.22.0`
  - 平台覆盖面补充 `weixin_oc`
- 原因：仓库规则明确要求：只要同步了 upstream 更新，就必须在同一轮里刷新 `project_index/`。
