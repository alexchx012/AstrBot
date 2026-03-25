from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from types import SimpleNamespace
from typing import Any, cast

import botpy
import botpy.message
from botpy import Client

from astrbot import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import At, File, Image, Plain, Record, Video
from astrbot.api.platform import (
    AstrBotMessage,
    MessageMember,
    MessageType,
    Platform,
    PlatformMetadata,
)
from astrbot.core.message.components import BaseMessageComponent
from astrbot.core.platform.astr_message_event import MessageSesion

from ...register import register_platform_adapter
from .qqofficial_message_event import QQOfficialMessageEvent
from .workspace_registry import QQOfficialWorkspaceRegistry

# remove logger handler
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


# QQ 机器人官方框架
class botClient(Client):
    def set_platform(self, platform: QQOfficialPlatformAdapter) -> None:
        self.platform = platform

    # 收到群消息
    async def on_group_at_message_create(
        self, message: botpy.message.GroupMessage
    ) -> None:
        abm = QQOfficialPlatformAdapter._parse_from_qqofficial(
            message,
            MessageType.GROUP_MESSAGE,
        )
        abm.group_id = cast(str, message.group_openid)
        abm.session_id = abm.group_id
        self.platform.remember_session_scene(abm.session_id, "group")
        self._commit(abm, message_source="group")

    # 收到频道消息
    async def on_at_message_create(self, message: botpy.message.Message) -> None:
        abm = QQOfficialPlatformAdapter._parse_from_qqofficial(
            message,
            MessageType.GROUP_MESSAGE,
        )
        abm.group_id = message.channel_id
        abm.session_id = abm.group_id
        self.platform.remember_session_scene(abm.session_id, "channel")
        self._commit(abm, message_source="channel")

    # 收到私聊消息
    async def on_direct_message_create(
        self, message: botpy.message.DirectMessage
    ) -> None:
        if self.platform.should_ignore_direct_message_event(message):
            return
        abm = QQOfficialPlatformAdapter._parse_from_qqofficial(
            message,
            MessageType.FRIEND_MESSAGE,
        )
        abm.session_id = abm.sender.user_id
        self.platform.remember_session_scene(abm.session_id, "friend")
        self._commit(abm, message_source="direct_message")

    # 收到 C2C 消息
    async def on_c2c_message_create(self, message: botpy.message.C2CMessage) -> None:
        abm = QQOfficialPlatformAdapter._parse_from_qqofficial(
            message,
            MessageType.FRIEND_MESSAGE,
        )
        abm.session_id = abm.sender.user_id
        self.platform.remember_session_scene(abm.session_id, "friend")
        prompt_sent = await self.platform.maybe_prompt_setid_for_c2c(abm)
        if prompt_sent:
            return
        self.platform.maybe_refresh_workspace_binding_for_c2c(abm)
        self._commit(abm, message_source="c2c")

    def _commit(self, abm: AstrBotMessage, message_source: str | None = None) -> None:
        if self.platform.should_skip_incoming_message(abm):
            return
        if self.platform.should_suppress_private_message_before_setid(
            abm, message_source
        ):
            return
        self.platform.remember_session_message_id(abm.session_id, abm.message_id)
        event = QQOfficialMessageEvent(
            abm.message_str,
            abm,
            self.platform.meta(),
            abm.session_id,
            self.platform.client,
        )
        event.set_extra("qq_appid", str(self.platform.appid))
        if message_source:
            event.set_extra("qq_message_source", message_source)
        self.platform.commit_event(event)


