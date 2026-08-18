# core/params/base/topology.py
# P2 新增：page_state 节点参数定义
# page_state 是拓扑画布的"页面状态节点"，用于定义"页面长什么样"。
# 通过复合特征（AND/OR 组合）识别当前所处页面，识别成功后会将 page_id
# 写入运行时变量 current_page_id，供 smart_jump 在拓扑地图上寻路使用。
#
# 页面名称 = 节点标题（node_name），不再单独配置；
# 页面出口 = 画布连线（边即出口，动作/名称配置在边上），不再作为节点参数。
#
# 本文件导出 PARAM_DEFINITIONS，供参数面板渲染与默认值合并使用。

from typing import Any

# page_state 节点参数定义
PARAM_DEFINITIONS: dict[str, dict[str, Any]] = {
    'page_state': {
        'label': '页面状态',
        'modes': ['topology'],
        'params': {
            # 页面唯一标识，对应拓扑地图邻接表中的节点 ID（内部字段，表单隐藏，新建时自动生成）
            'page_id': {
                'type': 'str',
                'label': '页面唯一标识',
                'default': '',
                'placeholder': '如：shop / dungeon_entrance',
                'hidden': True,
            },
            # 复合特征列表：每行一个条件（图像存在 / 文本包含），按组合模式聚合
            # 复用 condition_list_editor（与逻辑判断同款交互），pageFeatures 追加
            # 「组合方式 / 结果取反」两个页面特征专属字段
            'features': {
                'type': 'condition_list_editor',
                'label': '复合特征列表',
                'default': [],
                'pageFeatures': True,
                'addLabel': '添加特征',
                'description': '定义该页面的识别特征，按 feature_mode(AND/OR) 聚合判断',
            },
            # 全局特征组合模式：当单条特征未指定 combine_mode 时使用
            'feature_mode': {'type': 'select', 'label': '特征组合模式', 'default': 'and', 'options': ['and', 'or']},
        },
    }
}
