# core/node_executors/base_class.py
# P0 修正：any -> Any 类型标注，统一 build_jump_result 逻辑
# P1 增强：新增 build_path_result 用于 smart_jump 寻路结果

from typing import Any


class BaseNodeExecutor:
    """所有节点执行器的基类"""

    default_params: dict[str, Any] = {}

    def execute(self, node, context) -> dict[str, Any]:
        """
        执行节点逻辑
        :param node: Node 对象
        :param context: GraphExecutor 实例（执行上下文）
        :return: dict，必须包含 "success": bool，可选 "jump": dict
        """
        raise NotImplementedError()

    @staticmethod
    def build_jump_result(
        success: bool, jump_conf: Any = None, error: str | None = None, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        统一构建标准节点执行结果
        自动兼容 Jump 对象与 Dict 结构，确保跳转不中断
        P0 修正：any -> Any 类型标注
        """
        result: dict[str, Any] = {'success': success}
        if error:
            result['error'] = error

        if extra:
            result.update(extra)

        if jump_conf:
            jump_dict: dict[str, Any] = {}

            # 优先处理 Jump dataclass 对象（P1 统一：使用 to_dict 方法）
            if hasattr(jump_conf, 'to_dict') and callable(jump_conf.to_dict):
                jump_dict = jump_conf.to_dict()
            elif isinstance(jump_conf, dict):
                # 兼容字典结构
                jump_dict = {
                    'target': jump_conf.get('target') or jump_conf.get('target_task'),
                    'target_node': jump_conf.get('target_node'),
                    'return_on_complete': jump_conf.get('return_on_complete', False),
                }
            else:
                # 兼容旧版对象属性
                jump_dict = {
                    'target': getattr(jump_conf, 'target', None),
                    'target_node': getattr(jump_conf, 'target_node', None),
                    'return_on_complete': getattr(jump_conf, 'return_on_complete', False),
                }

            # 只有 target_node 有值时才写入 jump
            if jump_dict.get('target_node'):
                result['jump'] = jump_dict

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
