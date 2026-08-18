# tests/test_expressions.py
# 全局变量自由表达式求值器完整测试
import pytest

from core.expressions import ExpressionError, evaluate_expression


class FakeCtx:
    def __init__(self, variables=None):
        self.variables = variables or {}


VC = FakeCtx({
    'a': 5,
    'b': 10,
    'c': 3,
    'd': 4,
    'e': 2,
    'name': 'alice',
    'list': [1, 2, 3],
    'info': {'x': 10, 'y': 'hello'},
    'price': '12.5',
    'empty': '',
})

CTX = FakeCtx({**VC.variables, 'ocr_text': 'Hello World 123'})


def ev(text, ctx=VC):
    return evaluate_expression(text, ctx)


# ---------------------------------------------------------------- 算术

@pytest.mark.parametrize('expr,expected', [
    ('1+2*3', 7),
    ('(1+2)*3', 9),
    ('10-4-3', 3),
    ('7/2', 3.5),
    ('7//2', 3),
    ('7%3', 1),
    ('2**10', 1024),
    ('-5+3', -2),
    ('-(1+2)', -3),
    ('2*3+4*5', 26),
    ('10/4', 2.5),
    ('5.5+1', 6.5),
    ('1e2', 100.0),
    ('2**2**3', 256),  # 右结合
])
def test_arithmetic(expr, expected):
    assert ev(expr) == expected


# ---------------------------------------------------------------- 跨变量自由运算

def test_cross_variable_arithmetic():
    # $var{b}+$var{c}-$var{d}*$var{e}/$var{f} 场景
    assert ev('$var{b}+$var{c}-$var{d}*$var{e}/2') == 13 - 4  # 10+3-8/2 = 13-4 = 9
    assert ev('($var{b}+$var{c})*2') == 26
    assert ev('$var{a}*$var{a}+$var{e}') == 27


# ---------------------------------------------------------------- 字符串

def test_string_concat():
    assert ev("$var{a}+'ing'") == '5ing'          # 数字 + 字符串 → 宽松拼接
    assert ev("'前缀' + $var{name}") == '前缀alice'
    assert ev('"双引号" + "拼接"') == '双引号拼接'
    assert ev("$var{name}+'-'+$var{name}") == 'alice-alice'
    assert ev("'数量: ' + $var{a}") == '数量: 5'

def test_string_escape():
    assert ev(r"'a\nb'") == 'a\nb'
    assert ev(r"'it\'s'") == "it's"
    assert ev(r"'\tTab'") == '\tTab'
    assert ev("'反\\斜杠: \\\\'") == '反斜杠: \\'


# ---------------------------------------------------------------- 比较 / 逻辑

@pytest.mark.parametrize('expr,expected', [
    ('5 > 3', True),
    ('5 >= 5', True),
    ('4 < 3', False),
    ('5 == 5', True),
    ('5 != 6', True),
    ("'ab' == 'ab'", True),
    ("'ab' != 'ab'", False),
    ('10 > 2 and 2 > 1', True),
    ('10 > 2 or 2 > 9', True),
    ('not 5 > 3', False),
    ('not False', True),
    ('10 > 2 > 1', True),       # 链式
    ('10 > 20 > 1', False),
    ('$var{a} >= 5 and $var{b} <= 10', True),
    ('$var{price} > 10', True),  # 字符串数字按数值比较
])
def test_compare_logic(expr, expected):
    assert ev(expr) is expected


def test_and_or_semantics():
    # and/or 返回操作数（Python 语义）
    assert ev("'' or '默认值'") == '默认值'
    assert ev("'非空' or '默认值'") == '非空'
    assert ev("'x' and 'y'") == 'y'
    # 短路：右侧不报错
    assert ev("True or (1/0 == 1)") is True
    assert ev("False and (1/0 == 1)") is False


def test_or_default_for_missing_var():
    # 未定义变量解析为 None → or 兜底
    assert ev("$var{not_exist} or '兜底'") == '兜底'
    assert ev("$var{not_exist}") is None
    assert ev("$var{not_exist} == None", VC) is True


# ---------------------------------------------------------------- 三元

def test_ternary_question():
    assert ev('$var{a} > 3 ? "大" : "小"') == '大'
    assert ev('$var{a} > 10 ? "大" : "小"') == '小'
    assert ev('1 ? 2 ? 3 : 4 : 5') == 3  # 右结合外层 true → 3


def test_ternary_if_else():
    assert ev("'大' if $var{a} > 3 else '小'") == '大'
    assert ev("'大' if $var{a} > 10 else '小'") == '小'


def test_ternary_missing_separator():
    with pytest.raises(ExpressionError):
        ev('$var{a} > 3 ? "大"')


# ---------------------------------------------------------------- 函数白名单

