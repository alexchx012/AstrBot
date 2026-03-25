# Pytest Asyncio Threadsafe Heartbeat

## Background

After fixing the optional Mnemosyne plugin collection error, GitHub Actions `Unit Tests` still failed on commit `e9fc10f7` with repeated `Event loop is closed` annotations in the pytest step.

## Root Cause

In the current Python 3.12 test environment, delayed `loop.call_soon_threadsafe(...)` callbacks are not reliably processed while the event loop is idle inside async pytest tests and fixtures.

This affects code paths that rely on cross-thread callbacks, including the async SQLite stack used by AstrBot tests. The failure showed up as:

- hanging async database initialization during local repro
- `Event loop is closed` annotations in the GitHub Actions pytest job after the loop was torn down while background callback delivery lagged

## Changed Files

- `tests/conftest.py`
- `tests/unit/test_asyncio_threadsafe_callback.py`

## Key Implementation

- Added an autouse asyncio heartbeat fixture for function-scoped async tests.
- Added an autouse asyncio heartbeat fixture for module-scoped async fixtures.
- Added a regression test that reproduces the delayed `call_soon_threadsafe` wake-up failure.

The heartbeat keeps the event loop ticking during tests so delayed cross-thread callbacks are serviced promptly.

## Verification

Local verification on `/home/snight/AstrBot`:

1. Red:
   `env TESTING=true uv run pytest tests/unit/test_asyncio_threadsafe_callback.py -q`
   Result before the fixture change: `1 failed`, timeout inside `asyncio.wait_for(...)`
2. Green:
   `env TESTING=true uv run pytest tests/unit/test_asyncio_threadsafe_callback.py -q`
   Result after the fixture change: `1 passed`
3. Regression bundle:
   `env TESTING=true uv run pytest tests/unit/test_asyncio_threadsafe_callback.py tests/unit/test_mnemosyne_context_manager.py -q`
   Result: `2 passed`

## Compatibility Notes

- This patch only changes pytest behavior; it does not modify production runtime code.
- The heartbeat is intentionally test-only because the confirmed failure surface is CI / pytest loop handling, not the shipped bot runtime.
