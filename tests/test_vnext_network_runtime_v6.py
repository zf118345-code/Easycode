from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import ssl
import threading
import time
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from core.vnext.file_runtime_v6 import windows_file_reference
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.network_publish_v6 import NetworkPublishClosureError, network_publish_report
from core.vnext.network_runtime_v6 import (
    NetworkRuntimeV6,
    merge_network_authorizations,
    static_network_authorization,
)
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    BoolValue,
    CallStatement,
    ListValue,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    RecordValue,
    ResultBinding,
    StringValue,
    SymbolReferenceValue,
)
from core.vnext.publish import VNextPublisher
from core.vnext.runtime import RuntimeFailure, VNextRuntime

REQUEST = "official.network.request"
UPLOAD = "official.network.upload_file"
DOWNLOAD = "official.network.download_file"


def _args(function_id: str, **values: Any) -> dict[str, Any]:
    return {
        f"{function_id}.parameter.{name}": value
        for name, value in values.items()
    }


def _field(record: dict[str, Any], name: str) -> Any:
    return record[f'{record["record_type"]}.field.{name}']


def _record(owner: str, **fields: Any) -> dict[str, Any]:
    return {
        "record_type": owner,
        **{f"{owner}.field.{name}": value for name, value in fields.items()},
    }


class _HTTPFixture(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    calls: list[dict[str, Any]] = []
    external_redirect = ""

    def log_message(self, *_: Any) -> None:
        return

    def _body(self) -> bytes:
        length = int(self.headers.get("content-length") or 0)
        return self.rfile.read(length)

    def _record(self, body: bytes) -> None:
        self.__class__.calls.append({
            "method": self.command,
            "path": self.path,
            "query": parse_qsl(urlsplit(self.path).query, keep_blank_values=True),
            "repeat_headers": self.headers.get_all("X-Repeat") or [],
            "authorization": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type") or "",
            "body": body,
        })

    def _send(self, status: int, body: bytes, content_type: str = "text/plain; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Response", "first")
        self.send_header("X-Response", "second")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _dispatch(self) -> None:
        body = self._body()
        self._record(body)
        path = urlsplit(self.path).path
        if path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/echo?redirected=yes")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/redirect-external":
            self.send_response(302)
            self.send_header("Location", self.__class__.external_redirect)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/status":
            self._send(422, b'{"error":"business"}', "application/json")
            return
        if path == "/binary":
            self._send(200, b"\x00\x01\x02", "application/octet-stream")
            return
        if path == "/large":
            self._send(200, b"x" * 4096)
            return
        if path == "/slow":
            time.sleep(0.25)
            self._send(200, b"late")
            return
        if path == "/upload":
            self._send(201, b"uploaded")
            return
        if path == "/download":
            self._send(200, b"download-payload", "application/octet-stream")
            return
        if path == "/download-error":
            self._send(503, b"try later")
            return
        if path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"short")
            self.wfile.flush()
            self.close_connection = True
            return
        if path == "/slow-download":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", "10")
            self.end_headers()
            self.wfile.write(b"first")
            self.wfile.flush()
            time.sleep(0.25)
            try:
                self.wfile.write(b"last!")
                self.wfile.flush()
            except OSError:
                pass
            return
        if path == "/drop":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"short")
            self.wfile.flush()
            self.close_connection = True
            with suppress(OSError):
                self.connection.shutdown(socket.SHUT_RDWR)
            return
        payload = json.dumps({
            "method": self.command,
            "query": parse_qsl(urlsplit(self.path).query, keep_blank_values=True),
            "repeat_headers": self.headers.get_all("X-Repeat") or [],
            "content_type": self.headers.get("Content-Type") or "",
            "body": body.decode("utf-8"),
        }, ensure_ascii=False).encode("utf-8")
        self._send(200, payload, "application/json; charset=utf-8")

    do_GET = _dispatch
    do_HEAD = _dispatch
    do_POST = _dispatch
    do_PUT = _dispatch
    do_PATCH = _dispatch
    do_DELETE = _dispatch


