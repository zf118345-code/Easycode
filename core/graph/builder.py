# core/graph/builder.py
# P1 新增：邻接表构建器
# 从 Project 的 nodes + edges 反向构建邻接表，维护 node_id -> index 映射
# 为 smart_jump 的图论寻路提供 O(1) 查询能力

from collections import defaultdict


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
        # 所有任务组 ID -> 节点 ID 列表
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
    图构建器：从 Project 数据构建邻接表
    同时兼容新版 Edge 列表和旧版 node.params.on_success/on_failure
    """

    @staticmethod
    def build_from_project(project) -> dict[str, AdjacencyGraph]:
        """
        为每个任务组构建独立的邻接表
        :param project: Project 对象
        :return: {task_id: AdjacencyGraph}
        """
        graphs = {}

        for task_id, task in project.tasks.items():
            graph = AdjacencyGraph()

            # 1. 注册所有节点
            for idx, node in enumerate(task.nodes):
                graph.add_node(node.node_id, idx, task_id)

            # 2. 优先从全局 edges 列表添加边
            global_edges = getattr(project, 'edges', [])
            for edge in global_edges:
                if edge.canvas != 'workflow':
                    continue
                # 只添加属于当前任务组的边（源节点在当前任务组中）
                if edge.source_node in graph.node_index_map:
                    graph.add_edge(
                        edge.source_node,
                        edge.target_node,
                        edge.target_task,
                        edge.to_dict() if hasattr(edge, 'to_dict') else {},
                    )

            # 3. 兼容旧版：从 node.on_success/on_failure 添加边
            for node in task.nodes:
                if (
                    node.on_success
                    and node.on_success.target_node
                    and node.on_success.target_node not in [t[0] for t in graph.get_out_edges(node.node_id)]
                ):
                    graph.add_edge(
                        node.node_id,
                        node.on_success.target_node,
                        node.on_success.target,
                        {'source_port': 'success', **node.on_success.to_dict()},
                    )

                if (
                    node.on_failure
                    and node.on_failure.target_node
                    and node.on_failure.target_node not in [t[0] for t in graph.get_out_edges(node.node_id)]
                ):
                    graph.add_edge(
                        node.node_id,
                        node.on_failure.target_node,
                        node.on_failure.target,
                        {'source_port': 'failure', **node.on_failure.to_dict()},
                    )

                # 兼容 branch 节点的 candidates 连线
                candidates = node.params.get('candidates', [])
                if isinstance(candidates, list):
                    for cidx, candidate in enumerate(candidates):
                        if isinstance(candidate, dict):
                            on_success = candidate.get('on_success', {})
                            if on_success and isinstance(on_success, dict):
                                target_node = on_success.get('target_node')
                                target_task = on_success.get('target_task') or on_success.get('target')
                                if target_node and target_node not in [t[0] for t in graph.get_out_edges(node.node_id)]:
                                    graph.add_edge(
                                        node.node_id,
                                        target_node,
                                        target_task,
                                        {'source_port': f'branch_{cidx}', **on_success},
                                    )

            graphs[task_id] = graph

        return graphs

    @staticmethod
    def build_topology_graph(topology_map) -> AdjacencyGraph:
        """
        从拓扑地图构建页面级邻接表
        用于 smart_jump 的页面间寻路
        :param topology_map: TopologyMap 对象
        """
        graph = AdjacencyGraph()

        # 注册所有页面节点
        for idx, node in enumerate(topology_map.nodes):
            graph.add_node(node.page_id, idx, 'topology')

        # 添加拓扑边
        for edge in topology_map.edges:
            graph.add_edge(
                edge.source_page, edge.target_page, None, {'action': edge.action, 'conditions': edge.conditions}
            )

        return graph
