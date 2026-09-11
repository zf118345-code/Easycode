from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore
from core.vnext.bundle_signing_v6 import public_key_id
from core.vnext.distribution import (
    DistributionError,
    PLAYER_RUNTIME_CONTRACT_VERSION,
    VNextDistributionAssembler,
    write_player_runtime_contract,
)
from core.vnext.player_bundle import PlayerBundleError, VNextPlayerBundleManager
from core.vnext.publish import VNextPublisher
from core.vnext.publish_service import VNextPublishService
from core.vnext.workspace_context import VNextWorkspaceError
from core.vnext.pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash
from core.vnext.target_service import TargetConfiguration, target_configuration_revision
from core.vnext.update_protocol_v6 import UPDATE_ROLES, UpdateSigningIdentity
from core.vnext.update_repository_v6 import StaticUpdateRepository, UpdateRepositorySigner


def _publish(
    tmp_path: Path,
    update_configuration: dict | None = None,
    *,
    instructions: list[dict] | None = None,
    supported_platforms: list[str] | None = None,
) -> dict:
    project_root = tmp_path / 'project'
    project_root.mkdir()
    assets = project_root / 'assets'
    assets.mkdir()
    (assets / 'registry.json').write_text(
        json.dumps({
            'schema_version': 1,
            'assets': {},
            'folders': {'image': [], 'ocr': [], 'page': []},
        }) + '\n',
        encoding='utf-8',
    )
    (project_root / 'easycode.lock').write_text(json.dumps({
        'lock_version': 1,
        'project_format': 6,
        'toolchain': {
            'compiler_version': '6.0.0',
            'program_schema': 1,
            'ecir': 1,
            'pure_value_registry_version': PURE_OPERATION_REGISTRY_VERSION,
            'pure_value_registry_sha256': pure_operation_registry_hash(),
        },
        'official_functions': [],
        'extensions': [],
    }) + '\n', encoding='utf-8')
    if update_configuration is not None:
        (project_root / 'updates.json').write_text(
            json.dumps(update_configuration, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
    publisher = VNextPublisher(
        str(project_root),
        signing_key_store=AuthorSigningKeyStore(tmp_path / 'keys'),
    )
    linked = {
        'diagnostics': [],
        'ecir': {
            'entry_function_id': 'function_main',
            'functions': [{
                'function_id': 'function_main',
                'name': '主程序',
                'parameters': [],
                'parameter_definitions': [],
                'return_type': 'null',
                'instructions': list(instructions or []),
            }],
            'project_variables': [],
            'required_capabilities': [],
            'supported_platforms': list(supported_platforms or ['windows']),
        },
    }
    form = {'schema_version': 3, 'title': '运行', 'pages': []}
    target_config = TargetConfiguration(schema_version=1, targets=[], default_target_id=None)
    project = {
        'project_id': 'product_distribution_test',
        'name': '交付测试',
        'targets_schema_version': 1,
        'targets': [],
        'default_target_id': None,
        'target_configuration_revision': target_configuration_revision(target_config),
    }
    (project_root / 'project.json').write_text(
        json.dumps(project, ensure_ascii=False) + '\n', encoding='utf-8',
    )
    report = publisher.report(linked, form)
    assert report['valid'] is True, report
    return publisher.build(linked, form, project, report)


def test_workspace_android_package_derives_trust_root_and_uses_project_dist(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'project'
    project_root.mkdir()
    project = {'project_id': 'project.android.ui'}
    (project_root / 'project.json').write_text(json.dumps(project), encoding='utf-8')
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    import base64
    signature = {
        'algorithm': 'Ed25519',
        'key_id': public_key_id(public),
        'public_key': base64.b64encode(public).decode('ascii'),
        'integrity_sha256': 'a' * 64,
    }
    bundle = project_root / 'dist' / 'project.ecplayer'
    bundle.parent.mkdir()
    bundle.write_bytes(b'signed-bundle-placeholder')

    class Owner:
        _lock = threading.RLock()
        def _require(self, workspace_id, generation, writable=False):
            assert (workspace_id, generation, writable) == ('workspace', 7, True)
            return type('Workspace', (), {'project_path': str(project_root)})()
        @staticmethod
        def _read_json(path):
            return json.loads(Path(path).read_text(encoding='utf-8'))

    captured: dict = {}
    class AndroidService:
        @staticmethod
        def build(bundle_path, trust_root_path, **kwargs):
            captured.update(bundle_path=str(bundle_path), trust_root_path=str(trust_root_path), **kwargs)
            return {'apk_path': str(kwargs['output_path']), 'min_sdk': 24, 'evidence_path': 'evidence.json'}

    import core.vnext.android_delivery_v6 as android_delivery
    monkeypatch.setattr(android_delivery, 'android_delivery_service_v6', AndroidService())
    service = VNextPublishService(Owner(), 'project.json')
    monkeypatch.setattr(service, '_build_locked', lambda *_: {
        'path': str(bundle), 'release_id': 'release.ui', 'signature': signature,
        'report': {'android_build_declared': True},
    })

    result = service.android_package('workspace', 7)

    trust = json.loads(Path(captured['trust_root_path']).read_text(encoding='utf-8'))
    assert trust['product_id'] == 'project.android.ui'
    assert trust['key_id'] == signature['key_id']
    assert captured['variant'] == 'productionDebug'
    assert captured['output_path'] == project_root / 'dist' / 'android' / 'EasyCodePlayer-android-debug.apk'
    assert result['release_id'] == 'release.ui'


def test_workspace_package_explains_running_player_directory_lock(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / 'project'
    project_root.mkdir()

    class Owner:
        _lock = threading.RLock()

        @staticmethod
        def _require(_workspace_id, _generation, writable=False):
            assert writable is True
            return type('Workspace', (), {'project_path': str(project_root)})()

    service = VNextPublishService(Owner(), 'project.json')
    monkeypatch.setattr(service, 'build', lambda *_args: {
        'path': str(project_root / 'dist' / 'project.ecplayer'),
        'release_id': 'release.locked',
        'signature': {},
    })
    monkeypatch.setattr(
        VNextDistributionAssembler,
        'assemble',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError(13, 'Player_Bundle is in use')),
    )

    with pytest.raises(VNextWorkspaceError, match='Player_Bundle 正被正在运行的 EasyCode Player 占用'):
        service.package('workspace', 1)


def test_distribution_pins_author_key_and_packaged_player_requires_it(tmp_path: Path) -> None:
    published = _publish(tmp_path)
    with zipfile.ZipFile(published['path']) as archive:
        assert 'update/config.json' not in archive.namelist()
    runtime = tmp_path / 'runtime'
    web = tmp_path / 'web'
    runtime.mkdir()
    web.mkdir()
    (runtime / 'EasycodePlayer.exe').write_bytes(b'fake runtime boundary')
    (runtime / 'EasycodeUpdateHelper.exe').write_bytes(b'fake update helper boundary')
    (web / 'player.html').write_text('<main>Player</main>', encoding='utf-8')
    (web / 'capture.html').write_text('<main>Capture</main>', encoding='utf-8')
    (web / 'console.html').write_text('<main>Console</main>', encoding='utf-8')
    output = tmp_path / 'output'

    packaged = VNextDistributionAssembler(runtime, web).assemble(published['path'], output)

    root = Path(packaged['path'])
    trust_path = root / 'release' / 'trust-root.json'
    trust = json.loads(trust_path.read_text(encoding='utf-8'))
    assert trust['product_id'] == 'product_distribution_test'
    assert trust['key_id'] == published['signature']['key_id']
    launcher = (root / '启动脚本助手.bat').read_text(encoding='gbk')
    assert 'start "" EasycodePlayer.exe' in launcher
    assert '--player-bundle' not in launcher
    assert '--player-trust-root' not in launcher
    assert packaged['manifest']['release_id'] == published['release_id']
    assert packaged['manifest']['product'] == '运行'
    product = json.loads((root / 'release' / 'product.json').read_text(encoding='utf-8'))
    assert product == {
        'schema_version': 1,
        'application_name': '运行',
        'icon': '',
    }
    delivered = [
        path.relative_to(root).as_posix().casefold()
        for path in root.rglob('*') if path.is_file()
    ]
    assert 'release/web/player.html' in delivered
    assert 'release/web/capture.html' in delivered
    assert 'release/web/console.html' in delivered
    assert 'easycodeupdatehelper.exe' in delivered
    assert 'release/web/index.html' not in delivered
    assert not any(
        name.endswith(('.easy', '.vue', '.ts', '.tsx', '.jsx', '.map'))
        or '/src/' in f'/{name}/'
        or 'programdocument' in name
        or 'program_document' in name
        for name in delivered
    )
    with zipfile.ZipFile(packaged['bundle']) as archive:
        bundled_names = [name.replace('\\', '/').casefold() for name in archive.namelist()]
    assert not any(
        name.endswith('.easy')
        or '/programs/' in f'/{name}'
        or name.rsplit('/', 1)[-1] == 'program.json'
        or 'programdocument' in name
        or 'program_document' in name
        for name in bundled_names
    )

    loader = VNextPlayerBundleManager(require_trusted_key=True)
    loaded = loader.load(packaged['bundle'], trust_path)
    assert loaded['bundle']['signature']['key_id'] == trust['key_id']
    assert loader.preflight()['ready'] is False
    with pytest.raises(PlayerBundleError, match='需要操作目标'):
        loader.start({})
    loader.shutdown()

    other_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        Encoding.Raw,
        PublicFormat.Raw,
    )
    with pytest.raises(PlayerBundleError, match='固定信任根不匹配'):
        VNextPlayerBundleManager(require_trusted_key=True).load(
            packaged['bundle'],
            other_key,
        )


@pytest.mark.parametrize(
    'forbidden_name',
    ('programs/main.easy', 'program.json', 'runtime/ProgramDocument.json'),
)
def test_distribution_rejects_ide_web_and_editable_program_sources(
    tmp_path: Path,
    forbidden_name: str,
) -> None:
    published = _publish(tmp_path)
    runtime = tmp_path / 'runtime'
    web = tmp_path / 'web'
    runtime.mkdir()
    web.mkdir()
    (runtime / 'EasycodePlayer.exe').write_bytes(b'fake runtime boundary')
    (runtime / 'EasycodeUpdateHelper.exe').write_bytes(b'fake update helper boundary')
    (web / 'player.html').write_text('<main>Player</main>', encoding='utf-8')
    (web / 'capture.html').write_text('<main>Capture</main>', encoding='utf-8')
    (web / 'console.html').write_text('<main>Console</main>', encoding='utf-8')
    assembler = VNextDistributionAssembler(runtime, web)

    (web / 'index.html').write_text('<main>IDE</main>', encoding='utf-8')
    readiness = assembler.readiness()
    assert readiness['ready'] is False
    assert any(path.endswith('index.html') for path in readiness['forbidden'])
    (web / 'index.html').unlink()

    runtime_source = runtime / 'author_runtime.py'
    runtime_source.write_text('raise RuntimeError("source must not ship")\n', encoding='utf-8')
    readiness = assembler.readiness()
    assert readiness['ready'] is False
    assert any(path.endswith('author_runtime.py') for path in readiness['forbidden'])
    runtime_source.unlink()

    # Frozen third-party packages are allowed to carry small Python support
    # files. They are runtime dependencies, not editable EasyCode/author code.
    dependency_source = runtime / '_internal' / 'cv2' / 'config.py'
    dependency_source.parent.mkdir(parents=True)
    dependency_source.write_text('BINARIES_PATHS = []\n', encoding='utf-8')
    dependency_license = runtime / '_internal' / 'numpy.dist-info' / 'licenses' / 'src' / 'LICENSE'
    dependency_license.parent.mkdir(parents=True)
    dependency_license.write_text('third-party licence\n', encoding='utf-8')
    readiness = assembler.readiness()
    assert readiness['ready'] is True, readiness

    internal_author_source = runtime / '_internal' / 'core' / 'author_runtime.py'
    internal_author_source.parent.mkdir(parents=True)
    internal_author_source.write_text('raise RuntimeError("source must not ship")\n', encoding='utf-8')
    readiness = assembler.readiness()
    assert readiness['ready'] is False
    assert any(path.endswith('author_runtime.py') for path in readiness['forbidden'])
    internal_author_source.unlink()

    tainted_bundle = tmp_path / 'tainted.ecplayer'
    shutil.copy2(published['path'], tainted_bundle)
    with zipfile.ZipFile(tainted_bundle, 'a') as archive:
        archive.writestr(forbidden_name, '{"schema_version": 1}')
    with pytest.raises(DistributionError, match='可编辑程序源码'):
        assembler.assemble(tainted_bundle, tmp_path / 'output')


def test_release_packaging_requires_the_current_player_runtime_contract(tmp_path: Path) -> None:
    runtime = tmp_path / 'runtime'
    web = tmp_path / 'web'
    runtime.mkdir()
    web.mkdir()
    (runtime / 'EasycodePlayer.exe').write_bytes(b'fake runtime boundary')
    (runtime / 'EasycodeUpdateHelper.exe').write_bytes(b'fake update helper boundary')
    (web / 'player.html').write_text('<main>Player</main>', encoding='utf-8')
    (web / 'capture.html').write_text('<main>Capture</main>', encoding='utf-8')
    (web / 'console.html').write_text('<main>Console</main>', encoding='utf-8')
    assembler = VNextDistributionAssembler(runtime, web, require_current_runtime=True)

    missing_contract = assembler.readiness()
    assert missing_contract['ready'] is False
    assert any(path.endswith('runtime-contract.json') for path in missing_contract['missing'])

    contract_path = write_player_runtime_contract(runtime)
    current = assembler.readiness()
    assert current['ready'] is True, current
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    assert contract['contract_version'] == PLAYER_RUNTIME_CONTRACT_VERSION

    contract['contract_version'] -= 1
    contract_path.write_text(json.dumps(contract), encoding='utf-8')
    stale = assembler.readiness()
    assert stale['ready'] is False
    assert any('契约版本不匹配' in reason for reason in stale['missing'])


def test_enabled_update_config_is_signed_into_bundle_and_bootstraps_terminal_only_then(
    tmp_path: Path, monkeypatch,
) -> None:
    feed_url = 'https://updates.example.test/feed/content.bundle.test/project_content'
    signer = UpdateRepositorySigner(
        'content.bundle.test',
        {role: UpdateSigningIdentity.generate() for role in UPDATE_ROLES},
        mirrors=(feed_url,),
    )
    configuration = {
        'schema_version': 1,
        'domains': {
            'player_application': {
                'enabled': False, 'product_id': '', 'provider': 'self_hosted',
                'feed_base_url': '', 'channel': 'stable',
                'required_policy_capability': False,
                'initial_preferences': {
                    'automatic_check': True, 'automatic_download': False, 'automatic_apply': False,
                },
                'pinned_root': None,
            },
            'project_content': {
                'enabled': True, 'product_id': 'content.bundle.test', 'provider': 'self_hosted',
                'feed_base_url': feed_url, 'channel': 'stable',
                'required_policy_capability': True,
                'initial_preferences': {
                    'automatic_check': False, 'automatic_download': False, 'automatic_apply': False,
                },
                'pinned_root': signer.root_envelope(),
            },
        },
    }
    monkeypatch.setenv('EASYCODE_UPDATE_DATA_DIR', str(tmp_path / 'update-state'))
    monkeypatch.setenv('EASYCODE_UPDATE_CACHE_DIR', str(tmp_path / 'update-cache'))
    published = _publish(tmp_path, configuration)
    with zipfile.ZipFile(published['path']) as archive:
        assert 'update/config.json' in archive.namelist()
        bundled = json.loads(archive.read('update/config.json'))
        assert set(bundled['domains']) == {'project_content'}
        assert bundled['telemetry'] is False
    released = StaticUpdateRepository(tmp_path / 'feed', signer).publish_project_content(
        published['path'],
        display_version='1.0.0',
        platform='windows',
        architecture='x86_64',
    )
    assert released['release']['release_id'] == published['release_id']

    manager = VNextPlayerBundleManager()
    try:
        bootstrap = manager.load(published['path'])
        assert bootstrap['updates']['enabled'] is True
        assert set(bootstrap['updates']['domains']) == {'project_content'}
        assert bootstrap['updates']['domains']['project_content']['required_policy_capability'] is True
    finally:
        manager.shutdown()
