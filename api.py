# api.py
from fastapi.responses import JSONResponse
from fastapi import File, UploadFile, Form
import shutil
import base64
import io
from PIL import Image as PILImage
import pyautogui
import win32con
import os
import json
import uvicorn
import win32gui
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 导入你的核心模块
from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.executor import GraphExecutor
from core.models import Project

# api.py 中添加/修改
import threading
import time

# 用于存储执行状态（后续可扩展为 WebSocket 队列）
execution_status = {}

# ---------- 初始化 FastAPI ----------
app = FastAPI(title="节点自动化后端", version="1.0")

# 允许跨域（开发环境下 Vue 默认端口 5173，允许它访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 接口 1：获取所有节点参数定义 ----------
@app.get("/api/params")
async def get_params():
    """前端动态渲染表单的依据"""
    return ALL_PARAMS


# ---------- 接口 2：获取项目列表 ----------
@app.get("/api/projects")
async def list_projects():
    projects_dir = "projects"
    if not os.path.exists(projects_dir):
        os.makedirs(projects_dir)
    projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
    return {"projects": projects}


# ---------- 接口 3：获取指定项目的任务列表 ----------
@app.get("/api/projects/{project_name}/tasks")
async def list_tasks(project_name: str):
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    project = load_project(project_path)
    task_list = []
    for task_id, task in project.tasks.items():
        task_list.append({
            "task_id": task.task_id,
            "task_name": task.task_name,
            "node_count": len(task.nodes)
        })
    # 读取顺序
    project_json_path = os.path.join(project_path, "project.json")
    order = []
    if os.path.exists(project_json_path):
        with open(project_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            order = data.get("task_order", [])
    return {"tasks": task_list, "order": order}


# ---------- 接口 4：获取指定任务的完整数据（含所有节点） ----------
@app.get("/api/projects/{project_name}/tasks/{task_id}")
async def get_task(project_name: str, task_id: str):
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")

    project = load_project(project_path)
    task = project.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 将节点转换为可序列化的字典
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
            "node_name": node.node_name,  # 新增
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


# ---------- 接口 5：保存任务 ----------
class SaveTaskRequest(BaseModel):
    task_data: dict


@app.put("/api/projects/{project_name}/tasks/{task_id}")
async def save_task(project_name: str, task_id: str, request: SaveTaskRequest):
    project_path = os.path.join("projects", project_name)
    tasks_dir = os.path.join(project_path, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)

    task_data = request.task_data
    # 确保必要字段存在
    task_data["task_id"] = task_id
    if "task_name" not in task_data or not task_data["task_name"]:
        task_data["task_name"] = task_id
    # 删除可能残留的旧字段
    task_data.pop("description", None)
    task_data.pop("delay_before", None)
    # 确保 nodes 存在
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

    # 检查重名
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
    return {"status": "success", "message": "任务已删除"}

# ---------- 接口 6：执行任务 ----------
class RunRequest(BaseModel):
    task_id: str
    start_node_id: str = None


@app.post("/api/projects/{project_name}/run")
async def run_task(project_name: str, request: RunRequest):
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")

    project = load_project(project_path)
    executor = GraphExecutor(project, text_log_enabled=True, image_log_enabled=True)

    try:
        # 直接同步执行（如果任务耗时较长，可考虑异步）
        executor.run(request.task_id)
        return {"status": "success", "message": "执行完成"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

@app.get("/api/projects/{project_name}/tasks/order")
async def get_task_order(project_name: str):
    project_path = os.path.join("projects", project_name)
    project_json_path = os.path.join(project_path, "project.json")
    if not os.path.exists(project_json_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
    order = project_data.get("task_order", [])
    return {"order": order}


# ========== 新增：获取窗口列表接口 ==========
@app.get("/api/windows")
async def get_windows():
    import win32gui
    windows = []
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append({
                    "hwnd": hwnd,
                    "title": title
                })
    win32gui.EnumWindows(callback, windows)
    return {"windows": windows}


@app.post("/api/screenshot")
async def take_screenshot(request: dict):
    """
    截取指定窗口或桌面的截图
    请求体：{
        "window_title": "雷电模拟器",  // 可选，如果不传则截取全屏
        "offset_top": 0,
        "offset_bottom": 0,
        "offset_left": 0,
        "offset_right": 0,
        "is_emulator": false  // 暂时仅用于标识，不影响截图逻辑
    }
    返回：{"image": "data:image/png;base64,...", "rect": [x, y, w, h]}
    """
    window_title = request.get("window_title")
    offset_top = request.get("offset_top", 0)
    offset_bottom = request.get("offset_bottom", 0)
    offset_left = request.get("offset_left", 0)
    offset_right = request.get("offset_right", 0)

    if window_title:
        # 查找窗口
        hwnd = win32gui.FindWindow(None, window_title)
        if not hwnd:
            raise HTTPException(status_code=404, detail="未找到窗口")
        # 获取窗口客户区
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        # 应用裁剪
        x = left + offset_left
        y = top + offset_top
        w = (right - left) - offset_left - offset_right
        h = (bottom - top) - offset_top - offset_bottom
        if w <= 0 or h <= 0:
            raise HTTPException(status_code=400, detail="裁剪后区域无效")
        region = (x, y, w, h)
    else:
        # 全屏
        screen_w, screen_h = pyautogui.size()
        region = (0, 0, screen_w, screen_h)

    # 截图
    screenshot = pyautogui.screenshot(region=region)
    # 转为base64
    buffered = io.BytesIO()
    screenshot.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return JSONResponse(content={
        "image": f"data:image/png;base64,{img_base64}",
        "rect": region  # 实际截取的区域（屏幕坐标）
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


from pydantic import BaseModel


class RegionUpdate(BaseModel):
    relative_path: str  # 相对于项目 templates 目录的路径（不含扩展名）
    region: list[int]  # [x, y, w, h]


@app.post("/api/projects/{project_name}/regions")
async def update_region(project_name: str, data: RegionUpdate):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")

    print(f"项目路径: {project_path}")
    print(f"templates 目录: {templates_dir}")
    print(f"regions 文件路径: {regions_path}")

    # 确保 templates 目录存在
    os.makedirs(templates_dir, exist_ok=True)

    # 读取现有 regions.json
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    else:
        print("regions.json 不存在，将创建新文件")

    # 更新或添加
    regions[data.relative_path] = data.region
    print(f"写入数据: {data.relative_path} -> {data.region}")

    # 写回
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)

    return {"status": "success", "message": "region updated"}


@app.post("/api/projects/{project_name}/templates/sync")
async def sync_templates(project_name: str):
    """扫描项目 templates 目录，更新 regions.json"""
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    if not os.path.exists(templates_dir):
        raise HTTPException(status_code=404, detail="templates directory not found")

    regions_path = os.path.join(templates_dir, "regions.json")
    # 读取现有 regions
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)

    # 遍历 templates 目录下所有 .png 文件（含子目录）
    updated = 0
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.lower().endswith(".png"):
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                key = os.path.splitext(rel_path)[0].replace("\\", "/")
                if key not in regions:
                    # 新图片，添加默认区域 (全屏或 (0,0,0,0))
                    regions[key] = [0, 0, 0, 0]
                    updated += 1

    # 写回 regions.json
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)

    return {"status": "success", "updated": updated, "message": f"已同步 {updated} 个新模板"}

# ========== 逐文件上传 ==========
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

# ========== 保存模板（自动保存到项目 templates 并更新 regions.json） ==========
@app.post("/api/projects/save-template")
async def save_template(
    project_name: str = Form(...),
    relative_path: str = Form(...),  # 如 "subdir/icon"
    region_x: int = Form(...),
    region_y: int = Form(...),
    region_w: int = Form(...),
    region_h: int = Form(...),
    image: UploadFile = File(...)
):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    # 构建目标文件路径
    file_name = f"{relative_path}.png"
    file_path = os.path.join(templates_dir, file_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # 保存图片
    with open(file_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    # 更新 regions.json
    regions_path = os.path.join(templates_dir, "regions.json")
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    regions[relative_path] = [region_x, region_y, region_w, region_h]
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)

    return {"status": "success", "saved_path": relative_path}


# ========== 创建目录（用于新增子目录） ==========
class MkdirRequest(BaseModel):
    path: str  # 相对路径，如 "templates/subdir"

@app.post("/api/projects/{project_name}/mkdir")
async def create_directory(project_name: str, request: MkdirRequest):
    project_path = os.path.join("projects", project_name)
    full_path = os.path.join(project_path, request.path)
    os.makedirs(full_path, exist_ok=True)
    return {"status": "success"}

@app.get("/api/projects/{project_name}/regions")
async def get_regions(project_name: str):
    project_path = os.path.join("projects", project_name)
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ---------- 启动服务 ----------
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)