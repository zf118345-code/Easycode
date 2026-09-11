"""Strict, signed contracts for EasyCode format-6 extension packages.

This module deliberately contains no discovery or execution policy.  It owns
the wire formats that are shared by the IDE, publisher and Player loader.  A
package is executable only after the application service has separately
decided that it is installed, enabled and trusted.
"""

from __future__ import annotations

import base64
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .bundle_signing_v6 import (
    SIGNATURE_ALGORITHM,
    AuthorSigningIdentity,
    canonical_json_bytes,
    public_key_id,
    sha256_hex,
)


MANIFEST_FILE = "easycode-extension.json"
MANIFEST_SIGNATURE_FILE = "easycode-extension.sig"
LOCK_FILE = "easycode.lock"
RUNTIME_FORMAT = "ecx-runtime-1"
MANIFEST_VERSION = 1
LOCK_VERSION = 1

PACKAGE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")
STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
JVM_BINARY_NAME_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?:\$[A-Za-z_][A-Za-z0-9_]*)*$"
)

HostKind = Literal["windows", "android_native"]
TargetKind = Literal["windows", "android_adb", "android_native", "none"]
RuntimeKind = Literal["python-worker-3.12", "native-worker-v1", "android-kotlin-v1"]

# Stable review/host-capability vocabulary for executable extensions.  These
# are not an OS sandbox: trusted code can still call APIs available to the
# current process.  The registry prevents meaningless permission strings from
# entering signatures and gives publishers one authoritative Android floor and
# manifest projection for every declared capability.
EXTENSION_PERMISSION_SPECS: dict[str, dict[str, Any]] = {
    "filesystem.read": {
        "display_name": "读取文件",
        "minimum_android_api": 21,
        "android_manifest_permissions": (),
    },
    "filesystem.write": {
        "display_name": "写入文件",
        "minimum_android_api": 21,
        "android_manifest_permissions": (),
    },
    "host.launch_application": {
        "display_name": "启动应用",
        "minimum_android_api": 21,
        "android_manifest_permissions": (),
    },
    "messaging": {
        "display_name": "EasyCode 消息与局域网协作",
        "minimum_android_api": 23,
        "android_manifest_permissions": (
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.ACCESS_WIFI_STATE",
            "android.permission.CHANGE_WIFI_MULTICAST_STATE",
        ),
    },
    "network": {
        "display_name": "网络访问",
        "minimum_android_api": 21,
        "android_manifest_permissions": (
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
        ),
    },
    "target.control.read": {
        "display_name": "读取目标控件",
        "minimum_android_api": 21,
        "android_manifest_permissions": (),
    },
    "target.frame.read": {
        "display_name": "读取目标画面",
        "minimum_android_api": 21,
        "android_manifest_permissions": (
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION",
        ),
    },
    "target.input": {
        "display_name": "向目标发送输入",
        "minimum_android_api": 24,
        "android_manifest_permissions": (),
    },
}


def extension_android_manifest_permissions(permission_ids: Any) -> tuple[str, ...]:
    return tuple(sorted({
        manifest_permission
        for permission_id in permission_ids
        for manifest_permission in EXTENSION_PERMISSION_SPECS.get(str(permission_id), {}).get(
            "android_manifest_permissions", ()
        )
    }))


