from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ALIAS_RE = re.compile(r"^[a-z0-9]{3,10}$")
WORKSPACE_VERSION = 1


@dataclass
class AliasRegistrationResult:
    alias: str
    idempotent: bool = False
    workspace_ready: bool = False


@dataclass
class WorkspaceBindingResult:
    status: str
    reason: str
    workspace_path: Path | None = None
    ship_id: str = ""
    ship_mnt_data_relpath: str = ""
    last_known_good_relpath: str = ""


class QQWorkspaceAliasError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _build_workspace_identity(appid: str, raw_user_id: str) -> str:
    return f"v1:{appid}:{raw_user_id}"


def _build_shipyard_session_key(workspace_identity: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, workspace_identity).hex


def resolve_workspace_identity_from_event(event) -> str | None:
    get_platform_name = getattr(event, "get_platform_name", None)
    get_extra = getattr(event, "get_extra", None)
    get_sender_id = getattr(event, "get_sender_id", None)
    if (
        not callable(get_platform_name)
        or not callable(get_extra)
        or not callable(get_sender_id)
    ):
        return None

    if get_platform_name() != "qq_official":
        return None

    if get_extra("qq_message_source") != "c2c":
        return None

    appid = str(get_extra("qq_appid", "") or "").strip()
    if not appid.isdigit():
        return None

    raw_user_id = str(get_sender_id() or "").strip()
    if not raw_user_id:
        return None

    return _build_workspace_identity(appid, raw_user_id)


