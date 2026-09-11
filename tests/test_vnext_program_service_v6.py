from __future__ import annotations

import json

import pytest

from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
    minimal_function_registry,
)
from core.vnext.program_repository import ProgramConflictError, ProgramDocumentRepository
from core.vnext.program_service_v6 import ProgramCommandRequestError, ProgramServiceV6
from core.vnext.program_types import create_program_document
from core.vnext.workspace_context import VNextWorkspaceContext


def _service(tmp_path):
    project = tmp_path / 'project'
    (project / 'program' / 'functions').mkdir(parents=True)
    (project / 'program' / 'variables.json').write_text(
        json.dumps({'schema_version': 1, 'variables': []}),
        encoding='utf-8',
    )
    context = VNextWorkspaceContext()
    workspace = context.activate(
        workspace_id='workspace_test',
        project_id='project_test',
        project_name='test',
        project_path=str(project),
        read_only=False,
    )
    document = create_program_document('主程序', function_id='function_main', document_id='document_main')
    snapshot = ProgramDocumentRepository(project).create(document)
    return ProgramServiceV6(context, minimal_function_registry()), workspace, snapshot


def test_program_service_applies_typed_commands_and_supports_session_undo_redo(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)

    inserted = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        initial.revision,
        {'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID, 'location': {'block': 'root'}},
    )
    statement = inserted['document']['function']['statements'][0]
    value_id = statement['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]['value_id']
    assert statement['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]['kind'] == 'unset'

    configured = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        inserted['revision'],
        {
            'kind': 'update_argument',
            'statement_id': statement['statement_id'],
            'parameter_id': LOG_OUTPUT_CONTENT_PARAMETER_ID,
            'value': {'value_id': 'temporary_client_id', 'kind': 'string', 'value': '你好'},
        },
    )
    configured_value = configured['document']['function']['statements'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]
    assert configured_value == {'value_id': value_id, 'kind': 'string', 'value': '你好'}

    undone = service.undo(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        configured['revision'],
    )
    assert undone['document']['function']['statements'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]['kind'] == 'unset'
    assert undone['can_redo'] is True

    redone = service.redo(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        undone['revision'],
    )
    assert redone['document']['function']['statements'][0]['arguments'][LOG_OUTPUT_CONTENT_PARAMETER_ID]['value'] == '你好'


def test_program_service_rejects_stale_revision_without_losing_current_document(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)
    inserted = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        initial.revision,
        {'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID},
    )

    with pytest.raises(ProgramConflictError):
        service.apply_command(
            workspace.workspace_id,
            workspace.generation,
            'function_main',
            initial.revision,
            {'kind': 'delete_statement', 'statement_id': inserted['selected_statement_id']},
        )

    loaded = service.load(workspace.workspace_id, workspace.generation, 'function_main')
    assert loaded['revision'] == inserted['revision']
    assert len(loaded['document']['function']['statements']) == 1


def test_program_service_rejects_unknown_command_kind(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)

    with pytest.raises(ProgramCommandRequestError, match='不支持的结构命令'):
        service.apply_command(
            workspace.workspace_id,
            workspace.generation,
            'function_main',
            initial.revision,
            {'kind': 'magic'},
        )


def test_program_service_extract_is_undoable_across_both_documents(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)
    inserted = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        initial.revision,
        {
            'kind': 'insert_assignment',
            'target': {
                'kind': 'local', 'symbol_id': 'symbol_value',
                'display_name': '临时值', 'value_type': 'int64', 'declare': True,
            },
            'value': {'value_id': 'value_literal', 'kind': 'int64', 'value': 7},
        },
    )

    extracted = service.extract_statements(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        inserted['revision'],
        [inserted['selected_statement_id']],
        '准备临时值',
    )
    extracted_id = extracted['extracted_program']['function_id']
    assert extracted['document']['function']['statements'][0]['kind'] == 'call'
    assert service.load(workspace.workspace_id, workspace.generation, extracted_id)
    assert service.load(workspace.workspace_id, workspace.generation, 'function_main')['can_undo'] is True

    undone = service.undo(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        extracted['revision'],
    )
    assert undone['document']['function']['statements'][0]['kind'] == 'assignment'
    with pytest.raises(Exception):
        service.load(workspace.workspace_id, workspace.generation, extracted_id)

    redone = service.redo(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        undone['revision'],
    )
    assert redone['document']['function']['statements'][0]['kind'] == 'call'
    assert service.load(workspace.workspace_id, workspace.generation, extracted_id)


