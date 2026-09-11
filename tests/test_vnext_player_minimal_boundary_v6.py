from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.player_app import create_player_app
from core.vnext.bundle_signing_v6 import trust_root_document
from core.vnext.player_bundle import vnext_player_bundle_manager
from core.vnext.runtime import vnext_runtime
from tests.test_vnext_distribution_v6 import _publish


ROOT = Path(__file__).resolve().parents[1]

PLAYER_OPENAPI_ALLOWLIST = {
    ('GET', '/api/vnext/player/runtime/bootstrap'),
    ('GET', '/api/vnext/player/runtime/state'),
    ('POST', '/api/vnext/player/runtime/run'),
    ('POST', '/api/vnext/player/runtime/dangerous-operations'),
    ('GET', '/api/vnext/player/runtime/preflight'),
    ('GET', '/api/vnext/player/runtime/profiles'),
    ('PUT', '/api/vnext/player/runtime/profiles'),
    ('DELETE', '/api/vnext/player/runtime/profiles/{profile_id}'),
    ('GET', '/api/vnext/player/runtime/recording'),
    ('POST', '/api/vnext/player/runtime/recording/stop'),
    ('GET', '/api/vnext/player/runtime/recordings'),
    ('GET', '/api/vnext/player/runtime/recordings/{session_id}'),
    ('GET', '/api/vnext/player/runtime/recordings/{session_id}/frames/{sequence}'),
    ('POST', '/api/vnext/player/runtime/recordings/{session_id}/export'),
    ('GET', '/api/vnext/player/runtime/recordings/{session_id}/exports/{export_id}'),
    ('DELETE', '/api/vnext/player/runtime/recordings/{session_id}'),
    ('GET', '/api/vnext/player/runtime/assets/{asset_id}/content'),
    ('GET', '/api/vnext/player/runtime/actions'),
    ('POST', '/api/vnext/player/runtime/capture/start'),
    ('POST', '/api/vnext/player/runtime/capture/confirm'),
    ('POST', '/api/vnext/player/runtime/capture/cancel'),
    ('POST', '/api/vnext/player/runtime/images/restore'),
    ('GET', '/api/vnext/runs/{execution_id}'),
    ('DELETE', '/api/vnext/runs/{execution_id}'),
    ('GET', '/api/vnext/runs/{execution_id}/events'),
    ('POST', '/api/vnext/runs/{execution_id}/pause'),
    ('POST', '/api/vnext/runs/{execution_id}/resume'),
    ('GET', '/api/vnext/runs/{execution_id}/diagnostics'),
    ('GET', '/api/vnext/runs/{execution_id}/failure-frame'),
    ('GET', '/api/ui-control/events'),
    ('POST', '/api/capture/action'),
    ('POST', '/api/capture/action/ack'),
    ('POST', '/api/capture/close'),
    ('GET', '/api/vnext/player/runtime/updates'),
    ('POST', '/api/vnext/player/runtime/updates/check'),
    ('POST', '/api/vnext/player/runtime/updates/download'),
    ('POST', '/api/vnext/player/runtime/updates/apply'),
    ('PUT', '/api/vnext/player/runtime/updates/preferences'),
    ('GET', '/api/vnext/player/runtime/updates/{domain}/group-code'),
    ('POST', '/api/vnext/player/runtime/updates/reset-group'),
    ('PUT', '/api/vnext/player/runtime/updates/safe-point'),
    ('GET', '/api/vnext/schedules'),
    ('POST', '/api/vnext/schedules'),
    ('GET', '/api/vnext/schedules/occurrences'),
    ('GET', '/api/vnext/schedules/dispatches'),
    ('GET', '/api/vnext/schedules/diagnostics'),
    ('GET', '/api/vnext/schedules/{schedule_id}'),
    ('PUT', '/api/vnext/schedules/{schedule_id}'),
    ('DELETE', '/api/vnext/schedules/{schedule_id}'),
    ('GET', '/api/vnext/player-hub'),
    ('GET', '/api/vnext/player-hub/installations'),
    ('POST', '/api/vnext/player-hub/installations'),
    ('GET', '/api/vnext/player-hub/instances'),
    ('POST', '/api/vnext/player-hub/instances'),
    ('PUT', '/api/vnext/player-hub/instances/{instance_id}/release'),
    ('POST', '/api/vnext/player-hub/instances/{instance_id}/open'),
    ('POST', '/api/vnext/player-hub/console/open'),
    ('GET', '/api/vnext/player-hub/batches'),
    ('POST', '/api/vnext/player-hub/batches'),
    ('PUT', '/api/vnext/player-hub/batches/{batch_id}'),
    ('DELETE', '/api/vnext/player-hub/batches/{batch_id}'),
    ('POST', '/api/vnext/player-hub/agent/install'),
    ('DELETE', '/api/vnext/player-hub/agent'),
    ('POST', '/api/vnext/player-hub/tick'),
    ('GET', '/api/vnext/player-hub/lan'),
    ('POST', '/api/vnext/player-hub/lan/listener'),
    ('DELETE', '/api/vnext/player-hub/lan/listener'),
    ('POST', '/api/vnext/player-hub/lan/discovery'),
    ('POST', '/api/vnext/player-hub/lan/pairing-sessions'),
    ('POST', '/api/vnext/player-hub/lan/pairing/begin'),
    ('POST', '/api/vnext/player-hub/lan/pairing/complete'),
    ('POST', '/api/vnext/player-hub/lan/pairing-pending/{pending_id}/confirm'),
    ('PATCH', '/api/vnext/player-hub/lan/peers/{host_id}/permissions'),
    ('DELETE', '/api/vnext/player-hub/lan/peers/{host_id}'),
    ('POST', '/api/vnext/player-hub/lan/peers/{host_id}/refresh'),
    ('GET', '/api/vnext/player-hub/lan/diagnostics'),
}


