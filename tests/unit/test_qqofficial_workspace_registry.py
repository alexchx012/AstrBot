import json
import os
import sqlite3
import stat
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from astrbot.core.platform.sources.qqofficial.workspace_registry import (
    QQOfficialWorkspaceRegistry,
    QQWorkspaceAliasError,
    resolve_workspace_identity_from_event,
)


def _make_event(
    *,
    platform_name: str = "qq_official",
    message_source: str = "c2c",
    appid: str = "123456",
    user_id: str = "user-openid",
):
    event = MagicMock()
    event.get_platform_name.return_value = platform_name
    event.get_sender_id.return_value = user_id
    event.get_extra.side_effect = lambda key, default=None: {
        "qq_message_source": message_source,
        "qq_appid": appid,
    }.get(key, default)
    return event


def _manifest_path(root: Path) -> Path:
    return root / "data" / "qq_workspaces" / "manifest.json"


def _bay_db_path(root: Path) -> Path:
    return root / "data" / "shipyard" / "bay_data" / "bay.db"


def _ship_root(root: Path, ship_id: str) -> Path:
    return root / "data" / "shipyard" / "ship_mnt_data" / ship_id


def _create_bay_db(
    root: Path, session_id: str, ship_id: str, *, status: int = 1
) -> None:
    bay_db = _bay_db_path(root)
    bay_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(bay_db)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE ships (
            id TEXT PRIMARY KEY,
            status INTEGER NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            container_id TEXT,
            ip_address TEXT,
            ttl INTEGER NOT NULL,
            max_session_num INTEGER NOT NULL,
            current_session_num INTEGER NOT NULL,
            expires_at TEXT
        );
        CREATE TABLE session_ships (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            ship_id TEXT NOT NULL,
            created_at TEXT,
            last_activity TEXT,
            expires_at TEXT,
            initial_ttl INTEGER NOT NULL
        );
        """
    )
    cur.execute(
        """
        INSERT INTO ships (id, status, created_at, updated_at, container_id, ip_address, ttl, max_session_num, current_session_num, expires_at)
        VALUES (?, ?, '2026-03-23T00:00:00+00:00', '2026-03-23T00:01:00+00:00', 'container-1', '172.18.0.10', 3600, 10, 1, '2026-03-23T01:01:00+00:00')
        """,
        (ship_id, status),
    )
    cur.execute(
        """
        INSERT INTO session_ships (id, session_id, ship_id, created_at, last_activity, expires_at, initial_ttl)
        VALUES ('session-link-1', ?, ?, '2026-03-23T00:00:00+00:00', '2026-03-23T00:01:00+00:00', '2026-03-23T01:01:00+00:00', 3600)
        """,
        (session_id, ship_id),
    )
    conn.commit()
    conn.close()


def _create_ship_workspace(
    root: Path, ship_id: str, session_id: str, ship_user: str
) -> Path:
    ship_root = _ship_root(root, ship_id)
    workspace_dir = ship_root / "home" / ship_user / "workspace"
    metadata_dir = ship_root / "metadata"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "session_users.json").write_text(
        json.dumps({session_id: ship_user}),
        encoding="utf-8",
    )
    (metadata_dir / "users_info.json").write_text(
        json.dumps({ship_user: {"home": f"/home/{ship_user}"}}),
        encoding="utf-8",
    )
    return workspace_dir


def test_resolve_workspace_identity_for_qq_official_c2c():
    event = _make_event()

    assert resolve_workspace_identity_from_event(event) == "v1:123456:user-openid"


def test_resolve_workspace_identity_skips_non_target_scene():
    direct_message_event = _make_event(message_source="direct_message")
    wrong_platform_event = _make_event(platform_name="telegram")
    invalid_appid_event = _make_event(appid="app-123")

    assert resolve_workspace_identity_from_event(direct_message_event) is None
    assert resolve_workspace_identity_from_event(wrong_platform_event) is None
    assert resolve_workspace_identity_from_event(invalid_appid_event) is None


def test_maybe_mark_prompted_only_once(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()

    assert (
        registry.maybe_mark_prompted(appid="123456", raw_user_id="user-openid") is True
    )
    assert (
        registry.maybe_mark_prompted(appid="123456", raw_user_id="user-openid") is False
    )

    manifest = json.loads(_manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert manifest["alias_states"]["v1:123456:user-openid"] == "prompted"


def test_register_alias_creates_manifest_and_workspace_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()

    result = registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    alias_dir = tmp_path / "data" / "qq_workspaces" / "123456" / "abc123"
    manifest = json.loads(_manifest_path(tmp_path).read_text(encoding="utf-8"))

    assert result.alias == "abc123"
    assert result.idempotent is False
    assert alias_dir.is_dir()
    assert (alias_dir / "README.md").is_file()
    assert (
        manifest["aliases"]["abc123"]["workspace_identity"] == "v1:123456:user-openid"
    )
    assert manifest["workspaces"]["v1:123456:user-openid"]["status"] == "pending"
    assert (
        manifest["workspaces"]["v1:123456:user-openid"]["reason"]
        == "pending_first_resolution"
    )
    assert manifest["alias_states"]["v1:123456:user-openid"] == "registered"


def test_register_alias_rejects_invalid_alias(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()

    with pytest.raises(QQWorkspaceAliasError):
        registry.register_alias(
            appid="123456",
            raw_user_id="user-openid",
            alias="AA",
        )


def test_register_alias_rejects_global_conflict(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()

    registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    with pytest.raises(QQWorkspaceAliasError, match="该 ID 已被占用，请换一个"):
        registry.register_alias(
            appid="654321",
            raw_user_id="another-user",
            alias="abc123",
        )


def test_register_alias_is_idempotent_for_same_user(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()

    first = registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )
    readme_path = (
        tmp_path / "data" / "qq_workspaces" / "123456" / "abc123" / "README.md"
    )
    readme_path.unlink()

    second = registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    assert first.idempotent is False
    assert second.idempotent is True
    assert readme_path.is_file()


def test_refresh_workspace_binding_resolves_from_bay_db(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()
    registration = registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )
    assert registration.workspace_ready is False

    workspace_identity = "v1:123456:user-openid"
    session_id = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex
    ship_id = "ship-001"
    workspace_dir = _create_ship_workspace(tmp_path, ship_id, session_id, "ship_user_1")
    _create_bay_db(tmp_path, session_id, ship_id)

    result = registry.refresh_workspace_binding(
        workspace_identity,
        allow_fallback=True,
    )

    alias_dir = tmp_path / "data" / "qq_workspaces" / "123456" / "abc123"
    workspace_link = alias_dir / "workspace"
    manifest = json.loads(_manifest_path(tmp_path).read_text(encoding="utf-8"))

    assert result.status == "resolved"
    assert workspace_link.is_symlink()
    assert not workspace_link.readlink().is_absolute()
    assert workspace_link.resolve() == workspace_dir.resolve()
    assert (
        manifest["workspaces"][workspace_identity]["ship_mnt_data_relpath"]
        == "ship-001"
    )
    assert manifest["workspaces"][workspace_identity]["status"] == "resolved"
    assert manifest["workspaces"][workspace_identity]["reason"] == "resolved_current"


def test_refresh_workspace_binding_normalizes_workspace_permissions(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()
    registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    workspace_identity = "v1:123456:user-openid"
    session_id = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex
    ship_id = "ship-001"
    workspace_dir = _create_ship_workspace(tmp_path, ship_id, session_id, "ship_user_1")
    nested_file = workspace_dir / "created-by-sandbox.txt"
    nested_file.write_text("hello\n", encoding="utf-8")
    os.chmod(workspace_dir, 0o755)
    os.chmod(nested_file, 0o644)
    _create_bay_db(tmp_path, session_id, ship_id)

    registry.refresh_workspace_binding(
        workspace_identity,
        allow_fallback=True,
    )

    workspace_mode = stat.S_IMODE(workspace_dir.stat().st_mode)
    nested_file_mode = stat.S_IMODE(nested_file.stat().st_mode)

    assert workspace_mode & stat.S_IWGRP
    assert workspace_mode & stat.S_IXGRP
    assert workspace_mode & stat.S_ISGID
    assert nested_file_mode & stat.S_IWGRP


def test_refresh_workspace_binding_normalizes_workspace_permissions_for_other_users(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()
    registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    workspace_identity = "v1:123456:user-openid"
    session_id = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex
    ship_id = "ship-001"
    workspace_dir = _create_ship_workspace(tmp_path, ship_id, session_id, "ship_user_1")
    nested_file = workspace_dir / "created-by-sandbox.txt"
    nested_file.write_text("hello\n", encoding="utf-8")
    os.chmod(workspace_dir, 0o755)
    os.chmod(nested_file, 0o644)
    _create_bay_db(tmp_path, session_id, ship_id)

    registry.refresh_workspace_binding(
        workspace_identity,
        allow_fallback=True,
    )

    workspace_mode = stat.S_IMODE(workspace_dir.stat().st_mode)
    nested_file_mode = stat.S_IMODE(nested_file.stat().st_mode)

    assert workspace_mode & stat.S_IWOTH
    assert workspace_mode & stat.S_IXOTH
    assert nested_file_mode & stat.S_IWOTH


def test_refresh_workspace_binding_uses_unique_fallback_when_bay_unavailable(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()
    registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    workspace_identity = "v1:123456:user-openid"
    session_id = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex
    workspace_dir = _create_ship_workspace(
        tmp_path, "ship-fallback-1", session_id, "ship_user_1"
    )

    result = registry.refresh_workspace_binding(
        workspace_identity,
        allow_fallback=True,
    )

    alias_dir = tmp_path / "data" / "qq_workspaces" / "123456" / "abc123"
    assert result.status == "resolved"
    assert (alias_dir / "workspace").resolve() == workspace_dir.resolve()


def test_refresh_workspace_binding_keeps_last_known_good_when_resolution_regresses(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    registry = QQOfficialWorkspaceRegistry()
    registry.register_alias(
        appid="123456",
        raw_user_id="user-openid",
        alias="abc123",
    )

    workspace_identity = "v1:123456:user-openid"
    session_id = uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex
    ship_id = "ship-001"
    workspace_dir = _create_ship_workspace(tmp_path, ship_id, session_id, "ship_user_1")
    _create_bay_db(tmp_path, session_id, ship_id)

    first = registry.refresh_workspace_binding(workspace_identity, allow_fallback=True)
    assert first.status == "resolved"
    workspace_dir.rmdir()

    second = registry.refresh_workspace_binding(workspace_identity, allow_fallback=True)

    alias_dir = tmp_path / "data" / "qq_workspaces" / "123456" / "abc123"
    manifest = json.loads(_manifest_path(tmp_path).read_text(encoding="utf-8"))

    assert second.status == "unresolved"
    assert not (alias_dir / "workspace").exists()
    assert (alias_dir / "workspace.last_known_good").is_symlink()
    assert manifest["workspaces"][workspace_identity]["status"] == "unresolved"
    assert manifest["workspaces"][workspace_identity]["reason"] == "workspace_missing"
