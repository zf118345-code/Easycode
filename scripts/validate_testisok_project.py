"""Low-load service validation for the external strict-v3 ``testisok`` project."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if os.fspath(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(PROJECT_ROOT))
PROJECT_SITE_PACKAGES = PROJECT_ROOT / '.venv' / 'Lib' / 'site-packages'
if PROJECT_SITE_PACKAGES.is_dir() and os.fspath(PROJECT_SITE_PACKAGES) not in sys.path:
    sys.path.insert(1, os.fspath(PROJECT_SITE_PACKAGES))

from core.executor import GraphExecutor
from core.project_loader import load_project
from core.project_schema import load_project_documents
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService
from core.services.preflight_service import PreflightService
from core.services.recording_replay_service import RecordingReplayService


def validate(project_path: Path) -> dict:
    project_path = project_path.resolve()
    root = os.fspath(project_path)
    documents = load_project_documents(root)

    workflow = BlueprintService.load_workflow(root)
    workflow['main_graph']['blocks'][0]['description'] = '已通过 v3 保存回读'
    BlueprintService.save_workflow(root, workflow, create_snapshot=False)
    saved = BlueprintService.load_workflow(root)
    assert saved['main_graph']['blocks'][0]['description'] == '已通过 v3 保存回读'

    executor = GraphExecutor(
        load_project(root), project_dir=root,
        text_log_enabled=False, image_log_enabled=False,
    )
    executor.run('main', 'main_log_start')
    assert executor.variables.get('run_count') == 41.0

    asset_ref = documents['topology.json']['nodes'][0]['params']['features'][0]['image_source']
    asset = AssetService.resolve(root, asset_ref)
    assert Path(asset['full_path']).is_file()

    session_id = 'frame_recording_testisok_offline'
    first = RecordingReplayService.analyze_frame(root, session_id, 1)
    second = RecordingReplayService.analyze_frame(root, session_id, 2)
    regression = RecordingReplayService.analyze_session(root, session_id)
    assert not first['matched_pages'], first
    assert [item['node_name'] for item in second['matched_pages']] == ['开售页面'], second
    assert regression['error_frame_count'] == 0
    assert regression['coverage'][0]['matched_frames'] == 2

    preflight = PreflightService.check(root, check_scope='debug')
    assert preflight['counts']['error'] == 0, preflight['issues']

    return {
        'project_path': root,
        'schema_version': documents['project.json']['schema_version'],
        'documents': sorted(documents),
        'workflow_roundtrip': True,
        'execution': {'run_count': executor.variables.get('run_count'), 'logs': len(executor.logs)},
        'function_contract': {
            'functions': len(saved['functions']),
            'test_cases': len(saved['functions'][0]['test_cases']),
        },
        'asset': {'reference': asset_ref, 'exists': True},
        'offline_replay': {
            'first_frame_matches': len(first['matched_pages']),
            'second_frame_matches': [item['node_name'] for item in second['matched_pages']],
            'coverage': regression['coverage'],
        },
        'preflight': {'warnings': preflight['counts']['warning'], 'errors': 0},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', default=r'D:\PycharmProjects\testisok')
    args = parser.parse_args()
    print(json.dumps(validate(Path(args.path)), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
