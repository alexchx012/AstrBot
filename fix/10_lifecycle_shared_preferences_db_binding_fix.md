# Lifecycle Shared Preferences DB Binding Fix

## Background

After the pytest loop and fixture cleanup fixes, the next local reproduced failure moved to:

`sqlite3.OperationalError: attempt to write a readonly database`

during `tests/test_api_key_open_api.py` setup.

## Root Cause

`AstrBotCoreLifecycle` accepted a custom database instance via `self.db`, but still constructed:

- `UmopConfigRouter`
- `AstrBotConfigManager`

with the global `sp` singleton imported from `astrbot.api`, which is bound to the default global database created in `astrbot.core.__init__`.

In tests that intentionally create a temporary `SQLiteDatabase`, lifecycle initialization therefore mixed:

- temporary lifecycle database for core components
- global shared-preferences database for UMOP/config routing

This mismatched database binding caused writes to hit the wrong backing database.

## Changed Files

- `astrbot/core/core_lifecycle.py`
- `tests/unit/test_core_lifecycle.py`

## Key Implementation

- Create a lifecycle-owned `SharedPreferences(db_helper=self.db)` inside `AstrBotCoreLifecycle.initialize()`.
- Pass that lifecycle-bound shared-preferences instance to both `UmopConfigRouter` and `AstrBotConfigManager`.
- Added a unit regression test asserting lifecycle initialization no longer reuses the global `sp` singleton for those two components.

## Verification

1. Red:
   `env TESTING=true uv run pytest tests/unit/test_core_lifecycle.py -k lifecycle_bound_shared_preferences -q`
   Result before the fix: `1 failed`
2. Green:
   `env TESTING=true uv run pytest tests/unit/test_core_lifecycle.py -k lifecycle_bound_shared_preferences -q`
   Result after the fix: `1 passed`
3. Regression bundle:
   `env TESTING=true uv run pytest tests/unit/test_asyncio_threadsafe_callback.py tests/unit/test_mnemosyne_context_manager.py -q`
   Result: `2 passed`
4. Symptom movement:
   Re-running `tests/test_api_key_open_api.py::test_api_key_scope_and_revoke` after this fix no longer reproduced the previous `readonly database` setup failure.

## Compatibility Notes

- This changes lifecycle initialization semantics when a non-default database is injected.
- The new behavior is more coherent: routing/config shared-preferences now follow the lifecycle database instead of silently writing to the global default database.
