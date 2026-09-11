from __future__ import annotations

from scripts.generate_expression_syntax_reference import OUTPUT, render_reference
from core.vnext.pure_operations_v6 import EXECUTABLE_PURE_OPERATIONS
from core.vnext.value_catalog_v6 import PURE_OPERATION_PRESENTATIONS


def test_every_executable_pure_operation_has_one_unique_formula_name() -> None:
    assert set(PURE_OPERATION_PRESENTATIONS) == set(EXECUTABLE_PURE_OPERATIONS)
    names = [item.syntax_name for item in PURE_OPERATION_PRESENTATIONS.values()]
    assert len(names) == len(set(names)) == 98
    assert all('.' in name and not name.endswith('.') for name in names)


def test_checked_in_formula_reference_is_generated_from_the_registry() -> None:
    assert OUTPUT.read_text(encoding='utf-8') == render_reference()


def test_color_comparison_uses_color_specific_input_labels() -> None:
    presentation = PURE_OPERATION_PRESENTATIONS['core.color_matches.v1']
    assert presentation.input_labels['actual'] == '实际颜色'
    assert presentation.input_labels['expected'] == '目标颜色'
