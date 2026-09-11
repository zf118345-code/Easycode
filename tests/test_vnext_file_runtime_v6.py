from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from core.vnext.file_runtime_v6 import (
    FileRuntimeV6,
    windows_directory_reference,
    windows_file_reference,
)
from core.vnext.function_contracts_v6 import (
    OfficialFunctionRegistryV6,
    official_function_registry_v6,
)
from core.vnext.program_compiler import compile_program_bundle
from core.vnext.program_runtime_v6 import adapt_program_ecir_for_runtime
from core.vnext.program_types import (
    CallStatement,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    ResultBinding,
    SymbolReferenceValue,
)
from core.vnext.runtime import RuntimeFailure, VNextRuntime


def _instruction(
    instruction_id: str,
    function_id: str,
    opcode: str,
    arguments: dict[str, Any],
    result_slot: str | None = None,
) -> dict[str, Any]:
    return {
        'instruction_id': instruction_id,
        'function_id': function_id,
        'opcode': opcode,
        'arguments': arguments,
        'result_slot': result_slot,
        'source': {},
        'platforms': ['windows', 'android_local'],
        'capabilities': ['filesystem'],
        'callee_function_id': None,
    }


def _args(function_id: str, **values: Any) -> dict[str, Any]:
    return {f'{function_id}.parameter.{name}': value for name, value in values.items()}


