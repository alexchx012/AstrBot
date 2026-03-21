from types import SimpleNamespace
from unittest.mock import MagicMock

from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.sources.qqofficial.qqofficial_platform_adapter import (
    QQOfficialPlatformAdapter,
)


def _make_adapter():
    return QQOfficialPlatformAdapter(
        platform_config={
            "id": "test-qq",
            "appid": "appid",
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
