# core/graph/__init__.py
# P1 新增：图论引擎包
# 提供邻接表构建、最短路径计算、环路检测等图论能力
# 为 Batch 4 的 smart_jump 智能寻路与自愈引擎提供底层支撑

from .builder import AdjacencyGraph, GraphBuilder
from .pathfinder import PathFinder, PathResult

__all__ = ['GraphBuilder', 'AdjacencyGraph', 'PathFinder', 'PathResult']
