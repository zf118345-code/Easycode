from __future__ import annotations

from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.program_commands import (
    StatementLocation,
    copy_statement,
    delete_statement,
    insert_assignment,
    insert_call,
    insert_if,
    insert_if_from_call_result,
    insert_listen,
    insert_loop,
    insert_return,
    insert_target_scope,
    insert_try,
    review_dangerous_call,
    set_result_binding,
    set_step_label,
    update_assignment_target,
    update_call_argument,
)
from core.vnext.program_compiler import (
    compile_program_bundle,
    compile_program_document,
    linked_function_registry,
)
from core.vnext.program_contracts import (
    LOG_OUTPUT_CONTENT_PARAMETER_ID,
    LOG_OUTPUT_FUNCTION_ID,
    WAIT_DURATION_FUNCTION_ID,
    WAIT_DURATION_PARAMETER_ID,
)
from core.vnext.program_types import (
    AssignmentStatement,
    BoolValue,
    CallStatement,
    CatchClause,
    ComparisonValue,
    ConditionGroupValue,
    DurationValue,
    EntityReferenceValue,
    IfStatement,
    IntValue,
    JsonValue,
    ListenStatement,
    ListValue,
    LocalAssignmentTarget,
    LoopBinding,
    LoopStatement,
    MapEntry,
    MapValue,
    MemberAccessValue,
    MessageEventSource,
    NullValue,
    ProgramDocument,
    ProgramFunction,
    ProgramParameter,
    ProjectVariableAssignmentTarget,
    PureOperationValue,
    RecordValue,
    ResultBinding,
    RetryPolicy,
    ReturnStatement,
    StringValue,
    SymbolReferenceValue,
    TargetReferenceValue,
    TargetScopeStatement,
    TryStatement,
    UnsetValue,
    create_program_document,
)
from core.vnext.program_validation import retry_review_fingerprint, validate_program_document
from core.vnext.pure_operations_v6 import (
    pure_operation_registry_hash,
    pure_operation_registry_payload,
)


def _text(value_id: str, value: str) -> StringValue:
    return StringValue(value_id=value_id, value=value)


def _log(statement_id: str, value, *, result_binding=None) -> CallStatement:
    return CallStatement(
        statement_id=statement_id,
        function_id=LOG_OUTPUT_FUNCTION_ID,
        arguments={LOG_OUTPUT_CONTENT_PARAMETER_ID: value},
        result_binding=result_binding,
    )


def _wait(statement_id: str, milliseconds: int = 1) -> CallStatement:
    return CallStatement(
        statement_id=statement_id,
        function_id=WAIT_DURATION_FUNCTION_ID,
        arguments={
            WAIT_DURATION_PARAMETER_ID: DurationValue(
                value_id=f'value_{statement_id}',
                milliseconds=milliseconds,
            ),
        },
    )


