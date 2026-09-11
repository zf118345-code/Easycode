"""Authorized format-6 file and directory runtime for Windows hosts."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, suppress
from typing import Any

from .runtime import RuntimeFailure

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}
_ENCODINGS = {'utf-8': 'utf-8', 'utf-8-sig': 'utf-8-sig', 'gb18030': 'gb18030'}
_MAX_LIST_ENTRIES = 1000


def windows_file_reference(
    path: str,
    authorization_root: str,
    *,
    access: tuple[str, ...] = ('read',),
    authorization_root_id: str = '',
    source: str = 'external',
) -> dict[str, Any]:
    return _windows_reference(
        'file_ref', path, authorization_root, access,
        authorization_root_id=authorization_root_id, source=source,
    )


def windows_directory_reference(
    path: str,
    authorization_root: str,
    *,
    access: tuple[str, ...] = ('read', 'list'),
    authorization_root_id: str = '',
    source: str = 'external',
) -> dict[str, Any]:
    return _windows_reference(
        'directory_ref', path, authorization_root, access,
        authorization_root_id=authorization_root_id, source=source,
    )


def _windows_reference(
    kind: str,
    path: str,
    authorization_root: str,
    access: tuple[str, ...],
    *,
    authorization_root_id: str,
    source: str,
) -> dict[str, Any]:
    root = os.path.realpath(os.path.abspath(authorization_root))
    target = os.path.realpath(os.path.abspath(path))
    _assert_contained(target, root)
    return {
        'kind': kind,
        'platform': 'windows',
        'source': source,
        'display_name': os.path.basename(target) or target,
        'path': target,
        'authorization_root': root,
        'authorization_root_id': authorization_root_id or f'windows:{os.path.normcase(root)}',
        'access': sorted(set(access)),
    }


def _assert_contained(path: str, root: str) -> None:
    try:
        contained = os.path.commonpath((os.path.normcase(path), os.path.normcase(root))) == os.path.normcase(root)
    except ValueError as exc:
        raise RuntimeFailure('文件引用与授权根不在同一卷', error_id='file.outside_authorization') from exc
    if not contained:
        raise RuntimeFailure('文件引用超出授权根', error_id='file.outside_authorization')


def _validate_reference(reference: Any, kind: str, required_access: str) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(reference, dict) or reference.get('kind') != kind:
        raise RuntimeFailure(f'需要强类型 {kind}', error_id='file.invalid_reference')
    platform = str(reference.get('platform') or '')
    if platform == 'android':
        raise RuntimeFailure('Android URI 文件引用需要 APK 宿主，Windows 运行时不执行', error_id='file.android_host_unsupported')
    if platform != 'windows':
        raise RuntimeFailure(f'不支持的文件引用平台：{platform}', error_id='file.platform_unsupported')
    access = {str(item) for item in reference.get('access') or []}
    if required_access not in access:
        raise RuntimeFailure(f'文件引用未授予 {required_access} 权限', error_id='file.access_denied')
    raw_root_value = str(reference.get('authorization_root') or '')
    raw_path_value = str(reference.get('path') or '')
    if not raw_root_value or not raw_path_value or not reference.get('authorization_root_id'):
        raise RuntimeFailure('文件引用缺少 Windows 授权载荷', error_id='file.invalid_reference')
    root = os.path.realpath(os.path.abspath(raw_root_value))
    raw_path = os.path.abspath(raw_path_value)
    path = os.path.realpath(raw_path)
    _assert_contained(path, root)
    return path, root, reference


def _encoding(value: Any) -> str:
    key = str(value or 'utf-8').lower()
    if key not in _ENCODINGS:
        raise RuntimeFailure(f'不支持的文本编码：{key}', error_id='file.encoding_unsupported')
    return _ENCODINGS[key]


def _path_lock(path: str) -> threading.RLock:
    key = os.path.normcase(os.path.realpath(path))
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _locked_paths(*paths: str) -> Iterator[None]:
    locks = [_path_lock(path) for path in sorted(set(paths), key=os.path.normcase)]
    with ExitStack() as stack:
        for lock in locks:
            stack.enter_context(lock)
        for path in sorted(set(paths), key=os.path.normcase):
            stack.enter_context(_os_path_lock(path))
        yield


@contextmanager
def _os_path_lock(path: str) -> Iterator[None]:
    """Serialize EasyCode writers across processes on the same device."""

    key = hashlib.sha256(os.path.normcase(os.path.realpath(path)).encode('utf-8')).hexdigest()
    directory = os.path.join(tempfile.gettempdir(), 'EasyCode', 'file-locks')
    os.makedirs(directory, exist_ok=True)
    lock_path = os.path.join(directory, f'{key}.lock')
    stream = open(lock_path, 'a+b')  # noqa: SIM115
    try:
        stream.seek(0)
        if not stream.read(1):
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        with suppress(OSError):
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _atomic_bytes(path: str, content: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.easycode-file-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise RuntimeFailure(f'文件原子提交失败：{exc}', error_id='file.atomic_commit_failed') from exc
    finally:
        if os.path.exists(temporary):
            with suppress(OSError):
                os.remove(temporary)


def _atomic_copy(source: str, destination: str, cancelled: Callable[[], bool]) -> None:
    directory = os.path.dirname(destination)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.easycode-copy-', suffix='.tmp', dir=directory)
    try:
        with open(source, 'rb') as input_stream, os.fdopen(descriptor, 'wb') as output_stream:
            while True:
                _cancel(cancelled)
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(temporary, destination)
    except OSError as exc:
        raise RuntimeFailure(f'文件复制失败：{exc}', error_id='file.copy_failed') from exc
    finally:
        if os.path.exists(temporary):
            with suppress(OSError):
                os.remove(temporary)


def _file_parameter(arguments: dict[str, Any], function_id: str, name: str) -> Any:
    return arguments.get(f'{function_id}.parameter.{name}')


def _cancel(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise RuntimeFailure('文件操作已取消', error_id='runtime.cancelled')


class FileRuntimeV6:
    """Execute only frozen file/directory opcodes with exact stable slots."""

    @staticmethod
    def supports(opcode: str) -> bool:
        return opcode in {
            'file.exists', 'file.read_text', 'file.write_text', 'file.append_text',
            'file.replace_text', 'file.read_json', 'file.write_json', 'file.delete',
            'file.copy', 'file.move', 'directory.exists', 'directory.create',
            'directory.list', 'directory.copy', 'directory.move', 'directory.delete',
            'directory.delete_tree',
        }

    def execute(
        self,
        opcode: str,
        function_id: str,
        arguments: dict[str, Any],
        cancelled: Callable[[], bool],
        *,
        operation_context: dict[str, Any] | None = None,
    ) -> Any:
        if not self.supports(opcode):
            raise RuntimeFailure(f'文件运行时不支持：{opcode}', error_id='file.operation_unsupported')
        _cancel(cancelled)
        if opcode == 'directory.delete_tree':
            return self._execute_directory_delete_tree(
                function_id,
                arguments,
                cancelled,
                operation_context or {},
            )
        method = getattr(self, f'_execute_{opcode.replace(".", "_")}')
        return method(function_id, arguments, cancelled)

    def write_authorized_bytes(
        self,
        reference: Any,
        content: bytes,
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        """Atomically write an already-produced binary artifact to a writable file reference."""
        path, _, canonical = _validate_reference(reference, 'file_ref', 'write')
        if not isinstance(content, bytes):
            raise RuntimeFailure('二进制文件内容无效', error_id='runtime.argument_type')
        with _locked_paths(path):
            _cancel(cancelled)
            _atomic_bytes(path, content)
        return canonical

    def _execute_file_exists(self, fid: str, args: dict[str, Any], cancelled) -> bool:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'read')
        return os.path.isfile(path)

    def _execute_file_read_text(self, fid: str, args: dict[str, Any], cancelled) -> str:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'read')
        try:
            with open(path, encoding=_encoding(_file_parameter(args, fid, 'encoding'))) as stream:
                return stream.read()
        except FileNotFoundError as exc:
            raise RuntimeFailure('文件不存在', error_id='file.not_found') from exc
        except UnicodeError as exc:
            raise RuntimeFailure('文件解码失败', error_id='file.decode_failed') from exc
        except OSError as exc:
            raise RuntimeFailure(f'文件读取失败：{exc}', error_id='file.read_failed') from exc

    def _execute_file_write_text(self, fid: str, args: dict[str, Any], cancelled) -> None:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'write')
        content = str(_file_parameter(args, fid, 'content') or '')
        with _locked_paths(path):
            _cancel(cancelled)
            _atomic_bytes(path, content.encode(_encoding(_file_parameter(args, fid, 'encoding'))))

    def _execute_file_append_text(self, fid: str, args: dict[str, Any], cancelled) -> None:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'write')
        content = str(_file_parameter(args, fid, 'content') or '')
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with _locked_paths(path), open(path, 'ab') as stream:
                _cancel(cancelled)
                stream.write(content.encode(_encoding(_file_parameter(args, fid, 'encoding'))))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise RuntimeFailure(f'文件追加失败：{exc}', error_id='file.append_failed') from exc

    def _execute_file_replace_text(self, fid: str, args: dict[str, Any], cancelled) -> int:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'write')
        encoding = _encoding(_file_parameter(args, fid, 'encoding'))
        search = str(_file_parameter(args, fid, 'search') or '')
        replacement = str(_file_parameter(args, fid, 'replacement') or '')
        scope = str(_file_parameter(args, fid, 'scope') or 'all')
        if not search:
            raise RuntimeFailure('替换文本的查找内容不能为空', error_id='file.empty_search')
        if scope not in {'first', 'all'}:
            raise RuntimeFailure(f'不支持的替换范围：{scope}', error_id='file.replace_scope_unsupported')
        with _locked_paths(path):
            try:
                with open(path, encoding=encoding) as stream:
                    current = stream.read()
            except FileNotFoundError as exc:
                raise RuntimeFailure('文件不存在', error_id='file.not_found') from exc
            count = current.count(search) if scope == 'all' else int(search in current)
            if count:
                _cancel(cancelled)
                _atomic_bytes(path, current.replace(search, replacement, -1 if scope == 'all' else 1).encode(encoding))
            return count

    def _execute_file_read_json(self, fid: str, args: dict[str, Any], cancelled) -> Any:
        text = self._execute_file_read_text(fid, {
            **args, f'{fid}.parameter.encoding': 'utf-8',
        }, cancelled)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeFailure(f'JSON 语法错误：{exc}', error_id='file.json_invalid') from exc

    def _execute_file_write_json(self, fid: str, args: dict[str, Any], cancelled) -> None:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'write')
        try:
            content = (json.dumps(_file_parameter(args, fid, 'data'), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        except (TypeError, ValueError) as exc:
            raise RuntimeFailure(f'JSON 数据无法序列化：{exc}', error_id='file.json_not_serializable') from exc
        with _locked_paths(path):
            _cancel(cancelled)
            _atomic_bytes(path, content)

    def _execute_file_delete(self, fid: str, args: dict[str, Any], cancelled) -> bool:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'file'), 'file_ref', 'delete')
        with _locked_paths(path):
            _cancel(cancelled)
            if not os.path.exists(path):
                return False
            if not os.path.isfile(path):
                raise RuntimeFailure('文件.删除不能删除目录', error_id='file.expected_file')
            os.remove(path)
            return True

    def _execute_file_copy(self, fid: str, args: dict[str, Any], cancelled) -> dict[str, Any]:
        source, _, _ = _validate_reference(_file_parameter(args, fid, 'source'), 'file_ref', 'read')
        destination, _, reference = _validate_reference(_file_parameter(args, fid, 'destination'), 'file_ref', 'write')
        conflict = str(_file_parameter(args, fid, 'conflict') or 'error')
        if conflict not in {'error', 'overwrite'}:
            raise RuntimeFailure(f'不支持的文件冲突策略：{conflict}', error_id='file.conflict_policy_unsupported')
        with _locked_paths(source, destination):
            if os.path.exists(destination) and conflict != 'overwrite':
                raise RuntimeFailure('目标文件已存在', error_id='file.conflict')
            _cancel(cancelled)
            try:
                _atomic_copy(source, destination, cancelled)
            except FileNotFoundError as exc:
                raise RuntimeFailure('来源文件不存在', error_id='file.not_found') from exc
        return reference

    def _execute_file_move(self, fid: str, args: dict[str, Any], cancelled) -> dict[str, Any]:
        source, _, _ = _validate_reference(_file_parameter(args, fid, 'source'), 'file_ref', 'read_delete')
        destination, _, reference = _validate_reference(_file_parameter(args, fid, 'destination'), 'file_ref', 'write')
        conflict = str(_file_parameter(args, fid, 'conflict') or 'error')
        if conflict not in {'error', 'overwrite'}:
            raise RuntimeFailure(f'不支持的文件冲突策略：{conflict}', error_id='file.conflict_policy_unsupported')
        with _locked_paths(source, destination):
            if os.path.exists(destination) and conflict != 'overwrite':
                raise RuntimeFailure('目标文件已存在', error_id='file.conflict')
            _cancel(cancelled)
            try:
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                os.replace(source, destination)
            except FileNotFoundError as exc:
                raise RuntimeFailure('来源文件不存在', error_id='file.not_found') from exc
            except OSError as exc:
                raise RuntimeFailure(f'文件移动失败：{exc}', error_id='file.move_failed') from exc
        return reference

    def _execute_directory_exists(self, fid: str, args: dict[str, Any], cancelled) -> bool:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'directory'), 'directory_ref', 'read')
        return os.path.isdir(path)

    def _execute_directory_create(self, fid: str, args: dict[str, Any], cancelled) -> dict[str, Any]:
        parent, root, reference = _validate_reference(_file_parameter(args, fid, 'parent'), 'directory_ref', 'create')
        relative = str(_file_parameter(args, fid, 'relative_path') or '')
        if not relative or os.path.isabs(relative) or '..' in relative.replace('\\', '/').split('/'):
            raise RuntimeFailure('目录相对位置无效', error_id='file.invalid_relative_path')
        target = os.path.realpath(os.path.join(parent, relative))
        _assert_contained(target, root)
        existing = str(_file_parameter(args, fid, 'existing') or 'return_existing')
        if os.path.exists(target) and existing == 'error':
            raise RuntimeFailure('目录已存在', error_id='file.conflict')
        _cancel(cancelled)
        os.makedirs(target, exist_ok=existing == 'return_existing')
        return windows_directory_reference(
            target, root,
            access=tuple(
                item for item in (reference.get('access') or ())
                if item in {'read', 'list', 'create', 'move', 'delete_empty'}
            ),
            authorization_root_id=str(reference.get('authorization_root_id') or ''),
            source=str(reference.get('source') or 'external'),
        )

    def _execute_directory_list(self, fid: str, args: dict[str, Any], cancelled) -> list[dict[str, Any]]:
        path, root, reference = _validate_reference(_file_parameter(args, fid, 'directory'), 'directory_ref', 'list')
        parent_access = {str(item) for item in reference.get('access') or ()}
        root_id = str(reference.get('authorization_root_id') or '')
        source = str(reference.get('source') or 'external')
        recursive = bool(_file_parameter(args, fid, 'recursive'))
        filter_value = _file_parameter(args, fid, 'filter') or {}
        if not isinstance(filter_value, dict):
            raise RuntimeFailure('目录筛选必须是结构化值', error_id='directory.filter_invalid')
        pattern = filter_value.get('filesystem_filter.field.pattern', filter_value.get('pattern')) or '*'
        limit_value = filter_value.get('filesystem_filter.field.limit', filter_value.get('limit'))
        if not isinstance(pattern, str) or not pattern:
            raise RuntimeFailure('目录名称模式不能为空', error_id='directory.filter_invalid')
        if limit_value is None:
            limit = _MAX_LIST_ENTRIES
        elif isinstance(limit_value, bool) or not isinstance(limit_value, int) or not 1 <= limit_value <= _MAX_LIST_ENTRIES:
            raise RuntimeFailure(
                f'目录最大条数必须是 1 至 {_MAX_LIST_ENTRIES} 的整数',
                error_id='directory.filter_invalid',
            )
        else:
            limit = limit_value
        result: list[dict[str, Any]] = []
        iterator = os.walk(path, followlinks=False) if recursive else [(path, [], os.listdir(path))]
        for directory, directories, files in iterator:
            _cancel(cancelled)
            names = sorted(set(directories + files))
            for name in names:
                if not fnmatch.fnmatch(name, pattern):
                    continue
                child = os.path.join(directory, name)
                if os.path.islink(child):
                    result.append({
                        'filesystem_entry.field.name': name,
                        'filesystem_entry.field.entry_type': 'link',
                        'filesystem_entry.field.size': None,
                        'filesystem_entry.field.file': None,
                        'filesystem_entry.field.directory': None,
                    })
                elif os.path.isdir(child):
                    result.append({
                        'filesystem_entry.field.name': name,
                        'filesystem_entry.field.entry_type': 'directory',
                        'filesystem_entry.field.size': None,
                        'filesystem_entry.field.file': None,
                        'filesystem_entry.field.directory': windows_directory_reference(
                            child,
                            root,
                            access=tuple(sorted(parent_access & {'read', 'list'})),
                            authorization_root_id=root_id,
                            source=source,
                        ),
                    })
                else:
                    result.append({
                        'filesystem_entry.field.name': name,
                        'filesystem_entry.field.entry_type': 'file',
                        'filesystem_entry.field.size': os.path.getsize(child),
                        'filesystem_entry.field.file': windows_file_reference(
                            child,
                            root,
                            access=tuple(sorted(parent_access & {'read'})),
                            authorization_root_id=root_id,
                            source=source,
                        ),
                        'filesystem_entry.field.directory': None,
                    })
                if len(result) >= limit:
                    return result
            if not recursive:
                break
        return result

    def _tree_destination(self, fid: str, args: dict[str, Any], operation: str) -> tuple[str, str, str, dict[str, Any]]:
        source, _, _ = _validate_reference(_file_parameter(args, fid, 'source'), 'directory_ref', 'read' if operation == 'copy' else 'move')
        parent, root, parent_ref = _validate_reference(_file_parameter(args, fid, 'destination_parent'), 'directory_ref', 'create')
        name = str(_file_parameter(args, fid, 'name') or '')
        if not name or name in {'.', '..'} or os.path.basename(name) != name:
            raise RuntimeFailure('目标目录名无效', error_id='file.invalid_relative_path')
        destination = os.path.realpath(os.path.join(parent, name))
        _assert_contained(destination, root)
        try:
            destination_inside_source = (
                os.path.commonpath((os.path.normcase(destination), os.path.normcase(source)))
                == os.path.normcase(source)
            )
        except ValueError:
            destination_inside_source = False
        if destination_inside_source:
            raise RuntimeFailure(
                '目标目录不能位于来源目录内部',
                error_id='file.destination_inside_source',
            )
        return source, destination, root, parent_ref

    def _resolve_tree_conflict(self, destination: str, conflict: str) -> str | None:
        if not os.path.exists(destination):
            return destination
        if conflict == 'skip':
            return None
        if conflict == 'auto_rename':
            for index in range(2, 10002):
                candidate = f'{destination} ({index})'
                if not os.path.exists(candidate):
                    return candidate
        if conflict != 'error':
            raise RuntimeFailure(f'不支持的目录冲突策略：{conflict}', error_id='file.conflict_policy_unsupported')
        raise RuntimeFailure('目标目录已存在', error_id='file.conflict')

    def _execute_directory_copy(self, fid: str, args: dict[str, Any], cancelled) -> dict[str, Any]:
        source, destination, root, parent_ref = self._tree_destination(fid, args, 'copy')
        destination = self._resolve_tree_conflict(destination, str(_file_parameter(args, fid, 'conflict') or 'error'))
        if destination is None:
            return {
                'tree_operation_report.field.complete': True,
                'tree_operation_report.field.skipped': [os.path.basename(source)],
                'tree_operation_report.field.processed_files': 0,
                'tree_operation_report.field.processed_directories': 0,
                'tree_operation_report.field.failures': [],
                'tree_operation_report.field.destination': None,
            }
        report: dict[str, Any] = {
            'tree_operation_report.field.complete': False,
            'tree_operation_report.field.skipped': [],
            'tree_operation_report.field.processed_files': 0,
            'tree_operation_report.field.processed_directories': 0,
            'tree_operation_report.field.failures': [],
            'tree_operation_report.field.destination': None,
        }
        try:
            self._copy_tree(source, destination, cancelled, report)
            report['tree_operation_report.field.complete'] = True
        except RuntimeFailure as exc:
            if exc.error_id == 'runtime.cancelled':
                raise
            report['tree_operation_report.field.failures'].append({'error_id': exc.error_id, 'message': str(exc)})
        except OSError as exc:
            report['tree_operation_report.field.failures'].append({'error_id': 'file.directory_copy_failed', 'message': str(exc)})
        report['tree_operation_report.field.destination'] = windows_directory_reference(
            destination, root,
            access=tuple(item for item in (parent_ref.get('access') or ()) if item != 'delete_tree'),
            authorization_root_id=str(parent_ref.get('authorization_root_id') or ''),
            source=str(parent_ref.get('source') or 'external'),
        )
        return report

    def _copy_tree(
        self,
        source: str,
        destination: str,
        cancelled: Callable[[], bool],
        report: dict[str, Any],
    ) -> None:
        _cancel(cancelled)
        os.mkdir(destination)
        report['tree_operation_report.field.processed_directories'] += 1
        for entry in sorted(os.scandir(source), key=lambda item: item.name.casefold()):
            _cancel(cancelled)
            target = os.path.join(destination, entry.name)
            if entry.is_symlink():
                os.symlink(os.readlink(entry.path), target, target_is_directory=entry.is_dir())
                report['tree_operation_report.field.processed_files'] += 1
            elif entry.is_dir(follow_symlinks=False):
                self._copy_tree(entry.path, target, cancelled, report)
            else:
                _atomic_copy(entry.path, target, cancelled)
                report['tree_operation_report.field.processed_files'] += 1

    def _execute_directory_move(self, fid: str, args: dict[str, Any], cancelled) -> dict[str, Any]:
        source, destination, root, parent_ref = self._tree_destination(fid, args, 'move')
        destination = self._resolve_tree_conflict(destination, str(_file_parameter(args, fid, 'conflict') or 'error'))
        if destination is None:
            return {
                'tree_operation_report.field.complete': True,
                'tree_operation_report.field.skipped': [os.path.basename(source)],
                'tree_operation_report.field.processed_files': 0,
                'tree_operation_report.field.processed_directories': 0,
                'tree_operation_report.field.failures': [],
                'tree_operation_report.field.destination': None,
            }
        _cancel(cancelled)
        try:
            os.replace(source, destination)
            complete, failures = True, []
        except OSError as exc:
            complete = False
            failures = [{'error_id': 'file.directory_move_failed', 'message': str(exc)}]
        return {
            'tree_operation_report.field.complete': complete,
            'tree_operation_report.field.skipped': [],
            'tree_operation_report.field.processed_files': 0,
            'tree_operation_report.field.processed_directories': int(complete),
            'tree_operation_report.field.failures': failures,
            'tree_operation_report.field.destination': windows_directory_reference(
                destination,
                root,
                access=tuple(
                    item for item in (parent_ref.get('access') or ())
                    if item != 'delete_tree'
                ),
                authorization_root_id=str(parent_ref.get('authorization_root_id') or ''),
                source=str(parent_ref.get('source') or 'external'),
            ),
        }

    def _execute_directory_delete(self, fid: str, args: dict[str, Any], cancelled) -> bool:
        path, _, _ = _validate_reference(_file_parameter(args, fid, 'directory'), 'directory_ref', 'delete_empty')
        _cancel(cancelled)
        try:
            os.rmdir(path)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise RuntimeFailure(f'目录不为空或无法删除：{exc}', error_id='file.directory_not_empty') from exc

    @staticmethod
    def _same_path(left: str, right: str) -> bool:
        return os.path.normcase(os.path.realpath(os.path.abspath(left))) == os.path.normcase(
            os.path.realpath(os.path.abspath(right))
        )

    def _validate_delete_tree_confirmation(
        self,
        path: str,
        root: str,
        reference: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        from .function_contracts_v6 import official_function_registry_v6

        confirmation = context.get('confirmation') or {}
        statement_id = str(context.get('instruction_id') or '')
        expected_contract = official_function_registry_v6.require(
            'official.directory.delete_tree'
        ).fingerprint()
        required = {
            'confirmed': confirmation.get('confirmed') is True,
            'statement_id': str(confirmation.get('statement_id') or '') == statement_id and bool(statement_id),
            'authorization_root_id': str(confirmation.get('authorization_root_id') or '') == str(reference.get('authorization_root_id') or ''),
            'execution_config_revision': bool(str(confirmation.get('execution_config_revision') or '').strip()),
            'contract_fingerprint': str(confirmation.get('contract_fingerprint') or '') == expected_contract,
        }
        missing = sorted(name for name, valid in required.items() if not valid)
        if missing:
            raise RuntimeFailure(
                f'递归删除缺少有效的实际执行确认：{", ".join(missing)}',
                error_id='file.delete_tree_confirmation_required',
            )

        protected = [
            os.path.abspath(os.path.expanduser('~')),
            os.path.abspath(os.path.splitdrive(path)[0] + os.sep),
            *(str(item) for item in context.get('protected_roots') or [] if str(item)),
        ]
        for protected_root in protected:
            if protected_root and self._same_path(path, protected_root):
                raise RuntimeFailure(
                    '递归删除拒绝盘符根、用户目录、工作区或 Player 数据根',
                    error_id='file.protected_root',
                )

    def _delete_tree_entries(
        self,
        path: str,
        root: str,
        cancelled: Callable[[], bool],
    ) -> list[tuple[str, bool]]:
        entries: list[tuple[str, bool]] = []

        def visit(directory: str) -> None:
            _cancel(cancelled)
            resolved = os.path.realpath(directory)
            _assert_contained(resolved, root)
            for entry in sorted(os.scandir(directory), key=lambda item: item.name.casefold()):
                _cancel(cancelled)
                if entry.is_symlink():
                    raise RuntimeFailure(
                        f'递归删除拒绝符号链接：{entry.path}',
                        error_id='file.symlink_escape',
                    )
                child = os.path.realpath(entry.path)
                _assert_contained(child, root)
                if entry.is_dir(follow_symlinks=False):
                    visit(entry.path)
                else:
                    entries.append((entry.path, False))
            entries.append((directory, True))

        visit(path)
        return entries

    def _execute_directory_delete_tree(
        self,
        fid: str,
        args: dict[str, Any],
        cancelled: Callable[[], bool],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        path, root, reference = _validate_reference(
            _file_parameter(args, fid, 'directory'),
            'directory_ref',
            'delete_tree',
        )
        self._validate_delete_tree_confirmation(path, root, reference, context)
        raw_path = os.path.abspath(str(reference.get('path') or ''))
        if os.path.islink(raw_path):
            raise RuntimeFailure(
                '递归删除拒绝符号链接目标',
                error_id='file.symlink_escape',
            )
        if not os.path.isdir(path):
            return {
                'tree_delete_report.field.complete': True,
                'tree_delete_report.field.files_deleted': 0,
                'tree_delete_report.field.directories_deleted': 0,
                'tree_delete_report.field.failures': [],
            }
        # Preflight proves every descendant remains within the authorized tree
        # and rejects links before the first destructive mutation.
        entries = self._delete_tree_entries(path, root, cancelled)
        report = {
            'tree_delete_report.field.complete': False,
            'tree_delete_report.field.files_deleted': 0,
            'tree_delete_report.field.directories_deleted': 0,
            'tree_delete_report.field.failures': [],
        }
        for target, is_directory in entries:
            _cancel(cancelled)
            try:
                if is_directory:
                    os.rmdir(target)
                    report['tree_delete_report.field.directories_deleted'] += 1
                else:
                    os.remove(target)
                    report['tree_delete_report.field.files_deleted'] += 1
            except OSError as exc:
                report['tree_delete_report.field.failures'].append({
                    'path': target,
                    'error_id': 'file.delete_tree_failed',
                    'message': str(exc),
                })
                break
        report['tree_delete_report.field.complete'] = not report[
            'tree_delete_report.field.failures'
        ]
        return report


__all__ = [
    'FileRuntimeV6',
    'windows_directory_reference',
    'windows_file_reference',
]
