"""Installed IDE update product host.

The service is inert unless an installation ships an explicit signed config
path.  Source checkouts therefore have no IDE update endpoint, scheduler, or
network activity by default.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .update_client_v6 import (
    CommandPlatformInstaller,
    UpdateClient,
    UpdateClientConfig,
    UpdateClientError,
    UpdatePreferencesStore,
    native_platform,
)
from .update_protocol_v6 import verify_initial_root


class IdeUpdateService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: UpdateClient | None = None
        self._preferences: UpdatePreferencesStore | None = None
        self._initial: dict[str, bool] = {}
        self._loaded = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _config_path() -> Path | None:
        raw = str(os.environ.get("EASYCODE_IDE_UPDATE_CONFIG") or "").strip()
        return Path(raw).expanduser().resolve() if raw else None

    @staticmethod
    def _load_document(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateClientError("UPD-IDE-CONFIG-001", f"IDE 更新配置无法读取：{exc}") from exc
        expected = {
            "schema_version", "enabled", "product_id", "domain", "feed_base_url", "channel",
            "required_policy_capability", "initial_preferences", "pinned_root",
        }
        if not isinstance(value, dict) or set(value) != expected or value.get("schema_version") != 1:
            raise UpdateClientError("UPD-IDE-CONFIG-001", "IDE 更新配置字段或版本无效")
        if value.get("enabled") is not True or value.get("domain") != "ide":
            raise UpdateClientError("UPD-IDE-CONFIG-001", "IDE 更新配置必须显式启用 ide 产品域")
        product_id = str(value.get("product_id") or "").strip()
        root = value.get("pinned_root")
        if not product_id or not isinstance(root, dict):
            raise UpdateClientError("UPD-IDE-CONFIG-001", "IDE 更新配置缺少身份或信任根")
        verify_initial_root(root, product_id=product_id)
        preferences = value.get("initial_preferences")
        if (
            not isinstance(preferences, dict)
            or set(preferences) != {"automatic_check", "automatic_download", "automatic_apply"}
            or any(not isinstance(item, bool) for item in preferences.values())
        ):
            raise UpdateClientError("UPD-IDE-CONFIG-001", "IDE 初始更新偏好无效")
        return value

    def _ensure(self) -> UpdateClient | None:
        with self._lock:
            if self._loaded:
                return self._client
            self._loaded = True
            path = self._config_path()
            if path is None or not path.is_file():
                return None
            value = self._load_document(path)
            local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "EasyCode"
            durable = Path(os.environ.get("EASYCODE_UPDATE_DATA_DIR") or local / "UpdateState")
            cache = Path(os.environ.get("EASYCODE_UPDATE_CACHE_DIR") or local / "UpdateCache")
            preferences = UpdatePreferencesStore(durable, str(value["product_id"]))
            selected = preferences.get(value["initial_preferences"])
            platform_name, architecture = native_platform()
            helper = str(os.environ.get("EASYCODE_WINDOWS_UPDATE_HELPER") or "").strip()
            install_root = str(os.environ.get("EASYCODE_WINDOWS_INSTALL_ROOT") or "").strip()
            restart_raw = str(os.environ.get("EASYCODE_WINDOWS_RESTART_COMMAND") or "").strip()
            try:
                restart_command = json.loads(restart_raw) if restart_raw else []
            except json.JSONDecodeError as exc:
                raise UpdateClientError("UPD-IDE-CONFIG-001", "IDE 更新重启命令不是有效 JSON") from exc
            installer = (
                CommandPlatformInstaller(
                    [helper],
                    durable / "handoffs",
                    install_root=install_root,
                    restart_command=[str(item) for item in restart_command],
                )
                if helper and Path(helper).is_file() and install_root and isinstance(restart_command, list) and restart_command
                else None
            )
            self._client = UpdateClient(
                UpdateClientConfig(
                    enabled=True,
                    product_id=str(value["product_id"]),
                    domain="ide",
                    platform=platform_name,
                    architecture=architecture,
                    current_release_id=str(os.environ.get("EASYCODE_IDE_RELEASE_ID") or "ide-installed"),
                    current_release_sequence=int(os.environ.get("EASYCODE_IDE_RELEASE_SEQUENCE") or 0),
                    channel=str(value["channel"]),
                    automatic_checks=selected["automatic_check"],
                    required_policy_capability=bool(value["required_policy_capability"]),
                    feed_base_url=str(value["feed_base_url"]),
                    pinned_root=value["pinned_root"],
                ),
                durable_root=durable,
                cache_root=cache,
                installer=installer,
            )
            self._preferences = preferences
            self._initial = dict(value["initial_preferences"])
            return self._client

    def start(self) -> None:
        client = self._ensure()
        if client is None or self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ide-update-scheduler")
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(30):
            client = self._client
            if client is None:
                continue
            try:
                preferences = self._preferences.get(self._initial) if self._preferences else {}
                for result in client.run_due_checks():
                    if result.available and preferences.get("automatic_download"):
                        client.download()
                        if preferences.get("automatic_apply"):
                            client.apply()
            except Exception:
                continue

    def shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            if self._client is not None:
                self._client.close()
            self._client = None
            self._thread = None
            self._loaded = False

    def status(self) -> dict[str, Any]:
        client = self._ensure()
        if client is None:
            return {"enabled": False, "state": "disabled"}
        preferences = self._preferences.get(self._initial) if self._preferences else {}
        return {**client.status(), "preferences": preferences, "telemetry": False}

    def check(self) -> dict[str, Any]:
        client = self._ensure()
        if client is None:
            raise UpdateClientError("UPD-DISABLED-001", "IDE 更新能力未启用")
        return asdict(client.check(manual=True))

    def download(self) -> dict[str, Any]:
        client = self._ensure()
        if client is None:
            raise UpdateClientError("UPD-DISABLED-001", "IDE 更新能力未启用")
        path = client.download()
        return {"downloaded": True, "path": str(path), "status": client.status()}

    def apply(self) -> dict[str, Any]:
        client = self._ensure()
        if client is None:
            raise UpdateClientError("UPD-DISABLED-001", "IDE 更新能力未启用")
        return client.apply()

    def save_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure()
        if client is None or self._preferences is None:
            raise UpdateClientError("UPD-DISABLED-001", "IDE 更新能力未启用")
        preferences = self._preferences.save(values)
        client.set_automatic_checks(preferences["automatic_check"])
        return {"saved": True, "preferences": preferences}


ide_update_service_v6 = IdeUpdateService()


__all__ = ["IdeUpdateService", "ide_update_service_v6"]