def test_complete_statement_slice_validates_and_compiles_deterministically() -> None:
    numbers = ListValue(
        value_id='value_numbers',
        item_type='int64',
        items=(
            IntValue(value_id='value_number_1', value=1),
            IntValue(value_id='value_number_2', value=2),
        ),
    )
    assignment = AssignmentStatement(
        statement_id='stmt_assign_numbers',
        target=LocalAssignmentTarget(
            symbol_id='symbol_numbers',
            display_name='数字列表',
            value_type='list<int64>',
        ),
        value=numbers,
    )
    loop = LoopStatement(
        statement_id='stmt_loop',
        mode='for_each',
        source=SymbolReferenceValue(
            value_id='value_numbers_reference',
            symbol_id='symbol_numbers',
            value_type='list<int64>',
        ),
        item_binding=LoopBinding(
            symbol_id='symbol_item',
            display_name='当前项',
            value_type='int64',
        ),
        index_binding=LoopBinding(
            symbol_id='symbol_index',
            display_name='序号',
            value_type='int64',
        ),
        body=(_log(
            'stmt_log_item',
            SymbolReferenceValue(
                value_id='value_item_reference',
                symbol_id='symbol_item',
                value_type='int64',
            ),
        ),),
    )
    condition = ConditionGroupValue(
        value_id='value_condition_group',
        operator='all',
        conditions=(
            BoolValue(value_id='value_enabled', value=True),
            ComparisonValue(
                value_id='value_compare',
                operator='lt',
                left=IntValue(value_id='value_left', value=1),
                right=IntValue(value_id='value_right', value=2),
            ),
        ),
    )
    branch = IfStatement(
        statement_id='stmt_if',
        condition=condition,
        then_statements=(_wait('stmt_if_wait'),),
    )
    target_scope = TargetScopeStatement(
        statement_id='stmt_target',
        target=TargetReferenceValue(value_id='value_target', target_id='target_emulator'),
        body=(_wait('stmt_target_wait'),),
    )
    tried = TryStatement(
        statement_id='stmt_try',
        body=(_wait('stmt_try_wait'),),
        retry_policy=RetryPolicy(
            max_retries=IntValue(value_id='value_retries', value=2),
            interval=DurationValue(value_id='value_retry_interval', milliseconds=500),
        ),
        catches=(CatchClause(
            catch_id='catch_transient',
            error_ids=('target.offline',),
            error_binding=LoopBinding(
                symbol_id='symbol_error',
                display_name='异常',
                value_type='error',
            ),
            statements=(_log('stmt_catch_log', _text('value_catch_text', '失败')),),
        ),),
        finally_statements=(_log('stmt_finally_log', _text('value_finally_text', '结束')),),
    )
    listener = ListenStatement(
        statement_id='stmt_listener',
        event_source=MessageEventSource(
            name=_text('value_message_name', '组队邀请'),
            sender=EntityReferenceValue(
                value_id='value_sender',
                reference_id='instance_leader',
                reference_type='instance_ref',
            ),
        ),
        receive_binding=LoopBinding(
            symbol_id='symbol_message',
            display_name='邀请',
            value_type='received_message',
        ),
        condition=BoolValue(value_id='value_listener_ready', value=True),
        handler_function_id='func_handle_invite',
        handler_arguments={
            'func_handle_invite.parameter.message': SymbolReferenceValue(
                value_id='value_received_message',
                symbol_id='symbol_message',
                value_type='received_message',
            ),
        },
    )
    document = ProgramDocument(
        document_id='doc_complete',
        function=ProgramFunction(
            function_id='func_main',
            display_name='主程序',
            statements=(
                assignment,
                loop,
                branch,
                target_scope,
                tried,
                listener,
                ReturnStatement(statement_id='stmt_return'),
            ),
        ),
    )
    handler = ProgramDocument(
        document_id='doc_handle_invite',
        function=ProgramFunction(
            function_id='func_handle_invite',
            display_name='处理邀请',
            parameters=(ProgramParameter(
                parameter_id='func_handle_invite.parameter.message',
                symbol_id='handler_message',
                display_name='邀请',
                value_type='received_message',
            ),),
        ),
    )
    registry = linked_function_registry(
        (document, handler), official_function_registry_v6,
    )

    assert validate_program_document(document, registry) == ()
    blocked = compile_program_bundle(
        (document, handler),
        official_function_registry_v6,
        entry_function_id='func_main',
    )
    assert blocked['valid'] is False
    assert {'PGM-TARGET-001'} <= {
        item['code'] for item in blocked['diagnostics']
    }
    executable = document.model_copy(update={
        'function': document.function.model_copy(update={
            'statements': tuple(
                item
                for item in document.function.statements
                if not isinstance(item, (TargetScopeStatement, ListenStatement))
            ),
        }),
    })
    first = compile_program_document(executable, official_function_registry_v6)
    second = compile_program_document(executable, official_function_registry_v6)
    assert first['valid'] is True
    assert first['ecir_revision'] == second['ecir_revision']
    assert first['ecir']['pure_operation_registry'] == {
        'registry_version': pure_operation_registry_payload()['registry_version'],
        'content_hash': pure_operation_registry_hash(),
    }
    instructions = first['ecir']['functions'][0]['instructions']
    assert [item['opcode'] for item in instructions] == [
        'data.assign_local',
        'control.for_each',
        'control.if',
        'control.try',
        'control.return',
    ]
    assert instructions[1]['arguments']['snapshot'] is True
    assert instructions[1]['arguments']['body'][0]['arguments'][
        LOG_OUTPUT_CONTENT_PARAMETER_ID
    ] == {'kind': 'reference', 'scope': 'local', 'symbol_id': 'symbol_item'}
    assert instructions[3]['arguments']['retry_policy']['evaluate_on_entry'] is True
    assert 'value_number_2' in first['ecir']['debug_map']['values']
    assert first['ecir']['debug_map']['symbols']['symbol_numbers'] == {
        'function_id': 'func_main',
        'symbol_id': 'symbol_numbers',
        'display_name': '数字列表',
        'value_type': 'list<int64>',
        'kind': 'local',
    }
    assert first['ecir']['debug_map']['symbols']['symbol_item']['display_name'] == '当前项'
    assert first['ecir']['debug_map']['symbols']['symbol_error']['kind'] == 'error'


