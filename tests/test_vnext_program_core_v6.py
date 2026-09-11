from __future__ import annotations

import os

import pytest
from pydantic import ValidationError
import core.vnext.program_repository as program_repository_module

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_commands import (
    ProgramCommandError,
    ProgramReferenceError,
    StatementLocation,
    copy_statement,
    delete_statements,
    delete_statement,
    insert_call,
    move_statement,
    move_statements,
    paste_statements,
    repair_missing_call_arguments,
    set_step_label,
    update_call_argument,
)
from core.vnext.program_compiler import compile_program_document
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
    LOG_OUTPUT_LEVEL_PARAMETER_ID,
    WAIT_DURATION_FUNCTION_ID,
    WAIT_DURATION_PARAMETER_ID,
    FunctionContract,
    FunctionContractRegistry,
    minimal_function_registry,
)
from core.vnext.program_repository import (
    ProgramConflictError,
    ProgramDocumentCorruptError,
    ProgramDocumentRepository,
    ProgramRepositoryError,
)
from core.vnext.program_serialization import canonical_json_bytes
from core.vnext.program_types import (
    BoolValue,
    CallStatement,
    DurationValue,
    IfStatement,
    ProgramDocument,
    ProgramFunction,
    ResultBinding,
    StringValue,
    SymbolReferenceValue,
    create_program_document,
    new_stable_id,
)


def _configured_program() -> tuple[ProgramDocument, str, str]:
    registry = minimal_function_registry()
    document = create_program_document('主程序', function_id='func_main', document_id='doc_main')
    inserted_log = insert_call(document, registry, LOG_OUTPUT_FUNCTION_ID)
    log_value_id = inserted_log.document.function.statements[0].arguments[
        LOG_OUTPUT_CONTENT_PARAMETER_ID
    ].value_id
    document = update_call_argument(
        inserted_log.document,
        registry,
        inserted_log.selected_statement_id,
        LOG_OUTPUT_CONTENT_PARAMETER_ID,
        StringValue(value_id=new_stable_id('value'), value='开始'),
    ).document
    inserted_wait = insert_call(document, registry, WAIT_DURATION_FUNCTION_ID)
    document = update_call_argument(
        inserted_wait.document,
        registry,
        inserted_wait.selected_statement_id,
        WAIT_DURATION_PARAMETER_ID,
        DurationValue(value_id=new_stable_id('value'), milliseconds=1),
    ).document
    assert document.function.statements[0].arguments[LOG_OUTPUT_CONTENT_PARAMETER_ID].value_id == log_value_id
    return document, inserted_log.selected_statement_id, inserted_wait.selected_statement_id


def test_repository_parse_cache_observes_external_atomic_replacement(tmp_path):
    repository = ProgramDocumentRepository(tmp_path)
    original = create_program_document('原名称', function_id='func_cache', document_id='doc_cache')
    repository.create(original)
    assert repository.load('func_cache').document.function.display_name == '原名称'

    changed = original.model_copy(update={
        'function': original.function.model_copy(update={'display_name': '外部修改后的名称'}),
    })
    path = repository.path_for('func_cache')
    replacement = path.with_suffix('.replacement')
    replacement.write_bytes(canonical_json_bytes(changed))
    os.replace(replacement, path)

    assert repository.load('func_cache').document.function.display_name == '外部修改后的名称'


@pytest.mark.parametrize('function_id', ['../escape', '.hidden', 'C:drive', 'bad/name', ''])
def test_repository_path_guard_rejects_non_stable_ids(tmp_path, function_id):
    with pytest.raises(ProgramRepositoryError, match='invalid function ID'):
        ProgramDocumentRepository(tmp_path).path_for(function_id)


