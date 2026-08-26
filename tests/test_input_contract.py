from types import SimpleNamespace

import pytest


class Target(SimpleNamespace):
    def __init__(self, **kwargs):
        values = {
            'variables': {}, 'window_hwnd': None, 'window_rect': (10, 20, 100, 50),
            'is_emulator': False, 'device_id': None, 'android_width': None, 'android_height': None,
            'settings': {},
        }
        values.update(kwargs)
        super().__init__(**values)

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)


def test_workspace_coordinate_scales_from_recording_reference():
    from core.services.runtime_target import workspace_point, workspace_rect

    target = Target()
    assert workspace_point(target, 100, 50, [200, 100]) == (50, 25, 60, 45)
    assert workspace_rect(target, [20, 10, 100, 40], [200, 100]) == (10, 5, 50, 20)


def test_workspace_coordinate_rejects_out_of_bounds():
    from core.services.runtime_target import RuntimeTargetError, workspace_point

    with pytest.raises(RuntimeTargetError, match='越界'):
        workspace_point(Target(), 100, 0, [100, 50])


def test_pc_backend_failure_does_not_use_physical_mouse_by_default(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *args, **kwargs: (5, 6, 15, 26))
    monkeypatch.setattr(dispatcher, 'background_click', lambda *args, **kwargs:
                        {'ok': False, 'method': 'background', 'message': 'unsupported'})
    monkeypatch.setattr(dispatcher, '_physical_click', lambda *args, **kwargs:
                        pytest.fail('默认不得调用物理鼠标'))
    result = dispatcher.click_workspace(Target(window_hwnd=1001), 5, 6)
    assert result['ok'] is False
    assert result['method'] == 'background'


def test_pc_backend_failure_respects_explicitly_disabled_fallback(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *args, **kwargs: (5, 6, 15, 26))
    monkeypatch.setattr(dispatcher, 'background_click', lambda *args, **kwargs:
                        {'ok': False, 'method': 'background', 'message': 'unsupported'})
    monkeypatch.setattr(dispatcher, '_physical_click', lambda *args, **kwargs:
                        pytest.fail('显式关闭时不得调用物理鼠标'))
    result = dispatcher.click_workspace(Target(window_hwnd=1001, settings={'allow_physical_fallback': False}), 5, 6)
    assert result['ok'] is False


def test_pc_backend_failure_uses_physical_only_when_authorized(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *args, **kwargs: (5, 6, 15, 26))
    monkeypatch.setattr(dispatcher, 'background_click', lambda *args, **kwargs:
                        {'ok': False, 'method': 'background', 'message': 'unsupported'})
    monkeypatch.setattr(dispatcher, '_physical_click', lambda *args, **kwargs:
                        {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified'})
    result = dispatcher.click_workspace(
        Target(window_hwnd=1001, settings={'allow_physical_fallback': True}), 5, 6,
    )
    assert result['ok'] is True
    assert result['method'] == 'physical'
    assert result['fallback_reason'] == 'unsupported'


def test_emulator_never_falls_back_to_physical_mouse(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    target = Target(
        is_emulator=True,
        device_id='emulator-5554',
        android_width=1280,
        android_height=720,
        settings={'allow_physical_fallback': True},
    )
    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *args, **kwargs: (5, 6, 15, 26))
    monkeypatch.setattr(dispatcher, 'workspace_to_android', lambda *args, **kwargs: (50, 60))
    monkeypatch.setattr(dispatcher, '_adb_click', lambda *args, **kwargs:
                        {'ok': False, 'method': 'adb', 'message': 'offline'})
    monkeypatch.setattr(dispatcher, '_physical_click', lambda *args, **kwargs:
                        pytest.fail('ADB 失败不得回退物理鼠标'))
    result = dispatcher.click_workspace(target, 5, 6)
    assert result['ok'] is False
    assert result['method'] == 'adb'


def test_drag_and_text_background_failure_remain_strict(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    monkeypatch.setattr(dispatcher, 'workspace_point', lambda *args, **kwargs: (5, 6, 15, 26))
    monkeypatch.setattr(dispatcher, 'background_drag', lambda *args, **kwargs: {'ok': False, 'delivery': 'failed', 'message': 'unsupported'})
    monkeypatch.setattr(dispatcher, 'background_text', lambda *args, **kwargs: {'ok': False, 'delivery': 'failed', 'message': 'unsupported'})
    monkeypatch.setattr(dispatcher, '_physical_drag', lambda *args, **kwargs: pytest.fail('不得回退物理拖拽'))
    target = Target(window_hwnd=1001, settings={'allow_physical_fallback': False})
    assert dispatcher.drag_workspace(target, 1, 2, 3, 4)['ok'] is False
    assert dispatcher.text_workspace(target, 'hello', position=[1, 2])['ok'] is False


def test_fullscreen_text_forces_physical_even_when_project_switch_is_false(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    target = Target(window_hwnd=None, variables={'work_mode': 'desktop'}, settings={'allow_physical_fallback': False})
    monkeypatch.setattr(dispatcher, '_run_physical', lambda context, operation, prefix:
                        {'ok': True, 'method': 'physical', 'delivery': 'delivered_unverified'})
    result = dispatcher.text_workspace(target, 'hello', click_before=False)
    assert result['ok'] is True
    assert result['method'] == 'physical'


def test_android_text_clear_uses_scrcpy_select_all_before_utf8(monkeypatch):
    import core.services.android_stream as android_stream
    import core.services.input_dispatcher as dispatcher

    calls = []

    class Session:
        def keyevent(self, keycode, **kwargs):
            calls.append(('key', keycode, kwargs.get('metastate', 0)))
            return {'ok': True}

        def inject_text(self, value):
            calls.append(('text', value))
            return {'ok': True, 'method': 'scrcpy_control'}

    monkeypatch.setattr(android_stream, 'get_android_control_session', lambda context: Session())
    context = Target(
        is_emulator=True, device_id='emulator-5554', android_width=1280, android_height=720,
        settings={'android_input_transport': 'scrcpy'},
    )
    result = dispatcher._adb_text(context, '中文', clear_before=True, submit_key='enter')
    assert result['ok'] is True
    assert calls == [('key', 29, 0x1000), ('key', 67, 0), ('text', '中文'), ('key', 66, 0)]
