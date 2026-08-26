import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from core.capabilities import CapabilityContext, CapabilitySpec
from core.params import ALL_PARAMS
from core.services.capability_service import CapabilityError, CapabilityService
from core.services.platform_store import PlatformStore


class FakeExecutor:
    def __init__(self, project_dir, variables=None):
        self.project_dir = str(project_dir)
        self.variables = variables or {}
        self.is_stopped = False
        self.logs = []

    def log(self, message, level='info'):
        self.logs.append((level, message))


def _write_demo_package(project):
    root = project / 'capabilities' / 'demo'
    root.mkdir(parents=True)
    (root / 'capability.json').write_text(
        '''{
          "package_id": "demo", "version": "1.2.0",
          "functions": [{
            "id": "demo.add", "name": "求和", "entry": "main.py:run",
            "idempotent": true,
            "inputs": [{"name":"left","type":"int","required":true},{"name":"right","type":"int","default":2}],
            "outputs": [{"name":"total","type":"int"}]
          }]
        }''', encoding='utf-8'
    )
    (root / 'main.py').write_text(
        "def run(context, **inputs):\n    return {'success': True, 'data': {'total': inputs['left'] + inputs['right']}}\n",
        encoding='utf-8',
    )


def test_custom_capability_contract_bindings_and_outputs(tmp_path):
    _write_demo_package(tmp_path)
    executor = FakeExecutor(tmp_path, {'source': '5'})
    result = CapabilityService.invoke(
        executor, 'demo.add',
        input_bindings=[{'name': 'left', 'value': '$var.source'}, {'name': 'right', 'value': 4}],
        output_bindings=[{'source': 'total', 'target': '$var.total'}],
    )
    assert result['success'] is True
    assert result['data']['total'] == 9
    assert executor.variables['total'] == 9


def test_unknown_input_and_non_idempotent_retry_are_rejected(tmp_path):
    executor = FakeExecutor(tmp_path)
    with pytest.raises(CapabilityError, match='不接受输入'):
        CapabilityService.invoke(
            executor, 'platform.state.get',
            input_bindings=[{'name': 'key', 'value': 'x'}, {'name': 'unknown', 'value': 1}],
        )
    with pytest.raises(CapabilityError, match='未声明幂等'):
        CapabilityService.invoke(
            executor, 'platform.message.publish', retry_count=1,
            input_bindings=[{'name': 'channel', 'value': 'x'}, {'name': 'payload', 'value': {}}],
        )


def test_platform_capabilities_persist_state(tmp_path):
    executor = FakeExecutor(tmp_path)
    executor._platform_store = PlatformStore(str(tmp_path / 'platform.db'))
    result = CapabilityService.invoke(
        executor, 'platform.state.set',
        input_bindings=[{'name': 'key', 'value': 'last-page'}, {'name': 'value', 'value': 'home'}],
    )
    assert result['success'] is True
    read = CapabilityService.invoke(
        executor, 'platform.state.get',
        input_bindings=[{'name': 'key', 'value': 'last-page'}],
    )
    assert read['data']['value'] == 'home'


def test_call_capability_defaults_only_expose_contract_fields():
    fields = ALL_PARAMS['script_call']['params']
    assert 'call_mode' not in fields
    assert 'script' not in fields
    assert 'entry' not in fields
    assert fields['capability_id']['default'] == ''
    assert fields['input_bindings']['default'] == []
    assert fields['output_bindings']['default'] == []


def test_capability_bindings_support_function_parameter_and_local_scopes(tmp_path):
    executor = FakeExecutor(tmp_path, {
        '__param__:query': '登录页',
        '__local__:matched': False,
    })

    assert CapabilityService._resolve_binding('$param.query', executor) == '登录页'
    assert CapabilityService._resolve_binding('$local.matched', executor) is False

    CapabilityService.apply_outputs(
        {'data': {'matched': True}},
        [{'source': 'matched', 'target': '$local.matched'}],
        executor,
    )
    assert executor.variables['__local__:matched'] is True

    with pytest.raises(CapabilityError, match='能力输出目标必须'):
        CapabilityService.apply_outputs(
            {'data': {'matched': True}},
            [{'source': 'matched', 'target': '$param.query'}],
            executor,
        )


