# core/models.py
# 连线是一等公民；持久化边只存在于一张具体画布内。
from dataclasses import dataclass, field
from typing import Any, Optional

from core.registry import NodeExecutorRegistry


@dataclass
class Jump:
    """
    运行时连线路由；target_task 仅用于验证边没有越过当前图。
    """

    target_task: str | None = None  # 目标流程 ID
    target_node: str | None = None  # 目标节点 ID

@dataclass
class Edge:
    """
    连线一等公民实体：唯一 ID、源/目标节点、源端口（success/failure/branch_N）。
    """

    edge_id: str
    source_node: str  # 源节点 ID
    target_node: str  # 目标节点 ID
    source_port: str = 'success'  # 源端口: success / failure / branch_0 / branch_1 ...
    source_port_id: str = ''  # 稳定端口身份；显示顺序变化时保持不变
    label: str = ''  # 连线显示标签
    canvas: str = 'workflow'  # 所属画布: workflow / topology
    routing: dict[str, Any] = field(default_factory=dict)  # IDE 手动转接点；运行时忽略

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Edge']:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            edge_id=d.get('edge_id', ''),
            source_node=d.get('source_node', ''),
            target_node=d.get('target_node', ''),
            source_port=d.get('source_port', 'success'),
            source_port_id=d.get('source_port_id', ''),
            label=d.get('label', ''),
            canvas=d.get('canvas', 'workflow'),
            routing=dict(d.get('routing') or {}),
        )

    def to_dict(self) -> dict:
        payload = {
            'edge_id': self.edge_id,
            'source_node': self.source_node,
            'target_node': self.target_node,
            'source_port': self.source_port,
            'source_port_id': self.source_port_id or self.source_port,
            'label': self.label,
            'canvas': self.canvas,
        }
        if self.routing:
            payload['routing'] = self.routing
        return payload


@dataclass
class Node:
    node_id: str
    node_name: str
    node_type: str
    params: dict[str, Any] = field(default_factory=dict)
    delay_before: int = 0
    loop_count: int = 1  # -1 无限循环
    enabled: bool = True
    position: dict[str, int] | None = None  # 单画布坐标 {x, y}
    size: dict[str, int] | None = None  # 节点尺寸（用于碰撞检测和画布渲染）

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
    """Runtime graph frame.

    This is intentionally not the persisted v3 schema. The loader adapts the
    main graph and every function into these frames so the graph executor can
    stay small and deterministic.
    """
    task_id: str
    task_name: str
    nodes: list[Node] = field(default_factory=list)
    role: str = ''
    description: str = ''
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    local_variables: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    entry_node_id: str | None = None


def _topology_node_from_dict(d: Any) -> Optional['Node']:
    """把当前版拓扑节点字典转换为 Node。"""
    if not d or not isinstance(d, dict) or not d.get('node_id'):
        return None
    return Node(
        node_id=d['node_id'],
        node_name=d.get('node_name', d['node_id']),
        node_type=d['node_type'],
        params=dict(d.get('params') or {}),
        delay_before=d.get('delay_before', 0),
        loop_count=d.get('loop_count', 1),
        enabled=d.get('enabled', True),
        position=d.get('position'),
        size=d.get('size'),
    )


def _topology_node_to_dict(node: 'Node') -> dict:
    return {
        'node_id': node.node_id,
        'node_name': node.node_name,
        'node_type': node.node_type,
        'params': node.params,
        'delay_before': node.delay_before,
        'loop_count': node.loop_count,
        'enabled': node.enabled,
        'position': node.position,
        'size': node.size,
    }


@dataclass
class TopologyMap:
    """Runtime view of the one flat project page map."""

    tasks: list[Task] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any) -> 'TopologyMap':
        if not d or not isinstance(d, dict):
            return cls()
        edges = [dict(edge) for edge in d.get('edges', []) if isinstance(edge, dict)]
        nodes = [n for n in (_topology_node_from_dict(nd) for nd in d.get('nodes', []) or []) if n]
        task = Task(task_id='page_map', task_name='页面地图', nodes=nodes, role='page_map')
        return cls(tasks=[task] if nodes else [], edges=edges)

    def to_dict(self) -> dict:
        return {
            'nodes': [_topology_node_to_dict(node) for node in self.iter_nodes()],
            'edges': [dict(e) for e in self.edges],
        }

    def iter_nodes(self):
        for task in self.tasks:
            for node in task.nodes:
                yield node

    @staticmethod
    def node_page_id(node: 'Node') -> str:
        return (node.params or {}).get('page_id', '') or ''

    def resolve_page(self, ref: str) -> str:
        """把 node_id 或 page_id 统一解析为 page 标识（无法解析时返回 ref 本身）"""
        if not ref:
            return ''
        for node in self.iter_nodes():
            if node.node_id == ref:
                return TopologyMap.node_page_id(node) or ref
        return ref

    def get_node_by_page(self, page_id: str) -> Optional['Node']:
        for node in self.iter_nodes():
            if TopologyMap.node_page_id(node) == page_id:
                return node
        return None

    def get_neighbors(self, page_id: str) -> list[tuple[dict, Optional['Node']]]:
        """获取某页面的所有邻居（用于图论寻路）"""
        result = []
        for edge in self.edges:
            if self.resolve_page(edge.get('source_node', '')) == page_id:
                target_page = self.resolve_page(edge.get('target_node', ''))
                result.append((edge, self.get_node_by_page(target_page)))
        return result


@dataclass
class Project:
    project_name: str = 'default'
    tasks: dict[str, Task] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    # 全局连线列表
    edges: list[Edge] = field(default_factory=list)

    # 拓扑地图蓝图
    topology: TopologyMap = field(default_factory=TopologyMap)

    # UI 状态（与前端同步）
    ui_state: dict[str, Any] = field(default_factory=dict)

    # ⚡ 项目级引擎设置（加载等待/弹窗处理/识别匹配/执行引擎/日志调试，前端「项目设置」可配）
    settings: dict[str, Any] = field(default_factory=dict)
