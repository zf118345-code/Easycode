# core/node_executors/base/variable_op.py
# 变量操作执行器：使用自由表达式 new_value 赋值。
import re

from core.expressions import ExpressionError, evaluate_expression
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('variable_op')
class VariableOpNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        raw_target = str(params.get('target_var', '') or '').strip()
        target_var = self._clean_var_name(raw_target)

        if not target_var:
            if raw_target:
                context.log(f' [变量操作] 写入目标只支持 $var、$ctx 或函数内的 $local: {raw_target}')
                return self.build_result(False)
            context.log(' [变量操作] 未配置目标变量名')
            return self.build_result(True)

        new_value = params.get('new_value')

        if isinstance(new_value, str) and new_value.strip():
            return self._execute_expression(target_var, raw_target or f'$var{{{target_var}}}', new_value, context)

        context.log(f' [变量操作] [{target_var}] 未配置赋值表达式，已跳过')
        return self.build_result(True)

    @staticmethod
    def _clean_var_name(raw) -> str:
        """剥离 $var{} 前缀；裸变量名直接使用。"""
        text = (raw or '').strip()
        m = re.match(r'^\$(var|ctx|local)\{([^{}]+)\}$', text)
        if m:
            namespace, name = m.group(1), m.group(2).strip()
            return f'__local__:{name}' if namespace == 'local' else name
        dotted = re.match(r'^\$local\.([A-Za-z_][A-Za-z0-9_]*)$', text)
        if dotted:
            return f'__local__:{dotted.group(1)}'
        if text.startswith(('$param.', '$param{', '$env.', '$env{', '$sys.', '$sys{')):
            return ''  # parameters and environment/system values are read-only
        if text.startswith('$'):
            return ''
        return text

    def _execute_expression(self, target_var, display_target, expr, context):
        old_val = context.variables.get(target_var, None)
        try:
            new_val = evaluate_expression(expr, context)
        except ExpressionError as e:
            context.log(f' [变量操作] [{target_var}] 表达式求值失败: {e}')
            return self.build_result(False)

        context.variables[target_var] = new_val
        context.log(f' [变量操作] {display_target}: {old_val} -> {new_val}')
        return self.build_result(True)
