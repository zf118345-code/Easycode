from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.vnext.program_repository import ProgramConflictError, ProgramDocumentRepository
from core.vnext.program_types import (
    AssignmentStatement,
    EntityReferenceValue,
    IntValue,
    LocalAssignmentTarget,
    ProjectVariableReferenceValue,
    create_program_document,
)
from core.vnext.project_variable_service_v6 import (
    ProjectVariableReferencedError,
    ProjectVariableRequestError,
    ProjectVariableServiceV6,
)
from core.vnext.project_variables_v6 import (
    ProjectVariableDefinition,
    ProjectVariableRegistry,
)
from core.vnext.workspace_context import VNextWorkspaceContext


def _service(tmp_path):
    project = tmp_path / 'project'
    (project / 'program' / 'functions').mkdir(parents=True)
    (project / 'program' / 'variables.json').write_text(
        json.dumps({'schema_version': 1, 'variables': []}, ensure_ascii=False),
        encoding='utf-8',
    )
    (project / 'player').mkdir()
    (project / 'player' / 'form.json').write_text(
        json.dumps({'schema_version': 3, 'title': '脚本运行器', 'pages': []}),
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
    return project, ProjectVariableServiceV6(context), workspace


def _create(service, workspace, revision, *, name='副本列表', value_type='string', value='经验副本'):
    return service.create(
        workspace.workspace_id,
        workspace.generation,
        expected_revision=revision,
        display_name=name,
        value_type=value_type,
        default_value={'value_id': 'client_value', 'kind': value_type, 'value': value},
        description='本次运行要执行的副本',
    )


def test_project_variable_registry_is_strict_and_rejects_dynamic_defaults() -> None:
    with pytest.raises(ValidationError, match='static typed value'):
        ProjectVariableDefinition(
            variable_id='variable_test',
            display_name='错误默认值',
            value_type='string',
            default_value=ProjectVariableReferenceValue(
                value_id='value_ref',
                variable_id='variable_other',
                value_type='string',
            ),
        )

    with pytest.raises(ValidationError, match='static typed value'):
        ProjectVariableDefinition(
            variable_id='variable_sample',
            display_name='运行图片样本',
            value_type='image_sample',
            default_value=EntityReferenceValue(
                value_id='value_sample',
                reference_id='sample_runtime_only',
                reference_type='image_sample',
            ),
        )

    with pytest.raises(ValidationError, match='duplicate project-variable name'):
        ProjectVariableRegistry(variables=(
            ProjectVariableDefinition(
                variable_id='variable_a', display_name='次数', value_type='int64',
                default_value=IntValue(value_id='value_a', value=1),
            ),
            ProjectVariableDefinition(
                variable_id='variable_b', display_name='次数', value_type='int64',
                default_value=IntValue(value_id='value_b', value=2),
            ),
        ))

    with pytest.raises(ValidationError, match='static typed value'):
        ProjectVariableDefinition(
            variable_id='variable_frame',
            display_name='运行帧',
            value_type='frame_ref',
            default_value=EntityReferenceValue(
                value_id='value_frame',
                reference_id='frame_runtime_only',
                reference_type='frame_ref',
            ),
        )

    with pytest.raises(ValidationError, match='unsupported project-variable constraint'):
        ProjectVariableDefinition(
            variable_id='variable_unknown_constraint',
            display_name='错误约束',
            value_type='int64',
            default_value=IntValue(value_id='value_constraint', value=1),
            constraints={'magic': True},
        )

    with pytest.raises(ValidationError, match='positive number'):
        ProjectVariableDefinition(
            variable_id='variable_bad_step',
            display_name='错误步进',
            value_type='int64',
            default_value=IntValue(value_id='value_bad_step', value=1),
            constraints={'step': 0},
        )


def test_project_variable_crud_preserves_root_value_identity_and_revision(tmp_path) -> None:
    _project, service, workspace = _service(tmp_path)
    empty = service.load(workspace.workspace_id, workspace.generation)
    created = _create(service, workspace, empty['revision'])
    variable = created['variables'][0]
    assert variable['display_name'] == '副本列表'
    root_value_id = variable['default_value']['value_id']
    assert root_value_id == 'client_value'

    updated = service.update(
        workspace.workspace_id,
        workspace.generation,
        variable['variable_id'],
        expected_revision=created['revision'],
        changes={
            'display_name': '每日副本',
            'default_value': {'value_id': 'throw_away', 'kind': 'string', 'value': '金币副本'},
        },
    )
    assert updated['variables'][0]['display_name'] == '每日副本'
    assert updated['variables'][0]['default_value'] == {
        'value_id': root_value_id, 'kind': 'string', 'value': '金币副本',
    }

    with pytest.raises(ProgramConflictError):
        service.delete(
            workspace.workspace_id,
            workspace.generation,
            variable['variable_id'],
            expected_revision=created['revision'],
        )

    deleted = service.delete(
        workspace.workspace_id,
        workspace.generation,
        variable['variable_id'],
        expected_revision=updated['revision'],
    )
    assert deleted['variables'] == []


def test_project_variable_constraints_and_types_are_enforced(tmp_path) -> None:
    _project, service, workspace = _service(tmp_path)
    empty = service.load(workspace.workspace_id, workspace.generation)
    with pytest.raises(ProjectVariableRequestError, match='not assignable'):
        service.create(
            workspace.workspace_id,
            workspace.generation,
            expected_revision=empty['revision'],
            display_name='次数',
            value_type='int64',
            default_value={'value_id': 'value_wrong', 'kind': 'string', 'value': '1'},
        )

    with pytest.raises(ValidationError, match='below constraint minimum'):
        ProjectVariableDefinition(
            variable_id='variable_limit',
            display_name='次数',
            value_type='int64',
            default_value=IntValue(value_id='value_limit', value=0),
            constraints={'minimum': 1},
        )


def test_project_variable_references_block_delete_and_type_change(tmp_path) -> None:
    project, service, workspace = _service(tmp_path)
    empty = service.load(workspace.workspace_id, workspace.generation)
    created = _create(service, workspace, empty['revision'])
    variable = created['variables'][0]

    document = create_program_document(
        '主程序', function_id='function_main', document_id='document_main',
    )
    document = document.model_copy(update={'function': document.function.model_copy(update={
        'statements': (AssignmentStatement(
            statement_id='statement_use_variable',
            target=LocalAssignmentTarget(
                symbol_id='symbol_copy', display_name='副本', value_type='string',
            ),
            value=ProjectVariableReferenceValue(
                value_id='value_variable_ref',
                variable_id=variable['variable_id'],
                value_type='string',
            ),
        ),),
    })})
    ProgramDocumentRepository(project).create(document)

    references = service.references(
        workspace.workspace_id, workspace.generation, variable['variable_id'],
    )
    assert references[0]['kind'] == 'program_value'
    assert references[0]['statement_id'] == 'statement_use_variable'

    with pytest.raises(ProjectVariableReferencedError) as deleted:
        service.delete(
            workspace.workspace_id,
            workspace.generation,
            variable['variable_id'],
            expected_revision=created['revision'],
        )
    assert deleted.value.references == references

    with pytest.raises(ProjectVariableReferencedError):
        service.update(
            workspace.workspace_id,
            workspace.generation,
            variable['variable_id'],
            expected_revision=created['revision'],
            changes={
                'value_type': 'int64',
                'default_value': {'value_id': 'value_new', 'kind': 'int64', 'value': 1},
            },
        )


def test_project_variable_player_binding_is_a_real_reference(tmp_path) -> None:
    project, service, workspace = _service(tmp_path)
    empty = service.load(workspace.workspace_id, workspace.generation)
    created = _create(service, workspace, empty['revision'])
    variable_id = created['variables'][0]['variable_id']
    (project / 'player' / 'form.json').write_text(json.dumps({
        'schema_version': 3,
        'pages': [{
            'page_id': 'main',
            'title': '设置',
            'controls': [{
                'control_id': 'control_1',
                'type': 'text',
                'label': '副本列表',
                'source_type': 'string',
                'type_fingerprint': 'sha256:test-only-reference-scan',
                'binding': {'kind': 'project_variable', 'variable_id': variable_id},
            }],
        }],
    }), encoding='utf-8')

    references = service.references(workspace.workspace_id, workspace.generation, variable_id)
    assert references == [{
        'kind': 'data',
        'path': (project / 'player' / 'form.json').as_posix(),
        'location': '$.pages[0].controls[0].binding',
    }]
