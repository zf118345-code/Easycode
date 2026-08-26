# core/graph/builder.py
# 邻接表构建器
# 从 Project 的 nodes + edges 反向构建邻接表，维护 node_id -> index 映射
# 为 smart_jump 的图论寻路提供 O(1) 查询能力

from collections import defaultdict

from core.models import TopologyMap


class AdjacencyGraph:
    """
    有向图邻接表结构
    支持 O(1) 节点索引查询、O(1) 出边查询、环路检测
    """

    def __init__(self):
        # node_id -> node 在 task.nodes 中的索引
        self.node_index_map: dict[str, int] = {}
        # node_id -> [(target_node_id, target_task_id, edge)]
        self.adjacency: dict[str, list[tuple[str, str | None, dict]]] = defaultdict(list)
        # 反向邻接表：node_id -> [source_node_id, ...]
        self.reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        # 所有节点 ID 集合
        self.all_nodes: set[str] = set()
        # 所有流程/页面集合 ID -> 节点 ID 列表
        self.task_nodes: dict[str, list[str]] = defaultdict(list)

    def add_node(self, node_id: str, index: int, task_id: str = ''):
        """注册节点到图中"""
        self.node_index_map[node_id] = index
        self.all_nodes.add(node_id)
        if task_id:
            self.task_nodes[task_id].append(node_id)

    def add_edge(self, source_node: str, target_node: str, target_task: str | None = None, edge_data: dict = None):
        """添加有向边"""
        self.adjacency[source_node].append((target_node, target_task, edge_data or {}))
        self.reverse_adjacency[target_node].append(source_node)
        self.all_nodes.add(source_node)
        self.all_nodes.add(target_node)

    def get_out_edges(self, node_id: str) -> list[tuple[str, str | None, dict]]:
        """获取节点的所有出边"""
        return self.adjacency.get(node_id, [])

    def get_target_index(self, node_id: str) -> int | None:
        """获取节点在 task.nodes 中的索引"""
        return self.node_index_map.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self.all_nodes

    def get_all_nodes(self) -> set[str]:
        return self.all_nodes


class GraphBuilder:
    """
    图构建器：只从 Project.edges 构建邻接表。
    """

    @staticmethod
    def build_from_project(project) -> dict[str, AdjacencyGraph]:
        """
        为每个流程/页面集合构建独立的邻接表。
        :param project: Project 对象
        :return: {task_id: AdjacencyGraph}
        """
        graphs = {}

        for task_id, task in project.tasks.items():
            graph = AdjacencyGraph()

            # 1. 注册所有节点
            for idx, node in enumerate(task.nodes):
                graph.add_node(node.node_id, idx, task_id)

            # 2. 从全局 edges 列表添加边
            global_edges = getattr(project, 'edges', [])
            for edge in global_edges:
                if edge.canvas != 'workflow':
                    continue
            # 只添加属于当前流程/页面集合的边（源节点在当前容器中）
                if edge.source_node in graph.node_index_map:
                    graph.add_edge(
                        edge.source_node,
                        edge.target_node,
                        task_id,
                        edge.to_dict() if hasattr(edge, 'to_dict') else {},
                    )

            graphs[task_id] = graph

        return graphs

    @staticmethod
    def is_popup_node(node) -> bool:
        """Page-level popup identity; operation nodes never opt in directly."""
        return (
            str(getattr(node, 'node_type', '') or '') == 'page_state'
            and bool((getattr(node, 'params', None) or {}).get('is_random_popup', False))
        )

    @staticmethod
    def is_popup_task(task) -> bool:
        return any(GraphBuilder.is_popup_node(node) for node in (getattr(task, 'nodes', None) or []))

    @staticmethod
    def build_topology_graph(topology_map) -> AdjacencyGraph:
        """
        从拓扑地图构建页面级邻接表（主图不含高频随机弹窗页面）
        用于 smart_jump 的页面间寻路
        被页面级开关标记的弹窗页从主图中排除，其关闭动作子图由
        build_popup_graphs 单独构建；同一页面集合中的普通页面仍可寻路。
        :param topology_map: TopologyMap 对象（页面集合：tasks + edges）
        """
        graph = AdjacencyGraph()
        popup_node_ids = set()
        for task in topology_map.tasks:
            explicit = {n.node_id for n in task.nodes if GraphBuilder.is_popup_node(n)}
            popup_node_ids.update(explicit)

        # 建立 node_id -> page 键 的映射（page_id 存于节点 params；无 page_id 的节点用 node_id 兜底）
        page_keys: dict[str, str] = {}
        for idx, node in enumerate(topology_map.iter_nodes()):
            if node.node_id in popup_node_ids:
                continue  # 弹窗节点不入主图
            page_key = TopologyMap.node_page_id(node) or node.node_id
            page_keys[node.node_id] = page_key
            graph.add_node(page_key, idx, 'topology')

        # 添加拓扑边：把 source_node/target_node 解析为 page 键（弹窗节点相关的边忽略）
        for edge in topology_map.edges:
            src_id = edge.get('source_node', '')
            tgt_id = edge.get('target_node', '')
            if src_id in popup_node_ids or tgt_id in popup_node_ids:
                continue
            source_page = page_keys.get(src_id) or topology_map.resolve_page(src_id)
            target_page = page_keys.get(tgt_id) or topology_map.resolve_page(tgt_id)
            if not source_page or not target_page:
                continue
            edge_data = dict(edge)
            edge_data.setdefault('action', edge.get('action', ''))
            edge_data.setdefault('conditions', edge.get('conditions', []))
            graph.add_edge(source_page, target_page, None, edge_data)

        return graph

    @staticmethod
    def build_popup_graphs(topology_map) -> dict[str, AdjacencyGraph]:
        """
        按页面集合构建含高频随机弹窗页的关闭子图：{task_id: AdjacencyGraph}。
        页面级弹窗标记决定是否纳入检测；引擎清场后自动恢复主流程。
        """
        graphs: dict[str, AdjacencyGraph] = {}
        for task in topology_map.tasks:
            if not GraphBuilder.is_popup_task(task):
                continue
            graph = AdjacencyGraph()
            page_keys: dict[str, str] = {}
            for idx, node in enumerate(task.nodes):
                page_key = TopologyMap.node_page_id(node) or node.node_id
                page_keys[node.node_id] = page_key
                graph.add_node(page_key, idx, task.task_id)
            for edge in topology_map.edges:
                src_id = edge.get('source_node', '')
                tgt_id = edge.get('target_node', '')
                if src_id not in page_keys or tgt_id not in page_keys:
                    continue  # 跨组/对外连线忽略
                edge_data = dict(edge)
                edge_data.setdefault('action', edge.get('action', ''))
                edge_data.setdefault('conditions', edge.get('conditions', []))
                graph.add_edge(page_keys[src_id], page_keys[tgt_id], None, edge_data)
            graphs[task.task_id] = graph
        return graphs
