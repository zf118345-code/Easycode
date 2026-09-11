"""Source-free published extension execution for the Windows Player.

This module intentionally contains no package discovery, development entry,
trust-store mutation, signing-key creation, workspace context, or authoring
service.  It accepts only the sealed runtime projection already present in a
verified ``.ecplayer`` extraction root.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .extension_schema_v6 import (
    LOCK_FILE,
    ExtensionSchemaError,
    PublishedExtensionV1,
    load_easycode_lock,
    resolve_package_path,
    validate_published_extension,
)
from .runtime import RuntimeFailure


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionSchemaError(f'发布扩展描述无法读取：{path.name}（{exc}）') from exc
    if not isinstance(value, dict):
        raise ExtensionSchemaError(f'发布扩展描述必须是 JSON 对象：{path.name}')
    return value


def _published_call(
    runtime_root: Path,
    function_id: str,
    arguments: dict[str, Any],
    variables: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    lock_path = runtime_root / 'runtime' / LOCK_FILE
    if not lock_path.is_file():
        raise RuntimeFailure(
            '发布包缺少扩展运行锁',
            error_id='extension.runtime_invalid',
        )
    try:
        lock = load_easycode_lock(lock_path)
        contract_model = None
        published_variant = None
        for record in lock.extensions:
            descriptor_path = (
                runtime_root / 'runtime' / 'extensions' / record.package_id / 'extension.json'
            )
            if not descriptor_path.is_file():
                raise ExtensionSchemaError(f'缺少发布扩展描述：{record.package_id}')
            descriptor = PublishedExtensionV1.model_validate(_read_json(descriptor_path))
            validate_published_extension(runtime_root, descriptor, record)
            candidate_contract = next(
                (
                    item for item in descriptor.function_contracts
                    if item.function_id == function_id
                ),
                None,
            )
            if candidate_contract is None:
                continue
            contract_model = candidate_contract
            published_variant = next(
                (
                    item for item in descriptor.variants
                    if item.host == 'windows'
                    and item.runtime == 'python-worker-3.12'
                    and function_id in item.entrypoints
                ),
                None,
            )
            break
        if contract_model is None:
            raise RuntimeFailure(
                '发布包未锁定该扩展函数',
                error_id='extension.not_available',
            )
        if published_variant is None:
            raise RuntimeFailure(
                '当前宿主没有发布的扩展变体',
                error_id='extension.variant_missing',
            )
        contract = contract_model.model_dump(mode='json')
        request = {
            'mode': 'sealed',
            'artifact_path': str(resolve_package_path(runtime_root, published_variant.artifact_path)),
            'entrypoint': published_variant.entrypoints[function_id],
            'arguments': arguments,
            'variables': variables,
        }
        return contract, request, runtime_root
    except RuntimeFailure:
        raise
    except Exception as exc:
        raise RuntimeFailure(
            f'发布扩展运行闭包校验失败：{exc}',
            error_id='extension.runtime_invalid',
        ) from exc


def invoke_published_extension(
    project_path: str,
    function_id: str,
    arguments: dict[str, Any],
    variables: dict[str, Any],
    cancelled: Callable[[], bool],
    emit: Callable[[str, str], None],
) -> Any:
    """Validate one sealed call and execute it in the packaged worker."""

    contract, request, worker_cwd = _published_call(
        Path(project_path).resolve(),
        str(function_id or ''),
        arguments,
        variables,
    )
    try:
        parameter_names = {
            str(item.get('parameter_id') or ''): str(item.get('name') or '')
            for item in contract.get('parameters') or []
        }
        unknown_arguments = sorted(set(arguments) - set(parameter_names))
        if unknown_arguments:
            raise RuntimeFailure(
                f'扩展参数不在锁定契约中：{unknown_arguments[0]}',
                error_id='extension.arguments_invalid',
            )
        request['arguments'] = {
            parameter_names[parameter_id]: value
            for parameter_id, value in arguments.items()
            if parameter_names.get(parameter_id)
        }
        request['variables'] = {
            key: value
            for key, value in variables.items()
            if not str(key).startswith('__')
        }
        project_variables = variables.get('__project__')
        if isinstance(project_variables, dict):
            request['variables']['project'] = project_variables
        encoded = json.dumps(request, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except RuntimeFailure:
        raise
    except (TypeError, ValueError) as exc:
        raise RuntimeFailure(
            f'扩展参数无法序列化：{exc}',
            error_id='extension.arguments_invalid',
        ) from exc

    worker = Path(__file__).with_name('extension_worker_v6.py')
    worker_command = (
        [sys.executable, '--extension-worker']
        if getattr(sys, 'frozen', False)
        else [sys.executable, str(worker)]
    )
    worker_environment = os.environ.copy()
    worker_environment['PYTHONUTF8'] = '1'
    worker_environment['PYTHONIOENCODING'] = 'utf-8'
    worker_environment['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        process = subprocess.Popen(
            worker_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(worker_cwd),
            env=worker_environment,
        )
    except OSError as exc:
        raise RuntimeFailure(
            f'扩展 Worker 无法启动：{exc}',
            error_id='extension.worker_unavailable',
        ) from exc

    deadline = time.monotonic() + (int(contract.get('timeout_ms') or 30_000) / 1000)
    input_value: bytes | None = encoded
    while True:
        if cancelled():
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
            if process.poll() is None:
                process.kill()
            raise RuntimeFailure('扩展调用已取消', error_id='runtime.cancelled')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            process.wait(timeout=2)
            raise RuntimeFailure('扩展 Worker 执行超时', error_id='extension.timeout')
        try:
            stdout, stderr = process.communicate(
                input=input_value,
                timeout=min(0.1, remaining),
            )
            break
        except subprocess.TimeoutExpired:
            input_value = None

    try:
        response = json.loads(stdout.decode('utf-8'))
        if not isinstance(response, dict):
            raise ValueError('响应不是 JSON 对象')
    except Exception as exc:
        detail = stderr.decode('utf-8', errors='replace').strip()[:1000]
        raise RuntimeFailure(
            f'扩展 Worker 返回无效数据：{detail or exc}',
            error_id='extension.worker_protocol',
        ) from exc
    for log in response.get('logs') or []:
        if isinstance(log, dict):
            emit(str(log.get('level') or 'info'), str(log.get('message') or ''))
    if not response.get('ok'):
        error = response.get('error') if isinstance(response.get('error'), dict) else {}
        raise RuntimeFailure(
            str(error.get('message') or '扩展 Worker 执行失败'),
            error_id=str(error.get('code') or 'extension.worker_failed'),
        )
    return response.get('result')


__all__ = ['invoke_published_extension']

