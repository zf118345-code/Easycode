from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.capabilities import CapabilityContext, CapabilitySpec, capability_registry
from core.expressions import ExpressionError, evaluate_expression


class CapabilityError(RuntimeError):
    pass


class CapabilityService:
    """Discovery, contract validation and cancellable invocation for reusable capabilities."""

    _lock = threading.RLock()
    _fingerprints: dict[str, str] = {}
    _scope_specs: dict[str, list[CapabilitySpec]] = {}
    _scope_errors: dict[str, list[dict[str, str]]] = {}

    @staticmethod
    def _shared_root() -> Path:
        explicit = os.environ.get('EASYCODE_CAPABILITY_HOME')
        if explicit:
            return Path(explicit).expanduser().resolve()
        local = os.environ.get('LOCALAPPDATA')
        return (Path(local) / 'EasyCode' / 'capabilities' if local else Path.home() / '.easycode-app' / 'capabilities').resolve()

    @staticmethod
    def _package_roots(project_path: str | None) -> list[tuple[Path, str]]:
        roots: list[tuple[Path, str]] = []
        if project_path:
            project_root = Path(project_path).resolve() / 'capabilities'
            if project_root.is_dir():
                roots.extend((path, f'project:{Path(project_path).resolve()}:{path.name}') for path in sorted(project_root.iterdir()) if path.is_dir())
        shared = CapabilityService._shared_root()
        if shared.is_dir():
            roots.extend((path, f'shared:{path.name}') for path in sorted(shared.iterdir()) if path.is_dir())
        return roots

    @staticmethod
    def _fingerprint(roots: list[tuple[Path, str]]) -> str:
        digest = hashlib.sha256()
        for root, source in roots:
            digest.update(source.encode('utf-8'))
            for path in sorted(root.rglob('*')):
                if path.is_file() and path.suffix.lower() in {'.json', '.py'}:
                    stat = path.stat()
                    digest.update(str(path.relative_to(root)).encode('utf-8'))
                    digest.update(f'{stat.st_size}:{stat.st_mtime_ns}'.encode('ascii'))
        return digest.hexdigest()

    @staticmethod
    def _entry_target(package_root: Path, entry: str) -> tuple[Path, str, list[str]]:
        module_ref, separator, function_name = str(entry or '').partition(':')
        if not separator or not module_ref or not function_name:
            raise CapabilityError(f'能力入口必须为 module.py:function: {entry!r}')
        module_ref = module_ref.strip().replace('\\', '/')
        if module_ref.endswith('.py'):
            relative = module_ref
        else:
            relative = module_ref.replace('.', '/') + '.py'
        path = (package_root / relative).resolve()
        if package_root.resolve() not in path.parents or not path.is_file():
            raise CapabilityError(f'能力入口越界或不存在: {entry}')
        parts = list(Path(relative).with_suffix('').parts)
        if not all(part.isidentifier() for part in parts):
            raise CapabilityError(f'能力模块路径必须是合法 Python 标识符: {module_ref}')
        try:
            compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
        except (OSError, SyntaxError, UnicodeError) as exc:
            raise CapabilityError(f'能力入口语法校验失败 {entry}: {exc}') from exc
        return path, function_name.strip(), parts

    @staticmethod
    def _package_code_fingerprint(package_root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(package_root.rglob('*.py')):
            stat = path.stat()
            digest.update(str(path.relative_to(package_root)).encode('utf-8'))
            digest.update(f'{stat.st_size}:{stat.st_mtime_ns}'.encode('ascii'))
        return digest.hexdigest()[:16]

    @classmethod
    def _load_entry(cls, package_root: Path, entry: str, source: str):
        path, function_name, parts = cls._entry_target(package_root, entry)
        identity = f'{source}:{package_root.resolve()}:{cls._package_code_fingerprint(package_root)}'
        namespace = f'easycode_capability_{hashlib.sha256(identity.encode()).hexdigest()[:20]}'
        module_name = '.'.join([namespace, *parts])

        # Each capability package receives a private import namespace.  This
        # permits ``from .helper import ...`` without placing package folders
        # on sys.path or allowing two projects' helper.py files to collide.
        with cls._lock:
            if namespace not in sys.modules:
                package = types.ModuleType(namespace)
                package.__package__ = namespace
                package.__path__ = [str(package_root)]
                sys.modules[namespace] = package
            for index in range(1, len(parts)):
                parent_name = '.'.join([namespace, *parts[:index]])
                if parent_name in sys.modules:
                    continue
                parent = types.ModuleType(parent_name)
                parent.__package__ = parent_name
                parent.__path__ = [str(package_root.joinpath(*parts[:index]))]
                sys.modules[parent_name] = parent
            existing = sys.modules.get(module_name)
            if existing is None:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    raise CapabilityError(f'无法加载能力模块: {path.name}')
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    sys.modules.pop(module_name, None)
                    raise
            else:
                module = existing
        function = getattr(module, function_name, None)
        if not callable(function):
            raise CapabilityError(f'能力入口不可调用: {entry}')
        return function

    @classmethod
    def _lazy_entry(cls, package_root: Path, entry: str, source: str):
        # Validate path and syntax during discovery, but do not execute custom
        # developer code until the graph actually invokes the capability.
        cls._entry_target(package_root, entry)
        loaded = None
        load_lock = threading.Lock()

        def invoke(context, **inputs):
            nonlocal loaded
            if loaded is None:
                with load_lock:
                    if loaded is None:
                        loaded = cls._load_entry(package_root, entry, source)
            signature = inspect.signature(loaded)
            if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
                return loaded(context, **inputs)
            return loaded(context, inputs)

        invoke.__easycode_worker__ = {
            'package_root': str(package_root.resolve()),
            'entry': str(entry),
            'source': str(source),
        }

        return invoke

    @classmethod
    def create_package(
        cls,
        project_path: str,
        *,
        scope: str,
        package_id: str,
        function_name: str,
        display_name: str = '',
        description: str = '',
    ) -> dict[str, Any]:
        clean_package = str(package_id or '').strip().lower()
        clean_function = str(function_name or '').strip().lower()
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,63}', clean_package):
            raise CapabilityError('能力包ID必须以小写字母开头，只能包含小写字母、数字和下划线（2-64位）')
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', clean_function):
            raise CapabilityError('函数ID必须以小写字母开头，只能包含小写字母、数字和下划线')
        if str(scope or 'project').lower() == 'shared':
            parent = cls._shared_root()
            source_label = 'shared'
        else:
            if not project_path:
                raise CapabilityError('创建项目能力前必须打开项目')
            parent = Path(project_path).resolve() / 'capabilities'
            source_label = 'project'
        parent.mkdir(parents=True, exist_ok=True)
        destination = parent / clean_package
        if destination.exists():
            raise CapabilityError(f'能力包已存在: {clean_package}')
        temp_root = Path(tempfile.mkdtemp(prefix='.capability-', dir=str(parent)))
        try:
            capability_id = f'{clean_package}.{clean_function}'
            manifest = {
                'package_id': clean_package,
                'version': '1.0.0',
                'functions': [{
                    'id': capability_id,
                    'name': str(display_name or clean_function),
                    'description': str(description or ''),
                    'entry': 'main.py:run',
                    'idempotent': False,
                    'timeout_ms': 30000,
                    'permissions': [],
                    'inputs': [],
                    'outputs': [{'name': 'result', 'type': 'any'}],
                }],
            }
            (temp_root / 'capability.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (temp_root / 'main.py').write_text(
                '"""EasyCode capability. Edit inputs/outputs/permissions in capability.json."""\n\n'
                'def run(context, **inputs):\n'
                '    context.log("能力开始执行")\n'
                '    return {"success": True, "data": {"result": None}}\n',
                encoding='utf-8',
            )
            os.replace(temp_root, destination)
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise
        cls.discover(project_path, force=True)
        return {'id': capability_id, 'package_id': clean_package, 'scope': source_label, 'path': str(destination)}

    @classmethod
    def _load_package(cls, root: Path, source: str) -> list[CapabilitySpec]:
        manifest_path = root / 'capability.json'
        if not manifest_path.is_file():
            return []
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        except Exception as exc:
            raise CapabilityError(f'能力清单无法读取 {manifest_path}: {exc}') from exc
        if not isinstance(manifest, dict):
            raise CapabilityError(f'能力清单必须是JSON对象: {manifest_path}')
        package_id = str(manifest.get('package_id') or root.name).strip()
        package_version = str(manifest.get('version') or '1.0.0').strip()
        functions = manifest.get('functions') or []
        if not isinstance(functions, list):
            raise CapabilityError(f'能力清单 functions 必须是数组: {manifest_path}')
        loaded = []
        for item in functions:
            if not isinstance(item, dict):
                raise CapabilityError(f'能力声明必须是对象: {manifest_path}')
            capability_id = str(item.get('id') or '').strip()
            if not capability_id or '.' not in capability_id:
                raise CapabilityError(f'能力ID应使用 package.function 形式: {capability_id!r}')
            entry = str(item.get('entry') or '')
            function = cls._lazy_entry(root, entry, source)
            try:
                timeout_ms = max(1, int(item.get('timeout_ms') or 30000))
            except (TypeError, ValueError) as exc:
                raise CapabilityError(f'能力 {capability_id} timeout_ms 必须是整数') from exc
            loaded.append(CapabilitySpec(
                capability_id=capability_id,
                version=str(item.get('version') or package_version),
                entry=function,
                name=str(item.get('name') or capability_id),
                description=str(item.get('description') or ''),
                inputs=tuple(dict(value) for value in (item.get('inputs') or [])),
                outputs=tuple(dict(value) for value in (item.get('outputs') or [])),
                permissions=frozenset(str(value) for value in (item.get('permissions') or [])),
                timeout_ms=timeout_ms,
                idempotent=bool(item.get('idempotent', False)),
                package_id=package_id,
                source=source,
            ))
        return loaded

    @classmethod
    def discover(cls, project_path: str | None = None, *, force: bool = False) -> list[dict[str, Any]]:
        roots = cls._package_roots(project_path)
        fingerprint = cls._fingerprint(roots)
        scope = str(Path(project_path).resolve()) if project_path else '<none>'
        with cls._lock:
            if not force and cls._fingerprints.get(scope) == fingerprint:
                builtins = [spec for spec in capability_registry.list() if spec.source == 'builtin']
                result = [spec.public() for spec in [*builtins, *cls._scope_specs.get(scope, [])]]
                errors = cls._scope_errors.get(scope, [])
                if errors:
                    result.append({'id': '__discovery_errors__', 'name': '能力加载错误', 'version': '0', 'errors': errors, 'source': 'runtime'})
                return result
            errors = []
            loaded_specs = []
            identities: dict[tuple[str, str], str] = {}
            for root, source in roots:
                try:
                    for spec in cls._load_package(root, source):
                        identity = (spec.capability_id, spec.version)
                        if identity in identities:
                            errors.append({
                                'source': source,
                                'message': f'能力 {spec.capability_id}@{spec.version} 与 {identities[identity]} 重复，已保留先加载的定义',
                            })
                            continue
                        identities[identity] = source
                        loaded_specs.append(spec)
                except CapabilityError as exc:
                    errors.append({'source': source, 'message': str(exc)})
            cls._scope_specs[scope] = loaded_specs
            cls._scope_errors[scope] = errors
            cls._fingerprints[scope] = fingerprint
        builtins = [spec for spec in capability_registry.list() if spec.source == 'builtin']
        result = [spec.public() for spec in [*builtins, *loaded_specs]]
        if errors:
            result.append({'id': '__discovery_errors__', 'name': '能力加载错误', 'version': '0', 'errors': errors, 'source': 'runtime'})
        return result

    @classmethod
    def resolve(cls, project_path: str | None, capability_id: str, version: str | None = None) -> CapabilitySpec | None:
        cls.discover(project_path)
        scope = str(Path(project_path).resolve()) if project_path else '<none>'
        clean_version = str(version or '').strip()
        candidates = [
            spec for spec in cls._scope_specs.get(scope, [])
            if spec.capability_id == capability_id and (not clean_version or spec.version == clean_version)
        ]
        if candidates:
            def version_key(spec: CapabilitySpec):
                return tuple((0, int(part)) if part.isdigit() else (1, part) for part in spec.version.replace('-', '.').split('.'))
            return sorted(candidates, key=version_key)[-1]
        return capability_registry.resolve(capability_id, clean_version or None)

    @staticmethod
    def _coerce(value: Any, declaration: dict[str, Any]) -> Any:
        expected = str(declaration.get('type') or 'any').lower()
        if value is None:
            return None
        try:
            if expected in {'any', 'json', 'object'}:
                return value
            if expected in {'str', 'string'}:
                return str(value)
            if expected in {'int', 'integer'}:
                return int(value)
            if expected in {'float', 'number'}:
                return float(value)
            if expected in {'bool', 'boolean'}:
                if isinstance(value, str):
                    return value.strip().lower() in {'1', 'true', 'yes', 'on'}
                return bool(value)
            if expected == 'list':
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                raise ValueError('不是数组')
            if expected in {'dict', 'map'}:
                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                raise ValueError('不是对象')
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CapabilityError(f'输入 {declaration.get("name")} 无法转换为 {expected}: {exc}') from exc
        return value

    @staticmethod
    def _scoped_variable_key(reference: str, *, writable: bool = False) -> str | None:
        text = str(reference or '').strip()
        scopes = {
            '$var.': '', '$ctx.': '', '$local.': '__local__:', '$param.': '__param__:',
        }
        for prefix, storage_prefix in scopes.items():
            if text.startswith(prefix) and len(text) > len(prefix):
                if writable and prefix == '$param.':
                    return None
                return f'{storage_prefix}{text[len(prefix):]}'
        brace_scopes = {
            '$var{': '', '$ctx{': '', '$local{': '__local__:', '$param{': '__param__:',
        }
        for prefix, storage_prefix in brace_scopes.items():
            if text.startswith(prefix) and text.endswith('}') and len(text) > len(prefix) + 1:
                if writable and prefix == '$param{':
                    return None
                return f'{storage_prefix}{text[len(prefix):-1]}'
        return None

    @classmethod
    def _resolve_binding(cls, raw: Any, executor) -> Any:
        if not isinstance(raw, str):
            return deepcopy(raw)
        stripped = raw.strip()
        scoped_key = cls._scoped_variable_key(stripped)
        if scoped_key is not None:
            return deepcopy(executor.variables.get(scoped_key))
        if stripped.startswith('='):
            try:
                return evaluate_expression(stripped[1:], executor)
            except ExpressionError as exc:
                raise CapabilityError(f'能力输入表达式错误: {exc}') from exc
        return deepcopy(raw)

    @classmethod
    def build_inputs(cls, spec: CapabilitySpec, bindings: list[dict[str, Any]], executor) -> dict[str, Any]:
        bound = {str(item.get('name') or ''): item.get('value') for item in (bindings or []) if isinstance(item, dict)}
        result = {}
        for declaration in spec.inputs:
            name = str(declaration.get('name') or '').strip()
            if not name:
                continue
            if name in bound:
                value = cls._resolve_binding(bound[name], executor)
            elif 'default' in declaration:
                value = deepcopy(declaration.get('default'))
            elif declaration.get('required'):
                raise CapabilityError(f'缺少必填能力输入: {name}')
            else:
                value = None
            result[name] = cls._coerce(value, declaration)
        unknown = sorted(set(bound) - {str(item.get('name') or '') for item in spec.inputs})
        if unknown:
            raise CapabilityError(f'能力不接受输入: {", ".join(unknown)}')
        return result

    @staticmethod
    def normalize_result(raw: Any) -> dict[str, Any]:
        if raw is None:
            return {'success': True, 'code': 'OK', 'message': '', 'data': {}}
        if isinstance(raw, bool):
            return {'success': raw, 'code': 'OK' if raw else 'FAILED', 'message': '', 'data': {}}
        if not isinstance(raw, dict):
            return {'success': True, 'code': 'OK', 'message': '', 'data': {'result': raw}}
        success = bool(raw.get('success', True))
        data = raw.get('data')
        if not isinstance(data, dict):
            data = {key: value for key, value in raw.items() if key not in {'success', 'code', 'message', 'error'}}
        return {
            'success': success,
            'code': str(raw.get('code') or ('OK' if success else 'FAILED')),
            'message': str(raw.get('message') or raw.get('error') or ''),
            'data': data,
        }

    @staticmethod
    def _read_path(data: dict[str, Any], source: str):
        clean = str(source or '').removeprefix('data.')
        value: Any = data
        if not clean:
            return value
        for part in clean.split('.'):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    @classmethod
    def apply_outputs(cls, result: dict[str, Any], bindings: list[dict[str, Any]], executor) -> None:
        for binding in bindings or []:
            if not isinstance(binding, dict):
                continue
            source = str(binding.get('source') or binding.get('name') or '').strip()
            target = str(binding.get('target') or '').strip()
            if not source or not target:
                continue
            scoped_key = cls._scoped_variable_key(target, writable=True)
            if scoped_key is None or target.startswith(('$param.', '$param{')):
                raise CapabilityError(f'能力输出目标必须为 $var.name、$ctx.name 或函数内的 $local.name: {target}')
            executor.variables[scoped_key] = deepcopy(cls._read_path(result.get('data') or {}, source))

    @staticmethod
    def _worker_rpc(context: CapabilityContext, method: str, args: list, kwargs: dict):
        if method == 'set_variable':
            context.set_variable(*args, **kwargs)
            return True
        if method == 'platform_store':
            permission, operation, call_args, call_kwargs = args
            allowed = {
                'get_state', 'set_state', 'delete_state', 'publish_message', 'claim_messages', 'ack_message',
                'acquire_lease', 'renew_lease', 'release_lease', 'list_schedules', 'save_schedule', 'delete_schedule',
            }
            if operation not in allowed:
                raise PermissionError(f'能力工作进程不允许调用平台方法: {operation}')
            store = context.platform_store(str(permission))
            return getattr(store, operation)(*(call_args or []), **(call_kwargs or {}))
        allowed_methods = {
            'ocr_region', 'swipe', 'send_remote_message', 'claim_remote_messages',
            'ack_remote_message', 'acquire_remote_lease', 'renew_remote_lease', 'release_remote_lease',
        }
        if method not in allowed_methods:
            raise PermissionError(f'能力工作进程请求了未知方法: {method}')
        return getattr(context, method)(*args, **kwargs)

    @classmethod
    def _invoke_isolated(
        cls,
        executor,
        spec: CapabilitySpec,
        inputs: dict[str, Any],
        timeout_ms: int,
    ) -> dict[str, Any]:
        metadata = getattr(spec.entry, '__easycode_worker__', None)
        if not isinstance(metadata, dict):
            raise CapabilityError(f'能力 {spec.capability_id} 缺少隔离运行元数据')
        command = (
            [sys.executable, '--capability-worker']
            if getattr(sys, 'frozen', False)
            else [sys.executable, '-m', 'core.services.capability_worker']
        )
        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        environment = dict(os.environ)
        environment['PYTHONIOENCODING'] = 'utf-8'
        try:
            process = subprocess.Popen(
                command,
                cwd=str(Path(__file__).resolve().parents[2]),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=creation_flags,
                env=environment,
            )
        except OSError as exc:
            raise CapabilityError(f'无法启动能力隔离进程: {exc}') from exc
        output_queue: queue.Queue = queue.Queue()
        stderr_lines: list[str] = []

        def read_stdout():
            assert process.stdout is not None
            for line in process.stdout:
                output_queue.put(line)
            output_queue.put(None)

        def read_stderr():
            assert process.stderr is not None
            for line in process.stderr:
                stderr_lines.append(line.rstrip())
                if len(stderr_lines) > 50:
                    del stderr_lines[:10]

        threading.Thread(target=read_stdout, name=f'capability-out-{spec.capability_id}', daemon=True).start()
        threading.Thread(target=read_stderr, name=f'capability-err-{spec.capability_id}', daemon=True).start()
        cancellation = threading.Event()
        context = CapabilityContext(executor, spec, cancellation)
        request = {
            'package_root': metadata['package_root'],
            'entry': metadata['entry'],
            'inputs': inputs,
            'spec': spec.public(),
            'project_path': str(getattr(executor, 'project_dir', '') or ''),
            'variables': deepcopy(getattr(executor, 'variables', {}) or {}),
        }
        try:
            assert process.stdin is not None
            process.stdin.write(json.dumps(request, ensure_ascii=False, default=str) + '\n')
            process.stdin.flush()
            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                if bool(getattr(executor, 'is_stopped', False)):
                    cancellation.set()
                    process.terminate()
                    return {'success': False, 'code': 'CANCELLED', 'message': '能力调用已被停止', 'data': {}}
                try:
                    line = output_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                if line is None:
                    detail = '\n'.join(stderr_lines[-8:]).strip()
                    return {'success': False, 'code': 'WORKER_EXITED', 'message': f'能力隔离进程提前退出{f": {detail}" if detail else ""}', 'data': {}}
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    stderr_lines.append(line.rstrip())
                    continue
                event_type = event.get('type')
                if event_type == 'log':
                    context.log(event.get('message') or '', event.get('level') or 'info')
                elif event_type == 'progress':
                    message = str(event.get('message') or '')
                    if message:
                        context.log(f'{message}（{event.get("current")}/{event.get("total") or "?"}）')
                elif event_type == 'rpc':
                    response = {'type': 'rpc_response', 'id': event.get('id'), 'ok': True}
                    try:
                        response['result'] = cls._worker_rpc(context, str(event.get('method') or ''), list(event.get('args') or []), dict(event.get('kwargs') or {}))
                    except Exception as exc:
                        response.update({'ok': False, 'error': str(exc)})
                    process.stdin.write(json.dumps(response, ensure_ascii=False, default=str) + '\n')
                    process.stdin.flush()
                elif event_type == 'result':
                    return cls.normalize_result(event.get('result'))
                elif event_type == 'error':
                    detail = str(event.get('traceback') or '').strip()
                    if detail:
                        context.log(detail, 'error')
                    return {'success': False, 'code': 'EXCEPTION', 'message': str(event.get('error') or '能力执行异常'), 'data': {}}
            cancellation.set()
            process.terminate()
            return {'success': False, 'code': 'TIMEOUT', 'message': f'能力调用超时（{timeout_ms}ms），隔离进程已终止', 'data': {}}
        finally:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=1.0)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    stream.close() if stream else None
                except Exception:
                    pass

    @classmethod
    def invoke(
        cls,
        executor,
        capability_id: str,
        *,
        version: str = '',
        input_bindings: list[dict[str, Any]] | None = None,
        output_bindings: list[dict[str, Any]] | None = None,
        timeout_ms: int | None = None,
        retry_count: int = 0,
        retry_interval_ms: int = 200,
    ) -> dict[str, Any]:
        project_path = getattr(executor, 'project_dir', '') or None
        spec = cls.resolve(project_path, capability_id, version or None)
        if spec is None:
            raise CapabilityError(f'能力不存在: {capability_id}{f"@{version}" if version else ""}')
        retries = max(0, min(20, int(retry_count or 0)))
        if retries and not spec.idempotent:
            raise CapabilityError(f'能力 {spec.capability_id} 未声明幂等，禁止自动重试')
        inputs = cls.build_inputs(spec, input_bindings or [], executor)
        effective_timeout = max(1, min(24 * 60 * 60 * 1000, int(timeout_ms or spec.timeout_ms)))
        last_result = None
        for attempt in range(retries + 1):
            if spec.source != 'builtin' and getattr(spec.entry, '__easycode_worker__', None):
                last_result = cls._invoke_isolated(executor, spec, inputs, effective_timeout)
                if last_result.get('success') or attempt >= retries:
                    break
                time.sleep(max(0, int(retry_interval_ms or 0)) / 1000.0)
                continue
            cancellation = threading.Event()
            response_queue: queue.Queue = queue.Queue(maxsize=1)
            capability_context = CapabilityContext(executor, spec, cancellation)

            def worker():
                try:
                    signature = inspect.signature(spec.entry)
                    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
                        raw = spec.entry(capability_context, **inputs)
                    else:
                        raw = spec.entry(capability_context, inputs)
                    response_queue.put(('ok', raw))
                except BaseException as exc:  # daemon worker must always report a terminal result
                    response_queue.put(('error', exc))

            thread = threading.Thread(target=worker, name=f'easycode-capability-{spec.capability_id}', daemon=True)
            thread.start()
            deadline = time.monotonic() + effective_timeout / 1000.0
            outcome = None
            while time.monotonic() < deadline:
                if bool(getattr(executor, 'is_stopped', False)):
                    cancellation.set()
                    return {'success': False, 'code': 'CANCELLED', 'message': '能力调用已被停止', 'data': {}}
                try:
                    outcome = response_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                    break
                except queue.Empty:
                    continue
            if outcome is None:
                cancellation.set()
                last_result = {'success': False, 'code': 'TIMEOUT', 'message': f'能力调用超时（{effective_timeout}ms）', 'data': {}}
            elif outcome[0] == 'error':
                last_result = {'success': False, 'code': 'EXCEPTION', 'message': str(outcome[1]), 'data': {}}
            else:
                last_result = cls.normalize_result(outcome[1])
            if last_result.get('success') or attempt >= retries:
                break
            time.sleep(max(0, int(retry_interval_ms or 0)) / 1000.0)
        assert last_result is not None
        cls.apply_outputs(last_result, output_bindings or [], executor)
        last_result['capability'] = spec.public()
        return last_result
