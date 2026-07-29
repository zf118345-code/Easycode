# core/node_executors/log.py
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor

@NodeExecutorRegistry.register("log")
class LogNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        msg = node.params.get("message", "")
        context.log(f"[LOG] {msg}")
        return {"success": True}