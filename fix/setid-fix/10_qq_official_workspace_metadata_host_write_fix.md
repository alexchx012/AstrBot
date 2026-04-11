# QQ Official Workspace Metadata Host-Write Fix

## Background

The previous `/setid` permission fixes had already made the resolved sandbox
workspace target writable for host-side access, but the host-visible metadata
tree under `data/qq_workspaces/` still remained at default `755/644`.

That meant `snight` could write through:

- `data/qq_workspaces/<appid>/<alias>/workspace -> <real workspace>`

but still could **not** write directly inside:

- `data/qq_workspaces/`
- `data/qq_workspaces/<appid>/`
- `data/qq_workspaces/<appid>/<alias>/`
- `README.md`
- `manifest.json`
- `.manifest.lock`

## Root Cause

`astrbot/core/platform/sources/qqofficial/workspace_registry.py` only
normalized permissions for the resolved real workspace tree after successful
binding.

The metadata tree creation path still used:

- `mkdir(..., exist_ok=True)`
- `write_text(...)`

without any follow-up permission normalization.

So the metadata tree stayed at host-visible `755/644`, which blocked direct
host writes by `snight`.

## Files Changed

- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `tests/unit/test_qqofficial_workspace_registry.py`

## Key Implementation

- Added `_normalize_workspace_metadata_permissions()` to walk the full
  `data/qq_workspaces/` metadata tree.
- Reused the existing shared-mode logic so directories inherit writable
  `group/other` bits and keep `setgid`.
- Skipped symlink chmod changes to avoid mutating linked targets via the
  metadata pass.
- Called metadata normalization at the end of `_with_manifest_lock(...)`, so
  every manifest-backed registry operation repairs the metadata tree.

## Verification

- Red:
  `uv run pytest tests/unit/test_qqofficial_workspace_registry.py::test_register_alias_normalizes_metadata_permissions_for_other_users tests/unit/test_qqofficial_workspace_registry.py::test_refresh_workspace_binding_normalizes_existing_metadata_permissions -q`
  Result before fix: `2 failed`
- Green:
  Same command after fix
  Result: `2 passed`
- Related suite:
  `uv run pytest tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_setid_command.py tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_skill_sync -q`
  Result: `20 passed`
- Lint / format:
  `uv run ruff format astrbot/core/platform/sources/qqofficial/workspace_registry.py tests/unit/test_qqofficial_workspace_registry.py`
  `uv run ruff check astrbot/core/platform/sources/qqofficial/workspace_registry.py tests/unit/test_qqofficial_workspace_registry.py`
- Live host verification:
  after applying the patch to the running container and normalizing current
  data, `snight` could create files directly in:
  - `data/qq_workspaces/`
  - `data/qq_workspaces/<appid>/<alias>/`

## Upgrade Notes

- This fix extends the earlier permission model from the resolved workspace
  target to the host-visible metadata tree itself.
- If upstream later introduces a tighter host UID/GID mapping, revisit whether
  `other-write` on metadata files should be narrowed.
