import pytest

import core.node_executors  # noqa: F401 - register node executors
from core.executor import GraphExecutor, TaskExecutionFailed
from core.models import Edge, Node, Project, Task


SUCCESS_OUTCOME = 'outcome_success'
SYSTEM_EXCEPTION = 'system_exception'


def _node(node_id, node_type, params=None):
    return Node(
        node_id=node_id,
        node_name=node_id,
        node_type=node_type,
        params=params or {},
        delay_before=0,
        loop_count=1,
        enabled=True,
    )


def _edge(edge_id, source, target, port='success', stable_id='success'):
    return Edge(
        edge_id=edge_id,
        source_node=source,
        target_node=target,
        source_port=port,
        source_port_id=stable_id,
        canvas='workflow',
    )


def _call_node(function_id, bindings=None, outputs=None):
    return _node('call', 'call_function', {
        'function_id': function_id,
        'input_bindings': bindings or [],
        'output_bindings': outputs or [],
    })


def _function_task(function_id='fn_double', *, body=None, edges=None):
    body = body or [
        _node('entry', 'function_entry'),
        _node('calculate', 'variable_op', {
            'target_var': '$local.total',
            'new_value': '$param.amount * 2',
        }),
        _node('return', 'function_return', {
            'outcome_id': SUCCESS_OUTCOME,
            'output_bindings': [{'output_id': 'output_total', 'value': '$local.total'}],
        }),
    ]
    edges = edges or [
        _edge('fn_entry_calculate', 'entry', 'calculate'),
        _edge('fn_calculate_return', 'calculate', 'return'),
    ]
    return Task(
        task_id=function_id,
        task_name='翻倍',
        nodes=body,
        role='function',
        inputs=[{
            'parameter_id': 'parameter_amount',
            'name': 'amount',
            'type': 'number',
            'required': True,
            'default_value': None,
        }],
        outputs=[{'output_id': 'output_total', 'name': 'total', 'type': 'number'}],
        local_variables=[{'local_id': 'local_total', 'name': 'total', 'type': 'number', 'default_value': 0}],
        outcomes=[
            {'outcome_id': SUCCESS_OUTCOME, 'name': '成功'},
            {'outcome_id': SYSTEM_EXCEPTION, 'name': '异常', 'system': True},
        ],
        entry_node_id='entry',
    ), edges


def test_typed_function_call_writes_output_and_routes_stable_outcome():
    function, function_edges = _function_task()
    main = Task(task_id='main', task_name='主流程', role='main', nodes=[
        _call_node(
            function.task_id,
            [{'parameter_id': 'parameter_amount', 'value': '21'}],
            [{'output_id': 'output_total', 'target': '$var{answer}'}],
        ),
        _node('after_success', 'log', {'message': 'function-ok'}),
    ])
    project = Project(
        project_name='function-runtime',
        tasks={'main': main, function.task_id: function},
        edges=[
            *function_edges,
            _edge('main_success', 'call', 'after_success', 'outcome_0', SUCCESS_OUTCOME),
        ],
    )

    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    executor.run('main', 'call')

    assert executor.variables['answer'] == 42.0
    assert '__param__:amount' not in executor.variables
    assert '__local__:total' not in executor.variables
    assert any('function-ok' in item.get('message', '') for item in executor.logs)


def test_missing_required_function_parameter_stops_main_flow():
    function, function_edges = _function_task()
    main = Task(task_id='main', task_name='主流程', role='main', nodes=[_call_node(function.task_id)])
    project = Project(
        project_name='function-required',
        tasks={'main': main, function.task_id: function},
        edges=function_edges,
    )

    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    with pytest.raises(TaskExecutionFailed):
        executor.run('main', 'call')
    assert any('缺少必填函数参数' in item.get('message', '') for item in executor.logs)


def test_recursive_function_call_returns_system_exception_outcome():
    recursive_call = _node('recursive_call', 'call_function', {
        'function_id': 'fn_recursive',
        'input_bindings': [{'parameter_id': 'parameter_amount', 'value': '$param.amount'}],
        'output_bindings': [],
    })
    function, function_edges = _function_task(
        'fn_recursive',
        body=[_node('entry', 'function_entry'), recursive_call],
        edges=[_edge('fn_entry_recursive', 'entry', 'recursive_call')],
    )
    main = Task(task_id='main', task_name='主流程', role='main', nodes=[
        _call_node(function.task_id, [{'parameter_id': 'parameter_amount', 'value': 1}]),
        _node('handled', 'log', {'message': 'recursion-blocked'}),
    ])
    project = Project(
        project_name='function-recursion',
        tasks={'main': main, function.task_id: function},
        edges=[
            *function_edges,
            _edge('main_exception', 'call', 'handled', 'outcome_1', SYSTEM_EXCEPTION),
        ],
    )

    executor = GraphExecutor(project, text_log_enabled=False, image_log_enabled=False)
    executor.run('main', 'call')

    messages = [item.get('message', '') for item in executor.logs]
    assert any('禁止函数直接或间接递归' in message for message in messages)
    assert any('recursion-blocked' in message for message in messages)