def test_recursive_values_and_project_assignment_keep_typed_boundaries() -> None:
    value = RecordValue(
        value_id='value_record',
        record_type='record<settings>',
        fields={
            'settings.field.options': ListValue(
                value_id='value_options',
                item_type='string',
                items=(_text('value_option', '副本一'),),
            ),
            'settings.field.lookup': MapValue(
                value_id='value_lookup',
                key_type='string',
                entry_value_type='int64',
                entries=(MapEntry(
                    key=_text('value_key', '次数'),
                    value=IntValue(value_id='value_count', value=2),
                ),),
            ),
            'settings.field.extra': JsonValue(
                value_id='value_json',
                payload={'enabled': True, 'items': [1, 2]},
            ),
            'settings.field.calculated': PureOperationValue(
                value_id='value_operation',
                operation_id='core.number_add.v1',
                result_type='int64',
                inputs={
                    'core.number_add.v1.input.left': IntValue(
                        value_id='value_op_left', value=1,
                    ),
                    'core.number_add.v1.input.right': IntValue(
                        value_id='value_op_right', value=2,
                    ),
                },
            ),
        },
    )
    document = ProgramDocument(
        document_id='doc_project_assignment',
        function=ProgramFunction(
            function_id='func_main',
            display_name='主程序',
            statements=(AssignmentStatement(
                statement_id='stmt_project_assignment',
                target=ProjectVariableAssignmentTarget(
                    variable_id='variable_settings',
                    value_type='record<settings>',
                ),
                value=value,
            ),),
        ),
    )
    result = compile_program_document(document, official_function_registry_v6)
    assert result['valid'] is True
    instruction = result['ecir']['functions'][0]['instructions'][0]
    assert instruction['opcode'] == 'data.assign_project'
    assert instruction['arguments']['target']['variable_id'] == 'variable_settings'
    assert instruction['arguments']['value']['fields'][
        'settings.field.calculated'
    ]['operation_id'] == 'core.number_add.v1'


def test_optional_member_access_is_valid_both_as_strict_consumption_and_in_narrowed_branch() -> None:
    optional_result = ResultBinding(
        symbol_id='symbol_match',
        display_name='图片结果',
        value_type='optional<record.image_match>',
    )
    producer = CallStatement(
        statement_id='stmt_producer',
        function_id='official.image.find',
        arguments={
            'official.image.find.parameter.image': UnsetValue(
                value_id='value_image',
                expected_type='asset_ref<image>',
            ),
        },
        result_binding=optional_result,
    )
    member = MemberAccessValue(
        value_id='value_center',
        source=SymbolReferenceValue(
            value_id='value_match_reference',
            symbol_id='symbol_match',
            value_type='optional<record.image_match>',
        ),
        field_id='image_match.field.center',
        result_type='point',
    )
    unguarded = ProgramDocument(
        document_id='doc_unguarded',
        function=ProgramFunction(
            function_id='func_unguarded',
            display_name='未收窄',
            statements=(producer, _log('stmt_bad_member', member)),
        ),
    )
    assert not any(
        item.code.startswith('PGM-OPTIONAL')
        for item in validate_program_document(unguarded, official_function_registry_v6)
    )

    condition = ComparisonValue(
        value_id='value_has_match',
        operator='ne',
        left=SymbolReferenceValue(
            value_id='value_match_for_condition',
            symbol_id='symbol_match',
            value_type='optional<record.image_match>',
        ),
        right=NullValue(value_id='value_no_match'),
    )
    guarded = ProgramDocument(
        document_id='doc_guarded',
        function=ProgramFunction(
            function_id='func_guarded',
            display_name='已收窄',
            statements=(producer.model_copy(update={'statement_id': 'stmt_guarded_producer'}), IfStatement(
                statement_id='stmt_guard',
                condition=condition,
                then_statements=(_log('stmt_good_member', member),),
            )),
        ),
    )
    diagnostics = validate_program_document(guarded, official_function_registry_v6)
    assert not any(item.code.startswith('PGM-OPTIONAL') for item in diagnostics)


