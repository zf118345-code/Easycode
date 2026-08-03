# core/node_executors/base/logic_check.py
import os
import pyautogui
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import load_image, match_template_cv


def evaluate_condition(cond, context):
    """通用条件计算引擎：支持图片匹配、变量比较等扩展"""
    cond_type = cond.get("condition_type")
    params = cond.get("params", {})

    if cond_type == "image_exists":
        template_name = params.get("image_source", "")
        if not template_name:
            return False
        templates_dir = os.path.normpath(os.path.join(context.project_dir, "templates"))
        template_path = os.path.normpath(os.path.join(templates_dir, template_name + ".png"))
        if not os.path.exists(template_path):
            return False
        try:
            template = load_image(template_path)
            screenshot = pyautogui.screenshot(region=context.get_window_rect())
            threshold = params.get("threshold", 85) / 100.0
            max_val, _ = match_template_cv(screenshot, template, gray_scale=params.get("gray_scale", True))
            return max_val >= threshold
        except Exception:
            return False

    elif cond_type == "var_compare":
        var_name = params.get("var_name", "")
        operator = params.get("operator", "eq")
        target_val = params.get("target_value")

        current_val = context.variables.get(var_name)
        if current_val is None:
            return False

        try:
            # 尝试做数值转化比较
            c_num, t_num = float(current_val), float(target_val)
            if operator == "eq": return c_num == t_num
            elif operator == "ne": return c_num != t_num
            elif operator == "gt": return c_num > t_num
            elif operator == "gte": return c_num >= t_num
            elif operator == "lt": return c_num < t_num
            elif operator == "lte": return c_num <= t_num
        except (ValueError, TypeError):
            # 字符串比较
            c_str, t_str = str(current_val), str(target_val)
            if operator == "eq": return c_str == t_str
            elif operator == "ne": return c_str != t_str

    return False


@NodeExecutorRegistry.register("logic_check")
class LogicCheckNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        logic_mode = params.get("logic_mode", "or")  # "or" | "and"
        conditions = params.get("conditions", [])

        if not conditions:
            context.log("⚠️ logic_check 节点未配置任何条件，默认判定失败", "warning")
            return self.build_jump_result(False, params.get("on_failure", {}))

        results = []
        for idx, cond in enumerate(conditions):
            res = evaluate_condition(cond, context)
            results.append(res)
            context.log(f"🔍 [LogicCheck] 条件 {idx + 1} ({cond.get('condition_type')}) 判定结果: {res}")

            # 剪枝优化
            if logic_mode == "or" and res:
                context.log("✅ OR 逻辑满足，触发成功跳转")
                return self.build_jump_result(True, params.get("on_success", {}))
            elif logic_mode == "and" and not res:
                context.log("❌ AND 逻辑中断，触发失败跳转")
                return self.build_jump_result(False, params.get("on_failure", {}))

        final_res = all(results) if logic_mode == "and" else any(results)
        if final_res:
            context.log("✅ 条件组合全部满足，触发成功跳转")
            return self.build_jump_result(True, params.get("on_success", {}))
        else:
            context.log("❌ 条件组合判定失败，触发失败跳转")
            return self.build_jump_result(False, params.get("on_failure", {}))