@contextmanager
def _server():
    _HTTPFixture.calls = []
    _HTTPFixture.external_redirect = ""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HTTPFixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def _untrusted_https_server(directory: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1"),
    ])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "server-cert.pem"
    key_path = directory / "server-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HTTPFixture)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _execute(opcode: str, fid: str, url: str, values: dict[str, Any], **kwargs: Any):
    logs: list[dict[str, Any]] = []
    result = NetworkRuntimeV6().execute(
        opcode,
        fid,
        _args(fid, url=url, **values),
        static_network_authorization(url),
        kwargs.get("cancelled", lambda: False),
        logs.append,
    )
    return result, logs


def test_network_contracts_are_three_distinct_typed_atoms():
    request = official_function_registry_v6.require(REQUEST)
    upload = official_function_registry_v6.require(UPLOAD)
    download = official_function_registry_v6.require(DOWNLOAD)
    assert {item.opcode for item in (request, upload, download)} == {
        "network.request", "network.upload_file", "network.download_file",
    }
    request_types = {item.name: item.value_type for item in request.parameters}
    assert request_types["query"] == "list<http_pair>"
    assert request_types["headers"] == "list<http_pair>"
    assert request_types["body"] == "optional<http_body>"
    assert "file_ref" not in " ".join(request_types.values())
    assert {item.name for item in upload.parameters} >= {
        "fields", "query", "headers", "redirect", "timeout", "max_file_bytes",
    }
    assert {item.name for item in download.parameters} >= {
        "destination", "query", "headers", "redirect", "timeout", "max_file_bytes",
    }
    assert upload.permissions == ("network", "filesystem.read")
    assert download.permissions == ("network", "filesystem.write")
    assert all(item.verified_platforms == ("windows", "android_adb", "no_target") for item in (
        request, upload, download,
    ))
    assert all("android_local" not in item.verified_platforms for item in (
        request, upload, download,
    ))


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
def test_request_preserves_methods_repeated_query_and_headers(method: str):
    with _server() as base:
        result, logs = _execute(
            "network.request",
            REQUEST,
            f"{base}/echo?existing=1",
            {
                "method": method,
                "query": [
                    _record("http_pair", name="tag", value="a", sensitive=False),
                    _record("http_pair", name="tag", value="b", sensitive=False),
                ],
                "headers": [
                    _record("http_pair", name="X-Repeat", value="first", sensitive=False),
                    _record("http_pair", name="X-Repeat", value="second", sensitive=False),
                ],
                "body": (
                    _record("http_body", kind="text", text="hello", content_type=None)
                    if method not in {"GET", "HEAD"}
                    else None
                ),
            },
        )
    assert result["record_type"] == "http_response"
    assert _field(result, "status") == 200
    if method != "HEAD":
        echoed = json.loads(_field(result, "body"))
        assert echoed["query"] == [["existing", "1"], ["tag", "a"], ["tag", "b"]]
        assert echoed["repeat_headers"] == ["first", "second"]
    assert logs[0]["event"] == "network.request_finished"
    assert "?" not in logs[0]["url"]
    assert logs[0]["error_id"] == ""


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_request_rejects_body_for_bodyless_methods_before_network(method: str):
    with pytest.raises(RuntimeFailure) as failure:
        _execute(
            "network.request",
            REQUEST,
            "http://127.0.0.1:9/not-contacted",
            {
                "method": method,
                "body": _record("http_body", kind="text", text="unexpected", content_type=None),
            },
        )
    assert failure.value.error_id == "network.body_not_allowed"


def test_request_json_redirect_and_http_error_are_typed_results():
    with _server() as base:
        json_result, _ = _execute(
            "network.request",
            REQUEST,
            f"{base}/echo",
            {"method": "POST", "body": {"kind": "json", "value": {"name": "中文"}}},
        )
        redirected, _ = _execute(
            "network.request",
            REQUEST,
            f"{base}/redirect",
            {"redirect": "same_origin"},
        )
        failure_response, _ = _execute(
            "network.request",
            REQUEST,
            f"{base}/status",
            {},
        )
    echoed = json.loads(_field(json_result, "body"))
    assert echoed["content_type"].startswith("application/json")
    assert json.loads(echoed["body"]) == {"name": "中文"}
    assert _field(redirected, "status") == 200
    assert _field(redirected, "final_url").endswith("/echo?redirected=yes")
    assert _field(failure_response, "status") == 422
    assert json.loads(_field(failure_response, "body")) == {"error": "business"}


