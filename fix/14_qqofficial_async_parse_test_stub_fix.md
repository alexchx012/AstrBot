# QQOfficial Async Parse Test Stub Fix

## 背景

在同步上游 `v4.22.2` 后，`qq_official` 适配器的 `_parse_from_qqofficial()` 已经改成异步函数，用于支持附件准备等新逻辑。本地已有的 `tests/unit/test_qqofficial_platform_adapter.py` 仍然把它当成同步函数替身来 monkeypatch，导致升级后相关单元测试失败。

## 根因

- 生产代码接口从同步调用变成了异步调用。
- 本地测试夹具仍然使用 `staticmethod(lambda ...)` 返回普通对象。
- 调用点现在会 `await QQOfficialPlatformAdapter._parse_from_qqofficial(...)`，因此测试里的同步替身会触发 `TypeError: object AstrBotMessage can't be used in 'await' expression`。

## 改动文件

- `tests/unit/test_qqofficial_platform_adapter.py`

## 关键实现

- 新增 `_make_async_parse_stub(abm)`，统一生成可 `await` 的异步替身。
- 将文件内所有针对 `_parse_from_qqofficial` 的 monkeypatch 都改为使用异步 stub。
- 不回退上游异步实现，只修正测试夹具与实际接口保持一致。

## 验证方法

1. 运行：
   - `uv run pytest tests/test_web_searcher.py tests/unit/test_qqofficial_workspace_registry.py tests/unit/test_qqofficial_platform_adapter.py tests/unit/test_qqofficial_message_event.py -q`
2. 运行：
   - `uv run ruff format --check tests/unit/test_qqofficial_platform_adapter.py`
   - `uv run ruff check tests/unit/test_qqofficial_platform_adapter.py`
3. 预期结果：
   - 相关测试通过
   - `ruff` 检查通过

## 兼容与升级注意

- 如果上游后续继续调整 `_parse_from_qqofficial` 的签名或调用方式，测试里的 stub 也需要同步调整，不能再默认它是同步函数。
- 这次修复只更新测试夹具，不改变运行时行为。
