# core/expressions.py
# ⚡ 全局变量自由表达式求值器
# 用于 variable_op 的「最新赋值」字段：支持算术/比较/逻辑/三元/函数/下标。
# 变量引用必须严格前缀：$var{name} / $ctx{name} / $env{name} / $sys{name}
# （裸变量名一律不识别；$var{} 有值则用值，无值则视为 None，可用 or 兜底）。

import re
from dataclasses import dataclass
from typing import Any

from core.utils import _resolve_env_var


class ExpressionError(Exception):
    """表达式语法错误或运行时错误（消息为中文可读文案）"""


# ---------------------------------------------------------------- AST 节点

@dataclass
class _Literal:
    value: Any


@dataclass
class _Var:
    ns: str   # var / ctx / env / sys
    key: str


@dataclass
class _List:
    items: list


@dataclass
class _Call:
    func: str
    args: list


@dataclass
class _Unary:
    op: str
    operand: Any


@dataclass
class _BinOp:
    op: str
    left: Any
    right: Any


@dataclass
class _Compare:
    first: Any
    pairs: list  # [(op, node), ...] 链式比较


@dataclass
class _Ternary:
    cond: Any
    if_true: Any
    if_false: Any


@dataclass
class _IfElse:
    cond: Any
    if_true: Any
    if_false: Any


@dataclass
class _Index:
    obj: Any
    index: Any


# ---------------------------------------------------------------- Tokenizer

class Token:
    __slots__ = ('kind', 'value')

    def __init__(self, kind: str, value: Any = None):
        self.kind = kind
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f'Token({self.kind!r}, {self.value!r})'


_TOKEN_RE = re.compile(r'''
    (?P<WS>\s+)
  | (?P<NUMBER>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
  | (?P<STRING>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
  | (?P<VAR>\$(?:var|ctx|env|sys)\{[^{}]*\})
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP2>>=|<=|==|!=|\/\/|\*\*)
  | (?P<OP>[+\-*/%()\[\],?:<>])
  | (?P<BAD>.)
''', re.VERBOSE)

_KEYWORDS = {'and', 'or', 'not', 'if', 'else'}
_TRUE_WORDS = {'true', 'True', 'TRUE'}
_FALSE_WORDS = {'false', 'False', 'FALSE'}
_NONE_WORDS = {'none', 'None', 'null'}


