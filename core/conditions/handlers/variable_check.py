# core/conditions/handlers/variable_check.py
import re
from typing import Any
from core.conditions.base import BaseConditionEvaluator, ConditionRegistry
from core.utils import resolve_template_string


@ConditionRegistry.register("variable_check")
class VariableCheckEvaluator(BaseConditionEvaluator):

    @classmethod
    def evaluate(cls, params: dict, context: Any) -> bool:
        # ⚡ 兼容 variable_name / var_name 两种 Key
        raw_var_name = str(params.get("variable_name") or params.get("var_name", "")).strip()
        operator = str(params.get("operator", "eq"))
        # ⚡ 兼容 compare_value / target_value 两种 Key
        raw_target_val = params.get("compare_value") if params.get("compare_value") is not None else params.get("target_value", "")

        if not raw_var_name:
            return False

        # 清洗变量名中的 {$var.xxx} 或 {xxx} 包装
        clean_var_name = re.sub(r'^\{?(\$var\.)?([^}]+)\}?$', r'\2', raw_var_name)

        # 1. 获取变量实际值
        var_val = None
        if hasattr(context, 'variables') and isinstance(context.variables, dict):
            var_val = context.variables.get(clean_var_name, None)

        # 2. 特殊无目标值判定
        if operator in ("is_true", "true"): return bool(var_val) is True
        if operator in ("is_false", "false"): return bool(var_val) is False
        if operator in ("is_empty", "empty"):
            return var_val is None or var_val == "" or var_val == [] or var_val == {}
        if operator in ("is_not_empty", "not_empty"):
            return var_val is not None and var_val != "" and var_val != [] and var_val != {}

        # 3. 统一使用模板替换引擎求值 target_val
        target_val = resolve_template_string(str(raw_target_val), context)

        # 4. 数值类型转换比较 (优先尝试转 float 进行精确比较)
        try:
            if var_val is not None and target_val is not None:
                num_var = float(var_val)
                num_target = float(target_val)
                if operator == "eq": return num_var == num_target
                if operator == "ne": return num_var != num_target
                if operator == "gt": return num_var > num_target
                if operator in ("gte", "ge"): return num_var >= num_target
                if operator == "lt": return num_var < num_target
                if operator in ("lte", "le"): return num_var <= num_target
        except (ValueError, TypeError):
            pass

        # 5. 字符串类型比较
        str_var = str(var_val) if var_val is not None else ""
        str_target = str(target_val)
        if operator == "eq": return str_var == str_target
        if operator == "ne": return str_var != str_target
        if operator == "contains": return str_target in str_var
        if operator == "not_contains": return str_target not in str_var
        if operator == "starts_with": return str_var.startswith(str_target)
        if operator == "ends_with": return str_var.endswith(str_target)

        # 6. 列表/字典比较
        if isinstance(var_val, list):
            if operator == "contains": return target_val in var_val
            if operator == "len_eq": return len(var_val) == int(target_val)
        if isinstance(var_val, dict):
            if operator == "has_key": return str(target_val) in var_val

        return False