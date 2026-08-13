
# api.py

# 修复：蓝图 save 路由直接用 dict 落盘（不经 Pydantic 校验，不丢弃字段）

# 修复：蓝图 load 路由加 try/except

# 新增：停止执行路由 /api/execution/{id}/stop

# 修复：Pydantic v2 兼容（min_items -> min_length）

# 修复：条件导入缺失服务模块，避免单一缺失导致整个服务端 500

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import json
import threading
import logging
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
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

# 节点执行器注册
try:
    import core.node_executors
except ImportError as e:
    logger.warning(f"core.node_executors 导入失败，节点执行器可能不可用: {e}")

# 参数定义
try:
    from core.params import ALL_PARAMS
except ImportError:
    ALL_PARAMS = {}
    logger.warning("core.params 导入失败，使用空参数表")

# 工作区服务
try:
    from core.services.workspace_service import WorkspaceService
except ImportError:
    WorkspaceService = None
    logger.warning("WorkspaceService 不可用")

# 视觉服务
try:
    from core.services.vision_service import VisionService
except ImportError:
    VisionService = None
    logger.warning("VisionService 不可用")

# 执行服务
try:
    from core.services.execution_service import ExecutionService
except ImportError:
    ExecutionService = None
    logger.warning("ExecutionService 不可用")

# 导出服务
try:
    from core.services.export_service import ExportService
except ImportError:
    ExportService = None
    logger.warning("ExportService 不可用")

# Player 服务
try:
    from core.services.player_service import PlayerService
except ImportError:
    PlayerService = None
    logger.warning("PlayerService 不可用")

# 编译服务
try:
    from core.builder.compiler_service import CompilerService
except ImportError:
    CompilerService = None
    logger.warning("CompilerService 不可用")

# webview（仅生产模式需要）
try:
    import webview
except ImportError:
    webview = None
    logger.info("pywebview 不可用（开发模式不需要）")

def _service_unavailable(name: str):
    """统一的缺失服务错误响应"""
    raise HTTPException(status_code=503, detail=f"服务不可用: {name} 模块未加载")

