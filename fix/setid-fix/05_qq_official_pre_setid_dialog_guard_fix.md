# QQ Official Pre-SetID Dialogue Guard Fix

## Background

Real-device testing showed that the first `qq_official` private message could
still receive a normal assistant reply even after the `/setid` onboarding prompt
was sent.

At first glance this looked like a callback deduplication problem, but further
evidence showed the deeper issue was that a private-message path still reached
the main dialogue pipeline before the user finished `/setid` registration.

## Root Cause

- `workspace_registry` correctly marked the user as `prompted`.
- The first-contact message could still enter AstrBot's normal conversation flow
  as a `FriendMessage`.
- Evidence from the installed `botpy` SDK showed:
  - `DirectMessage` carries `guild_id` / `src_guild_id` / `channel_id`
  - `C2CMessage` uses `author.user_openid`
- The practical failure mode was:
  - a true C2C onboarding prompt was sent
  - then a second private-message path still reached the main dialogue pipeline
  - once that happened, `astrbot_plugin_mnemosyne` prepended long-term memory in
    `user_prompt` mode, which made the stray second reply more obvious

So the correct fix surface was the `qq_official` adapter boundary, not Mnemosyne.

## Modified Files

- `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
- `astrbot/core/platform/sources/qqofficial/workspace_registry.py`
- `tests/unit/test_qqofficial_platform_adapter.py`

## Key Implementation

- Added `QQOfficialWorkspaceRegistry.get_alias_state(...)` for read-only state
  checks.
- Kept a focused `prompted` guard only on the C2C path:
  - when alias state is `prompted`
  - and the incoming C2C text is not `/setid ...`
  - the message is suppressed before it reaches `commit_event(...)`
- Added a structural filter for `on_direct_message_create()`:
  - if a `DirectMessage` event lacks guild context
  - it is ignored as a non-guild duplicate private event
  - genuine guild direct messages still pass through
- Added `info`-level outgoing platform logs for:
  - the onboarding `/setid` prompt
  - standard text replies sent by the qq_official adapter

This keeps the logic narrowly scoped and avoids piling on heuristic duplicate
filters or plugin-side workarounds.

## Verification

- `uv run pytest tests/unit/test_qqofficial_platform_adapter.py::test_on_direct_message_create_ignores_events_without_guild_context tests/unit/test_qqofficial_platform_adapter.py::test_on_direct_message_create_allows_events_with_guild_context tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_suppresses_prompted_non_command tests/unit/test_qqofficial_platform_adapter.py::test_on_c2c_message_create_allows_setid_when_prompted tests/unit/test_qqofficial_platform_adapter.py::test_send_by_session_common_logs_outgoing_text tests/unit/test_qqofficial_platform_adapter.py::test_maybe_prompt_setid_logs_outgoing_prompt -q`
- `uv run pytest tests/unit/test_setid_command.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py -q`
- `uv run ruff check /home/snight/AstrBot`
- Real-device reset performed before retest:
  - `qq_workspaces` cleared
  - `ship_mnt_data` cleared
  - `bay.db` ship/session rows cleared
  - `data_v4.db` conversation + `sel_conv_id` for the QQ session cleared
  - Mnemosyne `message_counters.db` rows for the QQ session cleared
  - Milvus `default` collection rows for the QQ session cleared

## Upgrade Notes

- If future product requirements change so that pre-registration private
  messages should still talk to the model, this guard must be revisited.
- The correct place for this behavior is the `qq_official` adapter boundary,
  not the Mnemosyne plugin.
- If the plugin is modified later, do not use Mnemosyne behavior as the primary
  fix surface for this issue unless the message has already been confirmed to be
  correctly blocked at the adapter layer.
