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
async def test_on_c2c_message_create_calls_prompt_hook(monkeypatch):
    adapter = _make_adapter()
    abm = _make_message(message_id="msg-c2c", event_id="evt-c2c")
    prompt_mock = AsyncMock(return_value=True)
    refresh_mock = MagicMock()
    commit_mock = MagicMock()

    monkeypatch.setattr(
        QQOfficialPlatformAdapter,
        "_parse_from_qqofficial",
        staticmethod(lambda _message, _message_type: abm),
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
