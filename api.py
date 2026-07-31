import os
import json
import time
import threading
import shutil
import base64
import io
import win32gui
import win32con
import pyautogui
import uvicorn
from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

import core.node_executors  # 这行必须存在

from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.executor import GraphExecutor
from core.models import Project

# ---------- 初始化 ----------
app = FastAPI(title="节点自动化后端", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 执行状态存储 ----------
execution_status = {}
execution_logs = {}


class RunRequest(BaseModel):
    task_id: str
    start_node_id: Optional[str] = None


class SaveTaskRequest(BaseModel):
    task_data: dict


class RegionUpdate(BaseModel):
    relative_path: str
    region: list[int]


# ---------- 接口 ----------
@app.get("/api/params")
async def get_params():
    return ALL_PARAMS


@app.get("/api/projects")
async def list_projects():
    projects_dir = "projects"
    if not os.path.exists(projects_dir):
        os.makedirs(projects_dir)
    projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
    return {"projects": projects}


# ========== 项目根目录管理 ==========
PROJECTS_ROOT_FILE = "projects_root.json"

@app.get("/api/projects/root")
async def get_projects_root():
    """获取保存的项目根目录"""
    if os.path.exists(PROJECTS_ROOT_FILE):
        with open(PROJECTS_ROOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {"root": data.get("root", "")}
    return {"root": ""}

@app.post("/api/projects/root")
async def set_projects_root(request: dict):
    """保存项目根目录"""
    root = request.get("root")
    if not root:
        raise HTTPException(status_code=400, detail="root is required")
    with open(PROJECTS_ROOT_FILE, "w", encoding="utf-8") as f:
        json.dump({"root": root}, f, indent=2)
    return {"status": "success", "root": root}

@app.get("/api/projects/{project_name}/tasks")
async def list_tasks(project_name: str):
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")
    task_list = []
    for task_id, task in project.tasks.items():
        task_list.append({
            "task_id": task.task_id,
            "task_name": task.task_name,
            "node_count": len(task.nodes)
        })
    project_json_path = os.path.join(project_path, "project.json")
    order = []
    if os.path.exists(project_json_path):
        with open(project_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            order = data.get("task_order", [])
    return {"tasks": task_list, "order": order}


@app.get("/api/projects/{project_name}/tasks/{task_id}")
async def get_task(project_name: str, task_id: str):
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")
    task = project.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task_dict = {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "loop_count": task.loop_count,
        "loop_interval": task.loop_interval,
        "nodes": []
    }
    for node in task.nodes:
        node_dict = {
            "node_id": node.node_id,
            "node_name": node.node_name,
            "node_type": node.node_type,
            "params": node.params,
            "delay_before": node.delay_before,
            "loop_count": node.loop_count,
            "enabled": node.enabled,
            "on_success": {
                "type": node.on_success.type,
                "target": node.on_success.target,
                "target_node": node.on_success.target_node,
                "return_on_complete": node.on_success.return_on_complete
            },
            "on_failure": {
                "type": node.on_failure.type,
                "target": node.on_failure.target,
                "target_node": node.on_failure.target_node,
                "return_on_complete": node.on_failure.return_on_complete
            },
            "position": node.position
        }
        task_dict["nodes"].append(node_dict)
    return task_dict


@app.put("/api/projects/{project_name}/tasks/{task_id}")
async def save_task(project_name: str, task_id: str, request: SaveTaskRequest):
    project_path = os.path.join("projects", project_name)
    tasks_dir = os.path.join(project_path, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    task_data = request.task_data
    task_data["task_id"] = task_id
    if "task_name" not in task_data or not task_data["task_name"]:
        task_data["task_name"] = task_id
    task_data.pop("description", None)
    task_data.pop("delay_before", None)
    if "nodes" not in task_data:
        task_data["nodes"] = []
    file_path = os.path.join(tasks_dir, f"{task_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    return {"status": "success"}


@app.post("/api/projects/{project_name}/tasks")
async def create_task(project_name: str, request: SaveTaskRequest):
    project_path = os.path.join("projects", project_name)
    tasks_dir = os.path.join(project_path, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    task_data = request.task_data
    task_name = task_data.get("task_name", "新任务")
    for filename in os.listdir(tasks_dir):
        if filename.endswith(".json"):
            with open(os.path.join(tasks_dir, filename), "r", encoding="utf-8") as f:
                existing = json.load(f)
                if existing.get("task_name") == task_name:
                    raise HTTPException(status_code=400, detail="任务名称已存在")
    import time
    task_id = f"task_{int(time.time() * 1000)}"
    task_data["task_id"] = task_id
    task_data.pop("description", None)
    task_data.pop("delay_before", None)
    if "nodes" not in task_data:
        task_data["nodes"] = []
    file_path = os.path.join(tasks_dir, f"{task_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    return {"status": "success", "task_id": task_id}


@app.delete("/api/projects/{project_name}/tasks/{task_id}")
async def delete_task(project_name: str, task_id: str):
    project_path = os.path.join("projects", project_name)
    file_path = os.path.join(project_path, "tasks", f"{task_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="任务不存在")
    os.remove(file_path)
    return {"status": "success"}


# ========== 执行任务（关键） ==========
@app.post("/api/projects/{project_name}/run")
async def run_task(project_name: str, request: RunRequest, background_tasks: BackgroundTasks):
    # 1. 读取保存的项目根目录
    root_path = ""
    if os.path.exists(PROJECTS_ROOT_FILE):
        with open(PROJECTS_ROOT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            root_path = data.get("root", "")

    if not root_path:
        raise HTTPException(status_code=400, detail="未设置项目根目录，请先选择项目仓库路径")

    # 2. 构建项目绝对路径
    project_path = os.path.join(root_path, project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_path}")

    # 3. 加载项目数据
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")

    # 4. 生成执行ID
    execution_id = f"{request.task_id}_{int(time.time() * 1000)}"
    execution_status[execution_id] = {"status": "running", "message": "执行中..."}
    execution_logs[execution_id] = []

    # 5. 后台执行函数
    def execute_background():
        import logging
        from io import StringIO
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        import pyautogui
        original_failsafe = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False
        try:
            try:
                # 创建执行器，传入项目路径
                executor = GraphExecutor(project, project_dir=project_path, text_log_enabled=True,
                                         image_log_enabled=True)
                print(f"开始执行任务: {request.task_id}, 起始节点: {request.start_node_id}")
                executor.run(request.task_id, request.start_node_id)
                execution_status[execution_id] = {"status": "success", "message": "执行完成"}
                print("执行完成")
            except Exception as e:
                print(f"执行异常: {e}")
                execution_status[execution_id] = {"status": "error", "message": str(e)}
        finally:
            logs = log_stream.getvalue()
            if logs:
                execution_logs[execution_id] = logs.splitlines()
            else:
                execution_logs[execution_id] = ["（无日志）"]
            pyautogui.FAILSAFE = original_failsafe
            root_logger.removeHandler(handler)

    # 6. 启动后台任务
    background_tasks.add_task(execute_background)
    return {"execution_id": execution_id, "status": "started"}

@app.get("/api/projects/{project_name}/execution/{execution_id}")
async def get_execution_status(project_name: str, execution_id: str):
    status = execution_status.get(execution_id)
    if not status:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    logs = execution_logs.get(execution_id, [])
    return {
        "status": status,
        "logs": logs[-100:]  # 返回最近100条日志
    }


@app.post("/api/projects/{project_name}/tasks/order")
async def save_task_order(project_name: str, request: Request):
    data = await request.json()
    order = data.get("order")
    if not order or not isinstance(order, list):
        raise HTTPException(status_code=400, detail="无效的顺序数据")
    project_path = os.path.join("projects", project_name)
    project_json_path = os.path.join(project_path, "project.json")
    if not os.path.exists(project_json_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
    project_data["task_order"] = order
    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)
    return {"status": "success"}


@app.get("/api/windows")
async def get_windows():
    windows = []

    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append({"hwnd": hwnd, "title": title})

    win32gui.EnumWindows(callback, windows)
    return {"windows": windows}


@app.post("/api/screenshot")
async def take_screenshot(request: dict):
    window_title = request.get("window_title")
    offset_top = request.get("offset_top", 0)
    offset_bottom = request.get("offset_bottom", 0)
    offset_left = request.get("offset_left", 0)
    offset_right = request.get("offset_right", 0)
    if window_title:
        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            raise HTTPException(status_code=404, detail="未找到窗口")
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        x = left + offset_left
        y = top + offset_top
        w = (right - left) - offset_left - offset_right
        h = (bottom - top) - offset_top - offset_bottom
        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail="裁剪后区域无效")
        region = (x, y, w, h)
    else:
        screen_w, screen_h = pyautogui.size()
        region = (0, 0, screen_w, screen_h)
    screenshot = pyautogui.screenshot(region=region)
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return JSONResponse(content={
        "image": f"data:image/png;base64,{img_base64}",
        "rect": region
    })


@app.post("/api/screenshot/save")
async def save_screenshot(
        project_name: str = Form(...),
        template_name: str = Form(...),
        subdir: str = Form(""),
        region_x: int = Form(...),
        region_y: int = Form(...),
        region_w: int = Form(...),
        region_h: int = Form(...),
        image: UploadFile = File(...)
):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    if subdir:
        save_dir = os.path.join(templates_dir, subdir)
    else:
        save_dir = templates_dir
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{template_name}.png"
    filepath = os.path.join(save_dir, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(image.file, f)
    regions_path = os.path.join(templates_dir, "regions.json")
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    rel_path = os.path.join(subdir, filename) if subdir else filename
    rel_path = rel_path.replace("\\", "/")
    key = os.path.splitext(rel_path)[0]
    regions[key] = [region_x, region_y, region_w, region_h]
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
    return {"status": "success", "path": rel_path}


@app.get("/api/projects/{project_name}/regions")
async def get_regions(project_name: str):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@app.post("/api/projects/{project_name}/regions")
async def update_region(project_name: str, data: RegionUpdate):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")
    os.makedirs(templates_dir, exist_ok=True)
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    regions[data.relative_path] = data.region
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
    return {"status": "success"}


@app.post("/api/projects/{project_name}/templates/sync")
async def sync_templates(project_name: str):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    if not os.path.exists(templates_dir):
        raise HTTPException(status_code=404, detail="templates directory not found")
    regions_path = os.path.join(templates_dir, "regions.json")
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    updated = 0
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.lower().endswith(".png"):
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                key = os.path.splitext(rel_path)[0].replace("\\", "/")
                if key not in regions:
                    regions[key] = [0, 0, 0, 0]
                    updated += 1
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
    return {"status": "success", "updated": updated}


@app.post("/api/projects/import/file")
async def import_file(
        project_name: str = Form(...),
        relative_path: str = Form(...),
        file: UploadFile = File(...)
):
    project_path = os.path.join("projects", project_name)
    file_path = os.path.join(project_path, relative_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)