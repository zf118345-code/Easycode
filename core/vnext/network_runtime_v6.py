"""Typed HTTP runtime for format-6 programs.

The module deliberately owns only the three frozen network atoms.  It is not
a browser session and never keeps cookies between calls.  URL authorization
is carried by ECIR, checked again after DNS resolution and checked for every
redirect.  File bytes are streamed through authorized ``FileReference``
objects and never become ProgramDocument/runtime values or log payloads.
"""

from __future__ import annotations

import codecs
import contextlib
import ipaddress
import json
import os
import socket
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit

import httpcore
import httpx

from .file_runtime_v6 import _locked_paths, _validate_reference
from .runtime import RuntimeFailure


@contextlib.contextmanager
def _open_upload_source(path: str):
    """Open an authorised upload source and keep file errors structured."""

    try:
        with Path(path).open("rb") as stream:
            yield stream
    except OSError as exc:
        raise RuntimeFailure(
            "上传文件不可读取",
            error_id="file.read_failed",
        ) from exc

NETWORK_AUTHORIZATION_SCHEMA_VERSION = 1
DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_UPLOAD_FILE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 5
MAX_HEADER_COUNT = 256
MAX_PAIR_COUNT = 1024
_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}
_CROSS_ORIGIN_STRIP_HEADERS = _SENSITIVE_HEADERS | {"cookie2"}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class _ResolvedURL:
    url: str
    scheme: str
    host: str
    port: int
    origin: tuple[str, str, int]
    addresses: tuple[str, ...]
    scopes: tuple[str, ...]
    rule_id: str


class _CancelledUpload:
    """Small file proxy that checks cancellation on every streamed read."""

    def __init__(
        self,
        stream: BinaryIO,
        cancelled: Callable[[], bool],
        *,
        maximum: int,
    ) -> None:
        self._stream = stream
        self._cancelled = cancelled
        self._maximum = maximum
        self._read = 0

    def read(self, size: int = -1) -> bytes:
        _cancel(self._cancelled, phase="upload")
        data = self._stream.read(size)
        self._read += len(data)
        if self._read > self._maximum:
            raise RuntimeFailure(
                "上传文件超过允许大小",
                error_id="network.upload_too_large",
            )
        return data

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        value = self._stream.seek(offset, whence)
        if whence == os.SEEK_SET and offset == 0:
            self._read = 0
        return value

    def tell(self) -> int:
        return self._stream.tell()

    def fileno(self) -> int:
        return self._stream.fileno()

    @property
    def name(self) -> str:
        return str(getattr(self._stream, "name", "upload"))

    def close(self) -> None:
        self._stream.close()

    @property
    def closed(self) -> bool:
        return bool(self._stream.closed)


class _PinnedNetworkBackend(httpcore.SyncBackend):
    """Connect only to the IP addresses that passed the authorization check."""

    def __init__(self, resolved: _ResolvedURL) -> None:
        super().__init__()
        self._resolved = resolved

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[tuple[int, int, int | bytes]] | None = None,
    ) -> httpcore.NetworkStream:
        normalized = _normalize_host(host.decode("ascii") if isinstance(host, bytes) else host)
        if normalized != self._resolved.host or int(port) != self._resolved.port:
            raise httpcore.ConnectError("transport target does not match authorized origin")
        last_error: Exception | None = None
        for address in self._resolved.addresses:
            try:
                return super().connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("authorized origin has no approved address")


class _PinnedHTTPTransport(httpx.HTTPTransport):
    """HTTPX transport whose TCP backend cannot perform a second DNS lookup."""

    def __init__(self, resolved: _ResolvedURL) -> None:
        super().__init__(
            verify=True,
            trust_env=True,
            retries=0,
            limits=httpx.Limits(
                max_connections=1,
                max_keepalive_connections=0,
                keepalive_expiry=0,
            ),
        )
        ssl_context = self._pool._ssl_context  # type: ignore[attr-defined]
        self._pool.close()  # type: ignore[attr-defined]
        self._pool = httpcore.ConnectionPool(  # type: ignore[attr-defined]
            ssl_context=ssl_context,
            max_connections=1,
            max_keepalive_connections=0,
            keepalive_expiry=0,
            retries=0,
            network_backend=_PinnedNetworkBackend(resolved),
        )


def _argument(arguments: Mapping[str, Any], function_id: str, name: str) -> Any:
    return arguments.get(f"{function_id}.parameter.{name}")


def _record_field(value: Mapping[str, Any], owner: str, name: str) -> Any:
    """Read the stable field ID; plain keys remain a direct-adapter convenience."""

    stable = f"{owner}.field.{name}"
    return value[stable] if stable in value else value.get(name)


