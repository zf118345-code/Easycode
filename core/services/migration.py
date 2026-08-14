# core/services/migration.py
# 蓝图存储懒迁移：把旧版单文件 project_blueprint.json 拆分为三个新文件
#   - project.json  : project_name / variables / ui_state
#   - workflow.json : { tasks, edges }
#   - topology.json : { tasks, edges }（拓扑任务组化：节点折叠进 params，连线统一 source_node/target_node）
# 迁移幂等：完成后旧文件 rename 为 .bak，不再被读取；模块级锁防止并发迁移。

import json
import logging
import os
import tempfile
import threading
from typing import Any

logger = logging.getLogger(__name__)

LEGACY_BLUEPRINT_FILE = 'project_blueprint.json'
PROJECT_FILE = 'project.json'
WORKFLOW_FILE = 'workflow.json'
TOPOLOGY_FILE = 'topology.json'

_LEGACY_NODE_FIELDS = ('on_success', 'on_failure', 'positions', 'canvas_ids')

_migration_lock = threading.Lock()


def _atomic_write_json(file_path: str, data: dict):
    """原子写入 JSON（内联实现，先写临时文件再 os.replace，避免中途崩溃损坏文件）"""
    dir_path = os.path.dirname(os.path.abspath(file_path))
    fd, tmp_path = tempfile.mkstemp(suffix='.tmp', prefix='migrate_', dir=dir_path)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, file_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _clean_node_fields(node: dict) -> dict:
    """移除节点上已废弃的模型字段（顶层 on_success/on_failure/positions/canvas_ids）"""
    if not isinstance(node, dict):
        return node
    for key in _LEGACY_NODE_FIELDS:
        node.pop(key, None)
    return node


def _fold_topology_node(node: dict) -> dict:
    """旧版扁平拓扑节点 -> 新节点形状：type→node_type，页面数据折叠进 params（原 params 值优先）"""
    converted = {k: v for k, v in node.items() if k not in ('type', 'page_id', 'features', 'feature_mode', 'exits')}
    params = dict(node.get('params') or {})
    for key, default in (('page_id', ''), ('features', []), ('feature_mode', 'and'), ('exits', [])):
        if key not in params:
            params[key] = node.get(key, default)
    converted['params'] = params
    converted['node_type'] = node.get('node_type') or node.get('type') or 'page_state'
    converted.setdefault('enabled', True)
    return _clean_node_fields(converted)


def _convert_topology_edge(edge: dict) -> dict:
    """旧版拓扑连线 -> 新键名：source/target/source_page/target_page → source_node/target_node"""
    converted = {k: v for k, v in edge.items() if k not in ('source', 'target', 'source_page', 'target_page')}
    converted['source_node'] = edge.get('source_node') or edge.get('source') or edge.get('source_page') or ''
    converted['target_node'] = edge.get('target_node') or edge.get('target') or edge.get('target_page') or ''
    converted['canvas'] = 'topology'
    return converted


def convert_topology_dict(topo: dict[str, Any]) -> dict[str, Any]:
    """把任意形态的拓扑数据转换为任务组结构 {tasks, edges}"""
    if not isinstance(topo, dict):
        topo = {}
    if isinstance(topo.get('tasks'), list):
        tasks_out = []
        for task in topo['tasks']:
            if not isinstance(task, dict):
                continue
            task = dict(task)
            task['nodes'] = [_clean_node_fields(_fold_topology_node(n)) for n in task.get('nodes', []) if isinstance(n, dict)]
            tasks_out.append(task)
    else:
        nodes = [_fold_topology_node(n) for n in topo.get('nodes', []) if isinstance(n, dict)]
        tasks_out = []
        if nodes:
            tasks_out = [
                {
                    'task_id': 'task_topology',
                    'task_name': '拓扑地图',
                    'loop_count': 1,
                    'loop_interval': 0,
                    'nodes': nodes,
                }
            ]
    edges_out = [_convert_topology_edge(e) for e in topo.get('edges', []) if isinstance(e, dict)]
    return {'tasks': tasks_out, 'edges': edges_out}