def _openapi_operations(app) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for path, value in app.openapi()['paths'].items():
        for method in value:
            if method in {'get', 'post', 'put', 'patch', 'delete'}:
                result.add((method.upper(), path))
    return result


def test_player_app_openapi_is_an_explicit_terminal_allowlist() -> None:
    app = create_player_app(ROOT / 'release' / 'player-web')
    assert _openapi_operations(app) == PLAYER_OPENAPI_ALLOWLIST


def test_player_static_pages_exist_and_ide_authoring_routes_are_404(tmp_path: Path) -> None:
    web = tmp_path / 'player-web'
    web.mkdir()
    (web / 'player.html').write_text('<main id="player">Player</main>', encoding='utf-8')
    (web / 'capture.html').write_text('<main id="capture">Capture</main>', encoding='utf-8')
    (web / 'console.html').write_text('<main id="console">Console</main>', encoding='utf-8')
    with TestClient(create_player_app(web)) as client:
        assert client.get('/player.html').status_code == 200
        assert client.get('/capture.html').status_code == 200
        assert client.get('/console.html').status_code == 200
        assert client.get('/index.html').status_code == 404
        for path in (
            '/api/vnext/workspaces/active',
            '/api/vnext/programs',
            '/api/vnext/player/publish',
            '/api/vnext/player/package',
            '/api/vnext/extensions',
            '/api/build',
            '/api/capture/session/register',
            '/api/capture/snapshot/example',
            '/api/ui-control/mode',
            '/api/settings/hotkeys',
        ):
            assert client.get(path).status_code == 404, path


def test_player_app_import_graph_excludes_ide_and_legacy_services() -> None:
    code = """
import json, sys
from api.player_app import create_player_app
create_player_app('Z:/missing').openapi()
print(json.dumps(sorted(sys.modules)))
"""
    completed = subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    modules = set(json.loads(completed.stdout.strip().splitlines()[-1]))
    forbidden = {
        'api.app', 'api.contracts.vnext', 'api.routers.vnext_router',
        'api.routers.vnext_update_router', 'api.routers.build_router',
        'core.vnext.workspace', 'core.vnext.publish', 'core.vnext.publish_service',
        'core.vnext.program_compiler', 'core.vnext.extensions',
        'core.vnext.program_repository',
        'core.services.project_workspace_service',
        'core.services.capture_session_service', 'core.services.execution_service',
        'core.services.frame_recording_service',
    }
    assert modules.isdisjoint(forbidden)
    assert not any(name == 'core.conditions' or name.startswith('core.conditions.') for name in modules)
    assert not any(name == 'core.params' or name.startswith('core.params.') for name in modules)
    assert not any(name == 'core.player' or name.startswith('core.player.') for name in modules)