def test_dangerous_call_requires_server_owned_review_and_value_changes_invalidate_it() -> None:
    parameter_id = 'official.directory.delete_tree.parameter.directory'
    statement = CallStatement(
        statement_id='statement.delete_tree',
        function_id='official.directory.delete_tree',
        arguments={
            parameter_id: EntityReferenceValue(
                value_id='value.delete_tree.directory',
                reference_id='directory.authorized',
                reference_type='directory_ref<delete_tree>',
            ),
        },
    )
    document = ProgramDocument(
        document_id='document.delete_tree',
        function=ProgramFunction(
            function_id='function.delete_tree',
            display_name='清理缓存',
            statements=(statement,),
        ),
    )
    assert any(
        item.code == 'PGM-DANGER-001'
        for item in validate_program_document(document, official_function_registry_v6)
    )

    reviewed = review_dangerous_call(
        document, statement.statement_id, official_function_registry_v6,
    ).document
    assert not any(
        item.code == 'PGM-DANGER-001'
        for item in validate_program_document(reviewed, official_function_registry_v6)
    )
    compiled = compile_program_document(reviewed, official_function_registry_v6)
    assert compiled['valid'] is True, compiled['diagnostics']
    instruction = compiled['ecir']['functions'][0]['instructions'][0]
    assert instruction['dangerous_author_review']['fingerprint']

    changed = update_call_argument(
        reviewed,
        official_function_registry_v6,
        statement.statement_id,
        parameter_id,
        EntityReferenceValue(
            value_id='value.delete_tree.changed',
            reference_id='directory.other',
            reference_type='directory_ref<delete_tree>',
        ),
    ).document
    assert any(
        item.code == 'PGM-DANGER-001'
        for item in validate_program_document(changed, official_function_registry_v6)
    )


def test_structural_commands_create_nested_kinds_and_copy_owned_ids() -> None:
    document = create_program_document(
        '主程序', function_id='func_commands', document_id='doc_commands'
    )
    assigned = insert_assignment(
        document,
        LocalAssignmentTarget(
            symbol_id='symbol_numbers',
            display_name='数字',
            value_type='list<int64>',
        ),
        ListValue(
            value_id='value_numbers',
            item_type='int64',
            items=(IntValue(value_id='value_one', value=1),),
        ),
    )
    selected_if = insert_if(
        assigned.document,
        BoolValue(value_id='value_if_condition', value=True),
    )
    loop = insert_loop(
        selected_if.document,
        'for_each',
        SymbolReferenceValue(
            value_id='value_numbers_ref',
            symbol_id='symbol_numbers',
            value_type='list<int64>',
        ),
        item_binding=LoopBinding(
            symbol_id='symbol_loop_item', display_name='项', value_type='int64'
        ),
        location=StatementLocation(
            parent_statement_id=selected_if.selected_statement_id,
            block='then',
        ),
    )
    tried = insert_try(
        loop.document,
        retry_policy=RetryPolicy(
            max_retries=IntValue(value_id='value_retry_count', value=2),
            interval=DurationValue(value_id='value_retry_delay', milliseconds=500),
        ),
        catches=(CatchClause(catch_id='catch_error'),),
    )
    target = insert_target_scope(
        tried.document,
        TargetReferenceValue(value_id='value_target_ref', target_id='target_main'),
        location=StatementLocation(
            parent_statement_id=tried.selected_statement_id,
            block='catch',
            clause_id='catch_error',
        ),
    )
    returned = insert_return(
        target.document,
        location=StatementLocation(
            parent_statement_id=target.selected_statement_id,
            block='body',
        ),
    )
    listener = insert_listen(
        returned.document,
        MessageEventSource(name=_text('value_listen_name', '通知')),
        LoopBinding(
            symbol_id='symbol_notice', display_name='通知', value_type='received_message'
        ),
        'func_handle_notice',
    )
    labelled = set_step_label(listener.document, listener.selected_statement_id, '  处理通知  ')
    assert labelled.document.function.statements[-1].step_label == '处理通知'

    copied = copy_statement(
        labelled.document,
        selected_if.selected_statement_id,
        StatementLocation(),
    )
    original_if = labelled.document.function.statements[1]
    copied_if = copied.document.function.statements[-1]
    assert copied_if.statement_id != original_if.statement_id
    assert copied_if.then_statements[0].item_binding.symbol_id != (
        original_if.then_statements[0].item_binding.symbol_id
    )
    assert copied_if.then_statements[0].source.symbol_id == 'symbol_numbers'

    deleted = delete_statement(copied.document, copied_if.statement_id)
    assert len(deleted.document.function.statements) == len(
        labelled.document.function.statements
    )