def test_program_document_is_strict_and_canonical_json_is_deterministic():
    first = create_program_document('主程序', function_id='func_main', document_id='doc_main')
    second = ProgramDocument.model_validate({
        'function': {
            'return_type': 'null',
            'statements': [],
            'display_name': '主程序',
            'parameters': [],
            'function_id': 'func_main',
        },
        'document_id': 'doc_main',
        'schema_version': 1,
    })
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert b'\r\n' not in canonical_json_bytes(first)

    with pytest.raises(ValidationError):
        DurationValue.model_validate({'value_id': 'value_duration', 'milliseconds': '200'})

    with pytest.raises(ValidationError, match='duplicate stable ID'):
        ProgramDocument.model_validate({
            'schema_version': 1,
            'document_id': 'doc_main',
            'function': {
                'function_id': 'func_main',
                'display_name': '主程序',
                'parameters': [],
                'return_type': 'null',
                'statements': [{
                    'statement_id': 'stmt_same',
                    'kind': 'if',
                    'condition': {'value_id': 'value_same', 'kind': 'bool', 'value': True},
                    'then_statements': [{
                        'statement_id': 'stmt_same',
                        'kind': 'call',
                        'function_id': LOG_OUTPUT_FUNCTION_ID,
                        'arguments': {},
                    }],
                }],
            },
        })


def test_commands_insert_update_move_copy_and_delete_preserve_id_rules():
    document, log_statement_id, wait_statement_id = _configured_program()
    original_wait = next(
        item for item in document.function.statements if item.statement_id == wait_statement_id
    )
    original_wait_value_id = original_wait.arguments[WAIT_DURATION_PARAMETER_ID].value_id

    moved = move_statement(
        document,
        wait_statement_id,
        StatementLocation(before_statement_id=log_statement_id),
    )
    assert [item.statement_id for item in moved.document.function.statements] == [
        wait_statement_id,
        log_statement_id,
    ]
    assert moved.document.function.statements[0].arguments[
        WAIT_DURATION_PARAMETER_ID
    ].value_id == original_wait_value_id

    copied = copy_statement(moved.document, wait_statement_id, StatementLocation())
    copied_statement = copied.document.function.statements[-1]
    assert copied_statement.statement_id != wait_statement_id
    assert copied_statement.arguments[WAIT_DURATION_PARAMETER_ID].value_id != original_wait_value_id
    assert set(copied.created_ids).isdisjoint({wait_statement_id, original_wait_value_id})

    deleted = delete_statement(copied.document, log_statement_id)
    assert all(item.statement_id != log_statement_id for item in deleted.document.function.statements)


def test_repair_missing_call_arguments_uses_contract_defaults_and_preserves_existing_ids():
    registry = official_function_registry_v6
    inserted = insert_call(
        create_program_document('主程序', function_id='func_repair', document_id='doc_repair'),
        registry,
        'official.input.click',
    )
    raw = inserted.document.model_dump(mode='json')
    arguments = raw['function']['statements'][0]['arguments']
    position_id = arguments['official.input.click.parameter.position']['value_id']
    del arguments['official.input.click.parameter.button']
    del arguments['official.input.click.parameter.count']
    del arguments['official.input.click.parameter.hold']
    del arguments['official.input.click.parameter.interval']
    incomplete = ProgramDocument.model_validate(raw)

    repaired = repair_missing_call_arguments(
        incomplete,
        registry,
        inserted.selected_statement_id,
    )
    values = repaired.document.function.statements[0].arguments

    assert values['official.input.click.parameter.position'].value_id == position_id
    assert values['official.input.click.parameter.button'].value == 'primary'
    assert values['official.input.click.parameter.count'].value == 1
    assert values['official.input.click.parameter.hold'].milliseconds == 0
    assert values['official.input.click.parameter.interval'].milliseconds == 80
    assert len(repaired.created_ids) == 4
    assert position_id not in repaired.created_ids
    with pytest.raises(ProgramCommandError, match='no missing parameters'):
        repair_missing_call_arguments(repaired.document, registry, inserted.selected_statement_id)


