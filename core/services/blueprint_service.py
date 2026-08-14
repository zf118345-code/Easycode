# core/services/blueprint_service.py
# 蓝图三文件存储服务
#   - project.json  : project_name / variables / ui_state
#   - workflow.json : { tasks, edges }（流程画布）
#   - topology.json : { tasks, edges }（拓扑地图）
# 所有公开方法入口先执行旧版单文件 project_blueprint.json 的懒迁移（core.services.migration）

import json
import logging
import os
import tempfile
import time

from fastapi import HTTPException

from core.schemas import SaveTaskRequestSchema
from core.services.migration import PROJECT_FILE, TOPOLOGY_FILE, WORKFLOW_FILE, convert_topology_dict, ensure_migrated

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


def _load_json_file(file_path: str, default: dict) -> dict:
    """读取 JSON 文件，文件缺失/损坏时返回默认结构（不崩溃）"""
    try:
        with open(file_path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f'JSON 解析失败 [{file_path}]: {e}')
        result = dict(default)
        result['_error'] = f'文件解析失败: {e}'
        return result
    except FileNotFoundError:
        return dict(default)
    except Exception as e:
        logger.error(f'文件加载失败 [{file_path}]: {e}')
        raise HTTPException(status_code=500, detail=f'文件加载失败: {str(e)}') from e
    if not isinstance(data, dict):
        logger.warning(f'文件内容非 dict [{file_path}]，返回默认结构')
        return dict(default)
    return data


