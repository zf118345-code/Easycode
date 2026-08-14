import importlib

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('script_call')
class ScriptCallNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        script_name = params.get('script', '').strip()
        entry_func = params.get('entry', '').strip()
        return_on_complete = params.get('return_on_complete', False)

        if not script_name:
            context.log('script_call 缺少 script 参数', 'error')
            return {'success': False, 'error': 'missing script name'}

        # 尝试导入脚本模块
        try:
            # 假设脚本放在 scripts/ 目录下
            module = importlib.import_module(f'scripts.{script_name}')
        except ImportError as e:
            context.log(f'无法导入脚本 {script_name}: {e}', 'error')
            return {'success': False, 'error': f'script not found: {script_name}'}

        # 如果指定了入口函数，则调用；否则调用默认的 run 或 main
        if entry_func:
            func = getattr(module, entry_func, None)
        else:
            func = getattr(module, 'run', None) or getattr(module, 'main', None)

        if func is None:
            context.log(f'脚本 {script_name} 中未找到入口函数', 'error')
            return {'success': False, 'error': 'entry function not found'}

        try:
            # 将 context 传递给脚本，方便其访问变量和日志
            result = func(context)
            if result is None:
                result = {'success': True}
            elif isinstance(result, bool):
                result = {'success': result}
            elif not isinstance(result, dict):
                result = {'success': True, 'result': result}
        except Exception as e:
            context.log(f'脚本执行异常: {e}', 'error')
            return {'success': False, 'error': str(e)}

        # 如果 return_on_complete 为 True，则返回跳转类型为 end 或继续？
        # 实际跳转由 on_success/on_failure 控制，这里只需返回结果
        if return_on_complete:
            # 脚本执行完成后希望整个任务结束或返回，可以在 on_success 中设置跳转
            # 这里我们添加一个标志，但执行器不直接处理跳转
            context.log('脚本执行完成，return_on_complete=True，将由 on_success 控制后续')
        return result
