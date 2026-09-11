"""Application services for author update configuration and local publishing."""

from __future__ import annotations

import copy
import json
import os
import urllib.parse
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .bundle_signing_v6 import AuthorSigningKeyStore
from .update_protocol_v6 import UpdateProtocolError, verify_initial_root
from .update_repository_v6 import StaticUpdateRepository, UpdateRepositorySigner
from .workspace_context import VNextWorkspaceError

UPDATE_CONFIG_FILE = "updates.json"
UPDATE_CONFIG_SCHEMA_VERSION = 1
AUTHOR_DOMAINS = ("player_application", "project_content")


class UpdateConfigurationError(UpdateProtocolError):
    pass


def disabled_update_configuration() -> dict[str, Any]:
    return {
        "schema_version": UPDATE_CONFIG_SCHEMA_VERSION,
        "domains": {
            domain: {
                "enabled": False,
                "product_id": "",
                "provider": "self_hosted",
                "feed_base_url": "",
                "channel": "stable",
                "required_policy_capability": False,
                "initial_preferences": {
                    "automatic_check": True,
                    "automatic_download": False,
                    "automatic_apply": False,
                },
                "pinned_root": None,
            }
            for domain in AUTHOR_DOMAINS
        },
    }


def _feed_url(value: Any, *, enabled: bool) -> str:
    raw = str(value or "").strip().rstrip("/")
    if not enabled:
        if raw:
            raise UpdateConfigurationError("UPD-CONFIG-002", "关闭的更新域不得保留 Feed URL")
        return ""
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise UpdateConfigurationError("UPD-SOURCE-001", "更新 Feed 必须是无内嵌凭据的 HTTPS URL")
    return raw


def normalize_update_configuration(value: Any, *, project_id: str) -> dict[str, Any]:
    """Reject unknown fields so misspelled maintenance settings cannot leak."""

    if value is None:
        return disabled_update_configuration()
    if not isinstance(value, dict) or set(value) != {"schema_version", "domains"}:
        raise UpdateConfigurationError("UPD-CONFIG-001", "更新配置顶层字段无效")
    if value.get("schema_version") != UPDATE_CONFIG_SCHEMA_VERSION:
        raise UpdateConfigurationError("UPD-CONFIG-001", "更新配置版本不受支持")
    raw_domains = value.get("domains")
    if not isinstance(raw_domains, dict) or set(raw_domains) != set(AUTHOR_DOMAINS):
        raise UpdateConfigurationError("UPD-CONFIG-001", "更新配置必须显式包含两个 Player 产品域")
    normalized = disabled_update_configuration()
    seen_product_ids: set[str] = set()
    expected_fields = {
        "enabled", "product_id", "provider", "feed_base_url", "channel",
        "required_policy_capability", "initial_preferences", "pinned_root",
    }
    preference_fields = {"automatic_check", "automatic_download", "automatic_apply"}
    for domain in AUTHOR_DOMAINS:
        raw = raw_domains.get(domain)
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain} 更新配置字段无效")
        enabled = raw.get("enabled")
        if not isinstance(enabled, bool):
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain}.enabled 必须是布尔值")
        product_id = str(raw.get("product_id") or "").strip()
        provider = str(raw.get("provider") or "")
        channel = str(raw.get("channel") or "")
        required = raw.get("required_policy_capability")
        preferences = raw.get("initial_preferences")
        pinned_root = raw.get("pinned_root")
        if provider not in {"easycode_hosted", "self_hosted"}:
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain}.provider 无效")
        if channel not in {"test", "stable"}:
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain}.channel 无效")
        if not isinstance(required, bool):
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain}.required_policy_capability 必须是布尔值")
        if not isinstance(preferences, dict) or set(preferences) != preference_fields or any(
            not isinstance(item, bool) for item in preferences.values()
        ):
            raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain}.initial_preferences 无效")
        feed_url = _feed_url(raw.get("feed_base_url"), enabled=enabled)
        if enabled:
            if not product_id:
                raise UpdateConfigurationError("UPD-CONFIG-001", f"{domain} 缺少稳定 product_id")
            if product_id in seen_product_ids:
                raise UpdateConfigurationError("UPD-CONFIG-003", "Player 应用与项目内容必须使用独立 product_id")
            seen_product_ids.add(product_id)
            if pinned_root is not None:
                trusted = verify_initial_root(pinned_root, product_id=product_id)
                mirrors = set(trusted.get("mirrors") or [])
                if mirrors and feed_url not in mirrors:
                    raise UpdateConfigurationError("UPD-SOURCE-002", "Feed URL 不在签名信任根允许的镜像列表中")
        elif product_id or pinned_root is not None or required:
            raise UpdateConfigurationError("UPD-CONFIG-002", f"关闭的 {domain} 不得携带身份、信任根或强制策略能力")
        normalized["domains"][domain] = {
            "enabled": enabled,
            "product_id": product_id,
            "provider": provider,
            "feed_base_url": feed_url,
            "channel": channel,
            "required_policy_capability": required,
            "initial_preferences": copy.deepcopy(preferences),
            "pinned_root": copy.deepcopy(pinned_root),
        }
    # Project content's identity should stay visibly bound to this project,
    # without requiring equality (authors may reserve globally unique IDs).
    if not str(project_id or "").strip():
        raise UpdateConfigurationError("UPD-CONFIG-001", "项目缺少稳定 project_id")
    return normalized


