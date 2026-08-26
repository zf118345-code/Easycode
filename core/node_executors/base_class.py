# core/node_executors/base_class.py
# 节点执行结果构建工具。

from typing import Any


class BaseNodeExecutor:
    """所有节点执行器的基类"""

    default_params: dict[str, Any] = {}

    def execute(self, node, context) -> dict[str, Any]:
        """
        执行节点逻辑
        :param node: Node 对象
        :param context: GraphExecutor 实例（执行上下文）
        :return: dict，必须包含 "success": bool
        """
        raise NotImplementedError()

    @staticmethod
    def build_result(
        success: bool, error: str | None = None, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        统一构建标准节点执行结果。流程跳转只由实体边负责。
        """
        result: dict[str, Any] = {'success': success}
        if error:
            result['error'] = error

        if extra:
            result.update(extra)

        return result

    @staticmethod
    def build_path_result(
        success: bool,
        path: list = None,
        edges: list = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        P1 新增：构建 smart_jump 寻路结果
        :param path: 节点 ID 序列
        :param edges: 经过的边数据序列
        """
        result: dict[str, Any] = {'success': success}
        if error:
            result['error'] = error
        if path is not None:
            result['path'] = path
        if edges is not None:
            result['path_edges'] = edges
        if extra:
            result.update(extra)
        return result
