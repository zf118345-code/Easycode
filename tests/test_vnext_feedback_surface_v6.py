from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vnext_business_feedback_does_not_use_host_default_dialogs() -> None:
    frontend_root = ROOT / 'frontend' / 'src' / 'vnext'
    native_root = ROOT / 'native' / 'CaptureOverlay'
    android_root = ROOT / 'android' / 'app' / 'src' / 'main' / 'java'
    runtime_roots = (ROOT / 'core' / 'vnext', ROOT / 'core' / 'services', ROOT / 'api')
    forbidden = (
        'window.alert(',
        'window.confirm(',
        'window.prompt(',
        'MessageBox.Show',
        'System.Windows.Forms.MessageBox',
        'MessageBoxW(',
        'MessageBoxA(',
        'messagebox.',
        'AlertDialog',
    )

    offenders: list[str] = []
    paths = [
        *frontend_root.rglob('*'),
        *native_root.rglob('*.cs'),
        *android_root.rglob('*.kt'),
        ROOT / 'player.py',
    ]
    for runtime_root in runtime_roots:
        paths.extend(runtime_root.rglob('*.py'))
    for path in paths:
        if path.suffix not in {'.vue', '.ts', '.js', '.cs', '.py', '.kt'} or not path.is_file():
            continue
        source = path.read_text(encoding='utf-8')
        for marker in forbidden:
            if marker in source:
                offenders.append(f'{path.relative_to(ROOT)}: {marker}')

    assert offenders == []


def test_android_field_capture_success_has_one_feedback_surface() -> None:
    """All Android field outcomes return to the shared Player without native Toasts."""
    android_source = (
        ROOT
        / 'android'
        / 'app'
        / 'src'
        / 'main'
        / 'java'
        / 'com'
        / 'easycode'
        / 'player'
    )
    service = (
        android_source
        / 'capture'
        / 'ScreenCaptureService.kt'
    ).read_text(encoding='utf-8')
    player = (android_source / 'PlayerActivity.kt').read_text(encoding='utf-8')

    assert 'Toast.makeText' not in service
    assert 'Toast.makeText' not in player
    assert 'returnToPlayer(true, "字段已保存到方案 revision ${profile.revision}", destination)' in service
    assert 'cancelCurrent("字段采集已取消；旧值保持不变", destination)' in service
    assert 'add("host_feedback", feedback.deepCopy())' in player
    assert "easycode-native-capture-complete" in player
