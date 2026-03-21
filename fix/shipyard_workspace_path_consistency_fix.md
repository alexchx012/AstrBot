# Shipyard Workspace Path Consistency Fix

## 背景

2026-03-21 在 QQ 机器人会话里，模型先根据技能提示声称工作空间根目录是 `/workspace`，但 shell 修复后实际探测到的当前目录是 `/home/ship_<id>/workspace`，且 `/workspace` 不存在。该不一致会误导模型做路径判断，也会影响后续技能读取与排障结论。

## 根因

问题由两部分叠加造成：

1. `astrbot/core/skills/skill_manager.py` 在 sandbox 模式下把技能路径默认渲染成 `/workspace/skills/...`，这会把不存在的路径直接注入模型提示。
2. `astrbot/core/computer/computer_client.py` 在同步 sandbox skill 元数据时，只读取顶层 `stdout`。legacy Shipyard 的 shell 返回实际把输出放在 `data.stdout`，导致运行时真实路径没有回填进缓存，错误提示得不到纠正。

## 改动文件

- `astrbot/core/skills/skill_manager.py`
- `astrbot/core/computer/computer_client.py`
- `tests/test_computer_skill_sync.py`
- `tests/test_skill_manager_sandbox_cache.py`
- `tests/test_skill_metadata_enrichment.py`

## 关键实现

- 新增 sandbox 技能默认路径 helper，统一把本地/同步 skill 的提示路径改成稳定的工作区相对路径 `skills/<name>/SKILL.md`，不再硬编码 `/workspace/...`。
- 对 sandbox-only skill，基于缓存路径和技能名重建安全的提示路径，保留像 `/app/skills/...` 这样的真实运行时路径，同时避免路径注入。
- 将技能提示里的 Mandatory grounding 文案从“absolute path”改为“path shown above exactly”，和 sandbox 相对路径规则保持一致。
- 为 legacy Shipyard 增加 shell 结果兼容解析，支持从 `data.stdout`、`data.stderr`、`data.return_code` 读取输出与状态。

## 验证方法

1. 运行回归测试：
   - `uv run pytest tests/test_computer_skill_sync.py tests/test_skill_manager_sandbox_cache.py tests/test_skill_metadata_enrichment.py`
2. 运行格式与静态检查：
   - `uv run ruff format .`
   - `uv run ruff check .`
3. 预期结果：
   - legacy Shipyard 的 nested `data.stdout` 能被 skill scan 解析。
   - sandbox 本地 skill 在提示中显示为 `skills/<name>/SKILL.md`。
   - sandbox-only 内建 skill 保留真实缓存路径，如 `/app/skills/...`。
   - `build_skills_prompt` 不再强称 skill 路径一定是 absolute path。

## 兼容与升级注意

- legacy `shipyard` 与 `shipyard_neo` 的路径模型不同，后续如果继续统一提示词，优先使用“工作区相对路径”表述，避免假定固定绝对根目录。
- 如果后续升级 Shipyard SDK，需重新检查 shell 返回结构是否仍可能出现嵌套 `data.stdout` / `data.return_code`。
- 这次修复没有修改 legacy Shipyard 的真实工作目录，只修正了提示与解析层。
