from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _key(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex}'


def test_legacy_execution_run_is_idempotent(monkeypatch):
    from api.routers import execution_router

    calls: list[str] = []

    class ExecutionService:
        def run_task(self, project_path, task_id, start_node_id, blueprint_data, background_tasks):
            calls.append(task_id)
            return {'execution_id': f'execution-{len(calls)}'}

    monkeypatch.setattr(
        execution_router,
        'assert_matching_legacy_path',
        lambda _request, project_path, writable=False: project_path,
    )
    app = FastAPI()
    app.include_router(execution_router.create_execution_router(ExecutionService(), None))
    payload = {'project_path': 'D:/project', 'task_id': 'main', 'start_node_id': 'node-1'}
    headers = {'Idempotency-Key': _key('legacy-run')}

    with TestClient(app) as client:
        first = client.post('/api/run', headers=headers, json=payload)
        replay = client.post('/api/run', headers=headers, json=payload)
        conflict = client.post('/api/run', headers=headers, json={**payload, 'task_id': 'other'})

    assert first.status_code == 200
    assert replay.json() == first.json()
    assert calls == ['main']
    assert conflict.status_code == 409
    assert conflict.json()['detail']['code'] == 'idempotency_conflict'


def test_legacy_export_build_is_idempotent(monkeypatch):
    from api.routers import build_router

    calls: list[dict] = []

    class ExportService:
        def build_export_bundle(self, project_path, form_schema, acknowledge_warnings):
            calls.append(form_schema)
            return {'status': 'success', 'bundle': f'bundle-{len(calls)}'}

    monkeypatch.setattr(
        build_router,
        'assert_matching_legacy_path',
        lambda _request, project_path, writable=False: project_path,
    )
    app = FastAPI()
    app.include_router(build_router.create_build_router(ExportService(), None, None))
    payload = {'project_path': 'D:/project', 'form_schema': {'fields': []}}
    headers = {'Idempotency-Key': _key('legacy-build')}

    with TestClient(app) as client:
        first = client.post('/api/exporter/build', headers=headers, json=payload)
        replay = client.post('/api/exporter/build', headers=headers, json=payload)

    assert first.status_code == 200
    assert replay.json() == first.json()
    assert calls == [{'fields': []}]


def test_legacy_capture_asset_save_is_idempotent(monkeypatch):
    from api.routers import capture_router

    calls: list[dict] = []

    def save_assets(payload):
        calls.append(payload)
        return {'transaction_id': f'transaction-{len(calls)}', 'assets': []}

    monkeypatch.setattr(capture_router.capture_session_service, 'save_assets', save_assets)
    app = FastAPI()
    app.include_router(capture_router.create_capture_router())
    payload = {
        'snapshot_id': 'snapshot-1',
        'rects': [[10, 20, 30, 40]],
        'category': 'image',
    }
    headers = {'Idempotency-Key': _key('capture-save')}

    with TestClient(app) as client:
        first = client.post('/api/capture/assets', headers=headers, json=payload)
        replay = client.post('/api/capture/assets', headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert replay.json() == first.json()
    assert len(calls) == 1
