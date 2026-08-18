"""节点执行器与参数默认值测试

覆盖：
1. click 执行器：(0,0) 视为未设置 → 告警跳过不点击
2. wait 执行器：duration_ms（毫秒）与旧 seconds（秒）兼容
3. variable_op 策略：op_action 单一操作方式（兼容旧 num_op/str_op/list_op）
4. schema 默认值：wait ms / variable_op 只读与去类型标签 / 灰度默认关闭
"""

import time

import pytest

from core.params import ALL_PARAMS
from core.variables.types.list import ListVariableType
from core.variables.types.number import NumberVariableType
from core.variables.types.string import StringVariableType


# ========== 测试用假 context ==========

class FakeCtx:
    def __init__(self, variables=None):
        self.variables = variables or {}
        self.logs = []

    def log(self, msg, level='info', image=None):
        self.logs.append(msg)

    def is_window_mode(self):
        return False

    def get_window_rect(self):
        return (0, 0, 100, 100)

    @property
    def is_emulator(self):
        return False

    @property
    def device_id(self):
        return None


def make_node(params):
    from core.models import Node

    return Node(node_id='n', node_name='n', node_type='click', params=params)


# ========== click 执行器 ==========

class TestClickExecutor:
    def test_zero_coordinate_skips_click(self, monkeypatch):
        """坐标 (0,0)（未设置）→ 告警并失败，不执行任何点击"""
        from core.node_executors.base import click as click_mod

        clicked = []
        monkeypatch.setattr(click_mod.pyautogui, 'click', lambda *a, **k: clicked.append(a))

        from core.node_executors.base.click import ClickNodeExecutor

        ctx = FakeCtx()
        node = make_node({'position': [0, 0]})
        result = ClickNodeExecutor().execute(node, ctx)

        assert result['success'] is False
        assert clicked == []
        assert any('点击位置未设置' in m for m in ctx.logs)

    def test_normal_position_clicks(self, monkeypatch):
        """正常坐标 → 真实点击"""
        from core.node_executors.base import click as click_mod

        clicked = []
        monkeypatch.setattr(click_mod.pyautogui, 'click', lambda *a, **k: clicked.append(a))

        from core.node_executors.base.click import ClickNodeExecutor

        ctx = FakeCtx()
        node = make_node({'position': [100, 200]})
        result = ClickNodeExecutor().execute(node, ctx)

        assert result['success'] is True
        assert clicked == [(100, 200)]


# ========== wait 执行器 ==========

class TestWaitExecutor:
    def test_duration_ms(self, monkeypatch):
        """duration_ms 毫秒单位：1000ms → sleep 1s"""
        from core.node_executors.base import wait as wait_mod

        slept = []
        monkeypatch.setattr(wait_mod.time, 'sleep', lambda s: slept.append(s))

        from core.node_executors.base.wait import WaitNodeExecutor

        ctx = FakeCtx()
        node = make_node({'duration_ms': 1000})
        result = WaitNodeExecutor().execute(node, ctx)

        assert result['success'] is True
        assert slept == [1.0]
        assert '等待 1000 ms' in ctx.logs[0]

    def test_legacy_seconds_compat(self, monkeypatch):
        """旧数据 seconds（秒）→ 自动 ×1000 转为毫秒"""
        from core.node_executors.base import wait as wait_mod

        slept = []
        monkeypatch.setattr(wait_mod.time, 'sleep', lambda s: slept.append(s))

        from core.node_executors.base.wait import WaitNodeExecutor

        ctx = FakeCtx()
        node = make_node({'seconds': 2.0})
        WaitNodeExecutor().execute(node, ctx)
        assert slept == [2.0]  # 2.0 秒 → sleep 2.0s


# ========== variable_op 策略：op_action 单一化 ==========

