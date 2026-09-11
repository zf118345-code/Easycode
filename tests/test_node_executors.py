"""节点执行器与参数默认值测试

覆盖：
1. click 执行器：(0,0) 是合法工作区坐标，统一交给输入路由
2. wait 执行器：duration_ms（毫秒）
3. variable_op：自由表达式赋值
4. schema 默认值：wait ms / variable_op 只读与去类型标签 / 灰度默认关闭
"""



from core.params import ALL_PARAMS


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

    def get_setting(self, key, default=None):
        return default

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
    def test_zero_coordinate_is_valid(self, monkeypatch):
        """坐标 (0,0) 是合法工作区位置，不能再用它代表“未设置”。"""
        from core.node_executors.base import click as click_mod

        clicked = []
        monkeypatch.setattr(click_mod, 'click_workspace', lambda ctx, x, y, **kwargs:
                            clicked.append((x, y)) or {
                                'ok': True, 'method': 'background', 'message': 'queued',
                                'workspace_point': [x, y], 'screen_point': [x, y],
                            })

        from core.node_executors.base.click import ClickNodeExecutor

        ctx = FakeCtx()
        node = make_node({'position': [0, 0]})
        result = ClickNodeExecutor().execute(node, ctx)

        assert result['success'] is True
        assert clicked == [(0, 0)]

    def test_normal_position_clicks(self, monkeypatch):
        """正常坐标 → 统一输入路由"""
        from core.node_executors.base import click as click_mod

        clicked = []
        monkeypatch.setattr(click_mod, 'click_workspace', lambda ctx, x, y, **kwargs:
                            clicked.append((x, y)) or {
                                'ok': True, 'method': 'background', 'message': 'queued',
                                'workspace_point': [x, y], 'screen_point': [x, y],
                            })

        from core.node_executors.base.click import ClickNodeExecutor

        ctx = FakeCtx()
        node = make_node({'position': [100, 200]})
        result = ClickNodeExecutor().execute(node, ctx)

        assert result['success'] is True
        assert clicked == [(100, 200)]


class TestImageRecognitionExecutor:
    def test_missing_execution_mode_fails_before_loading_or_clicking(self):
        from core.node_executors.base import image_recognition as image_mod

        ctx = FakeCtx()
        node = make_node({'image_source': 'asset://asset_test'})
        executor = image_mod.ImageRecognitionNodeExecutor.__new__(image_mod.ImageRecognitionNodeExecutor)

        result = executor.execute(node, ctx)

        assert result['success'] is False
        assert result['error'] == 'invalid execution mode'
        assert any('运行模式无效或缺失' in message for message in ctx.logs)

    def test_disk_asset_resolution_continues_to_match_and_returns_success(self, monkeypatch):
        """asset:// 解析成功后必须继续加载和匹配，不能误报 template not found。"""
        import numpy as np
        from core.node_executors.base import image_recognition as image_mod

        template = np.zeros((8, 8, 3), dtype=np.uint8)
        screen = np.zeros((40, 40, 3), dtype=np.uint8)
        monkeypatch.setattr(
            image_mod.AssetService,
            'resolve',
            lambda project_dir, reference: {'full_path': r'D:\fake\template.png'},
        )
        monkeypatch.setattr(image_mod, 'load_image', lambda path: template)
        monkeypatch.setattr(
            image_mod,
            'capture_workspace_region',
            lambda context, region, reference_size: (screen, (0, 0, 40, 40)),
        )
        monkeypatch.setattr(image_mod, 'match_prepared_template_cv', lambda *args, **kwargs: (1.0, (10, 12)))
        monkeypatch.setattr(image_mod, 'refresh_work_area', lambda context: (100, 200, 40, 40))

        ctx = FakeCtx()
        ctx.project_dir = r'D:\project'
        ctx.image_log_enabled = False
        ctx._memory_templates = {}
        node = make_node({
            'image_source': 'asset://asset_test',
            'threshold': 85,
            'timeout': 100,
            'region_type': 'fullwindow',
            'execution_mode': 'wait_present',
        })

        executor = image_mod.ImageRecognitionNodeExecutor.__new__(image_mod.ImageRecognitionNodeExecutor)
        result = executor.execute(node, ctx)

        assert result['success'] is True
        assert result['confidence'] == 1.0
        assert result['workspace_pos'] == (10, 12)
        assert result['pos'] == (110, 212)


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

    def test_read_only_parameter_and_environment_cannot_be_assignment_targets(self):
        for target in ('$param.amount', '$env{PATH}'):
            ctx, result = self._run({}, {'target_var': target, 'new_value': '1'})
            assert result['success'] is False
            assert target not in ctx.variables

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
