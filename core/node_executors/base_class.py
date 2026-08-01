# core/node_executors/base_class.py

class BaseNodeExecutor:
    default_params = {}

    def execute(self, node, context):
        raise NotImplementedError()

    @staticmethod
    def build_jump_result(success: bool, jump_conf: dict = None, error: str = None, extra: dict = None) -> dict:
        """
        统一构建标准节点执行结果
        自动兼容 type/jump_type 与 target/target_task 的命名不一致问题
        """
        result = {"success": success}
        if error:
            result["error"] = error

        if extra:
            result.update(extra)

        if jump_conf:
            j_type = jump_conf.get("type") or jump_conf.get("jump_type", "next")
            j_target = jump_conf.get("target") or jump_conf.get("target_task", "")
            j_target_node = jump_conf.get("target_node", "")

            result["jump"] = {
                "type": j_type,
                "target": j_target,
                "target_node": j_target_node
            }
        return result