def test_request_rejects_binary_oversize_and_unapproved_targets():
    with _server() as base:
        with pytest.raises(RuntimeFailure) as binary:
            _execute("network.request", REQUEST, f"{base}/binary", {})
        with pytest.raises(RuntimeFailure) as large:
            _execute(
                "network.request",
                REQUEST,
                f"{base}/large",
                {"max_response_bytes": 100},
            )
        authorization = static_network_authorization(f"{base}/echo")
        with pytest.raises(RuntimeFailure) as denied:
            NetworkRuntimeV6().execute(
                "network.request",
                REQUEST,
                _args(REQUEST, url="http://localhost:1/"),
                authorization,
                lambda: False,
            )
    assert binary.value.error_id == "network.binary_response_unsupported"
    assert large.value.error_id == "network.response_too_large"
    assert denied.value.error_id == "network.permission_denied"


def test_cross_origin_redirect_reauthorizes_and_strips_sensitive_headers():
    with _server() as first, _server() as second:
        _HTTPFixture.external_redirect = f"{second}/echo"
        authorization = merge_network_authorizations(
            static_network_authorization(f"{first}/redirect-external"),
            static_network_authorization(f"{second}/echo"),
        )
        result = NetworkRuntimeV6().execute(
            "network.request",
            REQUEST,
            _args(
                REQUEST,
                url=f"{first}/redirect-external",
                redirect="cross_origin",
                headers=[
                    {"name": "Authorization", "value": "Bearer must-not-leak"},
                    {"name": "X-Normal", "value": "kept"},
                ],
            ),
            authorization,
            lambda: False,
        )
        destination = _HTTPFixture.calls[-1]
    assert _field(result, "status") == 200
    assert destination["authorization"] is None
    assert "must-not-leak" not in json.dumps(result, ensure_ascii=False)


def test_total_timeout_is_structured_and_does_not_retry():
    with _server() as base:
        with pytest.raises(RuntimeFailure) as failure:
            _execute(
                "network.request",
                REQUEST,
                f"{base}/slow",
                {"timeout": 50},
            )
        calls = [item for item in _HTTPFixture.calls if urlsplit(item["path"]).path == "/slow"]
    assert failure.value.error_id == "network.timeout"
    assert failure.value.transient is True
    assert len(calls) == 1


def test_tls_verification_cannot_be_disabled(tmp_path: Path):
    with _untrusted_https_server(tmp_path) as base, pytest.raises(RuntimeFailure) as failure:
        _execute("network.request", REQUEST, f"{base}/echo", {})
    assert failure.value.error_id == "network.tls_failed"


def test_request_transport_failure_is_not_retried():
    with _server() as base:
        with pytest.raises(RuntimeFailure) as failure:
            _execute(
                "network.request",
                REQUEST,
                f"{base}/drop",
                {"method": "POST", "body": {"kind": "text", "text": "one"}},
            )
        calls = [item for item in _HTTPFixture.calls if urlsplit(item["path"]).path == "/drop"]
    assert failure.value.error_id in {"network.response_interrupted", "network.protocol_failed"}
    assert len(calls) == 1


def test_multipart_upload_streams_authorized_file_and_keeps_field_order(tmp_path: Path):
    payload = ("文件内容" * 128).encode("utf-8")
    source = tmp_path / "源 文件.bin"
    source.write_bytes(payload)
    reference = windows_file_reference(str(source), str(tmp_path), access=("read",))
    with _server() as base:
        result, logs = _execute(
            "network.upload_file",
            UPLOAD,
            f"{base}/upload",
            {
                "fields": [
                    _record("multipart_field", kind="text", name="same", value="first"),
                    _record(
                        "multipart_field",
                        kind="file",
                        name="same",
                        file=reference,
                        filename="资料.bin",
                    ),
                    _record("multipart_field", kind="text", name="same", value="last"),
                ],
            },
        )
        captured = _HTTPFixture.calls[-1]["body"]
    assert _field(result, "status") == 201
    assert payload in captured
    assert captured.index(b"first") < captured.index(payload) < captured.index(b"last")
    assert "资料.bin".encode() in captured
    assert logs[0]["operation"] == "upload"
    assert str(source) not in json.dumps(logs, ensure_ascii=False)
    assert hashlib.sha256(payload).digest()  # fixed payload evidence without logging bytes


