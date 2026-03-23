# QQ Official Private Workspace Persistence Decisions

## Purpose

This file records implementation details that would normally require user confirmation, but were chosen conservatively so execution could continue unattended.

## Decisions

### 2026-03-23: Isolated worktree location

- Original choice to confirm: create the worktree inside the repository (`.worktrees/` or `worktrees/`) or outside the repository.
- Conservative implementation: use an external worktree at `/home/snight/.config/superpowers/worktrees/AstrBot/qq-official-workspace-persistence`.
- Reason: avoids touching repository ignore rules beyond the user's existing local `.gitignore` change and avoids direct work on `master`.

### 2026-03-23: Continue despite non-clean baseline

- Original choice to confirm: stop and investigate pre-existing related test failures before implementing the new plan.
- Conservative implementation: continue, but treat the baseline as non-clean and keep explicit evidence.
- Evidence:
  - `uv run pytest tests/unit/test_qqofficial_message_event.py tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_computer.py -q`
  - Pre-change failures: `tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard`, `test_get_booter_unknown_type`, `test_get_booter_rebuild_unavailable`
- Reason: user requested uninterrupted execution of `plan.md`; the failures are pre-existing and stem from current `get_booter()` runtime defaults, not from the planned workspace feature.

### 2026-03-23: Shipyard metadata fallback contract

- Original choice to confirm: whether to wait for a live `ship_mnt_data/<ship_id>/metadata/*` sample before implementing fallback parsing.
- Conservative implementation: proceed with a strict fallback parser that only resolves when metadata is unambiguous, and otherwise marks the workspace as `unresolved`.
- Evidence available:
  - `compose-with-shipyard.yml` binds `${PWD}/data/shipyard/bay_data` and `${PWD}/data/shipyard/ship_mnt_data`
  - local `bay.db` schema contains `session_ships(session_id, ship_id, ...)`
  - running `astrbot_shipyard` container creates `<ship_id>/home` and `<ship_id>/metadata`, and mounts metadata to `/app/metadata`
  - local `ship_mnt_data` is currently empty, so no live metadata sample exists yet
- Reason: this keeps behavior safe under uncertainty and matches the plan's "prefer unresolved over guessing" rule.

### 2026-03-23: Path helper scope

- Original choice to confirm: introduce a broader new path utility layer or keep the change local.
- Conservative implementation: use `pathlib.Path` in the new code and reuse the existing `astrbot.core.utils.astrbot_path` entry points instead of doing a broader path utility refactor first.
- Reason: the repository currently has `astrbot/core/utils/astrbot_path.py` but no `astrbot/core/utils/path_utils.py`; broad path infra changes would add unrelated scope.

### 2026-03-23: Alias immutability conflict response

- Original choice to confirm: what to return when the same `workspace_identity` tries to bind a different alias after the first successful `/setid`.
- Conservative implementation: reject the change with `你已经绑定过 ID，暂不支持修改。`
- Reason: v1 scope freezes alias after first success, and refusing mutation is safer than trying to support rename or remap flows without an explicit migration design.

### 2026-03-23: Deployment validation command in worktree

- Original choice to confirm: whether to stop/remove the running production-like containers from the worktree compose project when `container_name` conflicts appeared.
- Conservative implementation: keep the existing dependency containers untouched and deploy only the `astrbot` service with:
  - `docker compose -f compose-with-shipyard.yml -p astrbot up -d --build --no-deps astrbot`
- Reason: running the plain worktree command tried to recreate `milvus-*` and `astrbot_shipyard` under a different Compose project context and hit existing `container_name` conflicts. Reusing the active project name and `--no-deps` updated only the target service with the newly built image.

### 2026-03-23: Local project index refresh after upstream sync

- Original choice to confirm: whether to refresh `project_index/` inside the worktree even though it is not part of upstream tracked files.
- Conservative implementation: copy the existing local `project_index/` baseline into the worktree and make a minimal refresh for the merged source state:
  - version anchors updated from `4.21.0` to `4.22.0`
  - platform coverage notes updated to include `weixin_oc`
- Reason: repository rules require `project_index/` to be refreshed in the same round when upstream changes are synced.