def test_vnext_runtime_sources_do_not_reintroduce_excluded_legacy_packages() -> None:
    """Guard delayed runtime imports, not only the Player API bootstrap graph."""

    sources = list((ROOT / 'core' / 'vnext').glob('*.py'))
    sources += [ROOT / 'core' / 'vision' / 'ocr_engine.py', ROOT / 'api' / 'player_app.py']
    sources += list((ROOT / 'api' / 'routers').glob('vnext_player*.py'))
    forbidden = (
        'core.node_executors',
        'core.conditions',
        'core.params',
        'core.player',
    )
    offenders = {
        str(path.relative_to(ROOT)): token
        for path in sources
        for token in forbidden
        if token in path.read_text(encoding='utf-8')
    }
    assert offenders == {}


def test_delayed_vnext_ocr_execution_works_while_legacy_packages_are_blocked() -> None:
    code = r"""
import importlib.abc, json, sys, tempfile

blocked = ('core.node_executors', 'core.conditions', 'core.params', 'core.player')
class BlockLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.') for name in blocked):
            raise ModuleNotFoundError(fullname)
        return None
sys.meta_path.insert(0, BlockLegacy())

from PIL import Image
from core.vision import ocr_engine
from core.vnext.target_runtime import TargetDriver

class FakeDdddOcr:
    def classification(self, _content):
        return '边界正常'

ocr_engine._ENGINE_TYPE = 'ddddocr'
ocr_engine._OCR_ENGINE = FakeDdddOcr()
with tempfile.TemporaryDirectory() as root:
    driver = TargetDriver(root, {'target_id': 'probe', 'type': 'windows'})
    value = driver.recognize_text_on_frame(Image.new('RGB', (40, 20), 'white'), {})
assert value == '边界正常'
loaded = sorted(name for name in sys.modules if any(name == root or name.startswith(root + '.') for root in blocked))
print(json.dumps(loaded))
"""
    completed = subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == []


def test_published_extension_runtime_does_not_import_author_extension_service() -> None:
    code = """
import json, sys
from core.vnext.extension_runtime_v6 import invoke_published_extension
assert callable(invoke_published_extension)
print(json.dumps(sorted(sys.modules)))
"""
    completed = subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    modules = set(json.loads(completed.stdout.strip().splitlines()[-1]))
    assert 'core.vnext.extensions' not in modules
    assert 'core.vnext.workspace' not in modules
    assert 'core.vnext.publish' not in modules
    assert 'core.vnext.program_compiler' not in modules


