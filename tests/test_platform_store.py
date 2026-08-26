import time
import urllib.error

from core.services.platform_runtime_service import PlatformRuntimeService
from core.services.platform_store import PlatformStore


def test_state_is_namespaced_and_persistent(tmp_path):
    path = tmp_path / 'platform.db'
    store = PlatformStore(str(path))
    store.set_state('count', 3, 'account-a')
    store.set_state('count', 7, 'account-b')
    reopened = PlatformStore(str(path))
    assert reopened.get_state('count', 'account-a') == 3
    assert reopened.get_state('count', 'account-b') == 7


def test_message_claim_is_exclusive_and_acknowledged(tmp_path):
    store = PlatformStore(str(tmp_path / 'platform.db'))
    published = store.publish_message('team', {'code': 123}, sender='a')
    first = store.claim_messages('team', 'consumer-a')
    second = store.claim_messages('team', 'consumer-b')
    assert [item['id'] for item in first] == [published['id']]
    assert second == []
    assert store.ack_message(published['id'], 'consumer-b') is False
    assert store.ack_message(published['id'], 'consumer-a') is True
    assert store.claim_messages('team', 'consumer-a') == []


def test_lease_owner_and_token_protect_release(tmp_path):
    store = PlatformStore(str(tmp_path / 'platform.db'))
    lease = store.acquire_lease('emulator:1', 'worker-a', 30)
    assert lease
    assert store.acquire_lease('emulator:1', 'worker-b', 30) is None
    assert store.release_lease('emulator:1', 'worker-a', 'wrong') is False
    assert store.release_lease('emulator:1', 'worker-a', lease['token']) is True
    assert store.acquire_lease('emulator:1', 'worker-b', 30)


def test_daily_interval_and_once_schedule_lifecycle(tmp_path):
    store = PlatformStore(str(tmp_path / 'platform.db'))
    saved = store.save_schedule('fast', 'interval', '1', {'task_id': 't', 'node_id': 'n'})
    assert saved['next_run_at'] > time.time()
    with store._connect() as db:
        db.execute('UPDATE schedules SET next_run_at=? WHERE id=?', (time.time() - 1, saved['id']))
    due = store.claim_due_schedules('scheduler-a')
    assert [item['id'] for item in due] == [saved['id']]
    assert store.claim_due_schedules('scheduler-b') == []
    assert store.complete_schedule(saved['id'], 'scheduler-a', success=True)
    assert store.list_schedules()[0]['next_run_at'] > time.time()


def test_outbox_backoff_and_completion(tmp_path):
    store = PlatformStore(str(tmp_path / 'platform.db'))
    item = store.enqueue_outbox('http://127.0.0.1:9', 'token', 'message.publish', {'value': 1})
    due = store.due_outbox()
    assert due[0]['id'] == item['id']
    store.fail_outbox(item['id'], 1, 'offline')
    assert store.due_outbox() == []
    with store._connect() as db:
        db.execute('UPDATE outbox SET next_attempt_at=? WHERE id=?', (time.time() - 1, item['id']))
    store.complete_outbox(item['id'])
    assert store.outbox_status()['sent'] == 1


def test_remote_message_outbox_reuses_client_message_id(tmp_path, monkeypatch):
    service = PlatformRuntimeService()
    store = PlatformStore(str(tmp_path / 'platform.db'))
    sent_payloads = []

    def offline(_url, _token, payload, timeout=5.0):
        sent_payloads.append(payload)
        raise urllib.error.URLError('offline')

    monkeypatch.setattr(service, '_post_json', offline)
    result = service.send_remote_message(store, 'http://coordinator', 'secret', 'team', {'ready': True})

    assert result['queued'] is True
    assert result['message_id']
    queued = store.due_outbox()[0]
    assert sent_payloads[0]['id'] == result['message_id']
    assert queued['payload']['id'] == result['message_id']
