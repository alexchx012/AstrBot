from pathlib import Path
from unittest.mock import MagicMock

import pytest

from astrbot.builtin_stars.builtin_commands.commands.setid import SetIDCommand


def _make_event(
    *,
    platform_name: str = "qq_official",
    message_source: str = "c2c",
    appid: str = "123456",
    user_id: str = "user-openid",
):
    stored = []

    def _set_result(result):
        stored.append(result)

    event = MagicMock()
    event.get_platform_name.return_value = platform_name
    event.get_sender_id.return_value = user_id
    event.get_extra.side_effect = lambda key, default=None: {
        "qq_message_source": message_source,
        "qq_appid": appid,
    }.get(key, default)
    event.set_result.side_effect = _set_result
    event._stored_results = stored
    return event


def _result_text(event) -> str:
    result = event._stored_results[-1]
    return "".join(getattr(component, "text", "") for component in result.chain)


@pytest.mark.asyncio
async def test_setid_rejects_non_c2c_scene(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    cmd = SetIDCommand(MagicMock())
    event = _make_event(message_source="direct_message")

    await cmd.setid(event, "abc123")

    assert "仅支持 qq_official C2C 私聊" in _result_text(event)


@pytest.mark.asyncio
async def test_setid_rejects_invalid_alias(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    cmd = SetIDCommand(MagicMock())
    event = _make_event()

    await cmd.setid(event, "AA")

    assert "3-10 位小写字母或数字" in _result_text(event)


@pytest.mark.asyncio
async def test_setid_registers_alias_and_reports_pending_workspace(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    cmd = SetIDCommand(MagicMock())
    event = _make_event()

    await cmd.setid(event, "abc123")

    text = _result_text(event)
    assert "ID 已注册成功" in text
    assert "宿主机目录已创建" in text
    assert "workspace 尚未绑定" in text


@pytest.mark.asyncio
async def test_setid_returns_conflict_message(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    cmd = SetIDCommand(MagicMock())

    first_event = _make_event(user_id="user-a")
    second_event = _make_event(user_id="user-b")

    await cmd.setid(first_event, "abc123")
    await cmd.setid(second_event, "abc123")

    assert _result_text(second_event) == "该 ID 已被占用，请换一个"
