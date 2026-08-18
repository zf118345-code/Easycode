# core/params/base/variable_op.py
# 变量操作节点参数定义：精简为「目标变量 + 最新赋值（自由表达式）」
# var_type 只在左侧变量面板创建变量时使用，此处不再出现。

EXPRESSION_HELP = [
    '变量引用（严格前缀，可从左侧变量面板复制）：',
    '  $var{变量名}    用户全局变量',
    '  $ctx{字段名}    运行上下文变量',
    '  $env{字段名}    系统环境变量',
    '',
    '算术：  +  -  *  /  //  %  **   （自由嵌套括号）',
    '比较：  >  >=  <  <=  ==  !=   （结果 true/false）',
    '逻辑：  and  /  or  /  not',
    '三元：  $var{a} > 10 ? "大" : "小"',
    '        或  "大" if $var{a} > 10 else "小"',
    '',
    "字符串：  'text' 或 \"text\"，+ 可直接拼接（$var{a}+'ing'）",
    "下标：  $var{list}[0] / $var{list}[-1] / $var{dict}['key']",
    '列表：  [1, 2, 3] / [\'a\', \'b\']',
    '',
    '常用函数：',
    '  str()  int()  float()  bool()  len()  abs()',
    '  min()  max()  round()  sum()',
    '  upper()  lower()  strip()  replace()  split()  join()',
    '  contains()  startswith()  endswith()',
    '',
    '示例：',
    '  $var{b}+$var{c}-$var{d}*$var{e}/$var{f}',
    "  $var{count}+'ing'",
    "  upper($var{name}) + ' - 完成'",
    '  sum($var{score_list}) / len($var{score_list})',
]


def build_variable_op_params() -> dict:
    return {
        'target_var': {
            'type': 'str',
            'label': '目标变量',
            'default': '',
            'placeholder': '目标变量名，如 $var{run_count}（可从左侧变量面板复制）',
            'help': [
                '目标变量 = 运算结果的写入目标。',
                '格式（严格前缀）：',
                '  $var{变量名}    用户全局变量',
                '  $ctx{字段名}    运行上下文变量',
                '  $env{字段名}    系统环境变量',
                '示例：$var{run_count}',
            ],
        },
        'new_value': {
            'type': 'textarea',
            'label': '最新赋值（自由表达式）',
            'default': '',
            'rows': 4,
            'placeholder': (
                '支持任意运算，如：$var{总量} = $var{a}+$var{b}-$var{c}*$var{d}/$var{e}；'
                "拼接：$var{name}+'ed'；函数：upper($var{name})"
            ),
            'help': EXPRESSION_HELP,
        },
    }


PARAM_DEFINITIONS: dict = {
    'variable_op': {
        'label': '变量操作',
        'modes': ['workflow'],
        'params': build_variable_op_params(),
    }
}