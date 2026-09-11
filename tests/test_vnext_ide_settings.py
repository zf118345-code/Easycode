from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routers.vnext_router as vnext_router_module
from api.routers.vnext_router import create_vnext_router
from core.vnext.ide_settings_v6 import (
    DEFAULT_IDE_SHORTCUTS,
    IdeSettingsError,
    IdeSettingsStore,
    normalize_shortcut,
)


def test_normalize_ide_shortcut_uses_stable_modifier_order():
    assert normalize_shortcut('shift+ctrl+m') == 'Ctrl+Shift+M'
    assert normalize_shortcut('del') == 'Delete'
    assert normalize_shortcut('') == ''


def test_ide_settings_roundtrip_and_corrupt_recovery(tmp_path: Path):
    path = tmp_path / 'ide-settings.json'
    store = IdeSettingsStore(path)
    saved = store.save({'view.toggle_log': 'alt+l'})
    assert saved['shortcuts']['view.toggle_log'] == 'Alt+L'
    assert store.load() == saved

    path.write_text('{broken', encoding='utf-8')
    assert store.load()['shortcuts'] == DEFAULT_IDE_SHORTCUTS


def test_ide_settings_reject_unknown_and_duplicate_shortcuts(tmp_path: Path):
    store = IdeSettingsStore(tmp_path / 'ide-settings.json')
    with pytest.raises(IdeSettingsError, match='未知快捷键命令'):
        store.save({'unknown.command': 'Ctrl+Q'})
    with pytest.raises(IdeSettingsError, match='不能重复'):
        store.save({'edit.find': 'Ctrl+Z'})


def test_ide_settings_http_roundtrip_uses_current_user_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = IdeSettingsStore(tmp_path / 'ide-settings.json')
    monkeypatch.setattr(vnext_router_module, 'ide_settings_store', store)
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)

    initial = client.get('/api/vnext/ide-settings')
    assert initial.status_code == 200
    assert initial.json()['defaults'] == DEFAULT_IDE_SHORTCUTS

    saved = client.put('/api/vnext/ide-settings', json={'shortcuts': {'view.toggle_log': 'Alt+L'}})
    assert saved.status_code == 200
    assert saved.json()['shortcuts']['view.toggle_log'] == 'Alt+L'
    assert client.get('/api/vnext/ide-settings').json() == saved.json()

    duplicate = client.put('/api/vnext/ide-settings', json={'shortcuts': {'edit.find': 'Ctrl+Z'}})
    assert duplicate.status_code == 422
    assert duplicate.json()['detail']['code'] == 'ide_settings.invalid_shortcut'
