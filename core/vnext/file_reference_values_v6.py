"""Pure, capability-preserving derivation of child file references.

This module deliberately performs *no* filesystem access.  It validates the
portable relative-name contract and produces a deferred/lexical reference;
the Windows or Android file host still resolves the final target and proves
containment immediately before I/O.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileReferenceDerivationError(ValueError):
    error_id: str
    message: str

    def __str__(self) -> str:
        return self.message


_WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{index}' for index in range(1, 10)),
    *(f'LPT{index}' for index in range(1, 10)),
}
_WINDOWS_FORBIDDEN = frozenset('<>:"\\|?*')
_RESULT_ACCESS = {
    'file_ref<read>': 'read',
    'file_ref<write>': 'write',
}
_DIRECTORY_ACCESS = {
    'file_ref<read>': frozenset({'read'}),
    'file_ref<write>': frozenset({'write', 'create'}),
}


def safe_relative_segments(relative_path: Any) -> tuple[str, ...]:
    """Return normalized portable segments or a stable structured failure.

    A single forward-slash syntax is used by every host.  Rejecting Windows
    device names and reserved characters makes the saved ProgramDocument
    portable rather than allowing a project that only fails after packaging.
    """

    if not isinstance(relative_path, str):
        raise FileReferenceDerivationError(
            'file.relative_path_type', '相对位置必须是文本',
        )
    if not relative_path or len(relative_path.encode('utf-8')) > 4096:
        raise FileReferenceDerivationError(
            'file.relative_path_invalid', '相对位置不能为空或超过 4096 字节',
        )
    if relative_path.startswith(('/', '\\')) or '\\' in relative_path:
        raise FileReferenceDerivationError(
            'file.relative_path_invalid', '相对位置必须使用 /，且不能从根位置开始',
        )
    segments = tuple(relative_path.split('/'))
    if not segments or len(segments) > 128:
        raise FileReferenceDerivationError(
            'file.relative_path_invalid', '相对位置层级无效或超过 128 层',
        )
    for segment in segments:
        if (
            not segment
            or segment in {'.', '..'}
            or segment[-1:] in {' ', '.'}
            or len(segment.encode('utf-8')) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in segment)
            or any(character in _WINDOWS_FORBIDDEN for character in segment)
            or segment.split('.', 1)[0].upper() in _WINDOWS_RESERVED_NAMES
        ):
            raise FileReferenceDerivationError(
                'file.relative_path_invalid', f'相对位置包含不安全的名称：{segment or "<空>"}',
            )
    return segments


def derive_file_reference(
    directory: Any,
    relative_path: Any,
    result_type: str,
) -> dict[str, Any]:
    """Derive a child ``FileReference`` without widening authority or I/O."""

    requested_access = _RESULT_ACCESS.get(result_type)
    if requested_access is None:
        raise FileReferenceDerivationError(
            'file.reference_capability_invalid',
            f'不支持派生此文件引用能力：{result_type}',
        )
    if not isinstance(directory, dict) or directory.get('kind') != 'directory_ref':
        raise FileReferenceDerivationError(
            'file.invalid_reference', '需要已授权的目录引用',
        )
    platform = str(directory.get('platform') or '')
    if platform not in {'windows', 'android'}:
        raise FileReferenceDerivationError(
            'file.platform_unsupported', f'不支持的目录引用平台：{platform or "<空>"}',
        )
    authorization_root_id = str(directory.get('authorization_root_id') or '')
    if not authorization_root_id:
        raise FileReferenceDerivationError(
            'file.invalid_reference', '目录引用缺少授权根标识',
        )
    actual_access = {str(item) for item in directory.get('access') or ()}
    if not actual_access.intersection(_DIRECTORY_ACCESS[result_type]):
        raise FileReferenceDerivationError(
            'file.access_denied', f'目录引用不能派生 {requested_access} 文件引用',
        )

    segments = safe_relative_segments(relative_path)
    result: dict[str, Any] = {
        'kind': 'file_ref',
        'platform': platform,
        'source': 'derived_relative',
        'display_name': segments[-1],
        'authorization_root_id': authorization_root_id,
        # The derived value receives exactly one capability.  It never copies
        # the parent's broader access list.
        'access': [requested_access],
    }
    if platform == 'windows':
        parent_path = str(directory.get('path') or '')
        authorization_root = str(directory.get('authorization_root') or '')
        if not parent_path or not authorization_root:
            raise FileReferenceDerivationError(
                'file.invalid_reference', 'Windows 目录引用缺少授权载荷',
            )
        # ntpath is lexical and deterministic on every build host; realpath,
        # link/reparse-point containment and existence are deferred to I/O.
        result['path'] = ntpath.normpath(ntpath.join(parent_path, *segments))
        result['authorization_root'] = authorization_root
        return result

    private_path = str(directory.get('private_path') or '')
    uri = str(directory.get('uri') or '')
    if not private_path and not uri:
        raise FileReferenceDerivationError(
            'file.invalid_reference', 'Android 目录引用缺少私有路径或 SAF URI',
        )
    # Android resolves these segments through its private-files or SAF tree
    # host at I/O time.  Keeping the root carrier unchanged avoids fabricating
    # a child content:// URI and therefore avoids hidden provider access here.
    if private_path:
        result['private_path'] = private_path
    if uri:
        result['uri'] = uri
    result['relative_segments'] = list(directory.get('relative_segments') or ()) + list(segments)
    return result


__all__ = [
    'FileReferenceDerivationError',
    'derive_file_reference',
    'safe_relative_segments',
]
