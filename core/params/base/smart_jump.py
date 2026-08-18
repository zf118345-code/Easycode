# core/params/base/smart_jump.py
# P2 新增：smart_jump 智能跳转节点参数定义
# smart_jump 是主流程（workflow）专属节点，业务人员只需指定目标页面，
# 底层会自动在拓扑地图上从当前位置寻路，并沿途执行操作节点 / 页面确认到达目标页。
#
# 本文件导出 PARAM_DEFINITIONS，供参数面板渲染与默认值合并使用。

from typing import Any

from .defaults import NODE_DEFAULTS

# smart_jump 节点参数定义
PARAM_DEFINITIONS: dict[str, dict[str, Any]] = {
    'smart_jump': {
        'label': '智能跳转',
        'modes': ['workflow'],
        'params': {
            # 目标页面：下拉选择当前拓扑地图中已定义的页面（page_select 控件动态取数）
            'target_page_id': {'type': 'page_select', 'label': '目标页面', 'default': '', 'placeholder': '请选择目标页面'},
            # 超时时间（毫秒）：整个跳转执行（寻路 + 沿途执行）的最长等待时间
            'timeout': {'type': 'int', 'label': '超时时间(ms)', 'default': NODE_DEFAULTS['timeout'], 'min': 100, 'max': 600000, 'step': 500},
        },
    }
}
