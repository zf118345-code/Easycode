import sys
import os
import json
import tkinter as tk
import time
import re
from tkinter import messagebox, filedialog
import customtkinter as ctk
import pyautogui
import win32gui
import win32con
from PIL import Image, ImageTk
from core.models import Project, Task, Node, Jump
from core.utils import resource_path
from core.node_executors import *
from core.project_loader import load_project
from core.params import ALL_PARAMS

# ---------- 安全取值辅助函数 ----------
def safe_int(s, default=0):
    try:
        if s is None or s.strip() == "":
            return default
        return int(float(s.strip()))
    except:
        return default

def safe_float(s, default=0.0):
    try:
        if s is None or s.strip() == "":
            return default
        return float(s.strip())
    except:
        return default

# ---------- 辅助函数：创建带微调的输入框 ----------
def create_spinbox(parent, initial_value, min_val=None, max_val=None, step=1, width=50, callback=None):
    frame = ctk.CTkFrame(parent)
    frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

    var = tk.StringVar(value=str(initial_value))
    entry = ctk.CTkEntry(frame, textvariable=var, width=width)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def adjust(delta):
        try:
            val = safe_int(var.get(), initial_value) + delta
            if min_val is not None and val < min_val:
                val = min_val
            if max_val is not None and val > max_val:
                val = max_val
            var.set(str(val))
            if callback:
                callback()
        except:
            pass

    btn_up = ctk.CTkButton(frame, text="▲", width=20, height=20, command=lambda: adjust(step))
    btn_up.pack(side=tk.LEFT, padx=1)
    btn_down = ctk.CTkButton(frame, text="▼", width=20, height=20, command=lambda: adjust(-step))
    btn_down.pack(side=tk.LEFT, padx=1)

    def apply(event=None):
        try:
            val = safe_int(var.get(), initial_value)
            if min_val is not None and val < min_val:
                val = min_val
            if max_val is not None and val > max_val:
                val = max_val
            var.set(str(val))
            if callback:
                callback()
        except:
            var.set(str(initial_value))

    entry.bind("<FocusOut>", apply)
    entry.bind("<Return>", apply)

    return frame, var, entry


# ---------- 辅助函数：获取相对路径 ----------
def get_relative_template_path(project_path, abs_path):
    """
    将绝对路径转换为相对于项目 templates 目录的路径
    返回路径字符串（不含 .png 扩展名），例如 "subdir/icon"
    如果 abs_path 不在项目 templates 下，则仅返回文件名（不含扩展名）
    """
    templates_dir = os.path.join(project_path, "templates")
    # 统一转为绝对路径并规范化
    abs_path = os.path.abspath(abs_path)
    templates_dir = os.path.abspath(templates_dir)
    if abs_path.startswith(templates_dir):
        rel = os.path.relpath(abs_path, templates_dir)
        # 移除扩展名
        base, ext = os.path.splitext(rel)
        # 将反斜杠转为正斜杠（跨平台）
        return base.replace("\\", "/")
    else:
        # 如果不在项目内，仅返回文件名（不含扩展名）
        base = os.path.basename(abs_path)
        base, ext = os.path.splitext(base)
        return base


