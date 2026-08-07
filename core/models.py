# core/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from core.registry import NodeExecutorRegistry

@dataclass
class Jump:
    type: str = "next"
    target: Optional[str] = None
    target_node: Optional[str] = None
    return_on_complete: bool = False

@dataclass
class Node:
    node_id: str                    # 唯一标识，自动生成
    node_name: str                  # 用户自定义名称
    node_type: str                  # 节点类型
    params: Dict[str, Any] = field(default_factory=dict) # 参数
    delay_before: int = 0           # 执行前等待（毫秒）
    loop_count: int = 1             # 循环次数（-1 无限）
    enabled: bool = True
    on_success: Optional[Jump] = None  # ⭐ 补上成功跳转字段
    on_failure: Optional[Jump] = None  # ⭐ 补上失败跳转字段
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