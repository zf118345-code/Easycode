"""Atomic, optimistic ProgramDocument persistence for project format 6."""

from __future__ import annotations

import contextlib
import json
import os
import re
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .program_serialization import canonical_json_bytes, content_revision
from .program_types import ProgramDocument
from .program_validation import validate_program_document
from .revision_conflict import ProgramConflictError


class ProgramRepositoryError(RuntimeError):
    pass


class ProgramDocumentNotFoundError(ProgramRepositoryError):
    pass


class ProgramDocumentCorruptError(ProgramRepositoryError):
    pass


class ProgramDocumentValidationError(ProgramRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class ProgramSnapshot:
    document: ProgramDocument
    revision: str
    path: Path


@dataclass(frozen=True, slots=True)
class ProgramHistorySnapshot:
    history_id: str
    function_id: str
    revision: str
    created_at: str
    reason: str
    document: ProgramDocument
    path: Path


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}
_SNAPSHOT_CACHE_LIMIT = 4096
_SNAPSHOT_CACHE_GUARD = threading.Lock()
_SNAPSHOT_CACHE: OrderedDict[str, tuple[tuple[int, int, int, int], ProgramSnapshot]] = OrderedDict()
_STABLE_PATH_ID = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,159}$')


def _lock_for(path: Path) -> threading.RLock:
    key = os.path.normcase(os.path.abspath(path))
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _path_cache_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _file_signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)


def _cached_snapshot(path: Path, signature: tuple[int, int, int, int]) -> ProgramSnapshot | None:
    key = _path_cache_key(path)
    with _SNAPSHOT_CACHE_GUARD:
        cached = _SNAPSHOT_CACHE.get(key)
        if cached is None or cached[0] != signature:
            return None
        _SNAPSHOT_CACHE.move_to_end(key)
        return cached[1]


def _remember_snapshot(path: Path, snapshot: ProgramSnapshot) -> None:
    key = _path_cache_key(path)
    signature = _file_signature(path)
    with _SNAPSHOT_CACHE_GUARD:
        _SNAPSHOT_CACHE[key] = (signature, snapshot)
        _SNAPSHOT_CACHE.move_to_end(key)
        while len(_SNAPSHOT_CACHE) > _SNAPSHOT_CACHE_LIMIT:
            _SNAPSHOT_CACHE.popitem(last=False)


def _forget_snapshot(path: Path) -> None:
    with _SNAPSHOT_CACHE_GUARD:
        _SNAPSHOT_CACHE.pop(_path_cache_key(path), None)


