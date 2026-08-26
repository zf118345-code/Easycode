"""项目版本快照：内容哈希去重、按数量与空间双重限额保留。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


class SnapshotService:
    HISTORY_DIR = '.easycode/history'
    MAX_SNAPSHOTS = 100
    MAX_BYTES = 500 * 1024 * 1024

    @classmethod
    def _history_dir(cls, project_path: str) -> str:
        path = os.path.join(os.path.abspath(project_path), *cls.HISTORY_DIR.split('/'))
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _canonical_hash(blueprint: dict) -> str:
        payload = json.dumps(blueprint, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def create(cls, project_path: str, blueprint: dict, reason: str = 'save') -> dict:
        history_dir = cls._history_dir(project_path)
        digest = cls._canonical_hash(blueprint)
        latest = cls.list(project_path)
        if latest and latest[0].get('hash') == digest:
            return {**latest[0], 'deduplicated': True}

        now = datetime.now(timezone.utc)
        snapshot_id = f'{now.strftime("%Y%m%dT%H%M%S%fZ")}-{digest[:12]}'
        record = {
            'snapshot_id': snapshot_id,
            'created_at': now.isoformat(),
            'reason': reason,
            'hash': digest,
            'project_name': blueprint.get('project_name', ''),
            'blueprint': blueprint,
        }
        target = os.path.join(history_dir, snapshot_id + '.json')
        fd, tmp_path = tempfile.mkstemp(prefix='snapshot_', suffix='.tmp', dir=history_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
            os.replace(tmp_path, target)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        cls._prune(history_dir)
        return {key: value for key, value in record.items() if key != 'blueprint'}

    @classmethod
    def capture_current(cls, project_path: str, reason: str = 'save') -> dict:
        from core.services.blueprint_service import BlueprintService

        blueprint = BlueprintService.load_blueprint(project_path)
        auxiliary = {}
        for filename in ('form_schema.json', 'context.json'):
            path = os.path.join(project_path, filename)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding='utf-8-sig') as stream:
                    auxiliary[filename] = json.load(stream)
            except (OSError, ValueError):
                continue
        if auxiliary:
            blueprint['_auxiliary_files'] = auxiliary
        return cls.create(project_path, blueprint, reason)

    @classmethod
    def list(cls, project_path: str) -> list[dict]:
        history_dir = cls._history_dir(project_path)
        records = []
        for name in sorted(os.listdir(history_dir), reverse=True):
            if not name.endswith('.json'):
                continue
            path = os.path.join(history_dir, name)
            try:
                with open(path, encoding='utf-8') as stream:
                    record = json.load(stream)
                records.append({key: value for key, value in record.items() if key != 'blueprint'})
            except (OSError, ValueError):
                continue
        return records

    @classmethod
    def restore(cls, project_path: str, snapshot_id: str) -> dict:
        safe_id = os.path.basename(str(snapshot_id or ''))
        if safe_id != snapshot_id or not safe_id:
            raise ValueError('快照 ID 无效')
        path = os.path.join(cls._history_dir(project_path), safe_id + '.json')
        if not os.path.isfile(path):
            raise FileNotFoundError(f'快照不存在: {snapshot_id}')
        with open(path, encoding='utf-8') as stream:
            record = json.load(stream)
        blueprint = record.get('blueprint')
        if not isinstance(blueprint, dict):
            raise ValueError('快照内容损坏')

        # 先记录当前状态，恢复动作本身可撤回。
        cls.capture_current(project_path, reason='before_restore')
        from core.services.blueprint_service import BlueprintService

        auxiliary = blueprint.pop('_auxiliary_files', {}) if isinstance(blueprint.get('_auxiliary_files'), dict) else {}
        BlueprintService.save_blueprint(project_path, blueprint, create_snapshot=False)
        for filename, data in auxiliary.items():
            if filename not in ('form_schema.json', 'context.json'):
                continue
            BlueprintService._safe_write(os.path.join(project_path, filename), data)
        meta = BlueprintService.load_project_meta(project_path)
        BlueprintService.save_project_meta(
            project_path,
            meta,
            create_snapshot=True,
            snapshot_reason=f'restore:{snapshot_id}',
        )
        restored = cls.list(project_path)[0]
        return {'status': 'success', 'restored': restored}

    @classmethod
    def _prune(cls, history_dir: str):
        files = sorted(
            (name for name in os.listdir(history_dir) if name.endswith('.json')),
            reverse=True,
        )
        sizes = {}
        total = 0
        for name in files:
            try:
                sizes[name] = os.path.getsize(os.path.join(history_dir, name))
            except OSError:
                sizes[name] = 0
            total += sizes[name]
        # ``files`` is newest-first.  Prune oldest first so the most recent
        # recovery points survive both the count and disk-space policies.
        retained = len(files)
        for name in reversed(files):
            if retained <= cls.MAX_SNAPSHOTS and total <= cls.MAX_BYTES:
                break
            try:
                os.unlink(os.path.join(history_dir, name))
                total = max(0, total - sizes[name])
                retained -= 1
            except FileNotFoundError:
                retained -= 1
