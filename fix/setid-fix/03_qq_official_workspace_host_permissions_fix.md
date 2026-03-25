# QQ Official Workspace Host Permissions Fix

## Background

Real-device testing showed that the stable host-side entry
`data/qq_workspaces/<appid>/<alias>/workspace` could be resolved correctly, but
the host user `snight` could not create files through that path.

## Root Cause

The resolved legacy Shipyard workspace was visible on the host with ownership
mapped to `nobody:nogroup` and directory mode `755`. In the current environment,
`snight` is a member of `nogroup`, so the missing group write bit blocked host
side writes.

The binding flow only created symlinks. It did not normalize permissions on the
real workspace tree after resolution.

## Modified Files

- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `tests/unit/test_qqofficial_workspace_registry.py`

## Key Implementation

- Added workspace permission normalization during successful workspace binding.
- Mirrored owner permissions to group permissions for existing files.
- Made resolved directories group-readable, group-writable, group-executable,
  and `setgid`, so the shared group remains stable for host-side operations.
- Kept ownership unchanged. The fix relies on the existing host/container group
  mapping instead of hard-coding host user IDs.

## Verification

- `uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py -q`
- `uv run ruff format astrbot/core/platform/sources/qqofficial/workspace_registry.py tests/unit/test_qqofficial_workspace_registry.py`
- `uv run ruff check /home/snight/AstrBot`
- Real-device retest requested after environment reset

## Upgrade Notes

- This fix assumes the host user that needs workspace access shares the mapped
  group of the bind-mounted Shipyard workspace.
- If future deployment changes user-namespace mapping or bind-mount ownership,
  re-check whether group-based sharing is still sufficient.
- This fix does not change the separate timing issue where the first sandbox
  request may require a later refresh before the stable symlink is materialized.
