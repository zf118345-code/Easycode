import os
import json
import time
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

import core.node_executors  # 必须存在，触发节点注册

from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.executor import GraphExecutor
from core.models import Project

# ---------- 初始化 ----------
app = FastAPI(title="节点自动化后端", version="2.0")

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

# ---------- 请求模型 ----------
class RunRequest(BaseModel):
    project_path: str
    task_id: str
    start_node_id: Optional[str] = None

class SaveTaskRequest(BaseModel):
    project_path: str
    task_data: dict

class RegionUpdate(BaseModel):
    project_path: str
    relative_path: str
    region: list[int]

class SyncTemplatesRequest(BaseModel):
    project_path: str

class TaskOrderRequest(BaseModel):
    project_path: str
    order: list[str]

# ---------- 接口 ----------

@app.get("/api/params")
async def get_params():
    """获取所有节点参数定义"""
    return ALL_PARAMS

# ==================== 项目验证 ====================

@app.get("/api/projects/verify")
async def verify_project(project_path: str):
    """验证项目路径是否存在"""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
    # 检查是否包含 project.json 或 tasks 目录
    has_project_json = os.path.exists(os.path.join(project_path, "project.json"))
    has_tasks_dir = os.path.exists(os.path.join(project_path, "tasks"))
    return {
        "exists": True,
        "has_project_json": has_project_json,
        "has_tasks_dir": has_tasks_dir,
        "name": os.path.basename(project_path)
    }

# ==================== 任务管理 ====================

@app.get("/api/tasks")
async def list_tasks(project_path: str):
    """获取指定项目的所有任务列表"""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
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
    # 读取任务顺序
    project_json_path = os.path.join(project_path, "project.json")
    order = []
    if os.path.exists(project_json_path):
        with open(project_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            order = data.get("task_order", [])
    return {"tasks": task_list, "order": order}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, project_path: str):
    """获取指定任务的完整数据（含节点）"""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
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

@app.put("/api/tasks/{task_id}")
async def save_task(task_id: str, request: SaveTaskRequest):
    """保存任务数据（覆盖写入）"""
    project_path = request.project_path
    task_data = request.task_data
    if not project_path or not task_data:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    tasks_dir = os.path.join(project_path, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
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

@app.post("/api/tasks")
async def create_task(request: SaveTaskRequest):
    """创建新任务"""
    project_path = request.project_path
    task_data = request.task_data
    if not project_path or not task_data:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    tasks_dir = os.path.join(project_path, "tasks")
    os.makedirs(tasks_dir, exist_ok=True)
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

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, project_path: str):
    """删除任务"""
    file_path = os.path.join(project_path, "tasks", f"{task_id}.json")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="任务不存在")
    os.remove(file_path)
    return {"status": "success"}