class TestVariableOpAction:
    def test_number_op_action(self):
        ctx = FakeCtx({'base': 10})
        # op_action=add + num_value 常量
        assert NumberVariableType.execute('number', 5, {'op_action': 'add', 'num_value': '3'}, ctx) == 8
        # op_action=set
        assert NumberVariableType.execute('number', 5, {'op_action': 'set', 'num_value': '7'}, ctx) == 7
        # 旧字段 num_op 兼容
        assert NumberVariableType.execute('number', 5, {'num_op': 'mul', 'num_value': '2'}, ctx) == 10
        # $var{} 前缀语法
        assert NumberVariableType.execute('number', 1, {'op_action': 'add', 'num_value': '$var{base}'}, ctx) == 11
        # 裸变量名不再识别
        assert NumberVariableType.execute('number', 1, {'op_action': 'add', 'num_value': 'base'}, ctx) == 1

    def test_string_op_action(self):
        ctx = FakeCtx({'name': '世界'})
        # 输入框自由填写：纯字符串 / {var} 变量
        assert StringVariableType.execute('string', '你好', {'op_action': 'append', 'str_value': '!'}, ctx) == '你好!'
        assert StringVariableType.execute('string', '你好', {'op_action': 'append', 'str_value': '$var{name}'}, ctx) == '你好世界'
        assert StringVariableType.execute('string', '你好', {'op_action': 'set', 'str_value': '123'}, ctx) == '123'
        # replace
        assert StringVariableType.execute('string', 'a-b', {'op_action': 'replace', 'replace_find': '-', 'replace_with': '+'}, ctx) == 'a+b'
        # 旧字段 str_op 兼容
        assert StringVariableType.execute('string', 'x', {'str_op': 'set', 'str_value': 'y'}, ctx) == 'y'

    def test_list_op_action(self):
        ctx = FakeCtx()
        assert ListVariableType.execute('list', [1, 2], {'op_action': 'push', 'list_item_value': '3'}, ctx) == [1, 2, 3]
        assert ListVariableType.execute('list', [1, 2], {'op_action': 'pop'}, ctx) == [1]
        assert ListVariableType.execute('list', [1, 2], {'op_action': 'clear'}, ctx) == []
        join_ctx = FakeCtx({})
        result = ListVariableType.execute(
            'list', [1, 2],
            {'op_action': 'join', 'list_join_delimiter': '-', 'list_join_target_var': 'joined'}, join_ctx)
        assert result == [1, 2]            # 原数组不变
        assert join_ctx.variables['joined'] == '1-2'   # 拼接结果写入目标文本变量
        # 旧字段 list_op 兼容
        assert ListVariableType.execute('list', [1], {'list_op': 'push', 'list_item_value': '9'}, ctx) == [1, 9]


# ========== variable_op 表达式模式（new_value） ==========

