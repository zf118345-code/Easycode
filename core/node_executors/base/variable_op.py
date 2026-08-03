# core/node_executors/base/variable_op.py
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor


@NodeExecutorRegistry.register("variable_op")
class VariableOpNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        var_name = params.get("var_name", "").strip()
        op_type = params.get("op_type", "set")  # set | add | sub | mul | div | clear
        value = params.get("value", "")

        if not var_name:
            context.log("❌ [变量操作] 未指定变量名称", "error")
            return {"success": False, "error": "var_name missing"}

        old_val = context.variables.get(var_name, 0)

        try:
            if op_type == "set":
                new_val = value
            elif op_type in ("add", "sub", "mul", "div"):
                num_old = float(old_val) if str(old_val).replace('.', '', 1).isdigit() else 0.0
                num_val = float(value) if str(value).replace('.', '', 1).isdigit() else 0.0

                if op_type == "add": new_val = num_old + num_val
                elif op_type == "sub": new_val = num_old - num_val
                elif op_type == "mul": new_val = num_old * num_val
                elif op_type == "div": new_val = num_old / num_val if num_val != 0 else num_old

                # 如果是整型则转整数
                if isinstance(new_val, float) and new_val.is_integer():
                    new_val = int(new_val)
            elif op_type == "clear":
                context.variables.pop(var_name, None)
                context.log(f"🧹 [变量操作] 已清空变量 [{var_name}]")
                return {"success": True}

            context.variables[var_name] = new_val
            context.log(f"🔢 [变量操作] [{var_name}]: {old_val} ──({op_type} {value})──> {new_val}")
            return {"success": True}
        except Exception as e:
            context.log(f"💥 [变量操作异常]: {e}", "error")
            return {"success": False, "error": str(e)}