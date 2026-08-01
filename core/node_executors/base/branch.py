# core/node_executors/base/branch.py
import os
import pyautogui
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.utils import load_image, match_template_cv


@NodeExecutorRegistry.register("branch")
class BranchNodeExecutor(BaseNodeExecutor):
    def execute(self, node, context):
        params = node.params
        candidates = params.get("candidates", [])
        if not candidates:
            context.log("branch 节点缺少 candidates 参数", "error")
            return self.build_jump_result(False, params.get("on_failure_jump", {}), error="no candidates")

        region_conf = params.get("region", {})
        if region_conf.get("type") == "recorded":
            rect = region_conf.get("value")
            region = tuple(rect) if rect and len(rect) == 4 else context.get_window_rect()
        else:
            region = context.get_window_rect()

        default_threshold = params.get("threshold", 85) / 100.0
        best_score = -1.0
        best_target = None
        best_template = None

        # 截图一次供所有候选匹配使用，大幅提升性能
        screenshot = pyautogui.screenshot(region=region)

        for cand in candidates:
            template_name = cand.get("template")
            if not template_name:
                continue

            threshold = cand.get("threshold", default_threshold)
            if isinstance(threshold, int):
                threshold = threshold / 100.0

            templates_dir = os.path.join(context.project_dir, "templates")
            template_path = os.path.normpath(os.path.join(templates_dir, template_name + ".png"))

            if not os.path.exists(template_path):
                context.log(f"模板不存在: {template_path}", "warning")
                continue
            try:
                template = load_image(template_path)
            except:
                continue

            # 使用提取的通用匹配函数
            max_val, _ = match_template_cv(screenshot, template, gray_scale=True)
            context.log(f"模板 {template_name} 匹配分数: {max_val:.3f}")

            if max_val > best_score:
                best_score = max_val
                best_target = cand.get("target")
                best_template = template_name

        if best_score < default_threshold:
            context.log(f"最佳分数 {best_score:.3f} 低于阈值 {default_threshold}，跳转失败分支")
            return self.build_jump_result(False, params.get("on_failure_jump", {}))

        if best_target is None:
            context.log("未找到有效候选", "error")
            return self.build_jump_result(False, params.get("on_failure_jump", {}), error="no valid target")

        context.log(f"选择模板 {best_template}，分数 {best_score:.3f}，跳转到 {best_target}")
        return self.build_jump_result(True, {"type": "node", "target": best_target})