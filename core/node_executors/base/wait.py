# core/node_executors/base/wait.py
import time

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('wait')
class WaitNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        seconds = params.get('seconds', 1.0)
        context.log(f'等待 {seconds} 秒')
        time.sleep(seconds)

        # ⭐ 支持通过 on_success 灵活控制跳转
        return self.build_jump_result(True, params.get('on_success', {}))