def _validated_extension_permissions(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError("permissions 不能重复")
    unknown = sorted(set(value) - set(EXTENSION_PERMISSION_SPECS))
    if unknown:
        raise ValueError(f"未知扩展权限 ID：{unknown[0]}")
    return value


class ExtensionSchemaError(ValueError):
    """A package or sealed artifact is not safe or compatible."""


class _StrictModel(BaseModel):
    # JSON has arrays rather than tuples.  Pydantic may normalise those arrays
    # to immutable tuples, but it must never accept an undeclared field.
    model_config = ConfigDict(extra="forbid", validate_by_alias=True, serialize_by_alias=True)


def _safe_relative_path(value: str, *, label: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    parsed = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or parsed.is_absolute()
        or ".." in parsed.parts
        or any(part in {"", "."} for part in parsed.parts)
        or (parsed.parts and ":" in parsed.parts[0])
    ):
        raise ValueError(f"{label}必须是包内安全相对路径")
    return parsed.as_posix()


def resolve_package_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    """Resolve one package path without following a link outside its root."""

    normalized = _safe_relative_path(relative, label="扩展路径")
    package_root = root.resolve()
    candidate = package_root.joinpath(*PurePosixPath(normalized).parts)
    current = package_root
    for part in PurePosixPath(normalized).parts:
        current = current / part
        if current.is_symlink():
            raise ExtensionSchemaError(f"扩展包不允许符号链接：{normalized}")
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise ExtensionSchemaError(f"扩展文件不存在：{normalized}") from exc
    if resolved != package_root and package_root not in resolved.parents:
        raise ExtensionSchemaError(f"扩展路径越出包目录：{normalized}")
    return resolved


class DependencyV1(_StrictModel):
    package_id: str = Field(min_length=3, max_length=200)
    version: str = Field(min_length=5, max_length=160)
    optional: bool = False

    @field_validator("package_id")
    @classmethod
    def validate_package_id(cls, value: str) -> str:
        if not PACKAGE_ID_RE.fullmatch(value):
            raise ValueError("依赖 package_id 格式无效")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        normalized = " ".join(str(value).split())
        parts = normalized.split(" ")
        if not all(
            SEMVER_RE.fullmatch(part)
            or re.fullmatch(r"(?:>=|<=|>|<|==)" + SEMVER_RE.pattern[1:-1], part)
            for part in parts
        ):
            raise ValueError("依赖 version 必须是精确版本或受支持的语义版本范围")
        return normalized


class DisplayV1(_StrictModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    homepage: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("homepage")
    @classmethod
    def validate_homepage(cls, value: str | None) -> str | None:
        if value is not None and not re.match(r"^https?://", value, re.IGNORECASE):
            raise ValueError("display.homepage 只允许 http/https URL")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            canonical_json_bytes(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("display.metadata 必须可确定性序列化") from exc
        return value


class RequiresV1(_StrictModel):
    easycode: str = Field(min_length=5, max_length=160)
    program_schema: Literal[1]
    ecir: Literal[1]


class NetworkRuleV1(_StrictModel):
    rule_id: str = Field(min_length=3, max_length=200)
    hosts: tuple[str, ...] = Field(min_length=1)
    ports: tuple[int, ...] = ()
    protocols: tuple[Literal["http", "https", "tcp", "udp"], ...] = ()

    @field_validator("rule_id")
    @classmethod
    def validate_rule_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("network.rules.rule_id 格式无效")
        return value

    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("network.rules.hosts 不能为空或重复")
        return value

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(value) != len(set(value)) or any(item < 1 or item > 65535 for item in value):
            raise ValueError("network.rules.ports 必须是唯一的有效端口")
        return value


class NetworkV1(_StrictModel):
    level: Literal["none", "local_lan", "public"] = "none"
    rules: tuple[NetworkRuleV1, ...] = ()

    @model_validator(mode="after")
    def validate_level(self) -> "NetworkV1":
        if self.level == "none" and self.rules:
            raise ValueError("network.level 为 none 时不能声明网络规则")
        identifiers = [item.rule_id for item in self.rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("network.rules.rule_id 不能重复")
        return self


class ContributionV1(_StrictModel):
    contribution_id: str = Field(min_length=3, max_length=240)
    path: str = Field(min_length=1, max_length=500)
    variant_bindings: tuple[str, ...] = ()

    @field_validator("contribution_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("contribution_id 格式无效")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="贡献路径")


class ContributionsV1(_StrictModel):
    function_contracts: tuple[ContributionV1, ...] = ()
    data_schemas: tuple[ContributionV1, ...] = ()
    workspaces: tuple[ContributionV1, ...] = ()
    compiler_steps: tuple[ContributionV1, ...] = ()
    runtime_modules: tuple[ContributionV1, ...] = ()
    player_modules: tuple[ContributionV1, ...] = ()
    harness_adapters: tuple[ContributionV1, ...] = ()
    target_drivers: tuple[ContributionV1, ...] = ()

    def all(self) -> tuple[tuple[str, ContributionV1], ...]:
        result: list[tuple[str, ContributionV1]] = []
        for kind in type(self).model_fields:
            result.extend((kind, item) for item in getattr(self, kind))
        return tuple(result)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ContributionsV1":
        identifiers = [item.contribution_id for _kind, item in self.all()]
        if not identifiers:
            raise ValueError("扩展至少需要一个贡献")
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("contribution_id 在整个包内必须唯一")
        return self


class ArtifactV1(_StrictModel):
    path: str = Field(min_length=1, max_length=500)
    format: Literal["ecx-runtime-1"]
    sha256: str
    signature: str = Field(min_length=1, max_length=500)

    @field_validator("path", "signature")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="密封产物路径")

    @field_validator("sha256")
    @classmethod
    def validate_sha(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("artifact.sha256 必须是小写 SHA-256")
        return value


class HostVariantV1(_StrictModel):
    variant_id: str = Field(min_length=3, max_length=200)
    host: HostKind
    runtime: RuntimeKind
    minimum_android_api: int | None = Field(default=None, ge=21, le=37)
    targets: tuple[TargetKind, ...] = Field(min_length=1)
    development_entry: str | None = Field(default=None, max_length=500)
    entrypoints: dict[str, str] = Field(default_factory=dict)
    artifact: ArtifactV1 | None = None

    @field_validator("variant_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("variant_id 格式无效")
        return value

    @field_validator("development_entry")
    @classmethod
    def validate_optional_path(cls, value: str | None) -> str | None:
        return _safe_relative_path(value, label="变体路径") if value is not None else None

    @field_validator("entrypoints")
    @classmethod
    def validate_entrypoints(cls, value: dict[str, str]) -> dict[str, str]:
        for function_id, entry in value.items():
            if not STABLE_ID_RE.fullmatch(function_id):
                raise ValueError("entrypoints 包含无效 function_id")
            if not isinstance(entry, str) or not entry or len(entry) > 500:
                raise ValueError("entrypoints 入口名称无效")
        return value

    @model_validator(mode="after")
    def validate_compatibility(self) -> "HostVariantV1":
        if len(self.targets) != len(set(self.targets)):
            raise ValueError("变体 targets 不能重复")
        if self.host == "android_native" and set(self.targets) - {"android_native", "none"}:
            raise ValueError("Android 本机宿主不能声明 Windows/ADB 目标")
        if self.host == "windows" and "android_native" in self.targets:
            raise ValueError("Windows 宿主不能冒充 Android 本机运行时")
        if self.runtime == "python-worker-3.12" and self.host != "windows":
            raise ValueError("Python Worker 仅允许 Windows 宿主变体")
        if self.runtime == "android-kotlin-v1" and self.host != "android_native":
            raise ValueError("Kotlin 运行产物仅允许 Android 本机宿主")
        if self.host == "android_native" and self.minimum_android_api is None:
            raise ValueError("Android 本机变体必须声明 minimum_android_api")
        if self.host != "android_native" and self.minimum_android_api is not None:
            raise ValueError("minimum_android_api 只允许 Android 本机变体声明")
        if self.development_entry is not None and self.runtime != "python-worker-3.12":
            raise ValueError("development_entry 只允许受信任的 Python 开发变体")
        if self.runtime == "android-kotlin-v1":
            if any(not JVM_BINARY_NAME_RE.fullmatch(entry) for entry in self.entrypoints.values()):
                raise ValueError("Android Kotlin 入口必须是 JVM 二进制类名")
        elif any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry) for entry in self.entrypoints.values()):
            raise ValueError("Windows 入口只能声明模块内函数名")
        return self

    @property
    def sealed_artifact(self) -> str | None:
        return self.artifact.path if self.artifact else None

    @property
    def sealed_signature(self) -> str | None:
        return self.artifact.signature if self.artifact else None

    @property
    def sealed_sha256(self) -> str | None:
        return self.artifact.sha256 if self.artifact else None


class ExtensionDataV1(_StrictModel):
    schema_path: str = Field(alias="schema")
    schema_version: int = Field(ge=1)

    @field_validator("schema_path")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        return _safe_relative_path(value, label="扩展数据 Schema")


class LicenseV1(_StrictModel):
    id: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=500)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="许可证路径")


class ExtensionManifestV1(_StrictModel):
    manifest_version: Literal[1]
    package_id: str = Field(min_length=3, max_length=200)
    publisher_id: str = Field(min_length=3, max_length=160)
    version: str = Field(min_length=5, max_length=80)
    display: DisplayV1
    tier: Literal["function", "feature", "target_driver"]
    requires: RequiresV1
    activation: tuple[Literal[
        "on_project_enable", "on_function_call", "on_workspace_open", "on_run_start"
    ], ...] = ()
    permissions: tuple[str, ...] = ()
    network: NetworkV1 = Field(default_factory=NetworkV1)
    dependencies: tuple[DependencyV1, ...] = ()
    contributions: ContributionsV1
    variants: tuple[HostVariantV1, ...]
    data: ExtensionDataV1 | None = None
    licenses: tuple[LicenseV1, ...] = ()

    @field_validator("package_id", "publisher_id")
    @classmethod
    def validate_package_id(cls, value: str) -> str:
        if not PACKAGE_ID_RE.fullmatch(value):
            raise ValueError("package_id / publisher_id 必须是反向域名式小写稳定 ID")
        return value

    @field_validator("version")
    @classmethod
    def validate_versions(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("版本必须是完整语义版本")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_extension_permissions(value)

    @model_validator(mode="after")
    def validate_uniqueness(self) -> "ExtensionManifestV1":
        if not self.package_id.startswith(self.publisher_id + "."):
            raise ValueError("package_id 必须位于 publisher_id 命名空间下")
        collections = (
            ("依赖", [item.package_id for item in self.dependencies]),
            ("宿主变体", [item.variant_id for item in self.variants]),
            ("许可证", [item.id for item in self.licenses]),
            ("激活入口", list(self.activation)),
        )
        for label, identifiers in collections:
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{label} ID 不能重复")
        if not self.variants:
            raise ValueError("扩展至少需要一个宿主变体")
        if self.network.level != "none" and "network" not in self.permissions:
            raise ValueError("声明网络访问的扩展必须同时声明 network 权限")
        known_variants = {item.variant_id for item in self.variants}
        for _kind, contribution in self.contributions.all():
            unknown = set(contribution.variant_bindings) - known_variants
            if unknown:
                raise ValueError(f"贡献绑定未知宿主变体：{sorted(unknown)[0]}")
        return self

    @property
    def host_variants(self) -> tuple[HostVariantV1, ...]:
        return self.variants

    @property
    def display_name(self) -> str:
        return self.display.name

    @property
    def description(self) -> str:
        return self.display.description


class ParameterContractV1(_StrictModel):
    parameter_id: str = Field(min_length=3, max_length=240)
    name: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    value_type: str = Field(min_length=1, max_length=240)
    required: bool = True
    default: Any = None
    control: dict[str, Any] | None = None

    @field_validator("parameter_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("parameter_id 格式无效")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("参数 name 必须是稳定英文标识符")
        return value

    @model_validator(mode="after")
    def validate_default(self) -> "ParameterContractV1":
        if self.required and self.default is not None:
            raise ValueError("必填参数不能同时声明默认值")
        try:
            canonical_json_bytes(self.default)
            canonical_json_bytes(self.control) if self.control is not None else None
        except (TypeError, ValueError) as exc:
            raise ValueError("参数默认值与 Control 必须可确定性序列化") from exc
        return self


class ContractTestV1(_StrictModel):
    test_id: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None


class ExtensionFunctionContractV1(_StrictModel):
    function_id: str = Field(min_length=3, max_length=240)
    qualified_name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=4000)
    statement_summary: str = Field(default="", max_length=500)
    contract_version: str = Field(default="1.0.0", min_length=5, max_length=80)
    parameters: tuple[ParameterContractV1, ...] = ()
    return_type: str = Field(default="unit", min_length=1, max_length=240)
    targets: tuple[TargetKind, ...] = ()
    permissions: tuple[str, ...] = ()
    timeout_ms: int = Field(default=30_000, ge=50, le=600_000)
    contract_tests: tuple[ContractTestV1, ...] = ()

    @field_validator("function_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("function_id 格式无效")
        return value

    @field_validator("contract_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("contract_version 必须是完整语义版本")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_extension_permissions(value)

    @model_validator(mode="after")
    def validate_uniqueness(self) -> "ExtensionFunctionContractV1":
        parameter_ids = [item.parameter_id for item in self.parameters]
        parameter_names = [item.name for item in self.parameters]
        test_ids = [item.test_id for item in self.contract_tests]
        if len(parameter_ids) != len(set(parameter_ids)) or len(parameter_names) != len(set(parameter_names)):
            raise ValueError("函数参数 ID 与 name 不能重复")
        if len(test_ids) != len(set(test_ids)):
            raise ValueError("契约测试 ID 不能重复")
        if len(self.targets) != len(set(self.targets)):
            raise ValueError("函数 targets 不能重复")
        if self.statement_summary:
            names = set(parameter_names)
            referenced = re.findall(r"\{([^{}]+)\}", self.statement_summary)
            if self.statement_summary.count("{") != len(referenced) or self.statement_summary.count("}") != len(referenced):
                raise ValueError("语句摘要模板的大括号必须成对且只用于参数占位")
            unknown = [name for name in referenced if name.strip() not in names]
            if unknown:
                raise ValueError(f"语句摘要引用了不存在的参数：{unknown[0]}")
        return self


class FunctionContractFileV1(_StrictModel):
    contract_schema_version: Literal[1]
    contribution_id: str = Field(min_length=3, max_length=240)
    functions: tuple[ExtensionFunctionContractV1, ...]

    @field_validator("contribution_id")
    @classmethod
    def validate_contribution_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("contribution_id 格式无效")
        return value

    @model_validator(mode="after")
    def validate_functions(self) -> "FunctionContractFileV1":
        function_ids = [item.function_id for item in self.functions]
        if len(function_ids) != len(set(function_ids)):
            raise ValueError("函数契约 ID 不能重复")
        return self


class WorkspaceUiActionContractV1(_StrictModel):
    command_id: str = Field(min_length=3, max_length=240)
    label: str = Field(min_length=1, max_length=120)
    level: Literal["primary", "secondary", "danger"]

    @field_validator("command_id")
    @classmethod
    def validate_command_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("command_id 格式无效")
        return value


class WorkspaceUiContractV1(_StrictModel):
    ui_system_version: Literal[1]
    workspace_id: str = Field(min_length=3, max_length=240)
    display_name: str = Field(min_length=1, max_length=120)
    topology: Literal[
        "navigator-content-inspector",
        "navigator-detail",
        "single-task",
        "player-runtime",
    ]
    primary_object: str = Field(min_length=1, max_length=120)
    page_actions: tuple[WorkspaceUiActionContractV1, ...] = ()
    states: tuple[Literal[
        "loading", "error", "empty", "filtered-empty", "selection", "readonly", "offline",
    ], ...]
    has_inspector: bool
    narrow_behavior: Literal["single-column", "mutually-exclusive-drawers"]
    keyboard_entry: str = Field(min_length=1, max_length=240)
    permission_summary: str = Field(min_length=1, max_length=500)
    danger_commands: tuple[str, ...] = ()

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("workspace_id 格式无效")
        return value

    @model_validator(mode="after")
    def validate_ui_contract(self) -> "WorkspaceUiContractV1":
        action_ids = [item.command_id for item in self.page_actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("page_actions.command_id 不能重复")
        if sum(item.level == "primary" for item in self.page_actions) > 1:
            raise ValueError("同一工作区只能声明一个主操作")
        required_states = {"loading", "error", "empty", "selection"}
        if not required_states.issubset(self.states):
            missing = "、".join(sorted(required_states.difference(self.states)))
            raise ValueError(f"工作区缺少必要状态：{missing}")
        if len(self.states) != len(set(self.states)):
            raise ValueError("工作区 states 不能重复")
        if self.topology == "navigator-content-inspector" and not self.has_inspector:
            raise ValueError("三栏拓扑必须声明检查器")
        if self.has_inspector and self.narrow_behavior != "mutually-exclusive-drawers":
            raise ValueError("带检查器的窄屏工作区必须使用互斥抽屉")
        if any(command not in action_ids for command in self.danger_commands):
            raise ValueError("危险命令必须同时声明在 page_actions 中")
        return self


class WorkspaceContributionFileV1(_StrictModel):
    workspace_schema_version: Literal[1]
    contribution_id: str = Field(min_length=3, max_length=240)
    workspaces: tuple[WorkspaceUiContractV1, ...]

    @field_validator("contribution_id")
    @classmethod
    def validate_contribution_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("contribution_id 格式无效")
        return value

    @model_validator(mode="after")
    def validate_workspaces(self) -> "WorkspaceContributionFileV1":
        workspace_ids = [item.workspace_id for item in self.workspaces]
        if not workspace_ids:
            raise ValueError("工作区贡献不能为空")
        if len(workspace_ids) != len(set(workspace_ids)):
            raise ValueError("workspace_id 不能重复")
        return self


class SignedPackageFileV1(_StrictModel):
    path: str
    size: int = Field(ge=0)
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="扩展签名文件路径")

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("扩展签名文件哈希无效")
        return value


class ManifestSignatureV1(_StrictModel):
    signature_version: Literal[1]
    algorithm: Literal["Ed25519"]
    publisher_id: str
    key_id: str
    public_key: str
    signed_file: Literal["easycode-extension.json"]
    signed_sha256: str
    files: tuple[SignedPackageFileV1, ...]
    signature: str


class ArtifactSignatureV1(_StrictModel):
    signature_version: Literal[1]
    algorithm: Literal["Ed25519"]
    package_id: str
    version: str
    variant_id: str
    key_id: str
    public_key: str
    signed_sha256: str
    signature: str


class RuntimeFileV1(_StrictModel):
    path: str
    size: int = Field(ge=0)
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="运行产物路径")

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("运行文件哈希无效")
        return value


class SealedRuntimeV1(_StrictModel):
    format: Literal["ecx-runtime-1"]
    package_id: str
    version: str
    variant_id: str
    host: HostKind
    runtime: RuntimeKind
    minimum_android_api: int | None = Field(default=None, ge=21, le=37)
    targets: tuple[TargetKind, ...]
    module: str | None = None
    entrypoints: dict[str, str]
    files: tuple[RuntimeFileV1, ...]

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: str | None) -> str | None:
        return _safe_relative_path(value, label="运行模块") if value is not None else None

    @model_validator(mode="after")
    def validate_files(self) -> "SealedRuntimeV1":
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("运行产物文件路径不能重复")
        if self.module is not None and self.module not in paths:
            raise ValueError("运行模块必须进入密封文件闭包")
        if self.runtime == "android-kotlin-v1":
            if self.host != "android_native" or self.minimum_android_api is None:
                raise ValueError("Android Kotlin 密封产物缺少宿主或最低 API")
            if self.module is None or PurePosixPath(self.module).suffix.casefold() != ".jar":
                raise ValueError("Android Kotlin 密封产物必须声明一个 JAR module")
            if any(not JVM_BINARY_NAME_RE.fullmatch(entry) for entry in self.entrypoints.values()):
                raise ValueError("Android Kotlin 密封入口必须是 JVM 二进制类名")
        else:
            if self.minimum_android_api is not None:
                raise ValueError("非 Android 密封产物不能声明最低 Android API")
            if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry) for entry in self.entrypoints.values()):
                raise ValueError("Windows 密封入口只能声明模块内函数名")
        return self


class ToolchainLockV1(_StrictModel):
    compiler_version: str
    program_schema: Literal[1]
    ecir: Literal[1]
    # This is the semantic registry revision, not the easycode.lock schema
    # version. v7 adds portable temporal arithmetic and text extraction while
    # preserving stable operation/input-slot identities.
    pure_value_registry_version: Literal[10]
    pure_value_registry_sha256: str

    @field_validator("compiler_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("toolchain.compiler_version 必须是完整语义版本")
        return value

    @field_validator("pure_value_registry_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("pure_value_registry_sha256 无效")
        return value


class FunctionContractLockV1(_StrictModel):
    function_id: str
    contract_version: str
    contract_fingerprint: str

    @field_validator("function_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("函数锁定 ID 无效")
        return value

    @field_validator("contract_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("函数锁定版本无效")
        return value

    @field_validator("contract_fingerprint")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("函数契约指纹无效")
        return value


class LockedDependencyV1(_StrictModel):
    package_id: str
    version: str
    content_sha256: str

    @field_validator("package_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not PACKAGE_ID_RE.fullmatch(value):
            raise ValueError("锁定依赖 package_id 无效")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("锁定依赖必须是精确语义版本")
        return value

    @field_validator("content_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("锁定依赖内容哈希无效")
        return value


class LockedContributionV1(_StrictModel):
    contribution_id: str
    kind: Literal[
        "function_contracts", "data_schemas", "workspaces", "compiler_steps",
        "runtime_modules", "player_modules", "harness_adapters", "target_drivers",
    ]
    sha256: str

    @field_validator("contribution_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("锁定 contribution_id 无效")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("锁定贡献哈希无效")
        return value


class LockedVariantV1(_StrictModel):
    target: TargetKind
    host: HostKind
    variant_id: str
    runtime: RuntimeKind
    minimum_android_api: int | None = Field(default=None, ge=21, le=37)
    artifact_sha256: str | None = None
    artifact_signature_sha256: str | None = None

    @field_validator("variant_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not STABLE_ID_RE.fullmatch(value):
            raise ValueError("锁定 variant_id 无效")
        return value

    @field_validator("artifact_sha256", "artifact_signature_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("锁定密封产物哈希无效")
        return value

    @model_validator(mode="after")
    def validate_pair(self) -> "LockedVariantV1":
        if (self.artifact_sha256 is None) != (self.artifact_signature_sha256 is None):
            raise ValueError("密封产物与签名哈希必须同时锁定")
        if self.host == "android_native" and self.minimum_android_api is None:
            raise ValueError("Android 锁定变体缺少 minimum_android_api")
        if self.host != "android_native" and self.minimum_android_api is not None:
            raise ValueError("Windows 锁定变体不能声明 minimum_android_api")
        return self


class ExtensionLockRecordV1(_StrictModel):
    package_id: str
    version: str
    scope: Literal["official", "user", "project"]
    manifest_sha256: str
    content_sha256: str
    publisher_id: str
    publisher_key_fingerprint: str
    publisher_public_key: str
    trust_mode: Literal["official", "publisher_trusted", "local_trusted_code", "declarative_only"]
    dependencies: tuple[LockedDependencyV1, ...] = ()
    contributions: tuple[LockedContributionV1, ...] = ()
    selected_variants: tuple[LockedVariantV1, ...] = ()
    function_contracts: tuple[FunctionContractLockV1, ...] = ()

    @field_validator("package_id", "publisher_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not PACKAGE_ID_RE.fullmatch(value):
            raise ValueError("扩展锁定身份无效")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("扩展锁定版本无效")
        return value

    @field_validator("manifest_sha256", "content_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("扩展锁定哈希无效")
        return value

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ExtensionLockRecordV1":
        for label, values in (
            ("依赖", [item.package_id for item in self.dependencies]),
            ("贡献", [item.contribution_id for item in self.contributions]),
            ("宿主目标变体", [(item.host, item.target) for item in self.selected_variants]),
            ("函数契约", [item.function_id for item in self.function_contracts]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"扩展锁定{label}不能重复")
        return self


class EasyCodeLockV1(_StrictModel):
    lock_version: Literal[1]
    project_format: Literal[6]
    toolchain: ToolchainLockV1
    official_functions: tuple[FunctionContractLockV1, ...] = ()
    extensions: tuple[ExtensionLockRecordV1, ...] = ()

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "EasyCodeLockV1":
        official_ids = [item.function_id for item in self.official_functions]
        package_ids = [item.package_id for item in self.extensions]
        if len(official_ids) != len(set(official_ids)):
            raise ValueError("official_functions.function_id 不能重复")
        if len(package_ids) != len(set(package_ids)):
            raise ValueError("extensions.package_id 不能重复")
        return self


class PublishedVariantV1(_StrictModel):
    target: TargetKind
    host: HostKind
    runtime: RuntimeKind
    minimum_android_api: int | None = Field(default=None, ge=21, le=37)
    variant_id: str
    artifact_path: str
    artifact_signature_path: str
    artifact_sha256: str
    artifact_signature_sha256: str
    entrypoints: dict[str, str]

    @field_validator("artifact_path", "artifact_signature_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value, label="发布扩展运行路径")

    @field_validator("artifact_sha256", "artifact_signature_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("发布扩展产物哈希无效")
        return value

    @model_validator(mode="after")
    def validate_android_api(self) -> "PublishedVariantV1":
        if self.host == "android_native" and self.minimum_android_api is None:
            raise ValueError("Android 发布变体缺少 minimum_android_api")
        if self.host != "android_native" and self.minimum_android_api is not None:
            raise ValueError("Windows 发布变体不能声明 minimum_android_api")
        return self


class PublishedExtensionV1(_StrictModel):
    runtime_extension_schema: Literal[1]
    package_id: str
    version: str
    publisher_id: str
    publisher_key_fingerprint: str
    publisher_public_key: str
    manifest_sha256: str
    content_sha256: str
    trust_mode: Literal["official", "publisher_trusted", "local_trusted_code", "declarative_only"]
    permissions: tuple[str, ...] = ()
    network: NetworkV1
    dependencies: tuple[LockedDependencyV1, ...] = ()
    contributions: tuple[LockedContributionV1, ...] = ()
    function_contracts: tuple[ExtensionFunctionContractV1, ...] = ()
    variants: tuple[PublishedVariantV1, ...]

    @model_validator(mode="after")
    def validate_identity(self) -> "PublishedExtensionV1":
        if not PACKAGE_ID_RE.fullmatch(self.package_id) or not PACKAGE_ID_RE.fullmatch(self.publisher_id):
            raise ValueError("发布扩展身份无效")
        if not SEMVER_RE.fullmatch(self.version):
            raise ValueError("发布扩展版本无效")
        if not self.variants:
            raise ValueError("发布扩展没有密封宿主变体")
        return self


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionSchemaError(f"{label}无法读取：{exc}") from exc
    if not isinstance(value, dict):
        raise ExtensionSchemaError(f"{label}必须是 JSON 对象")
    return value


def load_manifest(root: Path) -> tuple[ExtensionManifestV1, bytes]:
    path = resolve_package_path(root, MANIFEST_FILE)
    value = _read_json_object(path, label="扩展清单")
    try:
        manifest = ExtensionManifestV1.model_validate(value)
    except ValidationError as exc:
        raise ExtensionSchemaError(f"扩展清单不符合 v1：{exc}") from exc
    for variant in manifest.variants:
        if variant.development_entry is not None:
            entry = resolve_package_path(root, variant.development_entry)
            if not entry.is_file() or entry.suffix.casefold() != ".py":
                raise ExtensionSchemaError(f"扩展开发入口无效：{variant.development_entry}")
    if manifest.data is not None:
        data_schema = resolve_package_path(root, manifest.data.schema_path)
        try:
            schema_value = json.loads(data_schema.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExtensionSchemaError(f"扩展数据 Schema 无法读取：{exc}") from exc
        if not isinstance(schema_value, dict):
            raise ExtensionSchemaError("扩展数据 Schema 必须是 JSON 对象")
    for license_item in manifest.licenses:
        license_path = resolve_package_path(root, license_item.path)
        if not license_path.is_file() or not license_path.read_bytes().strip():
            raise ExtensionSchemaError(f"扩展许可证材料为空：{license_item.path}")
    canonical = canonical_json_bytes(manifest.model_dump(mode="json", exclude_none=True))
    return manifest, canonical


def version_satisfies(version: str, constraint: str) -> bool:
    """Evaluate the intentionally small deterministic semver range grammar."""

    def parsed(value: str) -> tuple[int, int, int, str]:
        match = SEMVER_RE.fullmatch(value)
        if match is None:
            raise ExtensionSchemaError(f"语义版本无效：{value}")
        base, _, prerelease = value.partition("-")
        major, minor, patch = (int(item) for item in base.split("."))
        return major, minor, patch, prerelease

    current = parsed(version)
    for token in str(constraint).split():
        match = re.fullmatch(r"(>=|<=|>|<|==)?(.+)", token)
        if match is None:
            return False
        operator = match.group(1) or "=="
        wanted = parsed(match.group(2))
        if operator == "==" and current != wanted:
            return False
        if operator == ">=" and current < wanted:
            return False
        if operator == "<=" and current > wanted:
            return False
        if operator == ">" and current <= wanted:
            return False
        if operator == "<" and current >= wanted:
            return False
    return True


def load_easycode_lock(path: Path) -> EasyCodeLockV1:
    try:
        return EasyCodeLockV1.model_validate(_read_json_object(path, label="easycode.lock"))
    except ValidationError as exc:
        raise ExtensionSchemaError(f"easycode.lock 不符合 v1：{exc}") from exc


def _decode_public_key(value: str) -> bytes:
    try:
        result = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ExtensionSchemaError("扩展发布公钥格式无效") from exc
    if len(result) != 32:
        raise ExtensionSchemaError("扩展发布公钥长度无效")
    return result


def _signed_package_files(root: Path, manifest: ExtensionManifestV1) -> tuple[SignedPackageFileV1, ...]:
    excluded = {MANIFEST_FILE, MANIFEST_SIGNATURE_FILE}
    for variant in manifest.host_variants:
        if variant.sealed_artifact:
            excluded.add(variant.sealed_artifact)
        if variant.sealed_signature:
            excluded.add(variant.sealed_signature)
    records: list[SignedPackageFileV1] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise ExtensionSchemaError("扩展包不允许符号链接")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        content = path.read_bytes()
        records.append(SignedPackageFileV1(
            path=relative,
            size=len(content),
            sha256=sha256_hex(content),
        ))
    return tuple(records)


def _manifest_signature_payload(canonical: bytes, files: tuple[SignedPackageFileV1, ...]) -> bytes:
    return canonical_json_bytes({
        "manifest_sha256": sha256_hex(canonical),
        "files": [item.model_dump(mode="json") for item in files],
    })


def verify_manifest_signature(root: Path, manifest: ExtensionManifestV1, canonical: bytes) -> dict[str, Any]:
    path = resolve_package_path(root, MANIFEST_SIGNATURE_FILE)
    try:
        envelope = ManifestSignatureV1.model_validate(_read_json_object(path, label="扩展签名"))
    except ValidationError as exc:
        raise ExtensionSchemaError(f"扩展签名格式无效：{exc}") from exc
    if envelope.publisher_id != manifest.publisher_id:
        raise ExtensionSchemaError("扩展签名发布者与清单不一致")
    files = _signed_package_files(root, manifest)
    if envelope.files != files:
        raise ExtensionSchemaError("扩展签名文件闭包与包内容不一致")
    signed_payload = _manifest_signature_payload(canonical, files)
    if envelope.signed_sha256 != sha256_hex(signed_payload):
        raise ExtensionSchemaError("扩展包签名哈希不一致")
    public_key = _decode_public_key(envelope.public_key)
    if envelope.key_id != public_key_id(public_key):
        raise ExtensionSchemaError("扩展发布者密钥指纹不一致")
    try:
        signature = base64.b64decode(envelope.signature, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, signed_payload)
    except (ValueError, InvalidSignature) as exc:
        raise ExtensionSchemaError("扩展清单签名验证失败") from exc
    return envelope.model_dump(mode="json")


def sign_manifest(root: Path, manifest: ExtensionManifestV1, identity: AuthorSigningIdentity) -> dict[str, Any]:
    canonical = canonical_json_bytes(manifest.model_dump(mode="json", exclude_none=True))
    files = _signed_package_files(root, manifest)
    signed_payload = _manifest_signature_payload(canonical, files)
    signature = identity.private_key.sign(signed_payload)
    envelope = ManifestSignatureV1(
        signature_version=1,
        algorithm=SIGNATURE_ALGORITHM,
        publisher_id=manifest.publisher_id,
        key_id=identity.key_id,
        public_key=identity.public_key_base64,
        signed_file=MANIFEST_FILE,
        signed_sha256=sha256_hex(signed_payload),
        files=files,
        signature=base64.b64encode(signature).decode("ascii"),
    ).model_dump(mode="json")
    return envelope


def load_function_contracts(root: Path, manifest: ExtensionManifestV1) -> tuple[list[ExtensionFunctionContractV1], list[dict[str, Any]]]:
    functions: list[ExtensionFunctionContractV1] = []
    records: list[dict[str, Any]] = []
    function_ids: set[str] = set()
    contribution_ids = {item.contribution_id for _kind, item in manifest.contributions.all()}
    for kind, contribution in manifest.contributions.all():
        path = resolve_package_path(root, contribution.path)
        content = path.read_bytes()
        if kind == "workspaces":
            try:
                workspace_document = WorkspaceContributionFileV1.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ExtensionSchemaError(f"工作区契约无效 {contribution.path}：{exc}") from exc
            if workspace_document.contribution_id != contribution.contribution_id:
                raise ExtensionSchemaError("工作区契约 contribution_id 与清单不一致")
            for workspace in workspace_document.workspaces:
                if not workspace.workspace_id.startswith(manifest.package_id + "."):
                    raise ExtensionSchemaError(f"工作区 ID 越出扩展命名空间：{workspace.workspace_id}")
            records.append({
                "contribution_id": contribution.contribution_id,
                "kind": kind,
                "path": contribution.path,
                "sha256": sha256_hex(content),
                "workspaces": [item.workspace_id for item in workspace_document.workspaces],
            })
            continue
        if kind != "function_contracts":
            records.append({
                "contribution_id": contribution.contribution_id,
                "kind": kind,
                "path": contribution.path,
                "sha256": sha256_hex(content),
            })
            continue
        try:
            document = FunctionContractFileV1.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ExtensionSchemaError(f"函数契约无效 {contribution.path}：{exc}") from exc
        if document.contribution_id != contribution.contribution_id:
            raise ExtensionSchemaError("函数契约 contribution_id 与清单不一致")
        if document.contribution_id not in contribution_ids:
            raise ExtensionSchemaError("函数契约引用未知贡献")
        for function in document.functions:
            if not function.function_id.startswith(manifest.package_id + "."):
                raise ExtensionSchemaError(f"函数 ID 越出扩展命名空间：{function.function_id}")
            if function.function_id in function_ids:
                raise ExtensionSchemaError(f"重复函数 ID：{function.function_id}")
            function_ids.add(function.function_id)
            functions.append(function)
        records.append({
            "contribution_id": contribution.contribution_id,
            "kind": kind,
            "path": contribution.path,
            "sha256": sha256_hex(content),
            "functions": [item.function_id for item in document.functions],
        })
    variant_entrypoints = {
        function_id
        for variant in manifest.host_variants
        for function_id in variant.entrypoints
    }
    missing = sorted(function_ids - variant_entrypoints)
    unknown = sorted(variant_entrypoints - function_ids)
    if missing:
        raise ExtensionSchemaError(f"函数缺少宿主入口：{missing[0]}")
    if unknown:
        raise ExtensionSchemaError(f"宿主入口引用未知函数：{unknown[0]}")
    manifest_targets = {target for variant in manifest.variants for target in variant.targets}
    for function in functions:
        unknown_permissions = set(function.permissions) - set(manifest.permissions)
        if unknown_permissions:
            raise ExtensionSchemaError(
                f"函数权限未在 Manifest 声明：{sorted(unknown_permissions)[0]}"
            )
        required_android_api = max(
            (
                int(EXTENSION_PERMISSION_SPECS[permission]["minimum_android_api"])
                for permission in function.permissions
            ),
            default=21,
        )
        for variant in manifest.host_variants:
            if (
                variant.host == "android_native"
                and function.function_id in variant.entrypoints
                and int(variant.minimum_android_api or 21) < required_android_api
            ):
                raise ExtensionSchemaError(
                    f"Android 扩展函数 {function.function_id} 的权限要求 API "
                    f"{required_android_api}，高于变体 {variant.variant_id} 声明"
                )
        unsupported_targets = set(function.targets) - manifest_targets
        if unsupported_targets:
            raise ExtensionSchemaError(
                f"函数目标没有兼容宿主变体：{sorted(unsupported_targets)[0]}"
            )
    return functions, records


def create_artifact_signature(content: bytes, *, manifest: ExtensionManifestV1, variant: HostVariantV1, identity: AuthorSigningIdentity) -> dict[str, Any]:
    return ArtifactSignatureV1(
        signature_version=1,
        algorithm=SIGNATURE_ALGORITHM,
        package_id=manifest.package_id,
        version=manifest.version,
        variant_id=variant.variant_id,
        key_id=identity.key_id,
        public_key=identity.public_key_base64,
        signed_sha256=sha256_hex(content),
        signature=base64.b64encode(identity.private_key.sign(content)).decode("ascii"),
    ).model_dump(mode="json")


def verify_artifact_signature(content: bytes, envelope_value: dict[str, Any], *, manifest: ExtensionManifestV1, variant: HostVariantV1, expected_key_id: str) -> dict[str, Any]:
    try:
        envelope = ArtifactSignatureV1.model_validate(envelope_value)
    except ValidationError as exc:
        raise ExtensionSchemaError(f"密封产物签名格式无效：{exc}") from exc
    if (
        envelope.package_id != manifest.package_id
        or envelope.version != manifest.version
        or envelope.variant_id != variant.variant_id
    ):
        raise ExtensionSchemaError("密封产物签名身份与清单不一致")
    public_key = _decode_public_key(envelope.public_key)
    if envelope.key_id != public_key_id(public_key) or envelope.key_id != expected_key_id:
        raise ExtensionSchemaError("密封产物发布者与清单发布者不一致")
    if envelope.signed_sha256 != sha256_hex(content):
        raise ExtensionSchemaError("密封产物哈希与签名不一致")
    try:
        signature = base64.b64decode(envelope.signature, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, content)
    except (ValueError, InvalidSignature) as exc:
        raise ExtensionSchemaError("密封产物签名验证失败") from exc
    return envelope.model_dump(mode="json")


FORBIDDEN_RUNTIME_PARTS = {
    "src", "source", "sources", "test", "tests", ".idea", ".vscode", "__pycache__",
}
FORBIDDEN_RUNTIME_SUFFIXES = {
    ".py", ".pyi", ".md", ".toml", ".yaml", ".yml", ".lock", ".txt",
}
ALLOWED_RUNTIME_SUFFIXES = {".pyc", ".pyd", ".dll", ".so", ".jar", ".dex", ".json"}


def validate_sealed_artifact(root: Path, manifest: ExtensionManifestV1, variant: HostVariantV1, manifest_signature: dict[str, Any]) -> dict[str, Any]:
    if not variant.sealed_artifact or not variant.sealed_signature or not variant.sealed_sha256:
        raise ExtensionSchemaError(f"变体尚未构建密封产物：{variant.variant_id}")
    artifact_path = resolve_package_path(root, variant.sealed_artifact)
    signature_path = resolve_package_path(root, variant.sealed_signature)
    content = artifact_path.read_bytes()
    if sha256_hex(content) != variant.sealed_sha256:
        raise ExtensionSchemaError("密封产物内容与清单哈希不一致")
    envelope = verify_artifact_signature(
        content,
        _read_json_object(signature_path, label="密封产物签名"),
        manifest=manifest,
        variant=variant,
        expected_key_id=str(manifest_signature["key_id"]),
    )
    try:
        archive = zipfile.ZipFile(artifact_path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ExtensionSchemaError("密封产物不是有效 ecx-runtime-1 归档") from exc
    with archive:
        members = archive.infolist()
        names = [item.filename.replace("\\", "/") for item in members if not item.is_dir()]
        if not names or len(names) != len(set(names)):
            raise ExtensionSchemaError("密封产物为空或包含重复路径")
        if len(names) > 4096 or sum(max(0, item.file_size) for item in members) > 512 * 1024 * 1024:
            raise ExtensionSchemaError("密封产物超过安全上限")
        for item in members:
            name = item.filename.replace("\\", "/")
            parsed = PurePosixPath(name)
            if (
                not name
                or parsed.is_absolute()
                or ".." in parsed.parts
                or any(part.casefold() in FORBIDDEN_RUNTIME_PARTS for part in parsed.parts)
                or (item.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ExtensionSchemaError(f"密封产物包含不安全路径：{name}")
            suffix = parsed.suffix.casefold()
            if not item.is_dir() and (suffix in FORBIDDEN_RUNTIME_SUFFIXES or suffix not in ALLOWED_RUNTIME_SUFFIXES):
                raise ExtensionSchemaError(f"密封产物包含开发文件或未知类型：{name}")
        if "ecx-runtime.json" not in names:
            raise ExtensionSchemaError("密封产物缺少 ecx-runtime.json")
        try:
            descriptor = SealedRuntimeV1.model_validate(json.loads(archive.read("ecx-runtime.json")))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ExtensionSchemaError(f"密封运行描述无效：{exc}") from exc
        if (
            descriptor.package_id != manifest.package_id
            or descriptor.version != manifest.version
            or descriptor.variant_id != variant.variant_id
            or descriptor.host != variant.host
            or descriptor.runtime != variant.runtime
            or descriptor.minimum_android_api != variant.minimum_android_api
            or descriptor.targets != variant.targets
            or descriptor.entrypoints != variant.entrypoints
        ):
            raise ExtensionSchemaError("密封运行描述与已签名清单不一致")
        listed = {item.path: item for item in descriptor.files}
        actual = set(names) - {"ecx-runtime.json"}
        if actual != set(listed):
            raise ExtensionSchemaError("密封运行文件闭包不完整")
        for path, record in listed.items():
            payload = archive.read(path)
            if len(payload) != record.size or sha256_hex(payload) != record.sha256:
                raise ExtensionSchemaError(f"密封运行文件校验失败：{path}")
    return {
        "format": RUNTIME_FORMAT,
        "path": variant.sealed_artifact,
        "signature_path": variant.sealed_signature,
        "sha256": variant.sealed_sha256,
        "size": len(content),
        "signature": envelope,
        "descriptor": descriptor.model_dump(mode="json"),
    }


def validate_published_extension(
    root: Path,
    descriptor: PublishedExtensionV1,
    locked: ExtensionLockRecordV1,
) -> dict[str, Any]:
    """Validate one source-free runtime projection against its signed lock."""

    if (
        descriptor.package_id != locked.package_id
        or descriptor.version != locked.version
        or descriptor.publisher_id != locked.publisher_id
        or descriptor.publisher_key_fingerprint != locked.publisher_key_fingerprint
        or descriptor.publisher_public_key != locked.publisher_public_key
        or descriptor.manifest_sha256 != locked.manifest_sha256
        or descriptor.content_sha256 != locked.content_sha256
        or descriptor.trust_mode != locked.trust_mode
        or descriptor.dependencies != locked.dependencies
        or descriptor.contributions != locked.contributions
    ):
        raise ExtensionSchemaError("发布扩展描述与 easycode.lock 不一致")
    expected_contracts = {
        item.function_id: item for item in locked.function_contracts
    }
    actual_contracts = {
        item.function_id: item for item in descriptor.function_contracts
    }
    if set(expected_contracts) != set(actual_contracts):
        raise ExtensionSchemaError("发布扩展函数契约闭包与 easycode.lock 不一致")
    for function_id, function in actual_contracts.items():
        expected = expected_contracts[function_id]
        if (
            function.contract_version != expected.contract_version
            or sha256_hex(canonical_json_bytes(function.model_dump(mode="json")))
            != expected.contract_fingerprint
        ):
            raise ExtensionSchemaError(f"发布扩展函数契约指纹不一致：{function_id}")
    locked_variants = {
        (item.target, item.variant_id): item for item in locked.selected_variants
    }
    published_variants = {
        (item.target, item.variant_id): item for item in descriptor.variants
    }
    if set(locked_variants) != set(published_variants):
        raise ExtensionSchemaError("发布扩展宿主变体闭包与 easycode.lock 不一致")
    validated_artifacts: dict[str, dict[str, Any]] = {}
    for key, variant in published_variants.items():
        expected = locked_variants[key]
        if (
            variant.host != expected.host
            or variant.runtime != expected.runtime
            or variant.minimum_android_api != expected.minimum_android_api
            or variant.artifact_sha256 != expected.artifact_sha256
            or variant.artifact_signature_sha256 != expected.artifact_signature_sha256
        ):
            raise ExtensionSchemaError("发布扩展宿主变体与 easycode.lock 不一致")
        if variant.variant_id in validated_artifacts:
            continue
        artifact_path = resolve_package_path(root, variant.artifact_path)
        signature_path = resolve_package_path(root, variant.artifact_signature_path)
        content = artifact_path.read_bytes()
        signature_bytes = signature_path.read_bytes()
        if sha256_hex(content) != variant.artifact_sha256:
            raise ExtensionSchemaError("发布扩展密封产物哈希不一致")
        if sha256_hex(signature_bytes) != variant.artifact_signature_sha256:
            raise ExtensionSchemaError("发布扩展密封签名哈希不一致")
        try:
            signature_value = json.loads(signature_bytes)
            envelope = ArtifactSignatureV1.model_validate(signature_value)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ExtensionSchemaError(f"发布扩展密封签名格式无效：{exc}") from exc
        if (
            envelope.package_id != descriptor.package_id
            or envelope.version != descriptor.version
            or envelope.variant_id != variant.variant_id
            or envelope.key_id != descriptor.publisher_key_fingerprint
            or envelope.public_key != descriptor.publisher_public_key
            or envelope.signed_sha256 != variant.artifact_sha256
        ):
            raise ExtensionSchemaError("发布扩展密封签名身份不一致")
        public_key = _decode_public_key(envelope.public_key)
        if public_key_id(public_key) != envelope.key_id:
            raise ExtensionSchemaError("发布扩展发布者密钥指纹不一致")
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                base64.b64decode(envelope.signature, validate=True), content,
            )
        except (ValueError, InvalidSignature) as exc:
            raise ExtensionSchemaError("发布扩展密封签名验证失败") from exc
        try:
            archive = zipfile.ZipFile(io.BytesIO(content), "r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise ExtensionSchemaError("发布扩展密封产物不是有效归档") from exc
        with archive:
            members = archive.infolist()
            names = [item.filename.replace("\\", "/") for item in members if not item.is_dir()]
            if not names or len(names) != len(set(names)) or "ecx-runtime.json" not in names:
                raise ExtensionSchemaError("发布扩展密封产物路径闭包无效")
            if len(names) > 4096 or sum(max(0, item.file_size) for item in members) > 512 * 1024 * 1024:
                raise ExtensionSchemaError("发布扩展密封产物超过安全上限")
            for member in members:
                name = member.filename.replace("\\", "/")
                parsed = PurePosixPath(name)
                suffix = parsed.suffix.casefold()
                if (
                    not name
                    or parsed.is_absolute()
                    or ".." in parsed.parts
                    or any(part.casefold() in FORBIDDEN_RUNTIME_PARTS for part in parsed.parts)
                    or (member.external_attr >> 16) & 0o170000 == 0o120000
                    or (not member.is_dir() and (
                        suffix in FORBIDDEN_RUNTIME_SUFFIXES or suffix not in ALLOWED_RUNTIME_SUFFIXES
                    ))
                ):
                    raise ExtensionSchemaError(f"发布扩展密封产物包含不安全文件：{name}")
            try:
                runtime = SealedRuntimeV1.model_validate(json.loads(archive.read("ecx-runtime.json")))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ExtensionSchemaError(f"发布扩展密封描述无效：{exc}") from exc
            if (
                runtime.package_id != descriptor.package_id
                or runtime.version != descriptor.version
                or runtime.variant_id != variant.variant_id
                or runtime.host != variant.host
                or runtime.runtime != variant.runtime
                or runtime.minimum_android_api != variant.minimum_android_api
                or variant.target not in runtime.targets
                or runtime.entrypoints != variant.entrypoints
            ):
                raise ExtensionSchemaError("发布扩展密封描述与运行描述不一致")
            listed = {item.path: item for item in runtime.files}
            if set(names) - {"ecx-runtime.json"} != set(listed):
                raise ExtensionSchemaError("发布扩展密封运行文件闭包不完整")
            for path, record in listed.items():
                payload = archive.read(path)
                if len(payload) != record.size or sha256_hex(payload) != record.sha256:
                    raise ExtensionSchemaError(f"发布扩展密封运行文件校验失败：{path}")
        validated_artifacts[variant.variant_id] = {
            "artifact_path": str(artifact_path),
            "signature_path": str(signature_path),
            "runtime": runtime.model_dump(mode="json"),
        }
    return {
        "package_id": descriptor.package_id,
        "functions": sorted(actual_contracts),
        "artifacts": validated_artifacts,
    }


def package_digest(root: Path, paths: list[str]) -> str:
    records = []
    for relative in sorted(set(paths)):
        content = resolve_package_path(root, relative).read_bytes()
        records.append({"path": relative, "size": len(content), "sha256": sha256_hex(content)})
    return sha256_hex(canonical_json_bytes(records))


def ensure_no_package_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ExtensionSchemaError(f"扩展包不允许符号链接：{path.relative_to(root)}")
        resolved = path.resolve()
        if resolved != root.resolve() and root.resolve() not in resolved.parents:
            raise ExtensionSchemaError(f"扩展包路径越界：{path}")


__all__ = [
    "ArtifactSignatureV1",
    "ContributionV1",
    "ExtensionFunctionContractV1",
    "ExtensionManifestV1",
    "EXTENSION_PERMISSION_SPECS",
    "EasyCodeLockV1",
    "ExtensionLockRecordV1",
    "ExtensionSchemaError",
    "FunctionContractFileV1",
    "WorkspaceContributionFileV1",
    "WorkspaceUiActionContractV1",
    "WorkspaceUiContractV1",
    "HostVariantV1",
    "LOCK_FILE",
    "LOCK_VERSION",
    "MANIFEST_FILE",
    "MANIFEST_SIGNATURE_FILE",
    "PublishedExtensionV1",
    "PublishedVariantV1",
    "RUNTIME_FORMAT",
    "SealedRuntimeV1",
    "create_artifact_signature",
    "ensure_no_package_symlinks",
    "extension_android_manifest_permissions",
    "load_function_contracts",
    "load_easycode_lock",
    "load_manifest",
    "package_digest",
    "resolve_package_path",
    "sign_manifest",
    "validate_sealed_artifact",
    "validate_published_extension",
    "version_satisfies",
    "verify_manifest_signature",
]