class TestVariableOpExpression:
    def setup_method(self):
        from core.node_executors.base.variable_op import VariableOpNodeExecutor

        self.executor = VariableOpNodeExecutor()

    def _run(self, variables, params):
        ctx = FakeCtx(variables)
        node = make_node(params)
        result = self.executor.execute(node, ctx)
        return ctx, result

    def test_basic_arithmetic_assign(self):
        ctx, result = self._run({'a': 1, 'b': 10, 'c': 3}, {
            'target_var': '$var{a}',
            'new_value': '$var{b}+$var{c}',
        })
        assert result['success'] is True
        assert ctx.variables['a'] == 13

    def test_free_cross_variable(self):
        # 变量 b/c/d/e 互相加减乘除得到 a
        ctx, result = self._run({'a': 0, 'b': 10, 'c': 3, 'd': 4, 'e': 2}, {
            'target_var': '$var{a}',
            'new_value': '($var{b}+$var{c})*$var{d}/$var{e}',
        })
        assert result['success'] is True
        assert ctx.variables['a'] == 26.0

    def test_string_concat_append(self):
        # 变量 a = 变量 a + 'ing'
        ctx, result = self._run({'a': 'runn'}, {
            'target_var': '$var{a}',
            'new_value': "$var{a}+'ing'",
        })
        assert result['success'] is True
        assert ctx.variables['a'] == 'running'

    def test_string_concat_number(self):
        # 数字变量追加字符串 → 宽松拼接
        ctx, result = self._run({'a': 5}, {
            'target_var': '$var{a}',
            'new_value': "$var{a}+'ing'",
        })
        assert result['success'] is True
        assert ctx.variables['a'] == '5ing'

    def test_function_and_index(self):
        ctx, result = self._run({'scores': [3, 6, 9], 'name': 'alice'}, {
            'target_var': 'avg',
            'new_value': 'sum($var{scores}) / len($var{scores})',
        })
        assert ctx.variables['avg'] == 6.0

    def test_unsupported_slice_fails_safely(self):
        # 切片 [0:1] 暂不支持 → 安全失败而非崩溃
        ctx, result = self._run({'name': 'alice'}, {
            'target_var': '$var{topic}',
            'new_value': "upper($var{name})[0:1] + '…'",
        })
        assert result['success'] is False
        assert ctx.logs and '表达式' in ctx.logs[-1]

    def test_expression_error_returns_failure(self):
        ctx, result = self._run({'a': 1}, {
            'target_var': '$var{a}',
            'new_value': '1/0',
        })
        assert result['success'] is False
        assert any('表达式' in log and '求值失败' in log for log in ctx.logs)

    def test_syntax_error_returns_failure(self):
        ctx, result = self._run({'a': 1}, {
            'target_var': '$var{a}',
            'new_value': '(1+2',
        })
        assert result['success'] is False
        assert any('求值失败' in log for log in ctx.logs)

    def test_legacy_op_action_fallback(self):
        # 旧蓝图节点：无 new_value 但有 op_action → 走旧策略
        ctx, result = self._run({'x': 5}, {
            'target_var': '$var{x}',
            'op_action': 'add',
            'num_value': '3',
            'var_type': 'number',
        })
        assert result['success'] is True
        assert ctx.variables['x'] == 8

    def test_no_value_skips(self):
        ctx, result = self._run({'x': 5}, {'target_var': '$var{x}'})
        assert result['success'] is True
        assert ctx.variables['x'] == 5  # 未变
        assert any('未配置赋值表达式' in log for log in ctx.logs)

    def test_typed_result_kept(self):
        # 表达式结果类型自然保留（布尔/列表）
        ctx, result = self._run({'x': 1, 'y': 2}, {
            'target_var': '$var{flag}',
            'new_value': '$var{x} > $var{y} ? false : true',
        })
        assert ctx.variables['flag'] is True
        ctx, result = self._run({}, {
            'target_var': '$var{ops}',
            'new_value': '[1, 2, 3]',
        })
        assert ctx.variables['ops'] == [1, 2, 3]


# ========== schema 默认值 ==========

class TestSchemaDefaults:
    def test_wait_ms_default(self):
        w = ALL_PARAMS['wait']['params']
        assert w['duration_ms']['default'] == 1000
        assert w['duration_ms']['suffix'] == 'ms'
        assert 'seconds' not in w

    def test_variable_op_simplified(self):
        vo = ALL_PARAMS['variable_op']['params']
        # 精简为两字段：目标变量 + 最新赋值（textarea 表达式）
        assert set(vo.keys()) == {'target_var', 'new_value'}
        assert vo['target_var']['type'] == 'str'
        assert vo['new_value']['type'] == 'textarea'
        assert 'help' in vo['new_value'] and isinstance(vo['new_value']['help'], list)
        assert 'help' in vo['target_var']
        # 移除旧字段（var_type / op_action / 各类型操作值）
        for k in ('var_type', 'op_action', 'num_op', 'str_op', 'list_op', 'num_value', 'str_value', 'list_item_value'):
            assert k not in vo

    def test_gray_scale_default_off(self):
        # 灰度默认关闭（按需开启）
        assert ALL_PARAMS['image_recognition']['params']['gray_scale']['default'] is False
        assert ALL_PARAMS['ocr_recognition']['params']['gray_scale']['default'] is False