app = FastAPI(title="节点自动化后端", version="2.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================

#  基础配置路由

# ==============================================================================

@app.get("/api/params")
async def get_params():
    return ALL_PARAMS

@app.get("/api/projects/verify")
async def verify_project(project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
    return {
        "exists": True,
        "has_project_json": os.path.exists(os.path.join(project_path, "project.json")),
        "has_tasks_dir": os.path.exists(os.path.join(project_path, "tasks")),
        "name": os.path.basename(project_path)
    }

# ==============================================================================

#  蓝图与任务组路由

# ==============================================================================

@app.get("/api/blueprint")
async def get_full_blueprint(project_path: str):
    """加载蓝图，全面错误处理"""
    try:
        return await run_in_threadpool(BlueprintService.load_blueprint, project_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加载蓝图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加载蓝图失败: {str(e)}")

@app.post("/api/blueprint/save")
async def save_full_blueprint(request: SaveBlueprintRequestSchema):
    """
    保存蓝图
    关键修复：blueprint_data 是 Dict[str, Any]，直接落盘
    不经 Pydantic BlueprintSchema 校验，避免字段丢失和类型不匹配
    """
    try:
        await run_in_threadpool(
            BlueprintService.save_blueprint,
            request.project_path,
            request.blueprint_data
        )
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存蓝图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存蓝图失败: {str(e)}")

@app.get("/api/tasks")
async def list_tasks(project_path: str):
    try:
        return await run_in_threadpool(BlueprintService.list_tasks, project_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, project_path: str):
    try:
        return await run_in_threadpool(BlueprintService.get_task, task_id, project_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务失败: {str(e)}")

@app.put("/api/tasks/{task_id}")
async def save_task(task_id: str, request: SaveTaskRequestSchema):
    return await run_in_threadpool(BlueprintService.save_task, task_id, request)

@app.post("/api/tasks")
async def create_task(request: SaveTaskRequestSchema):
    return await run_in_threadpool(BlueprintService.create_task, request)

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, project_path: str):
    return await run_in_threadpool(BlueprintService.delete_task, task_id, project_path)

@app.get("/api/tasks/{task_id}/nodes")
async def get_task_nodes(task_id: str, project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        project = await run_in_threadpool(load_project, project_path)
        task = project.tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return [{"node_id": n.node_id, "node_name": n.node_name} for n in task.nodes]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取节点列表失败: {str(e)}")

@app.post("/api/tasks/order")
async def save_task_order(request: TaskOrderRequestSchema):
    return await run_in_threadpool(BlueprintService.save_task_order, request.project_path, request.order)

# ==============================================================================

#  客户动态表单导出、打包与 EXE 编译 API

# ==============================================================================

@app.get("/api/exporter/schema")
async def get_exporter_schema(project_path: str):
    if ExportService is None:
        _service_unavailable("ExportService")
    return await run_in_threadpool(ExportService.get_form_schema, project_path)

@app.post("/api/exporter/schema")
async def save_exporter_schema(data: dict = Body(...)):
    if ExportService is None:
        _service_unavailable("ExportService")
    project_path = data.get("project_path")
    schema_data = data.get("schema_data")
    return await run_in_threadpool(ExportService.save_form_schema, project_path, schema_data)

@app.post("/api/exporter/build")
async def build_export_bundle(data: dict = Body(...)):
    if ExportService is None:
        _service_unavailable("ExportService")
    project_path = data.get("project_path")
    form_schema = data.get("form_schema")
    return await run_in_threadpool(ExportService.build_export_bundle, project_path, form_schema)

@app.post("/api/exporter/compile-exe")
async def compile_player_executable(data: dict = Body(...)):
    if CompilerService is None:
        _service_unavailable("CompilerService")
    project_path = data.get("project_path")
    return await run_in_threadpool(CompilerService.compile_player_exe, project_path)

# ==============================================================================

#  Player 运行端专有 API 路由

# ==============================================================================

@app.get("/api/player/init")
async def player_init_session(project_path: str = None):
    if PlayerService is None:
        _service_unavailable("PlayerService")
    ebp_path = None
    config_path = None

    if project_path and os.path.exists(project_path):
        ebp_path = os.path.join(project_path, "release", "assets.ebp")
        config_path = os.path.join(project_path, "release", "user_config.json")

    if not ebp_path or not os.path.exists(ebp_path):
        projects_root = os.path.join(os.getcwd(), "projects")
        if os.path.exists(projects_root):
            for sub_p in os.listdir(projects_root):
                candidate_ebp = os.path.join(projects_root, sub_p, "release", "assets.ebp")
                if os.path.exists(candidate_ebp):
                    ebp_path = candidate_ebp
                    config_path = os.path.join(projects_root, sub_p, "release", "user_config.json")
                    break

    if not ebp_path or not os.path.exists(ebp_path):
        ebp_path = os.path.join(os.getcwd(), "release", "assets.ebp")
        config_path = os.path.join(os.getcwd(), "release", "user_config.json")

    return await run_in_threadpool(PlayerService.init_session, ebp_path, config_path)

@app.get("/api/player/providers")
async def get_player_provider_options(provider: str):
    if PlayerService is None:
        _service_unavailable("PlayerService")
    options = await run_in_threadpool(PlayerService.get_provider_options, provider)
    return {"status": "success", "options": options}

@app.post("/api/player/config")
async def save_player_user_config(
        data: dict = Body(...),
        config_path: str = "release/user_config.json"
):
    if PlayerService is None:
        _service_unavailable("PlayerService")
    user_config = data.get("user_config")
    return await run_in_threadpool(PlayerService.save_user_config, user_config, config_path)

@app.post("/api/player/run")
async def run_player_script(background_tasks: BackgroundTasks):
    if PlayerService is None:
        _service_unavailable("PlayerService")
    return PlayerService.run_script(background_tasks)

@app.post("/api/player/stop")
async def stop_player_script():
    if PlayerService is None:
        _service_unavailable("PlayerService")
    return await run_in_threadpool(PlayerService.stop_script)

# ==============================================================================

#  执行引擎与日志路由

# ==============================================================================

@app.post("/api/run")
async def run_task(request: RunRequestSchema, background_tasks: BackgroundTasks):
    """
    运行任务
    修复：blueprint_data 已是 dict，无需 model_dump()
    """
    if ExecutionService is None:
        _service_unavailable("ExecutionService")
    bp_dict = request.blueprint_data if request.blueprint_data else None
    try:
        return ExecutionService.run_task(
            request.project_path, request.task_id,
            request.start_node_id, bp_dict, background_tasks
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

@app.get("/api/execution/{execution_id}")
async def get_execution_status(execution_id: str):
    if ExecutionService is None:
        _service_unavailable("ExecutionService")
    try:
        return ExecutionService.get_execution_status(execution_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行状态失败: {str(e)}")

@app.post("/api/execution/{execution_id}/stop")
async def stop_execution(execution_id: str):
    """新增：停止正在运行的执行"""
    if ExecutionService is None:
        _service_unavailable("ExecutionService")
    try:
        return ExecutionService.stop_execution(execution_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止执行失败: {str(e)}")

@app.get("/api/execution/{execution_id}/stream")
async def stream_execution(execution_id: str):
    if ExecutionService is None:
        _service_unavailable("ExecutionService")
    status_data = ExecutionService.get_execution_status(execution_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    return StreamingResponse(
        ExecutionService.stream_execution_logs(execution_id),
        media_type="text/event-stream"
    )

# ==============================================================================

#  工作区与截图交互路由

# ==============================================================================

@app.get("/api/screenshot/full")
async def get_full_screenshot(project_path: str = ""):
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    return await run_in_threadpool(WorkspaceService.get_full_screenshot, project_path)

@app.post("/api/screenshot/crop")
async def crop_screenshot(request: CropScreenshotRequestSchema):
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    return await run_in_threadpool(
        WorkspaceService.crop_screenshot, request.project_path,
        request.template_name, request.crop_rect
    )

@app.post("/api/screenshot")
async def take_screenshot(request: dict = Body(...)):
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    res = await run_in_threadpool(WorkspaceService.take_screenshot, request)
    return JSONResponse(content=res)

@app.get("/api/windows")
async def get_windows():
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    return await run_in_threadpool(WorkspaceService.get_windows)

@app.post("/api/context")
async def save_context(request: ContextSaveRequestSchema):
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    return await run_in_threadpool(WorkspaceService.save_context, request)

@app.get("/api/context")
async def get_context(project_path: str):
    if WorkspaceService is None:
        _service_unavailable("WorkspaceService")
    return await run_in_threadpool(WorkspaceService.get_context, project_path)

# ==============================================================================

#  模板与视觉资源路由

# ==============================================================================

@app.get("/api/templates/tree")
async def get_templates_tree(project_path: str):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(VisionService.get_templates_tree, project_path)

@app.get("/api/templates/preview")
async def get_template_preview(project_path: str, relative_path: str = ""):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(VisionService.get_template_preview, project_path, relative_path)

@app.get("/api/image/thumb")
async def get_image_thumb(project_path: str, name: str):
    if VisionService is None:
        _service_unavailable("VisionService")
    thumb_path = await run_in_threadpool(VisionService.get_image_thumb_path, project_path, name)
    return FileResponse(thumb_path, media_type="image/png")

@app.post("/api/templates/mkdir")
async def create_template_folder(data: dict = Body(...)):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(
        VisionService.create_template_folder, data.get("project_path"),
        data.get("parent_path", ""), data.get("folder_name", "")
    )

@app.get("/api/regions")
async def get_regions(project_path: str):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(VisionService.get_regions, project_path)

@app.post("/api/regions")
async def save_region(data: dict = Body(...)):
    if VisionService is None:
        _service_unavailable("VisionService")
    template_name = data.get("template_name") or data.get("relative_path")
    crop_rect = data.get("crop_rect") or data.get("region")
    return await run_in_threadpool(
        VisionService.save_region, data.get("project_path"), template_name, crop_rect
    )

@app.post("/api/ocr/test")
async def test_ocr_recognition(request: OcrTestRequestSchema):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(
        VisionService.test_ocr, request.project_path, request.region_value,
        request.gray_scale, request.gray_threshold
    )

@app.post("/api/image/test")
async def test_image_recognition(request: ImageTestRequestSchema):
    if VisionService is None:
        _service_unavailable("VisionService")
    return await run_in_threadpool(
        VisionService.test_image, request.project_path, request.template_name,
        request.gray_scale, request.gray_threshold
    )

# ==============================================================================

#  静态托管与 PyWebView

# ==============================================================================

web_dir = os.path.join(os.getcwd(), "release", "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="player_static")

def start_webview():
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
