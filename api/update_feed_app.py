"""Deployable read-only host for an EasyCode static signed update tree.

TLS is expected at the reverse proxy.  This service has no author account,
signing key, telemetry, installation tracker, or device inventory; the local
publisher writes the static tree and this process only serves exact bytes.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from core.vnext.update_protocol_v6 import UPDATE_DOMAINS

_RANGE = re.compile(r"^bytes=(\d+)-(\d*)$")


def _root_from_environment() -> Path:
    raw = str(os.environ.get("EASYCODE_UPDATE_FEED_ROOT") or "").strip()
    if not raw:
        raise RuntimeError("EASYCODE_UPDATE_FEED_ROOT is required")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"update feed root does not exist: {root}")
    return root


def _resolve(root: Path, product_id: str, domain: str, relative: str) -> Path:
    if domain not in UPDATE_DOMAINS or not product_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-" for char in product_id):
        raise HTTPException(status_code=404, detail="feed object not found")
    normalized = str(relative or "").replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not normalized or pure.is_absolute() or ".." in pure.parts or ":" in pure.parts[0]:
        raise HTTPException(status_code=404, detail="feed object not found")
    candidate = (root / product_id / domain / Path(*pure.parts)).resolve()
    domain_root = (root / product_id / domain).resolve()
    try:
        candidate.relative_to(domain_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="feed object not found") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="feed object not found")
    return candidate


def _etag(path: Path) -> str:
    stat = path.stat()
    if stat.st_size <= 8 * 1024 * 1024:
        return '"sha256-' + hashlib.sha256(path.read_bytes()).hexdigest() + '"'
    return f'"immutable-{stat.st_size:x}-{stat.st_mtime_ns:x}"'


def _chunks(path: Path, start: int, length: int) -> Iterator[bytes]:
    remaining = length
    with path.open("rb") as stream:
        stream.seek(start)
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def create_update_feed_app(root: str | Path) -> FastAPI:
    feed_root = Path(root).expanduser().resolve()
    app = FastAPI(title="EasyCode Static Update Feed", version="1")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if str(os.environ.get("EASYCODE_UPDATE_REQUIRE_HTTPS") or "1").lower() not in {"0", "false", "no"}:
            forwarded = str(request.headers.get("x-forwarded-proto") or request.url.scheme).lower()
            if forwarded != "https" and request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
                return Response(status_code=400, content="HTTPS required")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/healthz")
    async def health() -> dict[str, object]:
        return {"ok": feed_root.is_dir(), "protocol": "easycode-update-feed", "version": 1}

    @app.api_route("/feed/{product_id}/{domain}/{relative:path}", methods=["GET", "HEAD"])
    async def feed_object(product_id: str, domain: str, relative: str, request: Request):
        path = _resolve(feed_root, product_id, domain, relative)
        size = path.stat().st_size
        etag = _etag(path)
        immutable = relative.startswith("artifacts/") or bool(re.match(r"^metadata/\d+\.", relative))
        headers = {
            "ETag": etag,
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=31536000, immutable" if immutable else "public, max-age=0, must-revalidate",
            "Content-Security-Policy": "default-src 'none'",
        }
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        start, end, status = 0, size - 1, 200
        requested_range = str(request.headers.get("range") or "")
        if requested_range:
            match = _RANGE.fullmatch(requested_range)
            if not match:
                return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1
            if start >= size or end < start or end >= size:
                return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        length = max(0, end - start + 1)
        headers["Content-Length"] = str(length)
        media = "application/json" if path.suffix == ".json" else "application/octet-stream"
        if request.method == "HEAD":
            return Response(status_code=status, headers=headers, media_type=media)
        return StreamingResponse(_chunks(path, start, length), status_code=status, headers=headers, media_type=media)

    return app


def _create_from_environment() -> FastAPI:
    try:
        return create_update_feed_app(_root_from_environment())
    except RuntimeError:
        # Importing the main IDE app must not require or invent a feed root.
        unavailable = FastAPI(title="EasyCode Static Update Feed (unconfigured)")

        @unavailable.get("/healthz")
        async def health() -> Response:
            return Response(status_code=503, content="EASYCODE_UPDATE_FEED_ROOT is not configured")

        return unavailable


app = _create_from_environment()


__all__ = ["app", "create_update_feed_app"]
