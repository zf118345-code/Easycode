"""Format-6 extension discovery, trust, locking and Worker execution.

``easycode-extension.json`` plus its declared contract files are the only
extension business facts. Python signatures and editable IDE source views are
intentionally absent from this module.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from .bundle_signing_v6 import AuthorSigningKeyStore, canonical_json_bytes, sha256_hex
from .control_defaults import parameter_ui_for_type
from .function_contracts_v6 import statement_summary_contract
from .extension_schema_v6 import (
    ExtensionFunctionContractV1,
    ExtensionManifestV1,
    ExtensionSchemaError,
    EasyCodeLockV1,
    FunctionContractFileV1,
    HostVariantV1,
    LOCK_FILE,
    MANIFEST_FILE,
    MANIFEST_SIGNATURE_FILE,
    RUNTIME_FORMAT,
    PublishedExtensionV1,
    create_artifact_signature,
    ensure_no_package_symlinks,
    load_function_contracts,
    load_easycode_lock,
    load_manifest,
    package_digest,
    resolve_package_path,
    sign_manifest,
    validate_sealed_artifact,
    validate_published_extension,
    version_satisfies,
    verify_manifest_signature,
)
from .mutation import ProjectMutationTransaction
from .program_contracts import FunctionContract, ParameterContract, get_contract
from .runtime import RuntimeFailure
from .workspace_context import VNextWorkspaceContext


ScopeName = Literal["official", "user", "project"]
SCOPE_PRECEDENCE: tuple[ScopeName, ...] = ("project", "user", "official")
HOST_RUNTIME_VERSION = "6.0.0"


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".easycode-extension-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if default is not None and not path.is_file():
        return copy.deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeFailure(f"扩展状态文件无法读取：{path.name}（{exc}）") from exc
    if not isinstance(value, dict):
        raise RuntimeFailure(f"扩展状态文件必须是 JSON 对象：{path.name}")
    return value


class ExtensionTrustStore:
    """Machine-local publisher trust; never copied into a project or bundle."""

    def __init__(self, root: str | Path | None = None) -> None:
        configured = str(os.environ.get("EASYCODE_EXTENSION_STATE_DIR") or "").strip()
        self.root = Path(
            configured
            or root
            or Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "EasyCode" / "Extensions"
        ).expanduser().resolve()
        self.path = self.root / "trust.json"

    def _document(self) -> dict[str, Any]:
        value = _read_json(self.path, default={"trust_version": 1, "publishers": {}})
        if value.get("trust_version") != 1 or not isinstance(value.get("publishers"), dict):
            raise RuntimeFailure("本机扩展信任记录格式无效")
        return value

    def record(self, key_id: str) -> dict[str, Any] | None:
        value = self._document()["publishers"].get(key_id)
        return dict(value) if isinstance(value, dict) else None

    def trust(self, *, key_id: str, publisher_id: str, mode: str) -> dict[str, Any]:
        if mode not in {"explicit", "local_development"}:
            raise RuntimeFailure("扩展信任模式无效")
        document = self._document()
        document["publishers"][key_id] = {
            "publisher_id": publisher_id,
            "mode": mode,
            "trusted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _atomic_write(self.path, _json_bytes(document))
        return dict(document["publishers"][key_id])

    def untrust(self, key_id: str) -> bool:
        document = self._document()
        existed = document["publishers"].pop(key_id, None) is not None
        if existed:
            _atomic_write(self.path, _json_bytes(document))
        return existed


class VNextExtensionRegistry:
    """Strict package registry used by authoring, compilation and runtime."""

    trust_store_factory: Callable[[], ExtensionTrustStore] = ExtensionTrustStore
    signing_key_store_factory: Callable[[], AuthorSigningKeyStore] = AuthorSigningKeyStore

    @classmethod
    def scope_roots(cls, project_path: str) -> dict[ScopeName, Path]:
        repository_root = Path(__file__).resolve().parents[2]
        local = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "EasyCode" / "Extensions"
        return {
            "official": Path(
                os.environ.get("EASYCODE_OFFICIAL_EXTENSIONS_DIR")
                or repository_root / "extensions" / "official"
            ).expanduser().resolve(),
            "user": Path(
                os.environ.get("EASYCODE_USER_EXTENSIONS_DIR")
                or local / "packages"
            ).expanduser().resolve(),
            "project": (Path(project_path).resolve() / "extensions").resolve(),
        }

    @classmethod
    def _scope_root(cls, project_path: str, scope: str) -> Path:
        if scope not in SCOPE_PRECEDENCE:
            raise RuntimeFailure("扩展安装范围必须是 official、user 或 project")
        return cls.scope_roots(project_path)[scope]  # type: ignore[index]

    @classmethod
    def _project_state(cls, project_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
        root = Path(project_path).resolve()
        project = _read_json(root / "project.json")
        try:
            lock = load_easycode_lock(root / LOCK_FILE).model_dump(mode="json")
        except ExtensionSchemaError as exc:
            raise RuntimeFailure(str(exc), error_id="extension.lock_invalid") from exc
        return project, lock

    @staticmethod
    def _package_files(root: Path) -> list[str]:
        ensure_no_package_symlinks(root)
        return [
            path.relative_to(root).as_posix()
            for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
            if path.is_file()
        ]

    @classmethod
    def _content_hash(cls, root: Path) -> str:
        return package_digest(root, cls._package_files(root))

    @classmethod
    def _discover_roots(cls, project_path: str) -> list[tuple[ScopeName, Path]]:
        found: list[tuple[ScopeName, Path]] = []
        for scope in SCOPE_PRECEDENCE:
            parent = cls.scope_roots(project_path)[scope]
            if not parent.is_dir() or parent.is_symlink():
                continue
            for root in sorted(parent.iterdir(), key=lambda item: item.name.casefold()):
                if root.is_symlink() or (root.is_dir() and (root / MANIFEST_FILE).is_file()):
                    found.append((scope, root))
        return found

    @classmethod
    def _lock_record(cls, project_path: str, package_id: str) -> dict[str, Any] | None:
        try:
            _project, lock = cls._project_state(project_path)
        except RuntimeFailure:
            return None
        return next(
            (dict(item) for item in lock.get("extensions") or [] if item.get("package_id") == package_id),
            None,
        )

    @classmethod
    def _inspect_root(cls, project_path: str, root: Path, scope: ScopeName) -> dict[str, Any]:
        diagnostics: list[dict[str, Any]] = []
        try:
            if root.is_symlink():
                raise ExtensionSchemaError("扩展安装目录不允许符号链接")
            ensure_no_package_symlinks(root)
            manifest, canonical = load_manifest(root)
            if not version_satisfies(HOST_RUNTIME_VERSION, manifest.requires.easycode):
                raise ExtensionSchemaError(
                    f"扩展要求 EasyCode {manifest.requires.easycode}，当前为 {HOST_RUNTIME_VERSION}"
                )
            signature = verify_manifest_signature(root, manifest, canonical)
            functions, contributions = load_function_contracts(root, manifest)
            artifact_records = [
                validate_sealed_artifact(root, manifest, variant, signature)
                for variant in manifest.host_variants
                if variant.sealed_artifact
            ]
            key_id = str(signature["key_id"])
            trust = (
                {"mode": "official", "publisher_id": manifest.publisher_id}
                if scope == "official"
                else cls.trust_store_factory().record(key_id)
            )
            project, _lock = cls._project_state(project_path)
            enabled = manifest.package_id in set(project.get("enabled_extension_ids") or [])
            locked = cls._lock_record(project_path, manifest.package_id)
            content_hash = cls._content_hash(root)
            lock_current = bool(
                locked
                and locked.get("scope") == scope
                and locked.get("version") == manifest.version
                and locked.get("content_sha256") == content_hash
                and locked.get("publisher_key_fingerprint") == key_id
            )
            if enabled and not lock_current:
                diagnostics.append({
                    "code": "extension.lock_drift",
                    "severity": "warning",
                    "message": "扩展内容与 easycode.lock 不一致；不会静默更新，请重新校验并显式启用",
                })
            return {
                "package_id": manifest.package_id,
                "display_name": manifest.display_name,
                "description": manifest.description,
                "version": manifest.version,
                "publisher": {
                    "publisher_id": manifest.publisher_id,
                    "display_name": manifest.publisher_id,
                },
                "scope": scope,
                "path": str(root),
                "manifest": manifest.model_dump(mode="json", exclude_none=True),
                "manifest_sha256": sha256_hex(canonical),
                "content_sha256": content_hash,
                "signature": signature,
                "signature_verified": True,
                "trusted": trust is not None,
                "trust": trust,
                "enabled": enabled,
                "lock_current": lock_current,
                "functions": [cls._function_payload(item, manifest.package_id, manifest) for item in functions],
                "function_contracts": [item.model_dump(mode="json") for item in functions],
                "contributions": contributions,
                "host_variants": [item.model_dump(mode="json", exclude_none=True) for item in manifest.host_variants],
                "sealed_artifacts": artifact_records,
                "dependencies": [item.model_dump(mode="json") for item in manifest.dependencies],
                "permissions": list(manifest.permissions),
                "network": manifest.network.model_dump(mode="json"),
                "tier": manifest.tier,
                "valid": not any(item["severity"] == "error" for item in diagnostics),
                "diagnostics": diagnostics,
            }
        except (ExtensionSchemaError, OSError, ValueError) as exc:
            return {
                "package_id": root.name,
                "display_name": root.name,
                "scope": scope,
                "path": str(root),
                "signature_verified": False,
                "trusted": False,
                "enabled": False,
                "lock_current": False,
                "functions": [],
                "function_contracts": [],
                "contributions": [],
                "host_variants": [],
                "sealed_artifacts": [],
                "dependencies": [],
                "permissions": [],
                "valid": False,
                "diagnostics": [{
                    "code": "extension.package_invalid",
                    "severity": "error",
                    "message": str(exc),
                }],
            }

    @classmethod
    def packages(cls, project_path: str) -> dict[str, Any]:
        packages = [cls._inspect_root(project_path, root, scope) for scope, root in cls._discover_roots(project_path)]
        identifiers: dict[str, list[dict[str, Any]]] = {}
        for package in packages:
            if package.get("valid"):
                identifiers.setdefault(str(package["package_id"]), []).append(package)
        for package_id, matches in identifiers.items():
            enabled = [item for item in matches if item.get("enabled")]
            if len(enabled) > 1:
                for item in enabled:
                    item["valid"] = False
                    item["diagnostics"].append({
                        "code": "extension.duplicate_enabled_package",
                        "severity": "error",
                        "message": f"同一 package_id 只能从一个范围启用：{package_id}",
                    })
        return {
            "schema_version": 1,
            "packages": packages,
            "scopes": [
                {"scope": scope, "path": str(path), "writable": scope != "official"}
                for scope, path in cls.scope_roots(project_path).items()
            ],
            "worker_notice": "Worker 提供超时、取消、日志、序列化和崩溃隔离；它不是抵御恶意代码的安全沙箱。",
        }

    @classmethod
    def package(cls, project_path: str, package_id: str, scope: str | None = None) -> dict[str, Any]:
        matches = [
            item for item in cls.packages(project_path)["packages"]
            if item.get("package_id") == package_id and (scope is None or item.get("scope") == scope)
        ]
        if not matches:
            raise RuntimeFailure(f"扩展包不存在：{package_id}")
        if len(matches) > 1 and scope is None:
            locked = cls._lock_record(project_path, package_id)
            if locked:
                selected = next((item for item in matches if item.get("scope") == locked.get("scope")), None)
                if selected:
                    return selected
            raise RuntimeFailure("扩展包存在多个安装范围，请明确选择范围")
        return matches[0]

    @staticmethod
    def _function_payload(
        function: ExtensionFunctionContractV1,
        package_id: str,
        manifest: ExtensionManifestV1,
    ) -> dict[str, Any]:
        namespace, _, name = function.qualified_name.partition(".")
        if not name:
            namespace, name = "扩展", function.qualified_name
        parameters = []
        for parameter in function.parameters:
            ui = dict(parameter.control or parameter_ui_for_type(parameter.value_type))
            parameters.append({
                "parameter_id": parameter.parameter_id,
                "name": parameter.name,
                "display_name": parameter.display_name,
                "value_type": parameter.value_type,
                "required": parameter.required,
                "has_default": not parameter.required,
                "default": parameter.default,
                "description": "",
                "ui": ui,
                "control": ui.get("control", "auto"),
                "constraints": {},
            })
        fingerprint = sha256_hex(canonical_json_bytes(function.model_dump(mode="json")))
        platforms = [
            "no_target" if item == "none" else "android_local" if item == "android_native" else item
            for item in function.targets
        ]
        android_floors = [
            int(variant.minimum_android_api or 21)
            for variant in manifest.host_variants
            if variant.host == "android_native" and function.function_id in variant.entrypoints
        ]
        return {
            "function_id": function.function_id,
            "qualified_name": function.qualified_name,
            "namespace": namespace,
            "name": name,
            "summary": function.statement_summary or function.qualified_name,
            "statement_summary": statement_summary_contract(
                function.statement_summary or function.qualified_name,
                function.parameters,
            ),
            "description": function.description,
            "source": "extension",
            "package_id": package_id,
            "layer": "extension",
            "opcode": "call.extension",
            "parameters": parameters,
            "return_type": function.return_type,
            "permissions": list(function.permissions),
            "target_kinds": list(function.targets),
            "platforms": platforms,
            "verified_platforms": platforms,
            "contract_version": function.contract_version,
            "contract_fingerprint": fingerprint,
            "implementation_state": "available",
            "timeout_ms": function.timeout_ms,
            "minimum_android_api": max(android_floors, default=21),
        }

    @classmethod
    def definitions(cls, project_path: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        definitions: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for package in cls.packages(project_path)["packages"]:
            if package.get("enabled") and package.get("trusted") and package.get("valid") and package.get("lock_current"):
                definitions.extend(copy.deepcopy(package.get("functions") or []))
            elif package.get("enabled"):
                errors.extend({
                    "source": str(package.get("path") or ""),
                    "message": str(item.get("message") or "扩展不可用"),
                } for item in package.get("diagnostics") or [] if item.get("severity") == "error")
                if not package.get("trusted"):
                    errors.append({"source": str(package.get("path") or ""), "message": "扩展尚未在本机信任"})
        return definitions, errors

    @classmethod
    def _write_package_files(cls, project_path: str, scope: str, package_id: str, files: dict[str, bytes]) -> Path:
        parent = cls._scope_root(project_path, scope)
        destination = parent / package_id
        if destination.exists():
            raise RuntimeFailure(f"扩展包已存在：{package_id}")
        if scope == "project":
            ProjectMutationTransaction.apply(project_path, {
                f"extensions/{package_id}/{relative}": content for relative, content in files.items()
            })
            return destination
        if scope == "official":
            raise RuntimeFailure("官方扩展范围为只读")
        parent.mkdir(parents=True, exist_ok=True)
        temporary = parent / f".{package_id}.{uuid.uuid4().hex}.tmp"
        try:
            for relative, content in files.items():
                path = temporary.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            os.replace(temporary, destination)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return destination

    @classmethod
    def scaffold(
        cls,
        project_path: str,
        *,
        package_id: str,
        publisher_id: str,
        publisher_name: str,
        display_name: str,
        description: str = "",
        scope: str = "project",
    ) -> dict[str, Any]:
        contribution_id = f"{package_id}.functions"
        variant_id = f"{package_id}.windows.python"
        manifest = ExtensionManifestV1.model_validate({
            "manifest_version": 1,
            "package_id": package_id,
            "publisher_id": publisher_id,
            "version": "1.0.0",
            "display": {
                "name": display_name,
                "description": description,
                "homepage": None,
                "metadata": {"publisher_display_name": publisher_name},
            },
            "tier": "function",
            "requires": {
                "easycode": ">=6.0.0 <7.0.0",
                "program_schema": 1,
                "ecir": 1,
            },
            "activation": ["on_project_enable", "on_function_call"],
            "permissions": [],
            "network": {"level": "none", "rules": []},
            "dependencies": [],
            "contributions": {
                "function_contracts": [{
                    "contribution_id": contribution_id,
                    "path": "contracts/functions.json",
                    "variant_bindings": [variant_id],
                }],
                "data_schemas": [],
                "workspaces": [],
                "compiler_steps": [],
                "runtime_modules": [],
                "player_modules": [],
                "harness_adapters": [],
                "target_drivers": [],
            },
            "variants": [{
                "variant_id": variant_id,
                "host": "windows",
                "runtime": "python-worker-3.12",
                "targets": ["windows", "android_adb", "none"],
                "development_entry": "src/main.py",
                "entrypoints": {},
            }],
            "data": None,
            "licenses": [{"id": "MIT", "path": "LICENSE"}],
        })
        contracts = FunctionContractFileV1(
            contract_schema_version=1,
            contribution_id=contribution_id,
            functions=(),
        )
        try:
            identity = cls.signing_key_store_factory().get_or_create(f"extension:{publisher_id}")
        except Exception as exc:
            raise RuntimeFailure(f"无法建立扩展开发者签名身份：{exc}") from exc
        files = {
            MANIFEST_FILE: _json_bytes(manifest.model_dump(mode="json", exclude_none=True)),
            "contracts/functions.json": _json_bytes(contracts.model_dump(mode="json")),
            "src/main.py": (
                '"""Trusted EasyCode extension implementation.\n\n'
                "Declare every public function in contracts/functions.json and variants.entrypoints.\n"
                '"""\n'
            ).encode("utf-8"),
            "README.md": (
                f"# {display_name}\n\n"
                "在外部 IDE 编辑。参数、返回值和 Control 只以 contracts/functions.json 为准；"
                "EasyCode 不解析 Python 签名。\n"
            ).encode("utf-8"),
            "LICENSE": (
                "MIT License\n\nCopyright (c) EasyCode extension author\n\n"
                "Permission is hereby granted, free of charge, to any person obtaining a copy "
                "of this software and associated documentation files (the \"Software\"), to deal "
                "in the Software without restriction, subject to the MIT License terms.\n"
            ).encode("utf-8"),
        }
        root = cls._write_package_files(project_path, scope, package_id, files)
        _atomic_write(root / MANIFEST_SIGNATURE_FILE, _json_bytes(sign_manifest(root, manifest, identity)))
        return {"created": True, "path": str(root), "package": cls.package(project_path, package_id, scope)}

    @classmethod
    def import_package(cls, project_path: str, *, source_path: str, scope: str = "project") -> dict[str, Any]:
        source = Path(source_path).expanduser().resolve()
        if not source.is_dir() or source.is_symlink():
            raise RuntimeFailure("请选择一个普通扩展包文件夹")
        package = cls._inspect_root(project_path, source, "project")
        if not package.get("valid"):
            raise RuntimeFailure(str((package.get("diagnostics") or [{}])[0].get("message") or "扩展包无效"))
        files = {
            relative: resolve_package_path(source, relative).read_bytes()
            for relative in cls._package_files(source)
        }
        destination = cls._write_package_files(project_path, scope, str(package["package_id"]), files)
        return {
            "imported": True,
            "path": str(destination),
            "package": cls.package(project_path, str(package["package_id"]), scope),
        }

    @classmethod
    def validate(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        return {
            "valid": bool(package.get("valid")),
            "package_id": package_id,
            "scope": scope,
            "diagnostics": copy.deepcopy(package.get("diagnostics") or []),
            "manifest_sha256": package.get("manifest_sha256"),
            "content_sha256": package.get("content_sha256"),
            "signature_verified": package.get("signature_verified"),
            "sealed_artifacts": copy.deepcopy(package.get("sealed_artifacts") or []),
        }

    @classmethod
    def trust(cls, project_path: str, package_id: str, scope: str, *, mode: str = "explicit") -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if not package.get("valid") or not package.get("signature_verified"):
            raise RuntimeFailure("扩展清单签名未通过，不能信任")
        signature = package["signature"]
        trust = cls.trust_store_factory().trust(
            key_id=str(signature["key_id"]),
            publisher_id=str(package["publisher"]["publisher_id"]),
            mode=mode,
        )
        return {"trusted": True, "package_id": package_id, "scope": scope, "trust": trust}

    @classmethod
    def untrust(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if package.get("enabled"):
            raise RuntimeFailure("请先禁用扩展，再撤销本机信任")
        removed = cls.trust_store_factory().untrust(str(package.get("signature", {}).get("key_id") or ""))
        return {"trusted": False, "removed": removed, "package_id": package_id, "scope": scope}

    @classmethod
    def references(cls, project_path: str, package_id: str, scope: str | None = None) -> list[dict[str, Any]]:
        package = cls.package(project_path, package_id, scope)
        identifiers = {
            package_id,
            *(str(item.get("function_id") or "") for item in package.get("functions") or []),
            *(str(item.get("contribution_id") or "") for item in package.get("contributions") or []),
        }
        identifiers.discard("")
        root = Path(project_path).resolve()
        files = [*sorted((root / "program" / "functions").glob("*.json"))]
        files.extend(path for path in (root / "player").rglob("*.json") if path.is_file())
        files.extend(path for path in (root / "extension-data").rglob("*.json") if path.is_file())
        if (root / "assets" / "registry.json").is_file():
            files.append(root / "assets" / "registry.json")
        references: list[dict[str, Any]] = []

        def walk(value: Any, trail: list[str], relative: str) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, [*trail, str(key)], relative)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, [*trail, str(index)], relative)
            elif isinstance(value, str) and value in identifiers:
                references.append({"path": relative, "json_path": ".".join(trail), "identifier": value})

        for path in files:
            try:
                walk(json.loads(path.read_text(encoding="utf-8-sig")), [], path.relative_to(root).as_posix())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
        return references

    @classmethod
    def _select_variants(cls, manifest: ExtensionManifestV1, root: Path) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        combinations = sorted({
            (variant.host, target)
            for variant in manifest.host_variants
            for target in variant.targets
        })
        for host, target in combinations:
            candidates = [
                item for item in manifest.host_variants
                if item.host == host and target in item.targets
            ]
            variant = sorted(candidates, key=lambda item: item.variant_id)[0]
            selected.append({
                "target": target,
                "host": host,
                "variant_id": variant.variant_id,
                "runtime": variant.runtime,
                "minimum_android_api": variant.minimum_android_api,
                "artifact_sha256": variant.sealed_sha256,
                "artifact_signature_sha256": (
                    sha256_hex(resolve_package_path(root, variant.sealed_signature).read_bytes())
                    if variant.sealed_signature else None
                ),
            })
        return selected

    @classmethod
    def _lock_payload(cls, project_path: str, package: dict[str, Any]) -> dict[str, Any]:
        manifest = ExtensionManifestV1.model_validate(package["manifest"])
        _project, current_lock = cls._project_state(project_path)
        locked_dependencies: list[dict[str, Any]] = []
        for dependency in manifest.dependencies:
            locked = next(
                (item for item in current_lock.get("extensions") or [] if item.get("package_id") == dependency.package_id),
                None,
            )
            if locked is None:
                if dependency.optional:
                    continue
                raise RuntimeFailure(f"请先显式启用依赖：{dependency.package_id}")
            if not version_satisfies(str(locked.get("version") or ""), dependency.version):
                raise RuntimeFailure(
                    f"依赖版本不满足约束：{dependency.package_id} {dependency.version}"
                )
            locked_dependencies.append({
                "package_id": dependency.package_id,
                "version": locked["version"],
                "content_sha256": locked["content_sha256"],
            })
        trust_mode = (
            "official" if package["scope"] == "official"
            else "local_trusted_code" if (package.get("trust") or {}).get("mode") == "local_development"
            else "publisher_trusted"
        )
        return {
            "package_id": manifest.package_id,
            "version": manifest.version,
            "scope": package["scope"],
            "manifest_sha256": package["manifest_sha256"],
            "content_sha256": package["content_sha256"],
            "publisher_id": manifest.publisher_id,
            "publisher_key_fingerprint": package["signature"]["key_id"],
            "publisher_public_key": package["signature"]["public_key"],
            "trust_mode": trust_mode,
            "dependencies": locked_dependencies,
            "contributions": [{
                "contribution_id": item["contribution_id"],
                "kind": item["kind"],
                "sha256": item["sha256"],
            } for item in package.get("contributions") or []],
            "function_contracts": [{
                "function_id": item["function_id"],
                "contract_version": item["contract_version"],
                "contract_fingerprint": item["contract_fingerprint"],
            } for item in package.get("functions") or []],
            "selected_variants": cls._select_variants(manifest, Path(str(package["path"]))),
        }

    @classmethod
    def enable(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if not package.get("valid") or not package.get("signature_verified"):
            raise RuntimeFailure("扩展校验未通过，不能启用")
        if not package.get("trusted"):
            raise RuntimeFailure("扩展尚未在本机信任；安装不等于信任")
        project, lock = cls._project_state(project_path)
        installed = [item for item in cls.packages(project_path)["packages"] if item.get("valid")]
        locked_by_id = {
            str(item.get("package_id") or ""): item for item in lock.get("extensions") or []
        }
        for dependency in package.get("dependencies") or []:
            locked_dependency = locked_by_id.get(dependency["package_id"])
            if locked_dependency is None:
                if dependency.get("optional"):
                    continue
                raise RuntimeFailure(f"请先显式启用依赖：{dependency['package_id']}")
            if not version_satisfies(str(locked_dependency.get("version") or ""), dependency["version"]):
                raise RuntimeFailure(f"依赖版本不满足约束：{dependency['package_id']} {dependency['version']}")
            if not any(
                item.get("package_id") == dependency["package_id"]
                and item.get("version") == locked_dependency.get("version")
                and item.get("content_sha256") == locked_dependency.get("content_sha256")
                for item in installed
            ):
                raise RuntimeFailure(f"锁定依赖内容不可用：{dependency['package_id']}")
        enabled = set(str(item) for item in project.get("enabled_extension_ids") or [])
        enabled.add(package_id)
        project["enabled_extension_ids"] = sorted(enabled)
        lock["extensions"] = sorted(
            [item for item in lock.get("extensions") or [] if item.get("package_id") != package_id]
            + [cls._lock_payload(project_path, package)],
            key=lambda item: str(item.get("package_id") or ""),
        )
        lock = EasyCodeLockV1.model_validate(lock).model_dump(mode="json")
        transaction_id = ProjectMutationTransaction.apply(project_path, {
            "project.json": _json_bytes(project),
            LOCK_FILE: _json_bytes(lock),
        })
        return {
            "enabled": True,
            "package_id": package_id,
            "scope": scope,
            "transaction_id": transaction_id,
            "lock": cls._lock_record(project_path, package_id),
        }

    @classmethod
    def disable(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        references = cls.references(project_path, package_id, scope)
        if references:
            raise RuntimeFailure(f"扩展仍有 {len(references)} 处项目/Player/资源引用，不能禁用")
        project, lock = cls._project_state(project_path)
        dependents = [
            item.get("package_id")
            for item in lock.get("extensions") or []
            if any(dep.get("package_id") == package_id for dep in item.get("dependencies") or [])
        ]
        if dependents:
            raise RuntimeFailure(f"扩展仍被已启用依赖使用：{dependents[0]}")
        project["enabled_extension_ids"] = sorted(
            item for item in set(project.get("enabled_extension_ids") or []) if item != package_id
        )
        lock["extensions"] = [item for item in lock.get("extensions") or [] if item.get("package_id") != package_id]
        lock = EasyCodeLockV1.model_validate(lock).model_dump(mode="json")
        transaction_id = ProjectMutationTransaction.apply(project_path, {
            "project.json": _json_bytes(project),
            LOCK_FILE: _json_bytes(lock),
        })
        return {"enabled": False, "package_id": package_id, "scope": scope, "transaction_id": transaction_id}

    @classmethod
    def delete_package(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if package.get("enabled"):
            raise RuntimeFailure("请先禁用扩展，再删除安装")
        references = cls.references(project_path, package_id, scope)
        if references:
            raise RuntimeFailure(f"扩展仍有 {len(references)} 处引用，不能删除")
        if scope == "official":
            raise RuntimeFailure("官方扩展不能删除")
        root = Path(str(package["path"])).resolve()
        if scope == "project":
            replacements = {
                path.relative_to(Path(project_path).resolve()).as_posix(): None
                for path in sorted(root.rglob("*"), reverse=True)
                if path.is_file()
            }
            transaction_id = ProjectMutationTransaction.apply(project_path, replacements)
            for directory in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
                with contextlib.suppress(OSError):
                    directory.rmdir()
            with contextlib.suppress(OSError):
                root.rmdir()
            return {"deleted": True, "package_id": package_id, "scope": scope, "transaction_id": transaction_id}
        trash = cls.trust_store_factory().root / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        destination = trash / f"{package_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        os.replace(root, destination)
        return {"deleted": True, "package_id": package_id, "scope": scope, "recoverable_path": str(destination)}

    @staticmethod
    def _zip_info(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        return info

    @classmethod
    def _build_python_variant(cls, root: Path, manifest: ExtensionManifestV1, variant: HostVariantV1) -> tuple[bytes, dict[str, Any]]:
        if not variant.development_entry:
            raise RuntimeFailure(f"Python 变体缺少 development_entry：{variant.variant_id}")
        source = resolve_package_path(root, variant.development_entry)
        if source.suffix.casefold() != ".py":
            raise RuntimeFailure("Python 开发入口必须是 .py 文件")
        with tempfile.TemporaryDirectory(prefix="EasyCodeExtensionBuild-") as temporary_name:
            target = Path(temporary_name) / "main.pyc"
            try:
                py_compile.compile(
                    str(source),
                    cfile=str(target),
                    dfile=f"extension://{manifest.package_id}/{variant.development_entry}",
                    doraise=True,
                    invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
                )
            except py_compile.PyCompileError as exc:
                raise RuntimeFailure(f"扩展 Python 编译失败：{exc.msg}") from exc
            compiled = target.read_bytes()
        runtime_path = "runtime/main.pyc"
        descriptor = {
            "format": RUNTIME_FORMAT,
            "package_id": manifest.package_id,
            "version": manifest.version,
            "variant_id": variant.variant_id,
            "host": variant.host,
            "runtime": variant.runtime,
            "targets": list(variant.targets),
            "module": runtime_path,
            "entrypoints": dict(variant.entrypoints),
            "files": [{"path": runtime_path, "size": len(compiled), "sha256": sha256_hex(compiled)}],
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(cls._zip_info("ecx-runtime.json"), _json_bytes(descriptor))
            archive.writestr(cls._zip_info(runtime_path), compiled)
        return output.getvalue(), descriptor

    @classmethod
    def _build_android_jvm_variant(
        cls,
        module_path: str | Path,
        manifest: ExtensionManifestV1,
        variant: HostVariantV1,
    ) -> tuple[bytes, dict[str, Any]]:
        source = Path(module_path).expanduser().resolve()
        if not source.is_file() or source.suffix.casefold() != ".jar":
            raise RuntimeFailure("请选择 Android 工具链已经编译完成的 .jar 文件")
        size = source.stat().st_size
        if size <= 0 or size > 256 * 1024 * 1024:
            raise RuntimeFailure("Android 扩展 JAR 必须大于 0 且不超过 256 MiB")
        try:
            with zipfile.ZipFile(source, "r") as archive:
                members = archive.infolist()
                names: set[str] = set()
                total = 0
                for member in members:
                    name = member.filename.replace("\\", "/")
                    directory = member.is_dir() or name.endswith("/")
                    canonical_name = name[:-1] if directory and name.endswith("/") else name
                    parts = canonical_name.split("/")
                    if (
                        name != member.filename
                        or name.startswith("/")
                        or not canonical_name
                        or any(part in {"", ".", ".."} for part in parts)
                        or name in names
                    ):
                        raise RuntimeFailure(f"Android 扩展 JAR 包含不安全或重复路径：{name}")
                    names.add(name)
                    if directory:
                        continue
                    total += max(0, member.file_size)
                    if total > 512 * 1024 * 1024 or len(names) > 65_535:
                        raise RuntimeFailure("Android 扩展 JAR 解压体积或文件数量超过安全上限")
                    lowered = name.casefold()
                    if PurePosixPath(lowered).suffix in {".java", ".kt", ".kts", ".so", ".dex"}:
                        raise RuntimeFailure(f"Android Kotlin/JVM JAR 包含源码、原生库或预编译 DEX：{name}")
                    if lowered.startswith("meta-inf/") and lowered.endswith((".sf", ".rsa", ".dsa", ".ec")):
                        raise RuntimeFailure(f"Android 扩展 JAR 不能携带会在 APK 转换后失效的 JAR 签名：{name}")
                for function_id, class_name in variant.entrypoints.items():
                    expected = class_name.replace(".", "/") + ".class"
                    if expected not in names:
                        raise RuntimeFailure(f"Android 扩展入口类不存在：{function_id} -> {class_name}")
        except RuntimeFailure:
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeFailure(f"Android 扩展模块不是有效 JAR：{exc}") from exc
        module = source.read_bytes()
        runtime_path = "runtime/module.jar"
        descriptor = {
            "format": RUNTIME_FORMAT,
            "package_id": manifest.package_id,
            "version": manifest.version,
            "variant_id": variant.variant_id,
            "host": variant.host,
            "runtime": variant.runtime,
            "minimum_android_api": variant.minimum_android_api,
            "targets": list(variant.targets),
            "module": runtime_path,
            "entrypoints": dict(variant.entrypoints),
            "files": [{"path": runtime_path, "size": len(module), "sha256": sha256_hex(module)}],
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(cls._zip_info("ecx-runtime.json"), _json_bytes(descriptor))
            archive.writestr(cls._zip_info(runtime_path), module)
        return output.getvalue(), descriptor

    @classmethod
    def seal_android_jvm(
        cls,
        project_path: str,
        package_id: str,
        scope: str,
        *,
        variant_id: str,
        module_path: str,
    ) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if not package.get("trusted"):
            raise RuntimeFailure("导入可执行 JAR 前必须先明确本机信任这个扩展发布者")
        if package.get("enabled"):
            raise RuntimeFailure("请先停用扩展，再替换 Android 可执行模块")
        root = Path(str(package["path"])).resolve()
        manifest = ExtensionManifestV1.model_validate(package["manifest"])
        variants = list(manifest.host_variants)
        matches = [item for item in variants if item.variant_id == variant_id]
        if len(matches) != 1:
            raise RuntimeFailure(f"找不到唯一 Android 宿主变体：{variant_id}")
        variant = matches[0]
        if variant.host != "android_native" or variant.runtime != "android-kotlin-v1":
            raise RuntimeFailure(f"变体 {variant_id} 不是 Android Kotlin/JVM 变体")
        if not variant.entrypoints:
            raise RuntimeFailure(f"Android 变体 {variant_id} 没有声明任何函数入口")
        try:
            identity = cls.signing_key_store_factory().get_or_create(f"extension:{manifest.publisher_id}")
        except Exception as exc:
            raise RuntimeFailure(f"扩展发布签名身份不可用：{exc}") from exc
        if identity.key_id != package["signature"]["key_id"]:
            raise RuntimeFailure("当前本机签名身份与扩展发布者不匹配")

        content, descriptor = cls._build_android_jvm_variant(module_path, manifest, variant)
        artifact_relative = f"dist/{variant.variant_id}.ecxrt"
        signature_relative = f"dist/{variant.variant_id}.ecxrt.sig"
        signature = create_artifact_signature(content, manifest=manifest, variant=variant, identity=identity)
        manifest_value = manifest.model_dump(mode="json", exclude_none=True)
        for item in manifest_value["variants"]:
            if item["variant_id"] == variant.variant_id:
                item["artifact"] = {
                    "path": artifact_relative,
                    "format": RUNTIME_FORMAT,
                    "sha256": sha256_hex(content),
                    "signature": signature_relative,
                }
        updated_manifest = ExtensionManifestV1.model_validate(manifest_value)
        replacements = {
            artifact_relative: content,
            signature_relative: _json_bytes(signature),
            MANIFEST_FILE: _json_bytes(updated_manifest.model_dump(mode="json", exclude_none=True)),
            MANIFEST_SIGNATURE_FILE: _json_bytes(sign_manifest(root, updated_manifest, identity)),
        }
        with tempfile.TemporaryDirectory(prefix="EasyCodeAndroidExtensionSeal-") as temporary_name:
            candidate = Path(temporary_name) / package_id
            shutil.copytree(root, candidate)
            for relative, payload in replacements.items():
                destination = candidate.joinpath(*relative.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
            candidate_manifest, canonical = load_manifest(candidate)
            candidate_signature = verify_manifest_signature(candidate, candidate_manifest, canonical)
            load_function_contracts(candidate, candidate_manifest)
            candidate_variant = next(
                item for item in candidate_manifest.host_variants
                if item.variant_id == variant.variant_id
            )
            validate_sealed_artifact(candidate, candidate_manifest, candidate_variant, candidate_signature)
        if scope == "project":
            ProjectMutationTransaction.apply(project_path, {
                f"extensions/{package_id}/{relative}": payload
                for relative, payload in replacements.items()
            })
        else:
            for relative, payload in replacements.items():
                _atomic_write(root.joinpath(*relative.split("/")), payload)
        refreshed = cls.package(project_path, package_id, scope)
        if not refreshed.get("valid") or not refreshed.get("signature_verified"):
            raise RuntimeFailure("Android 扩展密封完成后自检失败，原项目事务未产生可执行入口")
        return {
            "sealed": True,
            "package_id": package_id,
            "scope": scope,
            "variant_id": variant.variant_id,
            "minimum_android_api": variant.minimum_android_api,
            "module_sha256": sha256_hex(Path(module_path).expanduser().resolve().read_bytes()),
            "artifact": {
                "format": RUNTIME_FORMAT,
                "path": artifact_relative,
                "signature_path": signature_relative,
                "sha256": sha256_hex(content),
                "size": len(content),
                "descriptor": descriptor,
            },
            "package": refreshed,
        }

    @classmethod
    def build_sealed(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if not package.get("trusted"):
            raise RuntimeFailure("只有本机已信任扩展可以构建密封产物")
        root = Path(str(package["path"])).resolve()
        manifest = ExtensionManifestV1.model_validate(package["manifest"])
        try:
            identity = cls.signing_key_store_factory().get_or_create(
                f"extension:{manifest.publisher_id}"
            )
        except Exception as exc:
            raise RuntimeFailure(f"扩展发布签名身份不可用：{exc}") from exc
        if identity.key_id != package["signature"]["key_id"]:
            raise RuntimeFailure("当前本机签名身份与扩展发布者不匹配")
        manifest_value = manifest.model_dump(mode="json", exclude_none=True)
        replacements: dict[str, bytes] = {}
        artifacts: list[dict[str, Any]] = []
        for index, variant_value in enumerate(manifest_value["variants"]):
            variant = HostVariantV1.model_validate(variant_value)
            if variant.runtime != "python-worker-3.12":
                if variant.sealed_artifact:
                    artifacts.append(validate_sealed_artifact(root, manifest, variant, package["signature"]))
                    continue
                raise RuntimeFailure(f"{variant.variant_id} 需要由对应原生工具链提供密封产物")
            content, descriptor = cls._build_python_variant(root, manifest, variant)
            artifact_relative = f"dist/{variant.variant_id}.ecxrt"
            signature_relative = f"dist/{variant.variant_id}.ecxrt.sig"
            signature = create_artifact_signature(content, manifest=manifest, variant=variant, identity=identity)
            replacements[artifact_relative] = content
            replacements[signature_relative] = _json_bytes(signature)
            variant_value["artifact"] = {
                "path": artifact_relative,
                "format": RUNTIME_FORMAT,
                "sha256": sha256_hex(content),
                "signature": signature_relative,
            }
            manifest_value["variants"][index] = variant_value
            artifacts.append({
                "format": RUNTIME_FORMAT,
                "path": artifact_relative,
                "signature_path": signature_relative,
                "sha256": sha256_hex(content),
                "size": len(content),
                "signature": signature,
                "descriptor": descriptor,
            })
        updated_manifest = ExtensionManifestV1.model_validate(manifest_value)
        replacements[MANIFEST_FILE] = _json_bytes(updated_manifest.model_dump(mode="json", exclude_none=True))
        replacements[MANIFEST_SIGNATURE_FILE] = _json_bytes(sign_manifest(root, updated_manifest, identity))
        if scope == "project":
            ProjectMutationTransaction.apply(project_path, {
                f"extensions/{package_id}/{relative}": content for relative, content in replacements.items()
            })
        else:
            for relative, content in replacements.items():
                _atomic_write(root.joinpath(*relative.split("/")), content)
        refreshed = cls.package(project_path, package_id, scope)
        if refreshed.get("enabled"):
            cls.enable(project_path, package_id, scope)
        return {
            "built": True,
            "package_id": package_id,
            "scope": scope,
            "artifacts": artifacts,
            "package": cls.package(project_path, package_id, scope),
        }

    @classmethod
    def open_folder(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        path = Path(str(package["path"])).resolve()
        if os.name != "nt" or not hasattr(os, "startfile"):
            raise RuntimeFailure("当前宿主不支持打开外部 IDE 文件夹")
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError as exc:
            raise RuntimeFailure(f"无法打开扩展文件夹：{exc}") from exc
        return {"opened": True, "path": str(path)}

    @classmethod
    def contract_tests(cls, project_path: str, package_id: str, scope: str) -> dict[str, Any]:
        package = cls.package(project_path, package_id, scope)
        if not package.get("trusted"):
            raise RuntimeFailure("契约测试会执行开发代码，请先明确本机信任")
        results: list[dict[str, Any]] = []
        for contract in package.get("function_contracts") or []:
            for test in contract.get("contract_tests") or []:
                try:
                    actual = cls.invoke(
                        project_path,
                        contract["function_id"],
                        dict(test.get("arguments") or {}),
                        {},
                        lambda: False,
                        lambda _level, _message: None,
                    )
                    passed = actual == test.get("expected")
                    results.append({
                        "test_id": test["test_id"],
                        "function_id": contract["function_id"],
                        "passed": passed,
                        "expected": test.get("expected"),
                        "actual": actual,
                    })
                except Exception as exc:
                    results.append({
                        "test_id": test["test_id"],
                        "function_id": contract["function_id"],
                        "passed": False,
                        "error": str(exc),
                    })
        return {
            "passed": all(item["passed"] for item in results),
            "tests": results,
            "total": len(results),
        }

    @classmethod
    def publish_closure(cls, project_path: str) -> dict[str, Any]:
        project, lock = cls._project_state(project_path)
        enabled = set(project.get("enabled_extension_ids") or [])
        packages: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for record in lock.get("extensions") or []:
            package_id = str(record.get("package_id") or "")
            if package_id not in enabled:
                continue
            try:
                package = cls.package(project_path, package_id, str(record.get("scope") or ""))
                if not package.get("valid") or not package.get("trusted") or not package.get("lock_current"):
                    raise RuntimeFailure("扩展未通过签名、信任或锁一致性检查")
                variants = []
                seen_variant_ids: set[str] = set()
                for selected in record.get("selected_variants") or []:
                    if not selected.get("artifact_sha256") or not selected.get("artifact_signature_sha256"):
                        raise RuntimeFailure(f"变体尚未构建密封产物：{selected.get('variant_id')}")
                    if selected.get("variant_id") in seen_variant_ids:
                        continue
                    variant = next(
                        item for item in package.get("host_variants") or []
                        if item.get("variant_id") == selected.get("variant_id")
                    )
                    validated = validate_sealed_artifact(
                        Path(package["path"]),
                        ExtensionManifestV1.model_validate(package["manifest"]),
                        HostVariantV1.model_validate(variant),
                        package["signature"],
                    )
                    if validated["sha256"] != selected["artifact_sha256"]:
                        raise RuntimeFailure(f"锁定密封产物哈希漂移：{selected.get('variant_id')}")
                    signature_payload = resolve_package_path(
                        Path(package["path"]), validated["signature_path"]
                    ).read_bytes()
                    if sha256_hex(signature_payload) != selected["artifact_signature_sha256"]:
                        raise RuntimeFailure(f"锁定密封签名哈希漂移：{selected.get('variant_id')}")
                    variants.append(validated)
                    seen_variant_ids.add(str(selected.get("variant_id") or ""))
                packages.append({"lock": copy.deepcopy(record), "package": package, "artifacts": variants})
            except Exception as exc:
                errors.append({"source": package_id, "message": str(exc)})
        return {"packages": packages, "errors": errors, "lock": lock}

    @classmethod
    def invoke(
        cls,
        project_path: str,
        function_id: str,
        arguments: dict[str, Any],
        variables: dict[str, Any],
        cancelled: Callable[[], bool],
        emit: Callable[[str, str], None],
    ) -> Any:
        runtime_root = Path(project_path).resolve()
        published_lock_path = runtime_root / "runtime" / LOCK_FILE
        if published_lock_path.is_file():
            try:
                lock = load_easycode_lock(published_lock_path)
                published: tuple[dict[str, Any], Any, Any] | None = None
                for record in lock.extensions:
                    descriptor_path = runtime_root / "runtime" / "extensions" / record.package_id / "extension.json"
                    if not descriptor_path.is_file():
                        raise ExtensionSchemaError(f"缺少发布扩展描述：{record.package_id}")
                    descriptor = PublishedExtensionV1.model_validate(_read_json(descriptor_path))
                    validate_published_extension(runtime_root, descriptor, record)
                    contract_model = next(
                        (item for item in descriptor.function_contracts if item.function_id == function_id),
                        None,
                    )
                    if contract_model is None:
                        continue
                    variant_model = next(
                        (
                            item for item in descriptor.variants
                            if item.host == "windows"
                            and item.runtime == "python-worker-3.12"
                            and function_id in item.entrypoints
                        ),
                        None,
                    )
                    published = (descriptor.model_dump(mode="json"), contract_model, variant_model)
                    break
                if published is None:
                    raise RuntimeFailure("发布包未锁定该扩展函数", error_id="extension.not_available")
                _descriptor_value, contract_model, published_variant = published
                if published_variant is None:
                    raise RuntimeFailure("当前宿主没有发布的扩展变体", error_id="extension.variant_missing")
                contract = contract_model.model_dump(mode="json")
                request = {
                    "mode": "sealed",
                    "artifact_path": str(resolve_package_path(runtime_root, published_variant.artifact_path)),
                    "entrypoint": published_variant.entrypoints[function_id],
                    "arguments": arguments,
                    "variables": variables,
                }
                worker_cwd = runtime_root
            except RuntimeFailure:
                raise
            except Exception as exc:
                raise RuntimeFailure(
                    f"发布扩展运行闭包校验失败：{exc}", error_id="extension.runtime_invalid",
                ) from exc
        else:
            package = next(
                (item for item in cls.packages(project_path)["packages"] if any(
                    function.get("function_id") == function_id for function in item.get("functions") or []
                )),
                None,
            )
            if package is None or not all(package.get(key) for key in ("enabled", "trusted", "valid", "lock_current")):
                raise RuntimeFailure("扩展函数未启用、未信任或锁已变化", error_id="extension.not_available")
            contract = next(item for item in package["function_contracts"] if item["function_id"] == function_id)
            manifest = ExtensionManifestV1.model_validate(package["manifest"])
            variant = next(
                (item for item in manifest.host_variants if item.runtime == "python-worker-3.12" and function_id in item.entrypoints),
                None,
            )
            if variant is None or not variant.development_entry:
                raise RuntimeFailure("当前宿主没有可执行扩展变体", error_id="extension.variant_missing")
            entry_path = resolve_package_path(Path(package["path"]), variant.development_entry)
            request = {
                "mode": "development",
                "entry_path": str(entry_path),
                "entrypoint": variant.entrypoints[function_id],
                "arguments": arguments,
                "variables": variables,
            }
            worker_cwd = Path(package["path"])
        try:
            parameter_names = {
                str(item.get("parameter_id") or ""): str(item.get("name") or "")
                for item in contract.get("parameters") or []
            }
            unknown_arguments = sorted(set(arguments) - set(parameter_names))
            if unknown_arguments:
                raise RuntimeFailure(
                    f"扩展参数不在锁定契约中：{unknown_arguments[0]}",
                    error_id="extension.arguments_invalid",
                )
            request["arguments"] = {
                parameter_names[parameter_id]: value
                for parameter_id, value in arguments.items()
                if parameter_names.get(parameter_id)
            }
            request["variables"] = {
                key: value
                for key, value in variables.items()
                if not str(key).startswith("__")
            }
            project_variables = variables.get("__project__")
            if isinstance(project_variables, dict):
                request["variables"]["project"] = project_variables
            encoded = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise RuntimeFailure(f"扩展参数无法序列化：{exc}", error_id="extension.arguments_invalid") from exc
        worker = Path(__file__).with_name("extension_worker_v6.py")
        worker_command = [sys.executable, str(worker)]
        worker_environment = os.environ.copy()
        worker_environment["PYTHONUTF8"] = "1"
        worker_environment["PYTHONIOENCODING"] = "utf-8"
        worker_environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            worker_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(worker_cwd),
            env=worker_environment,
        )
        deadline = time.monotonic() + (int(contract.get("timeout_ms") or 30_000) / 1000)
        input_value: bytes | None = encoded
        while True:
            if cancelled():
                process.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=1)
                if process.poll() is None:
                    process.kill()
                raise RuntimeFailure("扩展调用已取消", error_id="runtime.cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait(timeout=2)
                raise RuntimeFailure("扩展 Worker 执行超时", error_id="extension.timeout")
            try:
                stdout, stderr = process.communicate(input=input_value, timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                input_value = None
        try:
            response = json.loads(stdout.decode("utf-8"))
        except Exception as exc:
            detail = stderr.decode("utf-8", errors="replace").strip()[:1000]
            raise RuntimeFailure(
                f"扩展 Worker 返回无效数据：{detail or exc}", error_id="extension.worker_protocol",
            ) from exc
        for log in response.get("logs") or []:
            if isinstance(log, dict):
                emit(str(log.get("level") or "info"), str(log.get("message") or ""))
        if not response.get("ok"):
            error = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise RuntimeFailure(
                str(error.get("message") or "扩展 Worker 执行失败"),
                error_id=str(error.get("code") or "extension.worker_failed"),
            )
        return response.get("result")


class VNextExtensionContractRegistry:
    """Dynamic registry overlay: official contracts plus the active lock only."""

    def __init__(self, context: VNextWorkspaceContext, official: Any) -> None:
        self._context = context
        self._official = official

    def get(self, function_id: str) -> Any | None:
        official = get_contract(self._official, function_id)
        if official is not None:
            return official
        workspace = self._context.active_model()
        if workspace is None:
            return None
        definitions, _errors = VNextExtensionRegistry.definitions(workspace.project_path)
        definition = next((item for item in definitions if item.get("function_id") == function_id), None)
        if definition is None:
            return None
        parameters = []
        for item in definition.get("parameters") or []:
            fields = {
                "parameter_id": item["parameter_id"],
                "name": item["name"],
                "display_name": item["display_name"],
                "value_type": item["value_type"],
                "required": bool(item.get("required", True)),
            }
            if item.get("has_default"):
                fields["default"] = item.get("default")
            parameters.append(ParameterContract(**fields))
        return FunctionContract(
            function_id=definition["function_id"],
            qualified_name=definition["qualified_name"],
            opcode="call.extension",
            parameters=tuple(parameters),
            return_type=definition.get("return_type") or "unit",
            platforms=tuple(definition.get("platforms") or ()),
            capabilities=tuple(definition.get("permissions") or ()),
            contract_version=definition.get("contract_version") or "1.0.0",
            contract_fingerprint=definition.get("contract_fingerprint") or "",
            minimum_android_api=int(definition.get("minimum_android_api") or 21),
            timeout_ms=int(definition.get("timeout_ms") or 30_000),
        )

    def require(self, function_id: str) -> Any:
        contract = self.get(function_id)
        if contract is None:
            raise KeyError(function_id)
        return contract


__all__ = [
    "ExtensionTrustStore",
    "VNextExtensionContractRegistry",
    "VNextExtensionRegistry",
]
