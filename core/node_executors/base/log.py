# core/node_executors/log.py
import sys
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor


@NodeExecutorRegistry.register("log")
class LogNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        msg = str(params.get("message", ""))
        formatted_msg = msg

        # 1. 变量插值解析（支持 {var_name} 占位符或直接变量名引用）
        if context.variables:
            for var_key, var_val in context.variables.items():
                placeholder = f"{{{var_key}}}"
                if placeholder in formatted_msg:
                    formatted_msg = formatted_msg.replace(placeholder, str(var_val))

            # 如果日志内容填写的直接是某个已存在的变量名，直接输出该变量值
            if msg in context.variables and msg == formatted_msg:
                formatted_msg = str(context.variables[msg])

        full_log_text = f"📝 [LOG] {formatted_msg}"

        # 2. 强行刷新打印到标准控制台（终端/IDE 调试能直接看到）
        print(full_log_text, flush=True)

        # 3. 推送到 ExecutionContext，供前端 SSE 日志面板实时推送
        context.log(full_log_text)

        # 4. 返回标准跳转元数据，保证图执行器能推导走向下一个节点
        return self.build_jump_result(True, params.get("on_success", {}))