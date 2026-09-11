"""Dedicated loopback application for the independently packaged Player."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.errors import detail_for_status, error_message, failure_detail, status_policy
from api.request_context import reset_request_id, set_request_id
from api.routers.vnext_player_capture_router import create_vnext_player_capture_router
from api.routers.vnext_player_lan_router import create_vnext_player_lan_router
from api.routers.vnext_player_runtime_router import create_vnext_player_runtime_router
from api.routers.vnext_player_update_router import create_vnext_player_update_router
from api.routers.vnext_schedule_hub_router import create_vnext_schedule_hub_router
from api.routers.vnext_schedule_router import create_vnext_schedule_router


logger = logging.getLogger(__name__)
_LOCAL_HOSTS = {'127.0.0.1', '::1', 'localhost', 'testclient'}
_SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
}


def _console_parent_origin() -> str:
    path = str(os.environ.get('EASYCODE_PLAYER_CONSOLE_ORIGIN_FILE') or '').strip()
    raw = ''
    if path:
        try:
            raw = Path(path).read_text(encoding='utf-8-sig').strip()
        except OSError:
            raw = ''
    if not raw:
        raw = str(os.environ.get('EASYCODE_PLAYER_CONSOLE_ORIGIN') or '').strip()
    try:
        parsed = urlparse(raw)
        port = int(parsed.port or 0)
    except (TypeError, ValueError):
        return ''
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or not 1 <= port <= 65535:
        return ''
    host = '127.0.0.1' if parsed.hostname in {'127.0.0.1', 'localhost'} else '[::1]'
    return f'http://{host}:{port}'


def _player_security_headers() -> dict[str, str]:
    parent = _console_parent_origin()
    if not parent:
        return dict(_SECURITY_HEADERS)
    return {
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'no-referrer',
        'Content-Security-Policy': (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; "
            f'frame-ancestors {parent}'
        ),
    }


_CONSOLE_SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': (
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "frame-src http://127.0.0.1:* http://localhost:*; frame-ancestors 'none'"
    ),
}


def _default_web_directory() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent / 'release' / 'web'
    return Path(__file__).resolve().parents[1] / 'release' / 'player-web'


def _player_product_branding() -> tuple[str, str]:
    """Read display-only branding generated beside the verified bundle."""

    configured = str(os.environ.get('EASYCODE_PLAYER_PRODUCT_METADATA') or '').strip()
    metadata_path = Path(configured).expanduser() if configured else _default_web_directory().parent / 'product.json'
    try:
        metadata_path = metadata_path.resolve()
        value = json.loads(metadata_path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 'EasyCode 自动化运行助手', ''
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        return 'EasyCode 自动化运行助手', ''
    application_name = str(value.get('application_name') or '').strip()[:120]
    icon_path = ''
    icon_value = str(value.get('icon') or '').strip().replace('\\', '/')
    if icon_value:
        parts = [part for part in icon_value.split('/') if part]
        if parts and not icon_value.startswith('/') and all(part not in {'.', '..'} for part in parts):
            candidate = metadata_path.parent.joinpath(*parts).resolve()
            if (metadata_path.parent == candidate.parent or metadata_path.parent in candidate.parents) and candidate.is_file():
                icon_path = os.fspath(candidate)
    return application_name or 'EasyCode 自动化运行助手', icon_path


@asynccontextmanager
async def _player_lifespan(_app: FastAPI):
    yield
    from core.services import capture_mode
    from core.services.native_capture_overlay import native_capture_overlay
    from core.services.player_capture_session import player_capture_session_service
    from core.vnext.player_bundle import vnext_player_bundle_manager
    from core.vnext.runtime import vnext_runtime
    from core.vnext.schedule_hub_v6 import shutdown_player_hub_v6

    with suppress(Exception):
        capture_mode.stop_mode()
    with suppress(Exception):
        player_capture_session_service.shutdown()
    with suppress(Exception):
        native_capture_overlay.shutdown()
    with suppress(Exception):
        shutdown_player_hub_v6()
    with suppress(Exception):
        vnext_player_bundle_manager.shutdown()
    with suppress(Exception):
        vnext_runtime.shutdown()


def create_player_app(web_directory: str | os.PathLike[str] | None = None) -> FastAPI:
    """Create the complete and intentionally small standalone Player API."""

    app = FastAPI(
        title='EasyCode Player API',
        version='6',
        docs_url=None,
        redoc_url=None,
        lifespan=_player_lifespan,
    )

    @app.middleware('http')
    async def loopback_boundary(request: Request, call_next):
        client_host = request.client.host if request.client else ''
        if client_host not in _LOCAL_HOSTS:
            return JSONResponse(
                status_code=403,
                content={'detail': detail_for_status(403, 'Player HTTP 服务只接受本机连接')},
            )
        response: Response = await call_next(request)
        for header, value in _player_security_headers().items():
            response.headers[header] = value
        return response

    @app.middleware('http')
    async def request_identity(request: Request, call_next):
        started_at = time.perf_counter()
        supplied = str(request.headers.get('X-Request-ID') or '').strip()
        request_id = supplied if supplied and len(supplied) <= 128 and all(
            char.isalnum() or char in '-_.' for char in supplied
        ) else f'req_{uuid.uuid4().hex}'
        request.state.request_id = request_id
        token = set_request_id(request_id)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers['X-Request-ID'] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            # Polling runs every 250 ms. Successful reads add no support value
            # and previously inflated player.log indefinitely, so retain only
            # failures and state-changing requests at the normal log level.
            request_log = logger.warning if status_code >= 400 else logger.info
            if status_code >= 400 or request.method not in {'GET', 'HEAD'}:
                request_log(
                    'player.api.request method=%s path=%s status=%s duration_ms=%s request_id=%s',
                    request.method,
                    request.url.path,
                    status_code,
                    duration_ms,
                    request_id,
                )
            else:
                logger.debug(
                    'player.api.request method=%s path=%s status=%s duration_ms=%s request_id=%s',
                    request.method,
                    request.url.path,
                    status_code,
                    duration_ms,
                    request_id,
                )
            reset_request_id(token)

    def normalize_error(request: Request, status_code: int, detail) -> dict:
        if isinstance(detail, dict) and detail.get('code') and detail.get('message'):
            normalized = dict(detail)
            normalized['request_id'] = str(
                normalized.get('request_id') or getattr(request.state, 'request_id', '')
            )
            normalized.setdefault('fields', [])
            normalized.setdefault('diagnostics', [])
            normalized.setdefault('recovery', {'retryable': False, 'action': 'none', 'message': ''})
            return normalized
        code, retryable, action = status_policy(status_code)
        return failure_detail(
            code,
            error_message(detail),
            request_id=str(getattr(request.state, 'request_id', '')),
            retryable=retryable,
            action=action,
        )

    @app.exception_handler(HTTPException)
    async def player_http_exception(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={'detail': normalize_error(request, exc.status_code, exc.detail)},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def player_validation_exception(request: Request, exc: RequestValidationError):
        fields = [{
            'path': '.'.join(str(part) for part in item.get('loc', ()) if part != 'body'),
            'message': str(item.get('msg') or '字段无效'),
            'type': str(item.get('type') or ''),
        } for item in exc.errors()]
        detail = failure_detail(
            'validation_error',
            '请求参数校验失败',
            request_id=str(getattr(request.state, 'request_id', '')),
            action='fix_request',
            fields=fields,
        )
        return JSONResponse(status_code=422, content={'detail': detail})

    @app.exception_handler(Exception)
    async def player_unhandled_exception(request: Request, exc: Exception):
        logger.error('player.api.unhandled_error', exc_info=exc)
        detail = failure_detail(
            'internal_error',
            'Player 内部错误',
            request_id=str(getattr(request.state, 'request_id', '')),
            retryable=True,
            action='retry',
        )
        return JSONResponse(status_code=500, content={'detail': detail})

    app.include_router(create_vnext_player_runtime_router())
    app.include_router(create_vnext_player_capture_router())
    app.include_router(create_vnext_player_update_router())
    app.include_router(create_vnext_schedule_router())
    app.include_router(create_vnext_schedule_hub_router())
    app.include_router(create_vnext_player_lan_router())

    web_root = Path(web_directory).resolve() if web_directory is not None else _default_web_directory()
    if web_root.is_dir():
        app.mount('/', StaticFiles(directory=os.fspath(web_root), html=True), name='player_static')
    return app


@asynccontextmanager
async def _player_console_lifespan(_app: FastAPI):
    yield
    from core.vnext.player_console_v1 import shutdown_player_console_v1
    from core.vnext.schedule_hub_v6 import shutdown_player_hub_v6

    with suppress(Exception):
        shutdown_player_console_v1()
    with suppress(Exception):
        shutdown_player_hub_v6()


def create_player_console_app(web_directory: str | os.PathLike[str] | None = None) -> FastAPI:
    """Create the native console host; product execution remains in workers."""

    from api.routers.vnext_player_console_router import create_vnext_player_console_router

    app = FastAPI(
        title='EasyCode Player Console API',
        version='1',
        docs_url=None,
        redoc_url=None,
        lifespan=_player_console_lifespan,
    )

    @app.middleware('http')
    async def console_loopback_boundary(request: Request, call_next):
        client_host = request.client.host if request.client else ''
        if client_host not in _LOCAL_HOSTS:
            return JSONResponse(
                status_code=403,
                content={'detail': detail_for_status(403, 'Player 控制台只接受本机连接')},
            )
        response: Response = await call_next(request)
        for header, value in _CONSOLE_SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    @app.exception_handler(HTTPException)
    async def console_http_exception(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else failure_detail(
            status_policy(exc.status_code)[0],
            error_message(exc.detail),
            retryable=status_policy(exc.status_code)[1],
            action=status_policy(exc.status_code)[2],
        )
        return JSONResponse(status_code=exc.status_code, content={'detail': detail}, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def console_validation_exception(_request: Request, exc: RequestValidationError):
        fields = [{
            'path': '.'.join(str(part) for part in item.get('loc', ()) if part != 'body'),
            'message': str(item.get('msg') or '字段无效'),
            'type': str(item.get('type') or ''),
        } for item in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={'detail': failure_detail('validation_error', '请求参数校验失败', action='fix_request', fields=fields)},
        )

    @app.exception_handler(Exception)
    async def console_unhandled_exception(_request: Request, exc: Exception):
        logger.error('player.console.api.unhandled_error', exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={'detail': failure_detail('internal_error', 'Player 控制台内部错误', retryable=True, action='retry')},
        )

    app.include_router(create_vnext_player_console_router())
    web_root = Path(web_directory).resolve() if web_directory is not None else _default_web_directory()
    if web_root.is_dir():
        app.mount('/', StaticFiles(directory=os.fspath(web_root), html=True), name='player_console_static')
    return app


class PlayerWindowApi:
    def __init__(self) -> None:
        self.window = None
        self.maximized = False

    def attach(self, window) -> None:
        self.window = window

    def minimize(self) -> dict:
        if self.window:
            self.window.minimize()
        return {'success': bool(self.window)}

    def toggle_maximize(self) -> dict:
        if not self.window:
            return {'success': False}
        if self.maximized:
            self.window.restore()
        else:
            self.window.maximize()
        self.maximized = not self.maximized
        return {'success': True, 'maximized': self.maximized}

    def close(self) -> dict:
        if self.window:
            self.window.destroy()
        return {'success': bool(self.window)}


def start_webview(port: int = 8000) -> None:
    """Launch the native Player shell, with pywebview as an optional fallback."""

    from core.services.native_desktop_shell import run_native_desktop_shell

    url = f'http://127.0.0.1:{int(port)}/player.html'
    application_name, icon_path = _player_product_branding()
    instance_name = str(os.environ.get('EASYCODE_PLAYER_INSTANCE_NAME') or '').strip()
    window_title = (
        f'{application_name} · {instance_name}'
        if instance_name else application_name
    )
    if run_native_desktop_shell(url, title=window_title, icon_path=icon_path):
        return
    try:
        import webview
    except ImportError:
        logger.error('Player 原生宿主和 pywebview 回退均不可用')
        return
    window_api = PlayerWindowApi()
    window = webview.create_window(
        title=window_title,
        url=url,
        js_api=window_api,
        width=960,
        height=720,
        resizable=True,
        frameless=True,
        easy_drag=True,
        min_size=(800, 600),
    )
    window_api.attach(window)
    webview.start()


def start_player_console_webview(port: int = 8000, *, selected_product: str = '') -> None:
    """Open the single native shell used to supervise isolated instances."""

    from urllib.parse import quote

    from core.services.native_desktop_shell import run_native_desktop_shell

    suffix = f'?product_id={quote(selected_product)}' if selected_product else ''
    url = f'http://127.0.0.1:{int(port)}/console.html{suffix}'
    if run_native_desktop_shell(
        url,
        title='EasyCode Player 控制台',
        width=1240,
        height=780,
    ):
        return
    try:
        import webview
    except ImportError:
        logger.error('Player 控制台原生宿主和 pywebview 回退均不可用')
        return
    window_api = PlayerWindowApi()
    window = webview.create_window(
        title='EasyCode Player 控制台',
        url=url,
        js_api=window_api,
        width=1240,
        height=780,
        resizable=True,
        frameless=True,
        easy_drag=True,
        min_size=(960, 640),
    )
    window_api.attach(window)
    webview.start()


__all__ = [
    'create_player_app', 'create_player_console_app',
    'start_webview', 'start_player_console_webview',
]
