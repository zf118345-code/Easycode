"""resolve_template_string 模板变量替换引擎单元测试

验证三大命名空间：
- 用户全局变量 {xxx} / {$var.xxx}
- 节点上下文 {$ctx.xxx}
- 系统/环境变量 {$env.xxx} / {$sys.xxx}
"""

from datetime import datetime

from core.utils import resolve_template_string


class _MockNode:
    def __init__(self, name):
        self.node_name = name


class _MockCtx:
    """模拟执行器上下文"""

    def __init__(self, variables=None, project_dir='/test/project', task_name='任务A', node_name='节点1'):
        self.variables = variables or {}
        self.project_dir = project_dir
        self.current_task_name = task_name
        self.current_node = _MockNode(node_name)


class TestPlainText:
    def test_non_string_returned_as_is(self):
        assert resolve_template_string(123) == 123
        assert resolve_template_string(None) is None
        assert resolve_template_string([1, 2]) == [1, 2]

    def test_no_braces_returned_as_is(self):
        assert resolve_template_string('hello world') == 'hello world'

    def test_empty_string(self):
        assert resolve_template_string('') == ''


class TestUserVariables:
    """用户全局变量：统一 $var{} 前缀语法（裸 {} 不再识别）"""

    def test_simple_variable(self):
        ctx = _MockCtx(variables={'count': 42})
        assert resolve_template_string('计数: $var{count}', ctx) == '计数: 42'

    def test_var_namespace(self):
        ctx = _MockCtx(variables={'name': 'Alice'})
        assert resolve_template_string('$var{name}', ctx) == 'Alice'

    def test_multiple_variables(self):
        ctx = _MockCtx(variables={'a': '1', 'b': '2'})
        assert resolve_template_string('$var{a}+$var{b}=3', ctx) == '1+2=3'

    def test_legacy_braced_dot_syntax_compat(self):
        """旧语法 {$var.name} 兼容（历史数据）"""
        ctx = _MockCtx(variables={'name': 'Alice'})
        assert resolve_template_string('{$var.name}', ctx) == 'Alice'

    def test_undefined_variable_preserved(self):
        """未定义的变量应保留原占位符"""
        ctx = _MockCtx(variables={})
        assert resolve_template_string('$var{undefined}', ctx) == '$var{undefined}'

    def test_bare_braces_not_resolved(self):
        """裸 {name} 不再识别为变量（必须带 $ 前缀）"""
        ctx = _MockCtx(variables={'count': 42})
        assert resolve_template_string('{count}', ctx) == '{count}'


class TestContextVariables:
    def test_ctx_variable(self):
        ctx = _MockCtx(variables={'ocr_text': '识别结果'})
        assert resolve_template_string('结果: $ctx{ocr_text}', ctx) == '结果: 识别结果'

    def test_legacy_ctx_syntax_compat(self):
        ctx = _MockCtx(variables={'ocr_text': '识别结果'})
        assert resolve_template_string('{$ctx.ocr_text}', ctx) == '识别结果'

    def test_ctx_undefined_preserved(self):
        ctx = _MockCtx(variables={})
        assert resolve_template_string('$ctx{missing}', ctx) == '$ctx{missing}'


class TestSystemVariables:
    def test_current_time(self):
        ctx = _MockCtx()
        result = resolve_template_string('$env{current_time}', ctx)
        # 验证格式为 YYYY-MM-DD HH:MM:SS
        datetime.strptime(result, '%Y-%m-%d %H:%M:%S')

    def test_timestamp(self):
        ctx = _MockCtx()
        result = resolve_template_string('$env{timestamp}', ctx)
        assert result.isdigit()
        assert len(result) >= 13  # 毫秒时间戳

    def test_project_path(self):
        ctx = _MockCtx(project_dir='/my/project')
        assert resolve_template_string('$sys{project_path}', ctx) == '/my/project'

    def test_task_name(self):
        ctx = _MockCtx(task_name='测试任务')
        assert resolve_template_string('$sys{task_name}', ctx) == '测试任务'

    def test_node_name(self):
        ctx = _MockCtx(node_name='点击节点')
        assert resolve_template_string('$sys{node_name}', ctx) == '点击节点'

    def test_legacy_env_syntax_compat(self):
        ctx = _MockCtx(project_dir='/p')
        assert resolve_template_string('{$sys.project_path}', ctx) == '/p'

    def test_unknown_env_key_preserved(self):
        ctx = _MockCtx()
        assert resolve_template_string('$env{unknown}', ctx) == '$env{unknown}'


