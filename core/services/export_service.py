# core/services/export_service.py
import json
import os
import hashlib
from datetime import datetime

from fastapi import HTTPException

from core.builder.exporter import ProjectExporter
from core.player.schema import normalize_form_schema
from core.services.preflight_service import PreflightService


class ExportService:
    """
    工业级导出与 Schema 业务服务
    实现控制层与打包导出逻辑的解耦
    """

    @classmethod
    def get_form_schema(cls, project_path: str) -> dict:
        """读取项目绑定的客户动态表单 Schema"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')

        schema_path = os.path.join(project_path, 'form_schema.json')
        if os.path.exists(schema_path):
            try:
                with open(schema_path, encoding='utf-8') as f:
                    original = json.load(f)
                return normalize_form_schema(original)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f'读取 Schema 失败: {e}') from e

        return normalize_form_schema({'form_title': '客户运行配置面板', 'groups': []})

    @classmethod
    def save_form_schema(cls, project_path: str, schema_data: dict) -> dict:
        """保存项目绑定的客户动态表单 Schema"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')

        schema_path = os.path.join(project_path, 'form_schema.json')
        try:
            normalized = normalize_form_schema(schema_data)
            changed = True
            if os.path.exists(schema_path):
                with open(schema_path, encoding='utf-8') as f:
                    previous = json.load(f)
                if previous != normalized:
                    cls._snapshot_and_write_schema(project_path, previous, normalized)
                else:
                    changed = False
            else:
                cls._atomic_write_json(schema_path, normalized)
            revision = None
            if changed:
                from core.services.blueprint_service import BlueprintService

                meta = BlueprintService.load_project_meta(project_path)
                BlueprintService.save_project_meta(
                    project_path,
                    meta,
                    create_snapshot=True,
                    snapshot_reason='save_form_schema',
                )
                revision = int(meta.get('revision', 0)) + 1
            return {
                'status': 'success',
                'schema_version': normalized['schema_version'],
                'revision': revision,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'保存 Schema 失败: {e}') from e

    @classmethod
    def build_export_bundle(cls, project_path: str, form_schema: dict, acknowledge_warnings: bool = False) -> dict:
        """执行项目打包与 DRM 加密构建"""
        if not project_path or not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')

        report = PreflightService.check(project_path, form_schema)
        if report['counts']['error']:
            raise HTTPException(status_code=422, detail={'message': '发布前检查未通过', 'preflight': report})
        if report['counts']['warning'] and not acknowledge_warnings:
            raise HTTPException(status_code=409, detail={'message': '发布前检查存在警告，需要确认', 'preflight': report})
        try:
            from core.services.build_snapshot_service import BuildSnapshotService

            snapshot = BuildSnapshotService.create(project_path)
            try:
                result = ProjectExporter.build_export_bundle(
                    snapshot['path'],
                    normalize_form_schema(form_schema),
                    output_dir=os.path.join(project_path, 'release'),
                )
                result['project_id'] = snapshot['project_id']
                result['revision'] = snapshot['revision']
            finally:
                BuildSnapshotService.remove(snapshot)
            from core.services.snapshot_service import SnapshotService

            SnapshotService.capture_current(project_path, 'build_bundle')
            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'打包编译失败: {e}') from e

    @classmethod
    def export_project_config(cls, project_path: str) -> dict:
        """导出可读配置快照（不包含模板与密包），供版本留档和人工核对。"""
        if not project_path or not os.path.isdir(project_path):
            raise HTTPException(status_code=404, detail='项目路径不存在')
        from core.services.blueprint_service import BlueprintService

        payload = BlueprintService.load_blueprint(project_path)
        payload['form_schema'] = cls.get_form_schema(project_path)
        context_path = os.path.join(project_path, 'context.json')
        if os.path.isfile(context_path):
            try:
                with open(context_path, encoding='utf-8-sig') as f:
                    payload['context'] = json.load(f)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f'context.json 无法导出: {exc}') from exc
        export_dir = os.path.join(project_path, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        safe_name = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in payload.get('project_name', 'project'))
        output_path = os.path.join(export_dir, f'{safe_name}-config-{stamp}.json')
        cls._atomic_write_json(output_path, payload)
        return {'success': True, 'output_file': output_path}

    @staticmethod
    def _atomic_write_json(path: str, data: dict) -> None:
        temp_path = f'{path}.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)

    @classmethod
    def _snapshot_and_write_schema(cls, project_path: str, previous: dict, normalized: dict) -> None:
        """覆盖前保留去重快照，再原子写入当前版 Schema。"""
        serialized = json.dumps(previous, ensure_ascii=False, sort_keys=True).encode('utf-8')
        digest = hashlib.sha256(serialized).hexdigest()[:12]
        history_dir = os.path.join(project_path, '.easycode', 'history', 'schema')
        os.makedirs(history_dir, exist_ok=True)
        existing = [name for name in os.listdir(history_dir) if digest in name]
        if not existing:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            cls._atomic_write_json(os.path.join(history_dir, f'form_schema-{stamp}-{digest}.json'), previous)
        cls._atomic_write_json(os.path.join(project_path, 'form_schema.json'), normalized)
