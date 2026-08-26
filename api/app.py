import os
import sys

# 设置 sys.path — api/ 是子目录，需要将项目根目录加入路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.services.dpi_service import enable_per_monitor_v2  # noqa: E402

enable_per_monitor_v2()

os.environ['FLAGS_use_mkldnn'] = '0'  # noqa: SIM112 - PaddlePaddle 要求小写
os.environ['FLAGS_enable_pir_api'] = '0'  # noqa: SIM112 - PaddlePaddle 要求小写

import logging  # noqa: E402
import asyncio  # noqa: E402
import secrets  # noqa: E402
import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402

# 安全配置（统一从环境变量读取，避免硬编码密钥/CORS 来源）
from core.config import SecurityConfig  # noqa: E402
from core.services.project_workspace_service import project_workspace_manager  # noqa: E402
from api.workspace_context import mutates_project_files, project_mutation_documents  # noqa: E402

# 速率限制（slowapi 可选，缺失时降级为无限制）
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
    from slowapi.errors import RateLimitExceeded  # noqa: E402
    from slowapi.util import get_remote_address  # noqa: E402

    _limiter = Limiter(key_func=get_remote_address, default_limits=[SecurityConfig.get_rate_limit()])
    _HAS_SLOWAPI = True
except ImportError:  # pragma: no cover - slowapi 未安装时降级
    _limiter = None
    _HAS_SLOWAPI = False
    logging.getLogger(__name__).warning(
        'slowapi 未安装，速率限制功能已禁用。生产环境建议安装: pip install slowapi'
    )

logger = logging.getLogger(__name__)


