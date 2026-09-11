"""Authoritative creation catalog for format-6 pure values.

The ProgramDocument stores stable operation and field IDs, while the IDE only
projects human readable names.  This module is the only place that turns an
expected value type into concrete, executable pure-operation signatures.  The
browser receives already-resolved input/result types and never reimplements
generic inference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Mapping

from .program_validation import types_compatible
from .function_contracts_v6 import enum_choices
from .pure_operations_v6 import (
    EXECUTABLE_PURE_OPERATIONS,
    OPERATION_INPUT_NAMES,
    PURE_OPERATION_REGISTRY_VERSION,
    pure_operation_registry_hash,
    pure_operation_type_issues,
)
from .record_types_v6 import record_type_contract, record_type_payload


@dataclass(frozen=True)
class PureOperationPresentationV6:
    operation_id: str
    display_name: str
    category: str
    description: str
    input_labels: Mapping[str, str]
    syntax_name: str

    def discovery_dict(
        self,
        *,
        compatible: bool,
        result_type_hints: tuple[str, ...],
    ) -> dict[str, object]:
        operation_word = self.operation_id.removeprefix('core.').removesuffix('.v1').replace('_', ' ')
        return {
            'operation_id': self.operation_id,
            'display_name': self.display_name,
            'namespace': self.category,
            'group': _operation_group(self.operation_id, self.category),
            'description': self.description,
            'syntax_name': self.syntax_name,
            'aliases': [self.display_name, operation_word],
            'keywords': list(_operation_keywords(self)),
            'input_labels': [
                self.input_labels.get(name, name)
                for name in OPERATION_INPUT_NAMES[self.operation_id]
            ],
            'example': _operation_example(self.operation_id),
            'result_type_hints': list(result_type_hints),
            'compatible': compatible,
            'disabled_reason': '' if compatible else _incompatible_reason(result_type_hints),
        }


@dataclass(frozen=True)
class PureOperationCandidateV6:
    candidate_id: str
    operation_id: str
    display_name: str
    category: str
    description: str
    result_type: str
    inputs: tuple[tuple[str, str, str, tuple[dict[str, object], ...]], ...]
    syntax_name: str

    def to_dict(self) -> dict[str, object]:
        return {
            'candidate_id': self.candidate_id,
            'operation_id': self.operation_id,
            'display_name': self.display_name,
            'category': self.category,
            'description': self.description,
            'syntax_name': self.syntax_name,
            'result_type': self.result_type,
            'inputs': [
                {
                    'input_id': input_id,
                    'display_name': display_name,
                    'value_type': value_type,
                    'choices': list(choices),
                }
                for input_id, display_name, value_type, choices in self.inputs
            ],
        }


@dataclass(frozen=True)
class RecordMemberCandidateV6:
    candidate_id: str
    source: str
    source_id: str
    source_display_name: str
    source_value_type: str
    result_type: str
    path: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            'candidate_id': self.candidate_id,
            'source': self.source,
            'source_id': self.source_id,
            'source_display_name': self.source_display_name,
            'source_value_type': self.source_value_type,
            'result_type': self.result_type,
            'path': [
                {'field_id': field_id, 'display_name': display_name, 'result_type': result_type}
                for field_id, display_name, result_type in self.path
            ],
        }


_INPUT_LABELS = {
    'left': '左侧', 'right': '右侧', 'value': '值', 'minimum': '最小值',
    'maximum': '最大值', 'digits': '小数位数', 'text': '文本',
    'separator': '分隔符', 'scale_x': '横向比例', 'scale_y': '纵向比例',
    'search': '查找内容', 'replacement': '替换为', 'start': '开始位置',
    'end': '结束位置', 'default': '默认值', 'condition': '条件',
    'when_true': '条件成立时', 'when_false': '条件不成立时', 'point': '坐标',
    'offset': '偏移量', 'rect': '区域', 'list': '列表', 'index': '序号',
    'other': '另一个值', 'map': '字典', 'key': '键', 'conflict': '冲突处理',
    'json': 'JSON 数据', 'path': '路径',
    'actual': '实际文本', 'expected': '目标文本', 'mode': '匹配方式',
    'timeout': '超时时间', 'interval': '检查间隔',
    'predicate': '保留条件', 'transform': '每项计算',
    'key_selector': '分组或排序依据', 'descending': '从大到小',
    'schema': '数据结构规则',
    'directory': '授权目录', 'relative_path': '相对位置',
    'pattern': '格式或正则', 'group': '分组序号', 'datetime': '日期与时间',
    'duration': '持续时间', 'later': '较晚时间', 'earlier': '较早时间',
    'date': '日期', 'days': '天数', 'time': '时间', 'amount': '数值',
    'tolerance': '容差',
}


EXPRESSION_NAMESPACES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ('文本', '组合、整理、查找和提取文字', ('字符串', '文字', '替换', '截取', '正则')),
    ('数值', '计算、取整、转换和限制数字', ('数字', '整数', '小数', '计算', '四舍五入')),
    ('类型', '在明确且安全的类型之间转换', ('转换', '解析', '转文本', '转整数', '转小数')),
    ('时间', '构造、解析、格式化和计算日期时间', ('日期', '时刻', '持续时间', '格式化', '时间差')),
    ('结果', '判断或处理可能没有结果的值', ('可选', '空', '无结果', '默认值', '有结果')),
    ('条件', '根据条件选择一个值', ('如果', '选择', '真假', '分支')),
    ('坐标', '偏移、缩放和读取区域位置', ('位置', '点', '区域', '中心', '缩放')),
    ('颜色', '比较两个颜色是否接近', ('像素', 'RGBA', '容差', '找色')),
    ('列表', '查询、修改、变换和统计有序数据', ('数组', '集合', '追加', '筛选', '排序')),
    ('字典', '按键查询、修改和整理键值数据', ('映射', '键值', '对象', '合并', '分组')),
    ('JSON', '解析和按路径读取或修改 JSON', ('接口数据', '路径', '解析', '结构', '对象')),
    ('文件', '从授权目录构造受约束文件引用', ('路径', '目录', '相对位置', '文件引用')),
)


_GROUP_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (('regex', 'extract', 'matches', 'path_exists', 'has_key', 'contains', 'find', 'get', 'first', 'last'), '查找与读取'),
    (('parse', 'to_int', 'to_float', 'to_text', 'format', 'from_milliseconds', 'from_seconds', 'from_minutes'), '转换与格式'),
    (('filter', 'map_values', 'group_by', 'sort_by', 'count_match', 'index_by'), '逐项整理'),
    (('append', 'prepend', 'insert', 'replace', 'remove', 'delete', 'clear', 'set', 'merge', 'concat'), '修改副本'),
    (('length', 'sum', 'average', 'min', 'max', 'difference', 'any', 'all', 'is_empty'), '判断与统计'),
    (('add', 'subtract', 'multiply', 'divide', 'modulo', 'round', 'clamp', 'scale', 'offset', 'center'), '计算与变换'),
)


def _operation_group(operation_id: str, category: str) -> str:
    action = operation_id.removeprefix('core.').removesuffix('.v1')
    for fragments, label in _GROUP_RULES:
        if any(
            action == fragment
            or action.startswith(f'{fragment}_')
            or action.endswith(f'_{fragment}')
            or f'_{fragment}_' in action
            for fragment in fragments
        ):
            return label
    return {'结果': '空值处理', '条件': '条件选择', '文件': '引用构造'}.get(category, '常用操作')


def _operation_keywords(presentation: PureOperationPresentationV6) -> tuple[str, ...]:
    namespace = next((item for item in EXPRESSION_NAMESPACES if item[0] == presentation.category), None)
    category_words = namespace[2] if namespace else ()
    action_words = tuple(
        word for word in presentation.description.replace('；', '，').replace('、', '，').split('，')
        if word
    )
    return tuple(dict.fromkeys((presentation.display_name, *category_words, *action_words)))


def _incompatible_reason(result_type_hints: tuple[str, ...]) -> str:
    if result_type_hints:
        return '这个操作的结果类型不能填入当前字段'
    return '当前字段或当前作用域没有可用的输入类型'


def _p(operation_id: str, display_name: str, category: str, description: str) -> PureOperationPresentationV6:
    short_name = display_name
    if category == '文本':
        short_name = short_name.replace('文本', '')
    elif category == '列表':
        short_name = short_name.replace('列表项', '').replace('列表', '')
    elif category == '字典':
        short_name = short_name.replace('字典项', '').replace('字典', '')
    elif category == '坐标':
        short_name = short_name.replace('坐标', '')
    elif category == 'JSON':
        short_name = short_name.replace('JSON ', '').replace('JSON', '')
    short_name = short_name.replace(' ', '')
    input_labels = {
        name: _INPUT_LABELS.get(name, name)
        for name in OPERATION_INPUT_NAMES.get(operation_id, ())
    }
    if operation_id == 'core.color_matches.v1':
        input_labels.update({'actual': '实际颜色', 'expected': '目标颜色'})
    return PureOperationPresentationV6(
        operation_id=operation_id,
        display_name=display_name,
        category=category,
        description=description,
        syntax_name=f'{category}.{short_name}',
        input_labels=input_labels,
    )


_PRESENTATIONS = (
    _p('core.number_add.v1', '相加', '数值', '把两个数相加'),
    _p('core.number_subtract.v1', '相减', '数值', '用左侧数减去右侧数'),
    _p('core.number_multiply.v1', '相乘', '数值', '把两个数相乘'),
    _p('core.number_divide.v1', '相除', '数值', '用左侧数除以右侧数'),
    _p('core.number_modulo.v1', '取余数', '数值', '取得整数或小数相除后的余数'),
    _p('core.number_min.v1', '取较小值', '数值', '返回两个数中较小的一个'),
    _p('core.number_max.v1', '取较大值', '数值', '返回两个数中较大的一个'),
    _p('core.number_clamp.v1', '限制范围', '数值', '把数值限制在最小值和最大值之间'),
    _p('core.number_round.v1', '四舍五入', '数值', '按指定小数位数四舍五入'),
    _p('core.number_to_int.v1', '转为整数', '数值', '把数值转换成整数'),
    _p('core.number_to_float.v1', '转为小数', '数值', '把数值转换成小数'),
    _p('core.value_to_text.v1', '转为文本', '类型', '把基础值转换成稳定、跨平台一致的文本'),
    _p('core.text_to_int.v1', '文本转整数', '类型', '严格解析整数；无法解析时返回无结果'),
    _p('core.text_to_float.v1', '文本转小数', '类型', '严格解析有限小数；无法解析时返回无结果'),
    _p('core.text_concat.v1', '拼接文本', '文本', '把两段文本连接起来'),
    _p('core.text_replace.v1', '替换文本', '文本', '替换文本中的指定内容'),
    _p('core.text_slice.v1', '截取文本', '文本', '按开始和结束位置截取文本'),
    _p('core.text_lower.v1', '转为小写', '文本', '把文本中的字母转为小写'),
    _p('core.text_upper.v1', '转为大写', '文本', '把文本中的字母转为大写'),
    _p('core.text_trim.v1', '去除首尾空白', '文本', '去除文本首尾的空白字符'),
    _p('core.text_length.v1', '文本长度', '文本', '取得文本包含的字符数量'),
    _p('core.text_matches.v1', '文本匹配', '文本', '按精确、包含或正则方式匹配两段文本'),
    _p('core.text_split.v1', '拆分文本', '文本', '按非空分隔符拆分为文本列表'),
    _p('core.text_join.v1', '连接文本列表', '文本', '用分隔符连接文本列表'),
    _p('core.text_regex_extract.v1', '按正则提取', '文本', '取得首次匹配的指定分组；未匹配返回无结果'),
    _p('core.text_regex_groups.v1', '取得正则分组', '文本', '取得首次匹配中的全部捕获分组'),
    _p('core.text_extract_first_int.v1', '提取第一个整数', '文本', '从混合文本中取得首个整数；没有或超出范围时返回无结果'),
    _p('core.text_parse_datetime.v1', '解析日期与时间', '时间', '按跨平台格式解析文本；失败返回无结果'),
    _p('core.datetime_add_duration.v1', '增加持续时间', '时间', '在日期与时间上增加持续时间'),
    _p('core.datetime_subtract_duration.v1', '减少持续时间', '时间', '从日期与时间中减去持续时间'),
    _p('core.datetime_difference.v1', '计算时间差', '时间', '计算较晚时间减较早时间的毫秒数'),
    _p('core.datetime_format.v1', '格式化日期与时间', '时间', '按跨平台格式输出文本'),
    _p('core.date_add_days.v1', '增加天数', '时间', '在日期上增加或减少天数'),
    _p('core.date_difference.v1', '计算相差天数', '时间', '计算较晚日期减较早日期的天数'),
    _p('core.time_add_duration.v1', '时间增加时长', '时间', '在一天内循环增加或减少持续时间'),
    _p('core.duration_from_milliseconds.v1', '毫秒数转持续时间', '时间', '把数值解释为毫秒'),
    _p('core.duration_from_seconds.v1', '秒数转持续时间', '时间', '把数值解释为秒'),
    _p('core.duration_from_minutes.v1', '分钟数转持续时间', '时间', '把数值解释为分钟'),
    _p('core.duration_poll_count.v1', '计算检查次数', '时间', '根据超时时间与检查间隔计算标准函数的有限检查次数'),
    _p('core.optional_has_value.v1', '有结果', '结果', '判断可选值是否包含结果'),
    _p('core.optional_default.v1', '无结果时使用默认值', '结果', '有结果时使用原值，否则使用默认值'),
    _p('core.select.v1', '按条件选择', '条件', '只计算并返回条件对应的一个值'),
    _p('core.point_offset.v1', '偏移坐标', '坐标', '在原坐标基础上增加偏移量'),
    _p('core.point_scale.v1', '缩放坐标', '坐标', '分别按横向和纵向比例缩放坐标'),
    _p('core.rect_center.v1', '区域中心', '坐标', '取得区域的中心坐标'),
    _p('core.rect_scale.v1', '缩放区域', '坐标', '分别按横向和纵向比例缩放区域及其位置'),
    _p('core.rect_from_center.v1', '按中心生成区域', '坐标', '以一个坐标为中心生成指定宽高的区域'),
    _p('core.color_matches.v1', '颜色接近', '颜色', '判断两个颜色的各通道差值是否都在容差内'),
    _p('core.list_is_empty.v1', '列表是否为空', '列表', '判断列表是否没有任何项'),
    _p('core.list_length.v1', '列表数量', '列表', '取得列表项数量'),
    _p('core.list_contains.v1', '列表包含', '列表', '判断列表是否包含指定值'),
    _p('core.list_first.v1', '列表第一项', '列表', '取得第一项；空列表返回无结果'),
    _p('core.list_last.v1', '列表最后一项', '列表', '取得最后一项；空列表返回无结果'),
    _p('core.list_get.v1', '按序号取列表项', '列表', '取得指定序号的项；越界返回无结果'),
    _p('core.list_append.v1', '追加列表项', '列表', '返回在末尾加入新项后的列表'),
    _p('core.list_prepend.v1', '前置列表项', '列表', '返回在开头加入新项后的列表'),
    _p('core.list_insert.v1', '插入列表项', '列表', '返回在指定序号插入新项后的列表'),
    _p('core.list_replace.v1', '替换列表项', '列表', '返回替换指定序号项后的列表'),
    _p('core.list_remove_at.v1', '删除列表项', '列表', '返回删除指定序号项后的列表'),
    _p('core.list_clear.v1', '清空列表', '列表', '返回同类型的空列表'),
    _p('core.list_reverse.v1', '反转列表', '列表', '返回顺序反转后的列表'),
    _p('core.list_slice.v1', '截取列表', '列表', '返回指定序号范围内的列表'),
    _p('core.list_concat.v1', '合并列表', '列表', '按顺序合并两个同类型列表'),
    _p('core.list_distinct.v1', '列表去重', '列表', '返回保留首次出现项的去重列表'),
    _p('core.list_sum.v1', '列表求和', '列表', '计算数值列表的总和'),
    _p('core.list_average.v1', '列表平均值', '列表', '计算数值列表平均值；空列表返回无结果'),
    _p('core.list_min.v1', '列表最小值', '列表', '取得最小项；空列表返回无结果'),
    _p('core.list_max.v1', '列表最大值', '列表', '取得最大项；空列表返回无结果'),
    _p('core.list_filter.v1', '筛选列表', '列表', '逐项判断，只保留满足条件的项'),
    _p('core.list_map.v1', '转换列表项', '列表', '用纯值计算把每一项转换为新值'),
    _p('core.list_sort_by.v1', '按依据排序', '列表', '按每项计算出的依据稳定排序'),
    _p('core.list_group_by.v1', '按依据分组', '列表', '把依据相同的项归入同一组'),
    _p('core.list_flatten.v1', '展平一层列表', '列表', '把列表中的子列表按顺序合并'),
    _p('core.list_zip.v1', '按位置组合列表', '列表', '把两个列表相同位置的项组合；以较短列表为准'),
    _p('core.list_find_first.v1', '查找首个满足项', '列表', '按顺序返回首个满足条件的项'),
    _p('core.list_any.v1', '任意一项满足', '列表', '遇到第一项满足条件时立即返回'),
    _p('core.list_all.v1', '全部项满足', '列表', '遇到第一项不满足条件时立即返回'),
    _p('core.list_count_match.v1', '统计满足项', '列表', '统计满足条件的列表项数量'),
    _p('core.list_index_by.v1', '按依据建立字典', '列表', '用每项的唯一依据建立字典；重复键会明确报错'),
    _p('core.map_has_key.v1', '字典包含键', '字典', '判断字典中是否存在指定键'),
    _p('core.map_get.v1', '读取字典值', '字典', '按键读取值；键不存在时返回无结果'),
    _p('core.map_set.v1', '设置字典值', '字典', '返回设置指定键值后的字典'),
    _p('core.map_delete.v1', '删除字典项', '字典', '返回删除指定键后的字典'),
    _p('core.map_clear.v1', '清空字典', '字典', '返回同类型的空字典'),
    _p('core.map_keys.v1', '字典所有键', '字典', '取得字典中所有键的列表'),
    _p('core.map_values.v1', '字典所有值', '字典', '取得字典中所有值的列表'),
    _p('core.map_entries.v1', '字典所有项', '字典', '取得字典键值项的列表'),
    _p('core.map_merge.v1', '合并字典', '字典', '按冲突策略合并两个同类型字典'),
    _p('core.map_filter.v1', '筛选字典项', '字典', '逐项判断，只保留满足条件的键值项'),
    _p('core.map_map_values.v1', '转换字典值', '字典', '保留键，并用纯值计算转换每个值'),
    _p('core.map_group_by.v1', '按依据分组字典项', '字典', '把键值项按计算依据分组'),
    _p('core.json_parse_text.v1', '解析 JSON 文本', 'JSON', '把文本解析为 JSON；格式无效时返回无结果'),
    _p('core.json_path_exists.v1', 'JSON 路径存在', 'JSON', '判断 JSON 中是否存在指定路径'),
    _p('core.json_path_get.v1', '读取 JSON 路径', 'JSON', '读取指定路径；不存在时返回无结果'),
    _p('core.json_path_set.v1', '设置 JSON 路径', 'JSON', '返回设置指定路径后的 JSON'),
    _p('core.json_path_delete.v1', '删除 JSON 路径', 'JSON', '返回删除指定路径后的 JSON'),
    _p('core.json_validate_schema.v1', '按结构规则验证 JSON', 'JSON', '验证 JSON 并转换为目标强类型值；失败会指出具体位置'),
    _p('core.file_ref_child.v1', '目录中的文件', '文件', '在已授权目录内生成能力不扩大的文件引用'),
)

PURE_OPERATION_PRESENTATIONS: dict[str, PureOperationPresentationV6] = {
    item.operation_id: item for item in _PRESENTATIONS
}

if set(PURE_OPERATION_PRESENTATIONS) != set(EXECUTABLE_PURE_OPERATIONS):
    missing = sorted(set(EXECUTABLE_PURE_OPERATIONS) - set(PURE_OPERATION_PRESENTATIONS))
    extra = sorted(set(PURE_OPERATION_PRESENTATIONS) - set(EXECUTABLE_PURE_OPERATIONS))
    raise RuntimeError(f'pure operation presentation drift; missing={missing}, extra={extra}')


def _generic_parts(type_id: str, prefix: str) -> tuple[str, ...] | None:
    marker = f'{prefix}<'
    if not type_id.startswith(marker) or not type_id.endswith('>'):
        return None
    inner = type_id[len(marker):-1]
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(inner):
        if char == '<':
            depth += 1
        elif char == '>':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(inner[start:index].strip())
            start = index + 1
    result.append(inner[start:].strip())
    return tuple(result) if result and all(result) else None


def _signature(operation_id: str, result_type: str, **inputs: str) -> tuple[str, dict[str, str]]:
    return result_type, {
        f'{operation_id}.input.{name}': value_type for name, value_type in inputs.items()
    }


def _resolved_signatures(
    operation_id: str,
    expected_type: str,
    available_types: tuple[str, ...],
) -> Iterable[tuple[str, dict[str, str]]]:
    numeric = 'float64' if expected_type in {'float64', 'percentage'} else 'int64'
    same_numeric = {
        'core.number_add.v1', 'core.number_subtract.v1', 'core.number_multiply.v1',
        'core.number_modulo.v1', 'core.number_min.v1', 'core.number_max.v1',
    }
    if operation_id in same_numeric and expected_type in {'int64', 'float64', 'percentage'}:
        yield _signature(operation_id, numeric, left=numeric, right=numeric)
    elif operation_id == 'core.number_divide.v1' and expected_type in {'float64', 'percentage'}:
        yield _signature(operation_id, 'float64', left='float64', right='float64')
    elif operation_id == 'core.number_clamp.v1' and expected_type in {'int64', 'float64', 'percentage'}:
        yield _signature(operation_id, numeric, value=numeric, minimum=numeric, maximum=numeric)
    elif operation_id == 'core.number_round.v1' and expected_type in {'int64', 'float64', 'percentage'}:
        yield _signature(operation_id, numeric, value=numeric, digits='int64')
    elif operation_id == 'core.number_to_int.v1' and expected_type == 'int64':
        yield _signature(operation_id, 'int64', value='float64')
    elif operation_id == 'core.number_to_float.v1' and expected_type in {'float64', 'percentage'}:
        yield _signature(operation_id, 'float64', value='int64')

    if operation_id == 'core.value_to_text.v1' and expected_type == 'string':
        scalar_types = {
            item for item in available_types
            if item in {'string', 'int64', 'float64', 'percentage', 'bool', 'date', 'datetime', 'time', 'time_of_day', 'duration'}
            or item.startswith('enum<')
        }
        for source_type in sorted(scalar_types):
            yield _signature(operation_id, 'string', value=source_type)
    elif operation_id == 'core.text_to_int.v1' and expected_type == 'optional<int64>':
        yield _signature(operation_id, expected_type, text='string')
    elif operation_id == 'core.text_to_float.v1' and expected_type == 'optional<float64>':
        yield _signature(operation_id, expected_type, text='string')
    elif operation_id == 'core.text_regex_extract.v1' and expected_type == 'optional<string>':
        yield _signature(operation_id, expected_type, text='string', pattern='string', group='int64')
    elif operation_id == 'core.text_regex_groups.v1' and expected_type == 'list<string>':
        yield _signature(operation_id, expected_type, text='string', pattern='string')
    elif operation_id == 'core.text_extract_first_int.v1' and expected_type == 'optional<int64>':
        yield _signature(operation_id, expected_type, text='string')
    elif operation_id == 'core.text_parse_datetime.v1' and expected_type == 'optional<datetime>':
        yield _signature(operation_id, expected_type, text='string', pattern='string')
    elif operation_id == 'core.text_matches.v1' and expected_type == 'bool':
        yield _signature(
            operation_id,
            'bool',
            actual='string',
            expected='string',
            mode='enum<text_match_mode>',
        )

    temporal_results = {
        'core.datetime_add_duration.v1': ('datetime', {'datetime': 'datetime', 'duration': 'duration'}),
        'core.datetime_subtract_duration.v1': ('datetime', {'datetime': 'datetime', 'duration': 'duration'}),
        'core.datetime_difference.v1': ('duration', {'later': 'datetime', 'earlier': 'datetime'}),
        'core.datetime_format.v1': ('string', {'datetime': 'datetime', 'pattern': 'string'}),
        'core.date_add_days.v1': ('date', {'date': 'date', 'days': 'int64'}),
        'core.date_difference.v1': ('int64', {'later': 'date', 'earlier': 'date'}),
        'core.time_add_duration.v1': ('time', {'time': 'time', 'duration': 'duration'}),
    }
    if operation_id in temporal_results:
        result, inputs = temporal_results[operation_id]
        if types_compatible(result, expected_type):
            yield _signature(operation_id, result, **inputs)
    if operation_id in {
        'core.duration_from_milliseconds.v1', 'core.duration_from_seconds.v1',
        'core.duration_from_minutes.v1',
    } and expected_type == 'duration':
        for amount_type in ('int64', 'float64'):
            yield _signature(operation_id, 'duration', amount=amount_type)
    elif operation_id == 'core.duration_poll_count.v1' and expected_type == 'int64':
        yield _signature(operation_id, 'int64', timeout='duration', interval='duration')

    text_results = {
        'core.text_concat.v1': ('string', {'left': 'string', 'right': 'string'}),
        'core.text_replace.v1': ('string', {'text': 'string', 'search': 'string', 'replacement': 'string'}),
        'core.text_slice.v1': ('string', {'text': 'string', 'start': 'int64', 'end': 'int64'}),
        'core.text_lower.v1': ('string', {'text': 'string'}),
        'core.text_upper.v1': ('string', {'text': 'string'}),
        'core.text_trim.v1': ('string', {'text': 'string'}),
        'core.text_length.v1': ('int64', {'text': 'string'}),
    }
    if operation_id in text_results:
        result, inputs = text_results[operation_id]
        if types_compatible(result, expected_type):
            yield _signature(operation_id, result, **inputs)
    if operation_id == 'core.text_split.v1' and expected_type == 'list<string>':
        yield _signature(operation_id, expected_type, text='string', separator='string')
    elif operation_id == 'core.text_join.v1' and expected_type == 'string':
        yield _signature(operation_id, expected_type, list='list<string>', separator='string')

    if operation_id == 'core.optional_has_value.v1' and expected_type == 'bool':
        for value_type in available_types:
            if _generic_parts(value_type, 'optional'):
                yield _signature(operation_id, 'bool', value=value_type)
    elif operation_id == 'core.optional_default.v1' and expected_type not in {'any', 'unit', 'unset'}:
        yield _signature(operation_id, expected_type, value=f'optional<{expected_type}>', default=expected_type)
    elif operation_id == 'core.select.v1' and expected_type not in {'any', 'unit', 'unset'}:
        yield _signature(operation_id, expected_type, condition='bool', when_true=expected_type, when_false=expected_type)
    elif operation_id == 'core.point_offset.v1' and expected_type == 'point':
        yield _signature(operation_id, 'point', point='point', offset='point')
    elif operation_id == 'core.point_scale.v1' and expected_type == 'point':
        yield _signature(operation_id, 'point', point='point', scale_x='float64', scale_y='float64')
    elif operation_id == 'core.rect_center.v1' and expected_type == 'point':
        yield _signature(operation_id, 'point', rect='rect')
    elif operation_id == 'core.rect_scale.v1' and expected_type == 'rect':
        yield _signature(operation_id, 'rect', rect='rect', scale_x='float64', scale_y='float64')
    elif operation_id == 'core.rect_from_center.v1' and expected_type == 'rect':
        yield _signature(operation_id, 'rect', center='point', width='float64', height='float64')
    elif operation_id == 'core.color_matches.v1' and expected_type == 'bool':
        yield _signature(operation_id, 'bool', actual='color', expected='color', tolerance='int64')

    available_lists = sorted({item for item in available_types if _generic_parts(item, 'list')})
    inferred_list = _generic_parts(expected_type, 'list')
    inferred_optional = _generic_parts(expected_type, 'optional')
    expected_map_parts = _generic_parts(expected_type, 'map')
    list_type = f'list<{inferred_list[0]}>' if inferred_list and len(inferred_list) == 1 else ''
    optional_item = inferred_optional[0] if inferred_optional and len(inferred_optional) == 1 else ''
    selector_keys = (
        'string', 'int64', 'float64', 'duration', 'date', 'datetime', 'time',
    )
    if operation_id == 'core.list_filter.v1' and list_type:
        yield _signature(
            operation_id, list_type, list=list_type,
            predicate=f'list_selector<{inferred_list[0]},bool>',
        )
    elif operation_id == 'core.list_map.v1' and list_type:
        for source_type in available_lists:
            source_item = _generic_parts(source_type, 'list')[0]
            yield _signature(
                operation_id, list_type, list=source_type,
                transform=f'list_selector<{source_item},{inferred_list[0]}>',
            )
    elif operation_id == 'core.list_sort_by.v1' and list_type:
        for key_type in selector_keys:
            yield _signature(
                operation_id, list_type, list=list_type,
                key_selector=f'list_selector<{inferred_list[0]},{key_type}>',
                descending='bool',
            )
    elif operation_id == 'core.list_group_by.v1' and expected_map_parts and len(expected_map_parts) == 2:
        group_type, grouped_type = expected_map_parts
        grouped_list = _generic_parts(grouped_type, 'list')
        if grouped_list and len(grouped_list) == 1:
            source_item = grouped_list[0]
            yield _signature(
                operation_id, expected_type, list=f'list<{source_item}>',
                key_selector=f'list_selector<{source_item},{group_type}>',
            )
    elif operation_id == 'core.list_flatten.v1' and list_type:
        yield _signature(operation_id, list_type, list=f'list<{list_type}>')
    elif operation_id == 'core.list_zip.v1' and inferred_list:
        record_parts = _generic_parts(inferred_list[0], 'record')
        pair_parts = _generic_parts(record_parts[0], 'zip_pair') if record_parts else None
        if pair_parts and len(pair_parts) == 2:
            yield _signature(
                operation_id, expected_type,
                list=f'list<{pair_parts[0]}>', other=f'list<{pair_parts[1]}>',
            )
    elif operation_id == 'core.list_find_first.v1' and optional_item:
        yield _signature(
            operation_id, expected_type, list=f'list<{optional_item}>',
            predicate=f'list_selector<{optional_item},bool>',
        )
    elif operation_id in {'core.list_any.v1', 'core.list_all.v1'} and expected_type == 'bool':
        for source_type in available_lists:
            item_type = _generic_parts(source_type, 'list')[0]
            yield _signature(
                operation_id, 'bool', list=source_type,
                predicate=f'list_selector<{item_type},bool>',
            )
    elif operation_id == 'core.list_count_match.v1' and expected_type == 'int64':
        for source_type in available_lists:
            item_type = _generic_parts(source_type, 'list')[0]
            yield _signature(
                operation_id, 'int64', list=source_type,
                predicate=f'list_selector<{item_type},bool>',
            )
    elif operation_id == 'core.list_index_by.v1' and expected_map_parts and len(expected_map_parts) == 2:
        key_type, item_type = expected_map_parts
        yield _signature(
            operation_id, expected_type, list=f'list<{item_type}>',
            key_selector=f'list_selector<{item_type},{key_type}>',
        )
    if operation_id in {'core.list_is_empty.v1', 'core.list_length.v1', 'core.list_contains.v1'}:
        result = 'int64' if operation_id == 'core.list_length.v1' else 'bool'
        if types_compatible(result, expected_type):
            for source_type in available_lists:
                item_type = _generic_parts(source_type, 'list')[0]
                inputs = {'list': source_type}
                if operation_id == 'core.list_contains.v1':
                    inputs['value'] = item_type
                yield _signature(operation_id, result, **inputs)
    elif operation_id in {'core.list_first.v1', 'core.list_last.v1', 'core.list_get.v1', 'core.list_min.v1', 'core.list_max.v1'} and optional_item:
        inputs = {'list': f'list<{optional_item}>'}
        if operation_id == 'core.list_get.v1':
            inputs['index'] = 'int64'
        yield _signature(operation_id, expected_type, **inputs)
    elif operation_id == 'core.list_sum.v1' and expected_type in {'int64', 'float64'}:
        yield _signature(operation_id, expected_type, list=f'list<{expected_type}>')
    elif operation_id == 'core.list_average.v1' and expected_type == 'optional<float64>':
        for source_type in available_lists:
            if source_type in {'list<int64>', 'list<float64>'}:
                yield _signature(operation_id, expected_type, list=source_type)
    elif list_type:
        item_type = inferred_list[0]
        if operation_id in {'core.list_append.v1', 'core.list_prepend.v1'}:
            yield _signature(operation_id, list_type, list=list_type, value=item_type)
        elif operation_id in {'core.list_insert.v1', 'core.list_replace.v1'}:
            yield _signature(operation_id, list_type, list=list_type, index='int64', value=item_type)
        elif operation_id == 'core.list_remove_at.v1':
            yield _signature(operation_id, list_type, list=list_type, index='int64')
        elif operation_id in {'core.list_clear.v1', 'core.list_reverse.v1', 'core.list_distinct.v1'}:
            yield _signature(operation_id, list_type, list=list_type)
        elif operation_id == 'core.list_slice.v1':
            yield _signature(operation_id, list_type, list=list_type, start='int64', end='int64')
        elif operation_id == 'core.list_concat.v1':
            yield _signature(operation_id, list_type, list=list_type, other=list_type)

    available_maps = sorted({item for item in available_types if _generic_parts(item, 'map')})
    inferred_map = _generic_parts(expected_type, 'map')
    map_type = expected_type if inferred_map and len(inferred_map) == 2 else ''
    if operation_id == 'core.map_filter.v1' and map_type:
        key_type, item_type = inferred_map
        yield _signature(
            operation_id, map_type, map=map_type,
            predicate=f'map_selector<{key_type},{item_type},bool>',
        )
    elif operation_id == 'core.map_map_values.v1' and map_type:
        output_key, output_value = inferred_map
        for source_type in available_maps:
            source_key, source_value = _generic_parts(source_type, 'map')
            if source_key == output_key:
                yield _signature(
                    operation_id, map_type, map=source_type,
                    transform=f'map_selector<{source_key},{source_value},{output_value}>',
                )
    elif operation_id == 'core.map_group_by.v1' and inferred_map and len(inferred_map) == 2:
        group_type, grouped_type = inferred_map
        grouped_list = _generic_parts(grouped_type, 'list')
        record_parts = _generic_parts(grouped_list[0], 'record') if grouped_list else None
        entry_parts = _generic_parts(record_parts[0], 'map_entry') if record_parts else None
        if entry_parts and len(entry_parts) == 2:
            source_key, source_value = entry_parts
            yield _signature(
                operation_id, expected_type, map=f'map<{source_key},{source_value}>',
                key_selector=f'map_selector<{source_key},{source_value},{group_type}>',
            )
    if operation_id == 'core.map_has_key.v1' and expected_type == 'bool':
        for source_type in available_maps:
            key_type, _ = _generic_parts(source_type, 'map')
            yield _signature(operation_id, 'bool', map=source_type, key=key_type)
    elif operation_id == 'core.map_get.v1' and optional_item:
        for source_type in available_maps:
            key_type, item_type = _generic_parts(source_type, 'map')
            if item_type == optional_item:
                yield _signature(operation_id, expected_type, map=source_type, key=key_type)
    elif operation_id in {'core.map_keys.v1', 'core.map_values.v1'} and inferred_list:
        expected_item = inferred_list[0]
        for source_type in available_maps:
            key_type, item_type = _generic_parts(source_type, 'map')
            if (operation_id == 'core.map_keys.v1' and key_type == expected_item) or (operation_id == 'core.map_values.v1' and item_type == expected_item):
                yield _signature(operation_id, expected_type, map=source_type)
    elif operation_id == 'core.map_entries.v1' and inferred_list:
        record_parts = _generic_parts(inferred_list[0], 'record')
        entry_parts = _generic_parts(record_parts[0], 'map_entry') if record_parts else None
        if entry_parts and len(entry_parts) == 2:
            yield _signature(
                operation_id,
                expected_type,
                map=f'map<{entry_parts[0]},{entry_parts[1]}>',
            )
    elif map_type:
        key_type, item_type = inferred_map
        if operation_id == 'core.map_set.v1':
            yield _signature(operation_id, map_type, map=map_type, key=key_type, value=item_type)
        elif operation_id == 'core.map_delete.v1':
            yield _signature(operation_id, map_type, map=map_type, key=key_type)
        elif operation_id == 'core.map_clear.v1':
            yield _signature(operation_id, map_type, map=map_type)
        elif operation_id == 'core.map_merge.v1':
            yield _signature(operation_id, map_type, map=map_type, other=map_type, conflict='enum<map_conflict>')

    json_signatures = {
        'core.json_parse_text.v1': ('optional<json_value>', {'text': 'string'}),
        'core.json_path_exists.v1': ('bool', {'json': 'json_value', 'path': 'list<string>'}),
        'core.json_path_get.v1': ('optional<json_value>', {'json': 'json_value', 'path': 'list<string>'}),
        'core.json_path_set.v1': ('optional<json_value>', {'json': 'json_value', 'path': 'list<string>', 'value': 'json_value'}),
        'core.json_path_delete.v1': ('optional<json_value>', {'json': 'json_value', 'path': 'list<string>'}),
    }
    if operation_id in json_signatures:
        result, inputs = json_signatures[operation_id]
        if types_compatible(result, expected_type):
            yield _signature(operation_id, result, **inputs)
    elif operation_id == 'core.json_validate_schema.v1' and expected_type not in {
        'any', 'unit', 'unset', 'null',
    } and not expected_type.startswith(('list_selector<', 'map_selector<')):
        yield _signature(
            operation_id, expected_type, json='json_value', schema='json_value',
        )
    elif operation_id == 'core.file_ref_child.v1':
        directory_types = {
            'file_ref<read>': ('directory_ref<read>', 'directory_ref<read_write>'),
            'file_ref<write>': ('directory_ref<create>', 'directory_ref<read_write>'),
        }.get(expected_type, ())
        for directory_type in directory_types:
            if directory_type in available_types:
                yield _signature(
                    operation_id,
                    expected_type,
                    directory=directory_type,
                    relative_path='relative_path',
                )


def resolve_operation_candidates(
    expected_type: str,
    available_types: Iterable[str] = (),
) -> tuple[PureOperationCandidateV6, ...]:
    available = tuple(sorted({str(item) for item in available_types if str(item)}))
    result: list[PureOperationCandidateV6] = []
    seen: set[str] = set()
    for operation_id in sorted(EXECUTABLE_PURE_OPERATIONS):
        presentation = PURE_OPERATION_PRESENTATIONS[operation_id]
        for result_type, inputs in _resolved_signatures(operation_id, expected_type, available):
            if pure_operation_type_issues(operation_id, result_type, inputs):
                continue
            if not types_compatible(result_type, expected_type):
                continue
            canonical = json.dumps(
                [operation_id, result_type, sorted(inputs.items())],
                ensure_ascii=False,
                separators=(',', ':'),
            )
            candidate_id = 'operation_candidate.' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            ordered_inputs = tuple(
                (
                    f'{operation_id}.input.{name}',
                    presentation.input_labels.get(name, name),
                    inputs[f'{operation_id}.input.{name}'],
                    tuple(dict(item) for item in enum_choices(inputs[f'{operation_id}.input.{name}'])),
                )
                for name in OPERATION_INPUT_NAMES[operation_id]
            )
            result.append(PureOperationCandidateV6(
                candidate_id=candidate_id,
                operation_id=operation_id,
                display_name=presentation.display_name,
                category=presentation.category,
                description=presentation.description,
                result_type=result_type,
                inputs=ordered_inputs,
                syntax_name=presentation.syntax_name,
            ))
    return tuple(result)


def operation_candidate(
    candidate_id: str,
    expected_type: str,
    available_types: Iterable[str] = (),
) -> PureOperationCandidateV6 | None:
    return next(
        (item for item in resolve_operation_candidates(expected_type, available_types) if item.candidate_id == candidate_id),
        None,
    )


def _record_type_id(value_type: str) -> str:
    normalized = str(value_type or '').strip()
    while normalized.startswith('optional<') and normalized.endswith('>'):
        normalized = normalized[len('optional<'):-1].strip()
    if normalized.startswith('list<') and normalized.endswith('>'):
        normalized = normalized[len('list<'):-1].strip()
    if normalized.startswith('record<') and normalized.endswith('>'):
        return normalized[7:-1]
    if normalized.startswith('record.'):
        return normalized[7:]
    return normalized


def resolve_member_candidates(
    expected_type: str,
    sources: Iterable[object],
    *,
    max_depth: int = 4,
) -> tuple[RecordMemberCandidateV6, ...]:
    result: list[RecordMemberCandidateV6] = []
    text_convertible_types = {
        'string', 'int64', 'float64', 'percentage', 'bool',
        'date', 'datetime', 'time', 'time_of_day', 'duration',
    }

    def field_matches(value_type: str) -> bool:
        if types_compatible(value_type, expected_type):
            return True
        # A text slot accepts scalar record fields because the frontend lowers
        # them to the same versioned value-to-text operation used for scalar
        # variables.  Structured members remain excluded.
        return expected_type == 'string' and (
            value_type in text_convertible_types or value_type.startswith('enum<')
        )

    for source in sources:
        source_kind = str(getattr(source, 'source', ''))
        source_id = str(getattr(source, 'source_id', ''))
        display_name = str(getattr(source, 'display_name', source_id))
        source_value_type = str(getattr(source, 'value_type', ''))
        narrowed_type = str(getattr(source, 'narrowed_type', ''))
        effective_type = narrowed_type or source_value_type

        def visit(
            record_type: str,
            path: tuple[tuple[str, str, str], ...],
            seen: frozenset[str],
            *,
            source_kind: str = source_kind,
            source_id: str = source_id,
            display_name: str = display_name,
            source_value_type: str = source_value_type,
        ) -> None:
            contract = record_type_contract(_record_type_id(record_type))
            if contract is None or len(path) >= max_depth:
                return
            for field in contract.fields:
                next_path = (*path, (field.field_id, field.display_name, field.value_type))
                if field_matches(field.value_type):
                    canonical = json.dumps(
                        [source_kind, source_id, [item[0] for item in next_path], expected_type],
                        ensure_ascii=False,
                        separators=(',', ':'),
                    )
                    result.append(RecordMemberCandidateV6(
                        candidate_id='member_candidate.' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24],
                        source=source_kind,
                        source_id=source_id,
                        source_display_name=display_name,
                        source_value_type=source_value_type,
                        result_type=field.value_type,
                        path=next_path,
                    ))
                nested = _record_type_id(field.value_type)
                if nested not in seen and record_type_contract(nested) is not None:
                    visit(nested, next_path, seen | {nested})

        root_type = _record_type_id(effective_type)
        if record_type_contract(root_type) is not None:
            visit(root_type, (), frozenset({root_type}))
    return tuple(sorted(result, key=lambda item: (item.source_display_name.casefold(), tuple(part[1] for part in item.path))))


_DISCOVERY_EXPECTED_TYPES = (
    'string', 'int64', 'float64', 'percentage', 'bool', 'date', 'datetime', 'time',
    'duration', 'point', 'rect', 'color', 'json_value', 'optional<string>',
    'optional<int64>', 'optional<float64>', 'optional<datetime>', 'optional<json_value>',
    'list<string>', 'list<int64>', 'list<float64>',
    'list<record<zip_pair<string,int64>>>',
    'list<record<map_entry<string,string>>>',
    'map<string,string>', 'map<string,list<string>>',
    'map<string,list<record<map_entry<string,string>>>>',
    'file_ref<read>', 'file_ref<write>',
)
_DISCOVERY_AVAILABLE_TYPES = (
    *_DISCOVERY_EXPECTED_TYPES,
    'directory_ref<read>', 'directory_ref<create>', 'directory_ref<read_write>',
    'list<list<string>>', 'list<map_entry<string,string>>',
)


@lru_cache(maxsize=None)
def _operation_result_type_hints(operation_id: str) -> tuple[str, ...]:
    result: list[str] = []
    for expected_type in _DISCOVERY_EXPECTED_TYPES:
        for result_type, inputs in _resolved_signatures(
            operation_id,
            expected_type,
            _DISCOVERY_AVAILABLE_TYPES,
        ):
            if pure_operation_type_issues(operation_id, result_type, inputs):
                continue
            if result_type not in result:
                result.append(result_type)
    return tuple(result[:8])


def _sample_input(value_type: str, label: str, choices: tuple[dict[str, object], ...] = ()) -> str:
    if choices:
        return str(choices[0].get('label') or choices[0].get('value') or label)
    if value_type == 'string':
        return f'"{label}"'
    if value_type == 'int64':
        return '1'
    if value_type in {'float64', 'percentage'}:
        return '1.5'
    if value_type == 'bool':
        return '开启'
    if value_type == 'duration':
        return '1 秒'
    if value_type == 'date':
        return '2026-09-06'
    if value_type == 'datetime':
        return '2026-09-06 18:30:00'
    if value_type in {'time', 'time_of_day'}:
        return '18:30:00'
    if value_type == 'point':
        return '坐标(100, 200)'
    if value_type == 'rect':
        return '区域(0, 0, 640, 360)'
    if value_type == 'color':
        return '@颜色'
    if value_type in {'json', 'json_value'}:
        return '@JSON数据'
    if value_type.startswith('list_selector<'):
        return '每项 => 开启'
    if value_type.startswith('map_selector<'):
        return '每项 => 开启'
    if value_type.startswith('list<'):
        return '@列表'
    if value_type.startswith('map<'):
        return '@字典'
    if value_type.startswith('optional<'):
        return '无结果'
    return f'@{label}'


@lru_cache(maxsize=None)
def _operation_example(operation_id: str) -> str:
    presentation = PURE_OPERATION_PRESENTATIONS[operation_id]
    selected: tuple[str, dict[str, str]] | None = None
    for expected_type in _DISCOVERY_EXPECTED_TYPES:
        selected = next(iter(_resolved_signatures(
            operation_id,
            expected_type,
            _DISCOVERY_AVAILABLE_TYPES,
        )), None)
        if selected:
            break
    if not selected:
        labels = [
            presentation.input_labels.get(name, name)
            for name in OPERATION_INPUT_NAMES[operation_id]
        ]
        return f'{presentation.syntax_name}({", ".join(labels)})'
    _, inputs = selected
    values = []
    for name in OPERATION_INPUT_NAMES[operation_id]:
        input_id = f'{operation_id}.input.{name}'
        value_type = inputs[input_id]
        values.append(_sample_input(
            value_type,
            presentation.input_labels.get(name, name),
            tuple(dict(item) for item in enum_choices(value_type)),
        ))
    return f'{presentation.syntax_name}({", ".join(values)})'


def _literal_suggestions(expected_type: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []

    def add(label: str, insert_text: str, description: str) -> None:
        result.append({'label': label, 'insert_text': insert_text, 'description': description})

    inner = _generic_parts(expected_type, 'optional')
    if inner:
        add('无结果', '无结果', '明确表示当前没有结果')
        expected_type = inner[0]
    if expected_type == 'bool':
        add('开启', '开启', '布尔值：是')
        add('关闭', '关闭', '布尔值：否')
    elif expected_type == 'int64':
        add('整数', '0', '直接输入整数，例如 18 或 -3')
    elif expected_type in {'float64', 'percentage'}:
        add('小数', '0.5', '直接输入有限小数，例如 18.5')
    elif expected_type == 'string':
        add('普通文字', '', '直接输入文字；不需要引号')
        add('引号文字', '""', '操作参数内的文字使用成对引号')
    elif expected_type == 'duration':
        add('毫秒', '500 毫秒', '以毫秒表示持续时间')
        add('秒', '2 秒', '以秒表示持续时间')
        add('分钟', '1 分钟', '以分钟表示持续时间')
    elif expected_type == 'date':
        add('日期', '2026-09-06', '格式：YYYY-MM-DD')
    elif expected_type == 'datetime':
        add('日期与时间', '2026-09-06 18:30:00', '格式：YYYY-MM-DD HH:mm:ss')
    elif expected_type in {'time', 'time_of_day'}:
        add('时间', '18:30:00', '格式：HH:mm:ss')
    elif expected_type in {'point', 'coordinate'}:
        add('坐标', '坐标(100, 200)', '格式：坐标(X, Y)')
    elif expected_type in {'rect', 'region'}:
        add('区域', '区域(0, 0, 640, 360)', '格式：区域(X, Y, 宽, 高)')
    elif _generic_parts(expected_type, 'list'):
        add('空列表', '[]', '创建当前项类型的空列表')
    elif expected_type == 'timezone':
        add('东八区', 'GMT+8', 'GMT 时区偏移')
        add('上海时区', 'Asia/Shanghai', 'IANA 时区名称')
    for choice in enum_choices(expected_type):
        add(str(choice['label']), str(choice['label']), '当前字段允许的固定选项')
    return result


def _operator_suggestions(expected_type: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []

    def add(label: str, insert_text: str, description: str) -> None:
        result.append({'label': label, 'insert_text': insert_text, 'description': description})

    comparable = expected_type in {
        'int64', 'float64', 'percentage', 'duration', 'date', 'datetime', 'time', 'time_of_day',
    }
    if expected_type in {'int64', 'float64', 'percentage'}:
        for label, token in (('相加', ' + '), ('相减', ' - '), ('相乘', ' * '), ('相除', ' / '), ('取余', ' % ')):
            add(label, token, f'在当前数值后{label}')
    if expected_type == 'bool':
        add('并且', ' 且 ', '两个条件都满足')
        add('或者', ' 或 ', '任一条件满足')
        add('取反', '非 ', '反转一个条件')
        for label in ('大于', '大于等于', '小于', '小于等于'):
            add(label, f' {label} ', '用于比较数值、日期、时间或持续时间')
    if comparable:
        for label in ('大于', '大于等于', '小于', '小于等于'):
            add(label, f' {label} ', f'比较两侧的{label}关系')
    if expected_type not in {'unit', 'unset', 'any'}:
        add('等于', ' 等于 ', '判断两个值相等')
        add('不等于', ' 不等于 ', '判断两个值不相等')
    return result


def _discovery_payload(expected_type: str, candidates: tuple[PureOperationCandidateV6, ...]) -> dict[str, object]:
    compatible_ids = {item.operation_id for item in candidates}
    result_hints = {
        operation_id: _operation_result_type_hints(operation_id)
        for operation_id in PURE_OPERATION_PRESENTATIONS
    }
    operation_counts: dict[str, int] = {}
    compatible_counts: dict[str, int] = {}
    for presentation in PURE_OPERATION_PRESENTATIONS.values():
        operation_counts[presentation.category] = operation_counts.get(presentation.category, 0) + 1
        if presentation.operation_id in compatible_ids:
            compatible_counts[presentation.category] = compatible_counts.get(presentation.category, 0) + 1
    return {
        'namespaces': [
            {
                'name': name,
                'description': description,
                'keywords': list(keywords),
                'operation_count': operation_counts.get(name, 0),
                'compatible_count': compatible_counts.get(name, 0),
            }
            for name, description, keywords in EXPRESSION_NAMESPACES
        ],
        'operations': [
            presentation.discovery_dict(
                compatible=presentation.operation_id in compatible_ids,
                result_type_hints=result_hints[presentation.operation_id],
            )
            for presentation in sorted(PURE_OPERATION_PRESENTATIONS.values(), key=lambda item: (item.category, item.syntax_name))
        ],
        'literals': _literal_suggestions(expected_type),
        'operators': _operator_suggestions(expected_type),
        'triggers': [
            {'keys': 'Ctrl+Space', 'description': '打开当前字段的全部可用写法'},
            {'keys': '@', 'description': '选择变量或前序结果'},
            {'keys': '.', 'description': '查看值字段或命名空间操作'},
            {'keys': '(', 'description': '查看操作参数与固定选项'},
        ],
    }


def pure_value_catalog_payload(
    expected_type: str,
    available_types: Iterable[str] = (),
    sources: Iterable[object] = (),
) -> dict[str, object]:
    record_type = _record_type_id(expected_type)
    record = record_type_contract(record_type)
    candidates = resolve_operation_candidates(expected_type, available_types)
    record_payload = None if record is None else record_type_payload(record)
    if record_payload is not None:
        for serialized, field_contract in zip(record_payload['fields'], record.fields, strict=True):
            serialized['choices'] = [dict(item) for item in enum_choices(field_contract.value_type)]
    return {
        'schema_version': 2,
        'registry_version': PURE_OPERATION_REGISTRY_VERSION,
        'registry_hash': pure_operation_registry_hash(),
        'expected_type': expected_type,
        'operations': [item.to_dict() for item in candidates],
        'discovery': _discovery_payload(expected_type, candidates),
        'members': [item.to_dict() for item in resolve_member_candidates(expected_type, sources)],
        'record': record_payload,
    }


__all__ = [
    'PURE_OPERATION_PRESENTATIONS',
    'EXPRESSION_NAMESPACES',
    'PureOperationCandidateV6',
    'PureOperationPresentationV6',
    'operation_candidate',
    'pure_value_catalog_payload',
    'resolve_operation_candidates',
    'resolve_member_candidates',
]
