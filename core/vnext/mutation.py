"""Journaled project mutations with crash-safe rollback and recovery."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .workspace_context import VNextWorkspaceError


FailureHook = Callable[[str, str], None]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write_bytes(path: str, content: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.easycode-mutation-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(temporary)
        raise


def _atomic_write_json(path: str, value: dict[str, Any]) -> None:
    _atomic_write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


class ProjectMutationTransaction:
    """Apply a set of project-relative replacements as one recoverable change.

    ``None`` means delete the path.  Original bytes and hashes are captured before
    the first project file changes.  An interrupted ``committing`` journal is
    rolled back on the next project open.
    """

    ROOT = '.easycode/transactions'

    def __init__(self, project_path: str, *, failure_hook: FailureHook | None = None) -> None:
        self.project_path = os.path.realpath(project_path)
        self.transaction_id = f'txn_{uuid.uuid4().hex}'
        self.directory = os.path.join(self.project_path, *self.ROOT.split('/'), self.transaction_id)
        self.journal_path = os.path.join(self.directory, 'journal.json')
        self.failure_hook = failure_hook
        self.journal: dict[str, Any] = {
            'schema_version': 1,
            'transaction_id': self.transaction_id,
            'state': 'staging',
            'operations': [],
        }

    def _safe_path(self, relative: str) -> tuple[str, str]:
        normalized = str(relative or '').replace('\\', '/').strip('/')
        if not normalized or '..' in normalized.split('/') or normalized.startswith(f'{self.ROOT}/'):
            raise VNextWorkspaceError(f'事务路径无效：{relative}')
        absolute = os.path.realpath(os.path.join(self.project_path, *normalized.split('/')))
        try:
            common = os.path.commonpath([self.project_path, absolute])
        except ValueError as exc:
            raise VNextWorkspaceError(f'事务路径超出项目：{relative}') from exc
        if common != self.project_path:
            raise VNextWorkspaceError(f'事务路径超出项目：{relative}')
        return normalized, absolute

    def _hook(self, stage: str, relative: str = '') -> None:
        if self.failure_hook is not None:
            self.failure_hook(stage, relative)

    def stage(self, replacements: Mapping[str, bytes | str | None]) -> None:
        if os.path.exists(self.directory):
            raise VNextWorkspaceError('项目事务目录已存在')
        os.makedirs(os.path.join(self.directory, 'staged'), exist_ok=False)
        os.makedirs(os.path.join(self.directory, 'backup'), exist_ok=False)
        operations: list[dict[str, Any]] = []
        seen: set[str] = set()
        for order, (raw_relative, raw_content) in enumerate(replacements.items()):
            relative, absolute = self._safe_path(raw_relative)
            key = os.path.normcase(relative)
            if key in seen:
                raise VNextWorkspaceError(f'事务包含重复路径：{relative}')
            seen.add(key)
            original_exists = os.path.isfile(absolute)
            if os.path.exists(absolute) and not original_exists:
                raise VNextWorkspaceError(f'事务目标不是文件：{relative}')
            original = Path(absolute).read_bytes() if original_exists else b''
            token = f'{order:04d}-{hashlib.sha256(relative.encode("utf-8")).hexdigest()}'
            backup_relative = f'backup/{token}.bin' if original_exists else ''
            staged_relative = f'staged/{token}.bin' if raw_content is not None else ''
            if backup_relative:
                _atomic_write_bytes(os.path.join(self.directory, *backup_relative.split('/')), original)
            if staged_relative:
                content = raw_content.encode('utf-8') if isinstance(raw_content, str) else bytes(raw_content)
                _atomic_write_bytes(os.path.join(self.directory, *staged_relative.split('/')), content)
                staged_hash = _sha256(content)
            else:
                staged_hash = ''
            operations.append({
                'relative': relative,
                'action': 'write' if raw_content is not None else 'delete',
                'original_exists': original_exists,
                'original_sha256': _sha256(original) if original_exists else '',
                'backup': backup_relative,
                'staged': staged_relative,
                'staged_sha256': staged_hash,
            })
        self.journal['operations'] = operations
        self.journal['state'] = 'prepared'
        _atomic_write_json(self.journal_path, self.journal)

    def _verify_originals(self) -> None:
        for operation in self.journal['operations']:
            relative, absolute = self._safe_path(operation['relative'])
            exists = os.path.isfile(absolute)
            if exists != bool(operation['original_exists']):
                raise VNextWorkspaceError(f'事务提交前文件已变化：{relative}')
            if exists and _sha256(Path(absolute).read_bytes()) != operation['original_sha256']:
                raise VNextWorkspaceError(f'事务提交前文件已变化：{relative}')

    def _restore(self) -> None:
        for operation in reversed(self.journal.get('operations') or []):
            _relative, absolute = self._safe_path(operation['relative'])
            if operation.get('original_exists'):
                backup = os.path.join(self.directory, *str(operation['backup']).split('/'))
                if not os.path.isfile(backup):
                    raise VNextWorkspaceError(f'事务备份缺失：{operation["relative"]}')
                _atomic_write_bytes(absolute, Path(backup).read_bytes())
            elif os.path.isfile(absolute):
                os.remove(absolute)

    def commit(self) -> None:
        if self.journal.get('state') != 'prepared':
            raise VNextWorkspaceError('项目事务尚未准备完成')
        self._verify_originals()
        self.journal['state'] = 'committing'
        _atomic_write_json(self.journal_path, self.journal)
        try:
            for operation in self.journal['operations']:
                relative, absolute = self._safe_path(operation['relative'])
                self._hook('before_apply', relative)
                if operation['action'] == 'write':
                    staged = os.path.join(self.directory, *str(operation['staged']).split('/'))
                    content = Path(staged).read_bytes()
                    if _sha256(content) != operation['staged_sha256']:
                        raise VNextWorkspaceError(f'事务暂存内容损坏：{relative}')
                    _atomic_write_bytes(absolute, content)
                elif os.path.isfile(absolute):
                    os.remove(absolute)
                self._hook('after_apply', relative)
            self._hook('before_commit_marker', '')
            self.journal['state'] = 'committed'
            _atomic_write_json(self.journal_path, self.journal)
        except Exception:
            self._restore()
            self.journal['state'] = 'rolled_back'
            _atomic_write_json(self.journal_path, self.journal)
            raise
        finally:
            if self.journal.get('state') in {'committed', 'rolled_back'}:
                shutil.rmtree(self.directory, ignore_errors=True)

    @classmethod
    def apply(
        cls,
        project_path: str,
        replacements: Mapping[str, bytes | str | None],
        *,
        failure_hook: FailureHook | None = None,
    ) -> str:
        transaction = cls(project_path, failure_hook=failure_hook)
        try:
            transaction.stage(replacements)
            transaction.commit()
            return transaction.transaction_id
        except Exception:
            if os.path.isdir(transaction.directory) and transaction.journal.get('state') in {'staging', 'prepared'}:
                shutil.rmtree(transaction.directory, ignore_errors=True)
            raise

    @classmethod
    def recover(cls, project_path: str) -> list[dict[str, str]]:
        root = os.path.join(os.path.realpath(project_path), *cls.ROOT.split('/'))
        if not os.path.isdir(root):
            return []
        recovered: list[dict[str, str]] = []
        for entry in sorted(os.listdir(root)):
            directory = os.path.join(root, entry)
            journal_path = os.path.join(directory, 'journal.json')
            if not os.path.isdir(directory):
                continue
            try:
                journal = json.loads(Path(journal_path).read_text(encoding='utf-8'))
                state = str(journal.get('state') or '')
                transaction = cls(project_path)
                transaction.transaction_id = entry
                transaction.directory = directory
                transaction.journal_path = journal_path
                transaction.journal = journal
                if state == 'committing':
                    transaction._restore()
                    recovered.append({'transaction_id': entry, 'action': 'rolled_back'})
                else:
                    recovered.append({'transaction_id': entry, 'action': 'discarded'})
                shutil.rmtree(directory, ignore_errors=False)
            except Exception as exc:
                raise VNextWorkspaceError(f'项目事务恢复失败 {entry}：{exc}') from exc
        with contextlib.suppress(OSError):
            os.rmdir(root)
        return recovered