def test_delete_and_move_reject_dangling_or_out_of_scope_symbol_references():
    producer_contract = FunctionContract(
        function_id='test_producer',
        qualified_name='测试.生成文本',
        opcode='test.producer',
        parameters=(),
        return_type='string',
    )
    registry = FunctionContractRegistry((*minimal_function_registry().values(), producer_contract))
    producer = CallStatement(
        statement_id='stmt_producer',
        function_id='test_producer',
        result_binding=ResultBinding(
            symbol_id='symbol_result',
            display_name='结果',
            value_type='string',
        ),
    )
    consumer = CallStatement(
        statement_id='stmt_consumer',
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={
            LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
                value_id='value_reference',
                symbol_id='symbol_result',
                value_type='string',
            ),
        },
    )
    branch = IfStatement(
        statement_id='stmt_if',
        condition=BoolValue(value_id='value_condition', value=True),
    )
    document = ProgramDocument(
        document_id='doc_main',
        function=ProgramFunction(
            function_id='func_main',
            display_name='主程序',
            statements=(producer, consumer, branch),
        ),
    )
    assert compile_program_document(document, registry)['valid'] is True

    with pytest.raises(ProgramReferenceError, match='局部变量引用不存在'):
        delete_statement(document, 'stmt_producer')
    with pytest.raises(ProgramReferenceError, match='局部变量引用不存在'):
        move_statement(
            document,
            'stmt_producer',
            StatementLocation(parent_statement_id='stmt_if', block='then'),
        )


def test_group_copy_move_and_delete_preserve_internal_reference_semantics():
    producer_contract = FunctionContract(
        function_id='test_producer',
        qualified_name='测试.生成文本',
        opcode='test.producer',
        parameters=(),
        return_type='string',
    )
    registry = FunctionContractRegistry((*minimal_function_registry().values(), producer_contract))
    producer = CallStatement(
        statement_id='stmt_producer',
        function_id='test_producer',
        result_binding=ResultBinding(
            symbol_id='symbol_result', display_name='结果', value_type='string',
        ),
    )
    consumer = CallStatement(
        statement_id='stmt_consumer',
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: SymbolReferenceValue(
            value_id='value_reference', symbol_id='symbol_result', value_type='string',
        )},
    )
    branch = IfStatement(
        statement_id='stmt_if',
        condition=BoolValue(value_id='value_condition', value=True),
    )
    document = ProgramDocument(
        document_id='doc_group',
        function=ProgramFunction(
            function_id='func_group', display_name='批量编辑',
            statements=(producer, consumer, branch),
        ),
    )

    pasted = paste_statements(
        document,
        [producer.model_dump(mode='json'), consumer.model_dump(mode='json')],
        StatementLocation(),
        registry=registry,
    )
    copied_producer, copied_consumer = pasted.document.function.statements[-2:]
    assert copied_producer.statement_id != producer.statement_id
    assert copied_consumer.statement_id != consumer.statement_id
    assert copied_producer.result_binding is not None
    copied_reference = copied_consumer.arguments[LOG_OUTPUT_CONTENT_PARAMETER_ID]
    assert isinstance(copied_reference, SymbolReferenceValue)
    assert copied_reference.symbol_id == copied_producer.result_binding.symbol_id
    assert copied_reference.symbol_id != 'symbol_result'

    target_document = ProgramDocument(
        document_id='doc_group_target',
        function=ProgramFunction(function_id='func_group_target', display_name='目标函数'),
    )
    cross_function = paste_statements(
        target_document,
        [producer.model_dump(mode='json'), consumer.model_dump(mode='json')],
        StatementLocation(),
        registry=registry,
    )
    target_producer, target_consumer = cross_function.document.function.statements
    assert target_producer.result_binding is not None
    target_reference = target_consumer.arguments[LOG_OUTPUT_CONTENT_PARAMETER_ID]
    assert isinstance(target_reference, SymbolReferenceValue)
    assert target_reference.symbol_id == target_producer.result_binding.symbol_id
    with pytest.raises(ProgramReferenceError, match='局部变量引用不存在'):
        paste_statements(
            target_document,
            [consumer.model_dump(mode='json')],
            StatementLocation(),
            registry=registry,
        )

    moved = move_statements(
        document,
        ['stmt_producer', 'stmt_consumer'],
        StatementLocation(parent_statement_id='stmt_if', block='then'),
    )
    moved_branch = moved.document.function.statements[0]
    assert isinstance(moved_branch, IfStatement)
    assert [item.statement_id for item in moved_branch.then_statements] == [
        'stmt_producer', 'stmt_consumer',
    ]

    deleted = delete_statements(document, ['stmt_producer', 'stmt_consumer'])
    assert [item.statement_id for item in deleted.document.function.statements] == ['stmt_if']


