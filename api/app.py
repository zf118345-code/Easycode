import os
import sys

# 设置 sys.path — api/ 是子目录，需要将项目根目录加入路径
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import threading
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# ====== 条件导入：核心模块（必须存在） ======
from core.schemas import (
    RunRequestSchema, SaveTaskRequestSchema, TaskOrderRequestSchema,
    SaveBlueprintRequestSchema, CropScreenshotRequestSchema,
    ContextSaveRequestSchema, OcrTestRequestSchema, ImageTestRequestSchema
)
from core.services.blueprint_service import BlueprintService
from core.project_loader import load_project

# ====== 条件导入：可选模块（缺失时降级，不阻止启动） ======

try:
    import core.node_executors
except ImportError as e:
    logger.warning(f"core.node_executors 导入失败，节点执行器可能不可用: {e}")

try:
    from core.params import ALL_PARAMS
except ImportError:
    ALL_PARAMS = {}
    logger.warning("core.params 导入失败，使用空参数表")

try:
    from core.services.workspace_service import WorkspaceService
except ImportError:
    WorkspaceService = None
    logger.warning("WorkspaceService 不可用")

try:
    from core.services.vision_service import VisionService
except ImportError:
    VisionService = None
    logger.warning("VisionService 不可用")

try:
    from core.services.execution_service import ExecutionService
except ImportError:
    ExecutionService = None
    logger.warning("ExecutionService 不可用")

try:
    from core.services.debug_service import DebugService
except ImportError:
    DebugService = None
    logger.warning("DebugService 不可用")

try:
    from core.services.export_service import ExportService
except ImportError:
    ExportService = None
    logger.warning("ExportService 不可用")

try:
    from core.services.player_service import PlayerService
except ImportError:
    PlayerService = None
    logger.warning("PlayerService 不可用")

try:
    from core.builder.compiler_service import CompilerService
except ImportError:
    CompilerService = None
    logger.warning("CompilerService 不可用")

try:
    import webview
except ImportError:
    webview = None
    logger.info("pywebview 不可用（开发模式不需要）")


def create_app():
    """创建 FastAPI 应用并注册所有路由"""
    app = FastAPI(title="节点自动化后端", version="2.4")

    # CORS：根据 APP_ENV 环境变量控制
    app_env = os.environ.get("APP_ENV", "dev")
    if app_env == "prod":
        allow_origins = ["http://127.0.0.1:8000", "http://localhost:8000"]
    else:
        allow_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ====== 注册路由 ======
    from api.routers.system_router import create_system_router
    from api.routers.blueprint_router import create_blueprint_router
    from api.routers.execution_router import create_execution_router
    from api.routers.workspace_router import create_workspace_router
    from api.routers.vision_router import create_vision_router
    from api.routers.build_router import create_build_router

    app.include_router(create_system_router(ALL_PARAMS))
    app.include_router(create_blueprint_router(BlueprintService, load_project))
    app.include_router(create_execution_router(ExecutionService, DebugService))
    app.include_router(create_workspace_router(WorkspaceService))
    app.include_router(create_vision_router(VisionService))
    app.include_router(create_build_router(ExportService, CompilerService, PlayerService))

    # ====== 静态托管 ======
    web_dir = os.path.join(os.getcwd(), "release", "web")
    if os.path.exists(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="player_static")

    return app


app = create_app()


def start_webview():
    """启动 PyWebView 原生窗口"""
    if webview is None:
        logger.error("pywebview 未安装，无法启动原生窗口模式")
        return
    url = "http://127.0.0.1:8000/#/player"
    webview.create_window(
        title="Easycode 自动化运行助手",
        url=url,
        width=960,
        height=720,
        resizable=True,
        frameless=True,
        easy_drag=True,
        min_size=(800, 600)
    )
    webview.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Easycode 后端引擎")
    parser.add_argument("--mode", type=str, default="dev", choices=["dev", "prod"],
                        help="运行模式: dev(仅后端), prod(带原生客户端窗口)")
    args = parser.parse_args()

    if args.mode == "prod":
        def run_server():
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview()
    else:
        print("FastAPI 后端引擎运行中 (开发模式)...")
        uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