def test_program_value_catalog_accepts_only_explicit_stable_selector_scope(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)
    inserted = service.apply_command(
        workspace.workspace_id, workspace.generation, 'function_main', initial.revision,
        {'kind': 'insert_call', 'function_id': LOG_OUTPUT_FUNCTION_ID},
    )
    statement_id = inserted['selected_statement_id']
    catalog = service.value_catalog(
        workspace.workspace_id, workspace.generation, 'function_main', statement_id, 'int64',
        [{
            'symbol_id': 'selector_item', 'display_name': '当前项', 'value_type': 'int64',
        }],
    )
    source = next(item for item in catalog['sources'] if item['source_id'] == 'selector_item')
    assert source == {
        'source': 'local', 'source_id': 'selector_item',
        'display_name': '当前项', 'value_type': 'int64', 'narrowed_type': '',
    }
    with pytest.raises(ProgramCommandRequestError, match='不完整'):
        service.value_catalog(
            workspace.workspace_id, workspace.generation, 'function_main', statement_id, 'int64',
            [{'symbol_id': 'selector_item', 'display_name': '', 'value_type': 'int64'}],
        )


def test_program_snapshot_projects_only_referenced_operation_names(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)
    operation_id = 'core.number_max.v1'
    result = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        initial.revision,
        {
            'kind': 'insert_assignment',
            'target': {
                'kind': 'local', 'symbol_id': 'symbol_stamina',
                'display_name': '当前体力', 'value_type': 'int64', 'declare': True,
            },
            'value': {
                'value_id': 'value_max', 'kind': 'operation',
                'operation_id': operation_id, 'result_type': 'int64',
                'inputs': {
                    f'{operation_id}.input.left': {
                        'value_id': 'value_left', 'kind': 'int64', 'value': 18,
                    },
                    f'{operation_id}.input.right': {
                        'value_id': 'value_right', 'kind': 'int64', 'value': 3,
                    },
                },
            },
        },
    )

    assert result['document']['function']['statements'][0]['value']['operation_id'] == operation_id
    assert result['presentations'] == {
        'operations': {
            operation_id: {
                'display_name': '取较大值',
                'syntax_name': '数值.取较大值',
                'input_labels': {
                    f'{operation_id}.input.left': '左侧',
                    f'{operation_id}.input.right': '右侧',
                },
            },
        },
        'fields': {},
        'record_types': {},
    }


def test_program_snapshot_projects_every_field_name_for_a_record_value(tmp_path) -> None:
    service, workspace, initial = _service(tmp_path)
    fields = {
        'ocr_preprocess.field.grayscale': {
            'value_id': 'value_grayscale', 'kind': 'bool', 'value': False,
        },
        'ocr_preprocess.field.binary': {
            'value_id': 'value_binary', 'kind': 'bool', 'value': True,
        },
        'ocr_preprocess.field.threshold': {
            'value_id': 'value_threshold', 'kind': 'int64', 'value': 127,
        },
        'ocr_preprocess.field.invert': {
            'value_id': 'value_invert', 'kind': 'bool', 'value': False,
        },
    }

    result = service.apply_command(
        workspace.workspace_id,
        workspace.generation,
        'function_main',
        initial.revision,
        {
            'kind': 'insert_assignment',
            'target': {
                'kind': 'local', 'symbol_id': 'symbol_preprocess',
                'display_name': '识别预处理', 'value_type': 'ocr_preprocess', 'declare': True,
            },
            'value': {
                'value_id': 'value_preprocess', 'kind': 'record',
                'record_type': 'ocr_preprocess', 'fields': fields,
            },
        },
    )

    assert result['presentations']['record_types'] == {'ocr_preprocess': 'OCR 预处理'}
    assert result['presentations']['fields'] == {
        'ocr_preprocess.field.binary': '二值化',
        'ocr_preprocess.field.grayscale': '灰度化',
        'ocr_preprocess.field.invert': '反色',
        'ocr_preprocess.field.threshold': '阈值',
    }
