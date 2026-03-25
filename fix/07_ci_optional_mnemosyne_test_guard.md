# CI Optional Mnemosyne Test Guard

## Background

GitHub Actions reported failures for both `Unit Tests` and `Run tests and upload coverage` after commit `0808ea6739d92f6eacc8509a1947b9dab4e90ab0`.

## Root Cause

`tests/unit/test_mnemosyne_context_manager.py` imported `astrbot_plugin_mnemosyne` at module import time and assumed the plugin source tree existed under `data/plugins/astrbot_plugin_mnemosyne`.

That assumption is only true on some local machines. Fresh CI checkouts do not include that optional plugin source tree, so pytest failed during collection with:

`ModuleNotFoundError: No module named 'astrbot_plugin_mnemosyne'`

## Changed Files

- `tests/unit/test_mnemosyne_context_manager.py`

## Key Implementation

- Added a module-level guard that skips the test when `data/plugins/astrbot_plugin_mnemosyne` is absent.
- Kept the real import path unchanged when the plugin source tree is present, so plugin regressions still fail normally on machines that actually have the plugin checked out.

## Verification

Evidence gathered in a fresh detached worktree at `/tmp/astrbot-ci-repro`:

1. Before the guard, `bash ./scripts/run_pytests_ci.sh ./tests` failed during collection with:
   `ModuleNotFoundError: No module named 'astrbot_plugin_mnemosyne'`
2. After the guard, the same command advanced past collection and reported:
   `collected 933 items / 1 skipped`

## Compatibility Notes

- This change only affects environments where the optional Mnemosyne plugin source tree is absent.
- Environments that actually vendor the plugin into `data/plugins/astrbot_plugin_mnemosyne` will still execute the test normally.
- During re-verification, a second local blocker appeared: `tests/test_api_key_open_api.py` hangs in this machine's fresh `uv sync` environment while awaiting SQLite initialization. That issue is separate from the missing-plugin collection error and has not yet been confirmed from GitHub's inaccessible full job logs.
