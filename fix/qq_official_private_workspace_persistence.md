# QQ Official Private Workspace Persistence Fix

## Background

This fix implements the `plan.md` goal of giving `qq_official` C2C users a stable host-side workspace entry without changing AstrBot's existing global `unified_msg_origin` semantics.

## Root Cause

The current legacy Shipyard integration keys sandbox reuse directly from the existing session identifier. That is sufficient for reuse, but it does not expose a stable, user-manageable host entry such as `qq_workspaces/<appid>/<alias>/workspace`, and it cannot distinguish the sandbox-only workspace identity from AstrBot's broader session semantics.

## Files Changed

- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
- `astrbot/core/computer/computer_client.py`
- `astrbot/core/computer/tools/browser.py`
- `astrbot/core/computer/tools/fs.py`
- `astrbot/core/computer/tools/neo_skills.py`
- `astrbot/core/computer/tools/python.py`
- `astrbot/core/computer/tools/shell.py`
- `astrbot/core/astr_main_agent_resources.py`
- `astrbot/builtin_stars/builtin_commands/commands/setid.py`
- `astrbot/builtin_stars/builtin_commands/commands/__init__.py`
- `astrbot/builtin_stars/builtin_commands/main.py`
- `tests/unit/test_qqofficial_workspace_registry.py`
- `tests/unit/test_qqofficial_platform_adapter.py`
- `tests/unit/test_setid_command.py`
- `tests/unit/test_computer.py`
- `tests/test_computer_skill_sync.py`
- `tests/test_neo_skill_tools.py`
- `project_index/README.md`
- `project_index/01_product_scope.md`
- `project_index/04_integrations_and_extensions.md`
- `project_index/05_development_and_build.md`

## Key Implementation

- Added `workspace_registry.py` as the qq_official-scoped source of truth for:
  - `workspace_identity = v1:<appid>:<raw_user_id>`
  - alias validation and global uniqueness
  - top-level `data/qq_workspaces/manifest.json`
  - host directory creation and `README.md`
  - legacy Shipyard path resolution from `bay.db`
  - strict metadata fallback and symlink lifecycle
- Kept AstrBot global session routing unchanged:
  - `context.get_config(umo=...)` still uses `unified_msg_origin`
  - legacy Shipyard `create_ship(session_id=...)` now uses `uuid.uuid5(...).hex(workspace_identity)` only when qq_official C2C resolves a valid workspace identity
- Added `/setid` as an in-scope builtin command:
  - only allowed for `qq_official` C2C
  - invalid alias rejected by rule
  - same alias for same user is idempotent
  - conflicting alias returns `该 ID 已被占用，请换一个`
  - first successful binding is immutable in v1
- Added qq_official platform seam behavior:
  - each C2C event now carries explicit `qq_appid` and `qq_message_source`
  - first C2C contact triggers a one-time `/setid` prompt outside command dispatch
  - non-resolved workspace identities get a light reparse on later C2C messages
- Added symlink lifecycle:
  - resolved state creates a relative `workspace` symlink
  - resolved state also refreshes `workspace.last_known_good`
  - regressing to unresolved removes `workspace` but preserves `workspace.last_known_good`

## Verification

- Dependency sync:
  - `uv sync`
- Targeted formatting and lint:
  - `uv run ruff format <changed python files>`
  - `uv run ruff check <changed python files>`
- Relevant regression suites after upstream sync:
  - `uv run pytest tests/test_computer_skill_sync.py tests/test_skill_manager_sandbox_cache.py tests/unit/test_qqofficial_message_event.py tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_computer.py tests/test_neo_skill_tools.py -q`
  - Result: `74 passed`
- Additional focused suites during TDD:
  - `uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py -q`
  - `uv run pytest tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_computer.py -q`
- Upstream check:
  - `git fetch upstream`
  - Result: upstream advanced to `v4.22.0`, so the worktree was merged with latest `upstream/master` before final verification
- Deployment gate:
  - Initial plain worktree compose command built the image but hit existing named-container conflicts because the active stack was already running under another Compose project context
  - Final successful deployment command:
    - `docker compose -f compose-with-shipyard.yml -p astrbot up -d --build --no-deps astrbot`
  - Evidence after restart:
    - `docker ps --format '{{.Names}} {{.Status}}'` showed `astrbot Up 15 seconds`
    - `curl -L -I --max-time 10 http://127.0.0.1:6185` returned `HTTP/1.1 200`
    - recent `docker logs astrbot` showed AstrBot `v4.22.0` booting and downloading the matching WebUI bundle

## Upgrade Notes

- `workspace_identity` is intentionally sandbox-only. Do not replace `unified_msg_origin` with it in unrelated subsystems.
- The legacy Shipyard selector now depends on two host-side facts:
  - `data/shipyard/bay_data/bay.db`
  - `data/shipyard/ship_mnt_data/<ship_id>/...`
- Fallback parsing stays intentionally strict. If future Shipyard metadata layout changes, prefer leaving the workspace `unresolved` over guessing.
- The current deployment validation had to reuse the active Compose project name (`-p astrbot`) because `container_name` values are hard-coded in `compose-with-shipyard.yml`.
- After upstream sync to `v4.22.0`, a separate upstream-side test drift remained in `tests/test_skill_metadata_enrichment.py`; it was not part of the qq_official / legacy Shipyard workspace change set and was not required to validate this fix path.
