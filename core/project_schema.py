"""EasyCode project document schema version 3.

Persisted data separates the main graph, callable functions and the one
project-wide page map. Runtime adapters may still use internal task objects,
but version-3 documents never store tasks, cross-graph edges, node folders or
visual-only canvas regions.
"""

from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from typing import Any


PROJECT_SCHEMA_VERSION = 3
PROJECT_FILE = 'project.json'
WORKFLOW_FILE = 'workflow.json'
TOPOLOGY_FILE = 'topology.json'
CONTEXT_FILE = 'context.json'
FORM_SCHEMA_FILE = 'form_schema.json'
PROJECT_DOCUMENTS = (PROJECT_FILE, WORKFLOW_FILE, TOPOLOGY_FILE, CONTEXT_FILE, FORM_SCHEMA_FILE)

MAIN_GRAPH_ID = 'main'
SYSTEM_EXCEPTION_OUTCOME_ID = 'system_exception'
FUNCTION_VALUE_TYPES = frozenset({
    'string', 'number', 'bool', 'boolean', 'list', 'dict', 'point', 'region',
    'image_asset', 'page', 'window', 'any',
})


class ProjectFormatError(ValueError):
    """Raised when a directory is not a valid current EasyCode project."""


def new_project_id() -> str:
    return f'project_{uuid.uuid4().hex}'


def new_stable_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex}'


def empty_project_meta(project_name: str, project_id: str | None = None) -> dict[str, Any]:
    return {
        'schema_version': PROJECT_SCHEMA_VERSION,
        'project_id': project_id or new_project_id(),
        'revision': 0,
        'project_name': str(project_name or '新项目'),
        'variables': {},
        'ui_state': {},
        'settings': {},
    }


def empty_canvas_graph(graph_id: str = '') -> dict[str, Any]:
    graph: dict[str, Any] = {'nodes': [], 'edges': []}
    if graph_id:
        graph['graph_id'] = graph_id
    return graph


def empty_workflow_graph() -> dict[str, Any]:
    return {
        'schema_version': PROJECT_SCHEMA_VERSION,
        'main_graph': empty_canvas_graph(MAIN_GRAPH_ID),
        'functions': [],
        'function_folders': [],
    }


def empty_page_map() -> dict[str, Any]:
    return {'schema_version': PROJECT_SCHEMA_VERSION, 'nodes': [], 'edges': []}


def create_function_definition(name: str = '新建函数', folder_id: str | None = None) -> dict[str, Any]:
    function_id = new_stable_id('function')
    entry_id = new_stable_id('node')
    return_id = new_stable_id('node')
    success_id = new_stable_id('outcome')
    return {
        'function_id': function_id,
        'name': str(name or '新建函数'),
        'description': '',
        'folder_id': folder_id,
        'parameters': [],
        'local_variables': [],
        'outputs': [],
        'outcomes': [
            {'outcome_id': success_id, 'name': '成功', 'color': 'success'},
            {'outcome_id': SYSTEM_EXCEPTION_OUTCOME_ID, 'name': '异常', 'color': 'danger', 'system': True, 'immutable': True},
        ],
        'test_cases': [],
        'graph': {
            'graph_id': function_id,
            'entry_node_id': entry_id,
            'nodes': [
                {
                    'node_id': entry_id, 'node_name': '函数入口', 'node_type': 'function_entry',
                    'params': {}, 'delay_before': 0, 'loop_count': 1, 'enabled': True,
                    'position': {'x': 80, 'y': 160}, 'size': {'w': 180, 'h': 84}, 'fixed': True,
                },
                {
                    'node_id': return_id, 'node_name': '返回成功', 'node_type': 'function_return',
                    'params': {'outcome_id': success_id, 'output_bindings': []},
                    'delay_before': 0, 'loop_count': 1, 'enabled': True,
                    'position': {'x': 420, 'y': 160}, 'size': {'w': 180, 'h': 92},
                },
            ],
            'edges': [],
        },
    }