class TestMixedNamespaces:
    def test_all_namespaces_in_one_string(self):
        ctx = _MockCtx(variables={'user': 'Bob'}, task_name='T1')
        result = resolve_template_string('用户:$var{user} 任务:$sys{task_name} 时间:$env{date}', ctx)
        assert '用户:Bob' in result
        assert '任务:T1' in result
        # 日期格式 YYYY-MM-DD
        datetime.strptime(result.split('时间:')[1], '%Y-%m-%d')

    def test_legacy_mixed_syntax_compat(self):
        ctx = _MockCtx(variables={'user': 'Bob'}, task_name='T1')
        result = resolve_template_string('用户:{user} 任务:{$sys.task_name}', ctx)
        # 裸 {user} 不再识别 → 保留原样；旧 {$sys.task_name} 正常替换
        assert '用户:{user}' in result
        assert '任务:T1' in result


# ========== 模板匹配：多尺度 + 通道统一（#3/#4） ==========

import numpy as np
import cv2


def _texture_img(w, h, seed=42):
    """带纹理的背景图（TM_CCOEFF_NORMED 在纯色图上退化，必须用纹理）"""
    rng = np.random.default_rng(seed)
    img = rng.integers(60, 180, size=(h, w, 3), dtype=np.uint8)
    return img


def test_match_template_color_channel_unified():
    """截图 RGB 与模板 BGR 通道统一后彩色匹配分数接近 1.0（修复通道错位）"""
    from core.utils import match_template_cv

    screen = _texture_img(200, 200, seed=1)
    patch = _texture_img(40, 40, seed=2)  # 纹理方块（BGR）
    screen[80:120, 90:130] = patch
    template = patch.copy()  # BGR 模板（cv2.imread 风格）

    # Pillow 截图是 RGB：转成 RGB 再传入（模拟 pyautogui.screenshot 输出）
    rgb_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)
    max_val, center = match_template_cv(rgb_screen, template, gray_scale=False)
    assert max_val > 0.9, f'通道统一后彩色匹配分数应接近 1.0，实际 {max_val}'
    assert center == (110, 100)


def test_match_template_gray_scale_works():
    from core.utils import match_template_cv

    screen = _texture_img(200, 200, seed=3)
    patch = _texture_img(40, 40, seed=4)
    screen[80:120, 90:130] = patch
    max_val, center = match_template_cv(screen, patch, gray_scale=True)
    assert max_val > 0.9
    assert center == (110, 100)


def test_match_template_multi_scale_hit():
    """模板在屏幕中以 75% 缩放出现（模拟 DPI 缩放）→ 多尺度匹配命中"""
    from core.utils import match_template_cv

    big = _texture_img(80, 80, seed=5)
    small = cv2.resize(big, (60, 60), interpolation=cv2.INTER_AREA)
    screen_bgr = _texture_img(300, 300, seed=6)
    screen_bgr[100:160, 120:180] = small
    # 真实截图是 RGB（Pillow）→ 传入前转 RGB；模板是 BGR（cv2.imread）
    screen = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2RGB)
    max_val, center = match_template_cv(screen, big, gray_scale=False)
    assert max_val > 0.9, f'多尺度匹配应命中缩放模板，实际 {max_val}'
    assert center == (150, 130)


def test_match_template_oversize_returns_none():
    from core.utils import match_template_cv

    screen = _texture_img(50, 50, seed=7)
    template = _texture_img(200, 200, seed=8)  # 最小尺度 0.5 仍 100x100 > 50
    max_val, center = match_template_cv(screen, template)
    assert max_val == -1.0 and center is None