class QQOfficialWorkspaceRegistry:
    _binding_locks: dict[str, threading.Lock] = {}
    _binding_locks_guard = threading.Lock()

    def _data_root(self) -> Path:
        return Path(get_astrbot_data_path())

    def _workspace_root(self) -> Path:
        return self._data_root() / "qq_workspaces"

    def _manifest_path(self) -> Path:
        return self._workspace_root() / "manifest.json"

    def _lock_path(self) -> Path:
        return self._workspace_root() / ".manifest.lock"

    def _default_manifest(self) -> dict:
        return {
            "version": WORKSPACE_VERSION,
            "updated_at": _utc_now(),
            "aliases": {},
            "workspaces": {},
            "alias_states": {},
        }

    def _ensure_numeric_appid(self, appid: str) -> str:
        normalized = appid.strip()
        if not normalized.isdigit():
            raise QQWorkspaceAliasError(
                "appid must be numeric for qq_official C2C workspace identity."
            )
        return normalized

    def _ensure_valid_alias(self, alias: str) -> str:
        normalized = alias.strip()
        if not ALIAS_RE.fullmatch(normalized):
            raise QQWorkspaceAliasError("ID 只能使用 3-10 位小写字母或数字。")
        return normalized

    def _normalize_manifest(self, manifest: dict | None) -> dict:
        data = self._default_manifest()
        if isinstance(manifest, dict):
            data.update(manifest)
        for key in ("aliases", "workspaces", "alias_states"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        data["version"] = WORKSPACE_VERSION
        if not isinstance(data.get("updated_at"), str):
            data["updated_at"] = _utc_now()
        return data

    def _read_manifest_unlocked(self) -> dict:
        manifest_path = self._manifest_path()
        if not manifest_path.is_file():
            return self._default_manifest()
        try:
            return self._normalize_manifest(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            return self._default_manifest()

    def _write_manifest_unlocked(self, manifest: dict) -> None:
        root = self._workspace_root()
        root.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path()
        temp_path = manifest_path.with_suffix(".tmp")
        payload = json.dumps(manifest, ensure_ascii=False, indent=2)
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(manifest_path)

    def _with_manifest_lock(self, callback):
        root = self._workspace_root()
        root.mkdir(parents=True, exist_ok=True)
        lock_path = self._lock_path()
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                manifest = self._read_manifest_unlocked()
                result = callback(manifest)
                manifest["updated_at"] = _utc_now()
                self._write_manifest_unlocked(manifest)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _find_alias_for_identity(
        self, manifest: dict, workspace_identity: str
    ) -> str | None:
        aliases = manifest.get("aliases", {})
        for alias, entry in aliases.items():
            if (
                isinstance(entry, dict)
                and entry.get("workspace_identity") == workspace_identity
            ):
                return alias
        return None

    def _get_binding_lock(self, workspace_identity: str) -> threading.Lock:
        with self._binding_locks_guard:
            return self._binding_locks.setdefault(workspace_identity, threading.Lock())

    def _alias_dir(self, appid: str, alias: str) -> Path:
        return self._workspace_root() / appid / alias

    def _relative_alias_path(self, appid: str, alias: str) -> str:
        return os.fspath(Path("qq_workspaces") / appid / alias)

    def _ensure_alias_directory(self, appid: str, alias: str) -> Path:
        alias_dir = self._alias_dir(appid, alias)
        alias_dir.mkdir(parents=True, exist_ok=True)
        return alias_dir

    def _ensure_alias_readme(self, appid: str, alias: str) -> None:
        alias_dir = self._ensure_alias_directory(appid, alias)
        readme_path = alias_dir / "README.md"
        if readme_path.is_file():
            return
        readme_path.write_text(
            (
                "# QQ Workspace Alias\n\n"
                f"- AppID: `{appid}`\n"
                f"- Alias: `{alias}`\n"
                "- This directory is a stable host-side entry for a qq_official C2C user.\n"
                "- The source of truth is `data/qq_workspaces/manifest.json`.\n"
                "- If `workspace` is not present yet, the alias is registered but the current sandbox root has not been bound.\n"
            ),
            encoding="utf-8",
        )

    def _shipyard_root(self) -> Path:
        return self._data_root() / "shipyard"

    def _bay_db_path(self) -> Path:
        return self._shipyard_root() / "bay_data" / "bay.db"

    def _ship_mnt_root(self) -> Path:
        return self._shipyard_root() / "ship_mnt_data"

    def _load_json_file(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _collect_session_users(self, payload, session_id: str) -> set[str]:
        matches: set[str] = set()

        def _walk(node) -> None:
            if isinstance(node, dict):
                direct = node.get(session_id)
                if isinstance(direct, str) and direct.strip():
                    matches.add(direct.strip())
                elif isinstance(direct, dict):
                    for key in ("ship_user", "username", "user", "name"):
                        value = direct.get(key)
                        if isinstance(value, str) and value.strip():
                            matches.add(value.strip())

                if node.get("session_id") == session_id:
                    for key in ("ship_user", "username", "user", "name"):
                        value = node.get(key)
                        if isinstance(value, str) and value.strip():
                            matches.add(value.strip())

                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(payload)
        return matches

    def _users_info_has_user(self, payload, ship_user: str) -> bool:
        if isinstance(payload, dict):
            if ship_user in payload:
                return True
            for key in ("ship_user", "username", "user", "name"):
                if payload.get(key) == ship_user:
                    return True
            return any(
                self._users_info_has_user(value, ship_user)
                for value in payload.values()
            )
        if isinstance(payload, list):
            return any(self._users_info_has_user(item, ship_user) for item in payload)
        return False

    def _resolve_workspace_from_selected_ship(
        self,
        ship_id: str,
        shipyard_session_key: str,
    ) -> WorkspaceBindingResult | None:
        ship_root = self._ship_mnt_root() / ship_id
        if not ship_root.is_dir():
            return None

        metadata_dir = ship_root / "metadata"
        home_dir = ship_root / "home"

        session_users = self._load_json_file(metadata_dir / "session_users.json")
        users_info = self._load_json_file(metadata_dir / "users_info.json")
        candidate_users = self._collect_session_users(
            session_users, shipyard_session_key
        )

        for ship_user in sorted(candidate_users):
            if users_info is not None and not self._users_info_has_user(
                users_info, ship_user
            ):
                continue
            workspace_path = home_dir / ship_user / "workspace"
            if workspace_path.is_dir():
                relpath = os.fspath(Path(ship_id) / "home" / ship_user / "workspace")
                return WorkspaceBindingResult(
                    status="resolved",
                    reason="resolved_current",
                    workspace_path=workspace_path,
                    ship_id=ship_id,
                    ship_mnt_data_relpath=ship_id,
                    last_known_good_relpath=relpath,
                )

        candidates = sorted(
            path for path in home_dir.glob("*/workspace") if path.is_dir()
        )
        if len(candidates) == 1:
            workspace_path = candidates[0]
            relpath = os.fspath(
                Path(ship_id) / "home" / workspace_path.parent.name / "workspace"
            )
            return WorkspaceBindingResult(
                status="resolved",
                reason="resolved_current",
                workspace_path=workspace_path,
                ship_id=ship_id,
                ship_mnt_data_relpath=ship_id,
                last_known_good_relpath=relpath,
            )

        return None

    def _resolve_workspace_from_fallback(
        self,
        shipyard_session_key: str,
    ) -> WorkspaceBindingResult:
        ship_mnt_root = self._ship_mnt_root()
        candidates: list[WorkspaceBindingResult] = []
        if not ship_mnt_root.is_dir():
            return WorkspaceBindingResult(status="unresolved", reason="bay_unavailable")

        for ship_root in sorted(
            path for path in ship_mnt_root.iterdir() if path.is_dir()
        ):
            metadata_dir = ship_root / "metadata"
            home_dir = ship_root / "home"
            session_users = self._load_json_file(metadata_dir / "session_users.json")
            users_info = self._load_json_file(metadata_dir / "users_info.json")
            if session_users is None or users_info is None:
                continue

            candidate_users = self._collect_session_users(
                session_users, shipyard_session_key
            )
            if len(candidate_users) != 1:
                continue

            ship_user = next(iter(candidate_users))
            if not self._users_info_has_user(users_info, ship_user):
                continue

            workspace_path = home_dir / ship_user / "workspace"
            if not workspace_path.is_dir():
                continue

            relpath = os.fspath(Path(ship_root.name) / "home" / ship_user / "workspace")
            candidates.append(
                WorkspaceBindingResult(
                    status="resolved",
                    reason="resolved_current",
                    workspace_path=workspace_path,
                    ship_id=ship_root.name,
                    ship_mnt_data_relpath=ship_root.name,
                    last_known_good_relpath=relpath,
                )
            )

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            return WorkspaceBindingResult(
                status="unresolved", reason="fallback_ambiguous"
            )
        return WorkspaceBindingResult(status="unresolved", reason="bay_unavailable")

    def _select_ship_id_from_bay_db(self, shipyard_session_key: str) -> str | None:
        bay_db_path = self._bay_db_path()
        if not bay_db_path.is_file():
            return None
        query = """
        SELECT ships.id
        FROM ships
        JOIN session_ships ON ships.id = session_ships.ship_id
        WHERE session_ships.session_id = ?
        ORDER BY
            CASE ships.status
                WHEN 1 THEN 0
                WHEN 0 THEN 1
                ELSE 2
            END,
            ships.updated_at DESC,
            session_ships.last_activity DESC
        LIMIT 1
        """
        conn = sqlite3.connect(bay_db_path)
        try:
            row = conn.execute(query, (shipyard_session_key,)).fetchone()
            return str(row[0]) if row else None
        finally:
            conn.close()

    def _set_relative_symlink(self, link_path: Path, target_path: Path) -> None:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        relative_target = os.path.relpath(target_path, link_path.parent)
        link_path.symlink_to(relative_target)

    def _group_shared_mode(self, mode: int, *, is_dir: bool) -> int:
        shared_mode = mode
        if mode & stat.S_IRUSR:
            shared_mode |= stat.S_IRGRP
            shared_mode |= stat.S_IROTH
        if mode & stat.S_IWUSR:
            shared_mode |= stat.S_IWGRP
            shared_mode |= stat.S_IWOTH
        if mode & stat.S_IXUSR:
            shared_mode |= stat.S_IXGRP
            shared_mode |= stat.S_IXOTH
        if is_dir:
            shared_mode |= stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_ISGID
        return shared_mode

    def _normalize_mode(self, path: Path, *, is_dir: bool) -> None:
        try:
            current_mode = stat.S_IMODE(path.stat().st_mode)
            target_mode = self._group_shared_mode(current_mode, is_dir=is_dir)
            if current_mode != target_mode:
                path.chmod(target_mode)
        except OSError:
            return

    def _normalize_workspace_permissions(self, workspace_path: Path) -> None:
        if not workspace_path.is_dir():
            return

        for root, dirnames, filenames in os.walk(workspace_path):
            root_path = Path(root)
            self._normalize_mode(root_path, is_dir=True)

            for dirname in dirnames:
                dir_path = root_path / dirname
                if dir_path.is_symlink():
                    continue
                self._normalize_mode(dir_path, is_dir=True)

            for filename in filenames:
                file_path = root_path / filename
                if file_path.is_symlink():
                    continue
                self._normalize_mode(file_path, is_dir=False)

    def _sync_workspace_links(
        self,
        *,
        alias_dir: Path,
        workspace_path: Path | None,
        last_known_good_relpath: str,
    ) -> None:
        workspace_link = alias_dir / "workspace"
        last_known_good_link = alias_dir / "workspace.last_known_good"

        if workspace_path is not None:
            self._set_relative_symlink(workspace_link, workspace_path)
            self._set_relative_symlink(last_known_good_link, workspace_path)
            return

        if workspace_link.exists() or workspace_link.is_symlink():
            workspace_link.unlink()

        if last_known_good_relpath:
            target_path = self._ship_mnt_root() / last_known_good_relpath
            if target_path.exists():
                self._set_relative_symlink(last_known_good_link, target_path)

    def refresh_workspace_binding(
        self,
        workspace_identity: str,
        *,
        allow_fallback: bool,
        mark_unresolved_on_failure: bool = True,
    ) -> WorkspaceBindingResult:
        binding_lock = self._get_binding_lock(workspace_identity)
        with binding_lock:

            def _update(manifest: dict) -> WorkspaceBindingResult:
                workspace_entry = manifest["workspaces"].get(workspace_identity)
                if not isinstance(workspace_entry, dict):
                    return WorkspaceBindingResult(
                        status="pending",
                        reason="pending_first_resolution",
                    )

                alias = str(workspace_entry.get("alias", "") or "")
                appid = str(workspace_entry.get("appid", "") or "")
                current_status = str(
                    workspace_entry.get("status", "pending") or "pending"
                )
                shipyard_session_key = str(
                    workspace_entry.get("shipyard_session_key")
                    or _build_shipyard_session_key(workspace_identity)
                )
                workspace_entry["shipyard_session_key"] = shipyard_session_key

                selected_ship_id = self._select_ship_id_from_bay_db(
                    shipyard_session_key
                )
                result: WorkspaceBindingResult | None = None
                if selected_ship_id:
                    result = self._resolve_workspace_from_selected_ship(
                        selected_ship_id,
                        shipyard_session_key,
                    )
                    if result is None:
                        result = WorkspaceBindingResult(
                            status="unresolved",
                            reason="workspace_missing",
                            ship_id=selected_ship_id,
                            ship_mnt_data_relpath=selected_ship_id,
                        )
                elif allow_fallback:
                    result = self._resolve_workspace_from_fallback(shipyard_session_key)

                if result is None:
                    result = WorkspaceBindingResult(
                        status="pending",
                        reason="pending_first_resolution",
                    )

                alias_dir = self._alias_dir(appid, alias) if alias and appid else None
                previous_last_known_good = str(
                    workspace_entry.get("last_known_good_relpath", "") or ""
                )

                if result.status == "resolved" and result.workspace_path is not None:
                    self._normalize_workspace_permissions(result.workspace_path)
                    workspace_entry["ship_id"] = result.ship_id
                    workspace_entry["ship_mnt_data_relpath"] = (
                        result.ship_mnt_data_relpath
                    )
                    workspace_entry["last_known_good_relpath"] = (
                        result.last_known_good_relpath
                    )
                    workspace_entry["status"] = "resolved"
                    workspace_entry["reason"] = "resolved_current"
                    workspace_entry["updated_at"] = _utc_now()
                    if alias_dir is not None:
                        self._ensure_alias_readme(appid, alias)
                        self._sync_workspace_links(
                            alias_dir=alias_dir,
                            workspace_path=result.workspace_path,
                            last_known_good_relpath=result.last_known_good_relpath,
                        )
                    return result

                if not mark_unresolved_on_failure and current_status == "pending":
                    workspace_entry["status"] = "pending"
                    workspace_entry["reason"] = "pending_first_resolution"
                    workspace_entry["updated_at"] = _utc_now()
                    return WorkspaceBindingResult(
                        status="pending",
                        reason="pending_first_resolution",
                    )

                workspace_entry["status"] = "unresolved"
                workspace_entry["reason"] = result.reason
                workspace_entry["updated_at"] = _utc_now()
                if result.ship_id:
                    workspace_entry["ship_id"] = result.ship_id
                if result.ship_mnt_data_relpath:
                    workspace_entry["ship_mnt_data_relpath"] = (
                        result.ship_mnt_data_relpath
                    )
                if previous_last_known_good:
                    workspace_entry["last_known_good_relpath"] = (
                        previous_last_known_good
                    )
                if alias_dir is not None:
                    self._ensure_alias_readme(appid, alias)
                    self._sync_workspace_links(
                        alias_dir=alias_dir,
                        workspace_path=None,
                        last_known_good_relpath=str(
                            workspace_entry.get("last_known_good_relpath", "") or ""
                        ),
                    )
                result.last_known_good_relpath = str(
                    workspace_entry.get("last_known_good_relpath", "") or ""
                )
                return result

            return self._with_manifest_lock(_update)

    def maybe_mark_prompted(self, appid: str, raw_user_id: str) -> bool:
        appid = self._ensure_numeric_appid(appid)
        raw_user_id = raw_user_id.strip()
        workspace_identity = _build_workspace_identity(appid, raw_user_id)

        def _update(manifest: dict) -> bool:
            existing_alias = self._find_alias_for_identity(manifest, workspace_identity)
            if existing_alias:
                manifest["alias_states"][workspace_identity] = "registered"
                return False

            current_state = manifest["alias_states"].get(workspace_identity)
            if current_state in {"prompted", "registered"}:
                return False

            manifest["alias_states"][workspace_identity] = "prompted"
            return True

        return self._with_manifest_lock(_update)

    def get_alias_state(self, *, appid: str, raw_user_id: str) -> str | None:
        appid = self._ensure_numeric_appid(appid)
        raw_user_id = raw_user_id.strip()
        workspace_identity = _build_workspace_identity(appid, raw_user_id)
        manifest = self._read_manifest_unlocked()
        state = manifest["alias_states"].get(workspace_identity)
        if not isinstance(state, str) or not state:
            return None
        return state

    def clear_prompted_state(self, *, appid: str, raw_user_id: str) -> bool:
        appid = self._ensure_numeric_appid(appid)
        raw_user_id = raw_user_id.strip()
        workspace_identity = _build_workspace_identity(appid, raw_user_id)

        def _update(manifest: dict) -> bool:
            existing_alias = self._find_alias_for_identity(manifest, workspace_identity)
            if existing_alias:
                manifest["alias_states"][workspace_identity] = "registered"
                return False

            current_state = manifest["alias_states"].get(workspace_identity)
            if current_state != "prompted":
                return False

            manifest["alias_states"].pop(workspace_identity, None)
            return True

        return self._with_manifest_lock(_update)

    def register_alias(
        self,
        *,
        appid: str,
        raw_user_id: str,
        alias: str,
    ) -> AliasRegistrationResult:
        appid = self._ensure_numeric_appid(appid)
        raw_user_id = raw_user_id.strip()
        alias = self._ensure_valid_alias(alias)
        workspace_identity = _build_workspace_identity(appid, raw_user_id)
        shipyard_session_key = _build_shipyard_session_key(workspace_identity)

        def _update(manifest: dict) -> AliasRegistrationResult:
            aliases = manifest["aliases"]
            workspaces = manifest["workspaces"]
            alias_states = manifest["alias_states"]

            existing_alias = self._find_alias_for_identity(manifest, workspace_identity)
            alias_entry = aliases.get(alias)
            is_idempotent = False

            if isinstance(alias_entry, dict):
                if alias_entry.get("workspace_identity") != workspace_identity:
                    raise QQWorkspaceAliasError("该 ID 已被占用，请换一个")
                is_idempotent = True
            elif existing_alias and existing_alias != alias:
                raise QQWorkspaceAliasError("你已经绑定过 ID，暂不支持修改。")

            aliases[alias] = {
                "workspace_identity": workspace_identity,
                "appid": appid,
                "raw_user_id": raw_user_id,
                "alias": alias,
                "alias_path": self._relative_alias_path(appid, alias),
            }
            workspaces[workspace_identity] = {
                "alias": alias,
                "appid": appid,
                "raw_user_id": raw_user_id,
                "shipyard_session_key": shipyard_session_key,
                "ship_id": workspaces.get(workspace_identity, {}).get("ship_id", ""),
                "ship_mnt_data_relpath": workspaces.get(workspace_identity, {}).get(
                    "ship_mnt_data_relpath", ""
                ),
                "last_known_good_relpath": workspaces.get(workspace_identity, {}).get(
                    "last_known_good_relpath", ""
                ),
                "status": workspaces.get(workspace_identity, {}).get(
                    "status", "pending"
                ),
                "reason": workspaces.get(workspace_identity, {}).get(
                    "reason", "pending_first_resolution"
                ),
                "updated_at": _utc_now(),
            }
            alias_states[workspace_identity] = "registered"

            return AliasRegistrationResult(alias=alias, idempotent=is_idempotent)

        result = self._with_manifest_lock(_update)
        self._ensure_alias_readme(appid, alias)
        binding = self.refresh_workspace_binding(
            workspace_identity,
            allow_fallback=True,
            mark_unresolved_on_failure=False,
        )
        result.workspace_ready = binding.status == "resolved"
        return result
