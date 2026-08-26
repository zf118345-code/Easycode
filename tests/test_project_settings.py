# tests/test_project_settings.py
# ⚡ 项目级引擎设置：默认值合并、API 读写、加载等待（帧稳定+超时轮询）
import json
import pytest
from core.settings import DEFAULT_PROJECT_SETTINGS, merge_settings, SETTINGS_GROUPS


def test_merge_settings_defaults_and_partial_override():
    """未知键忽略、缺失用默认、已知键覆盖"""
    merged = merge_settings(None)
    assert merged['popup_cooldown_ms'] == 800
    assert merged['frame_stable_frames'] == 2

    merged2 = merge_settings({'popup_cooldown_ms': 1500, 'unknown_key': 999, 'max_logs': None})
    assert merged2['popup_cooldown_ms'] == 1500
    assert merged2['max_logs'] == 500  # None 不覆盖
    assert 'unknown_key' not in merged2


def test_settings_groups_cover_all_defaults():
    """分组元数据覆盖全部默认设置项（前端可渲染每一项）"""
    keys_in_groups = {f['key'] for g in SETTINGS_GROUPS for f in g['fields']}
    assert keys_in_groups == set(DEFAULT_PROJECT_SETTINGS.keys()), keys_in_groups ^ set(DEFAULT_PROJECT_SETTINGS.keys())



def test_load_wait_hits_after_animation(monkeypatch):
    """加载等待：动画帧（变化）→ 纯等待不识别；静止后识别 → 命中（复用共享截图）"""
    from core.executor import GraphExecutor
    from PIL import Image
    import numpy as np

    frames = [Image.fromarray(np.full((64, 64), i % 8, dtype=np.uint8)) for i in range(4)]  # 动画（帧差大）
    frames += [Image.fromarray(np.full((64, 64), 30, dtype=np.uint8))] * 20  # 静止

    ex = object.__new__(GraphExecutor)
    ex.settings = {'frame_stable_frames': 2, 'frame_stable_threshold': 10,
                   'page_load_poll_ms': 5, 'page_load_anim_wait_ms': 5}
    monkeypatch.setattr(GraphExecutor, 'is_stopped', False)
    ex.variables = {}
    ex._prev_frame = None
    ex._stable_frame_count = 0
    ex._step_screen = None
    ex.logs = []
    ex.log = lambda msg, level='info', image=None: ex.logs.append(msg)
    ex._topology_page_label = lambda ref: ref
    ex.evaluate_current_page = lambda: 'page_hit' if ex._stable_frame_count >= 2 else ''

    capture_idx = {'n': 0}
    def capture():
        i = min(capture_idx['n'], len(frames) - 1)
        capture_idx['n'] += 1
        ex._step_screen = frames[i]
    ex._capture_workspace_step = capture

    result = ex._resolve_current_page_with_load_wait(800)
    assert result == 'page_hit', ex.logs
    assert any('页面加载完成' in l for l in ex.logs)


def test_load_wait_timeout_fails(monkeypatch):
    """加载等待：画面静止但始终识别不到 → 超时报错返回空（不再立即失败）"""
    from core.executor import GraphExecutor
    from PIL import Image
    import numpy as np

    static = Image.fromarray(np.full((64, 64), 30, dtype=np.uint8))

    ex = object.__new__(GraphExecutor)
    ex.settings = {'frame_stable_frames': 1, 'frame_stable_threshold': 100,
                   'page_load_poll_ms': 5, 'page_load_anim_wait_ms': 5}
    monkeypatch.setattr(GraphExecutor, 'is_stopped', False)
    ex.variables = {}
    ex._prev_frame = None
    ex._stable_frame_count = 0
    ex._step_screen = None
    ex.logs = []
    ex.log = lambda msg, level='info', image=None: ex.logs.append(msg)
    ex._topology_page_label = lambda ref: ref
    ex.evaluate_current_page = lambda: ''
    ex._capture_workspace_step = lambda: setattr(ex, '_step_screen', static)

    result = ex._resolve_current_page_with_load_wait(120)
    assert result == ''
    assert any('加载等待超时' in l for l in ex.logs)


def test_load_wait_anim_waits_without_evaluating(monkeypatch):
    """加载动画期间纯等待：帧变化大时不调用页面评估（省 CPU）"""
    from core.executor import GraphExecutor
    from PIL import Image
    import numpy as np

    ex = object.__new__(GraphExecutor)
    ex.settings = {'frame_stable_frames': 2, 'frame_stable_threshold': 10,
                   'page_load_poll_ms': 5, 'page_load_anim_wait_ms': 5}
    monkeypatch.setattr(GraphExecutor, 'is_stopped', False)
    ex.variables = {}
    ex._prev_frame = None
    ex._stable_frame_count = 0
    ex._step_screen = None
    ex.logs = []
    ex.log = lambda msg, level='info', image=None: ex.logs.append(msg)
    ex._topology_page_label = lambda ref: ref
    evals = {'n': 0}
    ex.evaluate_current_page = lambda: (evals.__setitem__('n', evals['n'] + 1), '')[1]

    idx = {'n': 0}
    def capture():
        ex._step_screen = Image.fromarray(np.full((64, 64), idx['n'] % 7, dtype=np.uint8))
        idx['n'] += 1
    ex._capture_workspace_step = capture

    ex._resolve_current_page_with_load_wait(120)
    # 动画期间评估次数远小于总帧数（纯等待为主）
    assert evals['n'] < 8, f'动画中不应频繁识别: {evals["n"]}'