def _record_value(owner: str, **fields: Any) -> dict[str, Any]:
    return {
        "record_type": owner,
        **{f"{owner}.field.{name}": value for name, value in fields.items()},
    }


def _cancel(cancelled: Callable[[], bool], *, phase: str = "request") -> None:
    if cancelled():
        raise RuntimeFailure(
            f"网络操作已取消（阶段：{phase}）",
            error_id="runtime.cancelled",
        )


def _duration_seconds(value: Any, default_milliseconds: int) -> float:
    raw = default_milliseconds if value is None else value
    if isinstance(raw, Mapping) and raw.get("kind") == "duration":
        raw = raw.get("milliseconds")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise RuntimeFailure("网络超时必须是持续时间", error_id="network.timeout_invalid")
    milliseconds = float(raw)
    if milliseconds <= 0 or milliseconds > 24 * 60 * 60 * 1000:
        raise RuntimeFailure(
            "网络超时必须大于 0 且不超过 24 小时",
            error_id="network.timeout_invalid",
        )
    return milliseconds / 1000.0


def _bounded_integer(value: Any, default: int, *, minimum: int, maximum: int, error_id: str) -> int:
    raw = default if value is None else value
    if isinstance(raw, bool) or not isinstance(raw, int) or not minimum <= raw <= maximum:
        raise RuntimeFailure(
            f"数值必须位于 {minimum} 到 {maximum} 之间",
            error_id=error_id,
        )
    return raw


def _normalize_host(host: str) -> str:
    try:
        return host.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise RuntimeFailure("URL 主机名无效", error_id="network.url_invalid") from exc