class BlueprintService:
    @classmethod
    def _prepare(cls, project_path: str) -> str:
        """所有读写入口：校验项目路径 + 懒迁移旧蓝图"""
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f'项目路径不存在: {project_path}')
        ensure_migrated(project_path)
        return project_path

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
        cls._prepare(project_path)
        data = _load_json_file(
            cls.get_blueprint_path(project_path),
            {'project_name': os.path.basename(project_path), 'variables': {}, 'ui_state': {}},
        )
        data.setdefault('project_name', os.path.basename(project_path))
        if not isinstance(data.get('variables'), dict):
            data['variables'] = {}
        if not isinstance(data.get('ui_state'), dict):
            data['ui_state'] = {}
        return data

    @classmethod
    def save_project_meta(cls, project_path: str, data: dict):
        cls._prepare(project_path)
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail='项目数据必须是字典类型')
        clean = cls._sanitize_for_json(data)
        project_data = {
            'project_name': clean.get('project_name', os.path.basename(project_path)),
            'variables': clean.get('variables', {}),
            'ui_state': clean.get('ui_state', {}),
        }
        cls._safe_write(cls.get_blueprint_path(project_path), project_data)

    # ============ workflow.json（流程画布） ============

    @classmethod
    def load_workflow(cls, project_path: str) -> dict:
        cls._prepare(project_path)
        data = _load_json_file(cls.get_workflow_path(project_path), {'tasks': [], 'edges': []})
        if not isinstance(data.get('tasks'), list):
            data['tasks'] = []
        if not isinstance(data.get('edges'), list):
            data['edges'] = []
        return data

    @classmethod
    def save_workflow(cls, project_path: str, data: dict):
        cls._prepare(project_path)
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail='流程画布数据必须是字典类型')
        clean = cls._sanitize_for_json(data)
        workflow_data = {
            'tasks': clean.get('tasks', []),
            'edges': clean.get('edges', []),
        }
        cls._safe_write(cls.get_workflow_path(project_path), workflow_data)

    # ============ topology.json（拓扑地图） ============

    @classmethod
    def load_topology(cls, project_path: str) -> dict:
        cls._prepare(project_path)
        data = _load_json_file(cls.get_topology_path(project_path), {'tasks': [], 'edges': []})
        if not isinstance(data.get('tasks'), list):
            data['tasks'] = []
        if not isinstance(data.get('edges'), list):
            data['edges'] = []
        return data

    @classmethod
    def save_topology(cls, project_path: str, data: dict):
        cls._prepare(project_path)
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail='拓扑地图数据必须是字典类型')
        clean = cls._sanitize_for_json(data)
        # 兼容旧版 {nodes, edges} 形态，统一转换为任务组结构
        topology_data = convert_topology_dict(clean)
        cls._safe_write(cls.get_topology_path(project_path), topology_data)

    # ============ 合并视图（快照/导出/执行用） ============

    @classmethod
    def load_blueprint(cls, project_path: str) -> dict:
        """加载合并蓝图视图（保留旧语义，供快照/导出/执行消费）"""
        cls._prepare(project_path)
        meta = cls.load_project_meta(project_path)
        workflow = cls.load_workflow(project_path)
        topology = cls.load_topology(project_path)
        return {
            'project_name': meta.get('project_name', os.path.basename(project_path)),
            'tasks': workflow.get('tasks', []),
            'variables': meta.get('variables', {}),
            'edges': workflow.get('edges', []),
            'topology': topology,
            'ui_state': meta.get('ui_state', {}),
        }

    @classmethod
    def save_blueprint(cls, project_path: str, data: dict):
        """
        保存合并蓝图：拆分写入三个文件
        兼容只含部分字段的 payload（如执行前保存、快照恢复、旧前端整包保存）
        """
        cls._prepare(project_path)
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail='蓝图数据必须是字典类型')
        clean = cls._sanitize_for_json(data)
        cls.save_project_meta(project_path, clean)
        if 'tasks' in clean or 'edges' in clean:
            cls.save_workflow(project_path, clean)
        if 'topology' in clean:
            cls.save_topology(project_path, clean['topology'])

    # ============ 任务 CRUD（操作 workflow.json） ============

    @classmethod
    def list_tasks(cls, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        task_list = [
            {
                'task_id': task.get('task_id'),
                'task_name': task.get('task_name'),
                'node_count': len(task.get('nodes', [])),
            }
            for task in workflow.get('tasks', [])
        ]
        order = [t['task_id'] for t in task_list]
        return {'tasks': task_list, 'order': order}

    @classmethod
    def get_task(cls, task_id: str, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        for task in workflow.get('tasks', []):
            if task.get('task_id') == task_id:
                return task
        raise HTTPException(status_code=404, detail=f'任务不存在: {task_id}')

    @classmethod
    def save_task(cls, task_id: str, request: SaveTaskRequestSchema) -> dict:
        workflow = cls.load_workflow(request.project_path)
        tasks = workflow.setdefault('tasks', [])
        task_dict = (
            request.task_data.model_dump() if hasattr(request.task_data, 'model_dump') else dict(request.task_data)
        )

        task_dict['task_id'] = task_id
        if 'task_name' not in task_dict or not task_dict['task_name']:
            task_dict['task_name'] = task_id

        found = False
        for i, t in enumerate(tasks):
            if t.get('task_id') == task_id:
                tasks[i] = task_dict
                found = True
                break
        if not found:
            tasks.append(task_dict)

        cls.save_workflow(request.project_path, workflow)
        return {'status': 'success'}

    @classmethod
    def create_task(cls, request: SaveTaskRequestSchema) -> dict:
        workflow = cls.load_workflow(request.project_path)
        tasks = workflow.setdefault('tasks', [])
        task_dict = (
            request.task_data.model_dump() if hasattr(request.task_data, 'model_dump') else dict(request.task_data)
        )
        task_name = task_dict.get('task_name', '新任务组')

        if any(t.get('task_name') == task_name for t in tasks):
            raise HTTPException(status_code=400, detail='任务名称已存在')

        task_id = f'task_{int(time.time() * 1000)}'
        task_dict['task_id'] = task_id
        task_dict['task_name'] = task_name
        if 'nodes' not in task_dict:
            task_dict['nodes'] = []

        tasks.append(task_dict)
        cls.save_workflow(request.project_path, workflow)
        return {'status': 'success', 'task_id': task_id}

    @classmethod
    def delete_task(cls, task_id: str, project_path: str) -> dict:
        workflow = cls.load_workflow(project_path)
        tasks = workflow.get('tasks', [])

        new_tasks = [t for t in tasks if t.get('task_id') != task_id]
        if len(new_tasks) == len(tasks):
            raise HTTPException(status_code=404, detail='任务不存在')

        workflow['tasks'] = new_tasks
        cls.save_workflow(project_path, workflow)
        return {'status': 'success'}

    # ============ 内部工具 ============

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
