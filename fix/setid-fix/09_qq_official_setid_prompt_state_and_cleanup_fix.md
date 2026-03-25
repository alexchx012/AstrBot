# QQ Official /setid Prompt State And Cleanup Fix

## Background

Code review on the `/setid` implementation identified two high-risk runtime
issues and a small amount of leftover dead code:

- the first C2C message being `/setid ...` could still trigger the onboarding
  prompt and skip command dispatch
- onboarding prompt delivery failure could leave the session stuck in
  `prompted` state
- explicit dead code remained in the computer client/tool layer

## Root Cause

- `maybe_prompt_setid_for_c2c()` did not special-case a first incoming
  `/setid ...` command before calling `maybe_mark_prompted(...)`.
- prompt state was persisted before QQ prompt delivery, but failures did not
  roll that state back.
- `_build_sync_and_scan_command()` and commented file tool implementations were
  no longer part of the active runtime path.

## Files Changed

- `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `astrbot/core/computer/computer_client.py`
- `astrbot/core/computer/tools/fs.py`
- `tests/unit/test_qqofficial_platform_adapter.py`

## Key Implementation

- Skip onboarding prompt when the incoming first C2C text is already
  `/setid ...`, so the command can enter the normal dispatch path immediately.
- Added `clear_prompted_state(...)` to the workspace registry.
- Roll back `prompted` state if onboarding prompt delivery fails.
- Removed the unused legacy combined sandbox skill sync helper from
  `computer_client.py`.
- Removed commented legacy file tool implementations and commented parameter
  fragments from `fs.py`.

## Verification

- `uv run pytest tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_allows_first_message_setid_without_prompt tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_commits_when_prompt_send_fails -q`
- `env ASTRBOT_ROOT=/tmp/astrbot-setid-fix-b uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_uses_workspace_identity_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_reuses_workspace_identity_cache_key tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_boot tests/unit/test_computer.py::TestComputerClient::test_get_booter_shipyard_resolves_workspace_binding_after_skill_sync -q`
- `uv run ruff format astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py astrbot/core/platform/sources/qqofficial/workspace_registry.py astrbot/core/computer/computer_client.py astrbot/core/computer/tools/fs.py tests/unit/test_qqofficial_platform_adapter.py`
- `uv run ruff check astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py astrbot/core/platform/sources/qqofficial/workspace_registry.py astrbot/core/computer/computer_client.py astrbot/core/computer/tools/fs.py tests/unit/test_qqofficial_platform_adapter.py`

## Upgrade Notes

- If upstream later changes QQ Official onboarding flow, preserve the rule that
  a direct first `/setid ...` command must not be swallowed by the prompt path.
- If prompt delivery becomes transactional elsewhere, `clear_prompted_state(...)`
  may become redundant and can be revisited.
- The removed code in `computer_client.py` and `fs.py` had no active in-repo
  callers at the time of deletion; re-check external scripts before reintroducing
  compatibility shims.
