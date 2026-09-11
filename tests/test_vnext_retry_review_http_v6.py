from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.vnext_router import create_vnext_router

LOG_CONTENT = 'official.log.output.parameter.content'


def _open(tmp_path: Path) -> tuple[TestClient, str, str, dict[str, str]]:
    app = FastAPI()
    app.include_router(create_vnext_router())
    client = TestClient(app)
    opened = client.post('/api/vnext/workspaces/open', json={
        'path': str(tmp_path / 'retry-review'),
        'initialize': True,
        'project_name': '重试审核',
    })
    assert opened.status_code == 200, opened.text
    payload = opened.json()
    workspace = payload['workspace']
    return client, payload['inspection']['entry_function_id'], payload['programs'][0]['revision'], {
        'X-Workspace-ID': workspace['workspace_id'],
        'X-Workspace-Generation': str(workspace['generation']),
    }


def _request(
    client: TestClient,
    headers: dict[str, str],
    function_id: str,
    revision: str,
    command: dict,
):
    return client.post(
        f'/api/vnext/programs/{function_id}/commands',
        headers=headers,
        json={'expected_revision': revision, 'command': command},
    )


def _ok(*args, **kwargs) -> dict:
    response = _request(*args, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def _retry_policy(prefix: str) -> dict:
    return {
        'max_retries': {'value_id': f'value_{prefix}_count', 'kind': 'int64', 'value': 2},
        'interval': {
            'value_id': f'value_{prefix}_interval',
            'kind': 'duration',
            'milliseconds': 10,
        },
        'transient_only': True,
    }


def _try_statement(snapshot: dict, statement_id: str) -> dict:
    return next(
        item
        for item in snapshot['document']['function']['statements']
        if item['statement_id'] == statement_id
    )


def test_retry_risk_review_is_server_owned_revisioned_and_invalidated(tmp_path: Path) -> None:
    client, function_id, revision, headers = _open(tmp_path)
    tried = _ok(client, headers, function_id, revision, {
        'kind': 'insert_try',
        'retry_policy': _retry_policy('risk'),
    })
    try_id = tried['selected_statement_id']
    inserted = _ok(client, headers, function_id, tried['revision'], {
        'kind': 'insert_call',
        'function_id': 'official.log.output',
        'arguments': {
            LOG_CONTENT: {'value_id': 'value_log_content', 'kind': 'string', 'value': '第一次'},
        },
        'location': {'parent_statement_id': try_id, 'block': 'body'},
    })
    log_id = inserted['selected_statement_id']
    assert any(item['code'] == 'PGM-TRY-003' for item in inserted['diagnostics'])

    compile_before = client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    )
    assert compile_before.status_code == 200, compile_before.text
    assert compile_before.json()['valid'] is False
    assert any(item['code'] == 'PGM-TRY-003' for item in compile_before.json()['diagnostics'])

    reviewed = _ok(client, headers, function_id, inserted['revision'], {
        'kind': 'review_retry_risk', 'statement_id': try_id,
    })
    fingerprint = _try_statement(reviewed, try_id)['retry_policy']['author_review_fingerprint']
    assert fingerprint.startswith('sha256:')
    assert reviewed['selected_statement_id'] == try_id
    assert reviewed['can_undo'] is True
    assert not any(item['code'] == 'PGM-TRY-003' for item in reviewed['diagnostics'])
    assert client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    ).json()['valid'] is True

    changed = _ok(client, headers, function_id, reviewed['revision'], {
        'kind': 'update_argument',
        'statement_id': log_id,
        'parameter_id': LOG_CONTENT,
        'value': {'value_id': 'client_replacement', 'kind': 'string', 'value': '第二次'},
    })
    changed_try = _try_statement(changed, try_id)
    assert changed_try['retry_policy']['author_review_fingerprint'] == fingerprint
    assert changed_try['body'][0]['arguments'][LOG_CONTENT]['value_id'] == 'value_log_content'
    assert any(item['code'] == 'PGM-TRY-003' for item in changed['diagnostics'])
    assert client.post(
        f'/api/vnext/programs/{function_id}/compile', headers=headers, json={},
    ).json()['valid'] is False

    stale = _request(client, headers, function_id, reviewed['revision'], {
        'kind': 'review_retry_risk', 'statement_id': try_id,
    })
    assert stale.status_code == 409

    reviewed_again = _ok(client, headers, function_id, changed['revision'], {
        'kind': 'review_retry_risk', 'statement_id': try_id,
    })
    assert _try_statement(reviewed_again, try_id)['retry_policy'][
        'author_review_fingerprint'
    ] != fingerprint
    undone = client.post(
        f'/api/vnext/programs/{function_id}/undo',
        headers=headers,
        json={'expected_revision': reviewed_again['revision']},
    )
    assert undone.status_code == 200, undone.text
    assert any(item['code'] == 'PGM-TRY-003' for item in undone.json()['diagnostics'])
    redone = client.post(
        f'/api/vnext/programs/{function_id}/redo',
        headers=headers,
        json={'expected_revision': undone.json()['revision']},
    )
    assert redone.status_code == 200, redone.text
    assert not any(item['code'] == 'PGM-TRY-003' for item in redone.json()['diagnostics'])


def test_retry_review_rejects_inapplicable_and_client_fingerprint(tmp_path: Path) -> None:
    client, function_id, revision, headers = _open(tmp_path)
    no_retry = _ok(client, headers, function_id, revision, {'kind': 'insert_try'})
    rejected = _request(client, headers, function_id, no_retry['revision'], {
        'kind': 'review_retry_risk', 'statement_id': no_retry['selected_statement_id'],
    })
    assert rejected.status_code == 422

    harmless = _ok(client, headers, function_id, no_retry['revision'], {
        'kind': 'insert_try', 'retry_policy': _retry_policy('harmless'),
    })
    harmless_id = harmless['selected_statement_id']
    harmless = _ok(client, headers, function_id, harmless['revision'], {
        'kind': 'insert_call',
        'function_id': 'official.wait.duration',
        'location': {'parent_statement_id': harmless_id, 'block': 'body'},
    })
    rejected = _request(client, headers, function_id, harmless['revision'], {
        'kind': 'review_retry_risk', 'statement_id': harmless_id,
    })
    assert rejected.status_code == 422

    forged = _request(client, headers, function_id, harmless['revision'], {
        'kind': 'update_try_retry_policy',
        'statement_id': harmless_id,
        'retry_policy': {
            **_retry_policy('forged'),
            'author_review_fingerprint': 'sha256:' + ('0' * 64),
        },
    })
    assert forged.status_code == 422
