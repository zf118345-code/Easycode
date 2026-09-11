"""Custom capability worker process using a small JSON-lines RPC protocol."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import json
import sys
import traceback
import types
from pathlib import Path


class WorkerRpc:
    def __init__(self, protocol, request: dict):
        self.protocol = protocol
        self.spec = request.get('spec') or {}
        self.project_path = str(request.get('project_path') or '')
        self.variables = dict(request.get('variables') or {})
        self._counter = 0

    @property
    def cancelled(self) -> bool:
        return False

    def _send(self, payload: dict) -> None:
        self.protocol.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')
        self.protocol.flush()

    def _rpc(self, method: str, *args, **kwargs):
        self._counter += 1
        call_id = self._counter
        self._send({'type': 'rpc', 'id': call_id, 'method': method, 'args': args, 'kwargs': kwargs})
        while True:
            line = sys.stdin.readline()
            if not line:
                raise RuntimeError('能力宿主已断开RPC通道')
            response = json.loads(line)
            if response.get('type') != 'rpc_response' or response.get('id') != call_id:
                continue
            if not response.get('ok'):
                raise RuntimeError(str(response.get('error') or 'RPC调用失败'))
            return response.get('result')

    def require(self, permission: str) -> None:
        if permission not in set(self.spec.get('permissions') or []):
            raise PermissionError(f'能力 {self.spec.get("id")} 未声明权限: {permission}')

    def log(self, message: str, level: str = 'info') -> None:
        self._send({'type': 'log', 'message': str(message), 'level': str(level or 'info')})

    def report_progress(self, current: int, total: int | None = None, message: str = '') -> None:
        self._send({'type': 'progress', 'current': int(current), 'total': int(total) if total is not None else None, 'message': str(message or '')})

    def get_variable(self, name: str, default=None):
        return self.variables.get(str(name), default)

    def set_variable(self, name: str, value) -> None:
        self.require('variables.write')
        self._rpc('set_variable', str(name), value)
        self.variables[str(name)] = value

    def platform_store(self, permission: str):
        self.require(permission)
        return PlatformProxy(self, permission)

    def ocr_region(self, region, **kwargs):
        self.require('screen.read')
        return self._rpc('ocr_region', region, **kwargs)

    def swipe(self, start, end, **kwargs):
        self.require('input.gesture')
        return self._rpc('swipe', start, end, **kwargs)

    def send_remote_message(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('send_remote_message', *args, **kwargs)

    def claim_remote_messages(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('claim_remote_messages', *args, **kwargs)

    def ack_remote_message(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('ack_remote_message', *args, **kwargs)

    def acquire_remote_lease(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('acquire_remote_lease', *args, **kwargs)

    def renew_remote_lease(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('renew_remote_lease', *args, **kwargs)

    def release_remote_lease(self, *args, **kwargs):
        self.require('network.coordinator')
        return self._rpc('release_remote_lease', *args, **kwargs)


class PlatformProxy:
    ALLOWED = {
        'get_state', 'set_state', 'delete_state', 'publish_message', 'claim_messages', 'ack_message',
        'acquire_lease', 'renew_lease', 'release_lease', 'list_schedules', 'save_schedule', 'delete_schedule',
    }

    def __init__(self, rpc: WorkerRpc, permission: str):
        self.rpc = rpc
        self.permission = permission

    def __getattr__(self, name: str):
        if name not in self.ALLOWED:
            raise AttributeError(name)
        return lambda *args, **kwargs: self.rpc._rpc('platform_store', self.permission, name, list(args), kwargs)


def load_entry(package_root: Path, entry: str):
    # Project extensions may vendor third-party wheels into ``_vendor``.  Keep
    # this path scoped to the isolated worker; never mutate the IDE process.
    vendor_root = package_root / '_vendor'
    for search_root in (vendor_root, package_root):
        if search_root.is_dir() and str(search_root) not in sys.path:
            sys.path.insert(0, str(search_root))
    module_ref, separator, function_name = str(entry or '').partition(':')
    if not separator:
        raise ValueError('能力入口缺少函数名')
    relative = module_ref.strip().replace('\\', '/')
    if not relative.endswith('.py'):
        relative = relative.replace('.', '/') + '.py'
    path = (package_root / relative).resolve()
    if package_root.resolve() not in path.parents or not path.is_file():
        raise ValueError('能力入口越界或不存在')
    parts = list(Path(relative).with_suffix('').parts)
    namespace = f'easycode_worker_{hashlib.sha256(str(package_root).encode()).hexdigest()[:16]}'
    package = types.ModuleType(namespace)
    package.__package__ = namespace
    package.__path__ = [str(package_root)]
    sys.modules[namespace] = package
    for index in range(1, len(parts)):
        parent_name = '.'.join([namespace, *parts[:index]])
        parent = types.ModuleType(parent_name)
        parent.__package__ = parent_name
        parent.__path__ = [str(package_root.joinpath(*parts[:index]))]
        sys.modules[parent_name] = parent
    module_name = '.'.join([namespace, *parts])
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError('无法加载能力模块')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    function = getattr(module, function_name.strip(), None)
    if not callable(function):
        raise ValueError(f'能力入口不可调用: {entry}')
    return function


def main() -> int:
    protocol = sys.stdout
    line = sys.stdin.readline()
    if not line:
        return 2
    try:
        request = json.loads(line)
        context = WorkerRpc(protocol, request)
        with contextlib.redirect_stdout(sys.stderr):
            function = load_entry(Path(request['package_root']).resolve(), request['entry'])
            inputs = dict(request.get('inputs') or {})
            signature = inspect.signature(function)
            if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
                result = function(context, **inputs)
            else:
                result = function(context, inputs)
        protocol.write(json.dumps({'type': 'result', 'result': result}, ensure_ascii=False, default=str) + '\n')
        protocol.flush()
        return 0
    except BaseException as exc:
        protocol.write(json.dumps({
            'type': 'error', 'error': str(exc),
            'traceback': ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
        }, ensure_ascii=False) + '\n')
        protocol.flush()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