def test_discovery_does_not_execute_code_and_relative_imports_work(tmp_path):
    root = tmp_path / 'capabilities' / 'lazy_demo'
    root.mkdir(parents=True)
    (root / 'capability.json').write_text(
        '''{
          "package_id": "lazy_demo", "version": "1.0.0",
          "functions": [{
            "id": "lazy_demo.double", "entry": "main.py:run",
            "inputs": [{"name":"value","type":"int","required":true}],
            "outputs": [{"name":"result","type":"int"}]
          }]
        }''', encoding='utf-8',
    )
    (root / 'helper.py').write_text('def double(value):\n    return value * 2\n', encoding='utf-8')
    (root / 'main.py').write_text(
        "from pathlib import Path\n"
        "from .helper import double\n"
        "Path(__file__).with_name('executed.marker').write_text('yes', encoding='utf-8')\n"
        "def run(context, **inputs):\n    return {'data': {'result': double(inputs['value'])}}\n",
        encoding='utf-8',
    )

    catalog = CapabilityService.discover(str(tmp_path), force=True)
    assert any(item.get('id') == 'lazy_demo.double' for item in catalog)
    assert not (root / 'executed.marker').exists(), '发现能力时不应执行项目 Python 代码'

    result = CapabilityService.invoke(
        FakeExecutor(tmp_path), 'lazy_demo.double',
        input_bindings=[{'name': 'value', 'value': 6}],
    )
    assert result['data']['result'] == 12
    assert (root / 'executed.marker').read_text(encoding='utf-8') == 'yes'


def test_duplicate_custom_capabilities_are_reported_without_ambiguity(tmp_path):
    for name in ('first', 'second'):
        root = tmp_path / 'capabilities' / name
        root.mkdir(parents=True)
        (root / 'capability.json').write_text(
            '{"package_id":"' + name + '","functions":[{"id":"same.run","entry":"main.py:run"}]}',
            encoding='utf-8',
        )
        (root / 'main.py').write_text("def run(context, **inputs):\n    return True\n", encoding='utf-8')

    catalog = CapabilityService.discover(str(tmp_path), force=True)
    declared = [item for item in catalog if item.get('id') == 'same.run']
    errors = next(item for item in catalog if item.get('id') == '__discovery_errors__')
    assert len(declared) == 1
    assert any('重复' in item['message'] for item in errors['errors'])


def test_capability_ocr_uses_bound_runtime_capture_without_preview_encoding(monkeypatch, tmp_path):
    from PIL import Image

    captured = {}

    def fake_capture(executor, rect, reference_size):
        captured['executor'] = executor
        captured['rect'] = rect
        captured['reference_size'] = reference_size
        return Image.new('RGB', (40, 20), 'white'), (1, 2, 40, 20)

    monkeypatch.setattr('core.services.runtime_target.capture_workspace_region', fake_capture)
    monkeypatch.setattr('core.node_executors.base.ocr_recognition.ocr_engine_recognize', lambda frame: '测试文字')
    executor = FakeExecutor(tmp_path)
    spec = CapabilitySpec(
        capability_id='test.ocr', version='1.0.0', entry=lambda *_: None,
        permissions=frozenset({'screen.read'}),
    )
    context = CapabilityContext(executor, spec, threading.Event())

    assert context.ocr_region([1, 2, 40, 20], reference_size=[960, 540]) == '测试文字'
    assert captured == {
        'executor': executor, 'rect': [1, 2, 40, 20], 'reference_size': [960, 540],
    }