# ---------- 主UI窗口 ----------
class MainUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("节点自动化 - 可视化编辑器")
        self.geometry("1400x900")
        self.minsize(1200, 700)

        self.project = None
        self.current_task_id = None
        self.current_task = None
        self._saving = False
        self.current_project_path = None
        self.template_regions = {}  # {relative_path: [x, y, w, h]}

        # ---- 项目管理栏（顶部） ----
        self.top_frame = ctk.CTkFrame(self, height=40)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        ctk.CTkLabel(self.top_frame, text="项目:", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.project_combo = ctk.CTkComboBox(self.top_frame, values=self._get_project_list(), command=self.switch_project, width=200)
        self.project_combo.pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(self.top_frame, text="新建项目", command=self.new_project, width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(self.top_frame, text="刷新项目列表", command=self.refresh_project_list, width=100).pack(side=tk.LEFT, padx=5)

        # ---- 主体布局 ----
        self.left_frame = ctk.CTkFrame(self, width=320)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=10, pady=10)
        self.left_frame.pack_propagate(False)

        # 任务管理区域
        self.task_frame = ctk.CTkFrame(self.left_frame)
        self.task_frame.pack(fill=tk.X, pady=5)

        ctk.CTkLabel(self.task_frame, text="任务管理", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=5)
        self.task_var = ctk.StringVar()
        self.task_combo = ctk.CTkComboBox(self.task_frame, variable=self.task_var,
                                          values=[], command=self.on_task_selected, width=150)
        self.task_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.btn_new_task = ctk.CTkButton(self.task_frame, text="+", command=self.new_task, width=30)
        self.btn_new_task.pack(side=tk.LEFT, padx=2)
        self.btn_save_task = ctk.CTkButton(self.task_frame, text="💾", command=self.save_task, width=30)
        self.btn_save_task.pack(side=tk.LEFT, padx=2)

        # 节点列表（支持拖拽排序）
        ctk.CTkLabel(self.left_frame, text="节点列表（拖动可排序）", font=("Arial", 14, "bold")).pack(pady=(10,5))
        self.node_listbox = tk.Listbox(self.left_frame, font=("Consolas", 10), height=20, selectmode=tk.SINGLE)
        self.node_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.node_listbox.bind("<<ListboxSelect>>", self.on_node_selected)
        self.node_listbox.bind("<Delete>", self.delete_selected_node)
        self.drag_start_index = None
        self.node_listbox.bind("<ButtonPress-1>", self.on_listbox_press)
        self.node_listbox.bind("<B1-Motion>", self.on_listbox_drag)
        self.node_listbox.bind("<ButtonRelease-1>", self.on_listbox_release)

        # 节点添加按钮
        add_frame = ctk.CTkFrame(self.left_frame)
        add_frame.pack(fill=tk.X, pady=5)
        self.btn_add_node = ctk.CTkButton(add_frame, text="添加节点", command=self.add_node_dialog, width=100)
        self.btn_add_node.pack(side=tk.LEFT, padx=5)
        self.btn_delete_node = ctk.CTkButton(add_frame, text="删除选中", command=self.delete_selected_node, width=100)
        self.btn_delete_node.pack(side=tk.LEFT, padx=5)

        # 右侧区域：节点编辑 + 截图工具
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.edit_frame = ctk.CTkFrame(self.right_frame)
        self.edit_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        ctk.CTkLabel(self.edit_frame, text="节点编辑", font=("Arial", 16, "bold")).pack(pady=5)
        self.edit_scroll = ctk.CTkScrollableFrame(self.edit_frame)
        self.edit_scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 截图工具区
        self.screenshot_toggle = ctk.CTkButton(self.right_frame, text="▼ 截图工具", command=self.toggle_screenshot)
        self.screenshot_toggle.pack(fill=tk.X, pady=2)

        self.screenshot_frame = ctk.CTkFrame(self.right_frame)
        self.screenshot_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.screenshot_frame.pack_propagate(False)
        self.screenshot_frame.configure(height=400)

        self.screenshot_panel = ScreenshotPanel(self.screenshot_frame, parent_ui=self)
        self.screenshot_panel.pack(fill=tk.BOTH, expand=True)

        # 加载默认项目（如果有demo则自动加载，否则空）
        self.load_default_project()

    # ---------- 项目管理 ----------
    def _get_project_list(self):
        projects_dir = "projects"
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)
        return [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]

    def refresh_project_list(self):
        self.project_combo.configure(values=self._get_project_list())

    def load_default_project(self):
        projects = self._get_project_list()
        if "demo" in projects:
            self.current_project_path = os.path.join("projects", "demo")
            self.project_combo.set("demo")
            self._load_current_project()
        elif projects:
            self.current_project_path = os.path.join("projects", projects[0])
            self.project_combo.set(projects[0])
            self._load_current_project()
        else:
            self.new_project("demo")

    def switch_project(self, project_name):
        if self._saving:
            return
        if self.current_project_path:
            self.save_task()
        self.current_project_path = os.path.join("projects", project_name)
        self._load_current_project()

    def _load_current_project(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            return
        try:
            self.project = load_project(self.current_project_path)
            self._load_template_regions()
            self.screenshot_panel.current_project_path = self.current_project_path
            self.refresh_task_list()
            if self.project.tasks:
                self.task_combo.set(list(self.project.tasks.keys())[0])
                self.current_task_id = list(self.project.tasks.keys())[0]
                self.current_task = self.project.tasks[self.current_task_id]
                self.refresh_node_list()
            else:
                self.task_combo.set("")
                self.current_task = None
                self.refresh_node_list()
        except Exception as e:
            messagebox.showerror("加载项目失败", str(e))

    def _load_template_regions(self):
        self.template_regions = {}
        if not self.current_project_path:
            return
        regions_path = os.path.join(self.current_project_path, "templates", "regions.json")
        if os.path.exists(regions_path):
            try:
                with open(regions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) == 4:
                            self.template_regions[k] = v
            except:
                pass

    def _save_template_regions(self):
        if not self.current_project_path:
            return
        regions_path = os.path.join(self.current_project_path, "templates", "regions.json")
        os.makedirs(os.path.dirname(regions_path), exist_ok=True)
        with open(regions_path, "w", encoding="utf-8") as f:
            json.dump(self.template_regions, f, indent=2, ensure_ascii=False)

    def new_project(self, name=None):
        if name is None:
            name = ctk.CTkInputDialog(text="请输入新项目名称（英文）:", title="新建项目").get_input()
            if not name:
                return
        project_dir = os.path.join("projects", name)
        if os.path.exists(project_dir):
            messagebox.showerror("错误", "项目已存在")
            return
        os.makedirs(project_dir)
        os.makedirs(os.path.join(project_dir, "tasks"))
        os.makedirs(os.path.join(project_dir, "templates"))
        with open(os.path.join(project_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"project_name": name, "variables": {}, "default_threshold": 0.85, "default_timeout": 3000}, f, indent=2)
        self.refresh_project_list()
        self.project_combo.set(name)
        self.current_project_path = project_dir
        self._load_current_project()
        messagebox.showinfo("成功", f"项目 {name} 已创建")

    # ---------- 任务管理 ----------
    def refresh_task_list(self):
        tasks = list(self.project.tasks.keys()) if self.project else []
        self.task_combo.configure(values=tasks)
        if tasks and self.current_task_id not in tasks:
            self.task_combo.set(tasks[0])
            self.current_task_id = tasks[0]
            self.current_task = self.project.tasks[self.current_task_id]
            self.refresh_node_list()

    def on_task_selected(self, choice):
        if self._saving:
            return
        self.save_current_node_if_needed()
        self.current_task_id = choice
        self.current_task = self.project.tasks[choice] if choice in self.project.tasks else None
        self.refresh_node_list()

    def new_task(self):
        name = ctk.CTkInputDialog(text="请输入新任务ID (英文):", title="新建任务").get_input()
        if not name:
            return
        if name in self.project.tasks:
            messagebox.showerror("错误", "任务ID已存在")
            return
        task = Task(task_id=name, task_name=name, nodes=[])
        self.project.tasks[name] = task
        self.refresh_task_list()
        self.task_combo.set(name)
        self.current_task_id = name
        self.current_task = task
        self.refresh_node_list()
        self.save_task()

    def save_task(self):
        if self._saving:
            return
        self._saving = True
        try:
            self.save_current_node_if_needed()
            if not self.current_task or not self.current_project_path:
                return
            tasks_dir = os.path.join(self.current_project_path, "tasks")
            os.makedirs(tasks_dir, exist_ok=True)
            task_data = {
                "task_id": self.current_task.task_id,
                "task_name": self.current_task.task_name,
                "description": self.current_task.description,
                "nodes": []
            }
            for node in self.current_task.nodes:
                defaults = Node.get_defaults(node.node_type)
                filtered_params = {}
                for k, v in node.params.items():
                    default_val = defaults.get(k)
                    if not self._is_default_value(v, default_val):
                        filtered_params[k] = v
                node_dict = {
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "params": filtered_params
                }
                if node.delay_before != 0:
                    node_dict["delay_before"] = node.delay_before
                if node.loop_count != 1:
                    node_dict["loop_count"] = node.loop_count
                if node.loop_interval != 0:
                    node_dict["loop_interval"] = node.loop_interval
                if not node.enabled:
                    node_dict["enabled"] = False
                if node.on_success and (node.on_success.type != "next" or node.on_success.target or node.on_success.target_node):
                    succ = {"type": node.on_success.type, "target": node.on_success.target}
                    if node.on_success.target_node:
                        succ["target_node"] = node.on_success.target_node
                    node_dict["on_success"] = succ
                if node.on_failure and (node.on_failure.type != "next" or node.on_failure.target or node.on_failure.target_node):
                    fail = {"type": node.on_failure.type, "target": node.on_failure.target}
                    if node.on_failure.target_node:
                        fail["target_node"] = node.on_failure.target_node
                    node_dict["on_failure"] = fail
                if node.position:
                    node_dict["position"] = node.position
                task_data["nodes"].append(node_dict)
            path = os.path.join(tasks_dir, f"{self.current_task_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)
        finally:
            self._saving = False

    def _is_default_value(self, value, default):
        if isinstance(value, dict) and isinstance(default, dict):
            if set(value.keys()) != set(default.keys()):
                return False
            for k in value:
                if not self._is_default_value(value[k], default.get(k)):
                    return False
            return True
        return value == default

    # ---------- 节点管理 ----------
    def save_current_node_if_needed(self):
        if hasattr(self, 'current_edit_node') and self.current_edit_node:
            self.save_node_editor(show_msg=False)

    def refresh_node_list(self, keep_selection=False):
        selected_id = None
        if keep_selection:
            selection = self.node_listbox.curselection()
            if selection:
                idx = selection[0]
                if 0 <= idx < len(self.current_task.nodes):
                    selected_id = self.current_task.nodes[idx].node_id
        self.node_listbox.delete(0, tk.END)
        if not self.current_task:
            return
        for i, node in enumerate(self.current_task.nodes):
            display = f"[{i+1}] {node.node_id} ({node.node_type})"
            self.node_listbox.insert(tk.END, display)
        if keep_selection and selected_id:
            for i, node in enumerate(self.current_task.nodes):
                if node.node_id == selected_id:
                    self.node_listbox.selection_set(i)
                    self.node_listbox.see(i)
                    break

    def on_node_selected(self, event):
        if self._saving:
            return
        self.save_current_node_if_needed()
        selection = self.node_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.current_edit_index = idx
        node = self.current_task.nodes[idx]
        self.display_node_editor(node)

    def display_node_editor(self, node):
        for widget in self.edit_scroll.winfo_children():
            widget.destroy()

        row = 0
        id_frame = ctk.CTkFrame(self.edit_scroll)
        id_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
        ctk.CTkLabel(id_frame, text="节点 ID:", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.node_id_var = tk.StringVar(value=node.node_id)
        id_entry = ctk.CTkEntry(id_frame, textvariable=self.node_id_var, width=150)
        id_entry.pack(side=tk.LEFT, padx=5)
        id_entry.bind("<FocusOut>", lambda e: self.update_node_id(node))
        id_entry.bind("<Return>", lambda e: self.update_node_id(node))
        row += 1

        ctk.CTkLabel(self.edit_scroll, text=f"类型: {node.node_type}").grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1

        self.create_int_entry(self.edit_scroll, row, "延迟(ms):", "delay_before", node.delay_before, 0, 10000)
        row += 1
        self.create_int_entry(self.edit_scroll, row, "循环次数:", "loop_count", node.loop_count, -1, 999)
        row += 1
        self.create_int_entry(self.edit_scroll, row, "循环间隔(ms):", "loop_interval", node.loop_interval, 0, 10000)
        row += 1

        self.create_jump_entry(self.edit_scroll, row, "成功跳转:", "on_success", node.on_success)
        row += 1
        self.create_jump_entry(self.edit_scroll, row, "失败跳转:", "on_failure", node.on_failure)
        row += 1

        param_defs = ALL_PARAMS.get(node.node_type, {}).get("params", {})
        if param_defs:
            ctk.CTkLabel(self.edit_scroll, text="--- 参数配置 ---", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
            row += 1
            self.current_param_entries = {}
            for param_name, config in param_defs.items():
                default_val = Node.get_defaults(node.node_type).get(param_name)
                current_val = node.params.get(param_name, default_val)
                self.create_param_entry(self.edit_scroll, row, param_name, config, current_val, node, default_val)
                row += 1

        self.current_edit_node = node

    def update_node_id(self, node):
        new_id = self.node_id_var.get().strip()
        if not new_id:
            messagebox.showwarning("提示", "节点ID不能为空")
            self.node_id_var.set(node.node_id)
            return
        if new_id != node.node_id:
            if any(n.node_id == new_id for n in self.current_task.nodes if n is not node):
                messagebox.showerror("错误", f"节点ID '{new_id}' 已存在")
                self.node_id_var.set(node.node_id)
                return
            old_id = node.node_id
            node.node_id = new_id
            for n in self.current_task.nodes:
                if n.on_success and n.on_success.target == old_id:
                    n.on_success.target = new_id
                if n.on_failure and n.on_failure.target == old_id:
                    n.on_failure.target = new_id
            self.refresh_node_list(keep_selection=True)
            self.save_task()

    def create_int_entry(self, parent, row, label, attr_name, value, min_val, max_val):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="e", padx=5)
        var = tk.StringVar(value=str(value))
        entry = ctk.CTkEntry(parent, textvariable=var, width=80)
        entry.grid(row=row, column=1, sticky="w", padx=5)
        def apply(event=None):
            val = safe_int(var.get(), value)
            if min_val is not None and val < min_val:
                val = min_val
            if max_val is not None and val > max_val:
                val = max_val
            var.set(str(val))
        entry.bind("<FocusOut>", apply)
        entry.bind("<Return>", apply)
        setattr(self, f"_edit_{attr_name}", (var, min_val, max_val, value))

    def create_jump_entry(self, parent, row, label, attr_name, jump_obj):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="e", padx=5)
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=1, sticky="w", padx=5)

        type_var = tk.StringVar(value=jump_obj.type if jump_obj else "next")
        target_var = tk.StringVar(value=jump_obj.target if jump_obj else "")
        target_node_var = tk.StringVar(value=jump_obj.target_node if jump_obj else "")
        return_var = tk.BooleanVar(value=jump_obj.return_on_complete if jump_obj else False)

        type_menu = ctk.CTkOptionMenu(frame, values=["next", "node", "task", "end", "error"],
                                      variable=type_var, width=80,
                                      command=lambda v: self._update_jump_target(target_container, v, target_var, target_node_var))
        type_menu.pack(side=tk.LEFT, padx=2)

        target_container = ctk.CTkFrame(frame)
        target_container.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        self._update_jump_target(target_container, type_var.get(), target_var, target_node_var)

        ctk.CTkLabel(frame, text="返回").pack(side=tk.LEFT, padx=2)
        ctk.CTkCheckBox(frame, variable=return_var, text="").pack(side=tk.LEFT, padx=2)

        setattr(self, f"_edit_{attr_name}", (type_var, target_var, target_node_var, return_var, target_container))

    def _update_jump_target(self, container, jump_type, target_var, target_node_var):
        for widget in container.winfo_children():
            widget.destroy()

        if jump_type in ("next", "end", "error"):
            ctk.CTkLabel(container, text="(无)").pack(side=tk.LEFT)
            target_var.set("")
            target_node_var.set("")
        elif jump_type == "node":
            if self.current_task:
                node_ids = [n.node_id for n in self.current_task.nodes]
                if node_ids:
                    ctk.CTkOptionMenu(container, values=node_ids, variable=target_var, width=120).pack(side=tk.LEFT)
                else:
                    ctk.CTkEntry(container, textvariable=target_var, width=100).pack(side=tk.LEFT)
            else:
                ctk.CTkEntry(container, textvariable=target_var, width=100).pack(side=tk.LEFT)
            target_node_var.set("")
        elif jump_type == "task":
            sub_frame = ctk.CTkFrame(container)
            sub_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            task_menu = ctk.CTkOptionMenu(sub_frame, values=[], variable=target_var, width=120)
            task_menu.pack(side=tk.LEFT, padx=2)

            node_menu = ctk.CTkOptionMenu(sub_frame, values=[], variable=target_node_var, width=120)
            node_menu.pack(side=tk.LEFT, padx=2)

            if self.project:
                task_ids = list(self.project.tasks.keys())
                task_menu.configure(values=task_ids)
                if task_ids:
                    target_var.set(task_ids[0])
                    self._update_task_node_menu(node_menu, task_ids[0])
                else:
                    target_var.set("")
                    node_menu.configure(values=[])
            else:
                target_var.set("")
                node_menu.configure(values=[])

            def on_task_select(choice):
                self._update_task_node_menu(node_menu, choice)
            task_menu.configure(command=on_task_select)

    def _update_task_node_menu(self, node_menu, task_id):
        if self.project and task_id in self.project.tasks:
            nodes = self.project.tasks[task_id].nodes
            node_ids = [n.node_id for n in nodes]
            node_menu.configure(values=node_ids)
            if node_ids:
                node_menu.set(node_ids[0])
            else:
                node_menu.set("")
        else:
            node_menu.configure(values=[])

    # ---------- 创建参数输入 ----------
    def create_param_entry(self, parent, row, param_name, config, value, node, default_val):
        param_type = config.get("type")
        label = config.get("label", param_name)
        ctk.CTkLabel(parent, text=label + ":").grid(row=row, column=0, sticky="e", padx=5)

        # ---------- 辅助函数：可浏览的字符串输入（图片字段，支持相对路径） ----------
        def create_browsable_string_entry(container, var, is_image_field=False):
            entry = ctk.CTkEntry(container, textvariable=var, width=120)
            entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            if is_image_field:
                def browse():
                    if self.current_project_path:
                        init_dir = os.path.join(self.current_project_path, "templates")
                    else:
                        init_dir = resource_path("templates")
                    if not os.path.exists(init_dir):
                        os.makedirs(init_dir)
                    file_path = filedialog.askopenfilename(
                        title="选择模板图片",
                        initialdir=init_dir,
                        filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
                    )
                    if file_path:
                        # 使用辅助函数计算相对路径
                        rel_path = get_relative_template_path(self.current_project_path, file_path)
                        var.set(rel_path)

                entry.bind("<Button-1>", lambda e: browse())
                btn = ctk.CTkButton(container, text="📂 浏览", width=60, command=browse)
                btn.pack(side=tk.LEFT, padx=2)
            return entry

        # ---------- 根据类型生成控件 ----------
        if param_type == "str":
            frame = ctk.CTkFrame(parent)
            frame.grid(row=row, column=1, sticky="w", padx=5)
            var = tk.StringVar(value=value if value is not None else "")
            is_image = param_name in ["data", "template"]
            create_browsable_string_entry(frame, var, is_image)
            setattr(self, f"_edit_param_{param_name}", (var, default_val))

        elif param_type == "int":
            frame = ctk.CTkFrame(parent)
            frame.grid(row=row, column=1, sticky="w", padx=5)
            var = tk.StringVar(value=str(value) if value is not None else str(default_val))
            entry = ctk.CTkEntry(frame, textvariable=var, width=80)
            entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            def apply_int(event=None):
                val = safe_int(var.get(), default_val)
                if config.get("min") is not None and val < config["min"]:
                    val = config["min"]
                if config.get("max") is not None and val > config["max"]:
                    val = config["max"]
                var.set(str(val))
            entry.bind("<FocusOut>", apply_int)
            entry.bind("<Return>", apply_int)
            setattr(self, f"_edit_param_{param_name}", (var, default_val, config.get("min"), config.get("max")))

        elif param_type == "float":
            frame = ctk.CTkFrame(parent)
            frame.grid(row=row, column=1, sticky="w", padx=5)
            var = tk.StringVar(value=str(value) if value is not None else str(default_val))
            entry = ctk.CTkEntry(frame, textvariable=var, width=80)
            entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            def apply_float(event=None):
                val = safe_float(var.get(), default_val)
                if config.get("min") is not None and val < config["min"]:
                    val = config["min"]
                if config.get("max") is not None and val > config["max"]:
                    val = config["max"]
                var.set(str(val))
            entry.bind("<FocusOut>", apply_float)
            entry.bind("<Return>", apply_float)
            setattr(self, f"_edit_param_{param_name}", (var, default_val, config.get("min"), config.get("max")))

        elif param_type == "bool":
            var = tk.BooleanVar(value=value if value is not None else False)
            cb = ctk.CTkCheckBox(parent, variable=var, text="")
            cb.grid(row=row, column=1, sticky="w", padx=5)
            setattr(self, f"_edit_param_{param_name}", (var, default_val))

        elif param_type == "select":
            options = config.get("options", [])
            var = tk.StringVar(value=value if value is not None else options[0])
            om = ctk.CTkOptionMenu(parent, values=options, variable=var, width=100)
            om.grid(row=row, column=1, sticky="w", padx=5)
            setattr(self, f"_edit_param_{param_name}", (var, default_val))

        elif param_type == "dict":
            sub_config = config.get("sub", {})
            frame = ctk.CTkFrame(parent)
            frame.grid(row=row, column=1, sticky="w", padx=5)
            sub_entries = {}

            # 特殊处理 region 参数：增加模板加载功能
            if param_name == "region":
                # 先处理各个子字段
                for sub_key, sub_conf in sub_config.items():
                    sub_val = value.get(sub_key, sub_conf.get("default")) if isinstance(value, dict) else sub_conf.get(
                        "default")
                    sub_default = sub_conf.get("default")
                    sub_type = sub_conf.get("type")

                    if sub_key == "type":
                        var = tk.StringVar(value=sub_val if sub_val is not None else sub_conf.get("options", [""])[0])
                        om = ctk.CTkOptionMenu(frame, values=sub_conf.get("options", []), variable=var, width=100)
                        om.pack(side=tk.LEFT, padx=2)
                        sub_entries[sub_key] = (var, sub_default)

                        # 绑定 type 变更事件，用于动态显示模板选择器和 value 控制
                        def on_region_type_change(*args):
                            self._update_region_template_visibility(frame, var, sub_entries)

                        var.trace("w", on_region_type_change)

                    elif sub_key == "value":
                        vals = sub_val if sub_val and len(sub_val) == 4 else [0, 0, 0, 0]
                        default_vals = sub_conf.get("default", [0, 0, 0, 0])
                        inner_frame = ctk.CTkFrame(frame)
                        inner_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
                        spin_vars = []
                        for i in range(4):
                            spin_frame, spin_var, spin_entry = create_spinbox(
                                inner_frame, vals[i], min_val=0, step=1, width=40, callback=None
                            )
                            spin_vars.append(spin_var)
                        # 存储 spin_vars 和 inner_frame 以便后续控制可见性
                        sub_entries[sub_key] = (spin_vars, default_vals, inner_frame)  # 新增 inner_frame

                    else:
                        if sub_type == "bool":
                            var = tk.BooleanVar(value=sub_val if sub_val is not None else False)
                            cb = ctk.CTkCheckBox(frame, variable=var, text="")
                            cb.pack(side=tk.LEFT, padx=2)
                            sub_entries[sub_key] = (var, sub_default)
                        elif sub_type == "str":
                            var = tk.StringVar(value=sub_val if sub_val is not None else "")
                            entry = ctk.CTkEntry(frame, textvariable=var, width=80)
                            entry.pack(side=tk.LEFT, padx=2)
                            sub_entries[sub_key] = (var, sub_default)

                # 添加模板选择下拉（在 type 为 recorded 时显示）
                self._create_template_selector(frame, sub_entries)

            else:
                # 常规 dict 处理
                for sub_key, sub_conf in sub_config.items():
                    sub_val = value.get(sub_key, sub_conf.get("default")) if isinstance(value, dict) else sub_conf.get("default")
                    sub_default = sub_conf.get("default")
                    sub_type = sub_conf.get("type")
                    if sub_type == "select":
                        var = tk.StringVar(value=sub_val if sub_val is not None else sub_conf.get("options", [""])[0])
                        om = ctk.CTkOptionMenu(frame, values=sub_conf.get("options", []), variable=var, width=70)
                        om.pack(side=tk.LEFT, padx=2)
                        sub_entries[sub_key] = (var, sub_default)
                    elif sub_type == "str":
                        is_image = sub_key in ["data", "template"]
                        inner_frame = ctk.CTkFrame(frame)
                        inner_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
                        var = tk.StringVar(value=sub_val if sub_val is not None else "")
                        create_browsable_string_entry(inner_frame, var, is_image)
                        sub_entries[sub_key] = (var, sub_default)
                    elif sub_type == "int":
                        inner_frame = ctk.CTkFrame(frame)
                        inner_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
                        var = tk.StringVar(value=str(sub_val) if sub_val is not None else str(sub_default))
                        entry = ctk.CTkEntry(inner_frame, textvariable=var, width=60)
                        entry.pack(side=tk.LEFT, padx=2)
                        def apply_sub_int(event=None, var=var, default=sub_default):
                            val = safe_int(var.get(), default)
                            var.set(str(val))
                        entry.bind("<FocusOut>", apply_sub_int)
                        entry.bind("<Return>", apply_sub_int)
                        sub_entries[sub_key] = (var, sub_default)
                    elif sub_type == "bool":
                        var = tk.BooleanVar(value=sub_val if sub_val is not None else False)
                        cb = ctk.CTkCheckBox(frame, variable=var, text="")
                        cb.pack(side=tk.LEFT, padx=2)
                        sub_entries[sub_key] = (var, sub_default)
                    elif sub_type == "list_int4":
                        vals = sub_val if sub_val and len(sub_val)==4 else [0,0,0,0]
                        default_vals = sub_conf.get("default", [0,0,0,0])
                        inner_frame = ctk.CTkFrame(frame)
                        inner_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
                        spin_vars = []
                        for i in range(4):
                            spin_frame, spin_var, spin_entry = create_spinbox(
                                inner_frame, vals[i], min_val=0, step=1, width=40, callback=None
                            )
                            spin_vars.append(spin_var)
                        sub_entries[sub_key] = (spin_vars, default_vals)
            setattr(self, f"_edit_param_{param_name}", sub_entries)

        elif param_type == "list_dict":
            frame = ctk.CTkFrame(parent)
            frame.grid(row=row, column=1, sticky="w", padx=5)

            var = tk.StringVar(value=json.dumps(value, ensure_ascii=False, indent=2) if value else "[]")
            textbox = ctk.CTkTextbox(frame, height=80, width=300)
            textbox.insert("1.0", var.get())
            textbox.pack(side=tk.LEFT, padx=2)
            setattr(self, f"_edit_param_{param_name}", (textbox, default_val))

            btn_add = ctk.CTkButton(frame, text="添加候选", width=80, command=lambda: self._add_candidate(textbox))
            btn_add.pack(side=tk.LEFT, padx=2)

    # ---------- 模板选择器（用于 region 参数） ----------
    def _create_template_selector(self, parent_frame, sub_entries):
        value_spins = None
        for key, data in sub_entries.items():
            if key == "value" and isinstance(data[0], list):
                value_spins = data[0]
                break
        if value_spins is None:
            return

        selector_frame = ctk.CTkFrame(parent_frame)
        selector_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        ctk.CTkLabel(selector_frame, text="模板:").pack(side=tk.LEFT, padx=2)
        template_var = tk.StringVar()
        template_combo = ctk.CTkOptionMenu(selector_frame, values=[], variable=template_var, width=120)
        template_combo.pack(side=tk.LEFT, padx=2)

        sub_entries["_template_selector"] = (template_var, template_combo)

        def refresh_template_list():
            if self.current_project_path:
                templates = list(self.template_regions.keys())
                template_combo.configure(values=templates)
                if templates:
                    template_var.set(templates[0])
                else:
                    template_var.set("")
            else:
                template_combo.configure(values=[])
                template_var.set("")

        def on_template_select(*args):
            selected = template_var.get()
            if selected and selected in self.template_regions:
                region = self.template_regions[selected]
                if len(region) == 4 and value_spins:
                    for i, val in enumerate(region):
                        value_spins[i].set(str(val))

        template_var.trace("w", on_template_select)

        self._template_selector_data = (template_var, template_combo, refresh_template_list)
        refresh_template_list()

        type_var = None
        for key, data in sub_entries.items():
            if key == "type" and isinstance(data[0], tk.StringVar):
                type_var = data[0]
                break
        if type_var:
            self._update_region_template_visibility(parent_frame, type_var, sub_entries)
            def on_type_change(*args):
                self._update_region_template_visibility(parent_frame, type_var, sub_entries)
            type_var.trace("w", on_type_change)

    def _update_region_template_visibility(self, parent_frame, type_var, sub_entries):
        # 获取 value 的 inner_frame 和 spin_vars
        value_frame = None
        for key, data in sub_entries.items():
            if key == "value" and len(data) >= 3:
                value_frame = data[2]  # 第三个元素是 inner_frame
                break

        # 查找模板选择器所在的框架（通过遍历子元素）
        selector_frame = None
        for child in parent_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame) and child.winfo_children():
                for sub_child in child.winfo_children():
                    if isinstance(sub_child, ctk.CTkLabel) and sub_child.cget("text") == "模板:":
                        selector_frame = child
                        break
                if selector_frame:
                    break

        current_type = type_var.get()
        if current_type == "fullwindow":
            # 隐藏 value 微调框和模板选择器
            if value_frame:
                value_frame.pack_forget()
            if selector_frame:
                selector_frame.pack_forget()
        elif current_type == "recorded":
            # 显示模板选择器，隐藏 value 微调框
            if value_frame:
                value_frame.pack_forget()
            if selector_frame:
                selector_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        elif current_type == "custom":
            # 显示 value 微调框，隐藏模板选择器
            if value_frame:
                value_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            if selector_frame:
                selector_frame.pack_forget()
        else:
            # 默认情况
            if value_frame:
                value_frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            if selector_frame:
                selector_frame.pack_forget()

    # ---------- 添加候选 ----------
    def _add_candidate(self, textbox):
        dialog = ctk.CTkToplevel(self)
        dialog.title("添加候选")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="模板名称:").pack(pady=5)
        template_var = tk.StringVar()
        template_entry = ctk.CTkEntry(dialog, textvariable=template_var, width=200)
        template_entry.pack(pady=5)

        ctk.CTkLabel(dialog, text="跳转目标节点:").pack(pady=5)
        target_var = tk.StringVar()
        if self.current_task:
            node_ids = [n.node_id for n in self.current_task.nodes]
            if node_ids:
                target_menu = ctk.CTkOptionMenu(dialog, values=node_ids, variable=target_var, width=200)
                target_menu.pack(pady=5)
            else:
                target_entry = ctk.CTkEntry(dialog, textvariable=target_var, width=200)
                target_entry.pack(pady=5)
        else:
            target_entry = ctk.CTkEntry(dialog, textvariable=target_var, width=200)
            target_entry.pack(pady=5)

        def confirm():
            template = template_var.get().strip()
            target = target_var.get().strip()
            if not template or not target:
                messagebox.showwarning("提示", "请输入模板和目标")
                return
            try:
                content = textbox.get("1.0", tk.END)
                candidates = json.loads(content) if content.strip() else []
            except:
                candidates = []
            candidates.append({"template": template, "target": target})
            textbox.delete("1.0", tk.END)
            textbox.insert("1.0", json.dumps(candidates, ensure_ascii=False, indent=2))
            dialog.destroy()

        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
        ctk.CTkButton(btn_frame, text="添加", command=confirm, fg_color="green").pack(side=tk.LEFT, padx=10)

    # ---------- 保存节点编辑器 ----------
    def save_node_editor(self, show_msg=True):
        if not hasattr(self, 'current_edit_node') or not self.current_edit_node:
            return
        node = self.current_edit_node
        defaults = Node.get_defaults(node.node_type)

        if hasattr(self, "_edit_delay_before"):
            var, min_v, max_v, default_val = self._edit_delay_before
            val = safe_int(var.get(), default_val)
            if min_v is not None and val < min_v:
                val = min_v
            if max_v is not None and val > max_v:
                val = max_v
            node.delay_before = val
        if hasattr(self, "_edit_loop_count"):
            var, min_v, max_v, default_val = self._edit_loop_count
            val = safe_int(var.get(), default_val)
            if min_v is not None and val < min_v:
                val = min_v
            if max_v is not None and val > max_v:
                val = max_v
            node.loop_count = val
        if hasattr(self, "_edit_loop_interval"):
            var, min_v, max_v, default_val = self._edit_loop_interval
            val = safe_int(var.get(), default_val)
            if min_v is not None and val < min_v:
                val = min_v
            if max_v is not None and val > max_v:
                val = max_v
            node.loop_interval = val

        if hasattr(self, "_edit_on_success"):
            type_var, target_var, target_node_var, return_var, container = self._edit_on_success
            node.on_success = Jump(type=type_var.get(), target=target_var.get(), target_node=target_node_var.get(), return_on_complete=return_var.get())
        if hasattr(self, "_edit_on_failure"):
            type_var, target_var, target_node_var, return_var, container = self._edit_on_failure
            node.on_failure = Jump(type=type_var.get(), target=target_var.get(), target_node=target_node_var.get(), return_on_complete=return_var.get())

        param_defs = ALL_PARAMS.get(node.node_type, {}).get("params", {})
        for param_name, config in param_defs.items():
            if not hasattr(self, f"_edit_param_{param_name}"):
                continue
            param_data = getattr(self, f"_edit_param_{param_name}")
            param_type = config.get("type")

            def get_default():
                return defaults.get(param_name)

            if param_type in ("int", "float", "str", "select", "bool"):
                var = param_data[0]
                default_val = param_data[1] if len(param_data) > 1 else get_default()
                if param_type == "str":
                    val = var.get().strip()
                    if val == "" and default_val != "":
                        node.params.pop(param_name, None)
                    elif val != default_val:
                        node.params[param_name] = val
                    else:
                        node.params.pop(param_name, None)
                elif param_type == "int":
                    val = safe_int(var.get(), default_val)
                    if val != default_val:
                        node.params[param_name] = val
                    else:
                        node.params.pop(param_name, None)
                elif param_type == "float":
                    val = safe_float(var.get(), default_val)
                    if val != default_val:
                        node.params[param_name] = val
                    else:
                        node.params.pop(param_name, None)
                elif param_type == "select":
                    val = var.get()
                    if val != default_val:
                        node.params[param_name] = val
                    else:
                        node.params.pop(param_name, None)
                elif param_type == "bool":
                    val = var.get()
                    if val != default_val:
                        node.params[param_name] = val
                    else:
                        node.params.pop(param_name, None)

            elif param_type == "dict":
                result = {}
                for sub_key, sub_data in param_data.items():
                    if sub_key.startswith("_"):
                        continue
                    sub_default = sub_data[1] if len(sub_data) > 1 else None
                    if isinstance(sub_data[0], list):
                        spin_vars = sub_data[0]
                        vals = [safe_int(v.get(), 0) for v in spin_vars]
                        if sub_default is not None and vals == sub_default:
                            continue
                        result[sub_key] = vals
                    else:
                        var = sub_data[0]
                        sub_type = config.get("sub", {}).get(sub_key, {}).get("type")
                        if sub_type == "str":
                            val = var.get().strip()
                            if val == "" and sub_default != "":
                                continue
                            if val != sub_default:
                                result[sub_key] = val
                        elif sub_type == "int":
                            val = safe_int(var.get(), sub_default)
                            if val != sub_default:
                                result[sub_key] = val
                        elif sub_type == "bool":
                            val = var.get()
                            if val != sub_default:
                                result[sub_key] = val
                        elif sub_type == "select":
                            val = var.get()
                            if val != sub_default:
                                result[sub_key] = val
                if result:
                    node.params[param_name] = result
                else:
                    node.params.pop(param_name, None)

            elif param_type == "list_dict":
                textbox = param_data[0]
                content = textbox.get("1.0", tk.END).strip()
                if content and content != "[]":
                    try:
                        parsed = json.loads(content)
                        node.params[param_name] = parsed
                    except:
                        node.params[param_name] = []
                else:
                    node.params.pop(param_name, None)

        self.refresh_node_list(keep_selection=True)
        if show_msg:
            messagebox.showinfo("成功", "节点已更新")

    def delete_selected_node(self, event=None):
        selection = self.node_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if messagebox.askyesno("确认删除", f"确定要删除节点 \"{self.current_task.nodes[idx].node_id}\" 吗？"):
            del self.current_task.nodes[idx]
            self.refresh_node_list()
            for widget in self.edit_scroll.winfo_children():
                widget.destroy()
            self.save_task()

    def add_node_dialog(self):
        if not self.current_task:
            messagebox.showwarning("提示", "请先选择一个任务")
            return
        node_types = list(ALL_PARAMS.keys())
        dialog = ctk.CTkToplevel(self)
        dialog.title("添加节点")
        dialog.geometry("300x400")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="选择节点类型:", font=("Arial", 12)).pack(pady=10)
        listbox = tk.Listbox(dialog, font=("Consolas", 10), height=15)
        for nt in node_types:
            listbox.insert(tk.END, nt)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def confirm():
            selection = listbox.curselection()
            if not selection:
                return
            node_type = node_types[selection[0]]
            node_id = f"{node_type}_{len(self.current_task.nodes)+1}"
            params = Node.get_defaults(node_type)
            node = Node(
                node_id=node_id,
                node_type=node_type,
                params=params,
                delay_before=0,
                loop_count=1,
                loop_interval=0,
                enabled=True,
                on_success=Jump(),
                on_failure=Jump()
            )
            self.current_task.nodes.append(node)
            self.refresh_node_list()
            dialog.destroy()
            self.save_task()

        btn_frame = ctk.CTkFrame(dialog)
        btn_frame.pack(fill=tk.X, pady=10)
        ctk.CTkButton(btn_frame, text="取消", command=dialog.destroy, width=80).pack(side=tk.RIGHT, padx=10)
        ctk.CTkButton(btn_frame, text="添加", command=confirm, width=80, fg_color="green").pack(side=tk.RIGHT, padx=10)

    def toggle_screenshot(self):
        if self.screenshot_frame.winfo_ismapped():
            self.screenshot_frame.pack_forget()
            self.screenshot_toggle.configure(text="▶ 截图工具")
        else:
            self.screenshot_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            self.screenshot_toggle.configure(text="▼ 截图工具")

    # ---------- 节点列表拖拽排序 ----------
    def on_listbox_press(self, event):
        self.drag_start_index = self.node_listbox.nearest(event.y)

    def on_listbox_drag(self, event):
        if self.drag_start_index is None:
            return
        current_index = self.node_listbox.nearest(event.y)
        if current_index < 0 or current_index >= len(self.current_task.nodes):
            return
        if current_index != self.drag_start_index:
            nodes = self.current_task.nodes
            nodes[self.drag_start_index], nodes[current_index] = nodes[current_index], nodes[self.drag_start_index]
            self.refresh_node_list(keep_selection=True)
            self.node_listbox.selection_set(current_index)
            self.drag_start_index = current_index

    def on_listbox_release(self, event):
        self.drag_start_index = None
        self.save_task()


