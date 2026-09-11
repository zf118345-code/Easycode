"""Generate the user-facing formula syntax reference from the pure-value registry."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.pure_operations_v6 import OPERATION_INPUT_NAMES  # noqa: E402
from core.vnext.value_catalog_v6 import (  # noqa: E402
    EXPRESSION_NAMESPACES,
    PURE_OPERATION_PRESENTATIONS,
)


OUTPUT = ROOT / 'docs' / 'vnext' / 'EXPRESSION_SYNTAX.md'
CATEGORY_ORDER = tuple(item[0] for item in EXPRESSION_NAMESPACES)

INTRO_LINES = (
    '## 输入器的含义',
    '',
    '统一值输入框把草稿解析为强类型值节点，不会把公式文字原样保存。同一段文字会按当前字段需要的类型解释；例如 `空` 在可选结果中表示无结果，在普通文本中仍是“空”字。',
    '',
    '## 不需要记忆的发现入口',
    '',
    '- 在任意统一值输入框按 `Ctrl+Space`：查看当前字段的直接值、变量入口、纯值命名空间、参数选项和运算符。',
    '- 输入 `@`：只列变量和前序结果本体；选中后输入 `.`：逐级查看该值的字段。',
    '- 输入 `文本.`、`数值.` 等命名空间：查看这一类全部纯值操作。当前字段不适用的操作仍可看见，但会禁用并说明原因。',
    '- 选择操作并进入括号：当前参数名称、类型、固定选项和可用直接值会随光标变化；不必背参数顺序。',
    '',
    '## 可直接输入的值',
    '',
    '| 类别 | 推荐写法 | 保存后的含义或展示 | 限制 |',
    '| --- | --- | --- | --- |',
    '| 普通文本 | `当前体力不足` | 原样显示 | 文本字段中的特殊词不会被强行当作运算 |',
    '| 引号文本 | `"旧服"`、`“旧服”`、`\'旧服\'` | 去掉外层引号后保存为文本 | 函数参数内推荐加引号 |',
    '| 整数 | `18`、`-3`、`+5` | 整数 | 必须在安全整数范围内 |',
    '| 小数/百分比字段 | `18.5`、`.25`、`-0.5` | 有限小数 | `50%` 不是百分比字面量；`%` 表示取余 |',
    '| 真 | `开启`、`是`、`真`、`true` | 统一显示为 `开启` | 英文不区分大小写 |',
    '| 假 | `关闭`、`否`、`假`、`false` | 统一显示为 `关闭` | 英文不区分大小写 |',
    '| 可选值为空 | `无结果`、`空`、`null` | 统一显示为 `无结果` | 只在当前字段是可选值时成立 |',
    '| 持续时间 | `500 毫秒`、`2 秒`、`1 分钟` | 按可读单位显示 | 也接受 `ms`、`s`、`min`；不得小于 0 |',
    '| 动态持续时间 | `[局部 · 秒数] 秒` | 变量词元加单位 | 单位前可以是数值表达式 |',
    '| 日期 | `2026-09-06` | `YYYY-MM-DD` | 必须是有效日期 |',
    '| 日期时间 | `2026-09-06 18:30`、`2026-09-06 18:30:45` | 内部规范为 ISO 日期时间 | 可省略秒 |',
    '| 时间 | `18:30`、`18:30:45` | `HH:mm` 或 `HH:mm:ss` | 24 小时制 |',
    '| 坐标 | `坐标(480, 320)` | 坐标摘要 | 两项均须为有限数值 |',
    '| 区域 | `区域(100, 80, 640, 360)` | 区域摘要 | 顺序为 X、Y、宽、高 |',
    '| 列表字面量 | `["data", "roomCode"]` | 强类型列表 | 只在已知列表项类型的位置使用；字典不能直接手写 `{...}` |',
    '| 枚举值 | `包含`、`"以后者为准"` | 当前字段的枚举值 | 可用值以表单或补全为准 |',
    '',
    '## 变量、结果和字段',
    '',
    '| 操作 | 输入方法 | 选择后的稳定展示 |',
    '| --- | --- | --- |',
    '| 选择变量或语句结果 | 输入 `@`，再从候选中选择 | `[局部 · 当前体力]` 或 `[项目 · 最低体力]`；界面用半方括号词元绘制 |',
    '| 读取直接字段 | 选择结构化值后输入 `.` | `[局部 · 图像结果].相似度` |',
    '| 读取嵌套字段 | 选择一层字段后继续输入 `.` | `[局部 · 识字结果].来源画面.宽度` |',
    '| 在文字中嵌入标量 | 在普通文字中输入 `@` 并选择 | `当前体力为 [项目 · 当前体力]`；数值、布尔、日期、时间等会转成稳定文本 |',
    '',
    '不建议手写变量词元。解析器为编辑便利仍接受 `@名称`、`局部.名称`、`项目.名称`、`[局部变量 · 名称]` 等别名；存在同名值时必须从 `@` 候选中选择。项目最终保存稳定变量 ID 和字段 ID，而不是显示文字。',
    '',
    '可选结果（例如“查找图像”）未经过“有结果”判断时仍显示字段目录，但不允许提交字段。先使用 `结果.有结果([局部 · 图像结果])` 判断，再在成立分支读取字段；需要继续计算时也可以使用 `结果.无结果时使用默认值(...)`。',
    '',
    '## 运算符与结构语法',
    '',
    '| 类别 | 可输入写法 | 规范展示 |',
    '| --- | --- | --- |',
    '| 四则与取余 | `+`、`-`、`*`、`/`、`%` | 保留符号，并用括号表达运算层级 |',
    '| 中文比较 | `等于`、`不等于`、`大于`、`大于等于`、`小于`、`小于等于` | 中文语义词高亮 |',
    '| 比较符号别名 | `==`、`!=`、`>`、`>=`、`<`、`<=` | 统一显示为对应中文比较词 |',
    '| 并且 | `条件A 且 条件B`、`A && B` | 统一显示为 `且` |',
    '| 或者 | `条件A 或 条件B`、`A || B` | 统一显示为 `或` |',
    '| 取反 | `非 条件`、`!条件` | 统一显示为 `非 (条件)` |',
    '| 分组 | `( ... )` | 明确运算和条件层级 |',
    '| 纯值操作 | `命名空间.操作(参数1, 参数2)` | 操作名和参数按语义分词显示；操作可以嵌套 |',
    '| 逐项表达式 | `每项 => 表达式`、`逐项 → 表达式` | 统一显示为 `每项 => ...` |',
    '',
    '列表逐项操作中可用 `@当前项`、`@当前序号`；字典逐项操作中可用 `@当前键`、`@当前值`。`且` 和 `或` 建议两侧留空格，避免与普通文字混淆。大于/小于只适用于数值、持续时间、日期和时间；等于/不等于还可以比较其他相同或兼容类型。',
    '',
    '## 中文标点兼容',
    '',
    '引号外的 `。`、`．` 会按 `.` 处理，`，` 按 `,` 处理，`（）` 按 `()` 处理，并接受中文引号 `“”`、`‘’`。引号内的标点保持文本原意。',
    '',
    '## 保存后会特殊显示的内容',
    '',
    '| 内容 | 展示规则 |',
    '| --- | --- |',
    '| 局部/项目变量 | 半方括号词元；两种作用域使用不同的克制文字色 |',
    '| 字段访问 | `.字段名` 作为操作词元 |',
    '| 运算、比较、逻辑词和纯值操作名 | 使用操作强调色 |',
    '| 括号与逗号 | 降低为辅助层级 |',
    '| `空/null/无结果` | 在可选字段中统一为 `无结果` |',
    '| 布尔别名 | 统一为 `开启` 或 `关闭` |',
    '| 图片、目标、文件、控件选择器等引用 | 显示“类型 + 业务名称”摘要；由选择器或捕获器生成，不要手写内部 ID |',
    '| 列表、字典、JSON 和其他结构值 | 简单列表显示内容；复杂值显示类型/业务摘要，并用 `.` 逐层读取 |',
    '| 未填写的可选字段 | 显示真实默认值或 placeholder，不伪装成已保存公式 |',
    '',
    '## 不能写进输入框的内容',
    '',
    '截图、OCR、等待、点击、文件读写、网络请求、消息收发、取得当前时间和随机数等会访问外部状态或每次可能返回不同结果的能力，必须作为独立流程语句插入。输入框只接受无等待、无外部副作用并可类型检查的纯值计算。',
    '',
)


def render_reference() -> str:
    groups: dict[str, list[object]] = defaultdict(list)
    for presentation in PURE_OPERATION_PRESENTATIONS.values():
        groups[presentation.category].append(presentation)

    lines = [
        '# 统一值输入语法参考',
        '',
        '> 本文件由 `scripts/generate_expression_syntax_reference.py` 从权威纯值注册表生成，请勿手工维护操作清单。',
        '',
        *INTRO_LINES,
    ]
    for category in (*CATEGORY_ORDER, *sorted(set(groups) - set(CATEGORY_ORDER))):
        items = sorted(groups.get(category, ()), key=lambda item: item.syntax_name)
        if not items:
            continue
        lines.extend((f'## {category}', '', '| 写法 | 参数 | 用途 | 示例 |', '| --- | --- | --- | --- |'))
        for item in items:
            names = OPERATION_INPUT_NAMES[item.operation_id]
            labels = '，'.join(item.input_labels.get(name, name) for name in names) or '无'
            lines.append(f'| `{item.syntax_name}(…)` | {labels} | {item.description} | `{item.discovery_dict(compatible=True, result_type_hints=()).get("example", "")}` |')
        lines.append('')

    lines.extend((
        '## 组合示例',
        '',
        '```text',
        '[局部 · 当前体力] 大于等于 [项目 · 最低体力] 且 非 [局部 · 正在战斗]',
        '当前体力为 [局部 · 当前体力]',
        '文本.替换([项目 · 公告内容], "旧服", "新服")',
        '数值.限制范围([局部 · 识别数值] + 5, 0, 100)',
        '列表.筛选([项目 · 副本等级], 每项 => @当前项 大于等于 15)',
        '字典.筛选([项目 · 角色配置], 每项 => @当前值 大于等于 3)',
        'JSON.读取路径([局部 · 接口结果], ["data", "roomCode"])',
        '```',
        '',
        '输入中的显示名称只用于编辑与补全；项目保存的是稳定操作 ID、输入槽 ID、变量 ID 和字段 ID。',
        '',
    ))
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = render_reference()
    if args.check:
        return 0 if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == rendered else 1
    OUTPUT.write_text(rendered, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
