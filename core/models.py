# core/models.py
# P1 重构：连线升格为一等公民（Edge），Node 支持多画布坐标，Project 扩展拓扑层
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from core.registry import NodeExecutorRegistry


@dataclass
class Jump:
    """
    连线驱动 Jump 模型：通过 target（目标任务组）与 target_node（目标节点）进行精确图路由
    兼容旧版 type/jump_type 字段但不再依赖它们
    """
    target: Optional[str] = None        # 目标任务组 ID
    target_node: Optional[str] = None   # 目标节点 ID
    return_on_complete: bool = False

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Jump']:
        if not d or not isinstance(d, dict):
            return None
        target_node = d.get("target_node")
        target_task = d.get("target_task") or d.get("target")

        # 无连线指向时返回 None，代表流程终点
        if not target_node and not target_task:
            return None

        return cls(
            target=target_task,
            target_node=target_node,
            return_on_complete=d.get("return_on_complete", False)
        )

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "target_node": self.target_node,
            "return_on_complete": self.return_on_complete
        }


@dataclass
class Edge:
    """
    P1 新增：连线一等公民实体
    拥有唯一 ID、源/目标节点、源端口（success/failure/branch_N）、可选条件、样式
    替代之前寄生在 node.params 中的 on_success/on_failure
    """
    edge_id: str
    source_node: str                          # 源节点 ID
    target_node: str                          # 目标节点 ID
    target_task: Optional[str] = None         # 目标任务组（跨任务连线时使用）
    source_port: str = "success"              # 源端口: success / failure / branch_0 / branch_1 ...
    condition: Optional[Dict[str, Any]] = None  # 连线绑定的条件（用于条件路由）
    return_on_complete: bool = False          # 跨任务跳转完成后是否返回
    label: str = ""                           # 连线显示标签
    canvas: str = "workflow"                  # 所属画布: workflow / topology

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Edge']:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            edge_id=d.get("edge_id", ""),
            source_node=d.get("source_node", ""),
            target_node=d.get("target_node", ""),
            target_task=d.get("target_task") or d.get("target"),
            source_port=d.get("source_port", "success"),
            condition=d.get("condition"),
            return_on_complete=d.get("return_on_complete", False),
            label=d.get("label", ""),
            canvas=d.get("canvas", "workflow")
        )

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "target_task": self.target_task,
            "source_port": self.source_port,
            "condition": self.condition,
            "return_on_complete": self.return_on_complete,
            "label": self.label,
            "canvas": self.canvas
        }


@dataclass
class Node:
    node_id: str
    node_name: str
    node_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    delay_before: int = 0
    loop_count: int = 1               # -1 无限循环
    enabled: bool = True
    on_success: Optional[Jump] = None  # 兼容旧版：成功跳转
    on_failure: Optional[Jump] = None  # 兼容旧版：失败跳转
    position: Optional[Dict[str, int]] = None  # 兼容旧版：单画布坐标 {x, y}

    # P1 新增：多画布坐标支持，key 为画布类型 ("workflow" / "topology")
    positions: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # P1 新增：节点尺寸（用于碰撞检测和画布渲染）
    size: Optional[Dict[str, int]] = None
    # P1 新增：节点所属画布列表
    canvas_ids: List[str] = field(default_factory=lambda: ["workflow"])

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

    def get_position(self, canvas: str = "workflow") -> Optional[Dict[str, int]]:
        """获取指定画布上的节点坐标，优先从 positions 取，降级到旧版 position"""
        if self.positions and canvas in self.positions:
            return self.positions[canvas]
        if canvas == "workflow" and self.position:
            return self.position
        return None

    def set_position(self, canvas: str, pos: Dict[str, int]):
        """设置指定画布上的节点坐标"""
        if not self.positions:
            self.positions = {}
        self.positions[canvas] = pos
        # 同步旧版 position 字段
        if canvas == "workflow":
            self.position = pos


@dataclass
class Task:
    task_id: str
    task_name: str
    loop_count: int = 1
    loop_interval: int = 0
    nodes: List[Node] = field(default_factory=list)


@dataclass
class TopologyNode:
    """
    P1 新增：拓扑画布的页面状态节点
    对应 Batch 3 的 page_state，定义"页面长什么样"
    """
    node_id: str
    node_name: str
    page_id: str = ""                        # 页面唯一标识（如 "shop", "dungeon_entrance"）
    features: List[Dict[str, Any]] = field(default_factory=list)  # 复合特征列表 (AND/OR)
    feature_mode: str = "and"                # 特征组合模式: and / or
    position: Optional[Dict[str, int]] = None
    exits: List[Dict[str, Any]] = field(default_factory=list)     # 出口列表（动作 + 目标 page_id）

    @classmethod
    def from_dict(cls, d: Any) -> Optional['TopologyNode']:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            node_id=d.get("node_id", ""),
            node_name=d.get("node_name", ""),
            page_id=d.get("page_id", ""),
            features=d.get("features", []),
            feature_mode=d.get("feature_mode", "and"),
            position=d.get("position"),
            exits=d.get("exits", [])
        )

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "page_id": self.page_id,
            "features": self.features,
            "feature_mode": self.feature_mode,
            "position": self.position,
            "exits": self.exits
        }


@dataclass
class TopologyEdge:
    """
    P1 新增：拓扑画布的连线
    描述页面之间的互通关系（如：商城 -> 主城 -> 副本入口）
    """
    edge_id: str
    source_page: str         # 源页面 ID
    target_page: str         # 目标页面 ID
    action: str = ""         # 过图动作描述
    conditions: List[Dict[str, Any]] = field(default_factory=list)  # 过图前置条件

    @classmethod
    def from_dict(cls, d: Any) -> Optional['TopologyEdge']:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            edge_id=d.get("edge_id", ""),
            source_page=d.get("source_page", ""),
            target_page=d.get("target_page", ""),
            action=d.get("action", ""),
            conditions=d.get("conditions", [])
        )

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_page": self.source_page,
            "target_page": self.target_page,
            "action": self.action,
            "conditions": self.conditions
        }


@dataclass
class TopologyMap:
    """
    P1 新增：拓扑地图蓝图数据结构
    Batch 1 中引入的"专属拓扑地图蓝图数据结构"
    """
    nodes: List[TopologyNode] = field(default_factory=list)
    edges: List[TopologyEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any) -> 'TopologyMap':
        if not d or not isinstance(d, dict):
            return cls()
        nodes = [TopologyNode.from_dict(n) for n in d.get("nodes", []) if n]
        edges = [TopologyEdge.from_dict(e) for e in d.get("edges", []) if e]
        return cls(nodes=nodes, edges=edges)

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges]
        }

    def get_node_by_page(self, page_id: str) -> Optional[TopologyNode]:
        for n in self.nodes:
            if n.page_id == page_id:
                return n
        return None

    def get_neighbors(self, page_id: str) -> List[tuple[TopologyEdge, TopologyNode]]:
        """获取某页面的所有邻居（用于图论寻路）"""
        result = []
        for edge in self.edges:
            if edge.source_page == page_id:
                target_node = self.get_node_by_page(edge.target_page)
                if target_node:
                    result.append((edge, target_node))
        return result


@dataclass
class Project:
    project_name: str = "default"
    tasks: Dict[str, Task] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)

    # P1 新增：全局连线列表（替代寄生在 params 中的 on_success/on_failure）
    edges: List[Edge] = field(default_factory=list)

    # P1 新增：拓扑地图蓝图
    topology: TopologyMap = field(default_factory=TopologyMap)

    # P1 新增：UI 状态（与前端同步）
    ui_state: Dict[str, Any] = field(default_factory=dict)