def _write_worker_package(project, package_id, manifest_function, source):
    root = project / 'capabilities' / package_id
    root.mkdir(parents=True)
    function = {
        'id': f'{package_id}.run',
        'name': package_id,
        'entry': 'main.py:run',
        'inputs': [],
        'outputs': [],
        **manifest_function,
    }
    (root / 'capability.json').write_text(json.dumps({
        'package_id': package_id,
        'version': '1.0.0',
        'functions': [function],
    }), encoding='utf-8')
    (root / 'main.py').write_text(source, encoding='utf-8')
    return root


def test_custom_capability_timeout_terminates_worker_process(tmp_path):
    root = _write_worker_package(
        tmp_path,
        'slow_worker',
        {'timeout_ms': 80},
        'import time\nfrom pathlib import Path\n\n'
        'def run(context, **inputs):\n'
        '    time.sleep(0.6)\n'
        '    Path(__file__).with_name("late.marker").write_text("should-not-exist", encoding="utf-8")\n'
        '    return True\n',
    )

    result = CapabilityService.invoke(FakeExecutor(tmp_path), 'slow_worker.run')

    assert result['success'] is False
    assert result['code'] == 'TIMEOUT'
    time.sleep(0.7)
    assert not (root / 'late.marker').exists()


def test_custom_capability_worker_rpc_can_write_declared_variable(tmp_path):
    _write_worker_package(
        tmp_path,
        'variable_worker',
        {'permissions': ['variables.write']},
        'def run(context, **inputs):\n'
        '    context.set_variable("worker_value", 42)\n'
        '    context.log("变量已写入")\n'
        '    return {"success": True, "data": {"value": context.get_variable("worker_value")}}\n',
    )
    executor = FakeExecutor(tmp_path)

    result = CapabilityService.invoke(executor, 'variable_worker.run')

    assert result['success'] is True
    assert result['data']['value'] == 42
    assert executor.variables['worker_value'] == 42
    assert any('变量已写入' in message for _level, message in executor.logs)


def test_create_package_scaffolds_project_and_shared_capabilities(monkeypatch, tmp_path):
    shared = tmp_path / 'shared-capabilities'
    monkeypatch.setenv('EASYCODE_CAPABILITY_HOME', str(shared))

    project_created = CapabilityService.create_package(
        str(tmp_path), scope='project', package_id='project_demo', function_name='execute',
        display_name='项目示例', description='仅属于当前项目',
    )
    shared_created = CapabilityService.create_package(
        str(tmp_path), scope='shared', package_id='shared_demo', function_name='execute',
        display_name='公共示例', description='供多个项目复用',
    )

    assert project_created['path'] == str(tmp_path / 'capabilities' / 'project_demo')
    assert shared_created['path'] == str(shared / 'shared_demo')
    catalog = CapabilityService.discover(str(tmp_path), force=True)
    indexed = {item['id']: item for item in catalog if item.get('id') != '__discovery_errors__'}
    assert indexed['project_demo.execute']['source'].startswith('project:')
    assert indexed['shared_demo.execute']['source'].startswith('shared:')


def test_executable_entry_dispatches_capability_worker_protocol_before_server_start(tmp_path):
    root = tmp_path / 'entry_worker'
    root.mkdir()
    (root / 'main.py').write_text(
        'def run(context, **inputs):\n'
        '    return {"success": True, "data": {"doubled": inputs["value"] * 2}}\n',
        encoding='utf-8',
    )
    request = {
        'package_root': str(root),
        'entry': 'main.py:run',
        'inputs': {'value': 7},
        'spec': {'id': 'entry_worker.run', 'permissions': []},
        'project_path': '',
        'variables': {},
    }

    process = subprocess.run(
        [sys.executable, 'api.py', '--capability-worker'],
        cwd=str(Path(__file__).resolve().parents[1]),
        input=json.dumps(request) + '\n',
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=10,
    )

    assert process.returncode == 0, process.stderr
    event = json.loads(process.stdout.strip().splitlines()[-1])
    assert event == {'type': 'result', 'result': {'success': True, 'data': {'doubled': 14}}}
