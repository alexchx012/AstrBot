# QQ Official Workspace Host Other-Write Fix

## Background

After the earlier host-permission patch, the stable host-side workspace entry
resolved correctly and the real workspace tree gained group-write permissions.
However, the real test host user `snight` still could not create files through
`data/qq_workspaces/<appid>/<alias>/workspace` without `sudo`.

## Root Cause

The previous permission fix assumed the host user that needs access shares the
mapped group of the bind-mounted Shipyard workspace.

That assumption was wrong in the current environment:

- host workspace paths are visible as `nobody:nogroup`
- `snight` is **not** a member of `nogroup`
- permission normalization only mirrored owner bits to `group`, not to `other`

So even after successful binding, directories became group-writable but still
blocked writes from the actual host user.

## Files Changed

- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `tests/unit/test_qqofficial_workspace_registry.py`

## Key Implementation

- Extended workspace permission normalization to mirror owner read/write/execute
  bits to both `group` and `other`.
- Kept the existing `setgid` behavior for directories.
- Added a regression test proving that resolved workspace permissions also grant
  write access for host users that do not share the mapped Shipyard group.

## Verification

- `uv run pytest tests/unit/test_qqofficial_workspace_registry.py::test_refresh_workspace_binding_normalizes_workspace_permissions_for_other_users -q`
- `uv run pytest tests/unit/test_qqofficial_workspace_registry.py::test_refresh_workspace_binding_normalizes_workspace_permissions tests/unit/test_qqofficial_workspace_registry.py::test_refresh_workspace_binding_normalizes_workspace_permissions_for_other_users -q`
- `env ASTRBOT_ROOT=/tmp/astrbot-testroot-permfix uv run pytest tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_skill_sync -q`
- `uv run ruff format astrbot/core/platform/sources/qqofficial/workspace_registry.py tests/unit/test_qqofficial_workspace_registry.py`
- `uv run ruff check astrbot/core/platform/sources/qqofficial/workspace_registry.py tests/unit/test_qqofficial_workspace_registry.py`

## Upgrade Notes

- This fix intentionally broadens resolved workspace permissions beyond
  group-sharing so that the stable host-side entry remains usable even when the
  host user is not part of the bind-mounted group mapping.
- If upstream later introduces an explicit host UID/GID mapping mechanism, that
  would be a tighter replacement for the current permission model.
