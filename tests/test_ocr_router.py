# tests/test_ocr_router.py
# ⚡ OCR 测试链路回归：路由必须把 image_source 透传给 test_ocr（此前丢失导致
# 选中模板图片后"测试识别"仍截屏幕区域而不是识别模板）
import io
import cv2
import numpy as np
import json

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService


def _make_template_png(text_region=True):
    """生成一张含黑色文字的白色小图（模拟模板）"""
    img = np.full((40, 120, 3), 255, dtype=np.uint8)
    cv2.putText(img, 'Hello', (5, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    ok, buf = cv2.imencode('.png', img)
    return io.BytesIO(buf.tobytes())


def test_ocr_test_router_passes_image_source(client, tmp_path, monkeypatch):
    """POST /api/ocr/test 携带 image_source 时，识别模板图片而非屏幕截图"""
    # 造一个带模板的项目
    proj = tmp_path / 'proj'
    (proj / 'templates' / 'ocr').mkdir(parents=True)
    (proj / 'templates' / 'ocr' / 't1.png').write_bytes(_make_template_png().getvalue())
    for filename, value in new_project_documents('ocr-test').items():
        (proj / filename).write_text(json.dumps(value), encoding='utf-8')
    AssetService.ensure_structure(str(proj))

    captured = {}

    def fake_test_ocr(
        project_path, region_value, gray_scale, gray_threshold,
        image_source='', region_reference_size=None,
    ):
        captured['image_source'] = image_source
        captured['region_value'] = region_value
        captured['region_reference_size'] = region_reference_size
        return {'status': 'success', 'text': 'FAKE', 'image': ''}

    import core.services.vision_service as vs
    monkeypatch.setattr(vs.VisionService, 'test_ocr', staticmethod(fake_test_ocr))

    opened = client.post('/api/workspaces/open', json={'path': str(proj)}).json()['workspace']
    headers = {
        'X-Workspace-Id': opened['workspace_id'],
        'X-Workspace-Generation': str(opened['generation']),
    }
    resp = client.post('/api/ocr/test', json={
        'project_path': str(proj),
        'image_source': 'ocr/t1',
        'region_value': [10, 20, 30, 40],
        'gray_scale': False,
        'gray_threshold': 127,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()['text'] == 'FAKE'
    # 关键断言：路由把 image_source 透传给了服务层
    assert captured['image_source'] == 'ocr/t1'
    assert captured['region_value'] == [10, 20, 30, 40]
    assert captured['region_reference_size'] == [0, 0]


def test_ocr_test_router_without_image_source(client, tmp_path, monkeypatch):
    """不传 image_source 时默认空字符串（不报错）"""
    captured = {}

    def fake_test_ocr(
        project_path, region_value, gray_scale, gray_threshold,
        image_source='', region_reference_size=None,
    ):
        captured['image_source'] = image_source
        return {'status': 'success', 'text': '', 'image': ''}

    import core.services.vision_service as vs
    monkeypatch.setattr(vs.VisionService, 'test_ocr', staticmethod(fake_test_ocr))

    for filename, value in new_project_documents('ocr-empty').items():
        (tmp_path / filename).write_text(json.dumps(value), encoding='utf-8')
    AssetService.ensure_structure(str(tmp_path))
    opened = client.post('/api/workspaces/open', json={'path': str(tmp_path)}).json()['workspace']
    headers = {
        'X-Workspace-Id': opened['workspace_id'],
        'X-Workspace-Generation': str(opened['generation']),
    }
    resp = client.post('/api/ocr/test', json={
        'project_path': str(tmp_path),
        'region_value': [0, 0, 0, 0],
    }, headers=headers)
    assert resp.status_code == 200
    assert captured['image_source'] == ''