def _write_json_graceful(file_path: str, data: dict):
    try:
        _atomic_write_json(file_path, data)
    except Exception as e:
        logger.error(f'迁移写入失败 [{file_path}]: {e}')
        raise


def _migrate_locked(project_path: str) -> bool:
    legacy_path = os.path.join(project_path, LEGACY_BLUEPRINT_FILE)
    if not os.path.isfile(legacy_path):
        return False

    try:
        with open(legacy_path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f'旧蓝图解析失败，跳过迁移（保留原文件） [{legacy_path}]: {e}')
        return False
    if not isinstance(data, dict):
        logger.error(f'旧蓝图内容非 dict，跳过迁移（保留原文件） [{legacy_path}]')
        return False

    logger.info(f'开始迁移旧蓝图: {legacy_path}')

    # 1) project.json：项目元数据
    variables = data.get('variables', {})
    ui_state = data.get('ui_state', {})
    project_data = {
        'project_name': data.get('project_name', os.path.basename(project_path)),
        'variables': variables if isinstance(variables, dict) else {},
        'ui_state': ui_state if isinstance(ui_state, dict) else {},
    }

    # 2) workflow.json：流程画布（旧版顶层 nodes 无 tasks 时包成 task_main）
    tasks = data.get('tasks', [])
    if not isinstance(tasks, list):
        tasks = []
    if not tasks and isinstance(data.get('nodes'), list):
        tasks = [
            {
                'task_id': 'task_main',
                'task_name': data.get('project_name', '主任务组'),
                'loop_count': 1,
                'loop_interval': 0,
                'nodes': data.get('nodes', []),
            }
        ]
    for task in tasks:
        if isinstance(task, dict):
            task['nodes'] = [_clean_node_fields(n) for n in task.get('nodes', []) if isinstance(n, dict)]
    edges = data.get('edges', [])
    workflow_data = {'tasks': tasks, 'edges': edges if isinstance(edges, list) else []}

    # 3) topology.json：拓扑地图任务组化
    topology_data = convert_topology_dict(data.get('topology', {}))

    # 4) 备份旧蓝图（rename 即"备份为 .bak 且旧文件不再读取"）
    bak_path = legacy_path + '.bak'
    try:
        os.replace(legacy_path, bak_path)
        logger.info(f'旧蓝图已备份为: {bak_path}')
    except Exception as e:
        logger.error(f'备份旧蓝图失败，中止迁移 [{legacy_path}]: {e}')
        return False

    # 5) 旧格式 project.json（含 tasks/topology/nodes）先备份再覆盖
    old_project_path = os.path.join(project_path, PROJECT_FILE)
    if os.path.isfile(old_project_path):
        try:
            with open(old_project_path, encoding='utf-8-sig') as f:
                old_project = json.load(f)
            if isinstance(old_project, dict) and any(k in old_project for k in ('tasks', 'topology', 'nodes')):
                os.replace(old_project_path, old_project_path + '.bak')
                logger.info(f'旧格式 project.json 已备份为: {old_project_path}.bak')
        except Exception as e:
            logger.warning(f'检查/备份旧 project.json 失败（继续迁移）: {e}')

    # 6) 写入三个新文件
    _write_json_graceful(os.path.join(project_path, PROJECT_FILE), project_data)
    _write_json_graceful(os.path.join(project_path, WORKFLOW_FILE), workflow_data)
    _write_json_graceful(os.path.join(project_path, TOPOLOGY_FILE), topology_data)

    logger.info(f'迁移完成: {project_path}（project.json / workflow.json / topology.json）')
    return True


def ensure_migrated(project_path: str) -> bool:
    """按需迁移：project_blueprint.json 存在时拆分写三文件并备份旧文件；幂等，并发安全"""
    if not project_path or not os.path.isdir(project_path):
        return False
    with _migration_lock:
        return _migrate_locked(project_path)
