from __future__ import annotations

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.record_types_v6 import (
    RECORD_TYPE_CONTRACTS,
    RecordTypeV6,
    editor_strategy_for_type,
    record_type_contract,
)


def test_every_registered_record_has_the_frozen_authoring_classification() -> None:
    inline = {
        "color", "size", "key_chord", "ocr_preprocess", "filesystem_filter",
        "window_selector", "http_pair", "http_body",
    }
    focused = {"multipart_field"}
    capture = {"control_selector"}
    reference = set(RECORD_TYPE_CONTRACTS) - inline - focused - capture

    assert {
        type_id: (contract.authoring_mode, contract.editor_strategy)
        for type_id, contract in RECORD_TYPE_CONTRACTS.items()
    } == {
        **{type_id: ("constructible", "inline_record") for type_id in inline},
        **{type_id: ("constructible", "focused") for type_id in focused},
        **{type_id: ("capture_only", "capture") for type_id in capture},
        **{type_id: ("reference_only", "reference") for type_id in reference},
    }

    # A new record is never accidentally made constructible by defaults.
    safe_default = RecordTypeV6(type_id="future_result", display_name="未来结果", fields=())
    assert (safe_default.authoring_mode, safe_default.editor_strategy) == (
        "reference_only", "reference",
    )


def test_record_editor_strategy_resolves_optional_and_collection_types() -> None:
    assert editor_strategy_for_type("optional<ocr_preprocess>") == "inline_record"
    assert editor_strategy_for_type("list<http_pair>") == "row_list"
    assert editor_strategy_for_type("list<multipart_field>") == "row_list"
    assert editor_strategy_for_type("optional<frame_ref>") == "reference"
    assert editor_strategy_for_type("control_selector") == "capture"
    assert editor_strategy_for_type("string") is None
    assert record_type_contract("record<ocr_preprocess>") is record_type_contract(
        "ocr_preprocess",
    )


def test_ocr_preprocess_has_complete_inline_field_metadata() -> None:
    contract = record_type_contract("ocr_preprocess")
    assert contract is not None
    assert contract.authoring_mode == "constructible"
    assert contract.editor_strategy == "inline_record"

    fields = {item.field_id: item for item in contract.fields}
    assert fields["ocr_preprocess.field.grayscale"].default is False
    assert fields["ocr_preprocess.field.binary"].default is False
    assert fields["ocr_preprocess.field.invert"].default is False
    threshold = fields["ocr_preprocess.field.threshold"]
    assert threshold.required is False
    assert threshold.has_default is True
    assert threshold.default == 127
    assert threshold.constraints == {"minimum": 0, "maximum": 255}
    assert threshold.ui == {
        "control": "slider-number",
        "importance": "primary",
        "placeholder": "0–255",
        "help": "仅在开启二值化时生效。",
        "visible_when": {
            "field_id": "ocr_preprocess.field.binary",
            "operator": "equals",
            "value": True,
        },
    }
    parameter = next(
        item
        for item in official_function_registry_v6.require('official.text.recognize').parameters
        if item.name == 'preprocess'
    )
    assert parameter.default == {
        field.field_id: field.default
        for field in contract.fields
        if field.has_default
    }


def test_constructible_record_field_rules_reference_stable_sibling_ids() -> None:
    for contract in RECORD_TYPE_CONTRACTS.values():
        known = {field.field_id for field in contract.fields}
        for record_field in contract.fields:
            visible_when = record_field.ui.get('visible_when')
            if visible_when is not None:
                assert visible_when['field_id'] in known
                assert visible_when['operator'] == 'equals'

    key_chord = record_type_contract('key_chord')
    assert key_chord is not None
    assert key_chord.fields[0].constraints == {
        'min_items': 1, 'max_items': 4, 'unique_items': True,
    }


def test_function_parameter_strategy_never_drifts_from_named_record_contracts() -> None:
    for function in official_function_registry_v6.complete_catalog():
        for parameter in function["parameters"]:
            strategy = editor_strategy_for_type(parameter["value_type"])
            if strategy is None:
                continue
            assert parameter["ui"]["editor_strategy"] == strategy, (
                function["function_id"], parameter["parameter_id"]
            )
            if strategy in {"reference", "capture"}:
                assert parameter["ui"]["editor_strategy"] not in {
                    "inline_record", "row_list", "focused",
                }


def test_every_official_parameter_carries_a_stable_first_render_strategy() -> None:
    allowed = {"scalar", "reference", "capture", "inline_record", "row_list", "focused"}
    for function in official_function_registry_v6.complete_catalog():
        for parameter in function["parameters"]:
            assert parameter["ui"].get("editor_strategy") in allowed, (
                function["function_id"], parameter["parameter_id"]
            )
