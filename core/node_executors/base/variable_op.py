# core/node_executors/variable_op.py
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.variables import VariableTypeRegistry


@NodeExecutorRegistry.register('variable_op')
class VariableOpNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        target_var = params.get('target_var', '').strip()
        var_type = params.get('var_type', 'number')

        if not target_var:
            context.log('⚠️ [变量操作] 未配置目标变量名')
            return self.build_jump_result(True, params.get('on_success', {}))

        # 1. 查找对应的类型策略类
        type_handler = VariableTypeRegistry.get(var_type)
        if not type_handler:
            context.log(f'❌ [变量操作] 不支持的数据类型: {var_type}')
            return self.build_jump_result(False, params.get('on_success', {}))

        # 2. 读取旧值并委托给具体的策略类处理
        old_val = context.variables.get(target_var, None)
        new_val = type_handler.execute(var_type, old_val, params, context)

        # 3. 写回全局上下文并打日志
        context.variables[target_var] = new_val
        context.log(f'🔢 [变量操作] [{target_var}]: {old_val} ──({var_type})──> {new_val}')

        return self.build_jump_result(True, params.get('on_success', {}))
