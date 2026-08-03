# core/node_executors/base/branch.py
import os
import pyautogui
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import load_image, match_template_cv


def evaluate_condition_with_score(cond, context):
    """
    评估条件并返回得分结构:
    (is_passed: bool, score: float)
    图片匹配返回实际置信度 (0.0 ~ 1.0)
    变量比较成立返回 1.0，不成立返回 0.0
    """
    cond_type = cond.get("condition_type")
    params = cond.get("params", {})

    if cond_type == "image_exists":
        template_name = params.get("image_source", "")
        if not template_name:
            return False, 0.0

        templates_dir = os.path.normpath(os.path.join(context.project_dir, "templates"))
        template_path = os.path.normpath(os.path.join(templates_dir, template_name + ".png"))

        if not os.path.exists(template_path):
            return False, 0.0

        try:
            template = load_image(template_path)
            screenshot = pyautogui.screenshot(region=context.get_window_rect())
            threshold = params.get("threshold", 85) / 100.0
            max_val, _ = match_template_cv(screenshot, template, gray_scale=params.get("gray_scale", True))

            is_passed = max_val >= threshold
            return is_passed, max_val
        except Exception as e:
            context.log(f"⚠️ [Branch] 图像评估异常: {e}", "warning")
            return False, 0.0

    elif cond_type == "var_compare":
        var_name = params.get("var_name", "")
        operator = params.get("operator", "eq")
        target_val = params.get("target_value")

        current_val = context.variables.get(var_name)
        if current_val is None:
            return False, 0.0

        try:
            c_num, t_num = float(current_val), float(target_val)
            if operator == "eq": is_passed = (c_num == t_num)
            elif operator == "ne": is_passed = (c_num != t_num)
            elif operator == "gt": is_passed = (c_num > t_num)
            elif operator == "gte": is_passed = (c_num >= t_num)
            elif operator == "lt": is_passed = (c_num < t_num)
            elif operator == "lte": is_passed = (c_num <= t_num)
            else: is_passed = False
        except (ValueError, TypeError):
            c_str, t_str = str(current_val), str(target_val)
            if operator == "eq": is_passed = (c_str == t_str)
            elif operator == "ne": is_passed = (c_str != t_str)
            else: is_passed = False

        return is_passed, (1.0 if is_passed else 0.0)

    return False, 0.0


@NodeExecutorRegistry.register("branch")
class BranchNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        candidates = params.get("candidates", [])
        best_match_mode = params.get("best_match_mode", True)

        if not candidates:
            context.log("❌ branch 节点未配置任何候选条件分支", "error")
            return self.build_jump_result(False, params.get("on_failure", {}), error="no candidates")

        context.log(f"🔀 [Branch 分流] 评估模式: {'最高置信度竞态' if best_match_mode else '顺序优先'} | 分支数: {len(candidates)}")

        best_cand = None
        highest_score = -1.0

        for idx, cand in enumerate(candidates):
            condition = cand.get("condition", {})
            jump_target = cand.get("on_success", {})

            is_passed, score = evaluate_condition_with_score(condition, context)
            cond_desc = f"图片 [{condition.get('params', {}).get('image_source')}]" if condition.get("condition_type") == "image_exists" else f"变量 [{condition.get('params', {}).get('var_name')}]"

            if is_passed:
                context.log(f"  ├─ 分支 {idx + 1} ({cond_desc}): 匹配通过 ✅ | 得分/置信度: {score:.3f}")

                # 顺序优先模式：直接命中并退出
                if not best_match_mode:
                    context.log(f"🎯 [Branch 顺序命中] 走向分支 {idx + 1} 的成功跳转")
                    return self.build_jump_result(True, jump_target)

                # 竞态模式：记录得分最高的分支
                if score > highest_score:
                    highest_score = score
                    best_cand = cand
            else:
                context.log(f"  ├─ 分支 {idx + 1} ({cond_desc}): 未通过 ❌ | 最高得分: {score:.3f}")

        if best_match_mode and best_cand:
            context.log(f"🏆 [Branch 竞态获胜] 最高得分分支 (分数: {highest_score:.3f})，走向其成功跳转")
            return self.build_jump_result(True, best_cand.get("on_success", {}))

        context.log("⏰ [Branch 兜底] 所有分支条件均未成立，触发通用失败跳转")
        return self.build_jump_result(False, params.get("on_failure", {}))