def _write_temp(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    with temporary.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return temporary


class ProgramDocumentRepository:
    """Persist ``program/functions/<function_id>.json`` without silent overwrite."""

    HISTORY_LIMIT = 100

    def __init__(self, project_path: str | os.PathLike[str]) -> None:
        self.project_path = Path(project_path).resolve()
        self.functions_path = self.project_path / 'program' / 'functions'
        self.history_path = self.project_path / '.easycode' / 'history' / 'program' / 'functions'
        self.recovery_path = self.project_path / '.easycode' / 'recovery' / 'program' / 'functions'

    @staticmethod
    def clear_snapshot_cache() -> None:
        """Clear the process-local parse cache for cold-start measurement/tests."""

        with _SNAPSHOT_CACHE_GUARD:
            _SNAPSHOT_CACHE.clear()

    def path_for(self, function_id: str) -> Path:
        # A validated stable ID cannot contain a separator, drive marker, or a
        # leading dot segment.  Avoid Path.resolve() here: this method is on the
        # 1k-function catalog hot path and the already-resolved project root is
        # immutable for this repository instance.
        if not _STABLE_PATH_ID.fullmatch(function_id or ''):
            raise ProgramRepositoryError(f'invalid function ID for project path: {function_id!r}')
        return self.functions_path / f'{function_id}.json'

    def _function_storage_path(self, root: Path, function_id: str) -> Path:
        # Reuse the same stable-ID path guard as the editable source tree.
        self.path_for(function_id)
        return root / function_id

    @staticmethod
    def _history_payload(
        document: ProgramDocument,
        *,
        revision: str,
        created_at: str,
        reason: str,
        source_revision: str,
    ) -> bytes:
        return (json.dumps({
            'schema_version': 1,
            'function_id': document.function.function_id,
            'revision': revision,
            'source_revision': source_revision,
            'created_at': created_at,
            'reason': reason,
            'document': document.model_dump(mode='json'),
        }, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

    def _archive_bytes(self, function_id: str, content: bytes, *, reason: str) -> str:
        document = self._decode(self.path_for(function_id), content)
        if document.function.function_id != function_id:
            raise ProgramDocumentCorruptError(
                f'file name {function_id!r} does not match {document.function.function_id!r}'
            )
        source_revision = content_revision(content)
        revision = content_revision(canonical_json_bytes(document))
        now = datetime.now(timezone.utc)
        created_at = now.isoformat(timespec='milliseconds')
        revision_token = revision.rsplit(':', 1)[-1][:12]
        history_id = f'{now.strftime("%Y%m%dT%H%M%S%fZ")}-{revision_token}-{uuid.uuid4().hex[:8]}'
        directory = self._function_storage_path(self.history_path, function_id)
        target = directory / f'{history_id}.json'
        temporary = _write_temp(target, self._history_payload(
            document,
            revision=revision,
            created_at=created_at,
            reason=reason,
            source_revision=source_revision,
        ))
        try:
            os.replace(temporary, target)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()
        history_files = sorted(directory.glob('*.json'), key=lambda item: item.name, reverse=True)
        for expired in history_files[self.HISTORY_LIMIT:]:
            with contextlib.suppress(OSError):
                expired.unlink()
        return history_id

    def _preserve_corrupt_bytes(self, function_id: str, content: bytes) -> Path:
        directory = self._function_storage_path(self.recovery_path, function_id)
        now = datetime.now(timezone.utc)
        revision_token = content_revision(content).rsplit(':', 1)[-1][:12]
        target = directory / f'{now.strftime("%Y%m%dT%H%M%S%fZ")}-{revision_token}.corrupt.json'
        temporary = _write_temp(target, content)
        try:
            os.replace(temporary, target)
        finally:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()
        return target

    def list_history(self, function_id: str) -> list[ProgramHistorySnapshot]:
        directory = self._function_storage_path(self.history_path, function_id)
        if not directory.is_dir():
            return []
        result: list[ProgramHistorySnapshot] = []
        for path in sorted(directory.glob('*.json'), key=lambda item: item.name, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                document = ProgramDocument.model_validate(payload['document'])
                revision = str(payload['revision'])
                if document.function.function_id != function_id:
                    continue
                if content_revision(canonical_json_bytes(document)) != revision:
                    continue
                result.append(ProgramHistorySnapshot(
                    history_id=path.stem,
                    function_id=function_id,
                    revision=revision,
                    created_at=str(payload['created_at']),
                    reason=str(payload.get('reason') or 'edit'),
                    document=document,
                    path=path,
                ))
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
                # A damaged history item must not hide other usable recovery points.
                continue
        return result

    def restore_history(
        self,
        function_id: str,
        history_id: str,
        *,
        expected_revision: str,
    ) -> ProgramSnapshot:
        if not history_id or any(char in history_id for char in ('/', '\\', ':')):
            raise ProgramRepositoryError('invalid history ID')
        candidates = {item.history_id: item for item in self.list_history(function_id)}
        candidate = candidates.get(history_id)
        if candidate is None:
            raise ProgramDocumentNotFoundError(history_id)
        path = self.path_for(function_id)
        with _lock_for(path):
            try:
                current = path.read_bytes()
            except FileNotFoundError:
                current = b''
            actual_revision = content_revision(current) if current else None
            if actual_revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, actual_revision)
            if current:
                try:
                    self._archive_bytes(function_id, current, reason='before_restore')
                except ProgramDocumentCorruptError:
                    self._preserve_corrupt_bytes(function_id, current)
            content = canonical_json_bytes(candidate.document)
            temporary = _write_temp(path, content)
            try:
                os.replace(temporary, path)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
            snapshot = ProgramSnapshot(candidate.document, content_revision(content), path)
            _remember_snapshot(path, snapshot)
            return snapshot

    @staticmethod
    def _decode(path: Path, content: bytes) -> ProgramDocument:
        try:
            payload = json.loads(content.decode('utf-8'))
            return ProgramDocument.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ProgramDocumentCorruptError(f'invalid ProgramDocument {path}: {exc}') from exc

    @staticmethod
    def _validate_for_save(document: ProgramDocument) -> None:
        diagnostics = validate_program_document(document)
        if diagnostics:
            raise ProgramDocumentValidationError('; '.join(item.message for item in diagnostics))

    def load(self, function_id: str) -> ProgramSnapshot:
        path = self.path_for(function_id)
        with _lock_for(path):
            try:
                signature = _file_signature(path)
            except FileNotFoundError as exc:
                raise ProgramDocumentNotFoundError(function_id) from exc
            cached = _cached_snapshot(path, signature)
            if cached is not None:
                return cached
            content = path.read_bytes()
            document = self._decode(path, content)
            if document.function.function_id != function_id:
                raise ProgramDocumentCorruptError(
                    f'file name {function_id!r} does not match {document.function.function_id!r}'
                )
            snapshot = ProgramSnapshot(document=document, revision=content_revision(content), path=path)
            _remember_snapshot(path, snapshot)
            return snapshot

    def create(self, document: ProgramDocument) -> ProgramSnapshot:
        self._validate_for_save(document)
        path = self.path_for(document.function.function_id)
        content = canonical_json_bytes(document)
        with _lock_for(path):
            temporary = _write_temp(path, content)
            try:
                try:
                    os.link(temporary, path)
                except FileExistsError as exc:
                    actual = content_revision(path.read_bytes()) if path.is_file() else None
                    raise ProgramConflictError(document.function.function_id, None, actual) from exc
            finally:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
            snapshot = ProgramSnapshot(document=document, revision=content_revision(content), path=path)
            _remember_snapshot(path, snapshot)
            return snapshot

    def save(self, document: ProgramDocument, *, expected_revision: str) -> ProgramSnapshot:
        self._validate_for_save(document)
        path = self.path_for(document.function.function_id)
        content = canonical_json_bytes(document)
        with _lock_for(path):
            try:
                current = path.read_bytes()
            except FileNotFoundError as exc:
                raise ProgramConflictError(document.function.function_id, expected_revision, None) from exc
            actual_revision = content_revision(current)
            if actual_revision != expected_revision:
                raise ProgramConflictError(
                    document.function.function_id,
                    expected_revision,
                    actual_revision,
                )
            self._archive_bytes(document.function.function_id, current, reason='before_edit')
            temporary = _write_temp(path, content)
            try:
                os.replace(temporary, path)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
            snapshot = ProgramSnapshot(document=document, revision=content_revision(content), path=path)
            _remember_snapshot(path, snapshot)
            return snapshot

    def delete(self, function_id: str, *, expected_revision: str) -> None:
        """Atomically remove one document after optimistic revision validation."""

        path = self.path_for(function_id)
        with _lock_for(path):
            try:
                current = path.read_bytes()
            except FileNotFoundError as exc:
                raise ProgramDocumentNotFoundError(function_id) from exc
            actual_revision = content_revision(current)
            if actual_revision != expected_revision:
                raise ProgramConflictError(function_id, expected_revision, actual_revision)
            self._archive_bytes(function_id, current, reason='before_delete')
            path.unlink()
            _forget_snapshot(path)


__all__ = [
    'ProgramConflictError',
    'ProgramDocumentCorruptError',
    'ProgramDocumentNotFoundError',
    'ProgramDocumentRepository',
    'ProgramHistorySnapshot',
    'ProgramDocumentValidationError',
    'ProgramRepositoryError',
    'ProgramSnapshot',
]
