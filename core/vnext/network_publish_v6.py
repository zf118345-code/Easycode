"""Derive the network/file publish closure from compiled format-6 ECIR."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .network_runtime_v6 import normalize_network_authorization
from .runtime import RuntimeFailure


class NetworkPublishClosureError(ValueError):
    pass


def _instructions(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _instructions(item)
        return
    if not isinstance(value, dict):
        return
    if "opcode" in value and "instruction_id" in value:
        yield value
    for child in value.values():
        if isinstance(child, (dict, list)):
            yield from _instructions(child)


def network_publish_report(ecir: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic, non-secret network sources and file permissions."""

    sources: dict[tuple[Any, ...], dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    levels: set[str] = set()
    file_permissions: set[str] = set()
    for function in ecir.get("functions") or ():
        function_id = str(function.get("function_id") or "")
        for instruction in _instructions(function.get("instructions") or []):
            opcode = str(instruction.get("opcode") or "")
            if not opcode.startswith("network."):
                continue
            try:
                authorization = normalize_network_authorization(
                    instruction.get("network_authorization")
                )
            except RuntimeFailure as exc:
                raise NetworkPublishClosureError(
                    f'网络指令 {instruction.get("instruction_id") or "<unknown>"} '
                    "缺少有效授权闭包"
                ) from exc
            if opcode == "network.upload_file":
                file_permissions.add("filesystem.read")
            elif opcode == "network.download_file":
                file_permissions.add("filesystem.write")
            rule_ids: list[str] = []
            for rule in authorization["rules"]:
                rule_ids.append(str(rule["rule_id"]))
                scopes = tuple(sorted(str(item) for item in rule["address_scopes"]))
                level = "public" if "public" in scopes else "lan"
                levels.add(level)
                key = (
                    str(rule["rule_id"]),
                    tuple(rule["schemes"]),
                    tuple(rule["hosts"]),
                    tuple(rule["ports"]),
                    scopes,
                )
                sources[key] = {
                    "rule_id": str(rule["rule_id"]),
                    "source": str(rule.get("source") or "project_policy"),
                    "schemes": list(rule["schemes"]),
                    "hosts": list(rule["hosts"]),
                    "ports": list(rule["ports"]),
                    "address_scopes": list(scopes),
                    "network_level": level,
                }
                if "http" in rule["schemes"] and "public" in scopes:
                    warning = {
                        "code": "P-NET-HTTP-PUBLIC",
                        "message": (
                            f'公网规则 {rule["rule_id"]} 允许明文 HTTP；'
                            "请求内容可能被读取或修改"
                        ),
                    }
                    if warning not in warnings:
                        warnings.append(warning)
            calls.append({
                "function_id": function_id,
                "statement_id": str(instruction.get("instruction_id") or ""),
                "official_function_id": str(instruction.get("function_id") or ""),
                "opcode": opcode,
                "rule_ids": sorted(rule_ids),
                "file_permissions": (
                    ["filesystem.read"]
                    if opcode == "network.upload_file"
                    else ["filesystem.write"]
                    if opcode == "network.download_file"
                    else []
                ),
            })
    level = "public" if "public" in levels else "lan" if levels else "none"
    return {
        "schema_version": 1,
        "network_level": level,
        "sources": [sources[key] for key in sorted(sources)],
        "calls": sorted(calls, key=lambda item: (item["function_id"], item["statement_id"])),
        "file_permissions": sorted(file_permissions),
        "warnings": sorted(warnings, key=lambda item: (item["code"], item["message"])),
    }


__all__ = ["NetworkPublishClosureError", "network_publish_report"]