@pytest.mark.parametrize(('anchor', 'before', 'expected'), [
    ('a', 'b', 'acdebf'),
    ('b', 'c', 'abcdef'),
    ('c', 'd', 'abcdef'),
    ('d', 'e', 'abcdef'),
    ('e', 'f', 'abcdef'),
    ('f', None, 'abfcde'),
])
def test_deferred_cut_paste_uses_after_anchor_semantics(anchor, before, expected):
    del anchor  # The UI resolves an after-anchor to this stable before ID.
    document = ProgramDocument(
        document_id='doc_cut',
        function=ProgramFunction(
            function_id='func_cut', display_name='剪切顺序',
            statements=tuple(CallStatement(
                statement_id=letter, function_id=LOG_OUTPUT_FUNCTION_ID,
            ) for letter in 'abcdef'),
        ),
    )
    moved = move_statements(
        document,
        ['c', 'd', 'e'],
        StatementLocation(before_statement_id=before),
    )
    assert ''.join(item.statement_id for item in moved.document.function.statements) == expected


def test_nested_if_compiles_structurally_with_stable_parameter_keys():
    registry = minimal_function_registry()
    then_call = CallStatement(
        statement_id='stmt_then_log',
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={
            LOG_OUTPUT_CONTENT_PARAMETER_ID: StringValue(value_id='value_then_text', value='命中'),
        },
    )
    otherwise_call = CallStatement(
        statement_id='stmt_else_log',
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={
            LOG_OUTPUT_CONTENT_PARAMETER_ID: StringValue(value_id='value_else_text', value='未命中'),
        },
    )
    document = ProgramDocument(
        document_id='doc_main',
        function=ProgramFunction(
            function_id='func_main',
            display_name='主程序',
            statements=(IfStatement(
                statement_id='stmt_if',
                condition=BoolValue(value_id='value_condition', value=True),
                then_statements=(then_call,),
                otherwise_statements=(otherwise_call,),
            ),),
        ),
    )
    first = compile_program_document(document, registry)
    second = compile_program_document(document, registry)
    assert first['valid'] is True
    assert first['ecir_revision'] == second['ecir_revision']
    instruction = first['ecir']['functions'][0]['instructions'][0]
    assert instruction['opcode'] == 'control.if'
    assert instruction['arguments']['then'][0]['opcode'] == 'log.write'
    assert instruction['arguments']['otherwise'][0]['opcode'] == 'log.write'

    assert instruction['arguments']['then'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID] == '命中'
    assert instruction['arguments']['otherwise'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID] == '未命中'


def test_unset_can_be_saved_but_blocks_compile(tmp_path):
    registry = minimal_function_registry()
    inserted = insert_call(
        create_program_document('主程序', function_id='func_main', document_id='doc_main'),
        registry,
        LOG_OUTPUT_FUNCTION_ID,
    )
    repository = ProgramDocumentRepository(tmp_path)
    snapshot = repository.create(inserted.document)
    assert repository.load('func_main').revision == snapshot.revision

    compiled = compile_program_document(inserted.document, registry)
    assert compiled['valid'] is False
    assert compiled['diagnostics'][0]['code'] == 'PGM-VALUE-001'
    assert compiled['diagnostics'][0]['value_id']