# ---------- 截图工具面板 ----------
class ScreenshotPanel(ctk.CTkFrame):
    def __init__(self, parent, parent_ui=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.parent_ui = parent_ui
        self.current_project_path = None

        self.captured_image = None
        self.captured_rect = None
        self.captured_offset = (0, 0)
        self.selection_rect = None

        self.zoom_factor = 4
        self.preview_size = 200

        self.create_widgets()

    def create_widgets(self):
        self.pack_propagate(False)
        self.configure(height=400)

        row1 = ctk.CTkFrame(self)
        row1.pack(fill=tk.X, pady=2, padx=5)

        ctk.CTkLabel(row1, text="窗口名称:", font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        self.window_title_var = ctk.StringVar()
        self.window_title_entry = ctk.CTkEntry(row1, textvariable=self.window_title_var, width=120)
        self.window_title_entry.pack(side=tk.LEFT, padx=2)
        self.capture_btn = ctk.CTkButton(row1, text="截图", command=self.on_capture, width=60)
        self.capture_btn.pack(side=tk.LEFT, padx=5)

        ctk.CTkLabel(row1, text="放大:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(10,2))
        self.zoom_var = ctk.StringVar(value="4")
        self.zoom_entry = ctk.CTkEntry(row1, textvariable=self.zoom_var, width=30)
        self.zoom_entry.pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(row1, text="设置", command=self.apply_zoom, width=40).pack(side=tk.LEFT, padx=2)

        row2 = ctk.CTkFrame(self)
        row2.pack(fill=tk.X, pady=2, padx=5)

        ctk.CTkLabel(row2, text="裁剪 (T,B,L,R):", font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        self.crop_top_var = ctk.StringVar(value="0")
        self.crop_bottom_var = ctk.StringVar(value="0")
        self.crop_left_var = ctk.StringVar(value="0")
        self.crop_right_var = ctk.StringVar(value="0")
        for var, label in [(self.crop_top_var, "T"), (self.crop_bottom_var, "B"),
                           (self.crop_left_var, "L"), (self.crop_right_var, "R")]:
            ctk.CTkLabel(row2, text=label, font=("Arial", 10)).pack(side=tk.LEFT, padx=1)
            ctk.CTkEntry(row2, textvariable=var, width=25).pack(side=tk.LEFT, padx=1)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, pady=2, padx=5)
        main_frame.pack_propagate(False)
        main_frame.configure(height=250)

        canvas_frame = ctk.CTkFrame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Escape>", lambda e: self.clear_selection())

        preview_frame = ctk.CTkFrame(main_frame, width=200)
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5)
        preview_frame.pack_propagate(False)

        ctk.CTkLabel(preview_frame, text="🔍 框选放大预览", font=("Arial", 10, "bold")).pack(pady=2)
        self.preview_canvas = tk.Canvas(preview_frame, bg='white', highlightthickness=1)
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.preview_info = ctk.CTkLabel(preview_frame, text="框选后显示", font=("Arial", 9))
        self.preview_info.pack(pady=2)

        row4 = ctk.CTkFrame(self)
        row4.pack(fill=tk.X, pady=2, padx=5)

        ctk.CTkLabel(row4, text="框选 (x,y,w,h):", font=("Arial", 10)).pack(side=tk.LEFT, padx=2)

        self.sel_vars = []
        def apply_values():
            try:
                vals = [safe_int(v.get(), 0) for v in self.sel_vars]
                if len(vals) == 4 and self.captured_image:
                    x, y, w, h = vals
                    x = max(0, min(x, self.captured_image.width - 1))
                    y = max(0, min(y, self.captured_image.height - 1))
                    w = min(w, self.captured_image.width - x)
                    h = min(h, self.captured_image.height - y)
                    if w > 0 and h > 0:
                        self.selection_rect = (x, y, w, h)
                        self._update_canvas_rect()
                        self.update_preview()
                        self._update_coord_display()
            except:
                pass

        for i, initial in enumerate([0,0,0,0]):
            frame = ctk.CTkFrame(row4)
            frame.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

            var = tk.StringVar(value=str(initial))
            entry = ctk.CTkEntry(frame, textvariable=var, width=50)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

            def make_adjust(delta):
                def adjust():
                    try:
                        val = safe_int(var.get(), 0) + delta
                        if val < 0: val = 0
                        var.set(str(val))
                        apply_values()
                    except:
                        pass
                return adjust

            btn_up = ctk.CTkButton(frame, text="▲", width=20, height=20, command=make_adjust(1))
            btn_up.pack(side=tk.LEFT, padx=1)
            btn_down = ctk.CTkButton(frame, text="▼", width=20, height=20, command=make_adjust(-1))
            btn_down.pack(side=tk.LEFT, padx=1)

            def on_change(event=None):
                apply_values()
            entry.bind("<FocusOut>", on_change)
            entry.bind("<Return>", on_change)

            self.sel_vars.append(var)

        ctk.CTkButton(row4, text="清除", command=self.clear_selection, width=50).pack(side=tk.LEFT, padx=5)

        row6 = ctk.CTkFrame(self)
        row6.pack(fill=tk.X, pady=2, padx=5)

        ctk.CTkLabel(row6, text="截图区域:", font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
        self.captured_rect_label = ctk.CTkLabel(row6, text="未截图", font=("Arial", 10))
        self.captured_rect_label.pack(side=tk.LEFT, padx=5)
        ctk.CTkLabel(row6, text="框选区域:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.selection_abs_label = ctk.CTkLabel(row6, text="", font=("Arial", 10))
        self.selection_abs_label.pack(side=tk.LEFT, padx=5)

        row7 = ctk.CTkFrame(self)
        row7.pack(fill=tk.X, pady=2, padx=5)

        ctk.CTkButton(row7, text="复制框选区域 (JSON)", command=self.copy_selection, width=140).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(row7, text="保存模板", command=self.save_selection, width=100, fg_color="#2a7a2a", hover_color="#1e5e1e").pack(side=tk.LEFT, padx=2)
        self.fill_btn = ctk.CTkButton(row7, text="填入节点参数", command=self.fill_region_to_node, width=100)
        self.fill_btn.pack(side=tk.LEFT, padx=2)

    def apply_zoom(self):
        try:
            val = int(self.zoom_var.get())
            if val < 1: val = 1
            if val > 20: val = 20
            self.zoom_factor = val
            self.zoom_var.set(str(val))
            if self.selection_rect:
                self.update_preview()
        except:
            pass

    def on_capture(self, event=None):
        title = self.window_title_var.get().strip()
        crop = {
            "top": safe_int(self.crop_top_var.get()),
            "bottom": safe_int(self.crop_bottom_var.get()),
            "left": safe_int(self.crop_left_var.get()),
            "right": safe_int(self.crop_right_var.get())
        }

        if title:
            hwnd = win32gui.FindWindow(None, title)
            if not hwnd:
                messagebox.showerror("错误", f"未找到窗口: {title}")
                return
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            client_rect = win32gui.GetClientRect(hwnd)
            left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))
            right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
            rect = (left, top, right - left, bottom - top)

            # 计算裁剪后的区域
            x = rect[0] + crop["left"]
            y = rect[1] + crop["top"]
            w = rect[2] - crop["left"] - crop["right"]
            h = rect[3] - crop["top"] - crop["bottom"]
            if w <= 0 or h <= 0:
                messagebox.showerror("错误", "裁剪后区域无效")
                return

            # 存储裁剪后的区域作为截图区域
            self.captured_rect = (x, y, w, h)
            # 关键修正：captured_offset 设为裁剪后区域的左上角，作为后续坐标参考的偏移量
            self.captured_offset = (x, y)
        else:
            # 全屏截图，无偏移
            screen_w, screen_h = pyautogui.size()
            self.captured_rect = (0, 0, screen_w, screen_h)
            self.captured_offset = (0, 0)

        # 截图
        x, y, w, h = self.captured_rect
        img = pyautogui.screenshot(region=(x, y, w, h))
        self.captured_image = img
        self.display_image(img)

        # 相对坐标（相对于内容区域）
        rel_x = x - self.captured_offset[0]  # 此时 x 等于 captured_offset[0]，所以为 0
        rel_y = y - self.captured_offset[1]  # 同理
        self.captured_rect_label.configure(text=f"({rel_x},{rel_y},{w},{h})")
        self.clear_selection()

    def display_image(self, img):
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 1 or canvas_h <= 1:
            canvas_w, canvas_h = 400, 300

        img_w, img_h = img.size
        ratio = min(canvas_w / img_w, canvas_h / img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.canvas.create_image((canvas_w - new_w)//2, (canvas_h - new_h)//2, anchor="nw", image=self.photo)
        self.canvas.image = self.photo
        self.canvas.scale_ratio = ratio
        self.canvas.img_offset_x = (canvas_w - new_w)//2
        self.canvas.img_offset_y = (canvas_h - new_h)//2
        self.canvas.img_w = new_w
        self.canvas.img_h = new_h
        self.canvas.orig_w = img_w
        self.canvas.orig_h = img_h

    def on_canvas_press(self, event):
        if not self.captured_image:
            return
        self.start_x = event.x
        self.start_y = event.y
        if hasattr(self.canvas, 'rect_id') and self.canvas.rect_id:
            self.canvas.delete(self.canvas.rect_id)
            self.canvas.rect_id = None

    def on_canvas_drag(self, event):
        if not hasattr(self, 'start_x') or self.start_x is None:
            return
        x0, y0 = self.start_x, self.start_y
        x1, y1 = event.x, event.y
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        if hasattr(self.canvas, 'rect_id') and self.canvas.rect_id:
            self.canvas.coords(self.canvas.rect_id, x0, y0, x1, y1)
        else:
            self.canvas.rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline='red', width=2)

    def on_canvas_release(self, event):
        if not hasattr(self, 'start_x') or self.start_x is None:
            return
        x0, y0 = self.start_x, self.start_y
        x1, y1 = event.x, event.y
        if x0 > x1: x0, x1 = x1, x0
        if y0 > y1: y0, y1 = y1, y0
        w = x1 - x0
        h = y1 - y0
        if w < 2 or h < 2:
            return

        ratio = self.canvas.scale_ratio if hasattr(self.canvas, 'scale_ratio') else 1.0
        offset_x = self.canvas.img_offset_x if hasattr(self.canvas, 'img_offset_x') else 0
        offset_y = self.canvas.img_offset_y if hasattr(self.canvas, 'img_offset_y') else 0

        orig_x = int((x0 - offset_x) / ratio)
        orig_y = int((y0 - offset_y) / ratio)
        orig_w = int(w / ratio)
        orig_h = int(h / ratio)

        orig_x = max(0, min(orig_x, self.captured_image.width - 1))
        orig_y = max(0, min(orig_y, self.captured_image.height - 1))
        orig_w = min(orig_w, self.captured_image.width - orig_x)
        orig_h = min(orig_h, self.captured_image.height - orig_y)

        if orig_w <= 0 or orig_h <= 0:
            return

        self.selection_rect = (orig_x, orig_y, orig_w, orig_h)
        if len(self.sel_vars) == 4:
            self.sel_vars[0].set(str(orig_x))
            self.sel_vars[1].set(str(orig_y))
            self.sel_vars[2].set(str(orig_w))
            self.sel_vars[3].set(str(orig_h))

        self._update_coord_display()
        self.update_preview()

    def _update_coord_display(self):
        if not self.captured_rect or not self.selection_rect:
            return
        x, y, w, h = self.selection_rect
        abs_x = self.captured_rect[0] + x
        abs_y = self.captured_rect[1] + y
        rel_x = abs_x - self.captured_offset[0]
        rel_y = abs_y - self.captured_offset[1]
        self.selection_abs_label.configure(text=f"({rel_x},{rel_y},{w},{h})")

    def update_preview(self):
        if not self.captured_image or not self.selection_rect:
            self.preview_canvas.delete("all")
            self.preview_info.configure(text="框选后显示放大")
            return

        x, y, w, h = self.selection_rect
        crop = self.captured_image.crop((x, y, x+w, y+h))
        if crop.width == 0 or crop.height == 0:
            return

        preview_w = self.preview_canvas.winfo_width()
        preview_h = self.preview_canvas.winfo_height()
        if preview_w <= 10 or preview_h <= 10:
            preview_w, preview_h = 200, 200

        ratio = min(preview_w / crop.width, preview_h / crop.height)
        new_w = int(crop.width * ratio)
        new_h = int(crop.height * ratio)
        zoomed = crop.resize((new_w, new_h), Image.Resampling.NEAREST)

        self.preview_photo = ImageTk.PhotoImage(zoomed)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image((preview_w - new_w)//2, (preview_h - new_h)//2, anchor="nw", image=self.preview_photo)
        self.preview_canvas.image = self.preview_photo
        self.preview_info.configure(text=f"框选: {w}x{h} 像素")

    def _update_canvas_rect(self):
        if not self.selection_rect:
            return
        x, y, w, h = self.selection_rect
        ratio = self.canvas.scale_ratio if hasattr(self.canvas, 'scale_ratio') else 1.0
        offset_x = self.canvas.img_offset_x if hasattr(self.canvas, 'img_offset_x') else 0
        offset_y = self.canvas.img_offset_y if hasattr(self.canvas, 'img_offset_y') else 0
        x0 = offset_x + x * ratio
        y0 = offset_y + y * ratio
        x1 = x0 + w * ratio
        y1 = y0 + h * ratio
        if hasattr(self.canvas, 'rect_id') and self.canvas.rect_id:
            self.canvas.coords(self.canvas.rect_id, x0, y0, x1, y1)
        else:
            self.canvas.rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline='red', width=2)

    def clear_selection(self):
        self.selection_rect = None
        for v in self.sel_vars:
            v.set("0")
        self.selection_abs_label.configure(text="")
        if hasattr(self.canvas, 'rect_id') and self.canvas.rect_id:
            self.canvas.delete(self.canvas.rect_id)
            self.canvas.rect_id = None
        self.preview_canvas.delete("all")
        self.preview_info.configure(text="框选后显示放大")

    def copy_selection(self):
        if not self.captured_rect or not self.selection_rect:
            return
        x, y, w, h = self.selection_rect
        abs_x = self.captured_rect[0] + x
        abs_y = self.captured_rect[1] + y
        rel_x = abs_x - self.captured_offset[0]
        rel_y = abs_y - self.captured_offset[1]
        text = f'"region": {{ "type": "recorded", "value": [{rel_x}, {rel_y}, {w}, {h}] }}'
        self.copy_to_clipboard(text)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("复制成功", "已复制到剪贴板")

    def save_selection(self):
        if not self.captured_image or not self.selection_rect:
            messagebox.showwarning("提示", "请先截图并框选区域")
            return
        x, y, w, h = self.selection_rect
        crop = self.captured_image.crop((x, y, x + w, y + h))
        if self.parent_ui and self.parent_ui.current_project_path:
            template_dir = os.path.join(self.parent_ui.current_project_path, "templates")
        else:
            template_dir = resource_path("templates")
        os.makedirs(template_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            title="保存模板图片",
            initialdir=template_dir,
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.png'):
            file_path += '.png'

        # 确保目标文件夹存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if os.path.exists(file_path):
            result = messagebox.askyesno("文件已存在", f"文件 {os.path.basename(file_path)} 已存在，是否覆盖？")
            if not result:
                return

        try:
            crop.save(file_path)
            messagebox.showinfo("保存成功", f"模板已保存至:\n{file_path}")
            self.clipboard_clear()
            self.clipboard_append(file_path)

            rel_path = get_relative_template_path(self.parent_ui.current_project_path, file_path)
            # 计算相对坐标（相对于内容区域）
            abs_x = self.captured_rect[0] + self.selection_rect[0]
            abs_y = self.captured_rect[1] + self.selection_rect[1]
            rel_x = abs_x - self.captured_offset[0]
            rel_y = abs_y - self.captured_offset[1]
            region = [rel_x, rel_y, self.selection_rect[2], self.selection_rect[3]]
            self.parent_ui.template_regions[rel_path] = region
            self.parent_ui._save_template_regions()
            if hasattr(self.parent_ui, '_template_selector_data'):
                _, _, refresh_func = self.parent_ui._template_selector_data
                refresh_func()
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def fill_region_to_node(self):
        if not self.selection_rect or not self.captured_offset:
            messagebox.showwarning("提示", "请先框选区域")
            return
        x, y, w, h = self.selection_rect
        rel_x = x + self.captured_rect[0] - self.captured_offset[0]
        rel_y = y + self.captured_rect[1] - self.captured_offset[1]
        region_value = [rel_x, rel_y, w, h]
        if self.parent_ui and hasattr(self.parent_ui, 'current_edit_node'):
            node = self.parent_ui.current_edit_node
            if "region" in node.params:
                node.params["region"]["value"] = region_value
                node.params["region"]["type"] = "recorded"
                messagebox.showinfo("成功", f"已更新节点 {node.node_id} 的 region 参数")
                self.parent_ui.display_node_editor(node)
            else:
                messagebox.showwarning("提示", "当前节点没有 region 参数")
        else:
            messagebox.showwarning("提示", "请先选中一个节点")


# ---------- 启动 ----------
if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MainUI()
    app.mainloop()