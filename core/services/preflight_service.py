"""IDE 运行与 Player 发布共用的项目可信性检查。"""

from __future__ import annotations

import os
import re
from collections import Counter, deque
from typing import Any

from core.params import ALL_PARAMS
from core.player.schema import normalize_form_schema, split_target
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService


def _is_writable_scope_target(value: str, *, allow_local: bool) -> bool:
    namespaces = 'var|ctx|local' if allow_local else 'var|ctx'
    return bool(re.fullmatch(rf'\$(?:{namespaces})(?:\.[A-Za-z_][A-Za-z0-9_]*|\{{[^{{}}]+\}})', str(value or '').strip()))


class PreflightService:
    @classmethod
    def check(
        cls,
        project_path: str,
        form_schema: dict | None = None,
        entry_task_id: str | None = None,
        entry_node_id: str | None = None,
        check_scope: str = 'publish',
    ) -> dict[str, Any]:
        debug_scope = str(check_scope or 'publish').strip().lower() == 'debug'
        issues: list[dict[str, str]] = []

        def add(severity: str, code: str, message: str, location: str = ''):
            issues.append({'severity': severity, 'code': code, 'message': message, 'location': location})

        def integer(value, fallback: int, field: str, location: str) -> int:
            try:
                return int(value if value not in (None, '') else fallback)
            except (TypeError, ValueError):
                add('error', 'INVALID_INTEGER', f'{field}必须是整数，当前值: {value!r}', location)
                return fallback

        def valid_region(value) -> bool:
            return (
                isinstance(value, (list, tuple))
                and len(value) == 4
                and all(isinstance(item, (int, float)) for item in value)
                and float(value[2]) > 0
                and float(value[3]) > 0
            )

        def effective_region(params: dict, prefix: str = '') -> tuple[Any, Any]:
            region = params.get(f'{prefix}region_value')
            reference_size = params.get(f'{prefix}region_reference_size')
            if params.get(f'{prefix}region_type') != 'recorded':
                return region, reference_size
            reference = str(params.get(f'{prefix}image_source') or '').strip()
            if not reference:
                return region, reference_size
            try:
                record = AssetService.resolve(project_path, reference).get('record') or {}
            except (FileNotFoundError, ValueError):
                return region, reference_size
            capture = record.get('capture') if isinstance(record, dict) else None
            captured_region = capture.get('region') if isinstance(capture, dict) else None
            if valid_region(captured_region):
                return captured_region, capture.get('reference_size') or reference_size
            return region, reference_size

        if not project_path or not os.path.isdir(project_path):
            add('error', 'PROJECT_NOT_FOUND', '项目路径不存在或不是文件夹', str(project_path or ''))
            return cls._report(issues)

        try:
            blueprint = BlueprintService.load_blueprint(project_path)
        except Exception as exc:
            add('error', 'PROJECT_LOAD_FAILED', f'项目无法加载: {exc}', project_path)
            return cls._report(issues)

        from core.services.capability_service import CapabilityService

        discovered = CapabilityService.discover(project_path, force=True)
        for item in discovered:
            if item.get('id') == '__discovery_errors__':
                for error in item.get('errors') or []:
                    add('error', 'CAPABILITY_PACKAGE_INVALID', error.get('message') or '能力包加载失败', error.get('source') or 'capabilities')

        main_graph = blueprint.get('main_graph') if isinstance(blueprint.get('main_graph'), dict) else {}
        functions = blueprint.get('functions') if isinstance(blueprint.get('functions'), list) else []
        tasks = [{
            'task_id': 'main', 'task_name': '主流程', 'role': 'main',
            'nodes': main_graph.get('nodes') or [], 'edges': main_graph.get('edges') or [],
            'inputs': [], 'outputs': [], 'outcomes': [],
        }]
        tasks.extend({
            'task_id': item.get('function_id'), 'task_name': item.get('name'), 'role': 'function',
            'nodes': (item.get('graph') or {}).get('nodes') or [],
            'edges': (item.get('graph') or {}).get('edges') or [],
            'entry_node_id': (item.get('graph') or {}).get('entry_node_id'),
            'inputs': item.get('parameters') or [], 'outputs': item.get('outputs') or [],
            'local_variables': item.get('local_variables') or [], 'outcomes': item.get('outcomes') or [],
        } for item in functions if isinstance(item, dict))
        edges = [edge for task in tasks for edge in (task.get('edges') or [])]
        settings = blueprint.get('settings') if isinstance(blueprint.get('settings'), dict) else {}
        allow_physical = bool(settings.get('allow_physical_fallback', False))
        schema = normalize_form_schema(form_schema if form_schema is not None else cls._load_schema(project_path))
        schema_targets = {
            str(field.get('target') or '')
            for group in schema.get('groups', [])
            for field in group.get('fields', [])
            if isinstance(field, dict)
        }
        context = {}
        try:
            from core.services.workspace_service import WorkspaceService

            context = WorkspaceService.load_runtime_context(project_path)
        except Exception as exc:
            add('error', 'CONTEXT_INVALID', f'工作面板配置无法读取: {exc}', 'context.json')
        screen_action_nodes = []
        visual_nodes = []
        forced_high_speed_nodes = []
        if not main_graph.get('nodes'):
            add('warning' if debug_scope else 'error', 'MAIN_FLOW_EMPTY', '主流程没有可执行节点', 'workflow.json/main_graph')

        task_ids = [str(task.get('task_id') or '') for task in tasks if isinstance(task, dict)]
        for duplicate in (item for item, count in Counter(task_ids).items() if item and count > 1):
            add('error', 'DUPLICATE_TASK_ID', f'任务 ID 重复: {duplicate}', duplicate)

        task_map = {task.get('task_id'): task for task in tasks if isinstance(task, dict) and task.get('task_id')}
        task_names = []
        node_map: dict[str, tuple[str, dict]] = {}
        duplicate_nodes = set()
        for task in tasks:
            if not isinstance(task, dict):
                add('error', 'INVALID_TASK', '任务记录必须是对象', 'workflow.json')
                continue
            task_id = str(task.get('task_id') or '')
            task_name = str(task.get('task_name') or task_id or '未命名流程')
            task_names.append(task_name)
            location = f'流程/{task_name}'
            if not task_id:
                add('error', 'TASK_ID_MISSING', '流程缺少 task_id', location)
            nodes = task.get('nodes') if isinstance(task.get('nodes'), list) else []
            if not nodes:
                add('warning', 'EMPTY_TASK', f'流程「{task_name}」没有节点', location)
            for node in nodes:
                if not isinstance(node, dict):
                    add('error', 'INVALID_NODE', '节点记录必须是对象', location)
                    continue
                node_id = str(node.get('node_id') or '')
                node_name = str(node.get('node_name') or node_id or '未命名节点')
                node_location = f'{location}/{node_name}'
                if not node_id:
                    add('error', 'NODE_ID_MISSING', '节点缺少 node_id', node_location)
                    continue
                if node_id in node_map:
                    duplicate_nodes.add(node_id)
                node_map[node_id] = (task_id, node)
                node_type = str(node.get('node_type') or '')
                if not node_type or node_type not in ALL_PARAMS:
                    add('error', 'UNKNOWN_NODE_TYPE', f'未知节点类型: {node_type or "(空)"}', node_location)
                node_loop = node.get('loop_count', 1)
                if not isinstance(node_loop, int) or node_loop < -1:
                    add('error', 'INVALID_NODE_LOOP', f'节点循环次数无效: {node_loop}', node_location)
                cls._check_node_assets(project_path, node, node_location, add)
                params = node.get('params') if isinstance(node.get('params'), dict) else {}
                image_mode = str(params.get('execution_mode') or '').strip().lower()
                image_click_modes = {'click_once', 'click_until_absent', 'click_until_stop'}
                is_screen_action = (
                    node_type in {'click', 'scroll', 'drag', 'text_input'}
                    or (
                        node_type == 'image_recognition'
                        and (
                            image_mode in image_click_modes
                            or (not image_mode and params.get('on_success_action') == 'click_center')
                        )
                    )
                    or (node_type == 'ocr_recognition' and params.get('on_success_action') == 'click_center')
                    or (node_type == 'control' and params.get('action', 'click') in {'click', 'double_click', 'hover', 'input_text'})
                )
                if is_screen_action:
                    screen_action_nodes.append((node_location, node_type, params))
                if node_type in {'click', 'scroll', 'drag', 'text_input'}:
                    context_mode = str(context.get('work_mode') or '').strip().lower()
                    if str(params.get('input_mode') or 'background').lower() in {'physical', 'foreground', 'mouse'} and not allow_physical and context_mode not in {'desktop', 'fullscreen', 'full_screen'}:
                        add(
                            'error',
                            'PHYSICAL_INPUT_NOT_AUTHORIZED',
                            '节点要求物理鼠标，但项目总开关“允许物理输入回退”处于关闭状态',
                            node_location,
                        )
                    reference_size = params.get('position_reference_size')
                    if not (
                        isinstance(reference_size, (list, tuple))
                        and len(reference_size) >= 2
                        and all(isinstance(value, (int, float)) and value > 0 for value in reference_size[:2])
                    ):
                        add('warning', 'COORDINATE_REFERENCE_MISSING', '输入坐标缺少录制参考尺寸，窗口缩放后可能偏移', node_location)
                if node_type == 'drag':
                    path_points = params.get('path_points')
                    action = str(params.get('action') or 'drag')
                    if path_points is not None:
                        minimum = 1 if action == 'long_press' else 2
                        if not isinstance(path_points, list) or not (minimum <= len(path_points) <= 32):
                            add('error', 'GESTURE_PATH_INVALID', f'{"长按" if action == "long_press" else "拖拽"}路径需要 {minimum}-32 个点', node_location)
                        else:
                            for index, point in enumerate(path_points):
                                position = point.get('position') if isinstance(point, dict) else None
                                if not (
                                    isinstance(position, (list, tuple)) and len(position) >= 2
                                    and all(isinstance(value, (int, float)) and value >= 0 for value in position[:2])
                                ):
                                    add('error', 'GESTURE_POINT_INVALID', f'手势路径第 {index + 1} 个坐标无效', node_location)
                if node_type == 'scroll':
                    termination = str(params.get('termination_mode') or 'fixed')
                    if termination in {'image_present', 'image_absent'} and not str(params.get('stop_image_source') or '').strip():
                        add('error', 'SCROLL_STOP_IMAGE_REQUIRED', '滚动结束条件缺少特征图片', node_location)
                    if termination == 'page_present' and not str(params.get('stop_page_id') or '').strip():
                        add('error', 'SCROLL_STOP_PAGE_REQUIRED', '滚动结束条件缺少目标页面', node_location)
                    if termination == 'expression' and not str(params.get('stop_expression') or '').strip():
                        add('error', 'SCROLL_STOP_EXPRESSION_REQUIRED', '滚动结束条件缺少表达式', node_location)
                if node_type in {'image_recognition', 'ocr_recognition'} and params.get('region_type') in {'recorded', 'custom'}:
                    region, reference_size = effective_region(params)
                    if not valid_region(region):
                        add(
                            'error',
                            'REGION_INVALID',
                            f'识别区域必须是 [x, y, 宽, 高] 且宽高大于 0，当前值: {region}',
                            node_location,
                        )
                    if not (
                        isinstance(reference_size, (list, tuple))
                        and len(reference_size) >= 2
                        and all(isinstance(value, (int, float)) and value > 0 for value in reference_size[:2])
                    ):
                        add('warning', 'REGION_REFERENCE_MISSING', '识别区域缺少录制参考尺寸，窗口缩放后可能偏移', node_location)
                if node_type == 'image_recognition':
                    visual_nodes.append((node_location, params))
                    if str(params.get('performance_mode') or 'auto').strip().lower() == 'high_speed':
                        forced_high_speed_nodes.append(node_location)
                    valid_modes = {'wait_present', 'wait_absent', 'click_once', 'click_until_absent', 'click_until_stop'}
                    if image_mode not in valid_modes:
                        add('error', 'IMAGE_MODE_INVALID', f'图像节点运行模式无效或缺失: {image_mode or "(空)"}', node_location)
                    if image_mode == 'click_until_stop' and not str(params.get('stop_image_source') or '').strip():
                        add('error', 'STOP_TEMPLATE_REQUIRED', '持续点击直到停止特征模式缺少停止特征图片', node_location)
                    if image_mode == 'click_until_stop' and params.get('stop_region_type') in {'recorded', 'custom'}:
                        stop_region, stop_reference = effective_region(params, 'stop_')
                        if not valid_region(stop_region):
                            add(
                                'error',
                                'STOP_REGION_INVALID',
                                f'停止特征区域必须是 [x, y, 宽, 高] 且宽高大于 0，当前值: {stop_region}',
                                node_location,
                            )
                        if not (
                            isinstance(stop_reference, (list, tuple))
                            and len(stop_reference) >= 2
                            and all(isinstance(value, (int, float)) and value > 0 for value in stop_reference[:2])
                        ):
                            add('warning', 'STOP_REGION_REFERENCE_MISSING', '停止特征区域缺少录制参考尺寸', node_location)
                if node_type == 'script_call':
                    call_mode = str(params.get('call_mode') or 'capability').strip().lower()
                    if call_mode != 'capability':
                        add('error', 'CAPABILITY_CALL_MODE_UNSUPPORTED', f'调用能力节点不支持旧调用方式: {call_mode}', node_location)
                        continue
                    capability_id = str(params.get('capability_id') or '').strip()
                    version = str(params.get('capability_version') or '').strip()
                    if not capability_id:
                        add('error', 'CAPABILITY_MISSING', '调用能力节点未选择能力函数', node_location)
                        continue
                    spec = CapabilityService.resolve(project_path, capability_id, version or None)
                    if spec is None:
                        suffix = f'@{version}' if version else ''
                        add('error', 'CAPABILITY_NOT_FOUND', f'能力不存在或版本不匹配: {capability_id}{suffix}', node_location)
                        continue
                    permissions = set(spec.permissions)
                    if permissions & {'screen.read', 'input.gesture', 'input.text', 'input.click'}:
                        screen_action_nodes.append((node_location, node_type, params))
                    if 'screen.read' in permissions:
                        visual_nodes.append((node_location, params))
                    bound_inputs = {
                        str(item.get('name') or ''): item
                        for item in (params.get('input_bindings') or []) if isinstance(item, dict)
                    }
                    declared_inputs = {str(item.get('name') or ''): item for item in spec.inputs}
                    for name, declaration in declared_inputs.items():
                        if declaration.get('required') and 'default' not in declaration and name not in bound_inputs:
                            add('error', 'CAPABILITY_REQUIRED_INPUT', f'能力必填输入未绑定: {name}', node_location)
                    for unknown in sorted(set(bound_inputs) - set(declared_inputs)):
                        add('error', 'CAPABILITY_UNKNOWN_INPUT', f'能力不接受输入: {unknown}', node_location)
                    declared_outputs = {str(item.get('name') or '') for item in spec.outputs}
                    for binding in params.get('output_bindings') or []:
                        if not isinstance(binding, dict):
                            continue
                        source = str(binding.get('source') or '').strip().removeprefix('data.')
                        target = str(binding.get('target') or '').strip()
                        if source and declared_outputs and source.split('.', 1)[0] not in declared_outputs:
                            add('warning', 'CAPABILITY_UNKNOWN_OUTPUT', f'能力未声明输出: {source}', node_location)
                        allow_local = task.get('role') == 'function'
                        if target and not _is_writable_scope_target(target, allow_local=allow_local):
                            scope_hint = '$var.name、$ctx.name 或 $local.name' if task.get('role') == 'function' else '$var.name 或 $ctx.name'
                            add('error', 'CAPABILITY_OUTPUT_TARGET_INVALID', f'能力输出目标必须是 {scope_hint}: {target}', node_location)
                    retries = integer(params.get('retry_count'), 0, '能力重试次数', node_location)
                    if retries > 0 and not spec.idempotent:
                        add('error', 'CAPABILITY_RETRY_NOT_IDEMPOTENT', '该能力未声明幂等，不能自动重试', node_location)
                    if integer(params.get('timeout_ms'), spec.timeout_ms, '能力超时', node_location) <= 0:
                        add('error', 'CAPABILITY_TIMEOUT_INVALID', '能力超时必须大于 0ms', node_location)
                    if spec.source != 'builtin':
                        add('warning', 'CUSTOM_CAPABILITY_REVIEW', f'项目能力将执行 Python 代码，请审查其权限: {capability_id}', node_location)

        for task_name, count in Counter(task_names).items():
            if count > 1:
                add('error', 'DUPLICATE_TASK_NAME', f'流程名称重复: {task_name}', 'workflow.json')

        for node_id in duplicate_nodes:
            add('error', 'DUPLICATE_NODE_ID', f'节点 ID 在多个位置重复: {node_id}', node_id)

        edge_ids = []
        adjacency: dict[str, list[str]] = {}
        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                add('error', 'INVALID_EDGE', '连线记录必须是对象', f'workflow.json/edges/{index}')
                continue
            edge_id = str(edge.get('edge_id') or '')
            if edge_id:
                edge_ids.append(edge_id)
            source = str(edge.get('source_node') or edge.get('source') or '')
            target = str(edge.get('target_node') or '')
            location = f'连线/{edge_id or index}'
            if not source or source not in node_map:
                add('error', 'DANGLING_EDGE_SOURCE', f'连线源节点不存在: {source or "(空)"}', location)
            if not target or target not in node_map:
                add('error', 'DANGLING_EDGE_TARGET', f'连线目标节点不存在: {target or "(空)"}', location)
            if source and target:
                adjacency.setdefault(source, []).append(target)
        for duplicate in (item for item, count in Counter(edge_ids).items() if count > 1):
            add('warning', 'DUPLICATE_EDGE_ID', f'连线 ID 重复: {duplicate}', duplicate)

        # 函数契约、稳定引用与无递归检查。
        call_graph: dict[str, set[str]] = {}
        for owner_id, task in task_map.items():
            for node in task.get('nodes', []):
                if node.get('node_type') != 'call_function':
                    continue
                params = node.get('params') if isinstance(node.get('params'), dict) else {}
                target_id = str(params.get('function_id') or '').strip()
                location = f'流程/{task.get("task_name") or owner_id}/{node.get("node_name") or node.get("node_id")}'
                if not target_id:
                    add('error', 'CALL_FUNCTION_TARGET_MISSING', '调用函数节点未选择目标函数', location)
                    continue
                if target_id == owner_id:
                    add('error', 'CALL_FUNCTION_DIRECT_RECURSION', '函数不能直接调用自身', location)
                    continue
                target_task = task_map.get(target_id)
                if target_task is None:
                    add('error', 'CALL_FUNCTION_NOT_FOUND', f'调用的目标函数不存在: {target_id}', location)
                    continue
                if str(target_task.get('role') or '') != 'function':
                    add('error', 'CALL_FUNCTION_TARGET_INVALID', '调用函数节点只能指向函数，不能指向主流程', location)
                    continue
                call_graph.setdefault(owner_id, set()).add(target_id)
                entry_id = str(target_task.get('entry_node_id') or '')
                if entry_id:
                    adjacency.setdefault(node.get('node_id'), []).append(entry_id)
                declared_inputs = {
                    str(item.get('parameter_id') or ''): item for item in (target_task.get('inputs') or []) if isinstance(item, dict)
                }
                bound_inputs = {
                    str(item.get('parameter_id') or item.get('name') or '')
                    for item in (params.get('input_bindings') or []) if isinstance(item, dict)
                }
                for parameter_id, declaration in declared_inputs.items():
                    default_value = declaration.get('default', declaration.get('default_value'))
                    if declaration.get('required') and default_value is None and parameter_id not in bound_inputs:
                        add('error', 'CALL_FUNCTION_REQUIRED_INPUT', f'函数必填参数未绑定: {declaration.get("name") or parameter_id}', location)
                for unknown in sorted(bound_inputs - set(declared_inputs)):
                    if unknown:
                        add('error', 'CALL_FUNCTION_UNKNOWN_INPUT', f'函数不存在该参数 ID: {unknown}', location)
                declared_outputs = {
                    str(item.get('output_id') or '') for item in (target_task.get('outputs') or []) if isinstance(item, dict)
                }
                for binding in params.get('output_bindings') or []:
                    if not isinstance(binding, dict):
                        continue
                    source = str(binding.get('output_id') or binding.get('source') or '')
                    target = str(binding.get('target') or '')
                    if source and source not in declared_outputs:
                        add('error', 'CALL_FUNCTION_UNKNOWN_OUTPUT', f'函数不存在该输出 ID: {source}', location)
                    if target and not _is_writable_scope_target(target, allow_local=task.get('role') == 'function'):
                        add('error', 'CALL_FUNCTION_OUTPUT_TARGET_INVALID', f'函数输出只能写入 $var、$ctx 或当前函数的 $local: {target}', location)

        # 当前架构明确禁止递归；运行时深度限制只是最后一道保护。
        def has_cycle(start, current, seen):
            for nxt in call_graph.get(current, set()):
                if nxt == start:
                    return True
                if nxt not in seen and has_cycle(start, nxt, seen | {nxt}):
                    return True
            return False

        for task_id in call_graph:
            if has_cycle(task_id, task_id, {task_id}):
                add('error', 'CALL_FUNCTION_INDIRECT_RECURSION', f'检测到间接递归调用: {task_id}', task_id)

        context_window = str(context.get('window_title') or '').strip()
        context_is_emulator = bool(context.get('is_emulator'))
        context_is_android = bool(context.get('is_android')) or str(context.get('work_mode') or '') == 'android'
        context_adb = str(context.get('adb_device_id') or '').strip()
        context_mode = str(context.get('work_mode') or '').strip().lower()
        if screen_action_nodes and not context_window and not context_is_android and '$ctx.window_title' not in schema_targets:
            if context_mode in {'desktop', 'fullscreen', 'full_screen'}:
                add('warning', 'DESKTOP_PHYSICAL_INPUT', '全屏工作面板固定使用物理输入，无法安全多开', 'context.json')
            elif not allow_physical:
                add(
                    'error',
                    'BACKGROUND_TARGET_MISSING',
                    '项目包含界面操作，但未绑定窗口且 Player 表单也未提供目标窗口；严格后台模式将阻止运行',
                    'context.json',
                )
            else:
                add('warning', 'DESKTOP_PHYSICAL_INPUT', '界面操作将依赖全桌面物理输入，无法安全多开', 'context.json')
        if context_is_android or '$ctx.is_android' in schema_targets:
            if not context_adb and '$ctx.adb_device_id' not in schema_targets:
                add('error', 'ADB_SERIAL_MISSING', 'Android目标未绑定唯一 ADB serial', 'context.json')
        elif context_is_emulator or '$ctx.is_emulator' in schema_targets:
            if not context_window and '$ctx.window_title' not in schema_targets:
                add('error', 'EMULATOR_WINDOW_MISSING', '模拟器模式未配置目标窗口', 'context.json')
            if not context_adb and '$ctx.adb_device_id' not in schema_targets:
                add('error', 'ADB_SERIAL_MISSING', '模拟器模式未绑定唯一 ADB serial', 'context.json')
        elif screen_action_nodes and (context_window or '$ctx.window_title' in schema_targets):
            add(
                'warning',
                'BACKGROUND_DELIVERY_UNVERIFIED',
                'PC 像素点击使用窗口后台消息，投递成功不等于界面效果已验证；不兼容的自绘/DirectX窗口会明确失败或保持“效果未验证”',
                '项目输入能力',
            )

        try:
            from core.services.capability_packaging_service import CapabilityPackagingService

            CapabilityPackagingService.collect_files(project_path, blueprint)
        except Exception as exc:
            add('error', 'CAPABILITY_PACKAGE_INCOMPLETE', str(exc), 'capabilities')

        schema_entry = schema.get('entry') if isinstance(schema.get('entry'), dict) else {}
        selected_task = entry_task_id or schema_entry.get('task_id')
        selected_node = entry_node_id or schema_entry.get('node_id')
        if not selected_task or not selected_node:
            add('error', 'ENTRY_REQUIRED', 'Player 必须明确选择主流程中的入口节点', 'form_schema.json/entry')
        if selected_task and selected_task != 'main':
            add('error', 'ENTRY_MUST_BE_MAIN', 'Player 入口必须位于主流程；函数只能通过调用函数节点进入', 'form_schema.json/entry')
        if selected_task and selected_task not in task_map:
            add('error', 'ENTRY_TASK_MISSING', f'运行入口任务不存在: {selected_task}', 'form_schema.json/entry')
        if selected_node:
            owner = node_map.get(selected_node)
            if not owner:
                add('error', 'ENTRY_NODE_MISSING', f'运行入口节点不存在: {selected_node}', 'form_schema.json/entry')
            elif selected_task and owner[0] != selected_task:
                add('error', 'ENTRY_NODE_WRONG_TASK', '运行入口节点不属于所选流程', 'form_schema.json/entry')
        cls._check_schema(schema, blueprint, node_map, add)
        for node in (blueprint.get('page_map') or {}).get('nodes') or []:
            if isinstance(node, dict):
                cls._check_node_assets(
                    project_path,
                    node,
                    f'页面地图/{node.get("node_name") or node.get("node_id") or "未命名节点"}',
                    add,
                )
        cls._check_topology(blueprint.get('page_map') or {}, tasks, add)

        reachable = set()
        if selected_node and selected_node in node_map:
            queue = deque([selected_node])
            while queue:
                current = queue.popleft()
                if current in reachable:
                    continue
                reachable.add(current)
                queue.extend(adjacency.get(current, []))
            if not debug_scope:
                for node_id, (_, node) in node_map.items():
                    if node.get('enabled', True) and node_id not in reachable:
                        add('suggestion', 'UNREACHABLE_NODE', f'节点从发布入口不可达: {node.get("node_name") or node_id}', node_id)

        android_visual_target = bool(
            visual_nodes
            and (context_is_emulator or context_is_android or '$ctx.is_emulator' in schema_targets or '$ctx.is_android' in schema_targets)
        )
        android_high_speed_available = False
        android_high_speed_detail = 'not_configured'
        if android_visual_target:
            try:
                from core.services.android_stream import validate_scrcpy_runtime

                android_high_speed_available, android_high_speed_detail = validate_scrcpy_runtime()
            except Exception as exc:
                android_high_speed_detail = str(exc)
            if not android_high_speed_available:
                if forced_high_speed_nodes:
                    add(
                        'error',
                        'ANDROID_HIGH_SPEED_UNAVAILABLE',
                        f'节点强制高速采帧，但运行时不可用: {android_high_speed_detail}',
                        forced_high_speed_nodes[0],
                    )
                else:
                    add(
                        'warning',
                        'ANDROID_HIGH_SPEED_FALLBACK',
                        f'Android高速采帧不可用，将明确降级为标准ADB截图: {android_high_speed_detail}',
                        '项目视觉能力',
                    )

        if debug_scope:
            # IDE“从当前节点执行”只要求当前可达子图正确。发布、导出仍使用完整项目严格检查。
            reachable_locations = set()
            reachable_types = set()
            for node_id in reachable:
                owner = node_map.get(node_id)
                if not owner:
                    continue
                task_id, node = owner
                task = task_map.get(task_id) or {}
                reachable_locations.add(node_id)
                reachable_locations.add(f'流程/{task.get("task_name") or task_id}/{node.get("node_name") or node_id}')
                reachable_types.add(str(node.get('node_type') or ''))
            has_reachable_screen_action = bool(reachable_types & {'click', 'scroll', 'drag', 'text_input', 'image_recognition', 'ocr_recognition', 'control', 'script_call'})
            has_reachable_smart_jump = 'smart_jump' in reachable_types
            schema_codes = {
                'SCHEMA_TARGET_INVALID', 'SCHEMA_SETTING_UNKNOWN', 'SCHEMA_NODE_UNKNOWN',
                'SCHEMA_NODE_FIELD_BLOCKED', 'SCHEMA_NODE_PARAM_UNKNOWN', 'SCHEMA_OPTIONS_MISSING',
                'SCHEMA_RANGE_INVALID', 'SCHEMA_TARGET_DUPLICATE',
            }
            topology_prefixes = ('TOPOLOGY_', 'DUPLICATE_PAGE_', 'SMART_JUMP_')
            global_publish_codes = {'CAPABILITY_PACKAGE_INVALID', 'CAPABILITY_PACKAGE_INCOMPLETE'}
            target_codes = {
                'BACKGROUND_TARGET_MISSING', 'DESKTOP_PHYSICAL_INPUT', 'EMULATOR_WINDOW_MISSING',
                'ADB_SERIAL_MISSING', 'BACKGROUND_DELIVERY_UNVERIFIED', 'ANDROID_HIGH_SPEED_UNAVAILABLE',
                'ANDROID_HIGH_SPEED_FALLBACK',
            }
            scoped = []
            for issue in issues:
                code = issue.get('code', '')
                location = issue.get('location', '')
                if code in schema_codes or code in global_publish_codes or code == 'UNREACHABLE_NODE':
                    continue
                if code.startswith(topology_prefixes) and not has_reachable_smart_jump:
                    continue
                if code in target_codes and not has_reachable_screen_action:
                    continue
                if location.startswith('流程/') and location.count('/') >= 2 and location not in reachable_locations:
                    continue
                if location in node_map and location not in reachable:
                    continue
                scoped.append(issue)
            issues = scoped

        report = cls._report(issues)
        if debug_scope:
            report['can_publish'] = False
            report['scope'] = 'debug'
        report['capabilities'] = {
            'physical_fallback': 'allowed' if allow_physical else 'blocked',
            'target_binding': (
                'android_device' if context_is_android
                else ('player_select' if '$ctx.window_title' in schema_targets else ('window' if context_window else 'desktop'))
            ),
            'emulator_input': (
                'scrcpy_control_with_adb_fallback'
                if android_high_speed_available
                else ('adb_persistent' if context_is_emulator or context_is_android or '$ctx.is_emulator' in schema_targets else 'not_configured')
            ),
            'pc_background_input': 'delivered_unverified',
            'target_capture': (
                'scrcpy_latest_frame'
                if android_high_speed_available
                else ('adb_standard' if context_is_emulator or context_is_android else ('print_window_strict' if context_window else 'desktop'))
            ),
            'android_high_speed_detail': android_high_speed_detail,
        }
        return report

    @staticmethod
    def _load_schema(project_path: str) -> dict:
        import json

        path = os.path.join(project_path, 'form_schema.json')
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding='utf-8-sig') as file:
                return json.load(file)
        except Exception:
            return {}

    @staticmethod
    def _check_node_assets(project_path: str, node: dict, location: str, add) -> None:
        params = node.get('params') if isinstance(node.get('params'), dict) else {}

        def walk(value):
            if isinstance(value, dict):
                for key, image_source in value.items():
                    if not str(key).endswith('image_source'):
                        continue
                    if isinstance(image_source, str) and image_source and '$' not in image_source and '{{' not in image_source:
                        from core.services.asset_service import AssetService
                        try:
                            AssetService.resolve(project_path, image_source)
                        except (FileNotFoundError, ValueError):
                            add('error', 'TEMPLATE_MISSING', f'模板图片不存在: {image_source}', location)
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(params)

    @staticmethod
    def _check_schema(schema: dict, blueprint: dict, workflow_node_map: dict, add) -> None:
        from core.settings import DEFAULT_PROJECT_SETTINGS

        all_nodes = {node_id: owner[1] for node_id, owner in workflow_node_map.items()}
        for node in (blueprint.get('page_map') or {}).get('nodes') or []:
            if node.get('node_id'):
                all_nodes[str(node['node_id'])] = node
        targets = []
        for group in schema.get('groups', []):
            for field in group.get('fields', []):
                target = str(field.get('target') or '')
                targets.append(target)
                slot, key = split_target(target)
                if not slot or not key:
                    add('error', 'SCHEMA_TARGET_INVALID', f'客户参数 Target 无效: {target or "(空)"}', 'form_schema.json')
                elif target.startswith('$settings.') and target[10:] not in DEFAULT_PROJECT_SETTINGS:
                    add('error', 'SCHEMA_SETTING_UNKNOWN', f'Player 绑定了不存在的项目设置: {target}', target)
                elif target.startswith('$node.'):
                    parts = target.split('.', 2)
                    node = all_nodes.get(parts[1]) if len(parts) == 3 else None
                    if node is None:
                        add('error', 'SCHEMA_NODE_UNKNOWN', f'Player 绑定的节点不存在: {target}', target)
                    elif parts[2] not in {'delay_before', 'loop_count'}:
                        if not parts[2].startswith('params.'):
                            add('error', 'SCHEMA_NODE_FIELD_BLOCKED', f'Player 不允许修改该节点字段: {target}', target)
                        else:
                            key_path = parts[2][7:].split('.')
                            cursor = node.get('params') or {}
                            for path_part in key_path:
                                if isinstance(cursor, dict) and path_part in cursor:
                                    cursor = cursor[path_part]
                                    continue
                                if isinstance(cursor, list) and path_part.isdigit() and 0 <= int(path_part) < len(cursor):
                                    cursor = cursor[int(path_part)]
                                    continue
                                else:
                                    add('error', 'SCHEMA_NODE_PARAM_UNKNOWN', f'Player 绑定的节点参数不存在: {target}', target)
                                    break
                if field.get('ui_type') in {'select', 'checkbox_group'} and not field.get('provider') and not field.get('options'):
                    add('error', 'SCHEMA_OPTIONS_MISSING', f'参数「{field.get("label") or target}」没有可选项', target)
                if field.get('min') is not None and field.get('max') is not None and field['min'] > field['max']:
                    add('error', 'SCHEMA_RANGE_INVALID', f'参数「{field.get("label") or target}」最小值大于最大值', target)
        for duplicate in (item for item, count in Counter(targets).items() if item and count > 1):
            add('error', 'SCHEMA_TARGET_DUPLICATE', f'客户参数 Target 重复: {duplicate}', duplicate)

    @staticmethod
    def _check_topology(topology: dict, workflow_tasks: list, add) -> None:
        pages = {}
        topology_nodes = set()
        for node in topology.get('nodes') or []:
            node_id = node.get('node_id')
            if node_id:
                topology_nodes.add(node_id)
            if node.get('node_type') != 'page_state':
                continue
            params = node.get('params') if isinstance(node.get('params'), dict) else {}
            page_id = params.get('page_id') or node_id
            if page_id in pages:
                add('error', 'DUPLICATE_PAGE_ID', f'页面 ID 重复: {page_id}', str(page_id))
            pages[page_id] = node
            if not params.get('features'):
                add('warning', 'PAGE_WITHOUT_FEATURES', f'页面「{node.get("node_name") or page_id}」没有识别特征', str(page_id))
        for index, edge in enumerate(topology.get('edges') or []):
            source = edge.get('source_node') or edge.get('source')
            target = edge.get('target_node') or edge.get('target')
            if source not in topology_nodes:
                add('error', 'TOPOLOGY_EDGE_SOURCE_MISSING', f'拓扑连线源页面不存在: {source}', f'topology/edges/{index}')
            if target not in topology_nodes:
                add('error', 'TOPOLOGY_EDGE_TARGET_MISSING', f'拓扑连线目标页面不存在: {target}', f'topology/edges/{index}')
        for task in workflow_tasks:
            for node in task.get('nodes', []) if isinstance(task, dict) else []:
                if node.get('node_type') == 'smart_jump':
                    target = (node.get('params') or {}).get('target_page_id')
                    if not target:
                        add('error', 'SMART_JUMP_TARGET_MISSING', '智能跳转节点未选择目标页面', str(node.get('node_id') or ''))
                    elif target not in pages and target not in topology_nodes:
                        add('error', 'SMART_JUMP_PAGE_NOT_FOUND', f'智能跳转目标页面不存在: {target}', str(node.get('node_id') or ''))

    @staticmethod
    def _report(issues: list[dict[str, str]]) -> dict[str, Any]:
        counts = {severity: sum(1 for issue in issues if issue['severity'] == severity) for severity in ('error', 'warning', 'suggestion')}
        return {
            'status': 'failed' if counts['error'] else ('warning' if counts['warning'] else 'passed'),
            'can_run': counts['error'] == 0,
            'can_publish': counts['error'] == 0,
            'counts': counts,
            'issues': issues,
        }
