# core/params/base/topology.py
# P2 新增：page_state 节点参数定义
# page_state 是拓扑画布的"页面状态节点"，用于定义"页面长什么样"。
# 通过复合特征（AND/OR 组合）识别当前所处页面，识别成功后会将 page_id
# 写入运行时变量 current_page_id，供 smart_jump 在拓扑地图上寻路使用。
#
# 本文件导出 PARAM_DEFINITIONS，供参数面板渲染与默认值合并使用。

from typing import Any, Dict

# page_state 节点参数定义
PARAM_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "page_state": {
        "label": "页面状态",
        "params": {
            # 页面唯一标识，对应拓扑地图邻接表中的节点 ID
            "page_id": {
                "type": "str",
                "label": "页面唯一标识",
                "default": "",
                "placeholder": "如：shop / dungeon_entrance"
            },
            # 页面显示名称，仅用于画布展示与日志，不参与寻路
            "page_name": {
                "type": "str",
                "label": "页面名称",
                "default": "",
                "placeholder": "如：商城页"
            },
            # 复合特征列表：每个特征描述一个识别条件，按组合模式聚合
            "features": {
                "type": "list_dict",
                "label": "复合特征列表",
                "default": [],
                "description": "定义该页面的识别特征，按 feature_mode(AND/OR) 聚合判断",
                "sub": {
                    # 特征类型：图像存在 / 文本包含
                    "feature_type": {
                        "type": "select",
                        "label": "特征类型",
                        "default": "image_exists",
                        "options": ["image_exists", "text_contains"]
                    },
                    # 特征参数：根据特征类型填充对应字段
                    "params": {
                        "type": "dict",
                        "label": "特征参数",
                        "default": {},
                        "sub": {
                            "template": {
                                "type": "file",
                                "label": "模板图片(image_exists)",
                                "default": ""
                            },
                            "text": {
                                "type": "str",
                                "label": "文本内容(text_contains)",
                                "default": ""
                            },
                            "region": {
                                "type": "str",
                                "label": "识别区域(x,y,w,h)",
                                "default": "",
                                "placeholder": "留空表示全屏"
                            },
                            "threshold": {
                                "type": "slider",
                                "label": "匹配置信度",
                                "default": 0.8,
                                "min": 0,
                                "max": 1
                            }
                        }
                    },
                    # 与上一特征的组合方式（首条特征忽略），缺失时回退到全局 feature_mode
                    "combine_mode": {
                        "type": "select",
                        "label": "与上一特征组合方式",
                        "default": "and",
                        "options": ["and", "or"]
                    },
                    # 结果取反，用于描述"不存在某图/某文本"这类负向特征
                    "negate": {
                        "type": "bool",
                        "label": "结果取反",
                        "default": False
                    }
                }
            },
            # 全局特征组合模式：当单条特征未指定 combine_mode 时使用
            "feature_mode": {
                "type": "select",
                "label": "特征组合模式",
                "default": "and",
                "options": ["and", "or"]
            },
            # 出口列表：描述该页面可前往的目标页面及过图动作，供拓扑地图构建邻接表
            "exits": {
                "type": "list_dict",
                "label": "出口列表",
                "default": [],
                "description": "定义该页面可前往的目标页面及过图动作",
                "sub": {
                    "exit_action": {
                        "type": "str",
                        "label": "出口动作",
                        "default": "",
                        "placeholder": "如：点击商城按钮"
                    },
                    "target_page_id": {
                        "type": "str",
                        "label": "目标页面 ID",
                        "default": ""
                    },
                    "transition_conditions": {
                        "type": "condition_list",
                        "label": "过图前置条件",
                        "default": []
                    }
                }
            }
        }
    }
}
