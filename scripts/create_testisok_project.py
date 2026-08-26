"""Create the user-authorized strict-v3 acceptance project ``testisok``."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if os.fspath(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(PROJECT_ROOT))

from core.project_schema import new_project_documents
from core.security import atomic_write_json
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService


def node(node_id: str, name: str, kind: str, params: dict, x: int, y: int, **extra) -> dict:
    value = {
        'node_id': node_id, 'node_name': name, 'node_type': kind, 'params': params,
        'position': {'x': x, 'y': y}, 'delay_before': 0, 'loop_count': 1, 'enabled': True,
    }
    value.update(extra)
    return value


def edge(edge_id: str, source: str, target: str, port: str = 'success', stable_id: str = 'success') -> dict:
    return {
        'edge_id': edge_id, 'source_node': source, 'target_node': target,
        'source_port': port, 'source_port_id': stable_id,
    }


def _existing_project_id(target: Path) -> str | None:
    try:
        value = json.loads((target / 'project.json').read_text(encoding='utf-8')).get('project_id')
        return value if str(value).startswith('project_') else None
    except Exception:
        return None


def _write_recording(target: Path, template: Image.Image) -> str:
    session_id = 'frame_recording_testisok_offline'
    session = target / 'recordings' / session_id
    session.mkdir(parents=True, exist_ok=True)
    records = []
    for index, show_target in ((1, False), (2, True), (3, True)):
        frame = Image.new('RGB', (640, 360), '#10151f')
        draw = ImageDraw.Draw(frame)
        draw.rectangle((0, 0, 639, 42), fill='#202a3b')
        if show_target:
            frame.paste(template, (180, 100))
        frame_path = session / f'frame_{index:08d}_{index}.png'
        frame.save(frame_path, format='PNG', compress_level=1)
        records.append({
            'index': index, 'capture_index': index, 'file': frame_path.name,
            'captured_at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            'timestamp_ns': index, 'width': 640, 'height': 360,
            'bytes': frame_path.stat().st_size, 'screen_region': [0, 0, 640, 360],
            'change_score': 1.0 if index < 3 else 0.0,
            'sha256': hashlib.sha256(frame_path.read_bytes()).hexdigest(),
            **({'event': {'type': 'manual', 'label': '开售画面出现'}} if index == 2 else {}),
        })
    (session / 'frames.jsonl').write_text(
        ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in records), encoding='utf-8',
    )
    atomic_write_json(os.fspath(session / 'session.json'), {
        'schema_version': 2, 'session_id': session_id,
        'started_at': records[0]['captured_at'], 'stopped_at': records[-1]['captured_at'],
        'status': 'stopped', 'target_title': 'testisok 离线测试窗口',
        'capture_backend': 'synthetic_test_fixture', 'frame_count': len(records),
        'workspace_size': [640, 360], 'screen_region': [0, 0, 640, 360],
        'event_count': 1, 'final': True,
    })
    return session_id


def create(target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    documents = new_project_documents('testisok', _existing_project_id(target))
    documents['form_schema.json'].update({
        'form_title': 'testisok Player 验收',
        'entry': {
            'task_id': 'main',
            'node_id': 'main_log_start',
            'node_name': '开始日志',
        },
    })
    for filename, value in documents.items():
        atomic_write_json(os.fspath(target / filename), value)
    AssetService.ensure_structure(os.fspath(target))

    template_path = target / 'templates' / 'page' / 'offline-sale-button.png'
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template = Image.new('RGB', (76, 34), '#172238')
    draw = ImageDraw.Draw(template)
    draw.rounded_rectangle((1, 1, 74, 32), radius=7, fill='#35c88a', outline='#e8fff6', width=2)
    draw.rectangle((15, 10, 60, 23), fill='#0c4c35')
    draw.line((20, 16, 55, 16), fill='#ffffff', width=3)
    template.save(template_path, format='PNG')
    asset = AssetService.register_file(
        os.fspath(target), 'page/offline-sale-button.png', 'page',
        capture={'region': [180, 100, 76, 34], 'reference_size': [640, 360], 'coordinate_space': 'workspace_px'},
    )
    reference = AssetService.reference(asset['id'])

    meta = BlueprintService.load_project_meta(os.fspath(target))
    meta['variables'] = {'run_count': 0}
    meta['settings'] = {'allow_physical_fallback': False}
    BlueprintService.save_project_meta(os.fspath(target), meta, create_snapshot=False)

    success_outcome = 'outcome_increment_success'
    function_id = 'function_increment'
    workflow = {
        'main_graph': {
            'graph_id': 'main',
            'nodes': [
                node('main_log_start', '开始日志', 'log', {'message': 'testisok v3 开始'}, 80, 100),
                node('main_call_increment', '调用计数函数', 'call_function', {
                    'function_id': function_id,
                    'input_bindings': [{'parameter_id': 'parameter_start', 'value': '40'}],
                    'output_bindings': [{'output_id': 'output_result', 'target': '$var{run_count}'}],
                }, 320, 100),
                node('main_log_end', '完成日志', 'log', {'message': 'testisok v3 完成'}, 580, 100),
            ],
            'edges': [
                edge('main_edge_start_call', 'main_log_start', 'main_call_increment'),
                edge('main_edge_call_end', 'main_call_increment', 'main_log_end', 'outcome_0', success_outcome),
            ],
        },
        'functions': [{
            'function_id': function_id, 'name': '计数加一',
            'description': '验证形参、局部变量、返回值和稳定结果出口。', 'folder_id': None,
            'parameters': [{
                'parameter_id': 'parameter_start', 'name': 'start', 'type': 'number',
                'required': True, 'default_value': 0,
            }],
            'local_variables': [{
                'local_id': 'local_result', 'name': 'result', 'type': 'number', 'default_value': 0,
            }],
            'outputs': [{'output_id': 'output_result', 'name': 'result', 'type': 'number'}],
            'outcomes': [
                {'outcome_id': success_outcome, 'name': '成功', 'color': 'success'},
                {'outcome_id': 'system_exception', 'name': '异常', 'color': 'danger', 'system': True, 'immutable': True},
            ],
            'test_cases': [{
                'test_id': 'test_increment_41', 'name': '40 加一',
                'inputs': {'parameter_start': 40}, 'expected_outcome_id': success_outcome,
            }],
            'graph': {
                'graph_id': function_id, 'entry_node_id': 'function_increment_entry',
                'nodes': [
                    node('function_increment_entry', '函数入口', 'function_entry', {}, 80, 120, fixed=True),
                    node('function_increment_calculate', '计算结果', 'variable_op', {
                        'target_var': '$local.result', 'new_value': '$param.start + 1',
                    }, 320, 120),
                    node('function_increment_return', '返回成功', 'function_return', {
                        'outcome_id': success_outcome,
                        'output_bindings': [{'output_id': 'output_result', 'value': '$local.result'}],
                    }, 580, 120),
                ],
                'edges': [
                    edge('function_edge_entry_calculate', 'function_increment_entry', 'function_increment_calculate'),
                    edge('function_edge_calculate_return', 'function_increment_calculate', 'function_increment_return'),
                ],
            },
        }],
        'function_folders': [],
    }
    BlueprintService.save_workflow(os.fspath(target), workflow, create_snapshot=False)

    topology = {
        'nodes': [node('page_sale', '开售页面', 'page_state', {
            'page_id': 'page_offline_sale', 'feature_mode': 'and',
            'features': [{
                'condition_type': 'image_exists', 'image_source': reference,
                'threshold': 0.95, 'region_type': 'recorded',
            }],
        }, 100, 100)],
        'edges': [],
    }
    BlueprintService.save_topology(os.fspath(target), topology, create_snapshot=False)
    session_id = _write_recording(target, template)
    return {
        'project_path': os.fspath(target), 'schema_version': 3,
        'asset': reference, 'recording_session_id': session_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=r'D:\PycharmProjects\testisok')
    args = parser.parse_args()
    print(json.dumps(create(Path(args.path).resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
