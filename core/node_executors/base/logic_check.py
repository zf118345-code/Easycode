# core/node_executors/base/logic_check.py
import time
import copy
from core.registry import NodeExecutorRegistry
from core.node_executors.base_class import BaseNodeExecutor
from core.conditions.evaluator import evaluate_condition


@NodeExecutorRegistry.register("logic_check")
class LogicCheckNodeExecutor(BaseNodeExecutor):
    def _get_cond_desc(self, cond):
        """格式化 5 大类判定条件的日志描述"""
        cond_type = cond.get("condition_type") or cond.get("type", "variable_check")
        cond_params = cond.get("params", cond)

        if cond_type == "image_exists":
            mode_str = "不存在" if cond_params.get("exist_mode") == "not_exists" else "存在"
            return f"图片{mode_str} [{cond_params.get('image_source', '未选图片')}]"
        elif cond_type == "text_contains":
            mode_str = cond_params.get("exist_mode", "contains")
            return f"文本({mode_str}) [{cond_params.get('target_text', '')}]"
        elif cond_type == "variable_check":
            var_name = cond_params.get('variable_name') or cond_params.get('var_name', '')
            val = cond_params.get('compare_value') if cond_params.get('compare_value') is not None else cond_params.get('target_value', '')
            return f"变量 [{var_name}] {cond_params.get('operator', 'eq')} [{val}]"
        elif cond_type == "window_state":
            return f"窗口 [{cond_params.get('window_title', '')}] ({cond_params.get('state_check', 'exists')})"
        elif cond_type == "file_exists":
            return f"文件检查 [{cond_params.get('file_path', '')}]"
        return f"条件 [{cond_type}]"

    def execute(self, node, context):
        params = node.params
        conditions = params.get("conditions", [])
        mode = str(params.get("logic_mode") or params.get("mode", "and")).lower()
        timeout_ms = float(params.get("timeout", 3000))
        timeout_sec = timeout_ms / 1000.0

        if not conditions:
            context.log("⚠️ [逻辑判断] 未配置任何判定条件，默认通过", "warning")
            return self.build_jump_result(True, params.get("on_success", {}))

        context.log(f"🔍 [逻辑判断] 开始评估条件组 (模式: {mode.upper()}, 条件数: {len(conditions)}, 超时: {int(timeout_ms)}ms)")

        start_time = time.time()
        attempt = 0

        # ⚡ 循环轮询，直到条件组判定通过或超时
        while True:
            attempt += 1
            passed_count = 0

            for idx, cond in enumerate(conditions):
                # ⚡ 强制深拷贝条件并写入 timeout=0 (单帧瞬间检测)
                eval_cond = copy.deepcopy(cond)
                if "params" in eval_cond and isinstance(eval_cond["params"], dict):
                    eval_cond["params"]["timeout"] = 0
                else:
                    eval_cond["timeout"] = 0

                is_passed = evaluate_condition(eval_cond, context)

                if is_passed:
                    passed_count += 1
                    # OR 模式短路：只要命中一个即可跳出内部条件循环
                    if mode == "or":
                        break
                else:
                    # AND 模式短路：只要有一个不满足即可跳出内部条件循环
                    if mode == "and":
                        break

            # 判断整体条件组是否成立
            final_success = (passed_count > 0) if mode == "or" else (passed_count == len(conditions))

            if final_success:
                context.log(f"🎯 [逻辑判断] 条件组判定整体通过 ✅ (第 {attempt} 次轮询) ──> 走向成功跳转")
                return self.build_jump_result(True, params.get("on_success", {}))

            elapsed = time.time() - start_time
            if elapsed >= timeout_sec:
                break

            time.sleep(0.1)  # 100ms 快速轮询间隔

        context.log(f"⏰ [逻辑判断] 轮询 {int(timeout_ms)}ms 后条件组仍未满足 ──> 走向失败跳转")
        return self.build_jump_result(False, params.get("on_failure", {}))