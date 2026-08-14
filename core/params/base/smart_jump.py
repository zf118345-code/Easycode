# core/params/base/smart_jump.py
# P2 新增：smart_jump 智能跳转节点参数定义
# smart_jump 是工作流画布中的节点，业务人员只需指定目标页面（或目标节点），
# 底层会自动在拓扑地图 / 工作流图上寻路，并逐步执行过图动作。
#
# 本文件导出 PARAM_DEFINITIONS，供参数面板渲染与默认值合并使用。

from typing import Any

# smart_jump 节点参数定义
PARAM_DEFINITIONS: dict[str, dict[str, Any]] = {
    'smart_jump': {
        'label': '智能跳转',
        'params': {
            # 目标页面 ID：在拓扑地图上寻路（页面级）
            'target_page_id': {'type': 'str', 'label': '目标页面 ID', 'default': '', 'placeholder': '如：shop'},
            # 目标任务组 ID：跨任务组寻路时指定，可选
            'target_task_id': {
                'type': 'str',
                'label': '目标任务组 ID',
                'default': '',
                'placeholder': '可选，跨任务组寻路时指定',
            },
            # 目标节点 ID：在工作流图上寻路（节点级），优先于目标页面
            'target_node_id': {
                'type': 'str',
                'label': '目标节点 ID',
                'default': '',
                'placeholder': '可选，优先于目标页面',
            },
            # 寻路策略：shortest 最短路径 / first_match 首条可达
            'path_strategy': {
                'type': 'select',
                'label': '寻路策略',
                'default': 'shortest',
                'options': ['shortest', 'first_match'],
            },
            # 最大重试次数：寻路失败后重新尝试的次数
            'max_retries': {'type': 'int', 'label': '最大重试次数', 'default': 3, 'min': 0, 'max': 20},
            # 是否自动清理弹窗阻碍：重试前尝试关闭常见弹窗
            'clear_obstacles': {'type': 'bool', 'label': '自动清理弹窗阻碍', 'default': True},
            # 超时时间（秒）：整体寻路的最长等待时间
            'timeout': {'type': 'int', 'label': '超时时间(秒)', 'default': 30, 'min': 1, 'max': 600},
        },
    }
}