def test_player_cli_commits_bundle_and_trust_before_app_import(tmp_path: Path) -> None:
    bundle = tmp_path / 'project.ecplayer'
    trust = tmp_path / 'trust-root.json'
    bundle.write_bytes(b'signed-bundle-placeholder')
    trust.write_text('{}', encoding='utf-8')
    code = """
import json, os, sys, types
fake_dpi = types.ModuleType('core.services.dpi_service')
fake_dpi.enable_per_monitor_v2 = lambda: None
sys.modules['core.services.dpi_service'] = fake_dpi
fake_app = types.ModuleType('api.player_app')
def create():
    assert os.environ['EASYCODE_PLAYER_BUNDLE'] == os.path.abspath(sys.argv[1])
    assert os.environ['EASYCODE_PLAYER_TRUST_ROOT'] == os.path.abspath(sys.argv[2])
    assert os.environ['EASYCODE_PLAYER_REQUIRE_TRUST_ROOT'] == '1'
    assert 'core.vnext.player_bundle' not in sys.modules
    return object()
fake_app.create_player_app = create
fake_app.start_webview = lambda _port: None
sys.modules['api.player_app'] = fake_app
import player
player._bootstrap_application(['--mode', 'dev', '--player-bundle', sys.argv[1], '--player-trust-root', sys.argv[2]])
print(json.dumps({'ordered': True}))
"""
    completed = subprocess.run(
        [sys.executable, '-c', code, os.fspath(bundle), os.fspath(trust)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == {'ordered': True}


def test_windowed_player_persists_bootstrap_failures(tmp_path: Path, monkeypatch) -> None:
    import player

    monkeypatch.setenv('LOCALAPPDATA', os.fspath(tmp_path))
    failure = RuntimeError('frozen bootstrap failed visibly')
    path = player._write_startup_failure(failure)
    assert path == tmp_path / 'EasyCode' / 'Player' / 'logs' / 'startup.log'
    content = path.read_text(encoding='utf-8')
    assert 'Player 启动失败' in content
    assert 'RuntimeError: frozen bootstrap failed visibly' in content


def test_packaged_player_direct_launch_discovers_release_and_uses_system_port(
    tmp_path: Path, monkeypatch,
) -> None:
    import player

    release = tmp_path / 'release'
    release.mkdir()
    bundle = release / 'project.ecplayer'
    trust = release / 'trust-root.json'
    bundle.write_bytes(b'signed-bundle-placeholder')
    trust.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(player, '_application_directory', lambda: tmp_path)
    for key in (
        'EASYCODE_PLAYER_BUNDLE', 'EASYCODE_PLAYER_TRUST_ROOT',
        'EASYCODE_PLAYER_REQUIRE_TRUST_ROOT', 'EASYCODE_PLAYER_PRODUCT_METADATA',
        'FLAGS_use_mkldnn', 'FLAGS_enable_pir_api',
    ):
        monkeypatch.setenv(key, '')

    parser = player._parser()
    args = parser.parse_args([])
    player._prepare_environment(args, parser)

    assert args.mode == 'prod'
    assert args.port == 0
    assert Path(args.player_bundle) == bundle
    assert Path(args.player_trust_root) == trust
    assert os.environ['EASYCODE_PLAYER_BUNDLE'] == os.fspath(bundle.resolve())
    assert os.environ['EASYCODE_PLAYER_TRUST_ROOT'] == os.fspath(trust.resolve())


def test_player_development_mode_keeps_explicit_8000_default() -> None:
    import player

    parser = player._parser()
    args = parser.parse_args(['--mode', 'dev'])
    args.player_console = True
    player._prepare_environment(args, parser)

    assert args.port == 8000


def test_windowed_player_does_not_let_uvicorn_probe_missing_console_streams() -> None:
    source = (ROOT / 'player.py').read_text(encoding='utf-8')

    assert "log_config=None" in source
    assert "access_log=False" in source


def test_player_native_shell_reads_packaged_application_name_and_icon(tmp_path: Path, monkeypatch) -> None:
    from api import player_app

    icon = tmp_path / 'branding' / 'app-icon.png'
    icon.parent.mkdir()
    icon.write_bytes(b'png-placeholder')
    metadata = tmp_path / 'product.json'
    metadata.write_text(json.dumps({
        'schema_version': 1,
        'application_name': '超能世界助手',
        'icon': 'branding/app-icon.png',
    }, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setenv('EASYCODE_PLAYER_PRODUCT_METADATA', os.fspath(metadata))

    assert player_app._player_product_branding() == ('超能世界助手', os.fspath(icon.resolve()))


def test_windows_player_requests_admin_and_can_reserve_distinct_loopback_ports(tmp_path: Path) -> None:
    import player

    spec = (ROOT / 'scripts' / 'player.spec').read_text(encoding='utf-8')
    assert 'uac_admin=True' in spec
    first, first_port = player._reserve_loopback_socket('127.0.0.1')
    second, second_port = player._reserve_loopback_socket('127.0.0.1')
    try:
        assert 1 <= first_port <= 65535
        assert 1 <= second_port <= 65535
        assert first_port != second_port
    finally:
        first.close()
        second.close()

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', str(tmp_path / 'instance-one'))
        assert player._diagnostics_directory() == (tmp_path / 'instance-one' / 'logs').resolve()
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize(
    ('marker', 'module_name'),
    (
        ('--capability-worker', 'core.services.capability_worker'),
        ('--extension-worker', 'core.vnext.extension_worker_v6'),
        ('--player-hub-agent', 'core.vnext.schedule_hub_v6'),
    ),
)
def test_player_worker_dispatch_precedes_application_and_bundle_import(
    marker: str,
    module_name: str,
) -> None:
    code = """
import json, sys, types
marker, module_name = sys.argv[1:3]
fake = types.ModuleType(module_name)
if marker == '--player-hub-agent':
    def main(arguments):
        assert arguments == ['agent']
        return 17
else:
    def main():
        return 17
fake.main = main
sys.modules[module_name] = fake
import player
result = player._dispatch_worker([marker])
print(json.dumps({
    'result': result,
    'app_imported': 'api.player_app' in sys.modules,
    'bundle_imported': 'core.vnext.player_bundle' in sys.modules,
}))
"""
    completed = subprocess.run(
        [sys.executable, '-c', code, marker, module_name],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == {
        'result': 17,
        'app_imported': False,
        'bundle_imported': False,
    }


def test_signed_bundle_bootstrap_run_and_stop_through_player_app(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wait_instruction = {
        'instruction_id': 'wait_for_stop',
        'opcode': 'wait.duration',
        'arguments': {'official.wait.duration.parameter.duration': 30_000},
        'result_slot': None,
        'source': {},
        'capabilities': [],
    }
    published = _publish(
        tmp_path,
        instructions=[wait_instruction],
        supported_platforms=['no_target'],
    )
    with zipfile.ZipFile(published['path']) as archive:
        names = [name.replace('\\', '/').casefold() for name in archive.namelist()]
    assert not any(name.endswith('.easy') for name in names)
    assert not any('/programs/' in f'/{name}' for name in names)
    assert not any(name.rsplit('/', 1)[-1] == 'program.json' for name in names)
    assert not any('programdocument' in name or 'program_document' in name for name in names)
    trust_path = tmp_path / 'trust-root.json'
    trust_path.write_text(
        json.dumps(
            trust_root_document(published['signature'], 'product_distribution_test'),
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('EASYCODE_PLAYER_BUNDLE', published['path'])
    monkeypatch.setenv('EASYCODE_PLAYER_TRUST_ROOT', os.fspath(trust_path))
    monkeypatch.setenv('EASYCODE_PLAYER_REQUIRE_TRUST_ROOT', '1')
    monkeypatch.setenv('EASYCODE_PLAYER_DATA_DIR', os.fspath(tmp_path / 'player-data'))
    vnext_player_bundle_manager.shutdown()
    vnext_runtime.shutdown()

    web = tmp_path / 'static'
    web.mkdir()
    (web / 'player.html').write_text('<main>Player</main>', encoding='utf-8')
    (web / 'capture.html').write_text('<main>Capture</main>', encoding='utf-8')
    (web / 'console.html').write_text('<main>Console</main>', encoding='utf-8')
    with TestClient(create_player_app(web)) as client:
        bootstrap = client.get('/api/vnext/player/runtime/bootstrap')
        assert bootstrap.status_code == 200
        assert bootstrap.json()['bundle']['release_id'] == published['release_id']

        started = client.post('/api/vnext/player/runtime/run', json={})
        assert started.status_code == 200
        started_payload = started.json()
        execution_id = started_payload['execution_id']
        worker = started_payload['worker']
        assert worker['isolated'] is True
        assert int(worker['pid']) > 0
        assert int(worker['pid']) != os.getpid()
        stopped = client.delete(f'/api/vnext/runs/{execution_id}')
        assert stopped.status_code == 200
        status = client.get(f'/api/vnext/runs/{execution_id}').json()
        for _ in range(100):
            if status['status'] == 'cancelled':
                break
            time.sleep(0.01)
            status = client.get(f'/api/vnext/runs/{execution_id}').json()
        assert status['status'] == 'cancelled'


def test_player_frontend_and_pyinstaller_manifests_are_minimal() -> None:
    vite_config = (ROOT / 'frontend' / 'vite.player.config.js').read_text(encoding='utf-8')
    player_app = (ROOT / 'frontend' / 'src' / 'vnext' / 'VNextPlayerApp.vue').read_text(encoding='utf-8')
    capture_entry = (ROOT / 'frontend' / 'src' / 'player-capture-main.js').read_text(encoding='utf-8')
    spec = (ROOT / 'scripts' / 'player.spec').read_text(encoding='utf-8')
    build_script = (ROOT / 'scripts' / 'build_vnext_player.py').read_text(encoding='utf-8')

    assert "../release/player-web" in vite_config
    assert "path.resolve(__dirname, 'player.html')" in vite_config
    assert "path.resolve(__dirname, 'capture.html')" in vite_config
    assert "path.resolve(__dirname, 'console.html')" in vite_config
    assert "path.resolve(__dirname, 'index.html')" not in vite_config
    assert "from './playerApi'" in player_app
    assert "from './api'" not in player_app
    assert 'captureApi' not in player_app
    assert 'CaptureFileManagerView' not in capture_entry

    assert "['../player.py']" in spec
    for forbidden_collect in (
        "collect_submodules('core.node_executors')",
        "collect_submodules('core.conditions')",
        "collect_submodules('core.player')",
        "collect_submodules('core.params')",
        "collect_submodules('core.vnext')",
    ):
        assert forbidden_collect not in spec
    assert "'core.vision.ocr_engine'" in spec
    assert "'core.node_executors.base.ocr_recognition'" not in spec
    assert "'core.vnext.extension_worker_v6'" in spec
    assert "'core.vnext.extension_runtime_v6'" in spec
    assert "'tkinter', 'matplotlib'" not in spec
    assert "not name.startswith(('ddddocr.api', 'ddddocr.__main__'))" in spec
    assert "'core.vnext.extensions'" in spec.partition('excludes=[')[2]
    assert "'core.vnext.extensions'" not in spec.partition('hiddenimports = [')[2].partition(']')[0]
    assert 'uac_admin=True' in spec
    assert "'build:player'" in build_script
    assert "'release' / 'player-web'" in build_script
    assert '_replace_runtime_template(built_runtime, runtime_root)' in build_script

    built = ROOT / 'release' / 'player-web'
    if built.is_dir():
        files = [path.relative_to(built) for path in built.rglob('*') if path.is_file()]
        assert Path('player.html') in files
        assert Path('capture.html') in files
        assert Path('console.html') in files
        assert Path('index.html') not in files
        assert not any(
            path.suffix.casefold() in {'.vue', '.ts', '.tsx', '.jsx', '.map', '.easy'}
            or 'src' in {part.casefold() for part in path.parts}
            for path in files
        )


def test_rebuilt_runtime_atomically_replaces_the_reusable_template(tmp_path: Path) -> None:
    from scripts.build_vnext_player import _replace_runtime_template

    source = tmp_path / 'fresh-runtime'
    source.mkdir()
    (source / 'EasycodePlayer.exe').write_bytes(b'fresh')
    (source / '_internal').mkdir()
    (source / '_internal' / 'runtime.pyd').write_bytes(b'new-runtime')
    destination = tmp_path / 'dist' / 'EasycodePlayer'
    destination.mkdir(parents=True)
    (destination / 'EasycodePlayer.exe').write_bytes(b'stale')
    (destination / 'removed-from-new-runtime.dll').write_bytes(b'stale')

    _replace_runtime_template(source, destination)

    assert (destination / 'EasycodePlayer.exe').read_bytes() == b'fresh'
    assert (destination / '_internal' / 'runtime.pyd').read_bytes() == b'new-runtime'
    assert not (destination / 'removed-from-new-runtime.dll').exists()
    assert not list(destination.parent.glob('EasycodePlayer.*-*'))


def test_android_player_has_one_shared_form_renderer() -> None:
    source = (ROOT / 'android' / 'app' / 'src' / 'main' / 'java' / 'com' / 'easycode' / 'player' / 'PlayerActivity.kt').read_text(encoding='utf-8')

    assert 'renderWebPlayer()' in source
    assert 'configureOfflinePlayer(AndroidPlayerWebBridge(::handleWebRequest))' in source
    assert 'private fun render()' not in source
    assert 'ValueEditor' not in source
    assert 'android.widget.EditText' not in source
