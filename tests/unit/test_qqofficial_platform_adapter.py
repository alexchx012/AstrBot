import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import (
    QQOfficialMessageEvent,
)
from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
    QQOfficialPlatformAdapter,
)


def _make_adapter():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    return QQOfficialPlatformAdapter(
        platform_config={
            "id": "test-qq",
            "appid": "123456",
            "secret": "secret",
            "enable_group_c2c": True,
            "enable_guild_direct_message": True,
        },
        platform_settings={},
        event_queue=MagicMock(),
    )


def _make_message(*, message_id: str, event_id: str | None = None) -> AstrBotMessage:
    abm = AstrBotMessage()
    abm.type = MessageType.FRIEND_MESSAGE
    abm.sender = MessageMember(user_id="user-1", nickname="tester")
    abm.message = []
    abm.message_str = "hello"
    abm.session_id = "session-1"
    abm.message_id = message_id
    abm.raw_message = SimpleNamespace(id=message_id, event_id=event_id)
    return abm


def _make_async_parse_stub(abm: AstrBotMessage):
    async def _stub(_message, _message_type):
        return abm

    return staticmethod(_stub)


def _mark_prompted(adapter: QQOfficialPlatformAdapter) -> None:
    adapter.workspace_registry.maybe_mark_prompted(
        appid=str(adapter.appid),
        raw_user_id="user-1",
    )


def test_duplicate_event_id_is_committed_once():
    adapter = _make_adapter()
    adapter.commit_event = MagicMock()

    adapter.client._commit(_make_message(message_id="msg-1", event_id="evt-1"))
    adapter.client._commit(_make_message(message_id="msg-1", event_id="evt-1"))

    assert adapter.commit_event.call_count == 1


def test_duplicate_message_id_without_event_id_is_committed_once():
    adapter = _make_adapter()
    adapter.commit_event = MagicMock()

    adapter.client._commit(_make_message(message_id="msg-2", event_id=None))
    adapter.client._commit(_make_message(message_id="msg-2", event_id=None))

    assert adapter.commit_event.call_count == 1


def test_commit_attaches_qq_c2c_metadata_to_event():
    adapter = _make_adapter()
    adapter.commit_event = MagicMock()

    adapter.client._commit(
        _make_message(message_id="msg-3", event_id="evt-3"),
        message_source="c2c",
    )

    event = adapter.commit_event.call_args.args[0]
    assert event.get_extra("qq_appid") == "123456"
    assert event.get_extra("qq_message_source") == "c2c"


