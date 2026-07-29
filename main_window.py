import sys
import os
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QScrollArea, QLabel, QPushButton,
    QComboBox, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox,
    QFrame, QSplitter, QMenuBar, QMenu, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QFileDialog, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QIcon, QFont

# 导入您的核心模块（路径可能需要调整）
from core.models import Project, Task, Node, Jump
from core.project_loader import load_project
from core.params import ALL_PARAMS
from core.registry import NodeExecutorRegistry
from core.executor import GraphExecutor

# 全局样式（QSS）在最后设置


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("节点自动化 - 可视化编辑器")
        self.resize(1400, 900)

        # 状态变量
        self.project = None
        self.current_task_id = None
        self.current_task = None
        self.current_project_path = None
        self.template_regions = {}

        # 创建中心部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ========== 左侧面板 ==========
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(5)

        # ---- 项目选择栏（顶部） ----
        project_bar = QWidget()
        project_layout = QHBoxLayout(project_bar)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_label = QLabel("项目:")
        self.project_combo = QComboBox()
        self.project_combo.currentTextChanged.connect(self.switch_project)
        self.btn_new_project = QPushButton("新建")
        self.btn_new_project.clicked.connect(self.new_project)
        project_layout.addWidget(project_label)
        project_layout.addWidget(self.project_combo, 1)
        project_layout.addWidget(self.btn_new_project)
        left_layout.addWidget(project_bar)

        # ---- 任务管理 ----
        task_bar = QWidget()
        task_layout = QHBoxLayout(task_bar)
        task_layout.setContentsMargins(0, 0, 0, 0)
        task_label = QLabel("任务:")
        self.task_combo = QComboBox()
        self.task_combo.currentTextChanged.connect(self.on_task_selected)
        self.btn_new_task = QPushButton("+")
        self.btn_new_task.clicked.connect(self.new_task)
        self.btn_save_task = QPushButton("💾")
        self.btn_save_task.clicked.connect(self.save_task)
        task_layout.addWidget(task_label)
        task_layout.addWidget(self.task_combo, 1)
        task_layout.addWidget(self.btn_new_task)
        task_layout.addWidget(self.btn_save_task)
        left_layout.addWidget(task_bar)

        # ---- 节点列表 ----
        node_label = QLabel("节点列表（拖动可排序）")
        left_layout.addWidget(node_label)
        self.node_list = QListWidget()
        self.node_list.setDragDropMode(QListWidget.InternalMove)  # 支持内部拖拽排序
        self.node_list.model().rowsMoved.connect(self.on_nodes_reordered)
        self.node_list.itemClicked.connect(self.on_node_selected)
        left_layout.addWidget(self.node_list)

        # ---- 节点添加/删除按钮 ----
        btn_layout = QHBoxLayout()
        self.btn_add_node = QPushButton("添加节点")
        self.btn_add_node.clicked.connect(self.add_node_dialog)
        self.btn_delete_node = QPushButton("删除选中")
        self.btn_delete_node.clicked.connect(self.delete_selected_node)
        btn_layout.addWidget(self.btn_add_node)
        btn_layout.addWidget(self.btn_delete_node)
        left_layout.addLayout(btn_layout)

        # 左侧面板添加到主布局
        main_layout.addWidget(left_panel)

        # ========== 右侧面板（编辑器 + 截图工具） ==========
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(5)

        # ---- 节点编辑区 ----
        self.edit_scroll = QScrollArea()
        self.edit_scroll.setWidgetResizable(True)
        self.edit_content = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_content)
        self.edit_scroll.setWidget(self.edit_content)
        right_layout.addWidget(self.edit_scroll, 3)  # 占大部分空间

        # ---- 截图工具区（可折叠） ----
        self.screenshot_toggle = QPushButton("▼ 截图工具")
        self.screenshot_toggle.setCheckable(True)
        self.screenshot_toggle.toggled.connect(self.toggle_screenshot)
        right_layout.addWidget(self.screenshot_toggle)

        self.screenshot_widget = ScreenshotPanel(self)
        self.screenshot_widget.setVisible(False)
        right_layout.addWidget(self.screenshot_widget, 1)

        # 右侧面板添加到主布局
        main_layout.addWidget(right_panel, 1)

        # 加载初始项目
        self.refresh_project_list()
        self.load_default_project()

        # 应用样式表
        self.setStyleSheet(self.get_style_sheet())

    # ======================== 样式表 ========================
    def get_style_sheet(self):
        """返回全局 QSS 样式，您可以在此自由修改颜色、圆角、字体等"""
        return """
            QMainWindow {
                background: #f0f2f5;
            }
            QWidget {
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background: #409EFF;
                color: black;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #66b1ff;
            }
            QPushButton:pressed {
                background: #3a8ee6;
            }
            QPushButton#danger {
                background: #f56c6c;
            }
            QPushButton#danger:hover {
                background: #f78989;
            }
            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 4px 8px;
                background: white;
                min-height: 22px;
            }
            QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #409EFF;
            }
            QListWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                background: white;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #ebeef5;
            }
            QListWidget::item:selected {
                background: #ecf5ff;
                color: #409EFF;
            }
            QListWidget::item:hover {
                background: #f5f7fa;
            }
            QScrollArea {
                border: none;
                background: white;
                border-radius: 4px;
            }
            QGroupBox {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: #303133;
            }
            QCheckBox {
                spacing: 5px;
            }
        """

    # ======================== 项目/任务管理 ========================
    def refresh_project_list(self):
        projects_dir = "projects"
        if not os.path.exists(projects_dir):
            os.makedirs(projects_dir)
        projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
        self.project_combo.clear()
        self.project_combo.addItems(projects)

    def load_default_project(self):
        projects = [self.project_combo.itemText(i) for i in range(self.project_combo.count())]
        if "demo" in projects:
            self.project_combo.setCurrentText("demo")
        elif projects:
            self.project_combo.setCurrentIndex(0)
        else:
            self.new_project("demo")

    def switch_project(self, project_name):
        if not project_name:
            return
        self.save_task()
        self.current_project_path = os.path.join("projects", project_name)
        self._load_current_project()

    def _load_current_project(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            return
        try:
            self.project = load_project(self.current_project_path)
            self._load_template_regions()
            self.refresh_task_list()
            if self.project.tasks:
                self.task_combo.setCurrentText(list(self.project.tasks.keys())[0])
                self.current_task_id = list(self.project.tasks.keys())[0]
                self.current_task = self.project.tasks[self.current_task_id]
                self.refresh_node_list()
            else:
                self.task_combo.clear()
                self.current_task = None
                self.refresh_node_list()
        except Exception as e:
            QMessageBox.critical(self, "加载项目失败", str(e))

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
            name, ok = QInputDialog.getText(self, "新建项目", "请输入项目名称（英文）:")
            if not ok or not name:
                return
        project_dir = os.path.join("projects", name)
        if os.path.exists(project_dir):
            QMessageBox.warning(self, "错误", "项目已存在")
            return
        os.makedirs(project_dir)
        os.makedirs(os.path.join(project_dir, "tasks"))
        os.makedirs(os.path.join(project_dir, "templates"))
        with open(os.path.join(project_dir, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"project_name": name, "variables": {}, "default_threshold": 0.85, "default_timeout": 3000}, f, indent=2)
        self.refresh_project_list()
        self.project_combo.setCurrentText(name)
        QMessageBox.information(self, "成功", f"项目 {name} 已创建")

    # ---------- 任务管理 ----------
    def refresh_task_list(self):
        self.task_combo.clear()
        if not self.project:
            return
        self.task_combo.addItems(list(self.project.tasks.keys()))

    def on_task_selected(self, task_id):
        if not task_id:
            return
        self.save_task()
        self.current_task_id = task_id
        self.current_task = self.project.tasks[task_id]
        self.refresh_node_list()

    def new_task(self):
        name, ok = QInputDialog.getText(self, "新建任务", "请输入任务ID（英文）:")
        if not ok or not name:
            return
        if name in self.project.tasks:
            QMessageBox.warning(self, "错误", "任务ID已存在")
            return
        task = Task(task_id=name, task_name=name, nodes=[])
        self.project.tasks[name] = task
        self.refresh_task_list()
        self.task_combo.setCurrentText(name)
        self.current_task = task
        self.current_task_id = name
        self.refresh_node_list()
        self.save_task()

    def save_task(self):
        if not self.current_task or not self.current_project_path:
            return
        # 先保存当前编辑的节点（如果有）
        # 这里需要调用一个保存节点编辑的方法，稍后实现

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
            node_dict = {"node_id": node.node_id, "node_type": node.node_type, "params": filtered_params}
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
    def refresh_node_list(self):
        self.node_list.clear()
        if not self.current_task:
            return
        for i, node in enumerate(self.current_task.nodes):
            item = QListWidgetItem(f"[{i+1}] {node.node_id} ({node.node_type})")
            self.node_list.addItem(item)

    def on_node_selected(self, item):
        # 根据选中的节点显示编辑内容
        idx = self.node_list.row(item)
        node = self.current_task.nodes[idx]
        self.display_node_editor(node)

    def on_nodes_reordered(self, parent, start, end, destination, row):
        # 节点拖拽排序后更新数据
        if start == row:  # 位置未变
            return
        nodes = self.current_task.nodes
        # 移除并插入
        node = nodes.pop(start)
        nodes.insert(row, node)
        # 刷新列表显示（保持选中）
        self.refresh_node_list()
        self.node_list.setCurrentRow(row)
        self.save_task()

    def display_node_editor(self, node):
        # 清空编辑区
        for i in reversed(range(self.edit_layout.count())):
            widget = self.edit_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # 构建编辑表单（示例：简单显示基本属性）
        # 实际需要动态生成所有参数控件，这里仅做演示
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # 节点ID（可编辑）
        id_edit = QLineEdit(node.node_id)
        form.addRow("节点 ID:", id_edit)

        # 类型（只读）
        type_label = QLabel(node.node_type)
        form.addRow("类型:", type_label)

        # 延迟、循环等（用QSpinBox示例）
        delay_spin = QSpinBox()
        delay_spin.setRange(0, 10000)
        delay_spin.setValue(node.delay_before)
        form.addRow("延迟(ms):", delay_spin)

        loop_spin = QSpinBox()
        loop_spin.setRange(-1, 999)
        loop_spin.setValue(node.loop_count)
        form.addRow("循环次数:", loop_spin)

        interval_spin = QSpinBox()
        interval_spin.setRange(0, 10000)
        interval_spin.setValue(node.loop_interval)
        form.addRow("循环间隔(ms):", interval_spin)

        # 保存修改按钮
        save_btn = QPushButton("保存节点修改")
        save_btn.clicked.connect(lambda: self.save_node_editor(node, id_edit, delay_spin, loop_spin, interval_spin))

        self.edit_layout.addLayout(form)
        self.edit_layout.addWidget(save_btn)
        self.edit_layout.addStretch()

        # 设置当前编辑的节点引用
        self._current_edit_node = node
        self._edit_widgets = (id_edit, delay_spin, loop_spin, interval_spin)

    def save_node_editor(self, node, id_edit, delay_spin, loop_spin, interval_spin):
        # 更新节点属性
        new_id = id_edit.text().strip()
        if new_id and new_id != node.node_id:
            # 检查重复
            if any(n.node_id == new_id for n in self.current_task.nodes if n is not node):
                QMessageBox.warning(self, "错误", f"节点ID '{new_id}' 已存在")
                return
            node.node_id = new_id
        node.delay_before = delay_spin.value()
        node.loop_count = loop_spin.value()
        node.loop_interval = interval_spin.value()
        # 实际还需保存参数表单中的值（略）
        self.refresh_node_list()
        self.save_task()
        QMessageBox.information(self, "成功", "节点已更新")

    # ---------- 添加/删除节点 ----------
    def add_node_dialog(self):
        if not self.current_task:
            QMessageBox.warning(self, "提示", "请先选择一个任务")
            return
        node_types = list(ALL_PARAMS.keys())
        # 简单对话框：使用列表选择
        dialog = QDialog(self)
        dialog.setWindowTitle("添加节点")
        dialog.resize(300, 400)
        layout = QVBoxLayout(dialog)
        label = QLabel("选择节点类型:")
        layout.addWidget(label)
        list_widget = QListWidget()
        for nt in node_types:
            list_widget.addItem(nt)
        layout.addWidget(list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted and list_widget.currentItem():
            node_type = list_widget.currentItem().text()
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
            self.save_task()

    def delete_selected_node(self):
        item = self.node_list.currentItem()
        if not item:
            return
        idx = self.node_list.row(item)
        node = self.current_task.nodes[idx]
        reply = QMessageBox.question(self, "确认删除", f"确定要删除节点 \"{node.node_id}\" 吗？")
        if reply == QMessageBox.Yes:
            del self.current_task.nodes[idx]
            self.refresh_node_list()
            self.save_task()
            # 清空编辑区
            self.display_node_editor(None)  # 待实现

    # ---------- 截图工具折叠 ----------
    def toggle_screenshot(self, checked):
        self.screenshot_widget.setVisible(checked)
        self.screenshot_toggle.setText("▼ 截图工具" if checked else "▶ 截图工具")


# ======================== 截图工具面板 ========================
# 由于截图工具涉及大量图像处理，此处仅提供框架，实际需移植原功能
class ScreenshotPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        layout = QVBoxLayout(self)
        label = QLabel("截图工具面板 (待移植)")
        layout.addWidget(label)

        # 这里可以放置原ScreenshotPanel中的控件，使用Qt的截图功能
        # 如：使用 QScreen.grabWindow() 截图，用 QLabel 显示等

        self.setVisible(False)


# ======================== 启动 ========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())