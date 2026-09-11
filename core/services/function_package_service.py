"""Data-only `.ecf` function export/import with dependency closure."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
import zipfile
from copy import deepcopy
from pathlib import PurePosixPath
from typing import Any

from core.project_schema import PROJECT_SCHEMA_VERSION, SYSTEM_EXCEPTION_OUTCOME_ID, WORKFLOW_FILE, validate_document
from core.security import assert_safe_path
from core.services.asset_service import AssetService

PACKAGE_VERSION = 1
MAX_PACKAGE_FILES = 4096
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_METADATA_BYTES = 32 * 1024 * 1024


def _id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex}'


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _asset_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).endswith('image_source') and isinstance(child, str) and child.startswith('asset://'):
                refs.add(child)
            refs.update(_asset_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_asset_refs(child))
    return refs


def _replace_asset_refs(value: Any, mapping: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if str(key).endswith('image_source') and child in mapping:
                value[key] = mapping[child]
            else:
                _replace_asset_refs(child, mapping)
    elif isinstance(value, list):
        for child in value:
            _replace_asset_refs(child, mapping)


def clone_function_with_new_ids(
    source: dict[str, Any],
    *,
    function_id_map: dict[str, str] | None = None,
    contract_id_maps: dict[str, dict[str, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    value = deepcopy(source)
    old_function_id = str(value.get('function_id') or '')
    next_function_id = (function_id_map or {}).get(old_function_id) or _id('function')
    value['function_id'] = next_function_id
    graph = value.setdefault('graph', {})
    graph['graph_id'] = next_function_id

    node_ids = {str(node.get('node_id')): _id('node') for node in graph.get('nodes', []) if isinstance(node, dict)}
    own_contract = (contract_id_maps or {}).get(old_function_id, {})
    parameter_ids = own_contract.get('parameters') or {str(item.get('parameter_id')): _id('parameter') for item in value.get('parameters', []) if isinstance(item, dict)}
    local_ids = {str(item.get('local_id')): _id('local') for item in value.get('local_variables', []) if isinstance(item, dict)}
    output_ids = own_contract.get('outputs') or {str(item.get('output_id')): _id('output') for item in value.get('outputs', []) if isinstance(item, dict)}
    outcome_ids = own_contract.get('outcomes') or {
        str(item.get('outcome_id')): (
            SYSTEM_EXCEPTION_OUTCOME_ID if str(item.get('outcome_id')) == SYSTEM_EXCEPTION_OUTCOME_ID else _id('outcome')
        )
        for item in value.get('outcomes', []) if isinstance(item, dict)
    }
    for item in value.get('parameters', []):
        item['parameter_id'] = parameter_ids[str(item.get('parameter_id'))]
    for item in value.get('local_variables', []):
        item['local_id'] = local_ids[str(item.get('local_id'))]
    for item in value.get('outputs', []):
        item['output_id'] = output_ids[str(item.get('output_id'))]
    for item in value.get('outcomes', []):
        item['outcome_id'] = outcome_ids[str(item.get('outcome_id'))]
    for test_case in value.get('test_cases', []):
        if not isinstance(test_case, dict):
            continue
        inputs = test_case.get('inputs') if isinstance(test_case.get('inputs'), dict) else {}
        test_case['inputs'] = {parameter_ids.get(str(key), str(key)): child for key, child in inputs.items()}
        expected = str(test_case.get('expected_outcome_id') or '')
        if expected:
            test_case['expected_outcome_id'] = outcome_ids.get(expected, expected)
    graph['entry_node_id'] = node_ids.get(str(graph.get('entry_node_id')), graph.get('entry_node_id'))
    call_contract_by_source: dict[str, dict[str, dict[str, str]]] = {}
    for node in graph.get('nodes', []):
        old_node_id = str(node.get('node_id'))
        node['node_id'] = node_ids[str(node.get('node_id'))]
        params = node.get('params') if isinstance(node.get('params'), dict) else {}
        if node.get('node_type') == 'function_return':
            params['outcome_id'] = outcome_ids.get(str(params.get('outcome_id')), params.get('outcome_id'))
            for binding in params.get('output_bindings') or []:
                binding['output_id'] = output_ids.get(str(binding.get('output_id')), binding.get('output_id'))
        if node.get('node_type') == 'call_function':
            old_target_id = str(params.get('function_id') or '')
            target_contract = (contract_id_maps or {}).get(old_target_id, {})
            call_contract_by_source[old_node_id] = target_contract
            for binding in params.get('input_bindings') or []:
                if isinstance(binding, dict):
                    current = str(binding.get('parameter_id') or '')
                    binding['parameter_id'] = (target_contract.get('parameters') or {}).get(current, current)
            for binding in params.get('output_bindings') or []:
                if isinstance(binding, dict):
                    current = str(binding.get('output_id') or binding.get('source') or '')
                    if 'output_id' in binding:
                        binding['output_id'] = (target_contract.get('outputs') or {}).get(current, current)
                    elif 'source' in binding:
                        binding['source'] = (target_contract.get('outputs') or {}).get(current, current)
            if function_id_map:
                params['function_id'] = function_id_map.get(old_target_id, old_target_id)
    for edge in graph.get('edges', []):
        old_source_id = str(edge.get('source_node'))
        edge['edge_id'] = _id('edge')
        edge['source_node'] = node_ids.get(str(edge.get('source_node')), edge.get('source_node'))
        edge['target_node'] = node_ids.get(str(edge.get('target_node')), edge.get('target_node'))
        call_contract = call_contract_by_source.get(old_source_id, {})
        call_outcomes = call_contract.get('outcomes') or {}
        edge['source_port_id'] = call_outcomes.get(str(edge.get('source_port_id')), edge.get('source_port_id'))
    return value


class FunctionPackageService:
    @staticmethod
    def _validate_archive(archive: zipfile.ZipFile) -> None:
        members = archive.infolist()
        if len(members) > MAX_PACKAGE_FILES:
            raise ValueError('函数包文件数量超过安全上限')
        if sum(max(0, item.file_size) for item in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError('函数包解压后体积超过安全上限')
        names: set[str] = set()
        for item in members:
            name = item.filename.replace('\\', '/')
            path = PurePosixPath(name)
            if not name or path.is_absolute() or '..' in path.parts or ':' in path.parts[0]:
                raise ValueError(f'函数包包含不安全路径: {item.filename}')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f'函数包不允许符号链接: {item.filename}')
            names.add(name)
        if not {'manifest.json', 'functions.json'}.issubset(names):
            raise ValueError('函数包缺少 manifest.json 或 functions.json')
        for required in ('manifest.json', 'functions.json'):
            if archive.getinfo(required).file_size > MAX_METADATA_BYTES:
                raise ValueError(f'函数包元数据超过安全上限: {required}')

    @staticmethod
    def _closure(workflow: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
        by_id = {str(item.get('function_id')): item for item in workflow.get('functions', []) if isinstance(item, dict)}
        if root_id not in by_id:
            raise FileNotFoundError(f'函数不存在: {root_id}')
        ordered: list[dict[str, Any]] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(function_id: str) -> None:
            if function_id in visited:
                return
            if function_id in visiting:
                raise ValueError(f'函数依赖存在递归环: {function_id}')
            visiting.add(function_id)
            function = by_id.get(function_id)
            if function is None:
                raise ValueError(f'函数依赖缺失: {function_id}')
            for node in (function.get('graph') or {}).get('nodes', []):
                if node.get('node_type') == 'call_function':
                    visit(str((node.get('params') or {}).get('function_id') or ''))
            visiting.remove(function_id)
            visited.add(function_id)
            ordered.append(function)

        visit(root_id)
        return ordered

    @classmethod
    def export_function(cls, project_path: str, function_id: str) -> str:
        from core.services.blueprint_service import BlueprintService

        workflow = BlueprintService.load_workflow(project_path)
        functions = cls._closure(workflow, function_id)
        refs = sorted(set().union(*(_asset_refs(item) for item in functions))) if functions else []
        capability_refs = sorted({
            str((node.get('params') or {}).get('capability_id') or '')
            for function in functions
            for node in (function.get('graph') or {}).get('nodes', [])
            if node.get('node_type') == 'script_call' and str((node.get('params') or {}).get('capability_id') or '')
        })
        export_root = os.path.join(project_path, '.easycode', 'exports')
        os.makedirs(export_root, exist_ok=True)
        root_name = next(item.get('name') for item in functions if item.get('function_id') == function_id)
        safe_name = ''.join(char for char in str(root_name or 'function') if char not in '<>:"/\\|?*').strip() or 'function'
        destination = os.path.join(export_root, f'{safe_name}.ecf')
        suffix = 1
        while os.path.exists(destination):
            destination = os.path.join(export_root, f'{safe_name}{suffix}.ecf')
            suffix += 1
        payload = {'root_function_id': function_id, 'functions': functions}
        payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        manifest = {
            'format': 'easycode-function', 'package_version': PACKAGE_VERSION,
            'minimum_schema_version': PROJECT_SCHEMA_VERSION,
            'root_function_id': function_id,
            'function_count': len(functions), 'capability_dependencies': capability_refs,
            'sha256': hashlib.sha256(payload_bytes).hexdigest(),
        }
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr('functions.json', payload_bytes)
            for reference in refs:
                resolved = AssetService.resolve(project_path, reference)
                archive.write(resolved['full_path'], f'assets/{resolved["asset_id"]}/{resolved["relative_path"]}')
                archive.writestr(
                    f'assets/{resolved["asset_id"]}/record.json',
                    json.dumps(resolved['record'], ensure_ascii=False, indent=2),
                )
        return destination

    @classmethod
    def import_function(cls, project_path: str, package_path: str) -> dict[str, Any]:
        from core.services.blueprint_service import BlueprintService

        with zipfile.ZipFile(package_path, 'r') as archive:
            cls._validate_archive(archive)
            manifest = json.loads(archive.read('manifest.json'))
            payload_bytes = archive.read('functions.json')
            if manifest.get('format') != 'easycode-function' or int(manifest.get('package_version', 0)) != PACKAGE_VERSION:
                raise ValueError('不是受支持的 EasyCode 函数包')
            if hashlib.sha256(payload_bytes).hexdigest() != manifest.get('sha256'):
                raise ValueError('函数包校验失败，文件可能已损坏')
            payload = json.loads(payload_bytes)
            source_functions = [item for item in payload.get('functions', []) if isinstance(item, dict)]
            function_id_map = {str(item.get('function_id')): _id('function') for item in source_functions}
            contract_id_maps = {}
            for item in source_functions:
                source_id = str(item.get('function_id') or '')
                contract_id_maps[source_id] = {
                    'parameters': {
                        str(value.get('parameter_id')): _id('parameter')
                        for value in item.get('parameters', []) if isinstance(value, dict)
                    },
                    'outputs': {
                        str(value.get('output_id')): _id('output')
                        for value in item.get('outputs', []) if isinstance(value, dict)
                    },
                    'outcomes': {
                        str(value.get('outcome_id')): (
                            SYSTEM_EXCEPTION_OUTCOME_ID
                            if str(value.get('outcome_id')) == SYSTEM_EXCEPTION_OUTCOME_ID
                            else _id('outcome')
                        )
                        for value in item.get('outcomes', []) if isinstance(value, dict)
                    },
                }
            imported = [
                clone_function_with_new_ids(
                    item,
                    function_id_map=function_id_map,
                    contract_id_maps=contract_id_maps,
                )
                for item in source_functions
            ]

            asset_mapping: dict[str, str] = {}
            templates_root = AssetService.ensure_structure(project_path)
            for name in archive.namelist():
                if not name.startswith('assets/') or not name.endswith('/record.json'):
                    continue
                old_asset_id = name.split('/')[1]
                record = json.loads(archive.read(name))
                old_relative = str(record.get('path') or '')
                source_name = f'assets/{old_asset_id}/{old_relative}'
                if source_name not in archive.namelist():
                    continue
                category = AssetService.infer_kind(old_relative, record.get('kind'))
                base_name = os.path.basename(old_relative)
                if not base_name or base_name in {'.', '..'}:
                    raise ValueError('函数包包含无效的资源文件名')
                stem, extension = os.path.splitext(base_name)
                relative = f'{category}/{base_name}'
                index = 1
                target = assert_safe_path(
                    templates_root,
                    os.path.join(templates_root, relative.replace('/', os.sep)),
                )
                while os.path.exists(target):
                    relative = f'{category}/{stem}{index}{extension}'
                    target = assert_safe_path(
                        templates_root,
                        os.path.join(templates_root, relative.replace('/', os.sep)),
                    )
                    index += 1
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(source_name) as source, open(target, 'wb') as destination:
                    shutil.copyfileobj(source, destination)
                registered = AssetService.register_file(project_path, relative, record.get('kind'), record.get('capture'))
                asset_mapping[f'asset://{old_asset_id}'] = f'asset://{registered["id"]}'
            for function in imported:
                _replace_asset_refs(function, asset_mapping)

        workflow = BlueprintService.load_workflow(project_path)
        used_names = {str(item.get('name') or '') for item in workflow.get('functions', [])}
        for function in imported:
            base = str(function.get('name') or '导入函数')
            name = base
            index = 1
            while name in used_names:
                name = f'{base}{index}'
                index += 1
            function['name'] = name
            used_names.add(name)
        workflow.setdefault('functions', []).extend(imported)
        validate_document(WORKFLOW_FILE, workflow)
        BlueprintService.save_workflow(project_path, workflow)
        root_id = function_id_map.get(str(payload.get('root_function_id') or ''))
        return {'imported': len(imported), 'root_function_id': root_id, 'function_ids': [item['function_id'] for item in imported]}
