# api.py
import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

import core.node_executors
from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.schemas import (
    RunRequestSchema, SaveTaskRequestSchema, TaskOrderRequestSchema,
    SaveBlueprintRequestSchema, CropScreenshotRequestSchema,
    ContextSaveRequestSchema, OcrTestRequestSchema, ImageTestRequestSchema
)

from core.services.blueprint_service import BlueprintService
from core.services.workspace_service import WorkspaceService
from core.services.vision_service import VisionService
from core.services.execution_service import ExecutionService

app = FastAPI(title="节点自动化后端", version="2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    return await run_in_threadpool(BlueprintService.load_blueprint, project_path)

@app.post("/api/blueprint/save")
async def save_full_blueprint(request: SaveBlueprintRequestSchema):
    await run_in_threadpool(BlueprintService.save_blueprint, request.project_path, request.blueprint_data.model_dump())
    return {"status": "success"}

@app.get("/api/tasks")
async def list_tasks(project_path: str):
    return await run_in_threadpool(BlueprintService.list_tasks, project_path)

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, project_path: str):
    return await run_in_threadpool(BlueprintService.get_task, task_id, project_path)

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
    project = await run_in_threadpool(load_project, project_path)
    task = project.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return [{"node_id": n.node_id, "node_name": n.node_name} for n in task.nodes]

@app.post("/api/tasks/order")
async def save_task_order(request: TaskOrderRequestSchema):
    return await run_in_threadpool(BlueprintService.save_task_order, request.project_path, request.order)

# ==============================================================================
#  执行引擎与日志路由
# ==============================================================================

@app.post("/api/run")
async def run_task(request: RunRequestSchema, background_tasks: BackgroundTasks):
    bp_dict = request.blueprint_data.model_dump() if request.blueprint_data else None
    return ExecutionService.run_task(request.project_path, request.task_id, request.start_node_id, bp_dict, background_tasks)

@app.get("/api/execution/{execution_id}")
async def get_execution_status(execution_id: str):
    return ExecutionService.get_execution_status(execution_id)

# ==============================================================================
#  工作区与截图交互路由
# ==============================================================================

@app.get("/api/screenshot/full")
async def get_full_screenshot(project_path: str = ""):
    return await run_in_threadpool(WorkspaceService.get_full_screenshot, project_path)

@app.post("/api/screenshot/crop")
async def crop_screenshot(request: CropScreenshotRequestSchema):
    return await run_in_threadpool(WorkspaceService.crop_screenshot, request.project_path, request.template_name, request.crop_rect)

@app.post("/api/screenshot")
async def take_screenshot(request: dict = Body(...)):
    res = await run_in_threadpool(WorkspaceService.take_screenshot, request)
    return JSONResponse(content=res)

@app.get("/api/windows")
async def get_windows():
    return await run_in_threadpool(WorkspaceService.get_windows)

@app.post("/api/context")
async def save_context(request: ContextSaveRequestSchema):
    return await run_in_threadpool(WorkspaceService.save_context, request)

@app.get("/api/context")
async def get_context(project_path: str):
    return await run_in_threadpool(WorkspaceService.get_context, project_path)

# ==============================================================================
#  模板与视觉资源路由
# ==============================================================================

@app.get("/api/templates/tree")
async def get_templates_tree(project_path: str):
    return await run_in_threadpool(VisionService.get_templates_tree, project_path)

@app.get("/api/templates/preview")
async def get_template_preview(project_path: str, relative_path: str = ""):
    return await run_in_threadpool(VisionService.get_template_preview, project_path, relative_path)

@app.get("/api/image/thumb")
async def get_image_thumb(project_path: str, name: str):
    thumb_path = await run_in_threadpool(VisionService.get_image_thumb_path, project_path, name)
    return FileResponse(thumb_path, media_type="image/png")

@app.post("/api/templates/mkdir")
async def create_template_folder(data: dict = Body(...)):
    return await run_in_threadpool(VisionService.create_template_folder, data.get("project_path"), data.get("parent_path", ""), data.get("folder_name", ""))

@app.get("/api/regions")
async def get_regions(project_path: str):
    return await run_in_threadpool(VisionService.get_regions, project_path)

@app.post("/api/regions")
async def save_region(data: dict = Body(...)):
    template_name = data.get("template_name") or data.get("relative_path")
    crop_rect = data.get("crop_rect") or data.get("region")
    return await run_in_threadpool(VisionService.save_region, data.get("project_path"), template_name, crop_rect)

@app.post("/api/ocr/test")
async def test_ocr_recognition(request: OcrTestRequestSchema):
    return await run_in_threadpool(VisionService.test_ocr, request.project_path, request.region_value, request.gray_scale, request.gray_threshold)

@app.post("/api/image/test")
async def test_image_recognition(request: ImageTestRequestSchema):
    return await run_in_threadpool(VisionService.test_image, request.project_path, request.template_name, request.gray_scale, request.gray_threshold)


@app.get("/api/execution/{execution_id}/stream")
async def stream_execution(execution_id: str):
    """
    前端通过 EventSource 订阅该接口，实现零延迟的服务器端实时日志推送
    """
    # 统一通过 ExecutionService 校验状态是否存在，避免直接引用底层变量
    status_data = ExecutionService.get_execution_status(execution_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    return StreamingResponse(
        ExecutionService.stream_execution_logs(execution_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)