def load_project_update_configuration(project_root: str | Path, *, project_id: str) -> dict[str, Any]:
    path = Path(project_root).resolve() / UPDATE_CONFIG_FILE
    if not path.is_file():
        return disabled_update_configuration()
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateConfigurationError("UPD-CONFIG-001", f"更新配置无法读取：{exc}") from exc
    return normalize_update_configuration(value, project_id=project_id)


def bundled_update_configuration(configuration: Mapping[str, Any]) -> dict[str, Any] | None:
    """Remove author/provider preferences; return None for a zero-byte closure."""

    enabled: dict[str, Any] = {}
    for domain, raw in (configuration.get("domains") or {}).items():
        if not isinstance(raw, Mapping) or not raw.get("enabled"):
            continue
        if raw.get("pinned_root") is None:
            raise UpdateConfigurationError("UPD-CONFIG-004", f"{domain} 尚未初始化签名信任根")
        enabled[str(domain)] = {
            "product_id": str(raw["product_id"]),
            "domain": str(domain),
            "feed_base_url": str(raw["feed_base_url"]),
            "channel": str(raw["channel"]),
            "required_policy_capability": bool(raw["required_policy_capability"]),
            "initial_preferences": copy.deepcopy(raw["initial_preferences"]),
            "pinned_root": copy.deepcopy(raw["pinned_root"]),
        }
    if not enabled:
        return None
    return {
        "schema_version": UPDATE_CONFIG_SCHEMA_VERSION,
        "protocol": "easycode-update-feed",
        "domains": enabled,
        "telemetry": False,
    }


def validate_bundled_update_configuration(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "protocol", "domains", "telemetry"}:
        raise UpdateConfigurationError("UPD-CONFIG-005", "Player 更新闭包字段无效")
    if value.get("schema_version") != 1 or value.get("protocol") != "easycode-update-feed":
        raise UpdateConfigurationError("UPD-CONFIG-005", "Player 更新闭包协议版本无效")
    if value.get("telemetry") is not False:
        raise UpdateConfigurationError("UPD-CONFIG-005", "更新闭包不得启用自动遥测")
    domains = value.get("domains")
    if not isinstance(domains, dict) or not domains or not set(domains).issubset(AUTHOR_DOMAINS):
        raise UpdateConfigurationError("UPD-CONFIG-005", "Player 更新闭包产品域无效")
    expected = {
        "product_id", "domain", "feed_base_url", "channel", "required_policy_capability",
        "initial_preferences", "pinned_root",
    }
    seen: set[str] = set()
    normalized: dict[str, Any] = {}
    for domain, raw in domains.items():
        if not isinstance(raw, dict) or set(raw) != expected or raw.get("domain") != domain:
            raise UpdateConfigurationError("UPD-CONFIG-005", f"{domain} Player 更新闭包字段无效")
        product_id = str(raw.get("product_id") or "").strip()
        if not product_id or product_id in seen:
            raise UpdateConfigurationError("UPD-CONFIG-005", "Player 更新 product_id 缺失或跨域复用")
        seen.add(product_id)
        feed_url = _feed_url(raw.get("feed_base_url"), enabled=True)
        channel = str(raw.get("channel") or "")
        if channel not in {"test", "stable"}:
            raise UpdateConfigurationError("UPD-CONFIG-005", f"{domain} Player 更新通道无效")
        required = raw.get("required_policy_capability")
        preferences = raw.get("initial_preferences")
        if not isinstance(required, bool):
            raise UpdateConfigurationError("UPD-CONFIG-005", f"{domain} 强制策略能力无效")
        if (
            not isinstance(preferences, dict)
            or set(preferences) != {"automatic_check", "automatic_download", "automatic_apply"}
            or any(not isinstance(item, bool) for item in preferences.values())
        ):
            raise UpdateConfigurationError("UPD-CONFIG-005", f"{domain} 初始更新偏好无效")
        root = raw.get("pinned_root")
        if not isinstance(root, dict):
            raise UpdateConfigurationError("UPD-CONFIG-005", f"{domain} 缺少信任根")
        trusted = verify_initial_root(root, product_id=product_id)
        mirrors = set(trusted.get("mirrors") or [])
        if mirrors and feed_url not in mirrors:
            raise UpdateConfigurationError("UPD-SOURCE-002", f"{domain} Feed 不在签名镜像列表")
        normalized[domain] = {
            "product_id": product_id,
            "domain": domain,
            "feed_base_url": feed_url,
            "channel": channel,
            "required_policy_capability": required,
            "initial_preferences": copy.deepcopy(preferences),
            "pinned_root": copy.deepcopy(root),
        }
    return {"schema_version": 1, "protocol": "easycode-update-feed", "domains": normalized, "telemetry": False}


