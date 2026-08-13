# core/graph/pathfinder.py
# P1 新增：图论寻路引擎
# 实现 BFS 最短路径算法，支持环路检测、访问计数、动态避障
# 为 Batch 4 的 smart_jump 提供"最短动作序列"计算能力

from typing import List, Optional, Dict, Set, Tuple
from collections import deque
from .builder import AdjacencyGraph


class PathResult:
    """寻路结果封装"""

    def __init__(self, success: bool, path: List[str] = None,
                 edges: List[dict] = None, reason: str = ""):
        self.success = success
        self.path = path or []          # 节点 ID 序列
        self.edges = edges or []         # 经过的边数据序列
        self.reason = reason             # 失败原因或额外信息

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "path": self.path,
            "edges": self.edges,
            "reason": self.reason
        }

    def __bool__(self):
        return self.success


class PathFinder:
    """
    图论寻路引擎
    支持 BFS 最短路径、环路检测、动态避障节点
    """

    # 单节点最大访问次数（防止环路死循环）
    MAX_VISITS_PER_NODE = 10
    # 寻路最大深度（防止图过大时性能问题）
    MAX_SEARCH_DEPTH = 100

    @staticmethod
    def find_shortest_path(graph: AdjacencyGraph,
                           source: str,
                           target: str,
                           avoid_nodes: Set[str] = None) -> PathResult:
        """
        BFS 最短路径算法
        :param graph: 邻接表
        :param source: 起始节点 ID
        :param target: 目标节点 ID
        :param avoid_nodes: 需要避开的节点集合（如已知弹窗阻碍）
        :return: PathResult
        """
        if not graph.has_node(source):
            return PathResult(False, reason=f"起始节点不存在: {source}")
        if not graph.has_node(target):
            return PathResult(False, reason=f"目标节点不存在: {target}")

        if source == target:
            return PathResult(True, path=[source], edges=[], reason="已在目标节点")

        avoid = avoid_nodes or set()

        # BFS 队列: (当前节点, 路径, 经过的边)
        queue = deque([(source, [source], [])])
        visited: Set[str] = {source}

        depth = 0
        while queue and depth < PathFinder.MAX_SEARCH_DEPTH:
            depth += 1
            level_size = len(queue)

            for _ in range(level_size):
                current, path, edges_data = queue.popleft()

                for target_node, target_task, edge_data in graph.get_out_edges(current):
                    if target_node in avoid:
                        continue
                    if target_node in visited:
                        continue

                    new_path = path + [target_node]
                    new_edges = edges_data + [edge_data]

                    if target_node == target:
                        return PathResult(
                            True,
                            path=new_path,
                            edges=new_edges,
                            reason=f"找到最短路径，共 {len(new_path)} 步"
                        )

                    visited.add(target_node)
                    queue.append((target_node, new_path, new_edges))

        return PathResult(False, reason=f"未找到从 {source} 到 {target} 的路径")

    @staticmethod
    def find_path_with_conditions(graph: AdjacencyGraph,
                                   source: str,
                                   target: str,
                                   condition_checker=None,
                                   avoid_nodes: Set[str] = None) -> PathResult:
        """
        带条件检查的寻路：每条边可以携带条件，只有条件满足时才可通行
        :param condition_checker: callable(edge_data, context) -> bool
        """
        if not graph.has_node(source):
            return PathResult(False, reason=f"起始节点不存在: {source}")
        if not graph.has_node(target):
            return PathResult(False, reason=f"目标节点不存在: {target}")

        if source == target:
            return PathResult(True, path=[source], edges=[], reason="已在目标节点")

        avoid = avoid_nodes or set()
        queue = deque([(source, [source], [])])
        visited: Set[str] = {source}
        depth = 0

        while queue and depth < PathFinder.MAX_SEARCH_DEPTH:
            depth += 1
            level_size = len(queue)

            for _ in range(level_size):
                current, path, edges_data = queue.popleft()

                for target_node, target_task, edge_data in graph.get_out_edges(current):
                    if target_node in avoid:
                        continue
                    if target_node in visited:
                        continue

                    # 条件检查
                    if condition_checker and not condition_checker(edge_data, None):
                        continue

                    new_path = path + [target_node]
                    new_edges = edges_data + [edge_data]

                    if target_node == target:
                        return PathResult(
                            True,
                            path=new_path,
                            edges=new_edges,
                            reason=f"找到条件路径，共 {len(new_path)} 步"
                        )

                    visited.add(target_node)
                    queue.append((target_node, new_path, new_edges))

        return PathResult(False, reason=f"未找到从 {source} 到 {target} 的条件路径")

    @staticmethod
    def detect_cycle(graph: AdjacencyGraph) -> Optional[List[str]]:
        """
        环路检测：使用 DFS 三色标记法
        :return: 如果存在环，返回环上的节点序列；否则返回 None
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in graph.all_nodes}
        parent: Dict[str, str] = {}

        def dfs(node):
            color[node] = GRAY
            for target_node, _, _ in graph.get_out_edges(node):
                if color.get(target_node, WHITE) == GRAY:
                    # 找到环，回溯环路径
                    cycle = [target_node]
                    curr = node
                    while curr != target_node and curr in parent:
                        cycle.append(curr)
                        curr = parent[curr]
                    cycle.append(target_node)
                    cycle.reverse()
                    return cycle
                if color.get(target_node, WHITE) == WHITE:
                    parent[target_node] = node
                    result = dfs(target_node)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for node in graph.all_nodes:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result

        return None

    @staticmethod
    def find_all_reachable(graph: AdjacencyGraph, source: str) -> Set[str]:
        """获取从 source 可达的所有节点"""
        if not graph.has_node(source):
            return set()

        visited: Set[str] = set()
        queue = deque([source])
        visited.add(source)

        while queue:
            current = queue.popleft()
            for target_node, _, _ in graph.get_out_edges(current):
                if target_node not in visited:
                    visited.add(target_node)
                    queue.append(target_node)

        visited.discard(source)  # 不包含自身
        return visited