def _parse_url(raw_url: Any) -> tuple[str, str, int, tuple[str, str, int]]:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise RuntimeFailure("URL 不能为空", error_id="network.url_invalid")
    value = raw_url.strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise RuntimeFailure("URL 不能包含控制字符", error_id="network.url_invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise RuntimeFailure("URL 端口或结构无效", error_id="network.url_invalid") from exc
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise RuntimeFailure(
            "网络函数只允许 http 或 https URL",
            error_id="network.scheme_denied",
        )
    if parsed.username is not None or parsed.password is not None:
        raise RuntimeFailure(
            "URL 不允许内嵌用户名或密码",
            error_id="network.credentials_in_url",
        )
    if not parsed.hostname:
        raise RuntimeFailure("URL 缺少主机名", error_id="network.url_invalid")
    host = _normalize_host(parsed.hostname)
    selected_port = int(port or (443 if scheme == "https" else 80))
    if not 1 <= selected_port <= 65535:
        raise RuntimeFailure("URL 端口无效", error_id="network.url_invalid")
    return scheme, host, selected_port, (scheme, host, selected_port)


def _address_scope(address: str) -> str:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if ip.is_loopback:
        return "loopback"
    if ip.is_private or ip.is_link_local:
        return "lan"
    if ip.is_global:
        return "public"
    raise RuntimeFailure(
        "目标解析到不可路由或保留地址",
        error_id="network.address_scope_denied",
    )


def _syntactic_scope(host: str) -> str:
    try:
        return _address_scope(host)
    except ValueError:
        if host == "localhost" or host.endswith(".localhost"):
            return "loopback"
        # A normal DNS name is public unless the author explicitly creates a
        # LAN rule.  This default rejects public-name-to-private-address DNS
        # rebinding instead of silently broadening access.
        return "public"


def _resolve(host: str, port: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RuntimeFailure(
            "无法解析网络目标",
            error_id="network.dns_failed",
            transient=True,
        ) from exc
    addresses = tuple(dict.fromkeys(str(record[4][0]).split("%", 1)[0] for record in records))
    if not addresses:
        raise RuntimeFailure(
            "网络目标没有可用地址",
            error_id="network.dns_failed",
            transient=True,
        )
    scopes = tuple(dict.fromkeys(_address_scope(address) for address in addresses))
    return addresses, scopes


def _canonical_rule(raw: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = str(raw.get("rule_id") or raw.get("policy_id") or "").strip()
    if not rule_id:
        raise ValueError("network rule requires rule_id")
    schemes = tuple(sorted({str(value).lower() for value in raw.get("schemes") or ()}))
    if not schemes or any(value not in {"http", "https"} for value in schemes):
        raise ValueError(f"network rule {rule_id} has invalid schemes")
    hosts = tuple(sorted({_normalize_host(str(value)) for value in raw.get("hosts") or ()}))
    if not hosts:
        raise ValueError(f"network rule {rule_id} requires exact hosts")
    ports = tuple(sorted({int(value) for value in raw.get("ports") or ()}))
    if not ports or any(not 1 <= value <= 65535 for value in ports):
        raise ValueError(f"network rule {rule_id} has invalid ports")
    scopes = tuple(sorted({str(value) for value in raw.get("address_scopes") or ()}))
    if not scopes or any(value not in {"loopback", "lan", "public"} for value in scopes):
        raise ValueError(f"network rule {rule_id} has invalid address scopes")
    return {
        "rule_id": rule_id,
        "source": str(raw.get("source") or "project_policy"),
        "schemes": list(schemes),
        "hosts": list(hosts),
        "ports": list(ports),
        "address_scopes": list(scopes),
    }


def normalize_network_authorization(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeFailure(
            "网络调用缺少编译期授权闭包",
            error_id="network.permission_denied",
        )
    if int(value.get("schema_version") or 0) != NETWORK_AUTHORIZATION_SCHEMA_VERSION:
        raise RuntimeFailure(
            "网络授权闭包版本不受支持",
            error_id="network.permission_denied",
        )
    try:
        rules = [_canonical_rule(item) for item in value.get("rules") or ()]
    except (TypeError, ValueError, RuntimeFailure) as exc:
        raise RuntimeFailure(
            "网络授权闭包无效",
            error_id="network.permission_denied",
        ) from exc
    if not rules:
        raise RuntimeFailure(
            "网络调用没有获批目标",
            error_id="network.permission_denied",
        )
    return {"schema_version": NETWORK_AUTHORIZATION_SCHEMA_VERSION, "rules": rules}


def static_network_authorization(url: str) -> dict[str, Any]:
    """Create a deterministic exact-origin authorization for a literal URL."""

    scheme, host, port, _ = _parse_url(url)
    origin = f"{scheme}://{host}:{port}"
    return {
        "schema_version": NETWORK_AUTHORIZATION_SCHEMA_VERSION,
        "rules": [{
            "rule_id": f"static:{origin}",
            "source": "static_url",
            "schemes": [scheme],
            "hosts": [host],
            "ports": [port],
            "address_scopes": [_syntactic_scope(host)],
        }],
    }


def project_network_authorization(policies: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Normalize author-approved dynamic-origin policies for compiler ECIR."""

    return {
        "schema_version": NETWORK_AUTHORIZATION_SCHEMA_VERSION,
        "rules": [_canonical_rule(item) for item in policies],
    }


def merge_network_authorizations(*values: Mapping[str, Any]) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    for value in values:
        normalized = normalize_network_authorization(value)
        for rule in normalized["rules"]:
            existing = rules.get(rule["rule_id"])
            if existing is not None and existing != rule:
                raise ValueError(f'network rule id collision: {rule["rule_id"]}')
            rules[rule["rule_id"]] = rule
    return {
        "schema_version": NETWORK_AUTHORIZATION_SCHEMA_VERSION,
        "rules": [rules[key] for key in sorted(rules)],
    }


def _authorize_url(url: str, authorization: Mapping[str, Any]) -> _ResolvedURL:
    scheme, host, port, origin = _parse_url(url)
    normalized = normalize_network_authorization(authorization)
    matching = [
        rule
        for rule in normalized["rules"]
        if scheme in rule["schemes"] and host in rule["hosts"] and port in rule["ports"]
    ]
    if not matching:
        raise RuntimeFailure(
            "网络目标不在作者批准的主机和端口范围内",
            error_id="network.permission_denied",
        )
    addresses, scopes = _resolve(host, port)
    rule = next(
        (item for item in matching if set(scopes).issubset(set(item["address_scopes"]))),
        None,
    )
    if rule is None:
        raise RuntimeFailure(
            "域名解析结果超出作者批准的地址范围",
            error_id="network.address_scope_denied",
        )
    return _ResolvedURL(
        url=url,
        scheme=scheme,
        host=host,
        port=port,
        origin=origin,
        addresses=addresses,
        scopes=scopes,
        rule_id=str(rule["rule_id"]),
    )


def _pair_list(value: Any, *, header: bool = False) -> list[tuple[str, str, bool]]:
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > (MAX_HEADER_COUNT if header else MAX_PAIR_COUNT):
        raise RuntimeFailure(
            "请求键值字段必须是有序列表且数量受限",
            error_id="network.pairs_invalid",
        )
    result: list[tuple[str, str, bool]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuntimeFailure("请求键值项无效", error_id="network.pairs_invalid")
        name = str(_record_field(item, "http_pair", "name") or "")
        raw = _record_field(item, "http_pair", "value")
        if not name or raw is None:
            raise RuntimeFailure("请求键值项缺少名称或值", error_id="network.pairs_invalid")
        text = str(raw)
        if any(character in name for character in "\r\n:") or any(character in text for character in "\r\n"):
            raise RuntimeFailure("请求键值项包含非法控制符", error_id="network.pairs_invalid")
        lowered = name.lower()
        if header and lowered in {"host", "content-length", "transfer-encoding", "connection"}:
            raise RuntimeFailure(
                f"请求头 {name} 由传输层管理",
                error_id="network.header_denied",
            )
        sensitive = bool(_record_field(item, "http_pair", "sensitive")) or (
            header and lowered in _SENSITIVE_HEADERS
        )
        result.append((name, text, sensitive))
    return result


def _append_query(url: str, pairs: Sequence[tuple[str, str, bool]]) -> str:
    if not pairs:
        return url
    parsed = urlsplit(url)
    added = urlencode([(name, value) for name, value, _ in pairs], doseq=False)
    query = f"{parsed.query}&{added}" if parsed.query else added
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def _request_body(value: Any) -> tuple[bytes | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, Mapping):
        raise RuntimeFailure(
            "普通网络请求正文只支持文本或 JSON",
            error_id="network.body_invalid",
        )
    kind = str(
        _record_field(value, "http_body", "kind")
        or value.get("body_type")
        or ""
    )
    if kind == "text":
        text = _record_field(value, "http_body", "text")
        if text is None:
            text = _record_field(value, "http_body", "value")
        if not isinstance(text, str):
            raise RuntimeFailure("文本请求正文无效", error_id="network.body_invalid")
        return text.encode("utf-8"), str(
            _record_field(value, "http_body", "content_type")
            or "text/plain; charset=utf-8"
        )
    if kind == "json":
        data = _record_field(value, "http_body", "json")
        if data is None:
            data = _record_field(value, "http_body", "value")
        try:
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise RuntimeFailure("JSON 请求正文无法序列化", error_id="network.body_invalid") from exc
        return encoded, "application/json; charset=utf-8"
    raise RuntimeFailure(
        "普通网络请求正文只支持文本或 JSON",
        error_id="network.body_invalid",
    )


def _response_headers(response: httpx.Response) -> list[dict[str, Any]]:
    return [
        _record_value("http_pair", name=name, value=value, sensitive=False)
        for name, value in response.headers.multi_items()
    ]


def _content_type(response: httpx.Response) -> str:
    return str(response.headers.get("content-type") or "")


def _ensure_text_response(response: httpx.Response, body: bytes) -> str:
    content_type = _content_type(response)
    media_type = content_type.split(";", 1)[0].strip().lower()
    textual = (
        not media_type
        or media_type.startswith("text/")
        or media_type in {
            "application/json",
            "application/xml",
            "application/x-www-form-urlencoded",
            "application/javascript",
        }
        or media_type.endswith("+json")
        or media_type.endswith("+xml")
    )
    if body and not textual:
        raise RuntimeFailure(
            "普通网络请求不接收二进制响应；请使用下载文件",
            error_id="network.binary_response_unsupported",
        )
    charset = response.charset_encoding or "utf-8"
    try:
        codecs.lookup(charset)
        return body.decode(charset, errors="strict")
    except (LookupError, UnicodeError) as exc:
        raise RuntimeFailure(
            "响应正文编码无效",
            error_id="network.response_encoding_failed",
        ) from exc


def _read_limited(
    response: httpx.Response,
    maximum: int,
    cancelled: Callable[[], bool],
    deadline: float,
    *,
    phase: str,
) -> bytes:
    content_length = response.headers.get("content-length")
    expected_length: int | None = None
    if content_length:
        try:
            expected_length = int(content_length)
            if expected_length > maximum:
                raise RuntimeFailure(
                    "响应正文超过允许大小",
                    error_id="network.response_too_large",
                )
        except ValueError:
            pass
    body = bytearray()
    try:
        for chunk in response.iter_bytes(chunk_size=64 * 1024):
            _cancel(cancelled, phase=phase)
            if time.monotonic() > deadline:
                raise RuntimeFailure(
                    "网络操作超过总超时",
                    error_id="network.timeout",
                    transient=True,
                )
            body.extend(chunk)
            if len(body) > maximum:
                raise RuntimeFailure(
                    "响应正文超过允许大小",
                    error_id="network.response_too_large",
                )
    except httpx.HTTPError as exc:
        raise RuntimeFailure(
            "响应读取中断",
            error_id="network.response_interrupted",
            transient=True,
        ) from exc
    # httpx yields decoded bytes.  When Content-Encoding is present the wire
    # Content-Length describes the encoded entity and must not be compared to
    # the decoded byte count.  The streaming size ceiling still applies to the
    # decoded bytes that the runtime actually retains.
    encoded = bool(response.headers.get("content-encoding"))
    if (
        response.request.method != "HEAD"
        and not encoded
        and expected_length is not None
        and len(body) != expected_length
    ):
        raise RuntimeFailure(
            "响应在完整接收前中断",
            error_id="network.response_interrupted",
            transient=True,
        )
    return bytes(body)


def _redacted_url(url: str) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    default = 443 if parsed.scheme.lower() == "https" else 80
    port = f":{parsed.port}" if parsed.port and parsed.port != default else ""
    path = quote(parsed.path or "/", safe="/%:@")
    return urlunsplit((parsed.scheme.lower(), f"{host}{port}", path, "", ""))


def _network_level(scopes: Iterable[str]) -> str:
    values = set(scopes)
    return "public" if "public" in values else "lan"


def _map_httpx_error(exc: Exception, cancelled: Callable[[], bool]) -> RuntimeFailure:
    if cancelled():
        return RuntimeFailure("网络操作已取消", error_id="runtime.cancelled")
    if isinstance(exc, httpx.TimeoutException):
        return RuntimeFailure("网络请求超时", error_id="network.timeout", transient=True)
    if isinstance(exc, httpx.ProxyError):
        return RuntimeFailure("代理连接失败", error_id="network.proxy_failed", transient=True)
    if isinstance(exc, httpx.ConnectError):
        message = str(exc).lower()
        if any(marker in message for marker in ("certificate", "ssl", "tls", "hostname")):
            return RuntimeFailure("TLS 或主机名验证失败", error_id="network.tls_failed")
        return RuntimeFailure("无法连接网络目标", error_id="network.unreachable", transient=True)
    if isinstance(exc, httpx.RemoteProtocolError):
        return RuntimeFailure("远端响应协议中断", error_id="network.response_interrupted", transient=True)
    if isinstance(exc, httpx.HTTPError):
        return RuntimeFailure("HTTP 传输失败", error_id="network.protocol_failed", transient=True)
    if isinstance(exc, OSError):
        return RuntimeFailure("网络或文件传输失败", error_id="network.transfer_failed", transient=True)
    return RuntimeFailure("网络传输失败", error_id="network.transfer_failed", transient=True)


class NetworkRuntimeV6:
    """Execute the three typed HTTP atoms without hidden retry/session state."""

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode in {
            "network.request",
            "network.upload_file",
            "network.download_file",
        }

    def execute(
        self,
        opcode: str,
        function_id: str,
        arguments: dict[str, Any],
        authorization: Mapping[str, Any],
        cancelled: Callable[[], bool],
        log: Callable[[dict[str, Any]], None] | None = None,
    ) -> Any:
        if not self.supports(opcode):
            raise RuntimeFailure(
                f"网络运行时不支持：{opcode}",
                error_id="network.operation_unsupported",
            )
        authorization = normalize_network_authorization(authorization)
        _cancel(cancelled)
        method = getattr(self, f'_execute_{opcode.replace(".", "_")}')
        return method(function_id, arguments, authorization, cancelled, log or (lambda _: None))

    @staticmethod
    def _shared(
        fid: str,
        args: Mapping[str, Any],
        *,
        default_timeout_ms: int,
    ) -> dict[str, Any]:
        query = _pair_list(_argument(args, fid, "query"))
        headers = _pair_list(_argument(args, fid, "headers"), header=True)
        redirect = str(_argument(args, fid, "redirect") or "same_origin")
        if redirect not in {"none", "same_origin", "cross_origin"}:
            raise RuntimeFailure("重定向策略无效", error_id="network.redirect_policy_invalid")
        timeout = _duration_seconds(_argument(args, fid, "timeout"), default_timeout_ms)
        response_limit = _bounded_integer(
            _argument(args, fid, "max_response_bytes"),
            DEFAULT_MAX_RESPONSE_BYTES,
            minimum=1,
            maximum=64 * 1024 * 1024,
            error_id="network.response_limit_invalid",
        )
        redirects = _bounded_integer(
            _argument(args, fid, "max_redirects"),
            DEFAULT_MAX_REDIRECTS,
            minimum=0,
            maximum=20,
            error_id="network.redirect_limit_invalid",
        )
        return {
            "url": _append_query(str(_argument(args, fid, "url") or ""), query),
            "headers": headers,
            "redirect": redirect,
            "timeout": timeout,
            "response_limit": response_limit,
            "max_redirects": redirects,
        }

    def _stream_request(
        self,
        *,
        method: str,
        url: str,
        headers: list[tuple[str, str, bool]],
        redirect_policy: str,
        max_redirects: int,
        timeout: float,
        authorization: Mapping[str, Any],
        cancelled: Callable[[], bool],
        request_kwargs: Callable[[str, str], dict[str, Any]],
        consume: Callable[[httpx.Response, float, _ResolvedURL], Any],
        log: Callable[[dict[str, Any]], None],
        operation: str,
    ) -> Any:
        request_id = f"request_{uuid.uuid4().hex}"
        started = time.monotonic()
        deadline = started + timeout
        current_url = url
        current_method = method
        current_headers = list(headers)
        redirects = 0
        resolved: _ResolvedURL | None = None
        status: int | None = None
        received = 0
        error_id = ""
        try:
            while True:
                _cancel(cancelled)
                if time.monotonic() >= deadline:
                    raise RuntimeFailure(
                        "网络操作超过总超时",
                        error_id="network.timeout",
                        transient=True,
                    )
                resolved = _authorize_url(current_url, authorization)
                wire_headers = [(name, value) for name, value, _ in current_headers]
                remaining = max(0.001, deadline - time.monotonic())
                kwargs = request_kwargs(current_method, current_url)
                try:
                    # The transport receives the exact DNS result that passed
                    # policy classification.  It connects to that numeric
                    # address while retaining the original host for Host/SNI
                    # and certificate hostname verification, closing the
                    # check/connect DNS-rebinding race.
                    with httpx.Client(
                        transport=_PinnedHTTPTransport(resolved),
                        follow_redirects=False,
                        trust_env=False,
                        cookies=None,
                    ) as client, client.stream(
                        current_method,
                        current_url,
                        headers=wire_headers,
                        timeout=httpx.Timeout(remaining),
                        **kwargs,
                    ) as response:
                        status = response.status_code
                        location = response.headers.get("location")
                        if status in _REDIRECT_STATUSES and location and redirect_policy != "none":
                            if redirects >= max_redirects:
                                raise RuntimeFailure(
                                    "HTTP 重定向次数超过上限",
                                    error_id="network.redirect_limit",
                                )
                            next_url = urljoin(current_url, location)
                            next_parsed = _authorize_url(next_url, authorization)
                            cross_origin = next_parsed.origin != resolved.origin
                            if cross_origin and redirect_policy != "cross_origin":
                                raise RuntimeFailure(
                                    "跨源重定向未获允许",
                                    error_id="network.redirect_denied",
                                )
                            if cross_origin:
                                current_headers = [
                                    item
                                    for item in current_headers
                                    if item[0].lower() not in _CROSS_ORIGIN_STRIP_HEADERS
                                    and not item[2]
                                ]
                            if status == 303 or (
                                status in {301, 302} and current_method == "POST"
                            ):
                                current_method = "GET"
                            current_url = next_url
                            redirects += 1
                            continue
                        result = consume(response, deadline, resolved)
                        if isinstance(result, Mapping):
                            received = int(
                                _record_field(
                                    result,
                                    str(result.get("record_type") or "http_response"),
                                    "bytes_written",
                                )
                                or _record_field(
                                    result,
                                    str(result.get("record_type") or "http_response"),
                                    "response_bytes",
                                )
                                or len(str(_record_field(
                                    result,
                                    str(result.get("record_type") or "http_response"),
                                    "body",
                                ) or "").encode("utf-8"))
                            )
                        return result
                except RuntimeFailure:
                    raise
                except Exception as exc:
                    raise _map_httpx_error(exc, cancelled) from exc
        except RuntimeFailure as exc:
            error_id = exc.error_id
            raise
        finally:
            elapsed = max(0.0, time.monotonic() - started)
            safe = resolved
            log({
                "event": "network.request_finished",
                "request_id": request_id,
                "operation": operation,
                "method": method,
                "url": _redacted_url(current_url),
                "network_level": _network_level(safe.scopes) if safe else "unknown",
                "elapsed_ms": round(elapsed * 1000),
                "status": status,
                "response_bytes": received,
                "redirects": redirects,
                "error_id": error_id,
            })

    def _execute_network_request(self, fid, args, authorization, cancelled, log):
        shared = self._shared(fid, args, default_timeout_ms=30_000)
        method = str(_argument(args, fid, "method") or "GET").upper()
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}:
            raise RuntimeFailure("HTTP 方法无效", error_id="network.method_invalid")
        body, content_type = _request_body(_argument(args, fid, "body"))
        if method in {"GET", "HEAD"} and body is not None:
            raise RuntimeFailure(
                "GET 或 HEAD 请求不能携带正文",
                error_id="network.body_not_allowed",
            )
        headers = list(shared["headers"])
        if body is not None and content_type and not any(
            name.lower() == "content-type" for name, _, _ in headers
        ):
            headers.append(("Content-Type", content_type, False))

        def kwargs(current_method: str, _: str) -> dict[str, Any]:
            if current_method in {"GET", "HEAD"} and current_method != method:
                return {}
            return {"content": body} if body is not None else {}

        def consume(response: httpx.Response, deadline: float, resolved: _ResolvedURL):
            raw = _read_limited(
                response,
                shared["response_limit"],
                cancelled,
                deadline,
                phase="response",
            )
            text = _ensure_text_response(response, raw)
            return _record_value(
                "http_response",
                status=response.status_code,
                headers=_response_headers(response),
                final_url=str(response.url),
                content_type=_content_type(response),
                body=text,
                response_bytes=len(raw),
            )

        return self._stream_request(
            method=method,
            url=shared["url"],
            headers=headers,
            redirect_policy=shared["redirect"],
            max_redirects=shared["max_redirects"],
            timeout=shared["timeout"],
            authorization=authorization,
            cancelled=cancelled,
            request_kwargs=kwargs,
            consume=consume,
            log=log,
            operation="request",
        )

    def _execute_network_upload_file(self, fid, args, authorization, cancelled, log):
        shared = self._shared(fid, args, default_timeout_ms=60_000)
        fields = _argument(args, fid, "fields")
        if not isinstance(fields, list) or not fields or len(fields) > MAX_PAIR_COUNT:
            raise RuntimeFailure(
                "multipart 字段必须是非空有序列表",
                error_id="network.multipart_invalid",
            )
        maximum = _bounded_integer(
            _argument(args, fid, "max_file_bytes"),
            DEFAULT_MAX_UPLOAD_FILE_BYTES,
            minimum=1,
            maximum=8 * 1024 * 1024 * 1024,
            error_id="network.upload_limit_invalid",
        )
        stack = contextlib.ExitStack()
        multipart: list[tuple[str, tuple[Any, ...]]] = []
        try:
            for field in fields:
                if not isinstance(field, Mapping):
                    raise RuntimeFailure("multipart 字段无效", error_id="network.multipart_invalid")
                kind = str(
                    _record_field(field, "multipart_field", "kind")
                    or field.get("field_type")
                    or ""
                )
                name = str(_record_field(field, "multipart_field", "name") or "")
                if not name or any(character in name for character in "\r\n"):
                    raise RuntimeFailure("multipart 字段名无效", error_id="network.multipart_invalid")
                content_type = str(
                    _record_field(field, "multipart_field", "content_type") or ""
                ) or None
                if kind == "text":
                    value = _record_field(field, "multipart_field", "text")
                    if value is None:
                        value = _record_field(field, "multipart_field", "value")
                    if not isinstance(value, str):
                        raise RuntimeFailure("multipart 文本字段无效", error_id="network.multipart_invalid")
                    multipart.append((name, (None, value, content_type or "text/plain; charset=utf-8")))
                    continue
                if kind != "file":
                    raise RuntimeFailure("multipart 字段类型无效", error_id="network.multipart_invalid")
                path, _, reference = _validate_reference(
                    _record_field(field, "multipart_field", "file")
                    or field.get("reference"),
                    "file_ref",
                    "read",
                )
                try:
                    size = os.path.getsize(path)
                except OSError as exc:
                    raise RuntimeFailure("上传文件不可读取", error_id="file.read_failed") from exc
                if size > maximum:
                    raise RuntimeFailure("上传文件超过允许大小", error_id="network.upload_too_large")
                stream = stack.enter_context(_open_upload_source(path))
                proxy = _CancelledUpload(stream, cancelled, maximum=maximum)
                filename = str(
                    _record_field(field, "multipart_field", "filename")
                    or reference.get("display_name")
                    or os.path.basename(path)
                )
                multipart.append((name, (filename, proxy, content_type or "application/octet-stream")))

            headers = list(shared["headers"])

            def kwargs(method: str, _: str) -> dict[str, Any]:
                if method == "GET":
                    return {}
                for _, item in multipart:
                    stream = item[1] if len(item) > 1 else None
                    if hasattr(stream, "seek"):
                        stream.seek(0)
                return {"files": multipart}

            def consume(response: httpx.Response, deadline: float, resolved: _ResolvedURL):
                raw = _read_limited(
                    response,
                    shared["response_limit"],
                    cancelled,
                    deadline,
                    phase="upload_response",
                )
                text = _ensure_text_response(response, raw)
                return _record_value(
                    "http_response",
                    status=response.status_code,
                    headers=_response_headers(response),
                    final_url=str(response.url),
                    content_type=_content_type(response),
                    body=text,
                    response_bytes=len(raw),
                )

            return self._stream_request(
                method="POST",
                url=shared["url"],
                headers=headers,
                redirect_policy=shared["redirect"],
                max_redirects=shared["max_redirects"],
                timeout=shared["timeout"],
                authorization=authorization,
                cancelled=cancelled,
                request_kwargs=kwargs,
                consume=consume,
                log=log,
                operation="upload",
            )
        finally:
            stack.close()

    def _execute_network_download_file(self, fid, args, authorization, cancelled, log):
        shared = self._shared(fid, args, default_timeout_ms=60_000)
        destination, _, reference = _validate_reference(
            _argument(args, fid, "destination"),
            "file_ref",
            "write",
        )
        maximum = _bounded_integer(
            _argument(args, fid, "max_file_bytes"),
            DEFAULT_MAX_DOWNLOAD_BYTES,
            minimum=1,
            maximum=8 * 1024 * 1024 * 1024,
            error_id="network.download_limit_invalid",
        )
        directory = os.path.dirname(destination)
        try:
            os.makedirs(directory, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".easycode-download-",
                suffix=".tmp",
                dir=directory,
            )
            os.close(descriptor)
        except OSError as exc:
            raise RuntimeFailure(
                "下载位置不支持受控临时文件",
                error_id="file.atomic_commit_unsupported",
            ) from exc

        headers = list(shared["headers"])

        def kwargs(_: str, __: str) -> dict[str, Any]:
            return {}

        def consume(response: httpx.Response, deadline: float, resolved: _ResolvedURL):
            if not 200 <= response.status_code < 300:
                raw = _read_limited(
                    response,
                    shared["response_limit"],
                    cancelled,
                    deadline,
                    phase="download_error_response",
                )
                text = _ensure_text_response(response, raw)
                return _record_value(
                    "http_download_result",
                    status=response.status_code,
                    headers=_response_headers(response),
                    final_url=str(response.url),
                    content_type=_content_type(response),
                    committed=False,
                    file=None,
                    bytes_written=0,
                    error_body=text,
                    response_bytes=len(raw),
                )
            content_length = response.headers.get("content-length")
            expected: int | None = None
            if content_length:
                try:
                    expected = int(content_length)
                except ValueError:
                    expected = None
                if expected is not None and expected > maximum:
                    raise RuntimeFailure(
                        "下载文件超过允许大小",
                        error_id="network.download_too_large",
                    )
            written = 0
            try:
                with open(temporary, "wb") as stream:
                    for chunk in response.iter_bytes(chunk_size=256 * 1024):
                        _cancel(cancelled, phase="download")
                        if time.monotonic() > deadline:
                            raise RuntimeFailure(
                                "下载超过总超时",
                                error_id="network.timeout",
                                transient=True,
                            )
                        written += len(chunk)
                        if written > maximum:
                            raise RuntimeFailure(
                                "下载文件超过允许大小",
                                error_id="network.download_too_large",
                            )
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            except RuntimeFailure:
                raise
            except httpx.StreamError as exc:
                raise RuntimeFailure(
                    "下载响应中断",
                    error_id="network.download_interrupted",
                    transient=True,
                ) from exc
            except OSError as exc:
                raise RuntimeFailure("下载临时文件写入失败", error_id="file.write_failed") from exc
            # See _read_limited: iter_bytes() is decoded, while Content-Length
            # is the encoded wire size when Content-Encoding is present.
            if (
                expected is not None
                and not response.headers.get("content-encoding")
                and written != expected
            ):
                raise RuntimeFailure(
                    "下载响应在完整接收前中断",
                    error_id="network.download_interrupted",
                    transient=True,
                )
            try:
                with _locked_paths(destination):
                    _cancel(cancelled, phase="download_commit")
                    # Validate again immediately before commit so a revoked or
                    # mutated reference cannot be hidden by a long transfer.
                    checked, _, _ = _validate_reference(reference, "file_ref", "write")
                    if os.path.normcase(checked) != os.path.normcase(destination):
                        raise RuntimeFailure(
                            "下载目标引用在传输期间发生变化",
                            error_id="file.reference_changed",
                        )
                    os.replace(temporary, destination)
            except RuntimeFailure:
                raise
            except OSError as exc:
                raise RuntimeFailure(
                    "下载文件原子提交失败",
                    error_id="file.atomic_commit_failed",
                ) from exc
            return _record_value(
                "http_download_result",
                status=response.status_code,
                headers=_response_headers(response),
                final_url=str(response.url),
                content_type=_content_type(response),
                committed=True,
                file=reference,
                bytes_written=written,
                error_body="",
                response_bytes=written,
            )

        try:
            return self._stream_request(
                method="GET",
                url=shared["url"],
                headers=headers,
                redirect_policy=shared["redirect"],
                max_redirects=shared["max_redirects"],
                timeout=shared["timeout"],
                authorization=authorization,
                cancelled=cancelled,
                request_kwargs=kwargs,
                consume=consume,
                log=log,
                operation="download",
            )
        finally:
            with contextlib.suppress(OSError):
                os.remove(temporary)


__all__ = [
    "DEFAULT_MAX_DOWNLOAD_BYTES",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_MAX_UPLOAD_FILE_BYTES",
    "NETWORK_AUTHORIZATION_SCHEMA_VERSION",
    "NetworkRuntimeV6",
    "merge_network_authorizations",
    "normalize_network_authorization",
    "project_network_authorization",
    "static_network_authorization",
]
