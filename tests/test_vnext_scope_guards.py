from __future__ import annotations

import zipfile
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.vnext.extension_schema_v6 import HostVariantV1
from core.vnext.function_contracts_v6 import official_function_registry_v6
from core.vnext.publish import VNextPublisher
from core.vnext.pure_operations_v6 import PURE_OPERATION_REGISTRY_VERSION, pure_operation_registry_hash


def test_v1_catalog_does_not_reintroduce_page_topology_functions() -> None:
    catalog = official_function_registry_v6.available_catalog()

    assert all(item.get('namespace') != '页面' for item in catalog)
    assert all(not str(item.get('opcode') or '').startswith('page.') for item in catalog)


def test_python_windows_variant_cannot_claim_android_native() -> None:
    compatible = HostVariantV1.model_validate({
        'variant_id': 'com.example.extension.windows',
        'host': 'windows',
        'runtime': 'python-worker-3.12',
        'targets': ['windows', 'android_adb', 'none'],
        'development_entry': 'src/main.py',
        'entrypoints': {},
    })
    assert 'android_native' not in compatible.targets
    with pytest.raises(ValidationError):
        HostVariantV1.model_validate({
            **compatible.model_dump(mode='json'),
            'targets': ['android_native'],
        })


def test_source_only_extension_blocks_publish_and_source_tree_is_never_bundled(tmp_path: Path) -> None:
    extension_root = tmp_path / 'extensions' / 'example.extension'
    extension_root.mkdir(parents=True)
    (extension_root / 'main.py').write_text('SECRET_SOURCE = True\n', encoding='utf-8')
    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'resource.txt').write_text('asset', encoding='utf-8')
    publisher = VNextPublisher(str(tmp_path))
    (tmp_path / 'easycode.lock').write_text(json.dumps({
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
    linked = {
        'diagnostics': [],
        'ecir': {
            'functions': [],
            'required_capabilities': [],
            'supported_platforms': ['windows'],
        },
    }
    packages = {'packages': [], 'errors': [{
        'source': 'example.extension',
        'message': 'source-only extension has no locked ecx-runtime-1 artifact',
    }]}

    blocked = publisher.report(linked, {'pages': []}, extension_errors=packages['errors'], extension_packages=packages)

    assert blocked['valid'] is False
    assert any(item['code'] == 'P2001' for item in blocked['errors'])

    # Exercise the archive boundary independently with an otherwise valid
    # report: the publisher may include project assets, but it must never walk
    # the editable extension source directory.
    built = publisher.build(
        linked,
        {'pages': []},
        {'project_id': 'project_test', 'name': 'test'},
        {'valid': True},
    )
    with zipfile.ZipFile(built['path']) as archive:
        names = archive.namelist()
    assert 'assets/resource.txt' in names
    assert not any(name.startswith('extensions/') for name in names)
    assert not any(name.endswith('.py') for name in names)
