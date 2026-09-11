from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.services.idempotency_service import (
    IdempotencyConflict,
    IdempotencyExecutionFailed,
    IdempotencyLedger,
)


def test_concurrent_duplicate_requests_execute_producer_once():
    ledger = IdempotencyLedger()
    counter = 0
    counter_lock = threading.Lock()

    def invoke():
        nonlocal counter
        claim = ledger.claim('request-1', 'publish', {'workspace': 'w1', 'revision': 7})
        if claim.role == 'cached':
            return claim.cached_result
        if claim.role == 'wait':
            return ledger.wait(claim, timeout=2)
        with counter_lock:
            counter += 1
        time.sleep(0.05)
        result = {'artifact': 'release.ecplayer', 'items': [1, 2, 3]}
        ledger.complete(claim, result)
        return result

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _index: invoke(), range(24)))

    assert counter == 1
    assert all(item == results[0] for item in results)
    results[0]['items'].append(4)
    assert ledger.claim('request-1', 'publish', {'workspace': 'w1', 'revision': 7}).cached_result == {
        'artifact': 'release.ecplayer', 'items': [1, 2, 3],
    }


def test_same_key_with_different_request_is_rejected():
    ledger = IdempotencyLedger()
    leader = ledger.claim('request-2', 'run', {'entry': 'main'})

    with pytest.raises(IdempotencyConflict, match='不同请求'):
        ledger.claim('request-2', 'run', {'entry': 'other'})

    ledger.complete(leader, {'execution_id': 'execution_1'})


def test_failed_leader_wakes_waiters_and_allows_a_later_retry():
    ledger = IdempotencyLedger()
    leader = ledger.claim('request-3', 'save', {'revision': 1})
    waiter = ledger.claim('request-3', 'save', {'revision': 1})

    ledger.fail(leader, RuntimeError('disk unavailable'))

    with pytest.raises(IdempotencyExecutionFailed, match='disk unavailable'):
        ledger.wait(waiter, timeout=0.2)
    assert ledger.claim('request-3', 'save', {'revision': 1}).role == 'leader'


@pytest.mark.parametrize('key', ['', 'with space', '/path', 'x' * 201])
def test_unsafe_idempotency_keys_are_rejected(key: str):
    with pytest.raises(ValueError, match='Idempotency-Key'):
        IdempotencyLedger().claim(key, 'save', {})