def test_result_binding_command_and_invalid_control_types_are_checked() -> None:
    document = create_program_document(
        '主程序', function_id='func_binding', document_id='doc_binding'
    )
    vision = insert_call(document, official_function_registry_v6, 'official.image.find')
    bound = set_result_binding(
        vision.document,
        official_function_registry_v6,
        vision.selected_statement_id,
        ResultBinding(
            symbol_id='symbol_image_match',
            display_name='图像结果',
            value_type='optional<image_match>',
        ),
    )
    assert bound.document.function.statements[0].result_binding.symbol_id == (
        'symbol_image_match'
    )
    renamed = set_result_binding(
        bound.document,
        official_function_registry_v6,
        vision.selected_statement_id,
        ResultBinding(
            symbol_id='symbol_client_replacement',
            display_name='新的图像结果名称',
            value_type='optional<image_match>',
        ),
    )
    renamed_binding = renamed.document.function.statements[0].result_binding
    assert renamed_binding is not None
    assert renamed_binding.symbol_id == 'symbol_image_match'
    assert renamed_binding.display_name == '新的图像结果名称'

    invalid_condition = ProgramDocument(
        document_id='doc_bad_condition',
        function=ProgramFunction(
            function_id='func_bad_condition',
            display_name='错误条件',
            statements=(IfStatement(
                statement_id='stmt_bad_if',
                condition=_text('value_bad_condition', '不能隐式转换'),
            ),),
        ),
    )
    assert any(
        item.code == 'PGM-TYPE-001'
        for item in validate_program_document(
            invalid_condition, official_function_registry_v6
        )
    )


def test_call_result_condition_command_is_atomic_and_preserves_explicit_statements() -> None:
    document = create_program_document(
        '主程序', function_id='func_result_condition', document_id='doc_result_condition'
    )
    image_call = insert_call(document, official_function_registry_v6, 'official.image.find')
    guarded = insert_if_from_call_result(
        image_call.document,
        official_function_registry_v6,
        image_call.selected_statement_id,
        display_name='登录按钮',
    )
    call, condition = guarded.document.function.statements
    assert call.kind == 'call'
    assert call.result_binding is not None
    assert call.result_binding.display_name == '登录按钮'
    assert condition.kind == 'if'
    assert isinstance(condition.condition, ComparisonValue)
    assert condition.condition.operator == 'ne'
    assert isinstance(condition.condition.left, SymbolReferenceValue)
    assert condition.condition.left.symbol_id == call.result_binding.symbol_id
    assert isinstance(condition.condition.right, NullValue)
    assert guarded.selected_statement_id == condition.statement_id

    existing = set_result_binding(
        image_call.document,
        official_function_registry_v6,
        image_call.selected_statement_id,
        ResultBinding(
            symbol_id='symbol_existing_match',
            display_name='已有结果',
            value_type='optional<image_match>',
        ),
    )
    reused = insert_if_from_call_result(
        existing.document, official_function_registry_v6, image_call.selected_statement_id,
    )
    reused_call, reused_condition = reused.document.function.statements
    assert reused_call.result_binding.symbol_id == 'symbol_existing_match'
    assert reused_condition.condition.left.symbol_id == 'symbol_existing_match'


def test_call_result_condition_supports_bool_and_rejects_other_results_without_mutation() -> None:
    document = create_program_document(
        '主程序', function_id='func_bool_condition', document_id='doc_bool_condition'
    )
    bool_call = insert_call(document, official_function_registry_v6, 'official.file.exists')
    guarded = insert_if_from_call_result(
        bool_call.document, official_function_registry_v6, bool_call.selected_statement_id,
    )
    call, condition = guarded.document.function.statements
    assert call.result_binding is not None
    assert isinstance(condition.condition, SymbolReferenceValue)
    assert condition.condition.value_type == 'bool'
    assert condition.condition.symbol_id == call.result_binding.symbol_id

    wait_call = insert_call(document, official_function_registry_v6, WAIT_DURATION_FUNCTION_ID)
    try:
        insert_if_from_call_result(
            wait_call.document, official_function_registry_v6, wait_call.selected_statement_id,
        )
    except Exception as error:
        assert 'only bool or optional' in str(error)
    else:
        raise AssertionError('unit result must not create a condition')
    assert wait_call.document.function.statements[0].result_binding is None


