"""Thread-safe bounded idempotency ledger for mutating API operations."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

_SAFE_KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$')


class IdempotencyConflict(RuntimeError):
    """The same operation/key pair was reused with a different request."""


class IdempotencyWaitTimeout(TimeoutError):
    """A duplicate request waited too long for the leader to complete."""


class IdempotencyExecutionFailed(RuntimeError):
    def __init__(self, original: BaseException):
        super().__init__(str(original))
        self.original = original


@dataclass(frozen=True)
class IdempotencyClaim:
    entry_id: str
    role: str
    cached_result: Any = None


@dataclass
class _Entry:
    entry_id: str
    composite_key: str
    fingerprint: str
    state: str
    created_at: float
    completed_at: float = 0
    result: Any = None
    error: BaseException | None = None


class IdempotencyLedger:
    def __init__(self, *, ttl_seconds: float = 15 * 60, max_entries: int = 2_000):
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._max_entries = max(16, int(max_entries))
        self._condition = threading.Condition(threading.RLock())
        self._active: dict[str, str] = {}
        self._entries: dict[str, _Entry] = {}

    @staticmethod
    def fingerprint(payload: Any) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
            default=lambda value: repr(value),
        ).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def validate_key(key: str) -> str:
        value = str(key or '').strip()
        if not _SAFE_KEY.fullmatch(value):
            raise ValueError('Idempotency-Key 必须是 1-200 位字母、数字或 . _ : -')
        return value

    def _cleanup_locked(self, now: float) -> None:
        expired = [
            entry_id for entry_id, entry in self._entries.items()
            if entry.state != 'pending' and now - (entry.completed_at or entry.created_at) > self._ttl_seconds
        ]
        terminal = sorted(
            (entry for entry in self._entries.values() if entry.state != 'pending' and entry.entry_id not in expired),
            key=lambda entry: entry.completed_at or entry.created_at,
        )
        overflow = max(0, len(self._entries) - len(expired) - self._max_entries)
        expired.extend(entry.entry_id for entry in terminal[:overflow])
        for entry_id in set(expired):
            entry = self._entries.pop(entry_id, None)
            if entry and self._active.get(entry.composite_key) == entry_id:
                self._active.pop(entry.composite_key, None)

    def claim(self, key: str, operation: str, payload: Any) -> IdempotencyClaim:
        clean_key = self.validate_key(key)
        clean_operation = str(operation or '').strip()
        if not clean_operation:
            raise ValueError('幂等操作名称不能为空')
        composite = f'{clean_operation}:{clean_key}'
        fingerprint = self.fingerprint(payload)
        now = time.monotonic()
        with self._condition:
            self._cleanup_locked(now)
            entry_id = self._active.get(composite)
            entry = self._entries.get(entry_id or '')
            if entry is not None:
                if entry.fingerprint != fingerprint:
                    raise IdempotencyConflict('相同 Idempotency-Key 已用于不同请求，请生成新键后重试')
                if entry.state == 'completed':
                    return IdempotencyClaim(entry.entry_id, 'cached', copy.deepcopy(entry.result))
                if entry.state == 'pending':
                    return IdempotencyClaim(entry.entry_id, 'wait')
                self._active.pop(composite, None)

            entry = _Entry(
                entry_id=f'idem_{uuid.uuid4().hex}',
                composite_key=composite,
                fingerprint=fingerprint,
                state='pending',
                created_at=now,
            )
            self._entries[entry.entry_id] = entry
            self._active[composite] = entry.entry_id
            return IdempotencyClaim(entry.entry_id, 'leader')

    def complete(self, claim: IdempotencyClaim, result: Any) -> None:
        with self._condition:
            entry = self._entries.get(claim.entry_id)
            if entry is None or entry.state != 'pending':
                return
            entry.state = 'completed'
            entry.completed_at = time.monotonic()
            entry.result = copy.deepcopy(result)
            self._condition.notify_all()

    def fail(self, claim: IdempotencyClaim, error: BaseException) -> None:
        with self._condition:
            entry = self._entries.get(claim.entry_id)
            if entry is None or entry.state != 'pending':
                return
            entry.state = 'failed'
            entry.completed_at = time.monotonic()
            entry.error = error
            if self._active.get(entry.composite_key) == entry.entry_id:
                self._active.pop(entry.composite_key, None)
            self._condition.notify_all()

    def wait(self, claim: IdempotencyClaim, timeout: float = 600) -> Any:
        deadline = time.monotonic() + max(0.1, float(timeout))
        with self._condition:
            while True:
                entry = self._entries.get(claim.entry_id)
                if entry is None:
                    raise IdempotencyWaitTimeout('幂等请求记录已过期，请重试')
                if entry.state == 'completed':
                    return copy.deepcopy(entry.result)
                if entry.state == 'failed':
                    raise IdempotencyExecutionFailed(entry.error or RuntimeError('原请求失败'))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise IdempotencyWaitTimeout('等待相同请求完成超时，请查询操作状态后再重试')
                self._condition.wait(remaining)


idempotency_ledger = IdempotencyLedger()
