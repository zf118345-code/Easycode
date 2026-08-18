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


def _migrate_workflow_edges_locked(project_path: str) -> bool:
    """
    workflow 边实体化迁移：把寄生在节点 params 里的连线（on_success / on_failure /
    candidates[i].on_success）提取为 workflow.json 顶层 edges 实体数组（与 topology.json 同构）。
    幂等：_migrated_edges 标记存在或该端口已有实体边时跳过；迁移前备份一次 workflow.json.bak。
    """
    wf_path = os.path.join(project_path, WORKFLOW_FILE)
    if not os.path.isfile(wf_path):
        return False
    try:
        with open(wf_path, encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f'workflow 边迁移：读取失败，跳过 [{wf_path}]: {e}')
        return False
    if not isinstance(data, dict) or data.get('_migrated_edges'):
        return False

    tasks = data.get('tasks', [])
    edges = data.get('edges', [])
    if not isinstance(edges, list):
        edges = []
    # 已有实体边集合（source, source_port），幂等去重
    existing = {(e.get('source_node'), e.get('source_port')) for e in edges if isinstance(e, dict)}

    def _jump_fields(jump: Any) -> dict | None:
        """从 Jump dict 提取 target_node/target_task/return_on_complete；无效连线返回 None"""
        if not isinstance(jump, dict):
            return None
        target_node = jump.get('target_node')
        target_task = jump.get('target_task') or jump.get('target')
        if not target_node and not target_task:
            return None
        return {
            'target_node': target_node,
            'target_task': target_task,
            'return_on_complete': bool(jump.get('return_on_complete', False)),
        }

    def _append_edge(source_node: str, port: str, fields: dict, cand_index: int | None = None) -> None:
        key = (source_node, port)
        if key in existing or not fields or not fields['target_node']:
            return
        existing.add(key)
        edge = {
            'edge_id': f'e_{source_node}_{port}_{fields["target_node"]}',
            'source_node': source_node,
            'target_node': fields['target_node'],
            'source_port': port,
            'return_on_complete': fields['return_on_complete'],
            'canvas': 'workflow',
        }
        if fields['target_task']:
            edge['target_task'] = fields['target_task']
        edges.append(edge)

    changed = False
    for task in tasks:
        if not isinstance(task, dict):
            continue
        for node in task.get('nodes', []):
            if not isinstance(node, dict):
                continue
            params = node.get('params')
            if not isinstance(params, dict):
                continue

            on_success = _jump_fields(params.get('on_success'))
            if on_success:
                _append_edge(node.get('node_id', ''), 'success', on_success)
                params.pop('on_success', None)
                changed = True

            on_failure = _jump_fields(params.get('on_failure'))
            if on_failure:
                _append_edge(node.get('node_id', ''), 'failure', on_failure)
                params.pop('on_failure', None)
                changed = True

            candidates = params.get('candidates')
            if isinstance(candidates, list):
                for cidx, candidate in enumerate(candidates):
                    if isinstance(candidate, dict):
                        cand_jump = _jump_fields(candidate.get('on_success'))
                        if cand_jump:
                            _append_edge(node.get('node_id', ''), f'branch_{cidx}', cand_jump, cidx)
                            candidate.pop('on_success', None)
                            changed = True

    if not changed and not edges:
        # 无任何可迁移内容，也落标记避免每次扫描
        data['_migrated_edges'] = True
        changed = True

    if changed:
        data['_migrated_edges'] = True
        bak_path = wf_path + '.bak'
        try:
            if not os.path.isfile(bak_path):
                import shutil
                shutil.copy2(wf_path, bak_path)
        except Exception as e:
            logger.warning(f'workflow 边迁移备份失败（继续迁移）: {e}')
        try:
            _write_json_graceful(wf_path, data)
            logger.info(f'workflow 边实体化完成: {wf_path}（{len(edges)} 条实体边）')
            return True
        except Exception as e:
            logger.error(f'workflow 边迁移写入失败: {e}')
            return False
    return False


