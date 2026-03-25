# QQ Official First Shipyard Binding Timing Fix

## Background

In the qq_official C2C `/setid` flow, the first sandbox request could create the
legacy Shipyard workspace successfully, but the stable host-side entry
`data/qq_workspaces/<appid>/<alias>/workspace` was not created until a later
incoming QQ message triggered another binding refresh.

## Root Cause

`astrbot.core.computer.computer_client.get_booter()` refreshed the
qq_official workspace binding before `ShipyardBooter.boot(...)`, but the first
version of the fix still refreshed too early in the success path.

The full timing problem had two layers:

1. Before `boot(...)`, the registry could only see the pre-boot state:
   - no `session_ships` row selected from `bay.db`
   - no resolved ship metadata/workspace path yet
2. Immediately after `boot(...)`, the registry could already see the selected
   ship row, but the stable workspace directory could still be missing until the
   subsequent sandbox skill sync finished touching the workspace filesystem.

Without a later refresh in the same request path, the binding stayed `pending`
or `unresolved` until a later QQ C2C message.

## Files Changed

- `astrbot/core/computer/computer_client.py`
- `tests/unit/test_computer.py`

## Key Implementation

- Kept the existing pre-boot refresh for shipyard workspaces.
- Added a second `refresh_workspace_binding(...)` call immediately after
  `client.boot(...)` succeeds for shipyard + qq_official workspace identities.
- Added a third `refresh_workspace_binding(...)` call after
  `_sync_skills_to_sandbox(...)`, so the same first sandbox request also covers
  the case where the workspace path only becomes visible during skill sync.
- Added regression tests that simulate both timing windows:
  - `/setid` already registered
  - `get_booter(...)` starts
  - fake Shipyard `boot(...)` creates `bay.db`, `session_ships`, and metadata`
  - workspace may appear either during `boot(...)` or during skill sync
  - assertion requires the stable `workspace` symlink to exist before
    `get_booter(...)` returns

## Verification

- `uv run pytest tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot -q`
- `uv run pytest tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_skill_sync -q`
- `env ASTRBOT_ROOT=/tmp/astrbot-testroot-fix-b uv run pytest tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_uses_workspace_identity_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_reuses_workspace_identity_cache_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot -q`
- `env ASTRBOT_ROOT=/tmp/astrbot-testroot-fix2 uv run pytest tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_uses_workspace_identity_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_reuses_workspace_identity_cache_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_skill_sync -q`
- `uv run ruff format astrbot/core/computer/computer_client.py tests/unit/test_computer.py`
- `uv run ruff check astrbot/core/computer/computer_client.py tests/unit/test_computer.py`

## Upgrade Notes

- If upstream changes the Shipyard boot lifecycle, keep the post-boot binding
  refresh semantics: the stable host-side workspace entry must be resolved in the
  same first sandbox request that creates the ship, even if the workspace path
  only becomes visible after the skill-sync stage.
- If future refactors move workspace binding out of `computer_client`, preserve
  the regression test or equivalent coverage for the first-boot timing window.
