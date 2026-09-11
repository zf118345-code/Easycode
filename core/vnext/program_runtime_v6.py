"""Format-6 ECIR adapter for the existing isolated vNext runtime.

ProgramDocument compilation intentionally emits stable function and parameter
IDs.  This adapter is a validation/copy boundary: it never mutates compiler
ECIR, never translates stable IDs into display names, and refuses every opcode
whose format-6 runtime semantics have not been verified.
"""

from __future__ import annotations

import copy
import os
from typing import Any

from .function_contracts_v6 import official_function_registry_v6
from .runtime import RuntimeFailure

_EXECUTABLE_OPCODES = {
    'log.write',
    'wait.duration',
    'wait.until',
    'random.integer',
    'time.now',
    'time.today',
    'project.data_directory',
    'data.assign_local',
    'data.assign_project',
    'call.project',
    'control.if',
    'control.repeat',
    'control.while',
    'control.for_each',
    'control.for_each_map',
    'control.break',
    'control.continue',
    'control.fail',
    'control.return',
    'control.try',
    'control.target_scope',
    'control.listen',
    'target.wait_online',
    'target.status',
    'target.capture_frame',
    'frame.save', 'frame.crop_region', 'vision.compare_samples',
    'color.read',
    'color.find',
    'clipboard.read_text', 'clipboard.write_text',
    'host.app.start',
    'host.app.wait_exit',
    'host.app.is_running',
    'host.app.stop',
    'window.find',
    'window.current',
    'window.activate',
    'window.close',
    'window.status',
    'window.move',
    'window.resize',
    'window.ensure_visible',
    'window.set_display_state',
    'vision.find',
    'vision.find_all',
    'text.recognize',
    'input.click',
    'input.text',
    'input.scroll',
    'input.drag',
    'input.key',
    'input.move_pointer',
    'control.find',
    'control.click',
    'control.click_selector',
    'control.read_text',
    'control.input_text',
    'control.read_status',
    'control.focus',
    'control.set_value',
    'control.select',
    'control.toggle',
    'control.scroll_into_view',
    'file.exists',
    'file.read_text',
    'file.write_text',
    'file.append_text',
    'file.replace_text',
    'file.read_json',
    'file.write_json',
    'file.delete',
    'file.copy',
    'file.move',
    'directory.exists',
    'directory.create',
    'directory.list',
    'directory.copy',
    'directory.move',
    'directory.delete',
    'directory.delete_tree',
    'network.request',
    'network.upload_file',
    'network.download_file',
    'message.send',
    'message.wait_receive',
    'message.wait_read',
    'message.cancel',
    'standard.window.wait_visible',
    'standard.control.wait_visible',
    'standard.control.wait_hidden',
    'standard.image.wait_visible',
    'standard.image.wait_hidden',
    'standard.image.click_once',
    'standard.image.click_until_hidden',
    'standard.image.click_position_until_visible',
    'standard.image.click_position_until_hidden',
    'standard.text.match',
    'standard.text.wait_visible',
}