def test_step_label_is_preserved_as_non_executable_debug_context() -> None:
    document, log_statement_id, _wait_statement_id = _configured_program()
    labelled = set_step_label(document, log_statement_id, '登录阶段').document

    compiled = compile_program_document(labelled, minimal_function_registry())

    assert compiled['valid'] is True
    assert compiled['ecir']['debug_map']['statements'][log_statement_id]['step_label'] == '登录阶段'


def test_project_data_directory_is_inspectable_and_compiles() -> None:
    inserted = insert_call(
        create_program_document(
            '主程序', function_id='func_planned', document_id='doc_planned'
        ),
        official_function_registry_v6,
        'official.project.data_directory',
    )
    compiled = compile_program_document(
        inserted.document,
        official_function_registry_v6,
    )
    assert compiled['valid'] is True
    instruction = compiled['ecir']['functions'][0]['instructions'][0]
    assert instruction['opcode'] == 'project.data_directory'


def test_repository_detects_conflict_and_atomic_failure_preserves_old_bytes(tmp_path, monkeypatch):
    repository = ProgramDocumentRepository(tmp_path)
    document, _, _ = _configured_program()
    created = repository.create(document)
    baseline = created.path.read_bytes()

    external = baseline.replace('开始'.encode(), '外部'.encode())
    created.path.write_bytes(external)
    with pytest.raises(ProgramConflictError) as conflict:
        repository.save(document, expected_revision=created.revision)
    assert conflict.value.actual_revision != created.revision
    assert created.path.read_bytes() == external

    current = repository.load('func_main')
    updated = update_call_argument(
        current.document,
        minimal_function_registry(),
        current.document.function.statements[0].statement_id,
        LOG_OUTPUT_CONTENT_PARAMETER_ID,
        StringValue(value_id=new_stable_id('value'), value='新内容'),
    ).document

    def fail_replace(_source, _destination):
        raise OSError('injected atomic replace failure')

    monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError, match='injected'):
        repository.save(updated, expected_revision=current.revision)
    assert created.path.read_bytes() == external
    assert not list(created.path.parent.glob('*.tmp'))


def test_repository_refuses_corrupt_or_mismatched_document(tmp_path):
    repository = ProgramDocumentRepository(tmp_path)
    path = repository.path_for('func_main')
    path.parent.mkdir(parents=True)
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ProgramDocumentCorruptError):
        repository.load('func_main')

    path.write_text(
        canonical_json_bytes(create_program_document(
            '其他函数',
            function_id='func_other',
            document_id='doc_other',
        )).decode('utf-8'),
        encoding='utf-8',
    )
    with pytest.raises(ProgramDocumentCorruptError, match='does not match'):
        repository.load('func_main')


def test_repository_keeps_valid_history_and_explicitly_restores_corrupt_source(tmp_path):
    repository = ProgramDocumentRepository(tmp_path)
    document, _, _ = _configured_program()
    created = repository.create(document)
    changed_raw = document.model_dump(mode='json')
    changed_raw['function']['display_name'] = '修改后的主程序'
    changed = ProgramDocument.model_validate(changed_raw)
    saved = repository.save(changed, expected_revision=created.revision)

    history = repository.list_history('func_main')
    assert len(history) == 1
    assert history[0].document.function.display_name == '主程序'
    assert history[0].revision == created.revision

    saved.path.write_text('{broken', encoding='utf-8')
    broken_revision = f'sha256:{__import__("hashlib").sha256(b"{broken").hexdigest()}'
    restored = repository.restore_history(
        'func_main', history[0].history_id, expected_revision=broken_revision,
    )
    assert restored.document.function.display_name == '主程序'
    assert repository.load('func_main').revision == restored.revision
    preserved = list((tmp_path / '.easycode' / 'recovery' / 'program' / 'functions' / 'func_main').glob('*.corrupt.json'))
    assert len(preserved) == 1
    assert preserved[0].read_text(encoding='utf-8') == '{broken'


