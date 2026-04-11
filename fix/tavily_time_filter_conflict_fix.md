# Tavily Time Filter Conflict Fix

## Background

- Trigger window: around `2026-03-27 11:20` in the running `astrbot` container logs.
- The session used provider `codesuc/gpt-5.4` and exposed the tool `web_search_tavily`.
- The failure pattern was a web-search request that could carry multiple Tavily time filters at the same time, which should be mutually exclusive.

## Root Cause

- `astrbot/core/tools/web_search_tools.py` defined `TavilyWebSearchTool.call(...)` with an implicit `days=3` default whenever `topic="news"`.
- When the model called the tool with `topic="news"` plus `time_range` or explicit dates, AstrBot still injected the hidden `days` filter into the Tavily payload.
- The code also had no preflight validation to block combinations like:
  - `days` + `time_range`
  - `days` + `start_date/end_date`
  - `time_range` + `start_date/end_date`

## Changed Files

- `astrbot/core/tools/web_search_tools.py`
- `tests/test_web_search_tools.py`

## Key Implementation

1. Added `_build_tavily_search_payload(...)` to centralize Tavily payload construction.
2. Removed the implicit `days=3` injection so AstrBot no longer sends a hidden `days` filter for `topic="news"`.
3. Added a preflight mutual-exclusion check for Tavily time filters before any outbound request is sent.
4. Updated the tool schema descriptions so the model sees stricter usage guidance for `days`, `time_range`, `start_date`, and `end_date`.

## Validation

- Red:
  - `uv run pytest tests/unit/test_qqofficial_workspace_registry.py::test_register_alias_normalizes_metadata_permissions_for_other_users tests/unit/test_qqofficial_workspace_registry.py::test_refresh_workspace_binding_normalizes_existing_metadata_permissions tests/test_web_search_tools.py -q`
  - Confirmed the 4 Tavily tests failed before the fix for the expected reasons: no mutual-exclusion error and hidden `days=3` still present.
- Green:
  - `uv run pytest tests/test_web_search_tools.py -q`
  - Result: `4 passed`
- Static checks:
  - `uv run ruff format .`
  - `uv run ruff check .`

## Compatibility Notes For Future Upgrades

- If upstream changes Tavily parameter semantics, re-check whether `days`, `time_range`, and explicit date ranges are still mutually exclusive.
- If upstream restores a non-empty default for `days`, verify that `topic="news"` with `time_range` still does not inject an extra `days` field.
- Keep `tests/test_web_search_tools.py` when rebasing; it is the regression guard for this bug.
