# core/node_executors/base_class.py

class BaseNodeExecutor:
    default_params = {}

    def execute(self, node, context):
        raise NotImplementedError()

    @staticmethod
    def build_jump_result(success: bool, jump_conf: any = None, error: str = None, extra: dict = None) -> dict:
        """
        统一构建标准节点执行结果
        自动兼容 Jump 对象与 Dict 结构，确保跳转不中断
        """
        result = {"success": success}
        if error:
            result["error"] = error

        if extra:
            result.update(extra)

        if jump_conf:
            # 兼容对象属性与字典键值
            if hasattr(jump_conf, 'type'):
                j_type = getattr(jump_conf, 'type', 'next')
                j_target = getattr(jump_conf, 'target', '')
                j_target_node = getattr(jump_conf, 'target_node', '')
            elif isinstance(jump_conf, dict):
                j_type = jump_conf.get("type") or jump_conf.get("jump_type", "next")
                j_target = jump_conf.get("target") or jump_conf.get("target_task", "")
                j_target_node = jump_conf.get("target_node", "")
            else:
                j_type, j_target, j_target_node = "next", "", ""

            result["jump"] = {
                "type": j_type,
                "target": j_target,
                "target_node": j_target_node
            }
        return result