def _adapt_instruction(
    instruction: dict[str, Any],
    debug_statements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapted = copy.deepcopy(instruction)
    statement_source = (debug_statements or {}).get(str(adapted.get('instruction_id') or ''))
    if isinstance(statement_source, dict):
        adapted['source'] = copy.deepcopy(statement_source)
    opcode = str(adapted.get('opcode') or '')
    if opcode not in _EXECUTABLE_OPCODES:
        raise RuntimeFailure(f'格式 6 指令尚未经过运行验证：{opcode or "<empty>"}')
    arguments = dict(adapted.get('arguments') or {})
    if opcode == 'control.if':
        arguments['then'] = [_adapt_instruction(item, debug_statements) for item in arguments.get('then') or []]
        arguments['additional_branches'] = [
            {
                **dict(branch),
                'body': [_adapt_instruction(item, debug_statements) for item in branch.get('body') or []],
            }
            for branch in arguments.get('additional_branches') or []
        ]
        arguments['otherwise'] = [_adapt_instruction(item, debug_statements) for item in arguments.get('otherwise') or []]
    elif opcode in {'control.repeat', 'control.while', 'control.for_each', 'control.for_each_map'}:
        arguments['body'] = [_adapt_instruction(item, debug_statements) for item in arguments.get('body') or []]
    elif opcode == 'control.try':
        arguments['body'] = [_adapt_instruction(item, debug_statements) for item in arguments.get('body') or []]
        arguments['catches'] = [
            {
                **dict(clause),
                'body': [_adapt_instruction(item, debug_statements) for item in clause.get('body') or []],
            }
            for clause in arguments.get('catches') or []
        ]
        arguments['finally'] = [
            _adapt_instruction(item, debug_statements) for item in arguments.get('finally') or []
        ]
    elif opcode == 'control.target_scope':
        target = dict(arguments.get('target') or {})
        if target.get('kind') != 'target_ref' or not str(target.get('target_id') or ''):
            raise RuntimeFailure(
                '目标作用域缺少稳定 target_id',
                error_id='target.reference_invalid',
            )
        arguments['body'] = [
            _adapt_instruction(item, debug_statements) for item in arguments.get('body') or []
        ]
    elif opcode == 'control.listen':
        event_source = dict(arguments.get('event_source') or {})
        if event_source.get('kind') != 'message':
            raise RuntimeFailure(
                '监听声明缺少消息事件源',
                error_id='runtime.listener_contract_invalid',
            )
        if not str(arguments.get('receive_slot') or ''):
            raise RuntimeFailure(
                '监听声明缺少接收绑定',
                error_id='runtime.listener_contract_invalid',
            )
        if not str(arguments.get('handler_function_id') or ''):
            raise RuntimeFailure(
                '监听声明缺少处理项目函数',
                error_id='runtime.listener_contract_invalid',
            )
    adapted['arguments'] = arguments
    return adapted


def adapt_program_ecir_for_runtime(ecir: dict[str, Any], *, project_path: str = '') -> dict[str, Any]:
    """Return an isolated runtime plan while preserving the stable-ID ECIR."""

    if int(ecir.get('program_model_version') or 0) != 1:
        raise RuntimeFailure('运行器不支持此 ProgramDocument 版本')
    plan = copy.deepcopy(ecir)
    target_platform = str(plan.get('target_platform') or '')
    supported_platforms = tuple(plan.get('supported_platforms') or ())
    if target_platform and target_platform not in supported_platforms:
        raise RuntimeFailure(f'程序没有经过目标平台运行验证：{target_platform}')
    plan['project_path'] = str(project_path or plan.get('project_path') or '')
    if plan['project_path'] and not str(plan.get('runtime_data_directory') or ''):
        plan['runtime_data_directory'] = os.path.join(
            plan['project_path'], '.easycode', 'data',
        )
    targets = list(plan.get('targets') or [])
    target_ids = [str(item.get('target_id') or '') for item in targets if isinstance(item, dict)]
    if any(not item for item in target_ids) or len(set(target_ids)) != len(target_ids):
        raise RuntimeFailure(
            '目标运行闭包缺少稳定 ID 或包含重复 ID',
            error_id='target.closure_invalid',
        )
    debug_statements = dict((plan.get('debug_map') or {}).get('statements') or {})
    for definition in plan.get('functions') or []:
        definition['instructions'] = [
            _adapt_instruction(item, debug_statements)
            for item in definition.get('instructions') or []
        ]
    return plan


def assert_available_runtime_contracts_are_bound() -> None:
    """Fail tests if the visible catalog grows without a runtime binding."""

    unbound = {
        item['opcode']
        for item in official_function_registry_v6.available_catalog()
        if item['opcode'] not in _EXECUTABLE_OPCODES
    }
    if unbound:
        raise RuntimeFailure(f'可插入函数缺少运行绑定：{sorted(unbound)}')
    invalid = {
        item['function_id']
        for item in official_function_registry_v6.available_catalog()
        if not item.get('verified_platforms')
    }
    if invalid:
        raise RuntimeFailure(f'可插入函数没有已验证平台：{sorted(invalid)}')

    # Being named in the ECIR allow-list is not enough.  Every visible host
    # operation must also be owned by the concrete runtime adapter that will
    # execute it.  This catches "looks available, always fails at runtime"
    # regressions such as exposing recursive directory deletion before its
    # authorization-root service exists.
    from .file_runtime_v6 import FileRuntimeV6
    from .message_runtime_v6 import MessageRuntimeV6
    from .network_runtime_v6 import NetworkRuntimeV6
    from .platform_runtime_v6 import PlatformRuntimeV6
    from .standard_functions_v6 import StandardRuntimeV6
    from .target_runtime import TargetDriver, WindowsTargetDriver

    adapter_mismatches: set[str] = set()
    for item in official_function_registry_v6.available_catalog():
        opcode = str(item['opcode'])
        if opcode.startswith(('file.', 'directory.')) and not FileRuntimeV6.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode.startswith('standard.') and not StandardRuntimeV6.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode.startswith('message.') and not MessageRuntimeV6.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode.startswith('network.') and not NetworkRuntimeV6.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode.startswith(('host.app.', 'target.wait_', 'target.status')) and not PlatformRuntimeV6.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode.startswith(('window.', 'control.')) and not WindowsTargetDriver.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if opcode == 'input.move_pointer' and not WindowsTargetDriver.supports(opcode):
            adapter_mismatches.add(item['function_id'])
        if (
            opcode.startswith(('target.', 'frame.', 'color.', 'vision.', 'text.', 'input.'))
            and not opcode.startswith(('target.wait_', 'target.status'))
            and opcode != 'input.move_pointer'
            and not TargetDriver.supports(opcode)
        ):
            adapter_mismatches.add(item['function_id'])
    if adapter_mismatches:
        raise RuntimeFailure(
            f'可插入函数没有具体运行适配器：{sorted(adapter_mismatches)}'
        )


__all__ = ['adapt_program_ecir_for_runtime', 'assert_available_runtime_contracts_are_bound']
