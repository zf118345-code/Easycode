# core/node_executors/log.py
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('log')
class LogNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        msg = str(params.get('message', ''))
        # 变量插值只接受统一表达式（$var{name} / $ctx{name} / $env{name}）。
        formatted_msg = str(context.parse_expr(msg))

        full_log_text = f' [LOG] {formatted_msg}'

        # 统一由 ExecutionContext 输出和转发。控制台只是观测副本，不能因为
        # Windows GBK/失效句柄无法编码 Emoji 而让一个日志节点执行失败。
        context.log(full_log_text)

        # 返回标准结果，图执行器根据实体边决定下一节点。
        return self.build_result(True)
