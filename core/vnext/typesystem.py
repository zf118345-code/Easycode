"""Shared static and runtime type semantics for EasyCode vNext.

The language intentionally has a small, explicit type system.  Static analysis,
ECIR compilation and the defensive runtime checks all import this module so a
value cannot mean one thing in the editor and another thing while executing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EasyType:
    name: str
    arguments: tuple[EasyType, ...] = ()

    def __str__(self) -> str:
        if not self.arguments:
            return self.name
        return f'{self.name}<{", ".join(str(item) for item in self.arguments)}>'


@dataclass(frozen=True)
class TypedValue:
    value_type: EasyType
    literal_known: bool = False
    literal: Any = None


@dataclass(frozen=True)
class TypeIssue:
    code: str
    message: str
    node: ast.AST
    hint: str = ''


@dataclass(frozen=True)
class TypeValidationResult:
    issues: tuple[TypeIssue, ...]
    local_types: dict[str, str]


ANY = EasyType('任意')
NULL = EasyType('空')
TEXT = EasyType('文本')
INTEGER = EasyType('整数')
DECIMAL = EasyType('小数')
BOOLEAN = EasyType('布尔')
DURATION = EasyType('持续时间')
TIME_POINT = EasyType('时间点')

_KNOWN_ATOMIC_TYPES = {
    '任意', '空', '文本', '整数', '小数', '布尔', '持续时间', '时间点',
    '坐标', '矩形', '图片资源', '页面', '目标', '控件选择器', '拖拽路径',
    '图像匹配结果',
}
_TYPE_ALIASES = {
    'any': '任意', 'Any': '任意', 'None': '空', 'none': '空',
    'str': '文本', 'string': '文本', 'int': '整数', 'float': '小数',
    'bool': '布尔', 'list': '列表', 'dict': '字典', 'Optional': '可选',
}
_DOMAIN_MEMBERS = {
    '图像匹配结果': {
        '已找到': BOOLEAN, '中心': EasyType('坐标'),
        '位置': EasyType('可选', (EasyType('坐标'),)),
        '区域': EasyType('可选', (EasyType('矩形'),)), '相似度': DECIMAL,
    },
}


def _split_generic_arguments(value: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(value):
        if character in '<[':
            depth += 1
        elif character in '>]':
            depth = max(0, depth - 1)
        elif character == ',' and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return [item for item in result if item]


def parse_type(value: str | EasyType | None) -> EasyType:
    if isinstance(value, EasyType):
        return value
    raw = ''.join(str(value or '任意').split())
    raw = _TYPE_ALIASES.get(raw, raw)
    for opener, closer in (('<', '>'), ('[', ']')):
        index = raw.find(opener)
        if index > 0 and raw.endswith(closer):
            name = _TYPE_ALIASES.get(raw[:index], raw[:index])
            arguments = tuple(parse_type(item) for item in _split_generic_arguments(raw[index + 1:-1]))
            if name == '可选' and len(arguments) != 1:
                return EasyType('未知类型', (EasyType(raw),))
            if name == '列表' and not arguments:
                arguments = (ANY,)
            if name == '字典':
                arguments = arguments or (ANY, ANY)
                if len(arguments) == 1:
                    arguments = (TEXT, arguments[0])
            return EasyType(name, arguments)
    if raw == '列表':
        return EasyType('列表', (ANY,))
    if raw == '字典':
        return EasyType('字典', (ANY, ANY))
    return EasyType(raw or '任意')


def canonical_type_name(value: str | EasyType | None) -> str:
    return str(parse_type(value))


def is_known_type(value: EasyType) -> bool:
    if value.name in _KNOWN_ATOMIC_TYPES:
        return not value.arguments
    if value.name == '可选':
        return len(value.arguments) == 1 and is_known_type(value.arguments[0])
    if value.name == '列表':
        return len(value.arguments) == 1 and is_known_type(value.arguments[0])
    if value.name == '字典':
        return len(value.arguments) == 2 and all(is_known_type(item) for item in value.arguments)
    return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _literal_is_coordinate(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(_is_number(item) for item in value)


def _literal_is_region(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 4 and all(_is_number(item) for item in value)


def is_assignable(actual: TypedValue | EasyType, expected: EasyType | str) -> bool:
    typed = actual if isinstance(actual, TypedValue) else TypedValue(actual)
    source, target = typed.value_type, parse_type(expected)
    if target == ANY or source == ANY:
        return True
    if target.name == '可选':
        return source == NULL or is_assignable(typed, target.arguments[0])
    if source.name == '可选':
        return target.name == '可选' and is_assignable(source.arguments[0], target.arguments[0])
    if source == NULL:
        return target == NULL
    if source == target:
        return True
    if source == INTEGER and target == DECIMAL:
        return True
    if target == TIME_POINT and source == TEXT:
        return True
    if target.name in {'页面', '目标'} and source == TEXT:
        return True
    if target.name == '坐标':
        return typed.literal_known and _literal_is_coordinate(typed.literal)
    if target.name == '矩形':
        return typed.literal_known and _literal_is_region(typed.literal)
    if target.name == '控件选择器' and source.name == '字典':
        return True
    if target.name == '拖拽路径' and source.name == '列表':
        return True
    if source.name == target.name == '列表':
        return is_assignable(source.arguments[0], target.arguments[0])
    if source.name == target.name == '字典':
        return all(is_assignable(left, right) for left, right in zip(source.arguments, target.arguments, strict=True))
    return False


def runtime_value_conforms(value: Any, expected: EasyType | str) -> bool:
    target = parse_type(expected)
    if target == ANY:
        return True
    if target.name == '可选':
        return value is None or runtime_value_conforms(value, target.arguments[0])
    if target == NULL:
        return value is None
    if target == TEXT:
        return isinstance(value, str)
    if target == INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if target == DECIMAL:
        return _is_number(value)
    if target == BOOLEAN:
        return isinstance(value, bool)
    if target == DURATION:
        return _is_number(value) and value >= 0
    if target == TIME_POINT:
        return isinstance(value, (str, datetime))
    if target.name == '坐标':
        return _literal_is_coordinate(value) or (
            isinstance(value, dict) and _is_number(value.get('x')) and _is_number(value.get('y'))
        )
    if target.name == '矩形':
        return _literal_is_region(value) or (
            isinstance(value, dict)
            and (
                all(_is_number(value.get(name)) for name in ('left', 'top', 'right', 'bottom'))
                or all(_is_number(value.get(name)) for name in ('x', 'y', 'width', 'height'))
            )
        )
    if target.name == '图片资源':
        return (isinstance(value, str) and bool(value)) or (
            isinstance(value, dict) and bool(value.get('resource_name') or value.get('asset_id'))
        )
    if target.name in {'页面', '目标'}:
        return isinstance(value, (str, dict))
    if target.name == '控件选择器':
        return isinstance(value, dict)
    if target.name == '拖拽路径':
        return isinstance(value, list) and bool(value)
    if target.name == '图像匹配结果':
        return isinstance(value, dict)
    if target.name in {'file_ref', 'directory_ref'}:
        if not isinstance(value, dict) or value.get('kind') != target.name:
            return False
        if not target.arguments:
            return True
        required = target.arguments[0].name
        return required in {str(item) for item in value.get('access') or []}
    if target.name == 'json_value':
        def is_json(item: Any) -> bool:
            if item is None or isinstance(item, (str, int, float, bool)):
                return True
            if isinstance(item, list):
                return all(is_json(child) for child in item)
            if isinstance(item, dict):
                return all(isinstance(key, str) and is_json(child) for key, child in item.items())
            return False

        return is_json(value)
    if target.name == '列表':
        return isinstance(value, list) and all(runtime_value_conforms(item, target.arguments[0]) for item in value)
    if target.name == '字典':
        return isinstance(value, dict) and all(
            runtime_value_conforms(key, target.arguments[0]) and runtime_value_conforms(item, target.arguments[1])
            for key, item in value.items()
        )
    return False


def _qualified_call_name(node: ast.Call) -> str:
    parts: list[str] = []
    current: ast.AST = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return '.'.join(reversed(parts))


def _common_type(values: list[TypedValue]) -> EasyType:
    if not values:
        return ANY
    current = values[0].value_type
    for item in values[1:]:
        other = item.value_type
        if other == current:
            continue
        if {other, current} <= {INTEGER, DECIMAL}:
            current = DECIMAL
        else:
            return ANY
    return current


class _TypeValidator:
    def __init__(self, declaration: ast.FunctionDef | ast.AsyncFunctionDef, functions: dict[str, Any]) -> None:
        self.declaration = declaration
        self.functions = functions
        self.issues: list[TypeIssue] = []
        self.environment: dict[str, TypedValue] = {}
        self.declared: dict[str, EasyType] = {}
        self.return_type = parse_type(_annotation_text(declaration.returns, '任意'))

    def issue(self, code: str, message: str, node: ast.AST, hint: str = '') -> None:
        self.issues.append(TypeIssue(code, message, node, hint))

    def _validate_declared_type(self, raw: str, node: ast.AST) -> EasyType:
        value_type = parse_type(raw)
        if not is_known_type(value_type):
            self.issue('E1200', f'未知类型：{raw}', node, '请使用 EasyCode 类型，例如 文本、整数、可选[矩形]')
            return ANY
        return value_type

    def _initialize_parameters(self) -> None:
        positional = [*self.declaration.args.posonlyargs, *self.declaration.args.args]
        defaults: list[ast.AST | None] = [None] * (len(positional) - len(self.declaration.args.defaults)) + list(self.declaration.args.defaults)
        for argument, default in zip(positional, defaults, strict=True):
            declared = self._validate_declared_type(_annotation_text(argument.annotation, '任意'), argument)
            self.environment[argument.arg] = TypedValue(declared)
            self.declared[argument.arg] = declared
            if default is not None:
                actual = self.infer(default)
                if not is_assignable(actual, declared):
                    self.issue(
                        'E1202',
                        f'参数“{argument.arg}”的默认值类型 {actual.value_type} 不能赋给 {declared}',
                        default,
                    )

    def _signature(self, name: str) -> Any | None:
        return self.functions.get(name)

    def infer(self, node: ast.AST | None, environment: dict[str, TypedValue] | None = None) -> TypedValue:
        env = environment if environment is not None else self.environment
        if node is None:
            return TypedValue(NULL, True, None)
        if isinstance(node, ast.Constant):
            value = node.value
            if value is None:
                return TypedValue(NULL, True, None)
            if isinstance(value, bool):
                return TypedValue(BOOLEAN, True, value)
            if isinstance(value, int):
                return TypedValue(INTEGER, True, value)
            if isinstance(value, float):
                return TypedValue(DECIMAL, True, value)
            if isinstance(value, str):
                return TypedValue(TEXT, True, value)
            return TypedValue(ANY, True, value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                self.issue('E1201', f'变量“{node.id}”尚未定义', node, '先赋值或将它声明为函数形参')
                return TypedValue(ANY)
            return env[node.id]
        if isinstance(node, ast.List):
            values = [self.infer(item, env) for item in node.elts]
            literal_known = all(item.literal_known for item in values)
            literal = [item.literal for item in values] if literal_known else None
            return TypedValue(EasyType('列表', (_common_type(values),)), literal_known, literal)
        if isinstance(node, ast.Dict):
            keys = [self.infer(item, env) for item in node.keys if item is not None]
            values = [self.infer(item, env) for item in node.values]
            literal_known = len(keys) == len(values) and all(item.literal_known for item in [*keys, *values])
            literal = {key.literal: value.literal for key, value in zip(keys, values, strict=True)} if literal_known else None
            return TypedValue(EasyType('字典', (_common_type(keys), _common_type(values))), literal_known, literal)
        if isinstance(node, ast.Call):
            name = _qualified_call_name(node)
            if name == '__easy_duration__':
                amount = self.infer(node.args[0], env) if node.args else TypedValue(ANY)
                if amount.value_type not in {INTEGER, DECIMAL, ANY}:
                    self.issue('E1203', '持续时间数值必须是整数或小数', node)
                return TypedValue(DURATION)
            if name == 'range':
                for item in node.args:
                    actual = self.infer(item, env)
                    if not is_assignable(actual, INTEGER):
                        self.issue('E1204', f'range 参数需要整数，实际为 {actual.value_type}', item)
                return TypedValue(EasyType('列表', (INTEGER,)))
            definition = self._signature(name)
            if definition is None:
                for item in node.args:
                    self.infer(item, env)
                for item in node.keywords:
                    self.infer(item.value, env)
                return TypedValue(ANY)
            parameters = list(getattr(definition, 'parameters', ()) or ())
            if len(node.args) > len(parameters):
                self.issue('E1205', f'{name} 最多接受 {len(parameters)} 个位置参数', node)
            keyword_values = {item.arg: item.value for item in node.keywords if item.arg}
            checked: set[int] = set()
            for index, parameter in enumerate(parameters):
                argument = node.args[index] if index < len(node.args) else keyword_values.get(parameter.name)
                if argument is None:
                    continue
                checked.add(id(argument))
                actual = self.infer(argument, env)
                expected = parse_type(parameter.value_type)
                if not is_assignable(actual, expected):
                    self.issue(
                        'E1204',
                        f'{name} 的参数“{parameter.name}”需要 {expected}，实际为 {actual.value_type}',
                        argument,
                    )
            for argument in [*node.args, *(item.value for item in node.keywords)]:
                if id(argument) not in checked:
                    self.infer(argument, env)
            return TypedValue(parse_type(getattr(definition, 'return_type', '任意')))
        if isinstance(node, ast.Attribute):
            owner = self.infer(node.value, env)
            member = _DOMAIN_MEMBERS.get(owner.value_type.name, {}).get(node.attr)
            if member is None and owner.value_type != ANY:
                self.issue('E1206', f'{owner.value_type} 没有成员“{node.attr}”', node)
                return TypedValue(ANY)
            return TypedValue(member or ANY)
        if isinstance(node, ast.UnaryOp):
            operand = self.infer(node.operand, env)
            if isinstance(node.op, ast.Not):
                if not is_assignable(operand, BOOLEAN):
                    self.issue('E1207', f'“非”需要布尔值，实际为 {operand.value_type}', node.operand)
                return TypedValue(BOOLEAN)
            if operand.value_type not in {INTEGER, DECIMAL, ANY}:
                self.issue('E1208', f'正负号只能用于数字，实际为 {operand.value_type}', node.operand)
                return TypedValue(ANY)
            return TypedValue(operand.value_type)
        if isinstance(node, ast.BoolOp):
            for item in node.values:
                actual = self.infer(item, env)
                if not is_assignable(actual, BOOLEAN):
                    self.issue('E1207', f'逻辑运算需要布尔值，实际为 {actual.value_type}', item)
            return TypedValue(BOOLEAN)
        if isinstance(node, ast.BinOp):
            left, right = self.infer(node.left, env), self.infer(node.right, env)
            if isinstance(node.op, ast.Add) and left.value_type == right.value_type == TEXT:
                return TypedValue(TEXT)
            if isinstance(node.op, ast.Add) and left.value_type.name == right.value_type.name == '列表':
                left_item = left.value_type.arguments[0] if left.value_type.arguments else ANY
                right_item = right.value_type.arguments[0] if right.value_type.arguments else ANY
                return TypedValue(EasyType('列表', (_common_type([
                    TypedValue(left_item), TypedValue(right_item),
                ]),)))
            if left.value_type in {INTEGER, DECIMAL, ANY} and right.value_type in {INTEGER, DECIMAL, ANY}:
                if isinstance(node.op, ast.Div) or DECIMAL in {left.value_type, right.value_type}:
                    return TypedValue(DECIMAL)
                return TypedValue(INTEGER if ANY not in {left.value_type, right.value_type} else ANY)
            self.issue('E1209', f'运算符不能用于 {left.value_type} 和 {right.value_type}', node)
            return TypedValue(ANY)
        if isinstance(node, ast.Compare):
            left = self.infer(node.left, env)
            for operator, comparator in zip(node.ops, node.comparators, strict=True):
                right = self.infer(comparator, env)
                if isinstance(operator, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                    numeric = left.value_type in {INTEGER, DECIMAL, ANY} and right.value_type in {INTEGER, DECIMAL, ANY}
                    textual = left.value_type == right.value_type == TEXT
                    if not numeric and not textual:
                        self.issue('E1210', f'不能比较 {left.value_type} 和 {right.value_type} 的大小', comparator)
                left = right
            return TypedValue(BOOLEAN)
        if isinstance(node, ast.Subscript):
            owner, key = self.infer(node.value, env), self.infer(node.slice, env)
            if owner.value_type.name == '列表':
                if not is_assignable(key, INTEGER):
                    self.issue('E1211', '列表下标必须是整数', node.slice)
                return TypedValue(owner.value_type.arguments[0])
            if owner.value_type.name == '字典':
                if not is_assignable(key, owner.value_type.arguments[0]):
                    self.issue('E1211', f'字典键需要 {owner.value_type.arguments[0]}', node.slice)
                return TypedValue(owner.value_type.arguments[1])
            if owner.value_type == TEXT:
                if not is_assignable(key, INTEGER):
                    self.issue('E1211', '文本下标必须是整数', node.slice)
                return TypedValue(TEXT)
            if owner.value_type != ANY:
                self.issue('E1211', f'{owner.value_type} 不支持下标访问', node)
            return TypedValue(ANY)
        self.issue('E1212', f'暂不支持表达式：{type(node).__name__}', node)
        return TypedValue(ANY)

    @staticmethod
    def _narrow(environment: dict[str, TypedValue], test: ast.AST, truthy: bool) -> dict[str, TypedValue]:
        narrowed = dict(environment)
        if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
            return narrowed
        name: ast.Name | None = test.left if isinstance(test.left, ast.Name) else None
        other = test.comparators[0]
        if name is None or not isinstance(other, ast.Constant) or other.value is not None:
            return narrowed
        value = narrowed.get(name.id)
        if value is None or value.value_type.name != '可选':
            return narrowed
        is_not = isinstance(test.ops[0], ast.IsNot)
        non_null_branch = truthy == is_not
        narrowed[name.id] = TypedValue(value.value_type.arguments[0] if non_null_branch else NULL)
        return narrowed

    def _merge_branches(
        self,
        base: dict[str, TypedValue],
        left: dict[str, TypedValue],
        right: dict[str, TypedValue],
    ) -> dict[str, TypedValue]:
        merged = dict(base)
        for name in set(left) & set(right):
            if name in self.declared:
                merged[name] = TypedValue(self.declared[name])
            elif left[name].value_type == right[name].value_type:
                merged[name] = TypedValue(left[name].value_type)
            elif {left[name].value_type, right[name].value_type} <= {INTEGER, DECIMAL}:
                merged[name] = TypedValue(DECIMAL)
            else:
                merged[name] = TypedValue(ANY)
        return merged

    def validate_block(self, statements: list[ast.stmt], environment: dict[str, TypedValue] | None = None) -> dict[str, TypedValue]:
        env = dict(environment if environment is not None else self.environment)
        for statement in statements:
            if isinstance(statement, ast.Assign):
                actual = self.infer(statement.value, env)
                for target in statement.targets:
                    if not isinstance(target, ast.Name):
                        self.issue('E1213', '赋值目标必须是变量名', target)
                        continue
                    declared = self.declared.get(target.id)
                    if declared is not None and not is_assignable(actual, declared):
                        self.issue('E1214', f'不能把 {actual.value_type} 赋给变量“{target.id}”的 {declared}', statement.value)
                    env[target.id] = TypedValue(declared, actual.literal_known, actual.literal) if declared else actual
                continue
            if isinstance(statement, ast.AnnAssign):
                if not isinstance(statement.target, ast.Name):
                    self.issue('E1213', '带类型的赋值目标必须是变量名', statement.target)
                    continue
                declared = self._validate_declared_type(_annotation_text(statement.annotation), statement.annotation)
                self.declared[statement.target.id] = declared
                if statement.value is None:
                    self.issue('E1215', f'变量“{statement.target.id}”声明后必须立即赋值', statement)
                    env[statement.target.id] = TypedValue(declared)
                    continue
                actual = self.infer(statement.value, env)
                if not is_assignable(actual, declared):
                    self.issue('E1214', f'不能把 {actual.value_type} 赋给变量“{statement.target.id}”的 {declared}', statement.value)
                env[statement.target.id] = TypedValue(declared, actual.literal_known, actual.literal)
                continue
            if isinstance(statement, ast.Expr):
                self.infer(statement.value, env)
                continue
            if isinstance(statement, ast.Return):
                actual = self.infer(statement.value, env)
                if not is_assignable(actual, self.return_type):
                    self.issue('E1216', f'返回值需要 {self.return_type}，实际为 {actual.value_type}', statement)
                continue
            if isinstance(statement, ast.If):
                condition = self.infer(statement.test, env)
                if not is_assignable(condition, BOOLEAN):
                    self.issue('E1207', f'如果条件需要布尔值，实际为 {condition.value_type}', statement.test)
                left = self.validate_block(statement.body, self._narrow(env, statement.test, True))
                right = self.validate_block(statement.orelse, self._narrow(env, statement.test, False)) if statement.orelse else dict(env)
                env = self._merge_branches(env, left, right)
                continue
            if isinstance(statement, ast.While):
                condition = self.infer(statement.test, env)
                if not is_assignable(condition, BOOLEAN):
                    self.issue('E1207', f'循环条件需要布尔值，实际为 {condition.value_type}', statement.test)
                self.validate_block(statement.body, self._narrow(env, statement.test, True))
                continue
            if isinstance(statement, ast.For):
                iterable = self.infer(statement.iter, env)
                if iterable.value_type.name == '列表':
                    item_type = iterable.value_type.arguments[0]
                elif iterable.value_type == TEXT:
                    item_type = TEXT
                elif iterable.value_type == ANY:
                    item_type = ANY
                else:
                    self.issue('E1217', f'{iterable.value_type} 不能用于“对于”循环', statement.iter)
                    item_type = ANY
                loop_env = dict(env)
                if isinstance(statement.target, ast.Name):
                    loop_env[statement.target.id] = TypedValue(item_type)
                self.validate_block(statement.body, loop_env)
                continue
            if isinstance(statement, ast.Try):
                body = self.validate_block(statement.body, env)
                alternatives = [body]
                for handler in statement.handlers:
                    caught = dict(env)
                    if handler.name:
                        caught[handler.name] = TypedValue(TEXT)
                    alternatives.append(self.validate_block(handler.body, caught))
                merged = alternatives[0]
                for alternative in alternatives[1:]:
                    merged = self._merge_branches(env, merged, alternative)
                env = self.validate_block(statement.finalbody, merged)
                self.validate_block(statement.orelse, body)
                continue
            if isinstance(statement, ast.With):
                for item in statement.items:
                    self.infer(item.context_expr, env)
                self.validate_block(statement.body, env)
                continue
            if isinstance(statement, (ast.Break, ast.Continue, ast.Pass)):
                continue
        return env

    @staticmethod
    def _block_definitely_returns(statements: list[ast.stmt]) -> bool:
        for statement in statements:
            if isinstance(statement, ast.Return):
                return True
            if (
                isinstance(statement, ast.If)
                and statement.orelse
                and _TypeValidator._block_definitely_returns(statement.body)
                and _TypeValidator._block_definitely_returns(statement.orelse)
            ):
                return True
            if isinstance(statement, ast.Try):
                paths = [statement.body, *(handler.body for handler in statement.handlers)]
                if paths and all(_TypeValidator._block_definitely_returns(path) for path in paths):
                    return True
        return False

    def validate(self) -> TypeValidationResult:
        if not is_known_type(self.return_type):
            self.issue('E1200', f'未知返回类型：{self.return_type}', self.declaration.returns or self.declaration)
            self.return_type = ANY
        self._initialize_parameters()
        self.environment = self.validate_block(self.declaration.body, self.environment)
        if self.return_type not in {ANY, NULL} and self.return_type.name != '可选' and not self._block_definitely_returns(self.declaration.body):
            self.issue('E1218', f'函数声明返回 {self.return_type}，但并非所有路径都有返回值', self.declaration)
        local_types = {name: str(value.value_type) for name, value in self.environment.items()}
        local_types.update({name: str(value) for name, value in self.declared.items()})
        return TypeValidationResult(tuple(self.issues), dict(sorted(local_types.items())))


def _annotation_text(node: ast.AST | None, default: str = '任意') -> str:
    if node is None:
        return default
    try:
        return ast.unparse(node).strip() or default
    except Exception:
        return default


def validate_function_types(
    declaration: ast.FunctionDef | ast.AsyncFunctionDef,
    functions: dict[str, Any],
) -> TypeValidationResult:
    return _TypeValidator(declaration, functions).validate()
