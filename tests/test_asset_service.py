import json
import io
import zipfile

import pytest
from PIL import Image

from core.services.asset_service import AssetService
from core.services.vision_service import VisionService
from core.builder.exporter import ProjectExporter
from core.player.loader import PlayerAssetLoader


def test_asset_registry_uses_stable_ids_and_purpose_directories(tmp_path):
    root = AssetService.ensure_structure(str(tmp_path))
    for name in ('image', 'ocr', 'page'):
        assert (tmp_path / 'templates' / name).is_dir()
    assert not (tmp_path / 'templates' / 'shared').exists()

    image_path = tmp_path / 'templates' / 'page' / 'login.png'
    Image.new('RGB', (12, 8), (20, 30, 40)).save(image_path)
    first = AssetService.register_file(
        str(tmp_path),
        'page/login.png',
        'page',
        capture={
            'region': [10, 20, 12, 8],
            'reference_size': [1280, 720],
            'coordinate_space': 'workspace_px',
        },
    )

    reference = AssetService.reference(first['id'])
    resolved = AssetService.resolve(str(tmp_path), reference)
    assert resolved['full_path'] == str(image_path)
    assert resolved['key'] == 'page/login'
    assert first['kind'] == 'page'
    assert first['width'] == 12
    assert first['height'] == 8

    api_record = VisionService.resolve_template(str(tmp_path), reference)
    assert api_record['capture'] == {
        'region': [10, 20, 12, 8],
        'reference_size': [1280, 720],
        'coordinate_space': 'workspace_px',
    }

    Image.new('RGB', (16, 9), (50, 60, 70)).save(image_path)
    second = AssetService.register_file(str(tmp_path), 'page/login.png', 'page')
    assert second['id'] == first['id']
    assert second['width'] == 16
    assert second['height'] == 9

    registry = json.loads((tmp_path / 'templates' / 'assets.json').read_text(encoding='utf-8'))
    assert registry['schema_version'] == 2
    assert registry['assets'][first['id']]['path'] == 'page/login.png'


def test_preview_exposes_stable_reference_without_embedding_full_base64(tmp_path):
    AssetService.ensure_structure(str(tmp_path))
    Image.new('RGB', (4, 3), (1, 2, 3)).save(tmp_path / 'templates' / 'image' / 'button.png')
    record = AssetService.register_file(str(tmp_path), 'image/button.png', 'image')

    preview = VisionService.get_template_preview(str(tmp_path), 'image')

    assert preview['images'] == [{
        'name': 'button.png',
        'relative_path': 'image/button.png',
        'asset_id': record['id'],
        'asset_ref': AssetService.reference(record['id']),
        'kind': 'image',
    }]


def test_asset_path_cannot_escape_templates_root(tmp_path):
    AssetService.ensure_structure(str(tmp_path))
    with pytest.raises(ValueError):
        AssetService.resolve(str(tmp_path), '../outside.png', require_exists=False)


def test_player_loader_aliases_registered_asset_ids_to_memory_templates(tmp_path):
    image_stream = io.BytesIO()
    Image.new('RGB', (5, 4), (100, 110, 120)).save(image_stream, format='PNG')
    registry = {
        'schema_version': 2,
        'assets': {
            'asset_login': {
                'id': 'asset_login',
                'path': 'page/login.png',
                'key': 'page/login',
                'kind': 'page',
            }
        },
    }
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, 'w') as archive:
        archive.writestr('blueprint.json', '{"tasks": []}')
        archive.writestr('form_schema.json', '{}')
        archive.writestr('templates/assets.json', json.dumps(registry))
        archive.writestr('templates/page/login.png', image_stream.getvalue())
    bundle = tmp_path / 'assets.ebp'
    bundle.write_bytes(ProjectExporter.encrypt_data(zip_stream.getvalue()))

    _, _, _, templates, _ = PlayerAssetLoader.load_bundle_from_ebp(str(bundle))

    assert 'page/login' in templates
    assert 'asset://asset_login' in templates
    assert templates['asset://asset_login'] is templates['page/login']
