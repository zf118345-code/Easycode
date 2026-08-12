# core/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from core.registry import NodeExecutorRegistry


@dataclass
class Jump:
    """
    ⚡ 纯连线驱动 Jump 模型：彻底废弃 type/jump_type 概念
    仅通过 target（目标任务组）与 target_node（目标节点）进行精确图路由
    """
    target: Optional[str] = None  # 目标任务组 ID (target_task)
    target_node: Optional[str] = None  # 目标节点 ID (target_node)
    return_on_complete: bool = False

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Jump']:
        if not d or not isinstance(d, dict):
            return None
        target_node = d.get("target_node")
        target_task = d.get("target_task") or d.get("target")

        # ⚡ 无连线指向时，直接返回 None，代表流程终点
        if not target_node and not target_task:
            return None

        return cls(
            target=target_task,
            target_node=target_node,
            return_on_complete=d.get("return_on_complete", False)
        )


@dataclass
class Node:
    node_id: str  # 唯一标识
    node_name: str  # 用户自定义名称
    node_type: str  # 节点类型
    params: Dict[str, Any] = field(default_factory=dict)  # 参数
    delay_before: int = 0  # 执行前等待（毫秒）
    loop_count: int = 1  # 循环次数（-1 无限）
    enabled: bool = True
    on_success: Optional[Jump] = None  # 成功跳转
    on_failure: Optional[Jump] = None  # 失败跳转
    position: Optional[Dict[str, int]] = None

    @staticmethod
    def get_defaults(node_type):
        return NodeExecutorRegistry.get_defaults(node_type)

    def merge_defaults(self):
        defaults = self.get_defaults(self.node_type)

        def merge(d, default):
            for k, v in default.items():
                if k not in d:
                    d[k] = v
                elif isinstance(v, dict) and isinstance(d.get(k), dict):
                    merge(d[k], v)

        merge(self.params, defaults)


@dataclass
class Task:
    task_id: str
    task_name: str
    loop_count: int = 1
    loop_interval: int = 0
    nodes: List[Node] = field(default_factory=list)


@dataclass
class Project:
    project_name: str = "default"
    tasks: Dict[str, Task] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)