def test_assignment_target_can_switch_between_local_and_project_variable() -> None:
    document = create_program_document(
        '主程序', function_id='func_target_switch', document_id='doc_target_switch'
    )
    inserted = insert_assignment(
        document,
        LocalAssignmentTarget(
            symbol_id='symbol_counter',
            display_name='计数',
            value_type='int64',
        ),
        IntValue(value_id='value_counter', value=1),
    )
    statement_id = inserted.selected_statement_id
    switched_to_project = update_assignment_target(
        inserted.document,
        statement_id,
        ProjectVariableAssignmentTarget(
            variable_id='variable_counter',
            value_type='int64',
        ),
    )
    project_assignment = switched_to_project.document.function.statements[0]
    assert project_assignment.statement_id == statement_id
    assert project_assignment.value.value_id == 'value_counter'
    assert project_assignment.target.kind == 'project_variable'
    assert project_assignment.target.variable_id == 'variable_counter'

    switched_to_local = update_assignment_target(
        switched_to_project.document,
        statement_id,
        LocalAssignmentTarget(
            symbol_id='symbol_counter_again',
            display_name='新的计数',
            value_type='int64',
        ),
    )
    local_assignment = switched_to_local.document.function.statements[0]
    assert local_assignment.statement_id == statement_id
    assert local_assignment.value.value_id == 'value_counter'
    assert local_assignment.target.kind == 'local'
    assert local_assignment.target.symbol_id == 'symbol_counter_again'

    invalid_repeat = ProgramDocument(
        document_id='doc_bad_repeat',
        function=ProgramFunction(
            function_id='func_bad_repeat',
            display_name='错误循环',
            statements=(LoopStatement(
                statement_id='stmt_bad_repeat',
                mode='repeat',
                source=IntValue(value_id='value_negative_count', value=-1),
            ),),
        ),
    )
    assert any(
        item.code == 'PGM-LOOP-006'
        for item in validate_program_document(
            invalid_repeat, official_function_registry_v6
        )
    )


def test_nested_unset_blocks_compile_and_retry_review_binds_side_effecting_body() -> None:
    expression = PureOperationValue(
        value_id='value_concat',
        operation_id='core.text_concat.v1',
        result_type='string',
        inputs={
            'core.text_concat.v1.input.left': UnsetValue(
                value_id='value_nested_unset',
                expected_type='string',
            ),
            'core.text_concat.v1.input.right': _text('value_suffix', '后缀'),
        },
    )
    unset_document = ProgramDocument(
        document_id='doc_nested_unset',
        function=ProgramFunction(
            function_id='func_nested_unset',
            display_name='未配置',
            statements=(_log('stmt_nested_unset', expression),),
        ),
    )
    compiled = compile_program_document(unset_document, official_function_registry_v6)
    assert compiled['valid'] is False
    assert any(
        item['code'] == 'PGM-VALUE-001'
        and item['value_id'] == 'value_nested_unset'
        for item in compiled['diagnostics']
    )

    retry = RetryPolicy(
        max_retries=IntValue(value_id='value_review_retries', value=2),
        interval=DurationValue(value_id='value_review_interval', milliseconds=500),
    )
    statement = TryStatement(
        statement_id='stmt_review_try',
        body=(_log('stmt_review_log', _text('value_review_text', '有副作用')),),
        retry_policy=retry,
    )
    unreviewed = ProgramDocument(
        document_id='doc_unreviewed',
        function=ProgramFunction(
            function_id='func_unreviewed',
            display_name='未审核',
            statements=(statement,),
        ),
    )
    assert any(
        item.code == 'PGM-TRY-003'
        for item in validate_program_document(unreviewed, official_function_registry_v6)
    )

    fingerprint = retry_review_fingerprint(statement, official_function_registry_v6)
    reviewed_statement = statement.model_copy(update={
        'retry_policy': retry.model_copy(update={
            'author_review_fingerprint': fingerprint,
        }),
    })
    reviewed = unreviewed.model_copy(update={
        'function': unreviewed.function.model_copy(update={
            'statements': (reviewed_statement,),
        }),
    })
    assert not any(
        item.code == 'PGM-TRY-003'
        for item in validate_program_document(reviewed, official_function_registry_v6)
    )
