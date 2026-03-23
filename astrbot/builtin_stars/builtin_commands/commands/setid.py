from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.core.platform.sources.qqofficial.workspace_registry import (
    QQOfficialWorkspaceRegistry,
    QQWorkspaceAliasError,
    resolve_workspace_identity_from_event,
)


class SetIDCommand:
    def __init__(self, context: star.Context) -> None:
        self.context = context
        self.registry = QQOfficialWorkspaceRegistry()

    async def setid(self, event: AstrMessageEvent, alias: str) -> None:
        workspace_identity = resolve_workspace_identity_from_event(event)
        if not workspace_identity:
            event.set_result(
                MessageEventResult().message("该命令仅支持 qq_official C2C 私聊使用。")
            )
            return

        appid = str(event.get_extra("qq_appid", "") or "")
        raw_user_id = event.get_sender_id()

        try:
            result = self.registry.register_alias(
                appid=appid,
                raw_user_id=raw_user_id,
                alias=alias,
            )
        except QQWorkspaceAliasError as exc:
            event.set_result(MessageEventResult().message(str(exc)))
            return

        lines = [
            "ID 已注册成功。",
            "宿主机目录已创建。",
        ]
        if result.workspace_ready:
            lines.append("正式 workspace 已就绪。")
        else:
            lines.append("正式 workspace 尚未绑定，后续解析成功后会自动建立。")
        event.set_result(MessageEventResult().message("\n".join(lines)))