@pytest.mark.asyncio
async def test_maybe_prompt_setid_for_c2c_sends_once(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-prompt", event_id="evt-prompt")
    post_mock = AsyncMock(return_value={"id": "ret-1"})

    monkeypatch.setattr(QQOfficialMessageEvent, "post_c2c_message", post_mock)

    first = await adapter.maybe_prompt_setid_for_c2c(abm)
    second = await adapter.maybe_prompt_setid_for_c2c(abm)

    assert first is True
    assert second is False
    post_mock.assert_awaited_once()
    assert "/setid" in post_mock.await_args.kwargs["content"]


@pytest.mark.asyncio
async def test_on_c2c_message_create_stops_after_first_prompt(monkeypatch):
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-c2c", event_id="evt-c2c")
    prompt_mock = AsyncMock(return_value=True)
    refresh_mock = MagicMock()
    commit_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(adapter, "maybe_prompt_setid_for_c2c", prompt_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter.client, "_commit", commit_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    prompt_mock.assert_awaited_once_with(abm)
    refresh_mock.assert_not_called()
    commit_mock.assert_not_called()


@pytest.mark.asyncio
async def test_on_c2c_message_create_commits_when_prompt_not_sent(monkeypatch):
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-c2c-2", event_id="evt-c2c-2")
    prompt_mock = AsyncMock(return_value=False)
    refresh_mock = MagicMock()
    commit_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(adapter, "maybe_prompt_setid_for_c2c", prompt_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter.client, "_commit", commit_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    prompt_mock.assert_awaited_once_with(abm)
    refresh_mock.assert_called_once_with(abm)
    commit_mock.assert_called_once_with(abm, message_source="c2c")


@pytest.mark.asyncio
async def test_on_c2c_message_create_allows_first_message_setid_without_prompt(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-c2c-setid", event_id="evt-c2c-setid")
    abm.message_str = "/setid abc123"
    post_mock = AsyncMock(return_value={"id": "ret-1"})
    refresh_mock = MagicMock()
    commit_event_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(QQOfficialMessageEvent, "post_c2c_message", post_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    post_mock.assert_not_awaited()
    refresh_mock.assert_called_once_with(abm)
    assert commit_event_mock.call_count == 1
    assert (
        adapter.workspace_registry.get_alias_state(
            appid=str(adapter.appid),
            raw_user_id="user-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_on_c2c_message_create_commits_when_prompt_send_fails(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-c2c-fail", event_id="evt-c2c-fail")
    post_mock = AsyncMock(side_effect=RuntimeError("boom"))
    refresh_mock = MagicMock()
    commit_event_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(QQOfficialMessageEvent, "post_c2c_message", post_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    post_mock.assert_awaited_once()
    refresh_mock.assert_called_once_with(abm)
    assert commit_event_mock.call_count == 1
    assert (
        adapter.workspace_registry.get_alias_state(
            appid=str(adapter.appid),
            raw_user_id="user-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_on_direct_message_create_ignores_events_without_guild_context(
    monkeypatch,
):
    adapter = _make_adapter()
    direct_abm = _make_message(message_id="msg-dm", event_id="evt-dm")
    commit_event_mock = MagicMock()
    raw_message = SimpleNamespace(guild_id=None, src_guild_id=None, channel_id=None)

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(direct_abm),
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_direct_message_create(raw_message)

    commit_event_mock.assert_not_called()


@pytest.mark.asyncio
async def test_on_direct_message_create_allows_events_with_guild_context(monkeypatch):
    adapter = _make_adapter()
    direct_abm = _make_message(message_id="msg-dm-guild", event_id="evt-dm-guild")
    commit_event_mock = MagicMock()
    raw_message = SimpleNamespace(
        guild_id="guild-1",
        src_guild_id="src-guild-1",
        channel_id="channel-1",
    )

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(direct_abm),
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_direct_message_create(raw_message)

    assert commit_event_mock.call_count == 1


@pytest.mark.asyncio
async def test_on_c2c_message_create_suppresses_prompted_non_command(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    _mark_prompted(adapter)
    abm = _make_message(message_id="msg-c2c-3", event_id="evt-c2c-3")
    prompt_mock = AsyncMock(return_value=False)
    refresh_mock = MagicMock()
    commit_event_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(adapter, "maybe_prompt_setid_for_c2c", prompt_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    prompt_mock.assert_awaited_once_with(abm)
    refresh_mock.assert_called_once_with(abm)
    commit_event_mock.assert_not_called()


@pytest.mark.asyncio
async def test_on_c2c_message_create_allows_setid_when_prompted(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    _mark_prompted(adapter)
    abm = _make_message(message_id="msg-c2c-4", event_id="evt-c2c-4")
    abm.message_str = "/setid abc123"
    prompt_mock = AsyncMock(return_value=False)
    refresh_mock = MagicMock()
    commit_event_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        _make_async_parse_stub(abm),
    )
    monkeypatch.setattr(adapter, "maybe_prompt_setid_for_c2c", prompt_mock)
    monkeypatch.setattr(
        adapter, "maybe_refresh_workspace_binding_for_c2c", refresh_mock
    )
    monkeypatch.setattr(adapter, "commit_event", commit_event_mock)

    await adapter.client.on_c2c_message_create(SimpleNamespace())

    prompt_mock.assert_awaited_once_with(abm)
    refresh_mock.assert_called_once_with(abm)
    assert commit_event_mock.call_count == 1


@pytest.mark.asyncio
async def test_maybe_prompt_setid_logs_outgoing_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-prompt-log", event_id="evt-prompt-log")
    post_mock = AsyncMock(return_value={"id": "ret-1"})
    log_mock = MagicMock()

    monkeypatch.setattr(QQOfficialMessageEvent, "post_c2c_message", post_mock)
    monkeypatch.setattr(
        "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.logger.info",
        log_mock,
    )

    assert await adapter.maybe_prompt_setid_for_c2c(abm) is True
    assert any(
        "[QQOfficial] Outgoing onboarding prompt"
        in str(call.args[0] if call.args else "")
        for call in log_mock.call_args_list
    )


@pytest.mark.asyncio
async def test_send_by_session_common_logs_outgoing_text(monkeypatch):
    adapter = _make_adapter()
    adapter._session_last_message_id["user-1"] = "inbound-msg-1"
    parse_mock = AsyncMock(
        return_value=("hello from adapter", None, None, None, None, None, None)
    )
    post_mock = AsyncMock(return_value={"id": "reply-msg-1"})
    log_mock = MagicMock()
    session = SimpleNamespace(
        session_id="user-1", message_type=MessageType.FRIEND_MESSAGE
    )

    monkeypatch.setattr(QQOfficialMessageEvent, "_parse_to_qqofficial", parse_mock)
    monkeypatch.setattr(QQOfficialMessageEvent, "post_c2c_message", post_mock)
    monkeypatch.setattr(
        "astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter.logger.info",
        log_mock,
    )

    await adapter._send_by_session_common(session, SimpleNamespace())

    post_mock.assert_awaited_once()
    assert any(
        "[QQOfficial] Outgoing message" in str(call.args[0] if call.args else "")
        for call in log_mock.call_args_list
    )
