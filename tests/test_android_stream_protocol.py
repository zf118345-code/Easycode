import struct
import threading
from types import SimpleNamespace


def test_scrcpy_touch_message_matches_pinned_4_1_protocol():
    from core.services.android_stream import ScrcpyVideoSession

    payload = ScrcpyVideoSession._touch_message(0, 100, 200, 1080, 1920)
    assert len(payload) == 32
    values = struct.unpack('>BBQIIHHHII', payload)
    assert values == (
        2,
        0,
        0xFFFFFFFFFFFFFFFE,
        100,
        200,
        1080,
        1920,
        0xFFFF,
        0,
        0,
    )


def test_android_auto_input_prefers_existing_scrcpy_control_session(monkeypatch):
    import core.services.input_dispatcher as dispatcher

    calls = []

    class VideoSession:
        def tap(self, x, y, width, height):
            calls.append((x, y, width, height))
            return {'ok': True, 'method': 'scrcpy_control', 'delivery': 'delivered_unverified'}

    context = SimpleNamespace(
        device_id='emulator-5554',
        android_width=1280,
        android_height=720,
        _android_video_session=VideoSession(),
        get_setting=lambda key, default=None: default,
    )
    monkeypatch.setattr(
        dispatcher,
        'get_android_input_session',
        lambda context: (_ for _ in ()).throw(AssertionError('must not use persistent ADB')),
    )
    result = dispatcher._adb_click(context, 100, 200, 2, 'left')
    assert result['ok'] is True
    assert result['method'] == 'scrcpy_control'
    assert calls == [(100, 200, 1280, 720), (100, 200, 1280, 720)]


def test_scrcpy_utf8_text_and_meta_key_protocol(monkeypatch):
    from core.services.android_stream import ScrcpyVideoSession

    class Socket:
        def __init__(self):
            self.payloads = []

        def sendall(self, payload):
            self.payloads.append(payload)

    session = ScrcpyVideoSession.__new__(ScrcpyVideoSession)
    session.device_id = 'emulator-5554'
    session._control_socket = Socket()
    session._control_lock = threading.RLock()
    monkeypatch.setattr(session, 'start', lambda: session)

    result = session.inject_text('中文A')
    assert result['ok'] is True
    header = session._control_socket.payloads[0][:14]
    message_type, _, paste, length = struct.unpack('>BQBI', header)
    assert message_type == 9
    assert paste == 1
    assert length == len('中文A'.encode('utf-8'))
    assert session._control_socket.payloads[0][14:] == '中文A'.encode('utf-8')

    session.keyevent(29, metastate=0x1000)
    down, up = struct.unpack('>BBIII', session._control_socket.payloads[1][:14]), struct.unpack('>BBIII', session._control_socket.payloads[1][14:])
    assert down == (0, 0, 29, 0, 0x1000)
    assert up == (0, 1, 29, 0, 0x1000)
