from types import SimpleNamespace
import time

import pytest


class FakeContext:
    def __init__(self, frames):
        self.frames = list(frames)
        self.logs = []
        self.variables = {}
        self.project_dir = r'D:\project'
        self.image_log_enabled = False
        self.current_task_name = 'test'
        self.current_node_index = 0
        self._memory_templates = {}
        self.is_stopped = False

    def log(self, message, level='info', image=None):
        self.logs.append((level, message))

    def get_setting(self, key, default=None):
        return default


class FakeFrameStream:
    context = None

    def __init__(self, capture, **kwargs):
        self.index = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def next(self, after_sequence=0, timeout_s=None):
        from core.services.runtime_session import FramePacket

        if self.index >= len(self.context.frames):
            if timeout_s:
                time.sleep(min(timeout_s, 0.02))
            raise TimeoutError()
        image = self.context.frames[self.index]
        self.index += 1
        return FramePacket(
            image=image,
            region=(0, 0, 100, 100),
            sequence=self.index,
            captured_at_ns=0,
            capture_duration_ms=1.0,
        )


def node(mode, **overrides):
    params = {
        'image_source': 'asset://A',
        'execution_mode': mode,
        'threshold': 85,
        'timeout': 1000,
        'region_type': 'fullwindow',
        'frame_interval_ms': 0,
        'click_interval_ms': 0,
        'max_clicks': 100,
        'present_stable_frames': 1,
        'absent_stable_frames': 2,
        'stop_stable_frames': 1,
        'match_scales': '1.0',
    }
    params.update(overrides)
    return SimpleNamespace(params=params)


@pytest.fixture
def harness(monkeypatch):
    from core.node_executors.base import image_recognition as module

    clicks = []
    monkeypatch.setattr(
        module,
        'create_visual_frame_stream',
        lambda context, capture, **kwargs: FakeFrameStream(capture),
    )
    monkeypatch.setattr(module, 'refresh_work_area', lambda context: (10, 20, 100, 100))
    monkeypatch.setattr(
        module.ImageRecognitionNodeExecutor,
        '_load_template',
        staticmethod(lambda reference, context: (reference, True)),
    )

    def match(packet, region, template, **kwargs):
        reference = getattr(template, 'reference', template)
        score = float(packet.image.get(reference, 0.0))
        return score, ((10, 12) if score >= 0.85 else None), 0.1

    monkeypatch.setattr(module.ImageRecognitionNodeExecutor, '_match', staticmethod(match))
    monkeypatch.setattr(
        module.ImageRecognitionNodeExecutor,
        '_smart_click',
        staticmethod(lambda position, context: clicks.append(position) or {
            'ok': True,
            'method': 'fake',
            'delivery': 'delivered_unverified',
        }),
    )
    executor = module.ImageRecognitionNodeExecutor.__new__(module.ImageRecognitionNodeExecutor)
    return module, executor, clicks


def run(harness, frames, configured_node):
    _, executor, _ = harness
    context = FakeContext(frames)
    FakeFrameStream.context = context
    return executor.execute(configured_node, context)


def test_wait_present_finishes_on_first_present_frame(harness):
    result = run(harness, [{'asset://A': 0.2}, {'asset://A': 0.95}], node('wait_present'))
    assert result['success'] is True
    assert result['stop_reason'] == 'target_found'
    assert result['frames'] == 2
    assert harness[2] == []


def test_wait_absent_requires_configured_stable_frames(harness):
    result = run(
        harness,
        [{'asset://A': 0.95}, {'asset://A': 0.1}, {'asset://A': 0.95}, {'asset://A': 0.1}, {'asset://A': 0.1}],
        node('wait_absent', absent_stable_frames=2),
    )
    assert result['success'] is True
    assert result['stop_reason'] == 'target_absent'
    assert result['frames'] == 5


def test_click_once_dispatches_exactly_one_click(harness):
    result = run(harness, [{'asset://A': 0.96}], node('click_once'))
    assert result['success'] is True
    assert result['stop_reason'] == 'clicked_once'
    assert result['click_count'] == 1
    assert harness[2] == [(10, 12)]


def test_click_until_absent_does_not_finish_on_one_flicker_frame(harness):
    result = run(
        harness,
        [{'asset://A': 0.96}, {'asset://A': 0.1}, {'asset://A': 0.96}, {'asset://A': 0.1}, {'asset://A': 0.1}],
        node('click_until_absent', absent_stable_frames=2),
    )
    assert result['success'] is True
    assert result['stop_reason'] == 'target_disappeared'
    assert result['click_count'] == 2


def test_stop_feature_has_priority_over_target_click_on_same_frame(harness):
    configured = node(
        'click_until_stop',
        stop_image_source='asset://B',
        stop_threshold=85,
    )
    result = run(
        harness,
        [
            {'asset://A': 0.96, 'asset://B': 0.1},
            {'asset://A': 0.96, 'asset://B': 0.1},
            {'asset://A': 0.96, 'asset://B': 0.99},
        ],
        configured,
    )
    assert result['success'] is True
    assert result['stop_reason'] == 'stop_feature_found'
    assert result['click_count'] == 2
    assert len(harness[2]) == 2


def test_click_until_stop_requires_stop_template(harness):
    result = run(harness, [{'asset://A': 0.96}], node('click_until_stop'))
    assert result['success'] is False
    assert result['error'] == 'stop template missing'


def test_continuous_click_honors_hard_click_limit(harness):
    result = run(
        harness,
        [{'asset://A': 0.96}, {'asset://A': 0.96}],
        node('click_until_absent', max_clicks=1),
    )
    assert result['success'] is False
    assert result['stop_reason'] == 'max_clicks_reached'
    assert result['click_count'] == 1


def test_continuous_click_keeps_cadence_when_static_surface_emits_no_new_frame(harness):
    result = run(
        harness,
        [{'asset://A': 0.96}],
        node('click_until_absent', max_clicks=3, click_interval_ms=10, timeout=100),
    )
    assert result['success'] is False
    assert result['stop_reason'] == 'max_clicks_reached'
    assert result['click_count'] == 3
    assert len(harness[2]) == 3


def test_recorded_region_uses_asset_capture_metadata_when_node_value_is_empty(harness, monkeypatch):
    module, _, _ = harness
    monkeypatch.setattr(
        module.AssetService,
        'resolve',
        classmethod(lambda cls, project_dir, reference, require_exists=True: {
            'record': {
                'capture': {
                    'region': [4, 5, 20, 30],
                    'reference_size': [100, 100],
                    'coordinate_space': 'workspace_px',
                },
            },
        }),
    )

    context = FakeContext([{'asset://A': 0.95}])
    FakeFrameStream.context = context
    result = harness[1].execute(
        node(
            'wait_present',
            region_type='recorded',
            region_value=[0, 0, 0, 0],
            region_reference_size=[0, 0],
        ),
        context,
    )

    assert result['success'] is True
    assert any('采用资源元数据: [4, 5, 20, 30]' in message for _, message in context.logs)


def test_invalid_custom_region_returns_visible_node_error(harness):
    result = run(
        harness,
        [{'asset://A': 0.95}],
        node('wait_present', region_type='custom', region_value=[0, 0, 0, 0]),
    )

    assert result['success'] is False
    assert result['stop_reason'] == 'invalid_region'
    assert '宽高大于 0' in result['error']
