# core/node_executors/base/variable_op.py
# 变量操作执行器：优先「自由表达式赋值」（new_value），旧版 op_action 字段走历史策略兜底。
import re

from core.expressions import ExpressionError, evaluate_expression
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.variables import VariableTypeRegistry


@NodeExecutorRegistry.register('variable_op')
class VariableOpNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        target_var = self._clean_var_name(params.get('target_var', ''))

        if not target_var:
            context.log('⚠️ [变量操作] 未配置目标变量名')
            return self.build_jump_result(True, params.get('on_success', {}))

        new_value = params.get('new_value')

        # 新版：自由表达式赋值优先（无表达式时旧节点自动回退历史策略）
        if isinstance(new_value, str) and new_value.strip():
            return self._execute_expression(target_var, new_value, params, context)

        # 旧版兼容：op_action 策略字段
        if params.get('op_action'):
            return self._execute_legacy(target_var, params, context)

        context.log(f'⚠️ [变量操作] [{target_var}] 未配置赋值表达式，已跳过')
        return self.build_jump_result(True, params.get('on_success', {}))

    @staticmethod
    def _clean_var_name(raw) -> str:
        """剥离 $var{} / $ctx{} / $env{} / $sys{} 前缀；裸变量名直接用"""
        text = (raw or '').strip()
        m = re.match(r'^\$(?:var|ctx|env|sys)\{([^{}]+)\}$', text)
        if m:
            return m.group(1).strip()
        return text

    def _execute_expression(self, target_var, expr, params, context):
        old_val = context.variables.get(target_var, None)
        try:
            new_val = evaluate_expression(expr, context)
        except ExpressionError as e:
            context.log(f'❌ [变量操作] [{target_var}] 表达式求值失败: {e}')
            return self.build_jump_result(False, params.get('on_failure', {}))

        context.variables[target_var] = new_val
        context.log(f'🔢 [变量操作] $var{{{target_var}}}: {old_val} ──(表达式)──> {new_val}')
        return self.build_jump_result(True, params.get('on_success', {}))

    # ------------------------------------------------------------------ 旧版兼容

    def _execute_legacy(self, target_var, params, context):
        old_val = context.variables.get(target_var, None)
        var_type = params.get('var_type', 'number')
        if old_val is not None:
            var_type = self._infer_var_type(old_val)

        type_handler = VariableTypeRegistry.get(var_type)
        if not type_handler:
            context.log(f'❌ [变量操作] 不支持的数据类型: {var_type}')
            return self.build_jump_result(False, params.get('on_failure', {}))

        new_val = type_handler.execute(var_type, old_val, params, context)

        context.variables[target_var] = new_val
        context.log(f'🔢 [变量操作] [{target_var}]: {old_val} ──({var_type})──> {new_val}')
        return self.build_jump_result(True, params.get('on_success', {}))

    @staticmethod
    def _infer_var_type(value) -> str:
        """按实际值推断变量类型（与全局变量面板类型对应）"""
        if isinstance(value, bool):
            return 'boolean'
        if isinstance(value, (int, float)):
            return 'number'
        if isinstance(value, list):
            return 'list'
        if isinstance(value, dict):
            return 'dict'
        return 'string'