@register_platform_adapter("qq_official", "QQ 机器人官方 API 适配器")
class QQOfficialPlatformAdapter(Platform):
    def __init__(
        self,
        platform_config: dict,
        platform_settings: dict,
        event_queue: asyncio.Queue,
    ) -> None:
        super().__init__(platform_config, event_queue)

        self.appid = platform_config["appid"]
        self.secret = platform_config["secret"]
        qq_group = platform_config["enable_group_c2c"]
        guild_dm = platform_config["enable_guild_direct_message"]

        if qq_group:
            self.intents = botpy.Intents(
                public_messages=True,
                public_guild_messages=True,
                direct_message=guild_dm,
            )
        else:
            self.intents = botpy.Intents(
                public_guild_messages=True,
                direct_message=guild_dm,
            )
        self.client = botClient(
            intents=self.intents,
            bot_log=False,
            timeout=20,
        )

        self.client.set_platform(self)

        self._session_last_message_id: dict[str, str] = {}
        self._session_scene: dict[str, str] = {}
        self._seen_incoming_event_keys: dict[str, float] = {}
        self._incoming_event_dedup_ttl: int = 60
        self.workspace_registry = QQOfficialWorkspaceRegistry()

        self.test_mode = os.environ.get("TEST_MODE", "off") == "on"

    async def maybe_prompt_setid_for_c2c(self, abm: AstrBotMessage) -> bool:
        sender_id = getattr(getattr(abm, "sender", None), "user_id", "") or ""
        if not sender_id:
            return False

        text = (getattr(abm, "message_str", "") or "").strip().lower()
        if text == "/setid" or text.startswith("/setid "):
            return False

        should_prompt = self.workspace_registry.maybe_mark_prompted(
            appid=str(self.appid),
            raw_user_id=sender_id,
        )
        if not should_prompt:
            return False

        try:
            await QQOfficialMessageEvent.post_c2c_message(
                SimpleNamespace(bot=self.client),  # type: ignore[arg-type]
                openid=sender_id,
                content="首次使用该私聊工作区前，请先发送 /setid <3-10位小写字母或数字> 绑定你的专属 ID。",
                msg_id=abm.message_id,
                msg_seq=random.randint(1, 10000),
            )
            logger.info(
                "[QQOfficial] Outgoing onboarding prompt to %s: /setid required",
                sender_id,
            )
            return True
        except Exception as exc:
            self.workspace_registry.clear_prompted_state(
                appid=str(self.appid),
                raw_user_id=sender_id,
            )
            logger.warning("[QQOfficial] Failed to send /setid prompt: %s", exc)
            return False

    def maybe_refresh_workspace_binding_for_c2c(self, abm: AstrBotMessage) -> None:
        sender_id = getattr(getattr(abm, "sender", None), "user_id", "") or ""
        appid = str(self.appid)
        if not sender_id or not appid.isdigit():
            return
        workspace_identity = f"v1:{appid}:{sender_id}"
        try:
            self.workspace_registry.refresh_workspace_binding(
                workspace_identity,
                allow_fallback=False,
            )
        except Exception as exc:
            logger.warning(
                "[QQOfficial] Failed to refresh workspace binding for %s: %s",
                workspace_identity,
                exc,
            )

    async def send_by_session(
        self,
        session: MessageSesion,
        message_chain: MessageChain,
    ) -> None:
        await self._send_by_session_common(session, message_chain)

    async def _send_by_session_common(
        self,
        session: MessageSesion,
        message_chain: MessageChain,
    ) -> None:
        (
            plain_text,
            image_base64,
            image_path,
            record_file_path,
            video_file_source,
            file_source,
            file_name,
        ) = await QQOfficialMessageEvent._parse_to_qqofficial(message_chain)
        if (
            not plain_text
            and not image_path
            and not image_base64
            and not record_file_path
            and not video_file_source
            and not file_source
        ):
            return

        msg_id = self._session_last_message_id.get(session.session_id)
        if not msg_id:
            logger.warning(
                "[QQOfficial] No cached msg_id for session: %s, skip send_by_session",
                session.session_id,
            )
            return

        payload: dict[str, Any] = {"content": plain_text, "msg_id": msg_id}
        ret: Any = None
        send_helper = SimpleNamespace(bot=self.client)

        if session.message_type == MessageType.GROUP_MESSAGE:
            scene = self._session_scene.get(session.session_id)
            if scene == "group":
                payload["msg_seq"] = random.randint(1, 10000)
                if image_base64:
                    media = await QQOfficialMessageEvent.upload_group_and_c2c_image(
                        send_helper,  # type: ignore
                        image_base64,
                        QQOfficialMessageEvent.IMAGE_FILE_TYPE,
                        group_openid=session.session_id,
                    )
                    payload["media"] = media
                    payload["msg_type"] = 7
                if record_file_path:
                    media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                        send_helper,  # type: ignore
                        record_file_path,
                        QQOfficialMessageEvent.VOICE_FILE_TYPE,
                        group_openid=session.session_id,
                    )
                    if media:
                        payload["media"] = media
                        payload["msg_type"] = 7
                if video_file_source:
                    media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                        send_helper,  # type: ignore
                        video_file_source,
                        QQOfficialMessageEvent.VIDEO_FILE_TYPE,
                        group_openid=session.session_id,
                    )
                    if media:
                        payload["media"] = media
                        payload["msg_type"] = 7
                        payload.pop("msg_id", None)
                if file_source:
                    media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                        send_helper,  # type: ignore
                        file_source,
                        QQOfficialMessageEvent.FILE_FILE_TYPE,
                        file_name=file_name,
                        group_openid=session.session_id,
                    )
                    if media:
                        payload["media"] = media
                        payload["msg_type"] = 7
                        payload.pop("msg_id", None)
                ret = await self.client.api.post_group_message(
                    group_openid=session.session_id,
                    **payload,
                )
            else:
                if image_path:
                    payload["file_image"] = image_path
                ret = await self.client.api.post_message(
                    channel_id=session.session_id,
                    **payload,
                )

        elif session.message_type == MessageType.FRIEND_MESSAGE:
            # 参考 https://bot.q.qq.com/wiki/develop/pythonsdk/api/message/post_message.html
            # msg_id 缺失时认为是主动推送，而似乎至少在私聊上主动推送是没有被限制的，这里直接移除 msg_id 可以避免越权或 msg_id 不可用的bug
            payload.pop("msg_id", None)
            payload["msg_seq"] = random.randint(1, 10000)
            if image_base64:
                media = await QQOfficialMessageEvent.upload_group_and_c2c_image(
                    send_helper,  # type: ignore
                    image_base64,
                    QQOfficialMessageEvent.IMAGE_FILE_TYPE,
                    openid=session.session_id,
                )
                payload["media"] = media
                payload["msg_type"] = 7
            if record_file_path:
                media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                    send_helper,  # type: ignore
                    record_file_path,
                    QQOfficialMessageEvent.VOICE_FILE_TYPE,
                    openid=session.session_id,
                )
                if media:
                    payload["media"] = media
                    payload["msg_type"] = 7
            if video_file_source:
                media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                    send_helper,  # type: ignore
                    video_file_source,
                    QQOfficialMessageEvent.VIDEO_FILE_TYPE,
                    openid=session.session_id,
                )
                if media:
                    payload["media"] = media
                    payload["msg_type"] = 7
            if file_source:
                media = await QQOfficialMessageEvent.upload_group_and_c2c_media(
                    send_helper,  # type: ignore
                    file_source,
                    QQOfficialMessageEvent.FILE_FILE_TYPE,
                    file_name=file_name,
                    openid=session.session_id,
                )
                if media:
                    payload["media"] = media
                    payload["msg_type"] = 7

            ret = await QQOfficialMessageEvent.post_c2c_message(
                send_helper,  # type: ignore
                openid=session.session_id,
                **payload,
            )
        else:
            logger.warning(
                "[QQOfficial] Unsupported message type for send_by_session: %s",
                session.message_type,
            )
            return

        sent_message_id = self._extract_message_id(ret)
        outline = plain_text or file_name or image_path or "[non-text message]"
        logger.info(
            "[QQOfficial] Outgoing message to %s (%s): %s",
            session.session_id,
            session.message_type,
            outline,
        )
        if sent_message_id:
            self.remember_session_message_id(session.session_id, sent_message_id)
        await super().send_by_session(session, message_chain)

    def remember_session_message_id(self, session_id: str, message_id: str) -> None:
        if not session_id or not message_id:
            return
        self._session_last_message_id[session_id] = message_id

    def remember_session_scene(self, session_id: str, scene: str) -> None:
        if not session_id or not scene:
            return
        self._session_scene[session_id] = scene

    def should_ignore_direct_message_event(
        self, message: botpy.message.DirectMessage
    ) -> bool:
        has_guild_context = bool(
            getattr(message, "guild_id", None)
            or getattr(message, "src_guild_id", None)
            or getattr(message, "channel_id", None)
        )
        if has_guild_context:
            return False

        logger.info(
            "[QQOfficial] Ignoring direct_message event without guild context. id=%s event_id=%s",
            getattr(message, "id", None),
            getattr(message, "event_id", None),
        )
        return True

    def should_suppress_private_message_before_setid(
        self,
        abm: AstrBotMessage,
        message_source: str | None,
    ) -> bool:
        if message_source != "c2c":
            return False

        sender_id = getattr(getattr(abm, "sender", None), "user_id", "") or ""
        appid = str(self.appid)
        if not sender_id or not appid.isdigit():
            return False

        state = self.workspace_registry.get_alias_state(
            appid=appid,
            raw_user_id=sender_id,
        )
        if state != "prompted":
            return False

        text = (getattr(abm, "message_str", "") or "").strip().lower()
        if message_source == "c2c" and (text == "/setid" or text.startswith("/setid ")):
            return False

        logger.info(
            "[QQOfficial] Suppressing pre-setid private message. source=%s session_id=%s text=%r",
            message_source,
            getattr(abm, "session_id", None),
            getattr(abm, "message_str", None),
        )
        return True

    def should_skip_incoming_message(self, abm: AstrBotMessage) -> bool:
        raw_message = getattr(abm, "raw_message", None)
        event_id = getattr(raw_message, "event_id", None)
        message_id = getattr(raw_message, "id", None) or getattr(
            abm, "message_id", None
        )

        keys = []
        if event_id:
            keys.append(f"event:{event_id}")
        if message_id:
            keys.append(f"message:{message_id}")
        if not keys:
            return False

        now = time.monotonic()
        expired = [
            key
            for key, ts in self._seen_incoming_event_keys.items()
            if now - ts > self._incoming_event_dedup_ttl
        ]
        for key in expired:
            del self._seen_incoming_event_keys[key]

        if any(key in self._seen_incoming_event_keys for key in keys):
            logger.debug(
                "[QQOfficial] Duplicate incoming message skipped. event_id=%s message_id=%s session_id=%s",
                event_id,
                message_id,
                getattr(abm, "session_id", None),
            )
            return True

        for key in keys:
            self._seen_incoming_event_keys[key] = now
        return False

    def _extract_message_id(self, ret: Any) -> str | None:
        if isinstance(ret, dict):
            message_id = ret.get("id")
            return str(message_id) if message_id else None
        message_id = getattr(ret, "id", None)
        if message_id:
            return str(message_id)
        return None

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="qq_official",
            description="QQ 机器人官方 API 适配器",
            id=cast(str, self.config.get("id")),
            support_proactive_message=True,
        )

    @staticmethod
    def _normalize_attachment_url(url: str | None) -> str:
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"

    @staticmethod
    def _append_attachments(
        msg: list[BaseMessageComponent],
        attachments: list | None,
    ) -> None:
        if not attachments:
            return

        for attachment in attachments:
            content_type = cast(
                str,
                getattr(attachment, "content_type", "") or "",
            ).lower()
            url = QQOfficialPlatformAdapter._normalize_attachment_url(
                cast(str | None, getattr(attachment, "url", None))
            )
            if not url:
                continue

            if content_type.startswith("image"):
                msg.append(Image.fromURL(url))
            else:
                filename = cast(
                    str,
                    getattr(attachment, "filename", None)
                    or getattr(attachment, "name", None)
                    or "attachment",
                )
                ext = os.path.splitext(filename)[1].lower()
                image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
                audio_exts = {
                    ".mp3",
                    ".wav",
                    ".ogg",
                    ".m4a",
                    ".amr",
                    ".silk",
                }
                video_exts = {
                    ".mp4",
                    ".mov",
                    ".avi",
                    ".mkv",
                    ".webm",
                }

                if content_type.startswith("audio") or ext in audio_exts:
                    msg.append(Record.fromURL(url))
                elif content_type.startswith("video") or ext in video_exts:
                    msg.append(Video.fromURL(url))
                elif content_type.startswith("image") or ext in image_exts:
                    msg.append(Image.fromURL(url))
                else:
                    msg.append(File(name=filename, file=url, url=url))

    @staticmethod
    def _parse_face_message(content: str) -> str:
        """Parse QQ official face message format and convert to readable text.

        QQ official face message format:
        <faceType=4,faceId="",ext="eyJ0ZXh0IjoiW+a7oeWktOmXruWPt10ifQ==">

        The ext field contains base64-encoded JSON with a 'text' field
        describing the emoji (e.g., '[满头问号]').

        Args:
            content: The message content that may contain face tags.

        Returns:
            Content with face tags replaced by readable emoji descriptions.
        """
        import base64
        import json
        import re

        def replace_face(match):
            face_tag = match.group(0)
            # Extract ext field from the face tag
            ext_match = re.search(r'ext="([^"]*)"', face_tag)
            if ext_match:
                try:
                    ext_encoded = ext_match.group(1)
                    # Decode base64 and parse JSON
                    ext_decoded = base64.b64decode(ext_encoded).decode("utf-8")
                    ext_data = json.loads(ext_decoded)
                    emoji_text = ext_data.get("text", "")
                    if emoji_text:
                        return f"[表情:{emoji_text}]"
                except Exception:
                    pass
            # Fallback if parsing fails
            return "[表情]"

        # Match face tags: <faceType=...>
        return re.sub(r"<faceType=\d+[^>]*>", replace_face, content)

    @staticmethod
    def _parse_from_qqofficial(
        message: botpy.message.Message
        | botpy.message.GroupMessage
        | botpy.message.DirectMessage
        | botpy.message.C2CMessage,
        message_type: MessageType,
    ):
        abm = AstrBotMessage()
        abm.type = message_type
        abm.timestamp = int(time.time())
        abm.raw_message = message
        abm.message_id = message.id
        # abm.tag = "qq_official"
        msg: list[BaseMessageComponent] = []

        if isinstance(message, botpy.message.GroupMessage) or isinstance(
            message,
            botpy.message.C2CMessage,
        ):
            if isinstance(message, botpy.message.GroupMessage):
                abm.sender = MessageMember(message.author.member_openid, "")
                abm.group_id = message.group_openid
            else:
                abm.sender = MessageMember(message.author.user_openid, "")
            # Parse face messages to readable text
            abm.message_str = QQOfficialPlatformAdapter._parse_face_message(
                message.content.strip()
            )
            abm.self_id = "unknown_selfid"
            msg.append(At(qq="qq_official"))
            msg.append(Plain(abm.message_str))
            QQOfficialPlatformAdapter._append_attachments(msg, message.attachments)
            abm.message = msg

        elif isinstance(message, botpy.message.Message) or isinstance(
            message,
            botpy.message.DirectMessage,
        ):
            if isinstance(message, botpy.message.Message):
                abm.self_id = str(message.mentions[0].id)
            else:
                abm.self_id = ""

            plain_content = QQOfficialPlatformAdapter._parse_face_message(
                message.content.replace(
                    "<@!" + str(abm.self_id) + ">",
                    "",
                ).strip()
            )

            QQOfficialPlatformAdapter._append_attachments(msg, message.attachments)
            abm.message = msg
            abm.message_str = plain_content
            abm.sender = MessageMember(
                str(message.author.id),
                str(message.author.username),
            )
            msg.append(At(qq="qq_official"))
            msg.append(Plain(plain_content))

            if isinstance(message, botpy.message.Message):
                abm.group_id = message.channel_id
        else:
            raise ValueError(f"Unknown message type: {message_type}")
        abm.self_id = "qq_official"
        return abm

    def run(self):
        return self.client.start(appid=self.appid, secret=self.secret)

    def get_client(self) -> botClient:
        return self.client

    async def terminate(self) -> None:
        await self.client.close()
        logger.info("QQ 官方机器人接口 适配器已被优雅地关闭")
