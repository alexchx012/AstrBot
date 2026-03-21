# QQ Official URL Block Fix

## Background

AstrBot running in the local `astrbot` container hit a QQ Official C2C send failure in the latest logs:

- `botpy.errors.ServerError: 消息发送失败, 不允许发送url`

The failing response was a long plain-text answer that AstrBot first wrapped into QQ markdown payload and sent through `/v2/users/{openid}/messages`.

## Root Cause

`QQOfficialMessageEvent._send_with_markdown_fallback()` only handled one markdown rejection branch before this fix:

- `不允许发送原生 markdown`

But the latest production failure was another server-side rejection for the same markdown send path:

- `不允许发送url`

Because that error string was not included in the fallback condition, the exception bubbled up and the reply was lost instead of retrying as plain `content`.

## Changed Files

- `astrbot/core/platform/sources/qqofficial/qqofficial_message_event.py`
- `tests/unit/test_qqofficial_message_event.py`

## Key Implementation

1. Added `URL_NOT_ALLOWED_ERROR = "不允许发送url"` to the QQ Official event sender.
2. Reused the existing markdown-to-content retry path when QQ rejects markdown payloads because of URL restriction.
3. Kept the existing newline-retry logic for streaming markdown unchanged.
4. Added a regression test to prove that a markdown send rejected with `不允许发送url` is retried as plain `content` with `msg_type=0`.

## Verification

Executed locally in `/home/snight/AstrBot`:

- `uv run pytest tests/unit/test_qqofficial_message_event.py`
- `uv run pytest tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_qqofficial_message_event.py`
- `uv run ruff format .`
- `uv run ruff check .`

All commands passed.

## Compatibility Notes For Future AstrBot Upgrades

- If upstream rewrites `QQOfficialMessageEvent._send_with_markdown_fallback()`, re-check both QQ markdown rejection strings:
  - `不允许发送原生 markdown`
  - `不允许发送url`
- If upstream changes QQ C2C payload semantics, confirm the fallback still removes `markdown`, sets `content`, and downgrades `msg_type` from `2` to `0`.
- Re-run the regression test after any merge that touches QQ Official sending, botpy version, or message serialization.