def _migrate_topology_modern_locked(project_path: str) -> bool:
    """
    新版拓扑语义迁移（幂等，按内容判定；无变化时不写盘）：
      1. page_state：page_name → node_name（标题即页面名）
      2. features 展平：{feature_type, params{...}} → {condition_type, ...平铺字段}（条件列表编辑器结构）
      3. exits 参数 → 拓扑边（有可解析目标页才建边；动作/条件挂到边上）
      4. 移除 page_state 的 page_name/exits 参数
      5. 清理 branch / page_state 的旧 success/failure 边（新模式以候选口/出口口表达）
    """
    topo_path = os.path.join(project_path, TOPOLOGY_FILE)
    wf_path = os.path.join(project_path, WORKFLOW_FILE)
    if not os.path.isfile(topo_path):
        return False

    try:
        with open(topo_path, encoding='utf-8-sig') as f:
            raw_topo = json.load(f)
    except Exception as e:
        logger.error(f'拓扑现代化迁移：读取失败，跳过 [{topo_path}]: {e}')
        return False
    if not isinstance(raw_topo, dict):
        return False

    topo = convert_topology_dict(raw_topo)
    tasks = topo.get('tasks', [])
    edges = topo.get('edges', [])
    if not isinstance(edges, list):
        edges = []
    changed = False

    # 页面键映射：page_id / node_id → node_id（exits 的 target_page_id 解析用）
    page_map: dict[str, str] = {}
    for task in tasks:
        for node in task.get('nodes', []):
            if not isinstance(node, dict):
                continue
            pid = (node.get('params') or {}).get('page_id')
            nid = node.get('node_id', '')
            if pid:
                page_map[pid] = nid
            if nid:
                page_map.setdefault(nid, nid)

    existing_ports = {
        (e.get('source_node'), e.get('source_port')) for e in edges if isinstance(e, dict)
    }

    for task in tasks:
        nodes = task.get('nodes', [])
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict) or node.get('node_type') != 'page_state':
                continue
            params = node.get('params')
            if not isinstance(params, dict):
                continue

            # 1) page_name → node_name
            page_name = params.pop('page_name', None)
            if page_name:
                node_name = node.get('node_name') or ''
                if not node_name or node_name.startswith('页面状态') or node_name == '未命名':
                    node['node_name'] = page_name
                    changed = True

            # 2) features 展平
            features = params.get('features')
            if isinstance(features, list) and any(
                isinstance(f, dict) and (f.get('feature_type') or f.get('type')) for f in features
            ):
                flat = [_flatten_feature(f) for f in features]
                flat = [f for f in flat if f is not None]
                params['features'] = flat
                changed = True

            # 2.1) 组合方式归一化：'and' 是旧 schema 的默认自动值（非用户显式选择），
            #      清空后跟随全局 feature_mode —— 修复「全局 or 被逐条 and 覆盖」问题；
            #      显式 'or'（覆盖全局）保留不动。
            for f in params.get('features', []):
                if isinstance(f, dict) and f.get('combine_mode') == 'and':
                    f.pop('combine_mode', None)
                    changed = True

            # 3) exits → 拓扑边
            exits = params.pop('exits', None)
            if isinstance(exits, list) and exits:
                for i, ex in enumerate(exits):
                    if not isinstance(ex, dict):
                        continue
                    target_key = ex.get('target_page_id') or ex.get('target_node') or ''
                    target_node = page_map.get(target_key)
                    if not target_node or target_node == node.get('node_id'):
                        continue
                    port = f'exit_{i}'
                    if (node.get('node_id'), port) in existing_ports:
                        continue
                    existing_ports.add((node.get('node_id'), port))
                    edge = {
                        'edge_id': f'e_{node.get("node_id")}_{port}_{target_node}',
                        'source_node': node.get('node_id'),
                        'target_node': target_node,
                        'source_port': port,
                        'canvas': 'topology',
                    }
                    action = ex.get('exit_action')
                    if action:
                        edge['label'] = action
                    conds = ex.get('transition_conditions')
                    if conds:
                        edge['conditions'] = conds
                    edges.append(edge)
                    changed = True

    # 4) 清理 branch / page_state 旧 success/failure 边（拓扑 + workflow 两文件）
    for file_path, file_edges in ((topo_path, edges), (wf_path, None)):
        data = None
        if file_edges is None:
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, encoding='utf-8-sig') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f'边清理迁移：读取失败，跳过 [{file_path}]: {e}')
                continue
            if not isinstance(data, dict):
                continue
            file_edges = data.get('edges', [])
            if not isinstance(file_edges, list):
                continue
            node_types = {}
            for task in data.get('tasks', []):
                for n in task.get('nodes', []):
                    if isinstance(n, dict):
                        node_types[n.get('node_id', '')] = n.get('node_type', '')
        else:
            node_types = {}
            for task in tasks:
                for n in task.get('nodes', []):
                    if isinstance(n, dict):
                        node_types[n.get('node_id', '')] = n.get('node_type', '')

        keep = []
        for e in file_edges:
            if not isinstance(e, dict):
                keep.append(e)
                continue
            src_type = node_types.get(e.get('source_node', ''), '')
            port = e.get('source_port', '')
            if src_type in ('branch', 'page_state') and port in ('success', 'failure'):
                changed = True
                continue
            keep.append(e)
        if len(keep) != len(file_edges):
            if data is not None:
                data['edges'] = keep
                _write_json_graceful(file_path, data)
            else:
                edges = keep

    if changed:
        topo['edges'] = edges
        _write_json_graceful(topo_path, topo)
        logger.info(f'拓扑现代化迁移完成: {project_path}')
        return True
    return False


