# core/models.py
# P1 重构：连线升格为一等公民（Edge），拓扑层任务组化（TopologyMap = tasks + edges）
from dataclasses import dataclass, field
from typing import Any, Optional

from core.registry import NodeExecutorRegistry


@dataclass
class Jump:
    """
    连线驱动 Jump 模型：通过 target（目标任务组）与 target_node（目标节点）进行精确图路由
    """

    target: str | None = None  # 目标任务组 ID
    target_node: str | None = None  # 目标节点 ID
    return_on_complete: bool = False

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Jump']:
        if not d or not isinstance(d, dict):
            return None
        target_node = d.get('target_node')
        target_task = d.get('target_task') or d.get('target')

        # 无连线指向时返回 None，代表流程终点
        if not target_node and not target_task:
            return None

        return cls(target=target_task, target_node=target_node, return_on_complete=d.get('return_on_complete', False))

    def to_dict(self) -> dict:
        return {'target': self.target, 'target_node': self.target_node, 'return_on_complete': self.return_on_complete}


@dataclass
class Edge:
    """
    连线一等公民实体：唯一 ID、源/目标节点、源端口（success/failure/branch_N）
    替代之前寄生在 node.params 中的 on_success/on_failure
    """

    edge_id: str
    source_node: str  # 源节点 ID
    target_node: str  # 目标节点 ID
    target_task: str | None = None  # 目标任务组（跨任务连线时使用）
    source_port: str = 'success'  # 源端口: success / failure / branch_0 / branch_1 ...
    return_on_complete: bool = False  # 跨任务跳转完成后是否返回
    label: str = ''  # 连线显示标签
    canvas: str = 'workflow'  # 所属画布: workflow / topology

    @classmethod
    def from_dict(cls, d: Any) -> Optional['Edge']:
        if not d or not isinstance(d, dict):
            return None
        return cls(
            edge_id=d.get('edge_id', ''),
            source_node=d.get('source_node', ''),
            target_node=d.get('target_node', ''),
            target_task=d.get('target_task') or d.get('target'),
            source_port=d.get('source_port', 'success'),
            return_on_complete=d.get('return_on_complete', False),
            label=d.get('label', ''),
            canvas=d.get('canvas', 'workflow'),
        )

    def to_dict(self) -> dict:
        return {
            'edge_id': self.edge_id,
            'source_node': self.source_node,
            'target_node': self.target_node,
            'target_task': self.target_task,
            'source_port': self.source_port,
            'return_on_complete': self.return_on_complete,
            'label': self.label,
            'canvas': self.canvas,
        }


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
    task_id: str
    task_name: str
    loop_count: int = 1
    loop_interval: int = 0
    nodes: list[Node] = field(default_factory=list)


def _topology_node_from_dict(d: Any) -> Optional['Node']:
    """拓扑节点 dict -> Node（新格式 node_type+params；兼容旧版扁平字段，折叠进 params，原 params 值优先）"""
    if not d or not isinstance(d, dict) or not d.get('node_id'):
        return None
    params = dict(d.get('params') or {})
    for key, default in (('page_id', ''), ('features', []), ('feature_mode', 'and'), ('exits', [])):
        if key not in params and key in d:
            params[key] = d.get(key, default)
    return Node(
        node_id=d['node_id'],
        node_name=d.get('node_name', d['node_id']),
        node_type=d.get('node_type') or d.get('type') or 'page_state',
        params=params,
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


def _normalize_topology_edge(d: dict) -> dict:
    """拓扑连线统一为 source_node/target_node 键名，兼容旧 source/target 与 source_page/target_page"""
    e = dict(d)
    e.setdefault('edge_id', '')
    e.setdefault('source_node', d.get('source') or d.get('source_page') or '')
    e.setdefault('target_node', d.get('target') or d.get('target_page') or '')
    e.setdefault('canvas', 'topology')
    return e


@dataclass
class TopologyMap:
    """
    拓扑地图蓝图：任务组化结构（与 workflow.json 同形）
    tasks 内为拓扑节点（page_state 等，页面数据存于 params），edges 为 {source_node, target_node, canvas: 'topology'} 连线
    兼容读取旧版扁平 {nodes, edges} 结构
    """

    tasks: list[Task] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any) -> 'TopologyMap':
        if not d or not isinstance(d, dict):
            return cls()
        edges = [_normalize_topology_edge(e) for e in d.get('edges', []) if isinstance(e, dict)]
        if 'tasks' in d:
            tasks = []
            for task_data in d.get('tasks', []) or []:
                if not isinstance(task_data, dict):
                    continue
                nodes = [n for n in (_topology_node_from_dict(nd) for nd in task_data.get('nodes', []) or []) if n]
                tasks.append(
                    Task(
                        task_id=task_data.get('task_id', 'task_topology'),
                        task_name=task_data.get('task_name', '拓扑地图'),
                        loop_count=task_data.get('loop_count', 1),
                        loop_interval=task_data.get('loop_interval', 0),
                        nodes=nodes,
                    )
                )
            return cls(tasks=tasks, edges=edges)
        # 旧版扁平结构：nodes 折进默认任务组
        nodes = [n for n in (_topology_node_from_dict(nd) for nd in d.get('nodes', []) or []) if n]
        tasks = [
            Task(task_id='task_topology', task_name='拓扑地图', loop_count=1, loop_interval=0, nodes=nodes)
        ]
        return cls(tasks=tasks, edges=edges)

    def to_dict(self) -> dict:
        return {
            'tasks': [
                {
                    'task_id': t.task_id,
                    'task_name': t.task_name,
                    'loop_count': t.loop_count,
                    'loop_interval': t.loop_interval,
                    'nodes': [_topology_node_to_dict(n) for n in t.nodes],
                }
                for t in self.tasks
            ],
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

    # P1 新增：全局连线列表（替代寄生在 params 中的 on_success/on_failure）
    edges: list[Edge] = field(default_factory=list)

    # P1 新增：拓扑地图蓝图
    topology: TopologyMap = field(default_factory=TopologyMap)

    # P1 新增：UI 状态（与前端同步）
    ui_state: dict[str, Any] = field(default_factory=dict)
