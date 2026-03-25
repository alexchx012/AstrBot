# Async SQLite Test Fixture Dispose Fix

## Background

After the optional plugin collection fix, GitHub Actions `Unit Tests` still failed with repeated `Event loop is closed` annotations in the pytest step.

## Root Cause

Several module-scoped async test fixtures created `SQLiteDatabase(...)` instances and drove `AstrBotCoreLifecycle`, but only stopped the lifecycle during teardown. They did not dispose the async SQLAlchemy engine afterwards.

That left async SQLite engine resources and background work alive past loop teardown, which is consistent with the observed `Event loop is closed` failure pattern in pytest.

## Changed Files

- `tests/test_api_key_open_api.py`
- `tests/test_dashboard.py`
- `tests/test_kb_import.py`

## Key Implementation

- After `core_lifecycle.stop()` teardown completes, explicitly call `await db.engine.dispose()` in each module-scoped fixture that owns a temporary `SQLiteDatabase`.

## Verification

- Confirmed the affected fixtures all created standalone `SQLiteDatabase` instances without disposing their engines:
  - `tests/test_api_key_open_api.py`
  - `tests/test_dashboard.py`
  - `tests/test_kb_import.py`
- Added explicit engine disposal in all three teardown paths.
- Fresh remote verification is delegated to the next GitHub Actions run triggered by this commit, because the original failure was observed in GitHub-hosted pytest rather than a stable local deterministic reproducer.

## Compatibility Notes

- This is test-only cleanup.
- Production runtime code is unchanged.
