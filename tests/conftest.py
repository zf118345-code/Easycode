"""pytest 公共 fixtures"""

import os
import sys

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest  # noqa: E402


@pytest.fixture
def app():
    """获取 FastAPI app（不启动 uvicorn）"""
    from api.app import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app, tmp_path):
    """FastAPI 测试客户端；用户级状态隔离到本测试的临时目录。"""
    from fastapi.testclient import TestClient
    from core.services.project_workspace_service import project_workspace_manager

    original_app_data_dir = project_workspace_manager.app_data_dir
    project_workspace_manager.shutdown()
    project_workspace_manager.app_data_dir = str(tmp_path / 'app-state')
    os.makedirs(project_workspace_manager.app_data_dir, exist_ok=True)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        project_workspace_manager.shutdown()
        project_workspace_manager.app_data_dir = original_app_data_dir


@pytest.fixture
def sample_blueprint():
    """测试用蓝图数据"""
    return {
        'schema_version': 3,
        'project_name': 'test_project',
        'main_graph': {
                'graph_id': 'main',
                'nodes': [
                    {
                        'node_id': 'node_1',
                        'node_name': '点击节点',
                        'node_type': 'click',
                        'params': {'position': [100, 200]},
                        'delay_before': 0,
                        'loop_count': 1,
                        'enabled': True,
                    }
                ],
                'edges': [],
        },
        'functions': [],
        'function_folders': [],
        'variables': {'count': 0},
        'page_map': {'schema_version': 3, 'nodes': [], 'edges': []},
        'ui_state': {},
        'settings': {},
    }