@pytest.mark.parametrize('expr,expected', [
    ("upper($var{name})", 'ALICE'),
    ("lower('ABC')", 'abc'),
    ("strip('  hi  ')", 'hi'),
    ("replace('a-b-c', '-', '+')", 'a+b+c'),
    ("split('a,b,c', ',')", ['a', 'b', 'c']),
    ("join(',', ['a', 'b', 'c'])", 'a,b,c'),
    ("join(['a', 'b', 'c'], '-')", 'a-b-c'),
    ("contains('Hello World', 'World')", True),
    ("contains(['a', 'b'], 'b')", True),
    ("contains($var{list}, 3)", True),
    ("startswith('hello', 'he')", True),
    ("endswith('hello', 'lo')", True),
    ("len('hello')", 5),
    ("len($var{list})", 3),
    ("abs(-5)", 5),
    ("abs($var{a} - 20)", 15),
    ("min(3, 1, 2)", 1),
    ("max(3, 1, 2)", 3),
    ("sum([1, 2, 3])", 6),
    ("round(3.14159, 2)", 3.14),
    ("round(3.7)", 4),
    ("str(123)", '123'),
    ("str($var{a})+'ing'", '5ing'),
    ("int('42')", 42),
    ("float('3.5')", 3.5),
    ("bool('')", False),
    ("bool('x')", True),
    ("int($var{price})", 12),
    ("max(len($var{name}), len('xyz'))", 5),
])
def test_functions(expr, expected):
    assert ev(expr) == expected


def test_join_single_arg():
    assert ev("join(['a', 'b'])") == 'ab'
    assert ev("join($var{list})") == '123'


def test_function_whitelist_rejects_unknown():
    with pytest.raises(ExpressionError):
        ev("exec('ls')")
    with pytest.raises(ExpressionError):
        ev("eval('1')")
    with pytest.raises(ExpressionError):
        ev("import os")


# ---------------------------------------------------------------- 下标

def test_index_list():
    assert ev('$var{list}[0]') == 1
    assert ev('$var{list}[-1]') == 3
    assert ev('[10, 20, 30][1]') == 20


def test_index_dict():
    assert ev("$var{info}['x']") == 10
    assert ev('$var{info}["y"]') == 'hello'
    assert ev('$var{info}[$var{key}]', FakeCtx({**VC.variables, 'key': 'x'})) == 10


def test_index_chain():
    assert ev('[[1, 2], [3, 4]][1][0]') == 3
    assert ev("$var{info}['y'][0]", ) == 'h'
    assert ev("'hello'[1]") == 'e'


def test_index_errors():
    with pytest.raises(ExpressionError):  # 越界
        ev('$var{list}[5]')
    with pytest.raises(ExpressionError):  # 键不存在
        ev("$var{info}['nope']")
    with pytest.raises(ExpressionError):  # 下标非整数
        ev("'abc'['x']")
    with pytest.raises(ExpressionError):  # 对数字下标
        ev('5[0]')


# ---------------------------------------------------------------- 字面量

@pytest.mark.parametrize('expr,expected', [
    ('True', True),
    ('False', False),
    ('true', True),
    ('None', None),
    ('null', None),
    ('[1, 2, 3]', [1, 2, 3]),
    ('[]', []),
    ('["a", "b"]', ['a', 'b']),
])
def test_literals(expr, expected):
    assert ev(expr) == expected


# ---------------------------------------------------------------- 变量命名空间

def test_namespaces():
    # $ctx 与 $var 等价查运行变量
    assert ev('$ctx{a} + 1') == 6
    assert ev('$ctx{ocr_text}', CTX) == 'Hello World 123'
    assert ev("upper($ctx{ocr_text})", CTX) == 'HELLO WORLD 123'
    # $env 走系统环境解析
    assert isinstance(ev('$env{current_time}'), str)
    assert ev('$env{project_path}', FakeCtx({'a': 1})) == ''


def test_empty_key_var():
    with pytest.raises(ExpressionError):
        ev('$var{}')


# ---------------------------------------------------------------- 错误处理

@pytest.mark.parametrize('expr', [
    '1/0',
    '1//0',
    '1%0',
    '10 +',
    '(1+2',
    '1+2)',
    'abc',
    '1 2',
    '$var{a} + $var{b',  # 未闭合大括号 → tokenizer 触发 BAD 或标识符错误，必须报错
    'unknown_func(1)',
])
def test_errors(expr):
    with pytest.raises(ExpressionError):
        ev(expr)


def test_empty_and_nonstring():
    assert ev('') == ''
    assert ev('   ') == '   '
    assert ev(123) == 123
    assert ev(None) is None
    assert ev(['a']) == ['a']


def test_error_message_contains_context():
    try:
        ev('1/0')
    except ExpressionError as e:
        assert '0' in str(e)
    else:
        raise AssertionError('Expected ExpressionError')