def new_project_documents(project_name: str, project_id: str | None = None) -> dict[str, dict[str, Any]]:
    return {
        PROJECT_FILE: empty_project_meta(project_name, project_id),
        WORKFLOW_FILE: empty_workflow_graph(),
        TOPOLOGY_FILE: empty_page_map(),
        CONTEXT_FILE: {'schema_version': PROJECT_SCHEMA_VERSION},
        FORM_SCHEMA_FILE: {'schema_version': PROJECT_SCHEMA_VERSION, 'form_title': '客户运行配置面板', 'groups': []},
    }


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectFormatError(f'{label} 必须是 JSON 对象')
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProjectFormatError(f'{label} 必须是数组')
    return value


def _validate_version(data: dict[str, Any], label: str) -> None:
    version = data.get('schema_version')
    if version != PROJECT_SCHEMA_VERSION:
        shown = '缺失' if version is None else repr(version)
        raise ProjectFormatError(f'{label} schema_version 为 {shown}，当前只支持版本 {PROJECT_SCHEMA_VERSION}')


def _validate_asset_references(value: Any, label: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_label = f'{label}.{key}'
            if str(key).endswith('image_source') and child not in (None, ''):
                if not isinstance(child, str) or not child.startswith('asset://'):
                    raise ProjectFormatError(f'{child_label} 必须使用 asset:// 稳定资源引用')
            _validate_asset_references(child, child_label)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_asset_references(child, f'{label}[{index}]')


def _validate_node(node: Any, label: str) -> str:
    node = _require_object(node, label)
    for field in ('node_id', 'node_name', 'node_type'):
        if not str(node.get(field) or '').strip():
            raise ProjectFormatError(f'{label} 缺少 {field}')
    if not isinstance(node.get('params'), dict):
        raise ProjectFormatError(f'{label}.params 必须是对象')
    if 'folder_id' in node:
        raise ProjectFormatError(f'{label} 不支持 folder_id；节点直接属于所在画布')
    _validate_asset_references(node['params'], f'{label}.params')
    params = node['params']
    obsolete = {'on_success', 'on_failure'} & set(params)
    if obsolete:
        raise ProjectFormatError(f'{label}.params 包含已废弃跳转字段: {", ".join(sorted(obsolete))}')
    if node['node_type'] == 'call_task':
        raise ProjectFormatError(f'{label} 请使用 call_function，不再支持 call_task')
    if node['node_type'] == 'wait' and 'seconds' in params:
        raise ProjectFormatError(f'{label} 请使用 duration_ms')
    if node['node_type'] == 'page_state' and not str(params.get('page_id') or '').strip():
        raise ProjectFormatError(f'{label} 缺少 page_id')
    return str(node['node_id'])


def _validate_edge(edge: Any, label: str, node_ids: set[str]) -> str:
    edge = _require_object(edge, label)
    for field in ('edge_id', 'source_node', 'target_node', 'source_port', 'source_port_id'):
        if not str(edge.get(field) or '').strip():
            raise ProjectFormatError(f'{label} 缺少 {field}')
    if {'target_task', 'return_on_complete'} & set(edge):
        raise ProjectFormatError(f'{label} 不支持跨画布连线字段')
    if str(edge['source_node']) not in node_ids or str(edge['target_node']) not in node_ids:
        raise ProjectFormatError(f'{label} 的源节点或目标节点不存在')
    return str(edge['edge_id'])


def validate_canvas_graph(value: Any, label: str, *, require_graph_id: bool = False) -> dict[str, Any]:
    graph = _require_object(value, label)
    if require_graph_id and not str(graph.get('graph_id') or '').strip():
        raise ProjectFormatError(f'{label} 缺少 graph_id')
    obsolete = {'tasks', 'node_folders', 'blocks'} & set(graph)
    if obsolete:
        raise ProjectFormatError(f'{label} 包含已移除字段: {", ".join(sorted(obsolete))}')
    nodes = _require_list(graph.get('nodes'), f'{label}.nodes')
    edges = _require_list(graph.get('edges'), f'{label}.edges')
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        node_id = _validate_node(node, f'{label}.nodes[{index}]')
        if node_id in node_ids:
            raise ProjectFormatError(f'{label} 存在重复 node_id: {node_id}')
        node_ids.add(node_id)
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        edge_id = _validate_edge(edge, f'{label}.edges[{index}]', node_ids)
        if edge_id in edge_ids:
            raise ProjectFormatError(f'{label} 存在重复 edge_id: {edge_id}')
        edge_ids.add(edge_id)
    return graph


def _validate_contract_items(items: Any, label: str, id_field: str) -> set[str]:
    values = _require_list(items, label)
    ids: set[str] = set()
    names: set[str] = set()
    for index, item in enumerate(values):
        item = _require_object(item, f'{label}[{index}]')
        item_id = str(item.get(id_field) or '').strip()
        name = str(item.get('name') or '').strip()
        if not item_id or not name or item_id in ids or name in names:
            raise ProjectFormatError(f'{label}[{index}] ID 或名称缺失/重复')
        value_type = str(item.get('type') or 'any')
        if value_type not in FUNCTION_VALUE_TYPES:
            raise ProjectFormatError(f'{label}[{index}].type 不受支持: {value_type}')
        ids.add(item_id)
        names.add(name)
    return ids


def _validate_function(function: Any, label: str, folder_ids: set[str]) -> str:
    function = _require_object(function, label)
    function_id = str(function.get('function_id') or '').strip()
    name = str(function.get('name') or '').strip()
    if not function_id or not name:
        raise ProjectFormatError(f'{label} 缺少 function_id 或 name')
    folder_id = str(function.get('folder_id') or '').strip()
    if folder_id and folder_id not in folder_ids:
        raise ProjectFormatError(f'{label}.folder_id 指向不存在的函数文件夹')
    _validate_contract_items(function.get('parameters'), f'{label}.parameters', 'parameter_id')
    _validate_contract_items(function.get('local_variables'), f'{label}.local_variables', 'local_id')
    _validate_contract_items(function.get('outputs'), f'{label}.outputs', 'output_id')
    outcomes = _require_list(function.get('outcomes'), f'{label}.outcomes')
    outcome_ids: set[str] = set()
    for index, outcome in enumerate(outcomes):
        outcome = _require_object(outcome, f'{label}.outcomes[{index}]')
        outcome_id = str(outcome.get('outcome_id') or '').strip()
        if not outcome_id or not str(outcome.get('name') or '').strip() or outcome_id in outcome_ids:
            raise ProjectFormatError(f'{label}.outcomes[{index}] ID 或名称缺失/重复')
        outcome_ids.add(outcome_id)
    if SYSTEM_EXCEPTION_OUTCOME_ID not in outcome_ids:
        raise ProjectFormatError(f'{label} 缺少不可变系统异常出口')
    test_ids: set[str] = set()
    for index, test_case in enumerate(_require_list(function.get('test_cases', []), f'{label}.test_cases')):
        test_case = _require_object(test_case, f'{label}.test_cases[{index}]')
        test_id = str(test_case.get('test_id') or '').strip()
        if not test_id or test_id in test_ids or not str(test_case.get('name') or '').strip():
            raise ProjectFormatError(f'{label}.test_cases[{index}] ID 或名称缺失/重复')
        if not isinstance(test_case.get('inputs', {}), dict):
            raise ProjectFormatError(f'{label}.test_cases[{index}].inputs 必须是对象')
        expected_outcome_id = str(test_case.get('expected_outcome_id') or '').strip()
        if expected_outcome_id and expected_outcome_id not in outcome_ids:
            raise ProjectFormatError(f'{label}.test_cases[{index}] 引用了不存在的结果出口')
        test_ids.add(test_id)
    graph = validate_canvas_graph(function.get('graph'), f'{label}.graph', require_graph_id=True)
    if str(graph.get('graph_id')) != function_id:
        raise ProjectFormatError(f'{label}.graph.graph_id 必须等于 function_id')
    entry_node_id = str(graph.get('entry_node_id') or '').strip()
    entry_nodes = [node for node in graph['nodes'] if node.get('node_type') == 'function_entry']
    if len(entry_nodes) != 1 or str(entry_nodes[0].get('node_id')) != entry_node_id:
        raise ProjectFormatError(f'{label} 必须有且仅有一个固定函数入口')
    return_nodes = [node for node in graph['nodes'] if node.get('node_type') == 'function_return']
    if not return_nodes:
        raise ProjectFormatError(f'{label} 至少需要一个显式返回节点')
    for node in return_nodes:
        outcome_id = str((node.get('params') or {}).get('outcome_id') or '')
        if outcome_id not in outcome_ids:
            raise ProjectFormatError(f'{label} 返回节点引用了不存在的 outcome_id: {outcome_id}')
    return function_id


def collect_function_references(workflow: dict[str, Any], target_function_id: str | None = None) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    owners: list[tuple[str, dict[str, Any]]] = [('main', workflow.get('main_graph') or {})]
    owners.extend((str(item.get('function_id') or ''), item.get('graph') or {}) for item in workflow.get('functions') or [])
    for owner_id, graph in owners:
        for node in graph.get('nodes') or []:
            if not isinstance(node, dict) or node.get('node_type') != 'call_function':
                continue
            target = str((node.get('params') or {}).get('function_id') or '').strip()
            if target_function_id is not None and target != target_function_id:
                continue
            references.append({'owner_graph_id': owner_id, 'node_id': str(node.get('node_id') or ''), 'target_function_id': target})
    return references


def validate_project_meta(data: Any) -> dict[str, Any]:
    data = _require_object(data, PROJECT_FILE)
    _validate_version(data, PROJECT_FILE)
    obsolete = {'tasks', 'nodes', 'edges', 'workflow', 'topology'} & set(data)
    if obsolete:
        raise ProjectFormatError(f'{PROJECT_FILE} 包含已废弃字段: {", ".join(sorted(obsolete))}')
    if not str(data.get('project_name') or '').strip():
        raise ProjectFormatError(f'{PROJECT_FILE}.project_name 不能为空')
    if not str(data.get('project_id') or '').startswith('project_'):
        raise ProjectFormatError(f'{PROJECT_FILE}.project_id 无效')
    revision = data.get('revision')
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise ProjectFormatError(f'{PROJECT_FILE}.revision 必须是非负整数')
    for field in ('variables', 'ui_state', 'settings'):
        if not isinstance(data.get(field), dict):
            raise ProjectFormatError(f'{PROJECT_FILE}.{field} 必须是对象')
    return data


def validate_workflow(data: Any) -> dict[str, Any]:
    data = _require_object(data, WORKFLOW_FILE)
    _validate_version(data, WORKFLOW_FILE)
    if {'tasks', 'edges', 'node_folders'} & set(data):
        raise ProjectFormatError(f'{WORKFLOW_FILE} 只支持 main_graph、functions 与 function_folders')
    main = validate_canvas_graph(data.get('main_graph'), f'{WORKFLOW_FILE}.main_graph', require_graph_id=True)
    if str(main.get('graph_id')) != MAIN_GRAPH_ID:
        raise ProjectFormatError(f'{WORKFLOW_FILE}.main_graph.graph_id 必须为 {MAIN_GRAPH_ID}')
    folders = _require_list(data.get('function_folders'), f'{WORKFLOW_FILE}.function_folders')
    folder_ids: set[str] = set()
    folder_names: set[str] = set()
    for index, folder in enumerate(folders):
        folder = _require_object(folder, f'{WORKFLOW_FILE}.function_folders[{index}]')
        folder_id = str(folder.get('folder_id') or '').strip()
        name = str(folder.get('name') or '').strip()
        if not folder_id or not name or folder_id in folder_ids or name in folder_names:
            raise ProjectFormatError(f'{WORKFLOW_FILE}.function_folders[{index}] ID 或名称缺失/重复')
        folder_ids.add(folder_id)
        folder_names.add(name)
    function_ids: set[str] = set()
    function_names: set[str] = set()
    for index, function in enumerate(_require_list(data.get('functions'), f'{WORKFLOW_FILE}.functions')):
        function_id = _validate_function(function, f'{WORKFLOW_FILE}.functions[{index}]', folder_ids)
        name = str(function.get('name') or '')
        if function_id in function_ids or name in function_names:
            raise ProjectFormatError(f'{WORKFLOW_FILE}.functions 存在重复 ID 或名称: {name}')
        function_ids.add(function_id)
        function_names.add(name)
    for ref in collect_function_references(data):
        if ref['target_function_id'] not in function_ids:
            raise ProjectFormatError(f'{WORKFLOW_FILE} 调用节点 {ref["node_id"]} 引用了不存在的函数 {ref["target_function_id"]}')
        if ref['owner_graph_id'] == ref['target_function_id']:
            raise ProjectFormatError(f'{WORKFLOW_FILE} 禁止函数直接调用自身: {ref["target_function_id"]}')
    return data


def validate_topology(data: Any) -> dict[str, Any]:
    data = _require_object(data, TOPOLOGY_FILE)
    _validate_version(data, TOPOLOGY_FILE)
    if {'tasks', 'collections', 'regions', 'blocks'} & set(data):
        raise ProjectFormatError(f'{TOPOLOGY_FILE} 是唯一扁平页面地图，不支持集合、区域或区块')
    validate_canvas_graph(data, TOPOLOGY_FILE)
    page_ids: set[str] = set()
    for node in data['nodes']:
        if node.get('node_type') != 'page_state':
            continue
        page_id = str((node.get('params') or {}).get('page_id') or '')
        if page_id in page_ids:
            raise ProjectFormatError(f'{TOPOLOGY_FILE} 存在重复 page_id: {page_id}')
        page_ids.add(page_id)
    return data


def validate_document(filename: str, data: Any) -> dict[str, Any]:
    if filename == PROJECT_FILE:
        return validate_project_meta(data)
    if filename == WORKFLOW_FILE:
        return validate_workflow(data)
    if filename == TOPOLOGY_FILE:
        return validate_topology(data)
    if filename == CONTEXT_FILE:
        data = _require_object(data, filename)
        _validate_version(data, filename)
        return data
    if filename == FORM_SCHEMA_FILE:
        data = _require_object(data, filename)
        _validate_version(data, filename)
        _require_list(data.get('groups'), f'{filename}.groups')
        return data
    raise ProjectFormatError(f'未知项目文档: {filename}')


def load_document(project_path: str, filename: str) -> dict[str, Any]:
    path = os.path.join(project_path, filename)
    if not os.path.isfile(path):
        raise ProjectFormatError(f'缺少 {filename}')
    try:
        with open(path, encoding='utf-8-sig') as stream:
            data = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ProjectFormatError(f'{filename} JSON 已损坏（第 {exc.lineno} 行，第 {exc.colno} 列）') from exc
    except OSError as exc:
        raise ProjectFormatError(f'{filename} 无法读取: {exc}') from exc
    return deepcopy(validate_document(filename, data))


def load_project_documents(project_path: str) -> dict[str, dict[str, Any]]:
    if not os.path.isdir(project_path):
        raise ProjectFormatError(f'项目路径不是文件夹: {project_path}')
    return {filename: load_document(project_path, filename) for filename in PROJECT_DOCUMENTS}
