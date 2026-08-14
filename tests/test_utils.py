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
    def test_simple_variable(self):
        ctx = _MockCtx(variables={'count': 42})
        assert resolve_template_string('计数: {count}', ctx) == '计数: 42'

    def test_var_namespace(self):
        ctx = _MockCtx(variables={'name': 'Alice'})
        assert resolve_template_string('{$var.name}', ctx) == 'Alice'

    def test_multiple_variables(self):
        ctx = _MockCtx(variables={'a': '1', 'b': '2'})
        assert resolve_template_string('{a}+{b}=3', ctx) == '1+2=3'

    def test_undefined_variable_preserved(self):
        """未定义的变量应保留原占位符"""
        ctx = _MockCtx(variables={})
        assert resolve_template_string('{undefined}', ctx) == '{undefined}'


class TestContextVariables:
    def test_ctx_variable(self):
        ctx = _MockCtx(variables={'ocr_text': '识别结果'})
        assert resolve_template_string('结果: {$ctx.ocr_text}', ctx) == '结果: 识别结果'

    def test_ctx_undefined_preserved(self):
        ctx = _MockCtx(variables={})
        assert resolve_template_string('{$ctx.missing}', ctx) == '{$ctx.missing}'


class TestSystemVariables:
    def test_current_time(self):
        ctx = _MockCtx()
        result = resolve_template_string('{$env.current_time}', ctx)
        # 验证格式为 YYYY-MM-DD HH:MM:SS
        datetime.strptime(result, '%Y-%m-%d %H:%M:%S')

    def test_timestamp(self):
        ctx = _MockCtx()
        result = resolve_template_string('{$env.timestamp}', ctx)
        assert result.isdigit()
        assert len(result) >= 13  # 毫秒时间戳

    def test_project_path(self):
        ctx = _MockCtx(project_dir='/my/project')
        assert resolve_template_string('{$sys.project_path}', ctx) == '/my/project'

    def test_task_name(self):
        ctx = _MockCtx(task_name='测试任务')
        assert resolve_template_string('{$sys.task_name}', ctx) == '测试任务'

    def test_node_name(self):
        ctx = _MockCtx(node_name='点击节点')
        assert resolve_template_string('{$sys.node_name}', ctx) == '点击节点'

    def test_unknown_env_key_preserved(self):
        ctx = _MockCtx()
        assert resolve_template_string('{$env.unknown}', ctx) == '{$env.unknown}'


class TestMixedNamespaces:
    def test_all_namespaces_in_one_string(self):
        ctx = _MockCtx(variables={'user': 'Bob'}, task_name='T1')
        result = resolve_template_string('用户:{user} 任务:{$sys.task_name} 时间:{$env.date}', ctx)
        assert '用户:Bob' in result
        assert '任务:T1' in result
        # 日期格式 YYYY-MM-DD
        datetime.strptime(result.split('时间:')[1], '%Y-%m-%d')
