from types import SimpleNamespace


class Context:
    is_stopped = False
    is_emulator = False

    def __init__(self):
        self.logs = []

    def log(self, message, level='info'):
        self.logs.append((level, message))


def node(params):
    return SimpleNamespace(params=params)


def test_scroll_auto_uses_pc_wheel_and_direction_sign(monkeypatch):
    from core.node_executors.base import scroll as module

    calls = []
    monkeypatch.setattr(module, 'scroll_workspace', lambda *args, **kwargs: calls.append(kwargs) or {'ok': True, 'method': 'background'})
    result = module.ScrollNodeExecutor().execute(node({
        'gesture_mode': 'auto', 'direction': 'down', 'position': [20, 30],
        'wheel_ticks': 4, 'repeat_count': 1,
    }), Context())
    assert result['success'] is True
    assert calls[0]['ticks'] == -4


def test_scroll_endpoint_hold_uses_swipe(monkeypatch):
    from core.node_executors.base import scroll as module

    calls = []
    monkeypatch.setattr(module, 'drag_workspace', lambda *args, **kwargs: calls.append((args, kwargs)) or {'ok': True, 'method': 'scrcpy_control'})
    context = Context()
    context.is_emulator = True
    result = module.ScrollNodeExecutor().execute(node({
        'gesture_mode': 'auto', 'direction': 'down', 'position_mode': 'custom', 'position': [200, 400],
        'distance_mode': 'pixels', 'distance_px': 250, 'release_mode': 'hold', 'hold_after_ms': 120,
        'repeat_count': 1, 'post_wait_ms': 0,
    }), context)
    assert result['success'] is True
    assert calls[0][0][3:5] == (200, 150)
    assert calls[0][1]['hold_after_ms'] == 120


def test_scroll_custom_path_keeps_start_and_end_in_one_reference_space():
    from core.node_executors.base.scroll import ScrollNodeExecutor

    context = Context()
    context.window_rect = (0, 0, 1920, 1080)
    start, end, reference = ScrollNodeExecutor._path({
        'direction': 'custom',
        'position_mode': 'center',
        'end_position': [480, 54],
        'position_reference_size': [960, 540],
    }, context)

    assert start == [480, 270]
    assert end == [480, 54]
    assert reference == [960, 540]


def test_drag_multi_point_path_remains_one_continuous_gesture(monkeypatch):
    from core.node_executors.base import drag as module

    calls = []
    monkeypatch.setattr(module, 'drag_path_workspace', lambda *args, **kwargs: calls.append((args, kwargs)) or {'ok': True, 'method': 'background'})
    result = module.DragNodeExecutor().execute(node({
        'action': 'drag',
        'path_points': [
            {'position': [10, 20], 'move_ms': 0, 'hold_ms': 50},
            {'position': [20, 30], 'move_ms': 100, 'hold_ms': 20},
            {'position': [40, 50], 'move_ms': 200, 'hold_ms': 0},
        ],
        'release_wait_ms': 0,
    }), Context())
    assert result['success'] is True
    assert len(calls) == 1
    assert len(calls[0][0][1]) == 3


def test_drag_long_press_and_text_template(monkeypatch):
    from core.node_executors.base import drag as drag_module
    from core.node_executors.base import text_input as text_module

    drag_calls = []
    monkeypatch.setattr(drag_module, 'drag_workspace', lambda *args, **kwargs: drag_calls.append((args, kwargs)) or {'ok': True, 'method': 'background'})
    assert drag_module.DragNodeExecutor().execute(node({
        'action': 'long_press',
        'path_points': [{'position': [10, 20], 'move_ms': 0, 'hold_ms': 0}],
        'long_press_ms': 900,
    }), Context())['success'] is True
    assert drag_calls[0][0][1:5] == (10, 20, 10, 20)
    assert drag_calls[0][1]['hold_before_ms'] == 900

    text_calls = []
    monkeypatch.setattr(text_module, 'resolve_template_string', lambda value, context: 'resolved')
    monkeypatch.setattr(text_module, 'text_workspace', lambda *args, **kwargs: text_calls.append((args, kwargs)) or {'ok': True, 'method': 'background'})
    assert text_module.TextInputNodeExecutor().execute(node({'text': '$var{name}', 'sensitive': True}), Context())['success'] is True
    assert text_calls[0][0][1] == 'resolved'


def test_drag_without_v3_path_fails_instead_of_guessing_legacy_coordinates():
    from core.node_executors.base.drag import DragNodeExecutor

    result = DragNodeExecutor().execute(node({
        'action': 'drag', 'start_position': [10, 20], 'end_position': [30, 40],
    }), Context())

    assert result['success'] is False
    assert '缺少路径点' in result['error']
