from __future__ import annotations

import logging

from api.errors import failure_detail, legacy_error_envelope, status_policy


def test_request_identity_echoes_valid_client_id_and_logs_completion(client, caplog):
    caplog.set_level(logging.INFO, logger='api.app')

    response = client.get('/api/params', headers={'X-Request-ID': 'desktop.req-42'})

    assert response.status_code == 200
    assert response.headers['X-Request-ID'] == 'desktop.req-42'
    record = next(
        item for item in caplog.records
        if getattr(item, 'event', '') == 'api.request.completed'
        and getattr(item, 'request_id', '') == 'desktop.req-42'
    )
    assert record.method == 'GET'
    assert record.path == '/api/params'
    assert record.status_code == 200
    assert record.duration_ms >= 0


def test_request_identity_replaces_unsafe_client_id(client):
    response = client.get('/api/params', headers={'X-Request-ID': 'bad id/with spaces'})

    request_id = response.headers['X-Request-ID']
    assert request_id.startswith('req_')
    assert request_id != 'bad id/with spaces'


def test_legacy_http_error_preserves_detail_and_adds_recovery_contract(client):
    response = client.get(
        '/api/execution/missing/stream',
        headers={'X-Request-ID': 'legacy-404'},
    )

    assert response.status_code == 404
    body = response.json()
    assert body['detail'] == '执行记录不存在'
    assert body['message'] == '执行记录不存在'
    assert body['code'] == 'not_found'
    assert body['request_id'] == 'legacy-404'
    assert body['recovery'] == {'retryable': False, 'action': 'none', 'message': ''}


def test_error_policy_builds_stable_vnext_and_legacy_envelopes():
    assert status_policy(409) == ('state_conflict', True, 'retry')
    detail = failure_detail('state_conflict', '版本已变化', request_id='req-1', retryable=True, action='reload')
    assert detail == {
        'code': 'state_conflict',
        'message': '版本已变化',
        'request_id': 'req-1',
        'fields': [],
        'recovery': {'retryable': True, 'action': 'reload', 'message': ''},
        'diagnostics': [],
    }
    legacy = legacy_error_envelope(503, {'message': '服务暂不可用'}, 'req-2')
    assert legacy['detail'] == {'message': '服务暂不可用'}
    assert legacy['code'] == 'service_unavailable'
    assert legacy['recovery'] == {'retryable': True, 'action': 'retry', 'message': ''}


def test_high_risk_operation_contracts_reject_unknown_or_unsafe_fields(client):
    cases = [
        ('/api/exporter/preflight', {'project_path': 'D:/project', 'project_paht': 'typo'}),
        ('/api/player/run', {'instance_id': 'instance-1', 'resuem': True}),
        ('/api/adb/resolve', {'window_title': '模拟器', 'process_id': -1}),
        ('/api/frame-recording/start', {
            'project_path': 'D:/project',
            'options': {'target_fps': 241},
        }),
        ('/api/run', {
            'project_path': 'D:/project', 'task_id': 'main', 'start_node': 'typo',
        }),
        ('/api/execution/missing/step', {'step': 'sideways'}),
        ('/api/execution/missing/breakpoints/add', {'node_id': ''}),
    ]

    for endpoint, payload in cases:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 422, (endpoint, response.text)


def test_operation_openapi_models_are_strict(client):
    schemas = client.get('/openapi.json').json()['components']['schemas']

    for name in (
        'ExporterBuildRequest',
        'ExporterPreflightRequest',
        'ExecutionRunRequest',
        'ExecutionStepRequest',
        'FrameRecordingStartRequest',
        'PlayerRunRequest',
        'ProjectSettingsRequest',
    ):
        assert schemas[name]['additionalProperties'] is False