def _runtime_root() -> Path:
    """Return the install/source root independent of the process working directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(current_dir).resolve()

# ====== 条件导入：核心模块（必须存在） ======
from core.project_loader import load_project  # noqa: E402
from core.services.blueprint_service import BlueprintService  # noqa: E402

# ====== 条件导入：可选模块（缺失时降级，不阻止启动） ======

try:
    import core.node_executors  # noqa: F401 - 副作用导入，注册执行器
except ImportError as e:
    logger.warning(f'core.node_executors 导入失败，节点执行器可能不可用: {e}')

try:
    from core.params import ALL_PARAMS
except ImportError:
    ALL_PARAMS = {}
    logger.warning('core.params 导入失败，使用空参数表')

try:
    from core.services.workspace_service import WorkspaceService
except ImportError:
    WorkspaceService = None
    logger.warning('WorkspaceService 不可用')

try:
    from core.services.frame_recording_service import frame_recording_service
except ImportError:
    frame_recording_service = None
    logger.warning('FrameRecordingService 不可用')

try:
    from core.services.vision_service import VisionService
except ImportError:
    VisionService = None
    logger.warning('VisionService 不可用')

try:
    from core.services.execution_service import ExecutionService
except ImportError:
    ExecutionService = None
    logger.warning('ExecutionService 不可用')

try:
    from core.services.debug_service import DebugService
except ImportError:
    DebugService = None
    logger.warning('DebugService 不可用')

try:
    from core.services.export_service import ExportService
except ImportError:
    ExportService = None
    logger.warning('ExportService 不可用')

try:
    from core.services.player_service import PlayerService
except ImportError:
    PlayerService = None
    logger.warning('PlayerService 不可用')

try:
    from core.builder.compiler_service import CompilerService
except ImportError:
    CompilerService = None
    logger.warning('CompilerService 不可用')

try:
    import webview
except ImportError:
    webview = None
    logger.info('pywebview 不可用（开发模式不需要）')


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    yield
    if frame_recording_service is not None:
        # 正常退出时补写 final session.json 并释放全局 Esc；图片从不清理。
        frame_recording_service.stop('process_shutdown', timeout=3.0)

    # CaptureOverlay 是 IDE 生命周期内常驻的原生子进程；后端退出时明确关闭。
    from core.services.native_capture_overlay import native_capture_overlay

    native_capture_overlay.shutdown()
    project_workspace_manager.shutdown()
    from core.services.platform_runtime_service import platform_runtime_service

    platform_runtime_service.shutdown()


def create_app():
    """创建 FastAPI 应用并注册所有路由"""
    app = FastAPI(title='节点自动化后端', version='2.4', lifespan=_lifespan)

    # ====== 速率限制中间件（slowapi 可选） ======
    if _HAS_SLOWAPI:
        app.state.limiter = _limiter

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
            logger.warning(f'速率限制触发 [{request.client.host if request.client else "?"}] {request.url.path}')
            return _rate_limit_exceeded_handler(request, exc)

    # ====== 安全响应头中间件 ======
    security_headers = SecurityConfig.get_security_headers()

    @app.middleware('http')
    async def protect_remote_lan_requests(request: Request, call_next):
        """Do not expose the rest of the IDE API when coordinator mode binds to LAN."""
        client_host = request.client.host if request.client else ''
        local_hosts = {'127.0.0.1', '::1', 'localhost', 'testclient'}
        expected = str(os.environ.get('EASYCODE_COORDINATOR_TOKEN') or '')
        if client_host not in local_hosts:
            supplied = str(request.headers.get('X-EasyCode-Token') or '')
            if not expected or not supplied or not secrets.compare_digest(supplied, expected):
                return JSONResponse(status_code=401, content={'detail': '远程请求缺少有效的协调服务令牌'})
        return await call_next(request)

    @app.middleware('http')
    async def add_security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
        if (
            response.status_code < 400
            and mutates_project_files(request.method, request.url.path)
            and request.headers.get('x-workspace-id')
        ):
            try:
                await asyncio.to_thread(
                    project_workspace_manager.acknowledge,
                    request.headers['x-workspace-id'],
                    int(request.headers.get('x-workspace-generation') or -1),
                    project_mutation_documents(request.method, request.url.path),
                )
            except Exception:
                # A switch may complete while a response is returning; the old
                # request is already done and must not change the new baseline.
                pass
        for header, value in security_headers.items():
            response.headers[header] = value
        return response

    # ====== CORS：来源统一委托给 SecurityConfig 读取 ======
    allow_origins = SecurityConfig.get_cors_origins()
    logger.info(f'CORS 允许来源: {allow_origins} (env={SecurityConfig.APP_ENV})')

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        # 仅允许实际使用到的 HTTP 方法，避免过度放开
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
        allow_headers=[
            'Content-Type',
            'Authorization',
            'X-Requested-With',
            'X-Workspace-Id',
            'X-Workspace-Generation',
            'X-EasyCode-Token',
        ],
    )

    # ====== 全局异常处理 ======
    from fastapi.exceptions import RequestValidationError

    from core.error_codes import ErrorCode
    from core.response import error_response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f'参数校验失败 [{request.url.path}]: {exc.errors()}')
        return error_response(ErrorCode.VALIDATION_ERROR, '请求参数校验失败', status_code=422)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f'未处理异常 [{request.url.path}]: {exc}', exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, '内部服务器错误', status_code=500)

    # ====== 注册路由 ======
    from api.routers.blueprint_router import create_blueprint_router
    from api.routers.build_router import create_build_router
    from api.routers.capture_router import create_capture_router
    from api.routers.capability_router import create_capability_router
    from api.routers.execution_router import create_execution_router
    from api.routers.project_workspace_router import create_project_workspace_router
    from api.routers.platform_router import create_platform_router
    from api.routers.system_router import create_system_router
    from api.routers.ui_control_router import create_ui_control_router
    from api.routers.vision_router import create_vision_router
    from api.routers.workspace_router import create_workspace_router

    app.include_router(create_system_router(ALL_PARAMS))
    app.include_router(create_project_workspace_router(project_workspace_manager))
    app.include_router(create_platform_router())
    app.include_router(create_blueprint_router(BlueprintService, load_project))
    app.include_router(create_execution_router(ExecutionService, DebugService))
    app.include_router(create_workspace_router(WorkspaceService, frame_recording_service))
    app.include_router(create_vision_router(VisionService))
    app.include_router(create_ui_control_router())
    app.include_router(create_capture_router())
    app.include_router(create_capability_router())
    app.include_router(create_build_router(ExportService, CompilerService, PlayerService))

    def workspace_blockers():
        blockers = []
        if ExecutionService is not None and ExecutionService.has_active_execution():
            blockers.append('任务正在运行或暂停调试')
        try:
            from core.services import capture_mode
            from core.services.capture_session_service import capture_session_service

            if capture_mode.get_state().get('active'):
                blockers.append('控件捕获模式正在运行')
            if capture_session_service.is_capture_active():
                blockers.append('截图捕获模式正在运行')
        except Exception:
            pass
        if frame_recording_service is not None and frame_recording_service.get_state().get('active'):
            blockers.append('逐帧录制正在运行')
        return blockers

    project_workspace_manager.set_activity_probe(workspace_blockers)

    # ====== 静态托管 ======
    web_dir = _runtime_root() / 'release' / 'web'
    if web_dir.exists():
        app.mount('/', StaticFiles(directory=str(web_dir), html=True), name='player_static')

    return app


app = create_app()


class PlayerWindowApi:
    """暴露给 Player 前端的最小原生窗口控制桥。"""

    def __init__(self):
        self.window = None
        self._maximized = False

    def attach(self, window):
        self.window = window

    def minimize(self):
        if self.window:
            self.window.minimize()
        return {'success': bool(self.window)}

    def toggle_maximize(self):
        if not self.window:
            return {'success': False}
        if self._maximized:
            self.window.restore()
        else:
            self.window.maximize()
        self._maximized = not self._maximized
        return {'success': True, 'maximized': self._maximized}

    def close(self):
        if self.window:
            self.window.destroy()
        return {'success': bool(self.window)}


def start_webview(port: int = 8000):
    """启动原生 WebView2 Player；旧 PyWebView 只作为显式兼容回退。"""
    from core.services.native_desktop_shell import run_native_desktop_shell

    url = f'http://127.0.0.1:{int(port)}/player.html'
    if run_native_desktop_shell(url):
        return

    logger.warning('原生桌面宿主不可用，正在使用 PyWebView 兼容回退')
    if webview is None:
        logger.error('PyWebView 兼容回退也不可用，Player 无法显示')
        return
    window_api = PlayerWindowApi()
    window = webview.create_window(
        title='Easycode 自动化运行助手',
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


def main(argv: list[str] | None = None) -> None:
    """Canonical CLI/packaged entry point for the EasyCode backend and shell."""
    import argparse

    parser = argparse.ArgumentParser(description='Easycode 后端引擎')
    parser.add_argument(
        '--mode', type=str, default='dev', choices=['dev', 'prod'], help='运行模式: dev(仅后端), prod(带原生客户端窗口)'
    )
    parser.add_argument('--host', default='127.0.0.1', help='监听地址；局域网协调服务可使用 0.0.0.0')
    parser.add_argument('--port', type=int, default=8000, help='监听端口')
    args = parser.parse_args(argv)

    if args.host not in {'127.0.0.1', 'localhost', '::1'} and not os.environ.get('EASYCODE_COORDINATOR_TOKEN'):
        parser.error('监听非本机地址时必须设置 EASYCODE_COORDINATOR_TOKEN')

    if args.mode == 'prod':

        def run_server():
            uvicorn.run(app, host=args.host, port=args.port, log_level='error')

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview(args.port)
    else:
        print('FastAPI 后端引擎运行中 (开发模式)...')
        uvicorn.run(app, host=args.host, port=args.port, reload=False)


if __name__ == '__main__':
    main()
