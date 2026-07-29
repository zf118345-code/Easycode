# core/node_executors/wait.py
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
import time

@NodeExecutorRegistry.register("wait")
class WaitNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        seconds = node.params.get("seconds", 1.0)
        context.log(f"等待 {seconds} 秒")
        time.sleep(seconds)
        return {"success": True}