@app.post("/api/tasks/order")
async def save_task_order(request: TaskOrderRequest):
    """保存任务排序"""
    project_path = request.project_path
    order = request.order
    if not project_path or not order:
        raise HTTPException(status_code=400, detail="无效参数")
    project_json_path = os.path.join(project_path, "project.json")
    if not os.path.exists(project_json_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    with open(project_json_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
    project_data["task_order"] = order
    with open(project_json_path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)
    return {"status": "success"}

# ==================== 执行任务 ====================

@app.post("/api/run")
async def run_task(request: RunRequest, background_tasks: BackgroundTasks):
    """启动任务执行（后台），自动应用保存的上下文"""
    project_path = request.project_path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")

    # 读取保存的上下文
    context_path = os.path.join(project_path, CONTEXT_FILE)
    saved_context = {}
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            saved_context = json.load(f)
    print(f"执行任务加载的上下文: {saved_context}")
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")

    execution_id = f"{request.task_id}_{int(time.time() * 1000)}"
    execution_status[execution_id] = {"status": "running", "message": "执行中..."}
    execution_logs[execution_id] = []

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
                # 创建执行器，传入保存的上下文
                executor = GraphExecutor(
                    project,
                    project_dir=project_path,
                    text_log_enabled=True,
                    image_log_enabled=True,
                    initial_context=saved_context  # 新增参数
                )
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

    background_tasks.add_task(execute_background)
    return {"execution_id": execution_id, "status": "started"}

@app.get("/api/execution/{execution_id}")
async def get_execution_status(execution_id: str):
    """查询执行状态和日志"""
    status = execution_status.get(execution_id)
    if not status:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    logs = execution_logs.get(execution_id, [])
    return {"status": status, "logs": logs[-100:]}

# ==================== 模板区域管理 ====================

@app.get("/api/regions")
async def get_regions(project_path: str):
    """获取项目的 regions.json"""
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.post("/api/regions")
async def update_region(request: RegionUpdate):
    """更新/添加单个区域配置"""
    project_path = request.project_path
    relative_path = request.relative_path
    region = request.region
    if not project_path or not relative_path or region is None:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    templates_dir = os.path.join(project_path, "templates")
    regions_path = os.path.join(templates_dir, "regions.json")
    os.makedirs(templates_dir, exist_ok=True)
    regions = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
    regions[relative_path] = region
    with open(regions_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
    return {"status": "success"}

@app.post("/api/templates/sync")
async def sync_templates(request: SyncTemplatesRequest):
    """扫描 templates 目录，同步新图片到 regions.json"""
    project_path = request.project_path
    if not project_path:
        raise HTTPException(status_code=400, detail="缺少 project_path")
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

# ==================== 截图工具 ====================

@app.get("/api/windows")
async def get_windows():
    """获取当前所有可见窗口标题"""
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
    """截取指定窗口或全屏"""
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
    project_path: str = Form(...),
    template_name: str = Form(...),
    subdir: str = Form(""),
    region_x: int = Form(...),
    region_y: int = Form(...),
    region_w: int = Form(...),
    region_h: int = Form(...),
    image: UploadFile = File(...)
):
    """保存截图模板到项目 templates 目录，并更新 regions.json"""
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

# ==================== 上下文管理 ====================

CONTEXT_FILE = "context.json"

@app.post("/api/context")
async def save_context(request: dict):
    project_path = request.get("project_path")
    context = request.get("context")
    if not project_path or context is None:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    print("\n" + "=" * 60)
    print("[保存上下文] 收到请求:")
    print(f"project_path: {project_path}")
    print("context:")
    print(json.dumps(context, indent=2, ensure_ascii=False))
    print("=" * 60 + "\n")

    # 字段映射
    mapped_context = {
        "window_title": context.get("windowTitle", ""),
        "is_emulator": context.get("isEmulator", False),
        "offset_top": context.get("offsetTop", 0),
        "offset_bottom": context.get("offsetBottom", 0),
        "offset_left": context.get("offsetLeft", 0),
        "offset_right": context.get("offsetRight", 0),
        "target_content_width": context.get("targetContentWidth", 0),
        "target_content_height": context.get("targetContentHeight", 0)
    }

    print("映射后的数据 (存储到文件):")
    print(json.dumps(mapped_context, indent=2, ensure_ascii=False))
    print("="*60 + "\n")

    context_path = os.path.join(project_path, CONTEXT_FILE)
    with open(context_path, "w", encoding="utf-8") as f:
        json.dump(mapped_context, f, indent=2, ensure_ascii=False)
    return {"status": "success"}


@app.get("/api/context")
async def get_context(project_path: str):
    """获取项目的工作面板上下文（映射回前端格式）"""
    context_path = os.path.join(project_path, CONTEXT_FILE)
    if not os.path.exists(context_path):
        # 如果文件不存在，返回空上下文
        return {}

    with open(context_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 将后端下划线格式映射回前端驼峰格式
    return {
        "windowTitle": data.get("window_title", ""),
        "isEmulator": data.get("is_emulator", False),
        "offsetTop": data.get("offset_top", 0),
        "offsetBottom": data.get("offset_bottom", 0),
        "offsetLeft": data.get("offset_left", 0),
        "offsetRight": data.get("offset_right", 0),
        "targetContentWidth": data.get("target_content_width", 0),
        "targetContentHeight": data.get("target_content_height", 0)
    }

@app.get("/api/tasks/{task_id}/nodes")
async def get_task_nodes(task_id: str, project_path: str):
    """获取指定任务的节点列表（用于跳转选择）"""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")
    task = project.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    nodes = []
    for node in task.nodes:
        nodes.append({
            "node_id": node.node_id,
            "node_name": node.node_name
        })
    return nodes

# ==================== 导入项目（保留兼容） ====================
@app.post("/api/projects/import/file")
async def import_file(
    project_name: str = Form(...),
    relative_path: str = Form(...),
    file: UploadFile = File(...)
):
    """导入文件到 projects 目录（用于兼容旧逻辑）"""
    project_path = os.path.join("projects", project_name)
    file_path = os.path.join(project_path, relative_path)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "success"}


# ==================== 模板目录管理（新增） ====================
@app.get("/api/templates/tree")
async def get_templates_tree(project_path: str):
    """获取项目 templates 目录的树形结构"""
    templates_dir = os.path.join(project_path, "templates")
    if not os.path.exists(templates_dir):
        return {"tree": []}

    def build_tree(dir_path, relative_path=""):
        result = []
        try:
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)
                if os.path.isdir(item_path):
                    child_rel_path = os.path.join(relative_path, item).replace("\\", "/")
                    result.append({
                        "name": item,
                        "type": "directory",
                        "id": child_rel_path,
                        "children": build_tree(item_path, child_rel_path)
                    })
                # 跳过文件，不添加到树中
        except Exception as e:
            print(f"读取目录失败: {dir_path}, 错误: {e}")
        return result

    tree = build_tree(templates_dir, "")
    return {"tree": tree}

@app.get("/api/templates/preview")
async def get_template_preview(project_path: str, relative_path: str = ""):
    """获取 templates 下指定目录的图片预览列表（base64）"""
    templates_dir = os.path.join(project_path, "templates")
    target_dir = os.path.join(templates_dir, relative_path)

    if not os.path.exists(target_dir):
        return {"images": []}

    images = []
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isfile(item_path) and item.lower().endswith(".png"):
                with open(item_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                    images.append({
                        "name": item,
                        "data": f"data:image/png;base64,{img_data}"
                    })
    except Exception as e:
        print(f"读取预览失败: {e}")

    return {"images": images}

@app.post("/api/templates/mkdir")
async def create_directory(request: dict):
    """在项目 templates 目录下创建新文件夹"""
    project_path = request.get("project_path")
    relative_path = request.get("relative_path", "")
    dir_name = request.get("dir_name")

    if not project_path or not dir_name:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    templates_dir = os.path.join(project_path, "templates")
    target_dir = os.path.join(templates_dir, relative_path, dir_name)

    if os.path.exists(target_dir):
        raise HTTPException(status_code=400, detail="目录已存在")

    try:
        os.makedirs(target_dir, exist_ok=True)
        return {"status": "success", "path": os.path.join(relative_path, dir_name)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建目录失败: {str(e)}")

# ---------- 启动 ----------
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)