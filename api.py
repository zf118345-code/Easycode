# api.py
import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"

import json
import time
import shutil
import base64
import io
import re
import logging
from collections import OrderedDict
import win32gui
import win32process
import win32con
import pyautogui
import uvicorn
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

import core.node_executors

from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.executor import GraphExecutor

app = FastAPI(title="节点自动化后端", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONTEXT_FILE = "context.json"
REGIONS_FILE_PATH = os.path.join("templates", "regions.json")

MAX_LOG_ENTRIES = 100
execution_status = OrderedDict()
execution_logs = OrderedDict()


def record_execution(execution_id, status_data, logs_data):
    if len(execution_status) >= MAX_LOG_ENTRIES:
        execution_status.popitem(last=False)
        execution_logs.popitem(last=False)
    execution_status[execution_id] = status_data
    execution_logs[execution_id] = logs_data


class RunRequest(BaseModel):
    project_path: str
    task_id: str
    start_node_id: Optional[str] = None
    blueprint_data: Optional[dict] = None  # ⭐ 新增：接收前端传来的实时画布数据


class SaveTaskRequest(BaseModel):
    project_path: str
    task_data: dict


class TaskOrderRequest(BaseModel):
    project_path: str
    order: list[str]


@app.get("/api/params")
async def get_params():
    return ALL_PARAMS


@app.get("/api/projects/verify")
async def verify_project(project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
    has_project_json = os.path.exists(os.path.join(project_path, "project.json"))
    has_tasks_dir = os.path.exists(os.path.join(project_path, "tasks"))
    return {
        "exists": True,
        "has_project_json": has_project_json,
        "has_tasks_dir": has_tasks_dir,
        "name": os.path.basename(project_path)
    }


# ====== api.py 中用于替换任务读写的完整后端函数 ======

BLUEPRINT_FILE = "project_blueprint.json"


def get_blueprint_path(project_path):
    return os.path.join(project_path, BLUEPRINT_FILE)


def load_blueprint(project_path):
    bp_path = get_blueprint_path(project_path)
    if os.path.exists(bp_path):
        with open(bp_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 默认空蓝图结构
    return {"project_name": os.path.basename(project_path), "tasks": [], "variables": {}}


def save_blueprint(project_path, data):
    bp_path = get_blueprint_path(project_path)
    with open(bp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.get("/api/tasks")
async def list_tasks(project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
    try:
        bp_data = load_blueprint(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载蓝图失败: {str(e)}")

    task_list = []
    for task in bp_data.get("tasks", []):
        task_list.append({
            "task_id": task.get("task_id"),
            "task_name": task.get("task_name"),
            "node_count": len(task.get("nodes", []))
        })

    order = [t["task_id"] for t in task_list]
    return {"tasks": task_list, "order": order}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, project_path: str):
    bp_data = load_blueprint(project_path)
    # 如果大文件里有 tasks 数组
    if "tasks" in bp_data:
        for task in bp_data.get("tasks", []):
            if task.get("task_id") == task_id:
                return task
        # 默认返回第一个
        if bp_data["tasks"]:
            return bp_data["tasks"][0]

    # 如果大文件本身就是单任务结构
    return bp_data


@app.put("/api/tasks/{task_id}")
async def save_task(task_id: str, request: SaveTaskRequest):
    project_path = request.project_path
    task_data = request.task_data
    if not project_path or not task_data:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    bp_data = load_blueprint(project_path)
    tasks = bp_data.setdefault("tasks", [])

    task_data["task_id"] = task_id
    if "task_name" not in task_data or not task_data["task_name"]:
        task_data["task_name"] = task_id

    # ⭐ 精确匹配 task_id 进行局部更新，严禁破坏其他任务组
    found = False
    for i, t in enumerate(tasks):
        if t.get("task_id") == task_id:
            tasks[i] = task_data
            found = True
            break
    if not found:
        tasks.append(task_data)

    save_blueprint(project_path, bp_data)
    return {"status": "success"}


@app.post("/api/tasks")
async def create_task(request: SaveTaskRequest):
    project_path = request.project_path
    task_data = request.task_data
    if not project_path or not task_data:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    bp_data = load_blueprint(project_path)
    tasks = bp_data.setdefault("tasks", [])
    task_name = task_data.get("task_name", "新任务组")

    if any(t.get("task_name") == task_name for t in tasks):
        raise HTTPException(status_code=400, detail="任务名称已存在")

    task_id = f"task_{int(time.time() * 1000)}"
    task_data["task_id"] = task_id
    task_data["task_name"] = task_name
    if "nodes" not in task_data:
        task_data["nodes"] = []

    tasks.append(task_data)
    save_blueprint(project_path, bp_data)
    return {"status": "success", "task_id": task_id}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, project_path: str):
    bp_data = load_blueprint(project_path)
    tasks = bp_data.get("tasks", [])

    new_tasks = [t for t in tasks if t.get("task_id") != task_id]
    if len(new_tasks) == len(tasks):
        raise HTTPException(status_code=404, detail="任务不存在")

    bp_data["tasks"] = new_tasks
    save_blueprint(project_path, bp_data)
    return {"status": "success"}

@app.get("/api/tasks/{task_id}/nodes")
async def get_task_nodes(task_id: str, project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")
    task = project.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return [{"node_id": n.node_id, "node_name": n.node_name} for n in task.nodes]

@app.post("/api/tasks/order")
async def save_task_order(request: TaskOrderRequest):
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


@app.post("/api/run")
async def run_task(request: RunRequest, background_tasks: BackgroundTasks):
    project_path = request.project_path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")

    # ⭐ 核心修复：如果前端带了最新的画布数据，先自动落盘保存，确保执行引擎读到最新节点
    if request.blueprint_data:
        try:
            save_blueprint(project_path, request.blueprint_data)
        except Exception as e:
            print(f"运行前自动同步保存蓝图失败: {e}")

    context_path = os.path.join(project_path, CONTEXT_FILE)
    saved_context = {}
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            saved_context = json.load(f)

    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")

    # ... 后续执行逻辑保持不变 ...

    execution_id = f"{request.task_id}_{int(time.time() * 1000)}"
    record_execution(execution_id, {"status": "running", "message": "执行中..."}, [])

    def execute_background():
        original_failsafe = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False

        executor = GraphExecutor(
            project,
            project_dir=project_path,
            text_log_enabled=True,
            image_log_enabled=True,
            initial_context=saved_context
        )

        try:
            # 实时挂载日志对象，让前端轮询能中途拿到日志
            execution_logs[execution_id] = executor.logs
            executor.run(request.task_id, request.start_node_id)
            execution_status[execution_id] = {"status": "success", "message": "执行完成"}
        except Exception as e:
            execution_status[execution_id] = {"status": "error", "message": str(e)}
        finally:
            execution_logs[execution_id] = executor.logs
            pyautogui.FAILSAFE = original_failsafe

    background_tasks.add_task(execute_background)
    return {"execution_id": execution_id, "status": "started"}


@app.get("/api/execution/{execution_id}")
async def get_execution_status(execution_id: str):
    """实时查询运行状态与透明化日志（含实时图片 Base64）"""
    status = execution_status.get(execution_id)
    if not status:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    logs = execution_logs.get(execution_id, [])
    return {"status": status, "logs": logs}


@app.get("/api/screenshot/full")
async def get_full_screenshot(project_path: str = ""):
    region = None

    if project_path:
        context_path = os.path.join(project_path, CONTEXT_FILE)
        if os.path.exists(context_path):
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    ctx = json.load(f)
                window_title = ctx.get("window_title")
                if window_title:
                    hwnd = win32gui.FindWindow(None, window_title)
                    if hwnd:
                        client_rect = win32gui.GetClientRect(hwnd)
                        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                        right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

                        off_top = ctx.get("offset_top", 0)
                        off_bottom = ctx.get("offset_bottom", 0)
                        off_left = ctx.get("offset_left", 0)
                        off_right = ctx.get("offset_right", 0)

                        x = left + off_left
                        y = top + off_top
                        w = (right - left) - off_left - off_right
                        h = (bottom - top) - offset_bottom - off_right

                        if w > 0 and h > 0:
                            region = (x, y, w, h)
            except Exception as e:
                print(f"读取工作区失败: {e}")

    try:
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {
            "image": img_str,
            "width": screenshot.width,
            "height": screenshot.height,
            "region": region or [0, 0, pyautogui.size()[0], pyautogui.size()[1]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"截取工作区失败: {str(e)}")


@app.post("/api/screenshot/crop")
async def crop_screenshot(data: dict = Body(...)):
    project_path = data.get("project_path")
    template_name = data.get("template_name")
    crop_rect = data.get("crop_rect")

    if not project_path or not template_name or not crop_rect:
        raise HTTPException(status_code=400, detail="缺少参数")

    templates_dir = os.path.join(project_path, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    clean_key = re.sub(r'\.png$', '', template_name, flags=re.IGNORECASE).replace("\\", "/")

    save_path = os.path.join(templates_dir, f"{clean_key}.png")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    try:
        rel_x, rel_y, w, h = crop_rect

        context_path = os.path.join(project_path, CONTEXT_FILE)
        abs_x, abs_y = rel_x, rel_y
        if os.path.exists(context_path):
            with open(context_path, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            window_title = ctx.get("window_title")
            if window_title:
                hwnd = win32gui.FindWindow(None, window_title)
                if hwnd:
                    client_rect = win32gui.GetClientRect(hwnd)
                    left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                    abs_x = left + ctx.get("offset_left", 0) + rel_x
                    abs_y = top + ctx.get("offset_top", 0) + rel_y

        full_img = pyautogui.screenshot()
        cropped_img = full_img.crop((abs_x, abs_y, abs_x + w, abs_y + h))
        cropped_img.save(save_path)

        regions_json_path = os.path.join(project_path, REGIONS_FILE_PATH)
        regions_data = {}
        if os.path.exists(regions_json_path):
            try:
                with open(regions_json_path, "r", encoding="utf-8") as f:
                    regions_data = json.load(f)
            except Exception:
                regions_data = {}

        regions_data[clean_key] = crop_rect

        with open(regions_json_path, "w", encoding="utf-8") as f:
            json.dump(regions_data, f, ensure_ascii=False, indent=2)

        return {"status": "success", "file_path": save_path, "key": clean_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存模板图片失败: {str(e)}")


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


@app.get("/api/templates/tree")
async def get_templates_tree(project_path: str):
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
        except Exception as e:
            print(f"读取目录失败: {dir_path}, 错误: {e}")
        return result

    tree = build_tree(templates_dir, "")
    return {"tree": tree}


@app.get("/api/templates/preview")
async def get_template_preview(project_path: str, relative_path: str = ""):
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


@app.get("/api/image/thumb")
async def get_image_thumb(project_path: str, name: str):
    """提供给前端节点卡片展示模板图片缩略图的接口"""
    if not project_path or not name:
        raise HTTPException(status_code=400, detail="缺少参数")

    # 清理路径防止越权和格式问题
    clean_name = re.sub(r'\.png$', '', name, flags=re.IGNORECASE).replace("\\", "/")
    template_path = os.path.join(project_path, "templates", f"{clean_name}.png")

    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="缩略图不存在")

    try:
        from fastapi.responses import FileResponse
        return FileResponse(template_path, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取缩略图失败: {str(e)}")

@app.post("/api/templates/mkdir")
async def create_template_folder(data: dict = Body(...)):
    project_path = data.get("project_path")
    parent_path = data.get("parent_path", "")
    folder_name = data.get("folder_name", "").strip()

    if not project_path or not folder_name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")

    target_dir = os.path.join(project_path, "templates", parent_path, folder_name)
    if os.path.exists(target_dir):
        raise HTTPException(status_code=400, detail="文件夹已存在")

    try:
        os.makedirs(target_dir, exist_ok=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建文件夹失败: {str(e)}")


@app.get("/api/regions")
async def get_regions(project_path: str):
    file_path = os.path.join(project_path, REGIONS_FILE_PATH)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@app.post("/api/regions")
async def save_region(data: dict = Body(...)):
    project_path = data.get("project_path")
    template_name = data.get("template_name") or data.get("relative_path")
    crop_rect = data.get("crop_rect") or data.get("region")

    if not project_path or not template_name or crop_rect is None:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    clean_name = re.sub(r'\.png$', '', template_name, flags=re.IGNORECASE).replace("\\", "/")
    file_name_only = os.path.basename(clean_name)
    file_path = os.path.join(project_path, REGIONS_FILE_PATH)

    regions = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                regions = json.load(f)
        except Exception:
            regions = {}

    regions[clean_name] = crop_rect
    regions[file_name_only] = crop_rect

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(regions, f, ensure_ascii=False, indent=2)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存区域信息失败: {str(e)}")


@app.get("/api/windows")
async def get_windows():
    windows = []
    seen_titles = set()

    IGNORE_TITLES = {
        "Program Manager",
        "Windows 输入体验",
        "Windows Input Experience",
        "新通知",
        "通知中心",
        "设置",
        "Settings"
    }

    def callback(hwnd, extra):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()
        if not title or title in IGNORE_TITLES:
            return

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if (ex_style & win32con.WS_EX_TOOLWINDOW) and not (ex_style & win32con.WS_EX_APPWINDOW):
            return

        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]

            if w < 100 or h < 100 or rect[2] <= 0 or rect[3] <= 0:
                return

            client_rect = win32gui.GetClientRect(hwnd)
            client_w = client_rect[2] - client_rect[0]
            client_h = client_rect[3] - client_rect[1]
            if client_w <= 0 or client_h <= 0:
                return

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            if title in seen_titles:
                return
            seen_titles.add(title)

            windows.append({
                "hwnd": hwnd,
                "title": title,
                "process_id": pid,
                "class_name": win32gui.GetClassName(hwnd)
            })
        except Exception:
            pass

    win32gui.EnumWindows(callback, None)
    return {"windows": windows}


@app.post("/api/context")
async def save_context(request: dict):
    project_path = request.get("project_path")
    context = request.get("context")
    if not project_path or context is None:
        raise HTTPException(status_code=400, detail="缺少必要参数")

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

    context_path = os.path.join(project_path, CONTEXT_FILE)
    with open(context_path, "w", encoding="utf-8") as f:
        json.dump(mapped_context, f, indent=2, ensure_ascii=False)
    return {"status": "success"}


@app.get("/api/context")
async def get_context(project_path: str):
    context_path = os.path.join(project_path, CONTEXT_FILE)
    if not os.path.exists(context_path):
        return {}

    with open(context_path, "r", encoding="utf-8") as f:
        data = json.load(f)

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

@app.post("/api/ocr/test")
async def test_ocr_recognition(data: dict = Body(...)):
    """实时响应测试接口：支持灰度二值化阈值调优，实时返回渲染图与抓取文字"""
    project_path = data.get("project_path")
    region_value = data.get("region_value", [0, 0, 0, 0])
    gray_scale = data.get("gray_scale", True)
    gray_threshold = data.get("gray_threshold", 127)

    if len(region_value) == 4 and region_value[2] > 0 and region_value[3] > 0:
        x, y, w, h = region_value
        context_path = os.path.join(project_path, CONTEXT_FILE) if project_path else None
        if context_path and os.path.exists(context_path):
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    ctx = json.load(f)
                window_title = ctx.get("window_title")
                if window_title:
                    hwnd = win32gui.FindWindow(None, window_title)
                    if hwnd:
                        client_rect = win32gui.GetClientRect(hwnd)
                        wx, wy = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
                        x += wx + ctx.get("offset_left", 0)
                        y += wy + ctx.get("offset_top", 0)
            except Exception:
                pass
        region_rect = (int(x), int(y), int(w), int(h))
    else:
        screen_w, screen_h = pyautogui.size()
        region_rect = (0, 0, screen_w, screen_h)

    try:
        import cv2
        import numpy as np
        import base64
        from core.node_executors.base.ocr_recognition import get_ocr_engine

        engine_type, ocr_engine = get_ocr_engine()

        screenshot = pyautogui.screenshot(region=region_rect)
        frame_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # 二值化/灰度化处理
        if gray_scale:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            # 应用二值化阈值点
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = frame_bgr

        detected_text = ""
        if engine_type == "ddddocr" and ocr_engine:
            _, img_bytes = cv2.imencode('.png', processed_img)
            raw_res = ocr_engine.classification(img_bytes.tobytes())
            detected_text = str(raw_res).strip() if raw_res else ""
        else:
            detected_text = "未激活识别库"

        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        return {
            "status": "success",
            "text": detected_text,
            "region": region_rect,
            "image": img_b64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"实时测试失败: {str(e)}")


@app.post("/api/image/test")
async def test_image_recognition(data: dict = Body(...)):
    """单张模板图片灰度/二值化效果实时预览接口"""
    project_path = data.get("project_path")
    template_name = data.get("template_name")
    gray_scale = data.get("gray_scale", True)
    gray_threshold = data.get("gray_threshold", 127)

    if not project_path or not template_name:
        return {"status": "empty", "image": ""}

    # 安全定位模板图片路径
    clean_name = re.sub(r'\.png$', '', template_name, flags=re.IGNORECASE).replace("\\", "/")
    template_path = os.path.join(project_path, "templates", f"{clean_name}.png")

    if not os.path.exists(template_path):
        file_name_only = os.path.basename(clean_name)
        template_path = os.path.join(project_path, "templates", f"{file_name_only}.png")
        if not os.path.exists(template_path):
            return {"status": "not_found", "image": ""}

    try:
        import cv2
        import numpy as np
        import base64

        # 读取单张模板图
        template_bgr = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template_bgr is None:
            return {"status": "read_error", "image": ""}

        # 如果开启了灰度/二值化处理
        if gray_scale:
            gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
            processed_img = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        else:
            processed_img = template_bgr

        # 转为 Base64 传回前端
        _, buffer = cv2.imencode('.png', processed_img)
        img_b64 = "data:image/png;base64," + base64.b64encode(buffer).decode('utf-8')

        return {
            "status": "success",
            "image": img_b64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模板灰度预览生成失败: {str(e)}")

@app.get("/api/blueprint")
async def get_full_blueprint(project_path: str):
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")
    return load_blueprint(project_path)


class SaveBlueprintRequest(BaseModel):
    project_path: str
    blueprint_data: dict


@app.post("/api/blueprint/save")
async def save_full_blueprint(request: SaveBlueprintRequest):
    project_path = request.project_path
    blueprint_data = request.blueprint_data
    if not project_path or not blueprint_data:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目路径不存在")

    try:
        # 直接整体写入 project_blueprint.json 大文件，彻底解决多任务组节点割裂问题
        save_blueprint(project_path, blueprint_data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存蓝图失败: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)