class VNextUpdateAuthorService:
    """Workspace-bound author operations; private keys remain in local stores."""

    def __init__(self, owner: Any, project_file: str) -> None:
        self._owner = owner
        self._project_file = project_file

    def _workspace(self, workspace_id: str, generation: int, *, writable: bool = False):
        return self._owner._require(workspace_id, generation, writable=writable)

    def configuration(self, workspace_id: str, generation: int) -> dict[str, Any]:
        with self._owner._lock:
            workspace = self._workspace(workspace_id, generation)
            project = self._owner._read_json(os.path.join(workspace.project_path, self._project_file))
            value = load_project_update_configuration(workspace.project_path, project_id=str(project.get("project_id") or ""))
            return {"configuration": value, "enabled": any(item["enabled"] for item in value["domains"].values())}

    def save_configuration(self, workspace_id: str, generation: int, value: Mapping[str, Any]) -> dict[str, Any]:
        with self._owner._lock:
            workspace = self._workspace(workspace_id, generation, writable=True)
            project = self._owner._read_json(os.path.join(workspace.project_path, self._project_file))
            normalized = normalize_update_configuration(dict(value), project_id=str(project.get("project_id") or ""))
            path = os.path.join(workspace.project_path, UPDATE_CONFIG_FILE)
            self._owner._atomic_write_json(path, normalized)
            return {"saved": True, "configuration": normalized}

    def initialize_repository(
        self,
        workspace_id: str,
        generation: int,
        *,
        domain: str,
        repository_root: str,
    ) -> dict[str, Any]:
        if domain not in AUTHOR_DOMAINS:
            raise VNextWorkspaceError("更新发布域无效")
        with self._owner._lock:
            workspace = self._workspace(workspace_id, generation, writable=True)
            project = self._owner._read_json(os.path.join(workspace.project_path, self._project_file))
            configuration = load_project_update_configuration(
                workspace.project_path, project_id=str(project.get("project_id") or ""),
            )
            selected = configuration["domains"][domain]
            if not selected["enabled"]:
                raise VNextWorkspaceError("该更新产品域尚未启用")
            if selected["provider"] == "easycode_hosted":
                raise VNextWorkspaceError("当前构建未连接真实 EasyCode 官方托管；请使用自建静态 HTTPS Feed")
            signer = UpdateRepositorySigner.from_author_store(
                str(selected["product_id"]), mirrors=[str(selected["feed_base_url"])],
            )
            repository = StaticUpdateRepository(repository_root, signer)
            result = repository.initialize([domain])
            root_path = Path(repository_root).resolve() / selected["product_id"] / domain / "metadata" / "root.json"
            selected["pinned_root"] = json.loads(root_path.read_text(encoding="utf-8-sig"))
            self._owner._atomic_write_json(os.path.join(workspace.project_path, UPDATE_CONFIG_FILE), configuration)
            return {**result, "domain": domain, "pinned_root": selected["pinned_root"]}

    def _repository(
        self,
        workspace_id: str,
        generation: int,
        *,
        domain: str,
        repository_root: str,
    ) -> tuple[Any, dict[str, Any], StaticUpdateRepository]:
        workspace = self._workspace(workspace_id, generation, writable=True)
        project = self._owner._read_json(os.path.join(workspace.project_path, self._project_file))
        configuration = load_project_update_configuration(
            workspace.project_path, project_id=str(project.get("project_id") or ""),
        )
        selected = configuration["domains"].get(domain)
        if not selected or not selected["enabled"] or selected["pinned_root"] is None:
            raise VNextWorkspaceError("该更新域未启用或仓库尚未初始化")
        if selected["provider"] == "easycode_hosted":
            raise VNextWorkspaceError("当前构建未连接真实 EasyCode 官方托管，不能伪造上传或发布状态")
        signer = UpdateRepositorySigner.from_author_store(
            str(selected["product_id"]), mirrors=[str(selected["feed_base_url"])],
        )
        return workspace, selected, StaticUpdateRepository(repository_root, signer)

    def publish_project_content(
        self,
        workspace_id: str,
        generation: int,
        *,
        repository_root: str,
        platform: str,
        architecture: str,
        display_version: str,
        notes: str = "",
    ) -> dict[str, Any]:
        with self._owner._lock:
            workspace, _selected, repository = self._repository(
                workspace_id, generation, domain="project_content", repository_root=repository_root,
            )
            built = self._owner._publishing._build_locked(workspace_id, generation)
            project = self._owner._read_json(os.path.join(workspace.project_path, self._project_file))
            author_identity = AuthorSigningKeyStore().get_or_create(str(project.get("project_id") or ""))
            result = repository.publish_project_content(
                built["path"],
                display_version=display_version,
                platform=platform,
                architecture=architecture,
                expected_public_key=author_identity.public_key_bytes,
                notes=notes,
            )
            return {**result, "bundle": built}

    def publish_application_artifact(
        self,
        workspace_id: str,
        generation: int,
        *,
        repository_root: str,
        artifact_path: str,
        platform: str,
        architecture: str,
        display_version: str,
        runtime_min: str,
        runtime_max: str,
        ecir_min: str,
        ecir_max: str,
        application_fingerprint: str,
        permissions_fingerprint: str,
        abi: list[str],
        android_version_code: int | None = None,
        android_certificate_sha256: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        with self._owner._lock:
            _workspace, _selected, repository = self._repository(
                workspace_id, generation, domain="player_application", repository_root=repository_root,
            )
            record: dict[str, Any] = {
                "source": artifact_path,
                "platform": platform,
                "architecture": architecture,
                "runtime_min": runtime_min,
                "runtime_max": runtime_max,
                "ecir_min": ecir_min,
                "ecir_max": ecir_max,
                "application_fingerprint": application_fingerprint,
                "permissions_fingerprint": permissions_fingerprint,
                "abi": abi,
            }
            if platform == "android":
                record.update(
                    android_version_code=android_version_code,
                    android_certificate_sha256=android_certificate_sha256,
                )
            return repository.publish_release(
                "player_application", [record], display_version=display_version, notes=notes,
            )

    def set_rollout(self, workspace_id: str, generation: int, *, domain: str, repository_root: str, **values: Any) -> dict[str, Any]:
        with self._owner._lock:
            _workspace, _selected, repository = self._repository(
                workspace_id, generation, domain=domain, repository_root=repository_root,
            )
            return repository.set_rollout(domain, **values)

    def set_required_policy(
        self,
        workspace_id: str,
        generation: int,
        *,
        domain: str,
        repository_root: str,
        release_id: str,
        effective_at: datetime,
        grace_deadline: datetime,
        reason: str,
        platform_targets: list[str],
    ) -> dict[str, Any]:
        with self._owner._lock:
            _workspace, selected, repository = self._repository(
                workspace_id, generation, domain=domain, repository_root=repository_root,
            )
            if not selected["required_policy_capability"]:
                raise VNextWorkspaceError("该 Player 未声明强制策略检查能力")
            return repository.publish_required_policy(
                domain,
                release_id=release_id,
                effective_at=effective_at,
                grace_deadline=grace_deadline,
                reason=reason,
                platform_targets=platform_targets,
            )

    def revoke_required_policy(self, workspace_id: str, generation: int, *, domain: str, repository_root: str) -> dict[str, Any]:
        with self._owner._lock:
            _workspace, _selected, repository = self._repository(
                workspace_id, generation, domain=domain, repository_root=repository_root,
            )
            return repository.revoke_required_policy(domain)


__all__ = [
    "AUTHOR_DOMAINS",
    "UPDATE_CONFIG_FILE",
    "UPDATE_CONFIG_SCHEMA_VERSION",
    "UpdateConfigurationError",
    "VNextUpdateAuthorService",
    "bundled_update_configuration",
    "disabled_update_configuration",
    "load_project_update_configuration",
    "normalize_update_configuration",
    "validate_bundled_update_configuration",
]