def _plan(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    return adapt_program_ecir_for_runtime({
        'program_model_version': 1,
        'entry_function_id': 'project.main',
        'functions': [{
            'function_id': 'project.main',
            'name': '主程序',
            'parameters': [],
            'parameter_definitions': [],
            'return_type': 'null',
            'instructions': instructions,
        }],
    })


def _terminal(runtime: VNextRuntime, execution_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot(execution_id)
        if snapshot['status'] in {'completed', 'failed', 'cancelled'}:
            return snapshot
        time.sleep(0.01)
    raise AssertionError('运行未在限时内结束')


def _run(instructions: list[dict[str, Any]]) -> dict[str, Any]:
    runtime = VNextRuntime(persist_event_log=False)
    return _terminal(runtime, runtime.start(_plan(instructions))['execution_id'])


def test_text_replace_json_and_file_lifecycle_end_to_end(tmp_path: Path) -> None:
    file_path = tmp_path / 'data.txt'
    copied_path = tmp_path / 'copied.txt'
    moved_path = tmp_path / 'moved.txt'
    json_path = tmp_path / 'data.json'
    write_ref = windows_file_reference(
        str(file_path), str(tmp_path), access=('read', 'write', 'delete', 'read_delete'),
    )
    copy_ref = windows_file_reference(
        str(copied_path), str(tmp_path), access=('read', 'write', 'delete', 'read_delete'),
    )
    move_ref = windows_file_reference(
        str(moved_path), str(tmp_path), access=('read', 'write', 'delete', 'read_delete'),
    )
    json_ref = windows_file_reference(
        str(json_path), str(tmp_path), access=('read', 'write'),
    )
    instructions = [
        _instruction('write', 'official.file.write_text', 'file.write_text', _args(
            'official.file.write_text', file=write_ref, content='A=false\nA=false', encoding='utf-8',
        )),
        _instruction('append', 'official.file.append_text', 'file.append_text', _args(
            'official.file.append_text', file=write_ref, content='\nEND', encoding='utf-8',
        )),
        _instruction('replace', 'official.file.replace_text', 'file.replace_text', _args(
            'official.file.replace_text', file=write_ref, search='A=false', replacement='A=true', scope='all', encoding='utf-8',
        ), 'replace_count'),
        _instruction('read', 'official.file.read_text', 'file.read_text', _args(
            'official.file.read_text', file=write_ref, encoding='utf-8',
        ), 'text'),
        _instruction('json.write', 'official.file.write_json', 'file.write_json', _args(
            'official.file.write_json', file=json_ref, data={'enabled': True, 'items': [1, 2]},
        )),
        _instruction('json.read', 'official.file.read_json', 'file.read_json', _args(
            'official.file.read_json', file=json_ref,
        ), 'json'),
        _instruction('copy', 'official.file.copy', 'file.copy', _args(
            'official.file.copy', source=write_ref, destination=copy_ref, conflict='error',
        )),
        _instruction('move', 'official.file.move', 'file.move', _args(
            'official.file.move', source=copy_ref, destination=move_ref, conflict='error',
        )),
        _instruction('delete', 'official.file.delete', 'file.delete', _args(
            'official.file.delete', file=move_ref,
        ), 'deleted'),
    ]
    result = _run(instructions)
    assert result['status'] == 'completed', result['error']
    assert result['variables']['replace_count'] == 2
    assert result['variables']['text'] == 'A=true\nA=true\nEND'
    assert result['variables']['json'] == {'enabled': True, 'items': [1, 2]}
    assert result['variables']['deleted'] is True
    assert not moved_path.exists()
    assert json.loads(json_path.read_text(encoding='utf-8'))['enabled'] is True


def test_program_bundle_parameter_reference_reaches_file_runtime(tmp_path: Path) -> None:
    path = tmp_path / 'compiled.txt'
    path.write_text('来自编译器', encoding='utf-8')
    parameter = ProgramParameter(
        parameter_id='project.main.parameter.file',
        symbol_id='project.main.symbol.file',
        display_name='文件',
        value_type='file_ref<read>',
    )
    document = ProgramDocument(
        document_id='document.project.main',
        function=ProgramFunction(
            function_id='project.main',
            display_name='主程序',
            parameters=(parameter,),
            statements=(CallStatement(
                statement_id='project.main.statement.read',
                function_id='official.file.read_text',
                arguments={
                    'official.file.read_text.parameter.file': SymbolReferenceValue(
                        value_id='project.main.value.file',
                        symbol_id=parameter.symbol_id,
                        value_type='file_ref<read>',
                    ),
                },
                result_binding=ResultBinding(
                    symbol_id='project.main.symbol.text',
                    display_name='文本',
                    value_type='string',
                ),
            ),),
        ),
    )
    verified_windows_registry = OfficialFunctionRegistryV6((
        official_function_registry_v6.require('official.file.read_text'),
    ))
    compiled = compile_program_bundle(
        [document], verified_windows_registry,
        entry_function_id='project.main', target_platform='windows',
    )
    assert compiled['valid'] is True, compiled['diagnostics']
    plan = adapt_program_ecir_for_runtime(compiled['ecir'])
    plan['function_arguments'] = {'project.main': {
        parameter.parameter_id: windows_file_reference(
            str(path), str(tmp_path), access=('read',),
        ),
    }}
    runtime = VNextRuntime(persist_event_log=False)
    result = _terminal(runtime, runtime.start(plan)['execution_id'])
    assert result['status'] == 'completed', result['error']
    assert result['variables']['project.main.symbol.text'] == '来自编译器'


def test_directory_create_list_copy_move_and_empty_delete(tmp_path: Path) -> None:
    root_ref = windows_directory_reference(
        str(tmp_path), str(tmp_path),
        access=('read', 'list', 'create', 'move', 'delete_empty'),
    )
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'one.txt').write_text('1', encoding='utf-8')
    source_ref = windows_directory_reference(
        str(source), str(tmp_path), access=('read', 'list', 'move', 'delete_empty'),
    )
    empty = tmp_path / 'empty'
    empty.mkdir()
    empty_ref = windows_directory_reference(
        str(empty), str(tmp_path), access=('read', 'delete_empty'),
    )
    instructions = [
        _instruction('create', 'official.directory.create', 'directory.create', _args(
            'official.directory.create', parent=root_ref, relative_path='created', existing='return_existing',
        ), 'created'),
        _instruction('list', 'official.directory.list', 'directory.list', _args(
            'official.directory.list', directory=root_ref, filter={'pattern': '*', 'limit': 20}, recursive=False,
        ), 'entries'),
        _instruction('copy', 'official.directory.copy', 'directory.copy', _args(
            'official.directory.copy', source=source_ref, destination_parent=root_ref, name='copied', conflict='error',
        ), 'copy_report'),
        _instruction('move', 'official.directory.move', 'directory.move', _args(
            'official.directory.move', source=source_ref, destination_parent=root_ref, name='moved', conflict='error',
        ), 'move_report'),
        _instruction('delete', 'official.directory.delete_empty', 'directory.delete', _args(
            'official.directory.delete_empty', directory=empty_ref,
        ), 'deleted'),
    ]
    result = _run(instructions)
    assert result['status'] == 'completed', result['error']
    assert result['variables']['copy_report']['tree_operation_report.field.complete'] is True
    assert result['variables']['move_report']['tree_operation_report.field.complete'] is True
    assert result['variables']['deleted'] is True
    assert (tmp_path / 'copied' / 'one.txt').read_text(encoding='utf-8') == '1'
    assert (tmp_path / 'moved' / 'one.txt').read_text(encoding='utf-8') == '1'
    assert len(result['variables']['entries']) <= 20


def test_directory_list_derived_references_never_gain_access(tmp_path: Path) -> None:
    child = tmp_path / 'child'
    child.mkdir()
    (tmp_path / 'data.txt').write_text('secret', encoding='utf-8')
    reference = windows_directory_reference(
        str(tmp_path),
        str(tmp_path),
        access=('list',),
        authorization_root_id='root.explicit',
        source='player_picker',
    )
    result = _run([_instruction(
        'list',
        'official.directory.list',
        'directory.list',
        _args(
            'official.directory.list',
            directory=reference,
            filter={'pattern': '*', 'limit': 20},
            recursive=False,
        ),
        'entries',
    )])
    assert result['status'] == 'completed', result['error']
    entries = result['variables']['entries']
    assert {item['filesystem_entry.field.name'] for item in entries} == {'child', 'data.txt'}
    for item in entries:
        derived = item['filesystem_entry.field.file'] or item['filesystem_entry.field.directory']
        assert derived['authorization_root_id'] == 'root.explicit'
        assert derived['source'] == 'player_picker'
        assert 'read' not in derived['access']


def test_directory_list_filter_is_structured_bounded_and_returns_composable_fields(tmp_path: Path) -> None:
    (tmp_path / 'alpha.txt').write_text('a', encoding='utf-8')
    (tmp_path / 'beta.txt').write_text('bb', encoding='utf-8')
    (tmp_path / 'ignore.json').write_text('{}', encoding='utf-8')
    reference = windows_directory_reference(
        str(tmp_path), str(tmp_path), access=('read', 'list'),
    )
    result = _run([_instruction(
        'list-filtered', 'official.directory.list', 'directory.list',
        _args(
            'official.directory.list', directory=reference,
            filter={
                'filesystem_filter.field.pattern': '*.txt',
                'filesystem_filter.field.limit': 1,
            },
            recursive=False,
        ),
        'entries',
    )])
    assert result['status'] == 'completed', result['error']
    assert len(result['variables']['entries']) == 1
    entry = result['variables']['entries'][0]
    assert entry['filesystem_entry.field.name'] == 'alpha.txt'
    assert entry['filesystem_entry.field.entry_type'] == 'file'
    assert entry['filesystem_entry.field.size'] == 1
    assert entry['filesystem_entry.field.file']['kind'] == 'file_ref'
    assert entry['filesystem_entry.field.directory'] is None


def test_directory_copy_rejects_destination_inside_source(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    nested_parent = source / 'nested'
    nested_parent.mkdir(parents=True)
    source_ref = windows_directory_reference(
        str(source), str(tmp_path), access=('read', 'list'),
    )
    nested_ref = windows_directory_reference(
        str(nested_parent), str(tmp_path), access=('create',),
    )
    result = _run([_instruction(
        'copy',
        'official.directory.copy',
        'directory.copy',
        _args(
            'official.directory.copy',
            source=source_ref,
            destination_parent=nested_ref,
            name='copy',
            conflict='error',
        ),
        'report',
    )])
    assert result['status'] == 'failed'
    assert result['error_id'] == 'file.destination_inside_source'
    assert not (nested_parent / 'copy').exists()


def test_concurrent_atomic_writes_never_leave_partial_content(tmp_path: Path) -> None:
    path = tmp_path / 'atomic.txt'
    reference = windows_file_reference(str(path), str(tmp_path), access=('write', 'read'))
    payloads = ['A' * 200_000, 'B' * 200_000, 'C' * 200_000]
    results: list[dict[str, Any]] = []

    def write(payload: str) -> None:
        results.append(_run([_instruction(
            f'write.{payload[0]}', 'official.file.write_text', 'file.write_text',
            _args('official.file.write_text', file=reference, content=payload, encoding='utf-8'),
        )]))

    threads = [threading.Thread(target=write, args=(payload,)) for payload in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(item['status'] == 'completed' for item in results)
    assert path.read_text(encoding='utf-8') in payloads
    assert not list(tmp_path.glob('.easycode-file-*.tmp'))


def test_authorization_escape_android_uri_and_recursive_delete_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / 'outside-easycode.txt'
    malicious = {
        'kind': 'file_ref', 'platform': 'windows', 'path': str(outside),
        'authorization_root': str(tmp_path), 'authorization_root_id': 'root.test',
        'access': ['read'],
    }
    escaped = _run([_instruction(
        'escape', 'official.file.exists', 'file.exists',
        _args('official.file.exists', file=malicious),
    )])
    assert escaped['error_id'] == 'file.outside_authorization'

    android = {
        'kind': 'file_ref', 'platform': 'android',
        'uri': 'content://provider/document/1', 'access': ['read'],
    }
    unsupported = _run([_instruction(
        'android', 'official.file.exists', 'file.exists',
        _args('official.file.exists', file=android),
    )])
    assert unsupported['error_id'] == 'file.android_host_unsupported'

    directory = windows_directory_reference(
        str(tmp_path), str(tmp_path), access=('delete_tree',),
    )
    recursive = _run([_instruction(
        'delete.tree', 'official.directory.delete_tree', 'directory.delete_tree',
        _args('official.directory.delete_tree', directory=directory),
    )])
    assert recursive['error_id'] == 'file.delete_tree_confirmation_required'
    assert tmp_path.exists()


def _delete_tree_context(statement_id: str, root_id: str, *, protected_roots=()):
    contract = official_function_registry_v6.require('official.directory.delete_tree')
    return {
        'instruction_id': statement_id,
        'protected_roots': list(protected_roots),
        'confirmation': {
            'confirmed': True,
            'statement_id': statement_id,
            'authorization_root_id': root_id,
            'execution_config_revision': 'test-revision-1',
            'contract_fingerprint': contract.fingerprint(),
        },
    }


def test_recursive_delete_requires_bound_confirmation_and_returns_report(tmp_path: Path) -> None:
    target = tmp_path / 'authorized-tree'
    (target / 'nested').mkdir(parents=True)
    (target / 'a.txt').write_text('a', encoding='utf-8')
    (target / 'nested' / 'b.txt').write_text('b', encoding='utf-8')
    root_id = 'root.tmp.delete-tree'
    reference = windows_directory_reference(
        str(target), str(tmp_path), access=('delete_tree',),
        authorization_root_id=root_id,
    )
    report = FileRuntimeV6().execute(
        'directory.delete_tree', 'official.directory.delete_tree',
        _args('official.directory.delete_tree', directory=reference),
        lambda: False,
        operation_context=_delete_tree_context('stmt.delete', root_id),
    )
    assert report == {
        'tree_delete_report.field.complete': True,
        'tree_delete_report.field.files_deleted': 2,
        'tree_delete_report.field.directories_deleted': 2,
        'tree_delete_report.field.failures': [],
    }
    assert not target.exists()


def test_recursive_delete_rejects_workspace_root_and_symlink_before_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    root_id = 'root.workspace'
    workspace_ref = windows_directory_reference(
        str(workspace), str(tmp_path), access=('delete_tree',),
        authorization_root_id=root_id,
    )
    with pytest.raises(RuntimeFailure) as protected:
        FileRuntimeV6().execute(
            'directory.delete_tree', 'official.directory.delete_tree',
            _args('official.directory.delete_tree', directory=workspace_ref),
            lambda: False,
            operation_context=_delete_tree_context(
                'stmt.workspace', root_id, protected_roots=(str(workspace),),
            ),
        )
    assert protected.value.error_id == 'file.protected_root'
    assert workspace.exists()

    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep.txt').write_text('keep', encoding='utf-8')
    target = workspace / 'tree'
    target.mkdir()
    link = target / 'escape'
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip('当前 Windows 环境不允许创建目录符号链接')
    target_ref = windows_directory_reference(
        str(target), str(workspace), access=('delete_tree',),
        authorization_root_id=root_id,
    )
    with pytest.raises(RuntimeFailure) as symlink:
        FileRuntimeV6().execute(
            'directory.delete_tree', 'official.directory.delete_tree',
            _args('official.directory.delete_tree', directory=target_ref),
            lambda: False,
            operation_context=_delete_tree_context('stmt.symlink', root_id),
        )
    assert symlink.value.error_id == 'file.symlink_escape'
    assert target.exists()
    assert (outside / 'keep.txt').read_text(encoding='utf-8') == 'keep'


def test_symlink_escape_and_cancelled_copy_preserve_destination(tmp_path: Path) -> None:
    outside = tmp_path.parent / 'outside-file.txt'
    outside.write_text('outside', encoding='utf-8')
    link = tmp_path / 'escape-link.txt'
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip('当前 Windows 环境不允许创建符号链接')
    with pytest.raises(RuntimeFailure) as escaped:
        windows_file_reference(str(link), str(tmp_path), access=('read',))
    assert getattr(escaped.value, 'error_id', '') == 'file.outside_authorization'

    source = tmp_path / 'large.bin'
    destination = tmp_path / 'destination.bin'
    source.write_bytes(b'A' * (3 * 1024 * 1024))
    destination.write_bytes(b'OLD')
    source_ref = windows_file_reference(str(source), str(tmp_path), access=('read',))
    destination_ref = windows_file_reference(str(destination), str(tmp_path), access=('write',))
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    with pytest.raises(RuntimeFailure) as stopped:
        FileRuntimeV6().execute(
            'file.copy', 'official.file.copy',
            _args(
                'official.file.copy', source=source_ref,
                destination=destination_ref, conflict='overwrite',
            ),
            cancelled,
        )
    assert getattr(stopped.value, 'error_id', '') == 'runtime.cancelled'
    assert destination.read_bytes() == b'OLD'
    assert not list(tmp_path.glob('.easycode-copy-*.tmp'))


def test_encoding_json_and_nonempty_directory_errors_are_specific(tmp_path: Path) -> None:
    path = tmp_path / 'invalid.json'
    path.write_text('{bad', encoding='utf-8')
    reference = windows_file_reference(str(path), str(tmp_path), access=('read',))
    invalid_json = _run([_instruction(
        'json', 'official.file.read_json', 'file.read_json',
        _args('official.file.read_json', file=reference),
    )])
    assert invalid_json['error_id'] == 'file.json_invalid'

    bad_encoding = _run([_instruction(
        'encoding', 'official.file.read_text', 'file.read_text',
        _args('official.file.read_text', file=reference, encoding='utf-32'),
    )])
    assert bad_encoding['error_id'] == 'file.encoding_unsupported'

    directory = tmp_path / 'nonempty'
    directory.mkdir()
    (directory / 'item').write_text('x', encoding='utf-8')
    directory_ref = windows_directory_reference(
        str(directory), str(tmp_path), access=('delete_empty',),
    )
    nonempty = _run([_instruction(
        'delete', 'official.directory.delete_empty', 'directory.delete',
        _args('official.directory.delete_empty', directory=directory_ref),
    )])
    assert nonempty['error_id'] == 'file.directory_not_empty'
