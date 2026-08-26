"""Structured execution-log categories shared by runtime and persistence."""

from __future__ import annotations

from typing import Final


LOG_CATEGORIES: Final[tuple[str, ...]] = (
    'execution',
    'node',
    'vision',
    'navigation',
    'operation',
    'data',
)

_CATEGORY_MARKERS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ('navigation', ('智能跳转', '弹窗处理', '寻路', '路径节点', '当前位置')),
    ('vision', ('页面状态', 'OCR', '图像识别', '识图', '模板匹配', '目标截图')),
    (
        'operation',
        (
            '目标绑定', '输入验证', '点击', '控件操作', 'set_window', '工作窗口',
            'ADB', '滚动', '滑动', '拖拽', '长按', '文本输入', '物理输入',
        ),
    ),
    (
        'data',
        (
            '变量操作', '变量写入', '条件评估', '逻辑判断', 'Branch', '分支',
            '调用能力', '能力 ', '脚本', '表达式',
        ),
    ),
    ('node', ('Node', '节点执行', '节点完成', '节点失败', '前置延迟', '等待 ')),
)
_FOLDED_CATEGORY_MARKERS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = tuple(
    (category, tuple(marker.casefold() for marker in markers))
    for category, markers in _CATEGORY_MARKERS
)


def infer_log_category(message: object, category: str | None = None) -> str:
    """Return a stable category while accepting explicit categories from callers."""
    explicit = str(category or '').strip().lower()
    if explicit in LOG_CATEGORIES:
        return explicit

    text = str(message or '').casefold()
    for candidate, markers in _FOLDED_CATEGORY_MARKERS:
        if any(marker in text for marker in markers):
            return candidate
    return 'execution'
