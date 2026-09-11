from __future__ import annotations

import builtins
import os
import time
from pathlib import Path

import pytest

from core.vnext.file_reference_values_v6 import (
    FileReferenceDerivationError,
    derive_file_reference,
    safe_relative_segments,
)
from core.vnext.pure_operations_v6 import pure_operation_type_issues
from core.vnext.runtime import VNextRuntime
from core.vnext.value_catalog_v6 import resolve_operation_candidates


def _ref(symbol_id: str) -> dict[str, str]:
    return {'kind': 'reference', 'scope': 'local', 'symbol_id': symbol_id}


def _operation(result_type: str, directory: object, relative_path: object) -> dict[str, object]:
    operation_id = 'core.file_ref_child.v1'
    return {
        'kind': 'operation',
        'operation_id': operation_id,
        'result_type': result_type,
        'inputs': {
            f'{operation_id}.input.directory': directory,
            f'{operation_id}.input.relative_path': relative_path,
        },
    }


def _instruction(
    instruction_id: str,
    opcode: str,
    arguments: dict[str, object],
    result_slot: str | None = None,
) -> dict[str, object]:
    function_id = {
        'project.data_directory': 'official.project.data_directory',
        'file.write_text': 'official.file.write_text',
    }.get(opcode, '')
    return {
        'instruction_id': instruction_id,
        'function_id': function_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': result_slot,
        'source': {},
        'capabilities': [],
    }


def _plan(project_path: Path, relative_path: str) -> dict[str, object]:
    return {
        'entry_function_id': 'project.main',
        'project_path': str(project_path),
        'functions': [{
            'function_id': 'project.main',
            'name': '主程序',
            'parameters': [],
            'parameter_definitions': [],
            'return_type': 'null',
            'instructions': [
                _instruction('data.directory', 'project.data_directory', {}, 'data_directory'),
                _instruction('file.write', 'file.write_text', {
                    'official.file.write_text.parameter.file': _operation(
                        'file_ref<write>', _ref('data_directory'), relative_path,
                    ),
                    'official.file.write_text.parameter.content': '闭环成功',
                    'official.file.write_text.parameter.encoding': 'utf-8',
                }),
            ],
        }],
    }


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


def test_registry_and_catalog_only_offer_capability_preserving_signatures() -> None:
    write = tuple(
        item for item in resolve_operation_candidates(
            'file_ref<write>', ('directory_ref<read_write>',),
        ) if item.operation_id == 'core.file_ref_child.v1'
    )
    read = tuple(
        item for item in resolve_operation_candidates(
            'file_ref<read>', ('directory_ref<read>',),
        ) if item.operation_id == 'core.file_ref_child.v1'
    )

    assert [(item.operation_id, item.result_type) for item in write] == [
        ('core.file_ref_child.v1', 'file_ref<write>'),
    ]
    assert [input_item[2] for input_item in write[0].inputs] == [
        'directory_ref<read_write>', 'relative_path',
    ]
    assert [(item.operation_id, item.result_type) for item in read] == [
        ('core.file_ref_child.v1', 'file_ref<read>'),
    ]
    assert not any(
        item.operation_id == 'core.file_ref_child.v1'
        for item in resolve_operation_candidates('file_ref<write>', ('directory_ref<read>',))
    )
    assert pure_operation_type_issues(
        'core.file_ref_child.v1',
        'file_ref<write>',
        {
            'core.file_ref_child.v1.input.directory': 'directory_ref<read>',
            'core.file_ref_child.v1.input.relative_path': 'relative_path',
        },
    )


def test_derivation_is_pure_and_shrinks_runtime_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_open(*_args, **_kwargs):
        raise AssertionError('pure derivation must not touch filesystem')

    monkeypatch.setattr(builtins, 'open', forbidden_open)
    reference = derive_file_reference(
        {
            'kind': 'directory_ref',
            'platform': 'windows',
            'path': r'D:\data',
            'authorization_root': r'D:\data',
            'authorization_root_id': 'root-1',
            'access': ['read', 'list', 'create', 'delete_empty'],
        },
        'reports/result.json',
        'file_ref<write>',
    )

    assert reference == {
        'kind': 'file_ref',
        'platform': 'windows',
        'source': 'derived_relative',
        'display_name': 'result.json',
        'authorization_root_id': 'root-1',
        'access': ['write'],
        'path': r'D:\data\reports\result.json',
        'authorization_root': r'D:\data',
    }


def test_android_derivation_is_deferred_to_saf_host() -> None:
    reference = derive_file_reference(
        {
            'kind': 'directory_ref',
            'platform': 'android',
            'source': 'player_picker',
            'uri': 'content://provider/tree/root',
            'authorization_root_id': 'android-tree:root',
            'access': ['read', 'list', 'write', 'create'],
        },
        'reports/result.json',
        'file_ref<read>',
    )

    assert reference['access'] == ['read']
    assert reference['uri'] == 'content://provider/tree/root'
    assert reference['relative_segments'] == ['reports', 'result.json']
    assert 'path' not in reference


@pytest.mark.parametrize(
    'relative_path',
    ['', '/root.txt', r'..\escape.txt', '../escape.txt', 'a//b', './file', 'CON.txt', 'bad?.txt'],
)
def test_unsafe_relative_paths_are_rejected_before_any_host_access(relative_path: str) -> None:
    with pytest.raises(FileReferenceDerivationError) as error:
        safe_relative_segments(relative_path)
    assert error.value.error_id == 'file.relative_path_invalid'


@pytest.mark.skipif(os.name != 'nt', reason='Windows reference host integration')
def test_project_data_directory_to_derived_file_executes_end_to_end(tmp_path: Path) -> None:
    runtime = VNextRuntime(persist_event_log=False)
    project_path = tmp_path / 'project'
    result = _terminal(runtime, runtime.start(_plan(project_path, 'result.txt'))['execution_id'])

    assert result['status'] == 'completed', result.get('error')
    assert (project_path / '.easycode' / 'data' / 'result.txt').read_text(encoding='utf-8') == '闭环成功'


@pytest.mark.skipif(os.name != 'nt', reason='Windows reference host integration')
def test_traversal_fails_before_mutating_outside_project_data(tmp_path: Path) -> None:
    runtime = VNextRuntime(persist_event_log=False)
    project_path = tmp_path / 'project'
    result = _terminal(runtime, runtime.start(_plan(project_path, '../escape.txt'))['execution_id'])

    assert result['status'] == 'failed'
    assert result['error_id'] == 'file.relative_path_invalid'
    assert not (project_path / '.easycode' / 'escape.txt').exists()
    assert not (project_path / 'escape.txt').exists()
