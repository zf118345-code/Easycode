# core/node_executors/base/branch.py
import copy
import time

from core.conditions.evaluator import evaluate_condition
from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry


@NodeExecutorRegistry.register('branch')
class BranchNodeExecutor(BaseNodeExecutor):
    def _get_cond_desc(self, condition):
        """格式化 5 大类判定条件的日志描述"""
        cond_type = condition.get('condition_type') or condition.get('type', 'variable_check')
        cond_params = condition.get('params', condition)

        if cond_type == 'image_exists':
            mode_str = '不存在' if cond_params.get('exist_mode') == 'not_exists' else '存在'
            return f'图片{mode_str} [{cond_params.get("image_source", "未选图片")}]'
        elif cond_type == 'text_contains':
            mode_str = cond_params.get('exist_mode', 'contains')
            return f'文本({mode_str}) [{cond_params.get("target_text", "")}]'
        elif cond_type == 'variable_check':
            var_name = cond_params.get('variable_name') or cond_params.get('var_name', '')
            val = (
                cond_params.get('compare_value')
                if cond_params.get('compare_value') is not None
                else cond_params.get('target_value', '')
            )
            return f'变量 [{var_name}] {cond_params.get("operator", "eq")} [{val}]'
        elif cond_type == 'window_state':
            return f'窗口 [{cond_params.get("window_title", "")}] ({cond_params.get("state_check", "exists")})'
        elif cond_type == 'file_exists':
            return f'文件检查 [{cond_params.get("file_path", "")}]'
        return f'条件 [{cond_type}]'

    def execute(self, node, context):
        params = node.params
        candidates = params.get('candidates', [])
        match_strategy = params.get('match_strategy', 'first')
        timeout_ms = float(params.get('timeout', 3000))
        timeout_sec = timeout_ms / 1000.0

        if not candidates:
            context.log('❌ [Branch 分流] 未配置任何候选分支条件', 'error')
            return self.build_jump_result(False, params.get('on_failure', {}), error='no candidates')

        strategy_label = '顺序优先' if match_strategy == 'first' else '择优优先'
        context.log(
            f'🔀 [Branch 分流] 开始评估分支列表 | 策略: {strategy_label} | 候选数: {len(candidates)} | 超时: {int(timeout_ms)}ms'
        )

        start_time = time.time()
        attempt = 0

        while True:
            attempt += 1
            passed_candidates = []

            for idx, cand in enumerate(candidates):
                condition = cand.get('condition', {})
                jump_target = cand.get('on_success', {})

                eval_cond = copy.deepcopy(condition)
                if 'params' in eval_cond and isinstance(eval_cond['params'], dict):
                    eval_cond['params']['timeout'] = 0
                else:
                    eval_cond['timeout'] = 0

                # ⚡ 测算单项条件匹配耗时与得分
                cond_start_time = time.time()
                context.last_match_score = 0.0  # 重置得分基准

                is_passed = evaluate_condition(eval_cond, context)
                cond_elapsed_ms = (time.time() - cond_start_time) * 1000.0

                # 获取条件计算出的真实得分（图像相似度 / 逻辑布尔值 1.0 或 0.0）
                score = float(getattr(context, 'last_match_score', 1.0 if is_passed else 0.0))
                if not is_passed and score == 1.0:
                    score = 0.0

                desc = self._get_cond_desc(condition)

                if is_passed:
                    context.log(
                        f'  ├─ 分支 {idx + 1} ({desc}): 匹配成功 ✅ | 得分: {score:.2f} | 耗时: {cond_elapsed_ms:.1f}ms'
                    )
                    passed_candidates.append({'index': idx, 'desc': desc, 'jump_target': jump_target, 'score': score})

                    # 模式一：顺序优先 (命中即跳)
                    if match_strategy == 'first':
                        context.log(
                            f'🎯 [Branch 命中] [顺序优先] 走向分支 {idx + 1} (branch_{idx}) 连线目标 (第 {attempt} 次轮询)'
                        )
                        return self.build_jump_result(True, jump_target)
                else:
                    context.log(
                        f'  ├─ 分支 {idx + 1} ({desc}): 未匹配 ❌ | 得分: {score:.2f} | 耗时: {cond_elapsed_ms:.1f}ms'
                    )

            # 模式二：择优优先 (对比全部成立项后取最高分)
            if match_strategy == 'best' and passed_candidates:
                passed_candidates.sort(key=lambda x: x['score'], reverse=True)
                best_match = passed_candidates[0]
                best_idx = best_match['index']
                best_desc = best_match['desc']
                best_score = best_match['score']

                context.log(
                    f'  ├─ 本轮评估共 {len(passed_candidates)} 项条件成立，最高得分项: 分支 {best_idx + 1} (得分: {best_score:.2f})'
                )
                context.log(f'🎯 [Branch 命中] [择优优先] 走向最高得分分支 {best_idx + 1} ({best_desc}) 连线目标')
                return self.build_jump_result(True, best_match['jump_target'])

            elapsed = time.time() - start_time
            if elapsed >= timeout_sec:
                break

            time.sleep(0.1)  # 100ms 高速轮询间隔

        total_elapsed_ms = (time.time() - start_time) * 1000.0
        context.log(f'⏰ [Branch 兜底] 轮询 {int(total_elapsed_ms)}ms 后所有候选条件均未成立 ──> 走向 Else 兜底连线')
        return self.build_jump_result(False, params.get('on_failure', {}))