def _flatten_feature(feature: dict) -> dict | None:
    """旧特征结构 → 新条件结构（condition_type + 平铺字段），无法识别的特征返回 None"""
    if not isinstance(feature, dict):
        return None
    ftype = feature.get('feature_type') or feature.get('type') or feature.get('condition_type') or ''
    params = feature.get('params')
    if not isinstance(params, dict):
        params = {}
    out: dict[str, Any] = {'condition_type': ftype}

    image_source = params.get('image_source') or params.get('template') or feature.get('template')
    if image_source:
        out['image_source'] = image_source
    target_text = params.get('target_text') or params.get('text') or feature.get('text')
    if target_text:
        out['target_text'] = target_text
    threshold = params.get('threshold')
    if threshold is None:
        threshold = feature.get('threshold')
    if threshold is not None:
        out['threshold'] = threshold
    region = params.get('region_value') or params.get('region') or feature.get('region')
    if region:
        rtype, rval = _parse_feature_region(region)
        out['region_type'] = rtype
        out['region_value'] = rval
    for key in ('combine_mode', 'negate'):
        if key in feature:
            out[key] = feature[key]

    if not out.get('image_source') and not out.get('target_text'):
        return None
    return out


def _parse_feature_region(region: Any) -> tuple[str, list[int]]:
    """旧特征 region（数组 / "x,y,w,h" 字符串）→ (region_type, region_value)；空值回退全屏"""
    if isinstance(region, (list, tuple)) and len(region) >= 4:
        try:
            return 'custom', [int(x) for x in region[:4]]
        except (ValueError, TypeError):
            pass
    if isinstance(region, str):
        parts = [p.strip() for p in region.replace('，', ',').split(',')]
        if len(parts) >= 4:
            try:
                return 'custom', [int(float(p)) for p in parts[:4]]
            except ValueError:
                pass
    return 'fullwindow', [0, 0, 0, 0]


def ensure_migrated(project_path: str) -> bool:
    """按需迁移：旧蓝图拆分三文件 + workflow 边实体化 + 拓扑现代化；幂等，并发安全"""
    if not project_path or not os.path.isdir(project_path):
        return False
    with _migration_lock:
        migrated = _migrate_locked(project_path)
        _migrate_workflow_edges_locked(project_path)
        _migrate_topology_modern_locked(project_path)
        return migrated
