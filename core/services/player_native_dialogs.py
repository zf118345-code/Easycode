"""Minimal native file/directory pickers for the independent Windows Player.

This module deliberately has no authoring-workspace dependency.  It returns
strongly typed references and never exposes a raw path as the field value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.vnext.file_runtime_v6 import windows_directory_reference, windows_file_reference


class PlayerNativeDialogError(RuntimeError):
    pass


def _reference_access(value_type: str, *, directory: bool) -> tuple[str, ...]:
    declared = str(value_type or '').strip().lower()
    access = declared.partition('<')[2].removesuffix('>') if '<' in declared else ''
    if directory:
        return {
            'read': ('read', 'list'),
            'list': ('list',),
            'create': ('create',),
            'move': ('move',),
            'delete_empty': ('delete_empty',),
            'delete_tree': ('delete_tree',),
            'read_write': ('read', 'list', 'create', 'write'),
        }.get(access, ('read', 'list'))
    return {
        'read': ('read',),
        'write': ('write',),
        'delete': ('delete',),
        'read_delete': ('read', 'read_delete'),
        'execute': ('execute',),
    }.get(access, ('read',))


def _file_types(constraints: dict[str, Any]) -> list[tuple[str, str]]:
    extensions = constraints.get('extensions') or constraints.get('file_extensions') or []
    if not isinstance(extensions, list):
        extensions = []
    patterns: list[str] = []
    for item in extensions:
        suffix = str(item or '').strip().lower()
        if not suffix:
            continue
        suffix = suffix if suffix.startswith('.') else f'.{suffix}'
        if suffix[1:].replace('-', '').replace('_', '').isalnum():
            patterns.append(f'*{suffix}')
    return [('允许的文件', ' '.join(dict.fromkeys(patterns)))] if patterns else [('所有文件', '*.*')]


class PlayerNativeDialogService:
    """Open one user-triggered Windows system picker and return a candidate."""

    @staticmethod
    def choose(
        action_id: str,
        *,
        label: str,
        value_type: str,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if os.name != 'nt':
            raise PlayerNativeDialogError('当前 Player 宿主不支持 Windows 系统选择器')
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            root.update_idletasks()
            try:
                title = str(label or '选择内容')
                if action_id == 'choose-file-read':
                    path = str(filedialog.askopenfilename(
                        parent=root, title=f'选择要读取的文件 · {title}',
                        filetypes=_file_types(dict(constraints or {})),
                    ) or '')
                elif action_id == 'choose-file-save':
                    path = str(filedialog.asksaveasfilename(
                        parent=root, title=f'选择保存位置 · {title}',
                        filetypes=_file_types(dict(constraints or {})),
                        confirmoverwrite=True,
                    ) or '')
                elif action_id == 'choose-directory':
                    path = str(filedialog.askdirectory(
                        parent=root, title=f'选择文件夹 · {title}', mustexist=True,
                    ) or '')
                else:
                    raise PlayerNativeDialogError(f'不支持的系统选择动作：{action_id}')
            finally:
                root.destroy()
        except PlayerNativeDialogError:
            raise
        except Exception as exc:
            raise PlayerNativeDialogError(f'Windows 系统选择器启动失败：{exc}') from exc

        if not path:
            return None
        selected = Path(path).resolve()
        if action_id == 'choose-file-read' and not selected.is_file():
            raise PlayerNativeDialogError('选择的读取文件不存在或不是文件')
        if action_id == 'choose-file-save' and not selected.parent.is_dir():
            raise PlayerNativeDialogError('选择的保存目录不存在或不可用')
        if action_id == 'choose-directory' and not selected.is_dir():
            raise PlayerNativeDialogError('选择的位置不是可用文件夹')

        if action_id == 'choose-directory':
            reference = windows_directory_reference(
                str(selected), str(selected),
                access=_reference_access(value_type, directory=True),
                source='player_system_picker',
            )
            kind = 'directory'
        else:
            reference = windows_file_reference(
                str(selected), str(selected.parent),
                access=_reference_access(value_type, directory=False),
                source='player_system_picker',
            )
            kind = 'file'
        return {
            'kind': kind,
            'display_name': str(reference.get('display_name') or selected.name),
            'access': list(reference.get('access') or []),
            'reference': reference,
        }


player_native_dialog_service = PlayerNativeDialogService()


__all__ = [
    'PlayerNativeDialogError',
    'PlayerNativeDialogService',
    'player_native_dialog_service',
]
