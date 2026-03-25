# QQ Message Fix

## Background

- Date: 2026-03-21
- Scope: QQ 官方适配器重复入站去重，Mnemosyne 首轮上下文污染修复
- Goal: 修复“QQ 私聊同一句被处理两次”和“首条消息被模型误判成发了两次”的本地问题

## Symptoms

1. `2026-03-20 23:17:58.739` 和 `2026-03-20 23:17:59.015` 两条完全相同的 QQ 私聊消息同时进入 `event_bus`，导致同一句被处理两次、回复两次。
2. 首条 `你好呀` 在 `event_bus` 只出现一次，但发给模型的 payload 里出现了两条 user message，导致模型误判“你连续发了两次你好呀”。

## Root Cause

### 1. qq_official websocket adapter had no dedup

- `qq_official` 的 websocket 入口会直接 `_commit()` 到事件队列。
- 原实现没有基于 `event_id` 或 `message.id` 的幂等保护。
- 一旦上游重复投递，AstrBot 会完整处理两次。

### 2. Mnemosyne mutated AstrBot request contexts in place

- `Mnemosyne` 在首次看到某个 session 时，会用 `init_conv(session_id, req.contexts, event)` 初始化自己的上下文管理器。
- 原实现直接保存 `req.contexts` 的原始引用。
- 随后 `add_message("user", ...)` 会把当前用户消息 append 到这份同一个 list 上。
- AstrBot reset 时又会正常追加当前轮输入一次，模型因此同时看到“历史里的当前消息”和“当前轮消息”。

## Code Changes

### A. QQ duplicate inbound guard

- File: `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
- Added `_seen_incoming_event_keys` and 60-second TTL cleanup.
- Dedup key strategy:
  - prefer `event_id`
  - also record `message.id`
  - skip commit when either key has already been seen inside TTL
- Applied the guard before `commit_event()`.

### B. Mnemosyne context isolation

- File: `data/plugins/astrbot_plugin_mnemosyne/memory_manager/context_manager.py`
- Changed `init_conv()` to store a deep copy of `contexts`.
- This prevents plugin-internal history writes from leaking back into AstrBot's live request contexts.

### C. Regression tests

- `tests/unit/test_mnemosyne_context_manager.py`
- `tests/unit/test_qqofficial_platform_adapter.py`

## Validation

- Red:
  - `uv run pytest tests/unit/test_mnemosyne_context_manager.py tests/unit/test_qqofficial_platform_adapter.py`
  - 3 tests failed before the fix
- Green:
  - same command passed after the fix

## Upgrade Notes

- Future AstrBot upgrades may overwrite:
  - `astrbot/core/platform/sources/qqofficial/qqofficial_platform_adapter.py`
  - `data/plugins/astrbot_plugin_mnemosyne/memory_manager/context_manager.py`
- If an upgrade reintroduces duplicate QQ private messages or first-turn duplicated user content, re-check these two local patches first.
