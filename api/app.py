import os
import sys

# 设置 sys.path — api/ 是子目录，需要将项目根目录加入路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ['FLAGS_use_mkldnn'] = '0'  # noqa: SIM112 - PaddlePaddle 要求小写
os.environ['FLAGS_enable_pir_api'] = '0'  # noqa: SIM112 - PaddlePaddle 要求小写

import logging  # noqa: E402
import threading  # noqa: E402

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import Response  # noqa: E402

# 安全配置（统一从环境变量读取，避免硬编码密钥/CORS 来源）
from core.config import SecurityConfig  # noqa: E402

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
    from core.services.debug_service import DebugService
except ImportError:
    DebugService = None
    logger.warning("DebugService 不可用")

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


def create_app():
    """创建 FastAPI 应用并注册所有路由"""
    app = FastAPI(title='节点自动化后端', version='2.4')

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
    async def add_security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
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
        allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
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
    from api.routers.execution_router import create_execution_router
    from api.routers.system_router import create_system_router
    from api.routers.vision_router import create_vision_router
    from api.routers.workspace_router import create_workspace_router

    app.include_router(create_system_router(ALL_PARAMS))
    app.include_router(create_blueprint_router(BlueprintService, load_project))
    app.include_router(create_execution_router(ExecutionService, DebugService))
    app.include_router(create_workspace_router(WorkspaceService))
    app.include_router(create_vision_router(VisionService))
    app.include_router(create_build_router(ExportService, CompilerService, PlayerService))

    # ====== 静态托管 ======
    web_dir = os.path.join(os.getcwd(), 'release', 'web')
    if os.path.exists(web_dir):
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='player_static')

    return app


app = create_app()


def start_webview():
    """启动 PyWebView 原生窗口"""
    if webview is None:
        logger.error('pywebview 未安装，无法启动原生窗口模式')
        return
    url = 'http://127.0.0.1:8000/#/player'
    webview.create_window(
        title='Easycode 自动化运行助手',
        url=url,
        width=960,
        height=720,
        resizable=True,
        frameless=True,
        easy_drag=True,
        min_size=(800, 600),
    )
    webview.start()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Easycode 后端引擎')
    parser.add_argument(
        '--mode', type=str, default='dev', choices=['dev', 'prod'], help='运行模式: dev(仅后端), prod(带原生客户端窗口)'
    )
    args = parser.parse_args()

    if args.mode == 'prod':

        def run_server():
            uvicorn.run(app, host='127.0.0.1', port=8000, log_level='error')

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview()
    else:
        print('FastAPI 后端引擎运行中 (开发模式)...')
        uvicorn.run(app, host='127.0.0.1', port=8000, reload=False)
