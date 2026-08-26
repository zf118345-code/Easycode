from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def _decode(value: str | None, fallback=None):
    if value in (None, ''):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


class PlatformStore:
    """Small durable runtime database shared by IDE and Player services."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str) -> None:
        self.path = str(Path(path).resolve())
        self._init_lock = threading.Lock()
        self._initialized = False
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA synchronous=NORMAL')
        connection.execute('PRAGMA busy_timeout=10000')
        connection.execute('PRAGMA foreign_keys=ON')
        return connection

    def _ensure_schema(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            with self._connect() as db:
                db.executescript(
                    '''
                    CREATE TABLE IF NOT EXISTS state_values (
                        namespace TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value_json TEXT NOT NULL,
                        updated_at REAL NOT NULL,
                        PRIMARY KEY(namespace, key)
                    );
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        channel TEXT NOT NULL,
                        sender TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ready',
                        claimed_by TEXT,
                        claimed_until REAL,
                        created_at REAL NOT NULL,
                        expires_at REAL
                    );
                    CREATE INDEX IF NOT EXISTS idx_messages_ready
                        ON messages(channel, status, created_at);
                    CREATE TABLE IF NOT EXISTS leases (
                        resource_key TEXT PRIMARY KEY,
                        owner TEXT NOT NULL,
                        token TEXT NOT NULL,
                        expires_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS schedules (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        schedule_type TEXT NOT NULL,
                        schedule_value TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 1,
                        next_run_at REAL,
                        claimed_by TEXT,
                        claimed_until REAL,
                        last_run_at REAL,
                        last_status TEXT,
                        last_error TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_schedules_due
                        ON schedules(enabled, next_run_at);
                    CREATE TABLE IF NOT EXISTS outbox (
                        id TEXT PRIMARY KEY,
                        endpoint TEXT NOT NULL,
                        token TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        next_attempt_at REAL NOT NULL,
                        last_error TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_outbox_pending
                        ON outbox(status, next_attempt_at);
                    '''
                )
                db.execute(f'PRAGMA user_version={self.SCHEMA_VERSION}')
            self._initialized = True

    @staticmethod
    def _now() -> float:
        return time.time()

    def get_state(self, key: str, namespace: str = 'default', default=None):
        with self._connect() as db:
            row = db.execute(
                'SELECT value_json FROM state_values WHERE namespace=? AND key=?',
                (str(namespace), str(key)),
            ).fetchone()
        return _decode(row['value_json'], default) if row else default

    def set_state(self, key: str, value: Any, namespace: str = 'default') -> dict[str, Any]:
        now = self._now()
        with self._connect() as db:
            db.execute(
                '''INSERT INTO state_values(namespace,key,value_json,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(namespace,key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at''',
                (str(namespace), str(key), _json(value), now),
            )
        return {'namespace': str(namespace), 'key': str(key), 'value': value, 'updated_at': now}

    def delete_state(self, key: str, namespace: str = 'default') -> bool:
        with self._connect() as db:
            cursor = db.execute('DELETE FROM state_values WHERE namespace=? AND key=?', (str(namespace), str(key)))
            return cursor.rowcount > 0

    def list_states(self, namespace: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            if namespace is None:
                rows = db.execute('SELECT * FROM state_values ORDER BY namespace,key').fetchall()
            else:
                rows = db.execute('SELECT * FROM state_values WHERE namespace=? ORDER BY key', (str(namespace),)).fetchall()
        return [{'namespace': row['namespace'], 'key': row['key'], 'value': _decode(row['value_json']), 'updated_at': row['updated_at']} for row in rows]

    def publish_message(
        self,
        channel: str,
        payload: Any,
        *,
        sender: str = '',
        ttl_seconds: int = 86400,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        message_id = str(message_id or uuid.uuid4())
        expires_at = now + max(1, int(ttl_seconds)) if ttl_seconds else None
        with self._connect() as db:
            db.execute(
                '''INSERT OR IGNORE INTO messages
                   (id,channel,sender,payload_json,status,created_at,expires_at) VALUES(?,?,?,?,?,?,?)''',
                (message_id, str(channel), str(sender), _json(payload), 'ready', now, expires_at),
            )
        return {'id': message_id, 'channel': str(channel), 'sender': str(sender), 'payload': payload, 'created_at': now}

    def claim_messages(
        self,
        channel: str,
        consumer: str,
        *,
        limit: int = 20,
        lease_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        now = self._now()
        until = now + max(1, int(lease_seconds))
        limit = max(1, min(500, int(limit)))
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM messages WHERE expires_at IS NOT NULL AND expires_at<=?', (now,))
            rows = db.execute(
                '''SELECT * FROM messages
                   WHERE channel=? AND (status='ready' OR (status='claimed' AND claimed_until<=?))
                   ORDER BY created_at LIMIT ?''',
                (str(channel), now, limit),
            ).fetchall()
            ids = [row['id'] for row in rows]
            if ids:
                placeholders = ','.join('?' for _ in ids)
                # The interpolated text is generated exclusively from one '?' per id.
                claim_sql = f'''UPDATE messages SET status='claimed', claimed_by=?, claimed_until=?
                    WHERE id IN ({placeholders})'''  # nosec B608
                db.execute(
                    claim_sql,
                    (str(consumer), until, *ids),
                )
            db.execute('COMMIT')
        return [
            {
                'id': row['id'], 'channel': row['channel'], 'sender': row['sender'],
                'payload': _decode(row['payload_json'], {}), 'created_at': row['created_at'],
                'claimed_until': until,
            }
            for row in rows
        ]

    def ack_message(self, message_id: str, consumer: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                "DELETE FROM messages WHERE id=? AND status='claimed' AND claimed_by=?",
                (str(message_id), str(consumer)),
            )
            return cursor.rowcount > 0

    def list_messages(self, channel: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        now = self._now()
        with self._connect() as db:
            db.execute('DELETE FROM messages WHERE expires_at IS NOT NULL AND expires_at<=?', (now,))
            if channel:
                rows = db.execute('SELECT * FROM messages WHERE channel=? ORDER BY created_at DESC LIMIT ?', (str(channel), max(1, min(500, int(limit))))).fetchall()
            else:
                rows = db.execute('SELECT * FROM messages ORDER BY created_at DESC LIMIT ?', (max(1, min(500, int(limit))),)).fetchall()
        return [{
            'id': row['id'], 'channel': row['channel'], 'sender': row['sender'],
            'payload': _decode(row['payload_json'], {}), 'status': row['status'],
            'claimed_by': row['claimed_by'], 'claimed_until': row['claimed_until'],
            'created_at': row['created_at'], 'expires_at': row['expires_at'],
        } for row in rows]

    def acquire_lease(self, resource_key: str, owner: str, ttl_seconds: int = 30) -> dict[str, Any] | None:
        now = self._now()
        expires_at = now + max(1, int(ttl_seconds))
        token = uuid.uuid4().hex
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT * FROM leases WHERE resource_key=?', (str(resource_key),)).fetchone()
            if current and current['expires_at'] > now and current['owner'] != str(owner):
                db.execute('ROLLBACK')
                return None
            if current and current['owner'] == str(owner):
                token = current['token']
            db.execute(
                '''INSERT INTO leases(resource_key,owner,token,expires_at,updated_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(resource_key) DO UPDATE SET owner=excluded.owner, token=excluded.token,
                   expires_at=excluded.expires_at, updated_at=excluded.updated_at''',
                (str(resource_key), str(owner), token, expires_at, now),
            )
            db.execute('COMMIT')
        return {'resource_key': str(resource_key), 'owner': str(owner), 'token': token, 'expires_at': expires_at}

    def renew_lease(self, resource_key: str, owner: str, token: str, ttl_seconds: int = 30) -> bool:
        now = self._now()
        with self._connect() as db:
            cursor = db.execute(
                '''UPDATE leases SET expires_at=?, updated_at=?
                   WHERE resource_key=? AND owner=? AND token=? AND expires_at>?''',
                (now + max(1, int(ttl_seconds)), now, str(resource_key), str(owner), str(token), now),
            )
            return cursor.rowcount > 0

    def release_lease(self, resource_key: str, owner: str, token: str) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                'DELETE FROM leases WHERE resource_key=? AND owner=? AND token=?',
                (str(resource_key), str(owner), str(token)),
            )
            return cursor.rowcount > 0

    def list_leases(self) -> list[dict[str, Any]]:
        now = self._now()
        with self._connect() as db:
            db.execute('DELETE FROM leases WHERE expires_at<=?', (now,))
            rows = db.execute('SELECT * FROM leases ORDER BY resource_key').fetchall()
        return [{
            'resource_key': row['resource_key'], 'owner': row['owner'], 'token': row['token'],
            'expires_at': row['expires_at'], 'updated_at': row['updated_at'],
        } for row in rows]

    def overview(self) -> dict[str, Any]:
        now = self._now()
        with self._connect() as db:
            db.execute('DELETE FROM messages WHERE expires_at IS NOT NULL AND expires_at<=?', (now,))
            db.execute('DELETE FROM leases WHERE expires_at<=?', (now,))
            counts = {
                'states': int(db.execute('SELECT COUNT(*) FROM state_values').fetchone()[0]),
                'messages': int(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]),
                'leases': int(db.execute('SELECT COUNT(*) FROM leases').fetchone()[0]),
                'schedules': int(db.execute('SELECT COUNT(*) FROM schedules').fetchone()[0]),
                'schedules_enabled': int(db.execute('SELECT COUNT(*) FROM schedules WHERE enabled=1').fetchone()[0]),
                'outbox_pending': int(db.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0]),
                'outbox_dead': int(db.execute("SELECT COUNT(*) FROM outbox WHERE status='dead'").fetchone()[0]),
            }
        return {'database': self.path, 'counts': counts, 'timestamp': now}

    @staticmethod
    def next_run(schedule_type: str, schedule_value: str, *, after: float | None = None) -> float | None:
        after = float(after if after is not None else time.time())
        kind = str(schedule_type or '').lower()
        value = str(schedule_value or '').strip()
        if kind == 'interval':
            return after + max(1.0, float(value))
        if kind == 'once':
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
            timestamp = parsed.timestamp()
            return timestamp if timestamp > after else None
        if kind == 'daily':
            hour, minute, *seconds = [int(part) for part in value.split(':')]
            now = datetime.fromtimestamp(after).astimezone()
            target = now.replace(hour=hour, minute=minute, second=seconds[0] if seconds else 0, microsecond=0)
            if target.timestamp() <= after:
                target += timedelta(days=1)
            return target.timestamp()
        raise ValueError(f'不支持的计划类型: {schedule_type}')

    def save_schedule(
        self,
        name: str,
        schedule_type: str,
        schedule_value: str,
        payload: dict[str, Any],
        *,
        enabled: bool = True,
        schedule_id: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        schedule_id = str(schedule_id or uuid.uuid4())
        next_at = self.next_run(schedule_type, schedule_value, after=now) if enabled else None
        with self._connect() as db:
            db.execute(
                '''INSERT INTO schedules(id,name,schedule_type,schedule_value,payload_json,enabled,next_run_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name,schedule_type=excluded.schedule_type,
                   schedule_value=excluded.schedule_value,payload_json=excluded.payload_json,enabled=excluded.enabled,
                   next_run_at=excluded.next_run_at,claimed_by=NULL,claimed_until=NULL,updated_at=excluded.updated_at''',
                (schedule_id, str(name), str(schedule_type), str(schedule_value), _json(payload), int(enabled), next_at, now, now),
            )
        return {'id': schedule_id, 'name': str(name), 'schedule_type': schedule_type, 'schedule_value': schedule_value, 'payload': payload, 'enabled': enabled, 'next_run_at': next_at}

    def list_schedules(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute('SELECT * FROM schedules ORDER BY created_at').fetchall()
        return [self._schedule_row(row) for row in rows]

    @staticmethod
    def _schedule_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            'id': row['id'], 'name': row['name'], 'schedule_type': row['schedule_type'],
            'schedule_value': row['schedule_value'], 'payload': _decode(row['payload_json'], {}),
            'enabled': bool(row['enabled']), 'next_run_at': row['next_run_at'],
            'last_run_at': row['last_run_at'], 'last_status': row['last_status'],
            'last_error': row['last_error'],
        }

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._connect() as db:
            return db.execute('DELETE FROM schedules WHERE id=?', (str(schedule_id),)).rowcount > 0

    def claim_due_schedules(self, owner: str, *, limit: int = 10, lease_seconds: int = 60) -> list[dict[str, Any]]:
        now = self._now()
        until = now + max(5, int(lease_seconds))
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute(
                '''SELECT * FROM schedules WHERE enabled=1 AND next_run_at IS NOT NULL AND next_run_at<=?
                   AND (claimed_until IS NULL OR claimed_until<=?) ORDER BY next_run_at LIMIT ?''',
                (now, now, max(1, min(100, int(limit)))),
            ).fetchall()
            ids = [row['id'] for row in rows]
            if ids:
                placeholders = ','.join('?' for _ in ids)
                db.execute(
                    f'UPDATE schedules SET claimed_by=?, claimed_until=? WHERE id IN ({placeholders})',  # nosec B608
                    (str(owner), until, *ids),
                )
            db.execute('COMMIT')
        return [self._schedule_row(row) for row in rows]

    def complete_schedule(self, schedule_id: str, owner: str, *, success: bool, error: str = '') -> bool:
        now = self._now()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM schedules WHERE id=? AND claimed_by=?', (str(schedule_id), str(owner))).fetchone()
            if not row:
                db.execute('ROLLBACK')
                return False
            next_at = self.next_run(row['schedule_type'], row['schedule_value'], after=now)
            enabled = 0 if row['schedule_type'] == 'once' else row['enabled']
            db.execute(
                '''UPDATE schedules SET enabled=?,next_run_at=?,claimed_by=NULL,claimed_until=NULL,
                   last_run_at=?,last_status=?,last_error=?,updated_at=? WHERE id=?''',
                (enabled, next_at, now, 'success' if success else 'error', str(error or ''), now, str(schedule_id)),
            )
            db.execute('COMMIT')
        return True

    def enqueue_outbox(self, endpoint: str, token: str, operation: str, payload: Any) -> dict[str, Any]:
        now = self._now()
        item_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                '''INSERT INTO outbox(id,endpoint,token,operation,payload_json,status,attempts,next_attempt_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,'pending',0,?,?,?)''',
                (item_id, str(endpoint), str(token), str(operation), _json(payload), now, now, now),
            )
        return {'id': item_id, 'status': 'pending'}

    def due_outbox(self, limit: int = 20) -> list[dict[str, Any]]:
        now = self._now()
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM outbox WHERE status='pending' AND next_attempt_at<=? ORDER BY created_at LIMIT ?",
                (now, max(1, min(100, int(limit)))),
            ).fetchall()
        return [{**dict(row), 'payload': _decode(row['payload_json'], {})} for row in rows]

    def complete_outbox(self, item_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE outbox SET status='sent',updated_at=? WHERE id=?", (self._now(), str(item_id)))

    def fail_outbox(self, item_id: str, attempts: int, error: str) -> None:
        now = self._now()
        delay = min(300.0, 2 ** min(8, max(0, int(attempts))))
        status = 'dead' if attempts >= 12 else 'pending'
        with self._connect() as db:
            db.execute(
                'UPDATE outbox SET status=?,attempts=?,next_attempt_at=?,last_error=?,updated_at=? WHERE id=?',
                (status, int(attempts), now + delay, str(error)[:2000], now, str(item_id)),
            )

    def outbox_status(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute('SELECT status,COUNT(*) AS count FROM outbox GROUP BY status').fetchall()
        return {row['status']: int(row['count']) for row in rows}
