from types import SimpleNamespace
from unittest.mock import MagicMock

import botpy.errors
import pytest

from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata
from astrbot.core.platform.sources.qqofficial.qqofficial_message_event import (
    QQOfficialMessageEvent,
)


def _make_event() -> QQOfficialMessageEvent:
    abm = AstrBotMessage()
    abm.type = MessageType.FRIEND_MESSAGE
    abm.sender = MessageMember(user_id="user-1", nickname="tester")
    abm.message = []
    abm.message_str = "hello"
    abm.session_id = "session-1"
    abm.message_id = "msg-1"
    abm.raw_message = SimpleNamespace(id="msg-1")

    return QQOfficialMessageEvent(
        message_str="hello",
        message_obj=abm,
        platform_meta=PlatformMetadata(
            name="qq_official",
            description="QQ Official",
            id="test-qq",
        ),
        session_id="session-1",
        bot=MagicMock(),
    )


@pytest.mark.asyncio
async def test_send_with_markdown_fallback_retries_url_rejected_markdown_as_content():
    event = _make_event()
    plain_text = "目录在 `/home/ship/workspace`"
    payload = {
        "markdown": {"content": plain_text},
        "msg_type": 2,
        "msg_id": "msg-1",
    }
    sent_payloads: list[dict] = []

    async def fake_send(current_payload: dict):
        sent_payloads.append(current_payload.copy())
        if current_payload.get("markdown"):
            raise botpy.errors.ServerError("消息发送失败, 不允许发送url ")
        return {"id": "ret-1"}

    result = await event._send_with_markdown_fallback(
        send_func=fake_send,
        payload=payload,
        plain_text=plain_text,
    )

    assert result == {"id": "ret-1"}
    assert len(sent_payloads) == 2
    assert sent_payloads[1]["content"] == plain_text
    assert sent_payloads[1]["msg_type"] == 0
    assert "markdown" not in sent_payloads[1]
