"""Current-user IDE preferences that never enter a published project."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Mapping


DEFAULT_IDE_SHORTCUTS: dict[str, str] = {
    'edit.undo': 'Ctrl+Z',
    'edit.redo': 'Ctrl+Y',
    'edit.find': 'Ctrl+F',
    'edit.copy_statements': 'Ctrl+C',
    'edit.cut_statements': 'Ctrl+X',
    'edit.paste_statements': 'Ctrl+V',
    'edit.duplicate_statement': 'Ctrl+D',
    'edit.delete_statement': 'Delete',
    'edit.extract_function': 'Ctrl+Shift+E',
    'run.start_or_resume': 'F5',
    'run.step': 'F10',
    'run.toggle_breakpoint': 'F9',
    'view.toggle_problems': 'Ctrl+Shift+M',
    'view.toggle_log': 'Ctrl+J',
    'help.command_palette': 'Ctrl+Shift+P',
}

_KEY_PATTERN = re.compile(r'^(?:[A-Z0-9]|F(?:[1-9]|1[0-9]|2[0-4])|DELETE|BACKSPACE|ENTER|ESCAPE|SPACE)$')
_MODIFIER_ORDER = ('Ctrl', 'Alt', 'Shift', 'Meta')


class IdeSettingsError(ValueError):
    pass


def normalize_shortcut(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    parts = [part.strip() for part in raw.replace('-', '+').split('+') if part.strip()]
    aliases = {
        'CONTROL': 'Ctrl', 'CTRL': 'Ctrl', 'ALT': 'Alt', 'SHIFT': 'Shift',
        'META': 'Meta', 'CMD': 'Meta', 'COMMAND': 'Meta', 'WIN': 'Meta',
        'ESC': 'Escape', 'DEL': 'Delete', 'RETURN': 'Enter',
    }
    modifiers: set[str] = set()
    key = ''
    for part in parts:
        normalized = aliases.get(part.upper(), part.upper())
        if normalized in _MODIFIER_ORDER:
            modifiers.add(normalized)
            continue
        if key:
            raise IdeSettingsError(f'快捷键只能包含一个普通按键：{raw}')
        key = normalized.title() if normalized in {'DELETE', 'BACKSPACE', 'ENTER', 'ESCAPE', 'SPACE'} else normalized
    if not key or not _KEY_PATTERN.fullmatch(key.upper()):
        raise IdeSettingsError(f'快捷键格式无效：{raw}')
    return '+'.join([*(item for item in _MODIFIER_ORDER if item in modifiers), key])


class IdeSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            base = Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()) / 'EasyCode'
            path = base / 'ide-settings.json'
        self.path = Path(path)
        self._lock = threading.RLock()

    def load(self) -> dict[str, object]:
        with self._lock:
            shortcuts = dict(DEFAULT_IDE_SHORTCUTS)
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8')) if self.path.is_file() else {}
                values = raw.get('shortcuts') if isinstance(raw, dict) else None
                if isinstance(values, dict):
                    for command_id, value in values.items():
                        if command_id in shortcuts and isinstance(value, str):
                            shortcuts[command_id] = normalize_shortcut(value)
            except (OSError, json.JSONDecodeError, IdeSettingsError):
                shortcuts = dict(DEFAULT_IDE_SHORTCUTS)
            return {'schema_version': 1, 'shortcuts': shortcuts, 'defaults': dict(DEFAULT_IDE_SHORTCUTS)}

    def save(self, values: Mapping[str, str]) -> dict[str, object]:
        unknown = sorted(set(values) - set(DEFAULT_IDE_SHORTCUTS))
        if unknown:
            raise IdeSettingsError(f'未知快捷键命令：{unknown[0]}')
        shortcuts = dict(DEFAULT_IDE_SHORTCUTS)
        shortcuts.update({command_id: normalize_shortcut(value) for command_id, value in values.items()})
        assigned = [value.casefold() for value in shortcuts.values() if value]
        if len(assigned) != len(set(assigned)):
            raise IdeSettingsError('快捷键不能重复；请先清除冲突项')
        payload = {'schema_version': 1, 'shortcuts': shortcuts}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f'{self.path.suffix}.tmp')
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            os.replace(temporary, self.path)
        return {**payload, 'defaults': dict(DEFAULT_IDE_SHORTCUTS)}


ide_settings_store = IdeSettingsStore()


__all__ = [
    'DEFAULT_IDE_SHORTCUTS', 'IdeSettingsError', 'IdeSettingsStore',
    'ide_settings_store', 'normalize_shortcut',
]