def test_download_commits_only_complete_2xx_and_preserves_old_target(tmp_path: Path):
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")
    reference = windows_file_reference(str(destination), str(tmp_path), access=("write",))
    with _server() as base:
        error_result, _ = _execute(
            "network.download_file",
            DOWNLOAD,
            f"{base}/download-error",
            {"destination": reference},
        )
        assert destination.read_bytes() == b"old"
        assert _field(error_result, "status") == 503
        assert _field(error_result, "committed") is False
        assert _field(error_result, "file") is None

        with pytest.raises(RuntimeFailure) as too_large:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/download",
                {"destination": reference, "max_file_bytes": 4},
            )
        assert destination.read_bytes() == b"old"

        result, logs = _execute(
            "network.download_file",
            DOWNLOAD,
            f"{base}/download",
            {"destination": reference},
        )
    assert too_large.value.error_id == "network.download_too_large"
    assert destination.read_bytes() == b"download-payload"
    assert _field(result, "committed") is True
    assert _field(result, "bytes_written") == len(b"download-payload")
    assert _field(result, "file") == reference
    assert not list(tmp_path.glob(".easycode-download-*.tmp"))
    assert str(destination) not in json.dumps(logs, ensure_ascii=False)


def test_download_truncation_and_cancellation_preserve_old_target(tmp_path: Path):
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")
    reference = windows_file_reference(str(destination), str(tmp_path), access=("write",))
    with _server() as base:
        with pytest.raises(RuntimeFailure) as truncated:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/truncated",
                {"destination": reference},
            )
        with pytest.raises(RuntimeFailure) as cancelled:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/download",
                {"destination": reference},
                cancelled=lambda: True,
            )
    assert truncated.value.error_id in {"network.download_interrupted", "network.response_interrupted"}
    assert cancelled.value.error_id == "runtime.cancelled"
    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".easycode-download-*.tmp"))


def test_download_midstream_cancel_and_commit_failure_preserve_old_target(
    tmp_path: Path,
    monkeypatch,
):
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")
    reference = windows_file_reference(str(destination), str(tmp_path), access=("write",))
    with _server() as base:
        cancel_after = time.monotonic() + 0.05
        with pytest.raises(RuntimeFailure) as cancelled:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/slow-download",
                {"destination": reference},
                cancelled=lambda: time.monotonic() >= cancel_after,
            )
        assert destination.read_bytes() == b"old"

        original_replace = os.replace

        def reject_download_commit(source: str, target: str) -> None:
            if os.path.basename(source).startswith(".easycode-download-"):
                raise OSError("injected commit failure")
            original_replace(source, target)

        monkeypatch.setattr(os, "replace", reject_download_commit)
        with pytest.raises(RuntimeFailure) as commit:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/download",
                {"destination": reference},
            )
    assert cancelled.value.error_id == "runtime.cancelled"
    assert commit.value.error_id == "file.atomic_commit_failed"
    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".easycode-download-*.tmp"))


def test_file_authorization_is_checked_before_network_connection(tmp_path: Path):
    destination = tmp_path / "result.bin"
    destination.write_bytes(b"old")
    denied_reference = windows_file_reference(
        str(destination),
        str(tmp_path),
        access=("read",),
    )
    with _server() as base:
        with pytest.raises(RuntimeFailure) as denied:
            _execute(
                "network.download_file",
                DOWNLOAD,
                f"{base}/download",
                {"destination": denied_reference},
            )
        calls = list(_HTTPFixture.calls)
    assert denied.value.error_id == "file.access_denied"
    assert calls == []
    assert destination.read_bytes() == b"old"


