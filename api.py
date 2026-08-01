# api.py
import os
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

import core.node_executors  # 必须存在，触发节点注册

from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.executor import GraphExecutor

# ---------- 初始化 ----------
app = FastAPI(title="节点自动化后端", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 全局常量 ----------
CONTEXT_FILE = "context.json"
REGIONS_FILE_PATH = os.path.join("templates", "regions.json")

# ---------- 执行状态限制存储（容量上限 100 预防内存泄漏） ----------
MAX_LOG_ENTRIES = 100
execution_status = OrderedDict()
execution_logs = OrderedDict()


def record_execution(execution_id, status_data, logs_data):
    if len(execution_status) >= MAX_LOG_ENTRIES:
        execution_status.popitem(last=False)
        execution_logs.popitem(last=False)
    execution_status[execution_id] = status_data
    execution_logs[execution_id] = logs_data


# ---------- 请求模型 ----------
class RunRequest(BaseModel):
    project_path: str
    task_id: str
    start_node_id: Optional[str] = None


class SaveTaskRequest(BaseModel):
    project_path: str
    task_data: dict


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


@app.get("/api/tasks/{task_id}/nodes")
async def get_task_nodes(task_id: str, project_path: str):
    """获取指定任务的节点列表（专门供前端节点下拉选择框使用）"""
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

    for filename in os.listdir(tasks_dir):
        if filename.endswith(".json"):
            with open(os.path.join(tasks_dir, filename), "r", encoding="utf-8") as f:
                existing = json.load(f)
                if existing.get("task_name") == task_name:
                    raise HTTPException(status_code=400, detail="任务名称已存在")

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
    """启动任务执行（后台包含预热与控制台格式化日志）"""
    project_path = request.project_path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="项目不存在")

    context_path = os.path.join(project_path, CONTEXT_FILE)
    saved_context = {}
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            saved_context = json.load(f)

    try:
        project = load_project(project_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载项目失败: {str(e)}")

    execution_id = f"{request.task_id}_{int(time.time() * 1000)}"
    record_execution(execution_id, {"status": "running", "message": "执行中..."}, [])

    def execute_background():
        from io import StringIO

        log_stream = StringIO()
        stream_handler = logging.StreamHandler(log_stream)
        console_handler = logging.StreamHandler()

        formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%H:%M:%S')
        stream_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(stream_handler)
        root_logger.addHandler(console_handler)

        original_failsafe = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False

        print("\n" + "=" * 70)
        print(f"🎬 [Easycode 运行引擎] 开始执行任务 ID: {request.task_id}")
        print("=" * 70)

        try:
            executor = GraphExecutor(
                project,
                project_dir=project_path,
                text_log_enabled=True,
                image_log_enabled=True,
                initial_context=saved_context
            )
            executor.run(request.task_id, request.start_node_id)
            execution_status[execution_id] = {"status": "success", "message": "执行完成"}
            print("=" * 70 + "\n")
        except Exception as e:
            execution_status[execution_id] = {"status": "error", "message": str(e)}
            print(f"💥 [执行失败]: {e}\n" + "=" * 70 + "\n")
        finally:
            logs = log_stream.getvalue()
            execution_logs[execution_id] = logs.splitlines() if logs else ["（无日志）"]
            pyautogui.FAILSAFE = original_failsafe
            root_logger.removeHandler(stream_handler)
            root_logger.removeHandler(console_handler)

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


# ==================== 截图工具与区域绑定 API ====================

@app.get("/api/screenshot/full")
async def get_full_screenshot(project_path: str = ""):
    """自动根据 Context 截取精准的工作区域大图（支持窗口/模拟器与裁剪）"""
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
                        h = (bottom - top) - off_top - off_bottom

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
    """保存裁剪后的模板图片，并将坐标记录到 templates/regions.json"""
    project_path = data.get("project_path")
    template_name = data.get("template_name")  # 例如 "EnterPage/test" 或 "test"
    crop_rect = data.get("crop_rect")  # [x, y, w, h]

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

        # 写入 templates/regions.json
        regions_json_path = os.path.join(project_path, REGIONS_FILE_PATH)
        regions_data = {}
        if os.path.exists(regions_json_path):
            try:
                with open(regions_json_path, "r", encoding="utf-8") as f:
                    regions_data = json.load(f)
            except Exception:
                regions_data = {}

        # 存入相对路径标准 Key 映射，如 "EnterPage/test": [447, 85, 102, 96]
        regions_data[clean_key] = crop_rect

        with open(regions_json_path, "w", encoding="utf-8") as f:
            json.dump(regions_data, f, ensure_ascii=False, indent=2)

        return {"status": "success", "file_path": save_path, "key": clean_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存模板图片失败: {str(e)}")


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


# ==================== 模板目录树、创建与预览 (供 FileBrowser 组件调用) ====================

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
async def create_template_folder(data: dict = Body(...)):
    """在 templates 的指定层级下新建文件夹"""
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


# ==================== 区域配置 (templates/regions.json 读写) ====================

@app.get("/api/regions")
async def get_regions(project_path: str):
    """获取 templates/regions.json 的内容"""
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
    """保存/更新图片的区域坐标到 templates/regions.json"""
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

    # 完整相对路径与纯文件名都保存一份
    regions[clean_name] = crop_rect
    regions[file_name_only] = crop_rect

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(regions, f, ensure_ascii=False, indent=2)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存区域信息失败: {str(e)}")


# ==================== 系统窗口与上下文控制 ====================

# api.py 中的 get_windows 接口替换

@app.get("/api/windows")
async def get_windows():
    """获取当前所有真正可见且有效的游戏/应用窗口（严格过滤后台系统幽灵窗口）"""
    windows = []
    seen_titles = set()

    # 系统内置的黑名单标题 & 挂起应用类名
    IGNORE_TITLES = {
        "Program Manager",
        "Windows 输入体验",
        "Windows Input Experience",
        "新通知",
        "通知中心",
        "设置",
        "Settings"
    }

    IGNORE_CLASSES = {
        "Windows.UI.Core.CoreWindow",
        "ApplicationFrameWindow",  # 当内部无实际画面时需要过滤
        "ToolGlobeTopMost"
    }

    def callback(hwnd, extra):
        # 1. 基本可见性检查
        if not win32gui.IsWindowVisible(hwnd):
            return

        # 2. 标题检查
        title = win32gui.GetWindowText(hwnd).strip()
        if not title or title in IGNORE_TITLES:
            return

        # 3. 样式扩展位检查 (过滤 TOOLWINDOW，保留任务栏主应用)
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)

        # 如果是工具窗口 (ToolWindow) 且不是显式主应用窗口 (AppWindow)，跳过
        if (ex_style & win32con.WS_EX_TOOLWINDOW) and not (ex_style & win32con.WS_EX_APPWINDOW):
            return

        # 4. 几何坐标与尺寸检查 (过滤隐藏在角落或宽高小于 100x100 的窗口)
        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]

            # 过滤过小或负坐标的不可见悬浮窗口
            if w < 100 or h < 100 or rect[2] <= 0 or rect[3] <= 0:
                return

            # 5. 客户区像素有效性检查
            client_rect = win32gui.GetClientRect(hwnd)
            client_w = client_rect[2] - client_rect[0]
            client_h = client_rect[3] - client_rect[1]
            if client_w <= 0 or client_h <= 0:
                return

            # 6. 进程名称安全检测 (过滤 Setting / ActionCenter 等系统隐藏进程)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # 7. 标题去重
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
    """获取项目的工作面板上下文"""
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)