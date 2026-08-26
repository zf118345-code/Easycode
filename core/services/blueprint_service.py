# core/services/blueprint_service.py
# 项目版本化文档存储服务
#   - project.json  : project_name / variables / ui_state
#   - workflow.json : { main_graph, functions, function_folders }
#   - topology.json : { nodes, edges, blocks }（项目唯一页面地图）
# 当前格式只接受严格 v3 项目文档，不自动迁移、补建或猜测修复旧字段。

import json
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid

from fastapi import HTTPException

from core.project_schema import (
    PROJECT_FILE,
    PROJECT_SCHEMA_VERSION,
    TOPOLOGY_FILE,
    WORKFLOW_FILE,
    ProjectFormatError,
    load_document,
    validate_document,
    collect_function_references,
    create_function_definition,
)
logger = logging.getLogger(__name__)


def _atomic_write_json(file_path: str, data: dict):
    """
    原子写入 JSON 文件
    先写入临时文件，再 rename 替换原文件，避免写入中途崩溃导致文件损坏
    """
    dir_path = os.path.dirname(os.path.abspath(file_path))
    fd, tmp_path = tempfile.mkstemp(suffix='.tmp', prefix='blueprint_', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows 下 os.replace 会原子替换；Linux 下 rename 也是原子的
        os.replace(tmp_path, file_path)
    except Exception:
        # 清理临时文件
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        raise


class BlueprintService:
    _save_lock = threading.RLock()

    @classmethod
    def _recover_pending_transactions(cls, project_path: str) -> None:
        root = os.path.join(project_path, '.easycode', 'recovery', 'transactions')
        if not os.path.isdir(root):
            return
        for name in os.listdir(root):
            transaction = os.path.join(root, name)
            manifest_path = os.path.join(transaction, 'manifest.json')
            if not os.path.isfile(manifest_path):
                continue
            try:
                with open(manifest_path, encoding='utf-8') as stream:
                    filenames = list((json.load(stream) or {}).get('filenames') or [])
                for filename in filenames:
                    if filename not in {PROJECT_FILE, WORKFLOW_FILE, TOPOLOGY_FILE}:
                        continue
                    backup = os.path.join(transaction, 'before', filename)
                    if os.path.isfile(backup):
                        shutil.copy2(backup, os.path.join(project_path, filename))
                shutil.rmtree(transaction, ignore_errors=True)
                logger.warning('已恢复未完成的项目保存事务: %s', name)
            except (OSError, ValueError) as exc:
                raise HTTPException(status_code=500, detail=f'项目保存恢复失败: {exc}') from exc

    @classmethod
    def _write_transaction(cls, project_path: str, documents: dict[str, dict]) -> None:
        """Commit multiple project documents as a recoverable unit."""
        if not documents:
            return
        allowed = {PROJECT_FILE, WORKFLOW_FILE, TOPOLOGY_FILE}
        if not set(documents).issubset(allowed):
            raise HTTPException(status_code=500, detail='项目事务包含未知文档')
        transaction_id = f'txn_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}'
        transaction = os.path.join(project_path, '.easycode', 'recovery', 'transactions', transaction_id)
        before = os.path.join(transaction, 'before')
        staged = os.path.join(transaction, 'staged')
        os.makedirs(before, exist_ok=False)
        os.makedirs(staged, exist_ok=False)
        filenames = list(documents)
        try:
            for filename, data in documents.items():
                source = os.path.join(project_path, filename)
                if os.path.isfile(source):
                    shutil.copy2(source, os.path.join(before, filename))
                _atomic_write_json(os.path.join(staged, filename), data)
            _atomic_write_json(
                os.path.join(transaction, 'manifest.json'),
                {'schema_version': 1, 'transaction_id': transaction_id, 'filenames': filenames},
            )
            for filename in filenames:
                os.replace(os.path.join(staged, filename), os.path.join(project_path, filename))
        except Exception:
            rollback_ok = True
            for filename in filenames:
                backup = os.path.join(before, filename)
                if os.path.isfile(backup):
                    try:
                        shutil.copy2(backup, os.path.join(project_path, filename))
                    except OSError:
                        rollback_ok = False
            if rollback_ok:
                shutil.rmtree(transaction, ignore_errors=True)
            raise
        else:
            shutil.rmtree(transaction, ignore_errors=True)

    @classmethod
    def _prepare(cls, project_path: str) -> str:
        """校验项目目录；当前格式不会自动迁移、补建或修复项目文件。"""
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f'项目路径不存在: {project_path}')
        if not os.path.isdir(project_path):
            raise HTTPException(status_code=422, detail='项目路径必须是文件夹')
        cls._recover_pending_transactions(project_path)
        return project_path

    @classmethod
    def _load_document(cls, project_path: str, filename: str) -> dict:
        cls._prepare(project_path)
        try:
            return load_document(project_path, filename)
        except ProjectFormatError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @staticmethod
    def get_blueprint_path(project_path: str) -> str:
        """project.json 路径"""
        return os.path.join(project_path, PROJECT_FILE)

    @staticmethod
    def get_workflow_path(project_path: str) -> str:
        return os.path.join(project_path, WORKFLOW_FILE)

    @staticmethod
    def get_topology_path(project_path: str) -> str:
        return os.path.join(project_path, TOPOLOGY_FILE)

    # ============ project.json（项目元数据） ============

    @classmethod
    def load_project_meta(cls, project_path: str) -> dict:
        return cls._load_document(project_path, PROJECT_FILE)

    @classmethod
    def save_project_meta(
        cls,
        project_path: str,
        data: dict,
        create_snapshot: bool = True,
        snapshot_reason: str = 'save_meta',
    ):
        with cls._save_lock:
            cls._prepare(project_path)
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail='项目数据必须是字典类型')
            clean = cls._sanitize_for_json(data)
            current = cls.load_project_meta(project_path)
            project_data = {
                'schema_version': PROJECT_SCHEMA_VERSION,
                'project_id': current['project_id'],
                'revision': int(current.get('revision', 0)) + (1 if create_snapshot else 0),
                'project_name': clean.get('project_name', current['project_name']),
                'variables': clean.get('variables', current.get('variables', {})),
                'ui_state': clean.get('ui_state', current.get('ui_state', {})),
                'settings': clean.get('settings', current.get('settings', {})),
            }
            cls._validate_document(PROJECT_FILE, project_data)
            cls._safe_write(cls.get_blueprint_path(project_path), project_data)
            if create_snapshot:
                cls._capture_snapshot(project_path, snapshot_reason)
            return project_data['revision']

    # ============ workflow.json（流程画布） ============

    @classmethod
    def load_workflow(cls, project_path: str) -> dict:
        return cls._load_document(project_path, WORKFLOW_FILE)

    @classmethod
    def save_workflow(cls, project_path: str, data: dict, create_snapshot: bool = True):
        with cls._save_lock:
            cls._prepare(project_path)
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail='流程画布数据必须是字典类型')
            clean = cls._sanitize_for_json(data)
            obsolete = {'tasks', 'edges', 'node_folders'} & set(clean)
            if obsolete:
                raise HTTPException(status_code=400, detail=f'workflow.json 不再支持旧字段: {", ".join(sorted(obsolete))}')
            missing = {'main_graph', 'functions', 'function_folders'} - set(clean)
            if missing:
                raise HTTPException(status_code=400, detail=f'workflow.json 缺少字段: {", ".join(sorted(missing))}')
            workflow_data = {
                'schema_version': PROJECT_SCHEMA_VERSION,
                'main_graph': clean.get('main_graph', {}),
                'functions': clean.get('functions', []),
                'function_folders': clean.get('function_folders', []),
            }
            from core.services.template_library_service import TemplateLibraryService
            TemplateLibraryService.sanitize_tombstoned_graph(project_path, workflow_data, 'workflow')
            cls._validate_document(WORKFLOW_FILE, workflow_data)
            documents = {WORKFLOW_FILE: workflow_data}
            if create_snapshot:
                meta = cls.load_project_meta(project_path)
                meta['revision'] = int(meta.get('revision', 0)) + 1
                cls._validate_document(PROJECT_FILE, meta)
                documents[PROJECT_FILE] = meta
            cls._write_transaction(project_path, documents)
            if create_snapshot:
                cls._capture_snapshot(project_path, 'save_workflow')

    # ============ topology.json（拓扑地图） ============

    @classmethod
    def load_topology(cls, project_path: str) -> dict:
        return cls._load_document(project_path, TOPOLOGY_FILE)

    @classmethod
    def save_topology(cls, project_path: str, data: dict, create_snapshot: bool = True):
        with cls._save_lock:
            cls._prepare(project_path)
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail='拓扑地图数据必须是字典类型')
            clean = cls._sanitize_for_json(data)
            obsolete = {'tasks', 'collections', 'regions'} & set(clean)
            if obsolete:
                raise HTTPException(status_code=400, detail=f'topology.json 是唯一扁平页面地图，不支持: {", ".join(sorted(obsolete))}')
            missing = {'nodes', 'edges', 'blocks'} - set(clean)
            if missing:
                raise HTTPException(status_code=400, detail=f'topology.json 缺少字段: {", ".join(sorted(missing))}')
            topology_data = {
                'schema_version': PROJECT_SCHEMA_VERSION,
                'nodes': clean.get('nodes', []),
                'edges': clean.get('edges', []),
                'blocks': clean.get('blocks', []),
            }
            from core.services.template_library_service import TemplateLibraryService
            TemplateLibraryService.sanitize_tombstoned_graph(project_path, topology_data, 'topology')
            cls._validate_document(TOPOLOGY_FILE, topology_data)
            documents = {TOPOLOGY_FILE: topology_data}
            if create_snapshot:
                meta = cls.load_project_meta(project_path)
                meta['revision'] = int(meta.get('revision', 0)) + 1
                cls._validate_document(PROJECT_FILE, meta)
                documents[PROJECT_FILE] = meta
            cls._write_transaction(project_path, documents)
            if create_snapshot:
                cls._capture_snapshot(project_path, 'save_topology')

    # ============ 合并视图（快照/导出/执行用） ============

    @classmethod
    def load_blueprint(cls, project_path: str) -> dict:
        """加载供快照、导出与执行消费的当前版合并视图。"""
        cls._prepare(project_path)
        meta = cls.load_project_meta(project_path)
        workflow = cls.load_workflow(project_path)
        topology = cls.load_topology(project_path)
        return {
            'schema_version': PROJECT_SCHEMA_VERSION,
            'project_id': meta['project_id'],
            'revision': meta['revision'],
            'project_name': meta.get('project_name', os.path.basename(project_path)),
            'main_graph': workflow.get('main_graph', {}),
            'functions': workflow.get('functions', []),
            'function_folders': workflow.get('function_folders', []),
            'variables': meta.get('variables', {}),
            'page_map': topology,
            'ui_state': meta.get('ui_state', {}),
            'settings': meta.get('settings', {}),
        }

    @classmethod
    def save_blueprint(cls, project_path: str, data: dict, create_snapshot: bool = True):
        """
        保存合并蓝图并拆分写入三个当前版项目文档。
        元数据保存允许只含元数据；画布字段存在时才写对应画布。
        """
        with cls._save_lock:
            cls._prepare(project_path)
            if not isinstance(data, dict):
                raise HTTPException(status_code=400, detail='蓝图数据必须是字典类型')
            clean = cls._sanitize_for_json(data)
            current = cls.load_project_meta(project_path)
            meta = {
                'schema_version': PROJECT_SCHEMA_VERSION,
                'project_id': current['project_id'],
                'revision': int(current.get('revision', 0)) + (1 if create_snapshot else 0),
                'project_name': clean.get('project_name', current['project_name']),
                'variables': clean.get('variables', current.get('variables', {})),
                'ui_state': clean.get('ui_state', current.get('ui_state', {})),
                'settings': clean.get('settings', current.get('settings', {})),
            }
            cls._validate_document(PROJECT_FILE, meta)
            documents = {PROJECT_FILE: meta}
            if 'main_graph' in clean or 'functions' in clean or 'function_folders' in clean:
                workflow = {
                    'schema_version': PROJECT_SCHEMA_VERSION,
                    'main_graph': clean.get('main_graph', {}),
                    'functions': clean.get('functions', []),
                    'function_folders': clean.get('function_folders', []),
                }
                from core.services.template_library_service import TemplateLibraryService
                TemplateLibraryService.sanitize_tombstoned_graph(project_path, workflow, 'workflow')
                cls._validate_document(WORKFLOW_FILE, workflow)
                documents[WORKFLOW_FILE] = workflow
            if 'topology' in clean:
                raise HTTPException(status_code=400, detail='请使用 page_map；topology 旧字段已移除')
            if 'page_map' in clean:
                topology_clean = cls._sanitize_for_json(clean.get('page_map'))
                topology = {
                    'schema_version': PROJECT_SCHEMA_VERSION,
                    'nodes': topology_clean.get('nodes', []),
                    'edges': topology_clean.get('edges', []),
                    'blocks': topology_clean.get('blocks', []),
                }
                from core.services.template_library_service import TemplateLibraryService
                TemplateLibraryService.sanitize_tombstoned_graph(project_path, topology, 'topology')
                cls._validate_document(TOPOLOGY_FILE, topology)
                documents[TOPOLOGY_FILE] = topology
            cls._write_transaction(project_path, documents)
            if create_snapshot:
                cls._capture_snapshot(project_path, 'save_blueprint')

    # ============ 函数 CRUD ============

    @classmethod
    def list_functions(cls, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        functions = [
            {
                'function_id': item.get('function_id'),
                'name': item.get('name'),
                'description': item.get('description', ''),
                'folder_id': item.get('folder_id'),
                'node_count': len((item.get('graph') or {}).get('nodes', [])),
                'parameters': item.get('parameters', []),
                'outputs': item.get('outputs', []),
                'outcomes': item.get('outcomes', []),
            }
            for item in workflow.get('functions', [])
        ]
        return {'functions': functions, 'function_folders': workflow.get('function_folders', [])}

    @classmethod
    def get_function(cls, function_id: str, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        for item in workflow.get('functions', []):
            if item.get('function_id') == function_id:
                return item
        raise HTTPException(status_code=404, detail=f'函数不存在: {function_id}')

    @classmethod
    def save_function(cls, function_id: str, project_path: str, function_data: dict) -> dict:
        workflow = cls.load_workflow(project_path)
        items = workflow.setdefault('functions', [])
        index = next((index for index, item in enumerate(items) if item.get('function_id') == function_id), -1)
        if index < 0:
            raise HTTPException(status_code=404, detail='函数不存在')
        value = cls._sanitize_for_json(function_data)
        value['function_id'] = function_id
        value.setdefault('graph', {})['graph_id'] = function_id
        value['name'] = cls._unique_function_name(value.get('name'), items, exclude_function_id=function_id)
        items[index] = value
        cls.save_workflow(project_path, workflow)
        return {'status': 'success', 'function_id': function_id, 'name': value['name']}

    @classmethod
    def create_function(cls, project_path: str, name: str = '新建函数', folder_id: str | None = None) -> dict:
        workflow = cls.load_workflow(project_path)
        items = workflow.setdefault('functions', [])
        function = create_function_definition(cls._unique_function_name(name, items), folder_id)
        items.append(function)
        cls.save_workflow(project_path, workflow)
        return function

    @classmethod
    def delete_function(cls, function_id: str, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        functions = workflow.get('functions', [])
        target = next((item for item in functions if item.get('function_id') == function_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail='函数不存在')
        references = collect_function_references(workflow, function_id)
        if references:
            raise HTTPException(
                status_code=409,
                detail=f'该函数仍被 {len(references)} 个“调用函数”节点使用，请先清理引用',
            )
        workflow['functions'] = [item for item in functions if item.get('function_id') != function_id]
        cls.save_workflow(project_path, workflow)
        return {'status': 'success'}

    @classmethod
    def duplicate_function(cls, function_id: str, project_path: str) -> dict:
        source = cls.get_function(function_id, project_path)
        workflow = cls.load_workflow(project_path)
        from core.services.function_package_service import clone_function_with_new_ids

        clone = clone_function_with_new_ids(source)
        clone['name'] = cls._unique_function_name(f'{source.get("name") or "函数"}副本', workflow.get('functions', []))
        workflow.setdefault('functions', []).append(clone)
        cls.save_workflow(project_path, workflow)
        return clone

    @staticmethod
    def _unique_function_name(raw_name: str | None, functions: list, exclude_function_id: str | None = None) -> str:
        base = str(raw_name or '新建函数').strip()[:64] or '新建函数'
        used = {
            str(item.get('name') or '').strip()
            for item in functions
            if item.get('function_id') != exclude_function_id
        }
        if base not in used:
            return base
        suffix = 1
        while f'{base[:max(1, 64 - len(str(suffix)))]}{suffix}' in used:
            suffix += 1
        return f'{base[:max(1, 64 - len(str(suffix)))]}{suffix}'

    # ============ 内部工具 ============

    @staticmethod
    def _validate_document(filename: str, data: dict):
        try:
            validate_document(filename, data)
        except ProjectFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def _validate_task_name(task: dict, tasks: list, exclude_task_id: str | None = None):
        name = str(task.get('task_name') or '').strip()
        if not name:
            raise HTTPException(status_code=400, detail='流程名称不能为空')
        if len(name) > 64:
            raise HTTPException(status_code=400, detail='流程名称不能超过 64 个字符')
        for existing in tasks:
            if existing.get('task_id') == exclude_task_id:
                continue
            if str(existing.get('task_name') or '').strip() == name:
                raise HTTPException(status_code=400, detail='流程名称已存在')

    @staticmethod
    def _unique_task_name(task: dict, tasks: list, exclude_task_id: str | None = None) -> str:
        """Return a valid, unique task name without turning a routine UI action into a save failure."""
        raw = str(task.get('task_name') or '').strip() or '新建流程'
        base = raw[:64]
        used = {
            str(existing.get('task_name') or '').strip()
            for existing in tasks
            if existing.get('task_id') != exclude_task_id
        }
        if base not in used:
            return base
        suffix = 1
        while True:
            suffix_text = str(suffix)
            candidate = f'{base[:max(1, 64 - len(suffix_text))]}{suffix_text}'
            if candidate not in used:
                return candidate
            suffix += 1

    @classmethod
    def _validate_tasks(cls, tasks):
        if not isinstance(tasks, list):
            raise HTTPException(status_code=400, detail='tasks 必须是数组')
        seen_ids = set()
        seen_names = set()
        for task in tasks:
            if not isinstance(task, dict):
                raise HTTPException(status_code=400, detail='流程数据必须是对象')
            task_id = str(task.get('task_id') or '').strip()
            if not task_id or task_id in seen_ids:
                raise HTTPException(status_code=400, detail=f'流程 ID 缺失或重复: {task_id}')
            seen_ids.add(task_id)
            name = str(task.get('task_name') or '').strip()
            if not name or len(name) > 64:
                raise HTTPException(status_code=400, detail=f'流程名称必须为 1-64 个字符: {name}')
            if name in seen_names:
                raise HTTPException(status_code=400, detail=f'流程名称重复: {name}')
            seen_names.add(name)

    @staticmethod
    def _capture_snapshot(project_path: str, reason: str):
        try:
            from core.services.snapshot_service import SnapshotService

            SnapshotService.capture_current(project_path, reason)
        except Exception as exc:
            # 快照失败不能破坏主保存链路，但会明确记录，前端发布前检查仍可提示。
            logger.warning(f'版本快照创建失败 [{project_path}]: {exc}')

    @staticmethod
    def _safe_write(file_path: str, data: dict):
        """原子写入 + 序列化失败兜底"""
        try:
            _atomic_write_json(file_path, data)
        except TypeError as e:
            # 序列化类型错误：尝试用 default=str 兜底
            logger.warning(f'序列化遇到类型问题，使用 default=str 兜底: {e}')
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            except Exception as e2:
                logger.error(f'保存失败(兜底) [{file_path}]: {e2}')
                raise HTTPException(status_code=500, detail=f'保存失败: {str(e2)}') from e2
        except Exception as e:
            logger.error(f'保存失败 [{file_path}]: {e}')
            raise HTTPException(status_code=500, detail=f'保存失败: {str(e)}') from e

    @staticmethod
    def _sanitize_for_json(obj):
        """
        递归清理不可 JSON 序列化的字段
        防止 numpy int64/float64、datetime 等类型导致 json.dump 失败
        修复：保留 None 值（之前 v is not None 过滤会丢失合法的 null 字段）
        修复：只过滤以 _ 开头的内部字段
        """
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.startswith('_'):
                    continue
                result[k] = BlueprintService._sanitize_for_json(v)
            return result
        elif isinstance(obj, list):
            return [BlueprintService._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            # 不可序列化的对象转为字符串
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)
