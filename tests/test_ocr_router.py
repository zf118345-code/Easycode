# tests/test_ocr_router.py
# ⚡ OCR 测试链路回归：路由必须把 image_source 透传给 test_ocr（此前丢失导致
# 选中模板图片后"测试识别"仍截屏幕区域而不是识别模板）
import io
import cv2
import numpy as np


def _make_template_png(text_region=True):
    """生成一张含黑色文字的白色小图（模拟模板）"""
    img = np.full((40, 120, 3), 255, dtype=np.uint8)
    cv2.putText(img, 'Hello', (5, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    ok, buf = cv2.imencode('.png', img)
    return io.BytesIO(buf.tobytes())


def test_ocr_test_router_passes_image_source(tmp_path, monkeypatch):
    """POST /api/ocr/test 携带 image_source 时，识别模板图片而非屏幕截图"""
    from fastapi.testclient import TestClient
    import sys, os
    sys.path.insert(0, os.getcwd())

    from api.app import app

    # 造一个带模板的项目
    proj = tmp_path / 'proj'
    (proj / 'templates' / 'ocr').mkdir(parents=True)
    (proj / 'templates' / 'ocr' / 't1.png').write_bytes(_make_template_png().getvalue())

    captured = {}

    def fake_test_ocr(project_path, region_value, gray_scale, gray_threshold, image_source=''):
        captured['image_source'] = image_source
        captured['region_value'] = region_value
        return {'status': 'success', 'text': 'FAKE', 'image': ''}

    import core.services.vision_service as vs
    monkeypatch.setattr(vs.VisionService, 'test_ocr', staticmethod(fake_test_ocr))

    client = TestClient(app)
    resp = client.post('/api/ocr/test', json={
        'project_path': str(proj),
        'image_source': 'ocr/t1',
        'region_value': [10, 20, 30, 40],
        'gray_scale': False,
        'gray_threshold': 127,
    })
    assert resp.status_code == 200
    assert resp.json()['text'] == 'FAKE'
    # 关键断言：路由把 image_source 透传给了服务层
    assert captured['image_source'] == 'ocr/t1'
    assert captured['region_value'] == [10, 20, 30, 40]


def test_ocr_test_router_without_image_source(tmp_path, monkeypatch):
    """不传 image_source 时默认空字符串（不报错）"""
    from fastapi.testclient import TestClient
    import sys, os
    sys.path.insert(0, os.getcwd())

    from api.app import app

    captured = {}

    def fake_test_ocr(project_path, region_value, gray_scale, gray_threshold, image_source=''):
        captured['image_source'] = image_source
        return {'status': 'success', 'text': '', 'image': ''}

    import core.services.vision_service as vs
    monkeypatch.setattr(vs.VisionService, 'test_ocr', staticmethod(fake_test_ocr))

    client = TestClient(app)
    resp = client.post('/api/ocr/test', json={
        'project_path': str(tmp_path),
        'region_value': [0, 0, 0, 0],
    })
    assert resp.status_code == 200
    assert captured['image_source'] == ''