def _unescape_string(raw: str) -> str:
    """去掉引号并处理 \\ 转义（\\n \\t \\r \\\\ \\' \\" 等）"""
    body = raw[1:-1]
    out = []
    i = 0
    mapping = {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', '\\': '\\', "'": "'", '"': '"'}
    while i < len(body):
        c = body[i]
        if c == '\\' and i + 1 < len(body):
            nxt = body[i + 1]
            out.append(mapping.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def tokenize(text: str) -> list:
    tokens = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise ExpressionError(f'第 {pos + 1} 个字符处存在无法识别的字符: {text[pos]!r}')
        kind = m.lastgroup
        raw = m.group()
        pos = m.end()

        if kind == 'WS':
            continue
        if kind == 'NUMBER':
            val = raw
            tokens.append(Token('NUMBER', float(val) if ('.' in val or 'e' in val or 'E' in val) else int(val)))
        elif kind == 'STRING':
            tokens.append(Token('STRING', _unescape_string(raw)))
        elif kind == 'VAR':
            m2 = re.match(r'\$([a-z]+)\{([^{}]*)\}', raw)
            tokens.append(Token('VAR', (m2.group(1), m2.group(2).strip())))
        elif kind == 'IDENT':
            if raw in _KEYWORDS:
                tokens.append(Token(raw.upper(), raw))
            elif raw in _TRUE_WORDS:
                tokens.append(Token('LITERAL', True))
            elif raw in _FALSE_WORDS:
                tokens.append(Token('LITERAL', False))
            elif raw in _NONE_WORDS:
                tokens.append(Token('LITERAL', None))
            else:
                tokens.append(Token('IDENT', raw))
        elif kind in ('OP2', 'OP'):
            tokens.append(Token(raw, raw))
        else:  # BAD —— 理论上不可达（regex 的 . 会吞掉任意字符）
            raise ExpressionError(f'第 {pos - len(raw) + 1} 个字符处存在无法识别的字符: {raw!r}')

    tokens.append(Token('EOF', None))
    return tokens


# ---------------------------------------------------------------- Parser

class _Parser:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at_end(self) -> bool:
        return self.peek().kind == 'EOF'

    def match(self, kind: str) -> bool:
        if self.peek().kind == kind:
            self.pos += 1
            return True
        return False

    def expect(self, kind: str, message: str):
        if not self.match(kind):
            raise ExpressionError(message)

    # expression → ternary
    def parse(self):
        if self.at_end():
            raise ExpressionError('表达式为空')
        node = self.parse_ternary()
        if not self.at_end():
            raise ExpressionError(f'表达式末尾存在多余内容: {self.peek().value!r}')
        return node

    # ternary → orExpr (('?' expr ':' expr) | ('if' orExpr 'else' expr))?
    def parse_ternary(self):
        or_node = self.parse_or()
        if self.match('IF'):
            cond = self.parse_or()
            self.expect('ELSE', '三元表达式缺少 else 分支')
            else_node = self.parse_ternary()
            return _IfElse(cond, or_node, else_node)
        if self.match('?'):
            if_true = self.parse_ternary()
            self.expect(':', '三元表达式缺少 ":" 分隔符（格式: 条件 ? 值1 : 值2）')
            if_false = self.parse_ternary()
            return _Ternary(or_node, if_true, if_false)
        return or_node

    # or → and ('or' and)*
    def parse_or(self):
        node = self.parse_and()
        while self.match('OR'):
            right = self.parse_and()
            node = _BinOp('or', node, right)
        return node

    # and → not ('and' not)*
    def parse_and(self):
        node = self.parse_not()
        while self.match('AND'):
            right = self.parse_not()
            node = _BinOp('and', node, right)
        return node

    # not → 'not' not | comparison
    def parse_not(self):
        if self.match('NOT'):
            return _Unary('not', self.parse_not())
        return self.parse_comparison()

    # comparison → additive (比较符 additive)*
    def parse_comparison(self):
        node = self.parse_additive()
        pairs = []
        while self.peek().kind in ('>', '>=', '<', '<=', '==', '!='):
            op = self.next().kind
            right = self.parse_additive()
            pairs.append((op, right))
        if pairs:
            return _Compare(node, pairs)
        return node

    # additive → mult (('+'|'-') mult)*
    def parse_additive(self):
        node = self.parse_mult()
        while self.peek().kind in ('+', '-'):
            op = self.next().kind
            right = self.parse_mult()
            node = _BinOp(op, node, right)
        return node

    # mult → unary (('*'|'/'|'//'|'%') unary)*
    def parse_mult(self):
        node = self.parse_unary()
        while self.peek().kind in ('*', '/', '//', '%'):
            op = self.next().kind
            right = self.parse_unary()
            node = _BinOp(op, node, right)
        return node

    # unary → ('-'|'+') unary | power
    def parse_unary(self):
        if self.peek().kind == '-':
            self.next()
            return _Unary('-', self.parse_unary())
        if self.peek().kind == '+':
            self.next()
            return _Unary('+', self.parse_unary())
        return self.parse_power()

    # power → postfix ('**' unary)?   （右结合）
    def parse_power(self):
        node = self.parse_postfix()
        if self.match('**'):
            right = self.parse_unary()
            return _BinOp('**', node, right)
        return node

    # postfix → atom ('[' expr ']')*
    def parse_postfix(self):
        node = self.parse_atom()
        while self.peek().kind == '[':
            self.next()
            index = self.parse_ternary()
            self.expect(']', '下标表达式缺少 "]"')
            node = _Index(node, index)
        return node

    # atom → 字面量 | 变量 | 函数调用 | 括号 | 列表字面量
    def parse_atom(self):
        tok = self.peek()

        if tok.kind == 'NUMBER':
            self.next()
            return _Literal(tok.value)
        if tok.kind == 'STRING':
            self.next()
            return _Literal(tok.value)
        if tok.kind == 'LITERAL':
            self.next()
            return _Literal(tok.value)
        if tok.kind == 'VAR':
            self.next()
            ns, key = tok.value
            if not key:
                raise ExpressionError(f'${ns}{{}} 变量名为空（格式: ${ns}{{变量名}}）')
            return _Var(ns, key)
        if tok.kind == 'IDENT':
            self.next()
            if self.match('('):
                args = []
                if not self.peek().kind == ')':
                    while True:
                        args.append(self.parse_ternary())
                        if not self.match(','):
                            break
                self.expect(')', f'函数 {tok.value} 缺少 ")"')
                return _Call(tok.value, args)
            raise ExpressionError(f'未知标识符: {tok.value}（仅支持函数调用与变量 $var{{}}/$ctx{{}}/$env{{}}）')
        if tok.kind == '(':
            self.next()
            node = self.parse_ternary()
            self.expect(')', '括号表达式缺少 ")"（括号不匹配）')
            return node
        if tok.kind == '[':
            self.next()
            items = []
            if not self.peek().kind == ']':
                while True:
                    items.append(self.parse_ternary())
                    if not self.match(','):
                        break
            self.expect(']', '列表字面量缺少 "]"')
            return _List(items)

        raise ExpressionError(f'此处需要表达式，但遇到: {tok.value!r}')


# ---------------------------------------------------------------- Evaluator

# 函数白名单：未在此清单中的函数一律拒绝
FUNC_WHITELIST = {
    'str', 'int', 'float', 'bool', 'len', 'abs', 'min', 'max', 'round', 'sum',
    'upper', 'lower', 'strip', 'replace', 'split', 'join',
    'contains', 'startswith', 'endswith',
}


def _truthy(v) -> bool:
    return bool(v)


def _resolve_var(ns: str, key: str, ctx) -> Any:
    """解析变量 token。var/ctx 查运行变量（未定义→None）；env/sys 走系统环境解析。"""
    if ns in ('var', 'ctx'):
        if ctx is None or not hasattr(ctx, 'variables') or not isinstance(ctx.variables, dict):
            return None
        return ctx.variables.get(key)
    return _resolve_env_var(key, ctx, f'${ns}{{{key}}}')


def _as_number(v, what: str, node=None):
    """宽松数值转换，失败报可读错误"""
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ExpressionError(f'{what} 需要数字，实际得到: {v!r}（类型 {type(v).__name__}）')


def _require_index_type(idx):
    if isinstance(idx, bool):
        return int(idx)
    if isinstance(idx, int):
        return idx
    if isinstance(idx, float) and idx.is_integer():
        return int(idx)
    raise ExpressionError(f'下标必须是整数，实际得到: {idx!r}')


def _compare(op: str, a, b) -> bool:
    if op == '==':
        return a == b
    if op == '!=':
        return a != b
    # 大小比较：优先数值比较（字符串数字也按数值比），其余按 Python 语义
    if not isinstance(a, bool) and not isinstance(b, bool):
        try:
            fa, fb = float(a), float(b)
            a, b = fa, fb
        except (TypeError, ValueError):
            pass
    if op == '>':
        return a > b
    if op == '>=':
        return a >= b
    if op == '<':
        return a < b
    if op == '<=':
        return a <= b
    raise ExpressionError(f'不支持的比较运算符: {op}')


def _call_function(name: str, args: list) -> Any:
    """执行白名单函数。args 已求值为实际值。"""
    if name == 'str':
        return str(args[0])
    if name == 'int':
        try:
            return int(args[0])
        except (TypeError, ValueError):
            # 宽容：数字字符串（如 '12.5'）先按浮点取整
            try:
                return int(float(args[0]))
            except (TypeError, ValueError):
                raise ExpressionError(f'int() 无法转换: {args[0]!r}')
    if name == 'float':
        try:
            return float(args[0])
        except (TypeError, ValueError):
            raise ExpressionError(f'float() 无法转换: {args[0]!r}')
    if name == 'bool':
        return bool(args[0])
    if name == 'len':
        try:
            return len(args[0])
        except TypeError:
            raise ExpressionError(f'len() 不支持的类型: {args[0]!r}')
    if name == 'abs':
        try:
            return abs(args[0])
        except TypeError:
            raise ExpressionError(f'abs() 需要数字，实际得到: {args[0]!r}')
    if name == 'min':
        try:
            return min(args)
        except (TypeError, ValueError):
            raise ExpressionError(f'min() 参数无效: {args!r}')
    if name == 'max':
        try:
            return max(args)
        except (TypeError, ValueError):
            raise ExpressionError(f'max() 参数无效: {args!r}')
    if name == 'round':
        return round(args[0], int(args[1]) if len(args) > 1 else 0)
    if name == 'sum':
        try:
            return sum(args[0])
        except TypeError:
            raise ExpressionError(f'sum() 需要可枚举集合，实际得到: {args[0]!r}')

    # ---- 字符串类函数：对字符串参数宽容 str() 转换 ----
    if name == 'upper':
        return str(args[0]).upper()
    if name == 'lower':
        return str(args[0]).lower()
    if name == 'strip':
        s = str(args[0])
        return s.strip(args[1]) if len(args) > 1 else s.strip()
    if name == 'replace':
        s = str(args[0])
        if len(args) < 3:
            raise ExpressionError('replace() 需要 3 个参数: replace(文本, 旧值, 新值)')
        return s.replace(str(args[1]), str(args[2]), int(args[3]) if len(args) > 3 else -1)
    if name == 'split':
        s = str(args[0])
        sep = args[1] if len(args) > 1 and args[1] is not None else None
        return s.split(str(sep) if sep is not None else None)
    if name == 'join':
        if len(args) == 1:
            items, sep = args[0], ''
        else:
            a, b = args[0], args[1]
            if isinstance(a, (list, tuple)) and isinstance(b, str):
                items, sep = a, b
            elif isinstance(a, str) and isinstance(b, (list, tuple)):
                sep, items = a, b
            elif isinstance(a, (list, tuple)):
                items, sep = a, str(b)
            else:
                items, sep = b, str(a)
        try:
            return str(sep).join(str(x) for x in items)
        except TypeError:
            raise ExpressionError(f'join() 需要集合参数，实际得到: {items!r}')
    if name == 'contains':
        a, b = args[0], args[1]
        if isinstance(a, (list, tuple, dict)):
            return b in a
        return str(b) in str(a)
    if name == 'startswith':
        return str(args[0]).startswith(str(args[1]))
    if name == 'endswith':
        return str(args[0]).endswith(str(args[1]))

    raise ExpressionError(f'不支持的函数: {name}（可用: {", ".join(sorted(FUNC_WHITELIST))}）')


def eval_node(node, ctx) -> Any:
    t = type(node)

    if t is _Literal:
        return node.value
    if t is _Var:
        return _resolve_var(node.ns, node.key, ctx)
    if t is _List:
        return [eval_node(x, ctx) for x in node.items]

    if t is _Call:
        if node.func not in FUNC_WHITELIST:
            raise ExpressionError(
                f'不支持的函数: {node.func}（可用: {", ".join(sorted(FUNC_WHITELIST))}）'
            )
        args = [eval_node(a, ctx) for a in node.args]
        return _call_function(node.func, args)

    if t is _Unary:
        v = eval_node(node.operand, ctx)
        if node.op == 'not':
            return not _truthy(v)
        if node.op == '-':
            return -_as_number(v, '一元负号', node)
        if node.op == '+':
            return _as_number(v, '一元正号', node)
        raise ExpressionError(f'不支持的一元运算符: {node.op}')

    if t is _BinOp:
        op = node.op
        if op == 'and':
            left = eval_node(node.left, ctx)
            return left if not _truthy(left) else eval_node(node.right, ctx)
        if op == 'or':
            left = eval_node(node.left, ctx)
            return left if _truthy(left) else eval_node(node.right, ctx)

        left = eval_node(node.left, ctx)
        right = eval_node(node.right, ctx)

        if op == '+':
            # 宽松拼接：任一侧为字符串时两侧都转字符串做拼接（$var{a}+'ing' 直接可用）
            if isinstance(left, str) or isinstance(right, str):
                return _to_str_join(left) + _to_str_join(right)
            return left + right
        if op == '-':
            return _as_number(left, '"-" 左侧', node) - _as_number(right, '"-" 右侧', node)
        if op == '*':
            try:
                return left * right
            except TypeError:
                raise ExpressionError(f'无法相乘: {left!r} * {right!r}')
        if op == '/':
            r = _as_number(right, '" / " 右侧', node)
            if r == 0:
                raise ExpressionError('除法运算遇到除数为 0')
            return _as_number(left, '" / " 左侧', node) / r
        if op == '//':
            r = _as_number(right, '" // " 右侧', node)
            if r == 0:
                raise ExpressionError('整除运算遇到除数为 0')
            return _as_number(left, '" // " 左侧', node) // r
        if op == '%':
            r = _as_number(right, '" % " 右侧', node)
            if r == 0:
                raise ExpressionError('取余运算遇到除数为 0')
            return _as_number(left, '" % " 左侧', node) % r
        if op == '**':
            return _as_number(left, '"**" 左侧', node) ** _as_number(right, '"**" 右侧', node)
        raise ExpressionError(f'不支持的二元运算符: {op}')

    if t is _Compare:
        current = eval_node(node.first, ctx)
        for op, expr in node.pairs:
            nxt = eval_node(expr, ctx)
            if not _compare(op, current, nxt):
                return False
            current = nxt
        return True

    if t is _Ternary:
        return eval_node(node.if_true, ctx) if _truthy(eval_node(node.cond, ctx)) else eval_node(node.if_false, ctx)

    if t is _IfElse:
        return eval_node(node.if_true, ctx) if _truthy(eval_node(node.cond, ctx)) else eval_node(node.if_false, ctx)

    if t is _Index:
        obj = eval_node(node.obj, ctx)
        idx = eval_node(node.index, ctx)
        try:
            if isinstance(obj, dict):
                return obj[idx]
            return obj[_require_index_type(idx)]
        except (KeyError, IndexError, TypeError, ValueError) as e:
            if isinstance(obj, dict):
                raise ExpressionError(f'字典中不存在键: {idx!r}')
            if isinstance(obj, (list, tuple, str)):
                raise ExpressionError(f'索引越界或无效: {idx!r}（集合长度 {len(obj)}）')
            raise ExpressionError(f'无法对 {type(obj).__name__} 类型进行下标访问')

    raise ExpressionError(f'未知 AST 节点类型: {t.__name__}')


def _to_str_join(v) -> str:
    """字符串拼接辅助：数字转字符串"""
    if isinstance(v, bool):
        return 'True' if v else 'False'
    return str(v)


def evaluate_expression(text: Any, context=None) -> Any:
    """
    表达式求值入口
    :param text: 表达式字符串。空串/空白/非字符串 → 原样返回。
    :param context: 执行上下文（需有 variables 属性）；为 None 时 $var/$ctx 解析为 None。
    :return: 求值结果（类型由表达式自然决定）
    :raises ExpressionError: 语法错误或运行时错误
    """
    if not isinstance(text, str) or not text.strip():
        return text
    try:
        tokens = tokenize(text)
        ast = _Parser(tokens).parse()
        return eval_node(ast, context)
    except ExpressionError:
        raise
    except Exception as e:  # pragma: no cover - 兜底，避免求值器崩溃整个流程
        raise ExpressionError(f'表达式求值失败: {e}')