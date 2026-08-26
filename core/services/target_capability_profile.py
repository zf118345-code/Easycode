"""Project-local, versioned capability observations for bound Windows targets."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from core.security import atomic_write_json


class TargetCapabilityProfileService:
    _lock = threading.RLock()

    @staticmethod
    def _path(project_dir: str) -> str:
        root = os.path.join(os.path.abspath(project_dir), '.easycode')
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, 'target-capabilities.json')

    @staticmethod
    def fingerprint(hwnd: int) -> dict[str, Any]:
        import win32api
        import win32gui
        import win32process

        root = int(win32gui.GetAncestor(int(hwnd), 2) or hwnd)
        _, pid = win32process.GetWindowThreadProcessId(root)
        executable = ''
        version = ''
        try:
            handle = win32api.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            try:
                import win32process as process_api

                executable = process_api.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            pass
        if executable:
            try:
                info = win32api.GetFileVersionInfo(executable, '\\')
                ms, ls = info['FileVersionMS'], info['FileVersionLS']
                version = f'{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}'
            except Exception:
                pass
        raw = '|'.join((os.path.normcase(executable), version, win32gui.GetClassName(root)))
        return {
            'id': hashlib.sha256(raw.encode('utf-8', errors='ignore')).hexdigest()[:24],
            'pid': int(pid),
            'executable': executable,
            'version': version,
            'class_name': win32gui.GetClassName(root),
        }

    @classmethod
    def _load(cls, project_dir: str) -> dict:
        path = cls._path(project_dir)
        if not os.path.isfile(path):
            return {'schema_version': 1, 'targets': {}}
        try:
            with open(path, encoding='utf-8-sig') as stream:
                value = json.load(stream)
            return value if isinstance(value, dict) and isinstance(value.get('targets'), dict) else {'schema_version': 1, 'targets': {}}
        except (OSError, ValueError):
            return {'schema_version': 1, 'targets': {}}

    @classmethod
    def observation(cls, context, capability: str) -> dict | None:
        project_dir = getattr(context, 'project_dir', '')
        hwnd = getattr(context, 'window_hwnd', None)
        if not project_dir or not hwnd:
            return None
        try:
            fingerprint = cls.fingerprint(hwnd)
        except Exception:
            return None
        with cls._lock:
            target = cls._load(project_dir).get('targets', {}).get(fingerprint['id'])
        item = target.get('capabilities', {}).get(capability) if isinstance(target, dict) else None
        return dict(item) if isinstance(item, dict) else None

    @classmethod
    def record(cls, context, capability: str, supported: bool, reason: str, **details) -> dict | None:
        project_dir = getattr(context, 'project_dir', '')
        hwnd = getattr(context, 'window_hwnd', None)
        if not project_dir or not hwnd:
            return None
        try:
            fingerprint = cls.fingerprint(hwnd)
        except Exception:
            return None
        with cls._lock:
            registry = cls._load(project_dir)
            targets = registry.setdefault('targets', {})
            target = targets.setdefault(fingerprint['id'], {**fingerprint, 'capabilities': {}})
            target.update(fingerprint)
            item = {
                'supported': bool(supported),
                'reason': str(reason or ''),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                **details,
            }
            target.setdefault('capabilities', {})[str(capability)] = item
            atomic_write_json(cls._path(project_dir), registry)
            return item


target_capability_profiles = TargetCapabilityProfileService()

