from pathlib import Path

import pytest

from scripts.build_player import verify_delivery_bundle


REQUIRED_DELIVERY_FILES = (
    'EasycodePlayer.exe',
    '_internal/native/CaptureOverlay/EasycodeCaptureOverlay.exe',
    '_internal/native/CaptureOverlay/Microsoft.Web.WebView2.Core.dll',
    '_internal/native/CaptureOverlay/Microsoft.Web.WebView2.WinForms.dll',
    '_internal/native/CaptureOverlay/WebView2Loader.dll',
    '_internal/uiautomation/bin/UIAutomationClient_VC140_X64.dll',
    '_internal/uiautomation/bin/UIAutomationClient_VC140_X86.dll',
    'release/assets.ebp',
    'release/web/index.html',
    'release/web/player.html',
    'release/web/capture.html',
)


def _complete_bundle(root: Path) -> None:
    for relative in REQUIRED_DELIVERY_FILES:
        target = root / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'test')


def test_verify_delivery_bundle_accepts_complete_clean_bundle(tmp_path):
    _complete_bundle(tmp_path)

    verified = verify_delivery_bundle(tmp_path)

    assert len(verified) == len(REQUIRED_DELIVERY_FILES)


def test_verify_delivery_bundle_rejects_missing_runtime_boundary(tmp_path):
    _complete_bundle(tmp_path)
    (tmp_path / 'release/web/player.html').unlink()

    with pytest.raises(RuntimeError, match='player.html'):
        verify_delivery_bundle(tmp_path)


def test_verify_delivery_bundle_rejects_webview_user_data(tmp_path):
    _complete_bundle(tmp_path)
    profile = tmp_path / '_internal/native/CaptureOverlay/EasycodeCaptureOverlay.exe.WebView2'
    profile.mkdir(parents=True)

    with pytest.raises(RuntimeError, match='WebView2'):
        verify_delivery_bundle(tmp_path)
