# core/params/base/control.py
# 控件操作节点参数定义：捕获控件 + 匹配操作（点击/双击/悬停）
# ⚡ 表单展示：控件信息（只读 textarea + 捕获/重置按钮）、目标窗口标题（快速定位筛选项）、
# 匹配序号、匹配超时时长、匹配成功操作；by/control_info 为隐藏字段，由「捕获控件」自动填充。

from .defaults import NODE_DEFAULTS

PARAM_DEFINITIONS = {
    'control': {
        'label': '控件操作',
        'modes': ['workflow'],
        'params': {
            'target': {
                # ⚡ capture_str：只读 textarea 展示捕获全部信息 + 「捕获控件/重置控件」按钮（前端专用控件）
                'type': 'capture_str',
                'label': '控件信息',
                'default': '',
                'placeholder': '点击「捕获控件」自动填入',
            },
            'action': {
                'type': 'select',
                'label': '匹配成功操作',
                'default': 'click',
                'options': [
                    {'value': 'click', 'label': '点击控件'},
                    {'value': 'double_click', 'label': '双击控件'},
                    {'value': 'hover', 'label': '悬停控件'},
                ],
            },
            'timeout': {
                'type': 'int',
                'label': '匹配超时时长',
                'default': NODE_DEFAULTS['timeout'],
                'suffix': 'ms',
                'min': 100,
                'step': 100,
            },
            # ---------------- 快速定位筛选项（捕获时自动填充，可手动修改） ----------------
            'window_title': {
                # ⚡ 可见筛选项：只在该窗口下查找（避免全桌面遍历）；窗口标题动态变化时可手动改静态部分
                'type': 'str',
                'label': '目标窗口标题',
                'default': '',
                'placeholder': '留空 = 全部窗口',
            },
            'index': {
                'type': 'int',
                'label': '匹配序号',
                'default': 0,
                'min': 0,
            },
            # ---------------- 以下为隐藏字段（捕获时自动填充，不展示） ----------------
            'by': {
                'type': 'select',
                'label': '查找方式',
                'default': 'uia_name',
                'hidden': True,
                'options': [
                    {'value': 'uia_name', 'label': '控件名称 (UIA，推荐)'},
                    {'value': 'uia_type', 'label': '控件类型 (UIA)'},
                    {'value': 'uia_id', 'label': '自动化ID (UIA)'},
                    {'value': 'uia_class', 'label': '控件类名 (UIA)'},
                    {'value': 'class_name', 'label': '控件类名 (Win32)'},
                    {'value': 'text', 'label': '控件文本 (Win32)'},
                    {'value': 'control_type', 'label': '控件类型 (Win32)'},
                ],
            },
            # 捕获的完整控件信息（name/type/id/class/rect/ancestor_path 等），表单不展示但执行时使用
            'control_info': {
                'type': 'dict',
                'label': '控件信息',
                'hidden': True,
            },
        },
    }
}