def test_repository_restore_refuses_stale_current_revision(tmp_path):
    repository = ProgramDocumentRepository(tmp_path)
    document, _, _ = _configured_program()
    created = repository.create(document)
    raw = document.model_dump(mode='json')
    raw['function']['display_name'] = '第二版'
    second = repository.save(ProgramDocument.model_validate(raw), expected_revision=created.revision)
    candidate = repository.list_history('func_main')[0]

    with pytest.raises(ProgramConflictError):
        repository.restore_history(
            'func_main', candidate.history_id, expected_revision=created.revision,
        )
    assert repository.load('func_main').revision == second.revision


@pytest.mark.parametrize('failure', [PermissionError('permission denied'), OSError(28, 'disk full')])
def test_history_write_failure_never_changes_the_editable_document(tmp_path, monkeypatch, failure):
    repository = ProgramDocumentRepository(tmp_path)
    document, _, _ = _configured_program()
    created = repository.create(document)
    baseline = created.path.read_bytes()
    raw = document.model_dump(mode='json')
    raw['function']['display_name'] = '不能落盘的版本'

    def fail_write(_path, _content):
        raise failure

    monkeypatch.setattr(program_repository_module, '_write_temp', fail_write)
    with pytest.raises(type(failure)):
        repository.save(ProgramDocument.model_validate(raw), expected_revision=created.revision)
    assert created.path.read_bytes() == baseline


def test_command_rejects_unknown_function_and_wrong_parameter_type():
    registry = minimal_function_registry()
    document = create_program_document('主程序')
    with pytest.raises(ProgramCommandError, match='function contract not found'):
        insert_call(document, registry, 'missing_function')

    wait = insert_call(document, registry, WAIT_DURATION_FUNCTION_ID)
    with pytest.raises(ProgramCommandError, match='参数需要 duration'):
        update_call_argument(
            wait.document,
            registry,
            wait.selected_statement_id,
            WAIT_DURATION_PARAMETER_ID,
            StringValue(value_id=new_stable_id('value'), value='2秒'),
        )

    log = insert_call(document, registry, LOG_OUTPUT_FUNCTION_ID)
    updated_enum = update_call_argument(
        log.document,
        registry,
        log.selected_statement_id,
        LOG_OUTPUT_LEVEL_PARAMETER_ID,
        StringValue(value_id=new_stable_id('value'), value='warning'),
    )
    assert updated_enum.document.function.statements[0].arguments[
        LOG_OUTPUT_LEVEL_PARAMETER_ID
    ].value == 'warning'

    with pytest.raises(ProgramCommandError, match='参数需要 duration'):
        insert_call(
            document,
            registry,
            WAIT_DURATION_FUNCTION_ID,
            arguments={
                WAIT_DURATION_PARAMETER_ID: StringValue(
                    value_id=new_stable_id('value'),
                    value='2秒',
                ),
            },
        )


def test_program_core_accepts_frozen_official_registry_without_source_adapter():
    inserted = insert_call(
        create_program_document('主程序', function_id='func_main', document_id='doc_main'),
        official_function_registry_v6,
        LOG_OUTPUT_FUNCTION_ID,
    )
    configured = update_call_argument(
        inserted.document,
        official_function_registry_v6,
        inserted.selected_statement_id,
        LOG_OUTPUT_CONTENT_PARAMETER_ID,
        StringValue(value_id=new_stable_id('value'), value='官方契约'),
    ).document
    result = compile_program_document(configured, official_function_registry_v6)
    assert result['valid'] is True
    instruction = result['ecir']['functions'][0]['instructions'][0]
    assert instruction['function_id'] == 'official.log.output'
    assert instruction['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID] == '官方契约'
    assert instruction['parameter_ids'][LOG_OUTPUT_CONTENT_PARAMETER_ID] == LOG_OUTPUT_CONTENT_PARAMETER_ID
    assert instruction['result_type'] == 'unit'
    assert 'result_type_id' not in instruction
