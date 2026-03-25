# QQ Official First C2C SetID Short-Circuit Fix

## Background

During real-device testing, the first `qq_official` C2C message correctly marked
the workspace state as `prompted`, but AstrBot still continued into the normal
conversation flow. The user therefore received a regular assistant reply instead
of only the `/setid` onboarding prompt.

## Root Cause

`QQOfficialClient.on_c2c_message_create()` awaited
`maybe_prompt_setid_for_c2c(abm)` but ignored its boolean result. Even when the
prompt was sent successfully, the same incoming message still went through:

- `maybe_refresh_workspace_binding_for_c2c(abm)`
- `_commit(abm, message_source="c2c")`

That behavior conflicts with the intended first-contact contract: the first C2C
message should only trigger the `/setid` prompt.

## Modified Files

- `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
- `tests/unit/test_qqofficial_platform_adapter.py`

## Key Implementation

- Added an early return in `on_c2c_message_create()` when
  `maybe_prompt_setid_for_c2c(abm)` returns `True`.
- Added tests for both branches:
  - first prompt sent: no refresh, no normal event commit
  - prompt not sent: normal refresh and commit still happen

## Verification

- `uv run pytest tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_stops_after_first_prompt tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_commits_when_prompt_not_sent -q`
- `uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py -q`
- `uv run ruff check /home/snight/AstrBot`

## Upgrade Notes

- If future product behavior changes to allow "prompt + assistant reply" on the
  same first C2C message, this early return will need to be revisited.
- The fix only changes first-contact flow when the prompt is actually sent. It
  does not change later C2C routing or `/setid` registration behavior.
