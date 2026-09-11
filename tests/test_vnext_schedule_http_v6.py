from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_schedule_router import create_vnext_schedule_router
from core.vnext.schedule_v6 import (
    DispatchAcceptance,
    LocalDispatchRequest,
    ScheduleServiceV6,
    StaticScheduleReferenceResolver,
    VirtualClock,
    reset_schedule_service_v6_for_tests,
)


class AcceptingDispatcher:
    def accept(self, request: LocalDispatchRequest) -> DispatchAcceptance:
        return DispatchAcceptance(request.dispatch_id, f'run-{request.dispatch_id[-12:]}')


def _client(tmp_path: Path) -> TestClient:
    resolver = StaticScheduleReferenceResolver(
        {
            ('host-local', 'instance-a', 'product-a', 'profile-a'): {
                'dispatch_scope': 'local',
                'host_name': '此电脑',
                'instance_name': '实例 A',
                'product_name': '产品 A',
                'profile_name': '默认方案',
                'release_id': 'release-6',
            }
        }
    )
    service = ScheduleServiceV6(
        tmp_path / 'schedules.sqlite3',
        clock=VirtualClock('2026-09-01T00:00:00Z'),
        resolver=resolver,
        dispatcher=AcceptingDispatcher(),
    )
    app = FastAPI()
    app.include_router(create_vnext_schedule_router(service))
    return TestClient(app)


def _payload() -> dict[str, object]:
    return {
        'schedule_id': 'schedule-http',
        'name': '每日本机计划',
        'timezone_id': 'Asia/Shanghai',
        'trigger': {'type': 'daily', 'local_time': '08:30:00'},
        'misfire_policy': 'skip',
        'max_lateness_seconds': 0,
        'overlap_policy': 'queue_once',
        'dispatch_mode': 'simultaneous',
        'entries': [
            {
                'entry_id': 'entry-a',
                'host_id': 'host-local',
                'instance_id': 'instance-a',
                'product_id': 'product-a',
                'profile_id': 'profile-a',
            }
        ],
    }


def test_schedule_crud_contract_and_revision_conflict(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post('/api/vnext/schedules', json=_payload())
    assert created.status_code == 201
    body = created.json()
    assert body['schedule_id'] == 'schedule-http'
    assert body['revision'] == 1
    assert body['entries'][0]['validated_summary']['release_id'] == 'release-6'

    assert client.get('/api/vnext/schedules').json()[0]['schedule_id'] == 'schedule-http'
    assert client.get('/api/vnext/schedules/schedule-http').status_code == 200

    updated_payload = {**_payload(), 'name': '已更新计划', 'expected_revision': 1}
    updated = client.put('/api/vnext/schedules/schedule-http', json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()['revision'] == 2

    conflict = client.put('/api/vnext/schedules/schedule-http', json=updated_payload)
    assert conflict.status_code == 409
    detail = conflict.json()['detail']
    assert detail['code'] == 'schedule.revision_conflict'
    assert detail['recovery']['action'] == 'reload_schedules'
    assert detail['diagnostics'][0]['actual_revision'] == 2

    deleted = client.delete(
        '/api/vnext/schedules/schedule-http',
        params={'expected_revision': 2},
    )
    assert deleted.status_code == 200
    assert deleted.json()['deleted_at'] is not None
    assert client.get('/api/vnext/schedules/schedule-http').status_code == 404


def test_schedule_http_rejects_unknown_fields_and_invalid_references(tmp_path: Path) -> None:
    client = _client(tmp_path)
    document = client.get('/openapi.json').json()
    assert document['components']['schemas']['SchedulePlanRequest']['additionalProperties'] is False
    assert '409' in document['paths']['/api/vnext/schedules/{schedule_id}']['put']['responses']
    unknown = client.post(
        '/api/vnext/schedules',
        json={**_payload(), 'looks_nice_but_is_not_real': True},
    )
    assert unknown.status_code == 422

    payload = _payload()
    payload['entries'] = [
        {
            **payload['entries'][0],
            'profile_id': 'profile-missing',
        }
    ]
    missing = client.post('/api/vnext/schedules', json=payload)
    assert missing.status_code == 422
    assert missing.json()['detail']['code'] == 'schedule.reference_unknown'


def test_schedule_history_endpoints_are_read_only_and_bounded(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.post('/api/vnext/schedules', json=_payload()).status_code == 201
    diagnostics = client.get('/api/vnext/schedules/diagnostics')
    assert diagnostics.status_code == 200
    assert diagnostics.json()[0]['event_type'] == 'schedule.created'
    assert client.get('/api/vnext/schedules/occurrences').json() == []
    assert client.get('/api/vnext/schedules/dispatches').json() == []
    assert client.get('/api/vnext/schedules/diagnostics', params={'limit': 5001}).status_code == 422


def test_router_and_openapi_do_not_create_runtime_state_until_first_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / 'lazy' / 'schedules.sqlite3'
    monkeypatch.setenv('EASYCODE_VNEXT_SCHEDULE_DATABASE', str(database))
    reset_schedule_service_v6_for_tests()
    app = FastAPI()
    app.include_router(create_vnext_schedule_router())
    assert database.exists() is False
    TestClient(app).get('/openapi.json')
    assert database.exists() is False
    response = TestClient(app).get('/api/vnext/schedules')
    assert response.status_code == 200
    assert database.exists() is True
    reset_schedule_service_v6_for_tests()