def test_authorization_rejects_non_http_credentials_and_dns_scope(monkeypatch):
    with pytest.raises(RuntimeFailure) as scheme:
        static_network_authorization("file:///tmp/data")
    with pytest.raises(RuntimeFailure) as credentials:
        static_network_authorization("https://user:secret@example.com/")
    authorization = static_network_authorization("https://example.com/")
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(RuntimeFailure) as rebinding:
        NetworkRuntimeV6().execute(
            "network.request",
            REQUEST,
            _args(REQUEST, url="https://example.com/"),
            authorization,
            lambda: False,
        )
    assert scheme.value.error_id == "network.scheme_denied"
    assert credentials.value.error_id == "network.credentials_in_url"
    assert rebinding.value.error_id == "network.address_scope_denied"


def test_compiler_embeds_exact_origin_and_runtime_executes_the_same_ecir():
    with _server() as base:
        url = f"{base}/echo"
        document = ProgramDocument(
            document_id="document_network",
            function=ProgramFunction(
                function_id="function_network",
                display_name="网络测试",
                statements=(CallStatement(
                    statement_id="statement_request",
                    function_id=REQUEST,
                    arguments={
                        f"{REQUEST}.parameter.url": StringValue(
                            value_id="value_url",
                            value=url,
                        ),
                        f"{REQUEST}.parameter.query": ListValue(
                            value_id="value_query",
                            item_type="http_pair",
                            items=(RecordValue(
                                value_id="value_query_pair",
                                record_type="http_pair",
                                fields={
                                    "http_pair.field.name": StringValue(
                                        value_id="value_query_name", value="tag"
                                    ),
                                    "http_pair.field.value": StringValue(
                                        value_id="value_query_value", value="compiled"
                                    ),
                                    "http_pair.field.sensitive": BoolValue(
                                        value_id="value_query_sensitive", value=False
                                    ),
                                },
                            ),),
                        ),
                    },
                    result_binding=ResultBinding(
                        symbol_id="response",
                        display_name="响应",
                        value_type="http_response",
                    ),
                ),),
            ),
        )
        compiled = compile_program_document(
            document,
            official_function_registry_v6,
            target_platform="no_target",
        )
        assert compiled["valid"] is True, compiled["diagnostics"]
        instruction = compiled["ecir"]["functions"][0]["instructions"][0]
        assert instruction["network_authorization"]["rules"][0]["hosts"] == ["127.0.0.1"]
        runtime = VNextRuntime(persist_event_log=False)
        execution_id = runtime.start(
            adapt_program_ecir_for_runtime(compiled["ecir"]),
        )["execution_id"]
        deadline = time.monotonic() + 3
        snapshot: dict[str, Any] = {}
        while time.monotonic() < deadline:
            snapshot = runtime.snapshot(execution_id)
            if snapshot["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.01)
    assert snapshot["status"] == "completed", snapshot
    assert _field(snapshot["variables"]["response"], "status") == 200
    assert json.loads(_field(snapshot["variables"]["response"], "body"))["query"] == [
        ["tag", "compiled"]
    ]
    assert any(item["category"] == "network" for item in snapshot["events"])


def test_dynamic_url_requires_author_policy_and_policy_is_embedded():
    document = ProgramDocument(
        document_id="document_dynamic_network",
        function=ProgramFunction(
            function_id="function_dynamic_network",
            display_name="动态网络测试",
            parameters=(ProgramParameter(
                parameter_id="parameter_url",
                symbol_id="url_input",
                display_name="接口地址",
                value_type="url",
            ),),
            statements=(CallStatement(
                statement_id="statement_dynamic_request",
                function_id=REQUEST,
                arguments={
                    f"{REQUEST}.parameter.url": SymbolReferenceValue(
                        value_id="value_dynamic_url",
                        symbol_id="url_input",
                        value_type="url",
                    ),
                },
            ),),
        ),
    )
    denied = compile_program_document(document, official_function_registry_v6)
    assert denied["valid"] is False
    assert any(item["code"] == "PGM-NET-001" for item in denied["diagnostics"])

    allowed = compile_program_document(
        document,
        official_function_registry_v6,
        network_policies=[{
            "policy_id": "policy_api",
            "schemes": ["https"],
            "hosts": ["api.example.com"],
            "ports": [443],
            "address_scopes": ["public"],
        }],
    )
    assert allowed["valid"] is True, allowed["diagnostics"]
    authorization = allowed["ecir"]["functions"][0]["instructions"][0][
        "network_authorization"
    ]
    assert authorization["rules"] == [{
        "rule_id": "policy_api",
        "source": "project_policy",
        "schemes": ["https"],
        "hosts": ["api.example.com"],
        "ports": [443],
        "address_scopes": ["public"],
    }]


def test_publish_report_exposes_real_origins_and_file_permission_closure():
    public = static_network_authorization("http://api.example.com/v1?secret=hidden")
    local = static_network_authorization("http://127.0.0.1:8123/upload")
    ecir = {
        "functions": [{
            "function_id": "function_main",
            "instructions": [{
                "instruction_id": "request_public",
                "function_id": REQUEST,
                "opcode": "network.request",
                "network_authorization": public,
                "arguments": {},
            }, {
                "instruction_id": "upload_local",
                "function_id": UPLOAD,
                "opcode": "network.upload_file",
                "network_authorization": local,
                "arguments": {},
            }, {
                "instruction_id": "download_nested",
                "opcode": "control.if",
                "arguments": {
                    "then": [{
                        "instruction_id": "download_public",
                        "function_id": DOWNLOAD,
                        "opcode": "network.download_file",
                        "network_authorization": public,
                        "arguments": {},
                    }],
                },
            }],
        }],
    }
    report = network_publish_report(ecir)
    assert report["network_level"] == "public"
    assert report["file_permissions"] == ["filesystem.read", "filesystem.write"]
    assert {item["opcode"] for item in report["calls"]} == {
        "network.request", "network.upload_file", "network.download_file",
    }
    assert {host for item in report["sources"] for host in item["hosts"]} == {
        "api.example.com", "127.0.0.1",
    }
    serialized = json.dumps(report, ensure_ascii=False)
    assert "secret" not in serialized
    assert any(item["code"] == "P-NET-HTTP-PUBLIC" for item in report["warnings"])

    with pytest.raises(NetworkPublishClosureError):
        network_publish_report({
            "functions": [{
                "function_id": "function_main",
                "instructions": [{
                    "instruction_id": "missing_closure",
                    "opcode": "network.request",
                }],
            }],
        })


def test_publisher_blocks_missing_network_closure_and_reports_real_level(tmp_path: Path):
    authorization = static_network_authorization("https://api.example.com/v1")
    ecir = {
        "entry_function_id": "function_main",
        "supported_platforms": ["windows", "android_adb", "no_target"],
        "required_capabilities": ["network", "filesystem.write"],
        "functions": [{
            "function_id": "function_main",
            "name": "主程序",
            "parameter_definitions": [],
            "instructions": [{
                "instruction_id": "download",
                "function_id": DOWNLOAD,
                "opcode": "network.download_file",
                "network_authorization": authorization,
                "arguments": {},
            }],
        }],
    }
    publisher = VNextPublisher(str(tmp_path))
    form = {"schema_version": 3, "title": "Player", "pages": []}
    valid = publisher.report({"ecir": ecir, "diagnostics": []}, form)
    assert valid["valid"] is True, valid["errors"]
    assert valid["network_level"] == "public"
    assert valid["network"]["file_permissions"] == ["filesystem.write"]
    assert valid["network_sources"][0]["hosts"] == ["api.example.com"]

    missing_permission_ecir = {**ecir, "required_capabilities": ["network"]}
    missing_permission = publisher.report(
        {"ecir": missing_permission_ecir, "diagnostics": []},
        form,
    )
    assert missing_permission["valid"] is False
    assert any(item["code"] == "P2203" for item in missing_permission["errors"])

    missing_authorization_ecir = json.loads(json.dumps(ecir))
    del missing_authorization_ecir["functions"][0]["instructions"][0][
        "network_authorization"
    ]
    missing_authorization = publisher.report(
        {"ecir": missing_authorization_ecir, "diagnostics": []},
        form,
    )
    assert missing_authorization["valid"] is False
    assert any(item["code"] == "P2201" for item in missing_authorization["errors"])
