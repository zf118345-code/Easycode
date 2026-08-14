"""pytest 公共 fixtures"""

import os
import sys

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app():
    """获取 FastAPI app（不启动 uvicorn）"""
    from api.app import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_blueprint():
    """测试用蓝图数据"""
    return {
        'project_name': 'test_project',
        'tasks': [
            {
                'task_id': 'task_main',
                'task_name': '主任务',
                'loop_count': 1,
                'loop_interval': 0,
                'nodes': [
                    {
                        'node_id': 'node_1',
                        'node_name': '点击节点',
                        'node_type': 'click',
                        'params': {'x': 100, 'y': 200},
                        'delay_before': 0,
                        'loop_count': 1,
                        'enabled': True,
                    }
                ],
            }
        ],
        'variables': {'count': 0},
        'edges': [],
        'topology': {'nodes': [], 'edges': []},
        'ui_state': {},
    }
