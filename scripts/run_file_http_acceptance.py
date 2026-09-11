"""Run the signed file/HTTP acceptance project in a frozen Windows Player.

This is intentionally a real Player harness rather than a unit-test shortcut:
the project is signed and source-free, the frozen executable verifies it, and
the assertions execute inside the isolated Runtime worker.  A loopback server
is used only as a deterministic HTTP peer; it never substitutes Runtime work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore, trust_root_document  # noqa: E402
from core.vnext.file_runtime_v6 import windows_file_reference  # noqa: E402
from core.vnext.network_runtime_v6 import static_network_authorization  # noqa: E402
from core.vnext.publish import VNextPublisher  # noqa: E402
from core.vnext.pure_operations_v6 import (  # noqa: E402
    PURE_OPERATION_REGISTRY_VERSION,
    pure_operation_registry_hash,
)
from core.vnext.target_service import TargetConfiguration, target_configuration_revision  # noqa: E402

try:
    from benchmark_vnext_player import _bootstrap, _free_port, _stop  # noqa: E402
except ModuleNotFoundError:
    from scripts.benchmark_vnext_player import _bootstrap, _free_port, _stop  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reference(slot: str) -> dict[str, Any]:
    return {"kind": "reference", "scope": "local", "symbol_id": slot}


def _member(slot: str, field_id: str) -> dict[str, Any]:
    return {"kind": "member_access", "source": _reference(slot), "field_id": field_id}


def _fail(instruction_id: str, error_id: str, message: str) -> dict[str, Any]:
    return {
        "instruction_id": instruction_id,
        "opcode": "control.fail",
        "arguments": {"error_id": error_id, "message": message, "details": None},
        "result_slot": None,
        "platforms": ["windows", "no_target"],
        "capabilities": [],
        "source": {},
    }


def _assert_equal(
    instruction_id: str,
    actual: Any,
    expected: Any,
    operand_type: str,
    message: str,
) -> dict[str, Any]:
    return {
        "instruction_id": instruction_id,
        "opcode": "control.if",
        "arguments": {
            "condition": {
                "kind": "compare",
                "left": actual,
                "operator": "eq",
                "right": expected,
                "operand_type": operand_type,
            },
            "then": [],
            "additional_branches": [],
            "otherwise": [_fail(f"{instruction_id}.fail", f"{instruction_id}.failed", message)],
        },
        "result_slot": None,
        "platforms": ["windows", "no_target"],
        "capabilities": [],
        "source": {},
    }


def _args(function_id: str, **values: Any) -> dict[str, Any]:
    return {f"{function_id}.parameter.{name}": value for name, value in values.items()}


def _call(
    instruction_id: str,
    function_id: str,
    opcode: str,
    arguments: dict[str, Any],
    *,
    result_slot: str | None = None,
    result_type: str = "unit",
    capabilities: tuple[str, ...] = (),
    network_url: str = "",
) -> dict[str, Any]:
    value = {
        "instruction_id": instruction_id,
        "function_id": function_id,
        "opcode": opcode,
        "arguments": arguments,
        "parameter_ids": {},
        "result_type": result_type,
        "result_slot": result_slot,
        "platforms": ["windows", "no_target"],
        "capabilities": list(capabilities),
        "source": {},
    }
    if network_url:
        value["network_authorization"] = static_network_authorization(network_url)
    return value


class _Fixture(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls: list[dict[str, Any]] = []

    def log_message(self, *_: Any) -> None:
        return

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self.__class__.calls.append({"method": "GET", "path": self.path, "bytes": 0})
        if self.path == "/request":
            self._send(200, b"request-ok")
        elif self.path == "/download":
            self._send(200, b"download-payload", "application/octet-stream")
        elif self.path == "/download-fail":
            self._send(503, b"temporary-unavailable")
        else:
            self._send(404, b"not-found")

    def do_POST(self) -> None:  # noqa: N802
        body = self._body()
        self.__class__.calls.append({
            "method": "POST",
            "path": self.path,
            "bytes": len(body),
            "contains_upload_payload": b"upload-payload-acceptance" in body,
        })
        if self.path == "/upload":
            self._send(201, b"uploaded")
        else:
            self._send(404, b"not-found")


def _linked(base_url: str, files: dict[str, dict[str, Any]]) -> dict[str, Any]:
    request_url = f"{base_url}/request"
    upload_url = f"{base_url}/upload"
    failed_download_url = f"{base_url}/download-fail"
    download_url = f"{base_url}/download"
    instructions = [
        _call("file.write", "official.file.write_text", "file.write_text", _args(
            "official.file.write_text", file=files["text"], content="A=false\nA=false", encoding="utf-8",
        ), capabilities=("filesystem",)),
        _call("file.replace", "official.file.replace_text", "file.replace_text", _args(
            "official.file.replace_text", file=files["text"], search="A=false",
            replacement="A=true", scope="all", encoding="utf-8",
        ), result_slot="replace_count", result_type="int64", capabilities=("filesystem",)),
        _assert_equal("assert.replace-count", _reference("replace_count"), 2, "int64", "文本替换次数不是 2"),
        _call("file.read", "official.file.read_text", "file.read_text", _args(
            "official.file.read_text", file=files["text"], encoding="utf-8",
        ), result_slot="text_value", result_type="string", capabilities=("filesystem",)),
        _assert_equal("assert.file-content", _reference("text_value"), "A=true\nA=true", "string", "文件读取内容不正确"),
        _call("http.request", "official.network.request", "network.request", _args(
            "official.network.request", url=request_url, method="GET", query=[], headers=[],
            redirect="same_origin", timeout={"kind": "duration", "milliseconds": 10_000},
            max_response_bytes=1024, max_redirects=2, body=None,
        ), result_slot="request_result", result_type="http_response", capabilities=("network",), network_url=request_url),
        _assert_equal("assert.request-status", _member("request_result", "http_response.field.status"), 200, "int64", "HTTP 请求状态不是 200"),
        _assert_equal("assert.request-body", _member("request_result", "http_response.field.body"), "request-ok", "string", "HTTP 请求正文不正确"),
        _call("http.upload", "official.network.upload_file", "network.upload_file", _args(
            "official.network.upload_file", url=upload_url, query=[], headers=[], redirect="same_origin",
            timeout={"kind": "duration", "milliseconds": 10_000}, max_response_bytes=1024,
            max_redirects=2, max_file_bytes=1024 * 1024,
            fields=[{"record_type": "multipart_field", "multipart_field.field.kind": "file",
                     "multipart_field.field.name": "payload", "multipart_field.field.value": None,
                     "multipart_field.field.file": files["upload"],
                     "multipart_field.field.filename": "payload.txt"}],
        ), result_slot="upload_result", result_type="http_response",
            capabilities=("network", "filesystem.read"), network_url=upload_url),
        _assert_equal("assert.upload-status", _member("upload_result", "http_response.field.status"), 201, "int64", "上传状态不是 201"),
        _call("http.download-fail", "official.network.download_file", "network.download_file", _args(
            "official.network.download_file", url=failed_download_url, query=[], headers=[],
            redirect="same_origin", timeout={"kind": "duration", "milliseconds": 10_000},
            max_response_bytes=1024, max_redirects=2, destination=files["failed_download"],
            max_file_bytes=1024 * 1024,
        ), result_slot="failed_download_result", result_type="http_download_result",
            capabilities=("network", "filesystem.write"), network_url=failed_download_url),
        _assert_equal("assert.failed-not-committed", _member("failed_download_result", "http_download_result.field.committed"), False, "bool", "失败下载不应提交文件"),
        _call("http.download", "official.network.download_file", "network.download_file", _args(
            "official.network.download_file", url=download_url, query=[], headers=[],
            redirect="same_origin", timeout={"kind": "duration", "milliseconds": 10_000},
            max_response_bytes=1024, max_redirects=2, destination=files["download"],
            max_file_bytes=1024 * 1024,
        ), result_slot="download_result", result_type="http_download_result",
            capabilities=("network", "filesystem.write"), network_url=download_url),
        _assert_equal("assert.download-committed", _member("download_result", "http_download_result.field.committed"), True, "bool", "成功下载没有原子提交"),
        _assert_equal("assert.download-bytes", _member("download_result", "http_download_result.field.bytes_written"), len(b"download-payload"), "int64", "下载字节数不正确"),
    ]
    return {
        "diagnostics": [],
        "ecir": {
            "ecir_version": 1,
            "program_model_version": 1,
            "pure_operation_registry": {
                "registry_version": PURE_OPERATION_REGISTRY_VERSION,
                "content_hash": pure_operation_registry_hash(),
            },
            "entry_function_id": "function.file-http-acceptance",
            "target_platform": "windows",
            "supported_platforms": ["windows", "no_target"],
            "required_capabilities": ["filesystem", "filesystem.read", "filesystem.write", "network"],
            "functions": [{
                "function_id": "function.file-http-acceptance",
                "name": "文件与 HTTP 验收",
                "parameters": [],
                "parameter_definitions": [],
                "return_type": "null",
                "instructions": instructions,
            }],
            "project_variables": [],
            "targets": [],
            "default_target_id": None,
        },
    }


def _create_bundle(output: Path, base_url: str, data: Path) -> dict[str, Any]:
    project_root = output / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    upload = data / "upload-source.txt"
    upload.write_text("upload-payload-acceptance", encoding="utf-8")
    failed_download = data / "failed-download.txt"
    failed_download.write_text("preserve-old", encoding="utf-8")
    refs = {
        "text": windows_file_reference(str(data / "text.txt"), str(data), access=("read", "write"), source="author"),
        "upload": windows_file_reference(str(upload), str(data), access=("read",), source="author"),
        "failed_download": windows_file_reference(str(failed_download), str(data), access=("read", "write"), source="author"),
        "download": windows_file_reference(str(data / "download.txt"), str(data), access=("read", "write"), source="author"),
    }
    _write_json(project_root / "assets" / "registry.json", {
        "schema_version": 1, "assets": {}, "folders": {"image": [], "ocr": [], "page": []},
    })
    _write_json(project_root / "easycode.lock", {
        "lock_version": 1, "project_format": 6,
        "toolchain": {"compiler_version": "6.0.0", "program_schema": 1, "ecir": 1,
                      "pure_value_registry_version": PURE_OPERATION_REGISTRY_VERSION,
                      "pure_value_registry_sha256": pure_operation_registry_hash()},
        "official_functions": [], "extensions": [],
    })
    project = {
        "project_id": "acceptance_file_http", "name": "文件与 HTTP 验收",
        "targets_schema_version": 1, "targets": [], "default_target_id": None,
        "target_configuration_revision": target_configuration_revision(
            TargetConfiguration(schema_version=1, targets=(), default_target_id=None)
        ),
    }
    _write_json(project_root / "project.json", project)
    linked = _linked(base_url, refs)
    form = {"schema_version": 3, "title": "文件与 HTTP 验收", "pages": []}
    publisher = VNextPublisher(str(project_root), signing_key_store=AuthorSigningKeyStore(output / "keys"))
    report = publisher.report(linked, form)
    if not report.get("valid"):
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
    published = publisher.build(linked, form, project, report)
    bundle = output / "file-http.ecplayer"
    shutil.copyfile(published["path"], bundle)
    trust_root = output / "trust-root.json"
    _write_json(trust_root, trust_root_document(published["signature"], project["project_id"]))
    return {"bundle": bundle, "trust_root": trust_root, "release_id": published["release_id"], "report": report}


def _request_json(url: str, *, method: str = "GET", body: dict[str, Any] | None = None,
                  headers: dict[str, str] | None = None) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method=method, headers={
        "Content-Type": "application/json", **(headers or {}),
    })
    with urllib.request.urlopen(request, timeout=15.0) as response:
        return json.loads(response.read().decode("utf-8"))


def run(candidate: Path, output: Path) -> dict[str, Any]:
    candidate = candidate.resolve()
    output = output.resolve()
    executable = candidate / "EasycodePlayer.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"输出目录必须为空，不会覆盖现有证据：{output}")
    output.mkdir(parents=True, exist_ok=True)
    data = output / "data"
    data.mkdir()
    _Fixture.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Fixture)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    created = _create_bundle(output, base_url, data)
    port = _free_port()
    player_data = output / "player-data"
    environment = dict(os.environ)
    environment["LOCALAPPDATA"] = os.fspath(player_data)
    process = subprocess.Popen(
        [os.fspath(executable), "--mode", "dev", "--port", str(port),
         "--player-bundle", os.fspath(created["bundle"]),
         "--player-trust-root", os.fspath(created["trust_root"])],
        cwd=os.fspath(candidate), env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        ready_ms, bootstrap = _bootstrap(port)
        api = f"http://127.0.0.1:{port}"
        started = _request_json(
            f"{api}/api/vnext/player/runtime/run", method="POST", body={},
            headers={"Idempotency-Key": f"file-http-{uuid.uuid4().hex}"},
        )
        execution_id = str(started["execution_id"])
        deadline = time.monotonic() + 60.0
        terminal = started
        while time.monotonic() < deadline:
            terminal = _request_json(f"{api}/api/vnext/runs/{execution_id}")
            if str(terminal.get("status")) in {"completed", "failed", "cancelled", "stopped"}:
                break
            time.sleep(0.1)
        if terminal.get("status") != "completed":
            raise RuntimeError(json.dumps(terminal, ensure_ascii=False, indent=2))
        upload_calls = [item for item in _Fixture.calls if item["path"] == "/upload"]
        checks = {
            "text_content": (data / "text.txt").read_text(encoding="utf-8") == "A=true\nA=true",
            "failed_download_preserved": (data / "failed-download.txt").read_text(encoding="utf-8") == "preserve-old",
            "download_content": (data / "download.txt").read_bytes() == b"download-payload",
            "upload_received": len(upload_calls) == 1 and upload_calls[0]["contains_upload_payload"] is True,
            "no_download_temp_files": not list(data.glob(".easycode-download-*.tmp")),
        }
        if not all(checks.values()):
            raise RuntimeError(f"宿主证据检查失败：{checks}")
        bundle_signature = bootstrap.get("bundle", {}).get("signature") or {}
        if not bundle_signature:
            raise RuntimeError("冻结 Player 已运行项目，但 bootstrap 未返回已验证的签名身份")
        evidence = {
            "schema_version": 1,
            "status": "passed",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "candidate": str(candidate),
            "player_sha256": _sha256(executable),
            "bundle": str(created["bundle"]),
            "bundle_sha256": _sha256(created["bundle"]),
            "bundle_release_id": created["release_id"],
            # PlayerBundleManager only becomes available after signature and
            # integrity verification; bootstrap exposes that accepted identity.
            "signature_verified": True,
            "signing_key_id": str(bundle_signature.get("key_id") or ""),
            "runtime_release_id": str(bootstrap.get("bundle", {}).get("release_id") or ""),
            "ready_ms": round(ready_ms, 3),
            "execution_id": execution_id,
            "execution_status": terminal["status"],
            "checks": checks,
            "http_calls": list(_Fixture.calls),
            "network_level": created["report"].get("network_level"),
            "required_capabilities": created["report"].get("required_capabilities"),
        }
        _write_json(output / "file-http-evidence.json", evidence)
        return evidence
    finally:
        server.shutdown()
        server.server_close()
        _stop([process])


def main() -> int:
    parser = argparse.ArgumentParser(description="运行冻结 Windows Player 文件与 HTTP 真实验收")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.candidate, arguments.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
