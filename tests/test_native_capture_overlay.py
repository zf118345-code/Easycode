import os

import pytest

from core.services.native_capture_overlay import NativeCaptureOverlay


def test_winexe_host_uses_redirected_pipe_streams_without_console_code_pages():
    """A winexe has no console handle, even when stdin/stdout are redirected.

    Accessing Console.InputEncoding/OutputEncoding calls the console code-page
    APIs and crashes the native host with ERROR_INVALID_HANDLE before it can
    emit its ready event. Keep the transport bound directly to the redirected
    standard streams instead.
    """
    source = (NativeCaptureOverlay.source_dir() / 'Program.cs').read_text(encoding='utf-8')

    assert 'Console.OpenStandardInput()' in source
    assert 'Console.OpenStandardOutput()' in source
    assert 'Console.InputEncoding =' not in source
    assert 'Console.OutputEncoding =' not in source


def test_native_overlay_compiler_targets_wpf_executable(tmp_path, monkeypatch):
    sources = tmp_path / 'native' / 'CaptureOverlay'
    sources.mkdir(parents=True)
    (sources / 'Program.cs').write_text('class Program {}', encoding='utf-8')
    monkeypatch.setattr(NativeCaptureOverlay, '_repo_root', staticmethod(lambda: tmp_path))

    command = NativeCaptureOverlay._compiler_command(tmp_path / 'overlay.exe')

    assert '/target:winexe' in command
    assert '/platform:x64' in command
    assert any('PresentationFramework.dll' in argument for argument in command)
    assert any('WindowsFormsIntegration.dll' in argument for argument in command)
    assert any('Microsoft.Web.WebView2.Core.dll' in argument for argument in command)
    assert any('Microsoft.Web.WebView2.WinForms.dll' in argument for argument in command)
    assert command[-1].endswith('Program.cs')


def test_native_overlay_reuses_vue_file_browser_instead_of_a_second_save_dialog():
    source_dir = NativeCaptureOverlay.source_dir()
    overlay_source = (source_dir / 'CaptureOverlayWindow.cs').read_text(encoding='utf-8')
    browser_host_source = (source_dir / 'CaptureFileBrowserWindow.cs').read_text(encoding='utf-8')
    program_source = (source_dir / 'Program.cs').read_text(encoding='utf-8')

    assert '_resourceBrowser.OpenAsync(' in overlay_source
    assert '_payload.Origin' in overlay_source
    assert '/capture.html' in browser_host_source
    assert 'capture-file-manager-ready' in browser_host_source
    assert 'PrewarmAsync' in browser_host_source
    assert 'kind == "warm"' in program_source
    assert 'WebView2' in browser_host_source
    assert not (source_dir / 'SaveResourceDialog.cs').exists()


def test_resource_browser_waits_for_host_hwnd_and_reports_webview_failures():
    source_dir = NativeCaptureOverlay.source_dir()
    browser_source = (source_dir / 'CaptureFileBrowserWindow.cs').read_text(encoding='utf-8')
    provider_source = (source_dir / 'WebViewEnvironmentProvider.cs').read_text(encoding='utf-8')
    program_source = (source_dir / 'Program.cs').read_text(encoding='utf-8')

    assert 'await EnsureHostedControlReadyAsync();' in browser_source
    assert 'new WindowInteropHelper(this).EnsureHandle()' in browser_source
    assert '_webView.IsHandleCreated' in browser_source
    assert 'DispatcherPriority.Loaded' in browser_source
    assert 'LastFailureDetail' in browser_source
    assert 'HRESULT 0x' in browser_source
    assert 'NavigationCompleted' in browser_source
    assert '_environmentTask.IsFaulted' in provider_source
    assert 'ResetAfterFailure' in provider_source
    assert '_resourceBrowser.LastFailureDetail' in program_source


def test_field_capture_uses_lucide_check_and_closes_after_success():
    source_dir = NativeCaptureOverlay.source_dir()
    overlay_source = (source_dir / 'CaptureOverlayWindow.cs').read_text(encoding='utf-8')
    icon_source = (source_dir / 'LucideIcons.cs').read_text(encoding='utf-8')

    assert 'ToolButton("check", _fieldDestination == "resource" ?' in overlay_source
    assert '"录入所选资源 (Enter)" : "确认并回填 (Enter)"' in overlay_source
    assert '{ "check", new[] { "M20,6 L9,17 L4,12" } }' in icon_source
    assert 'if (closeAfter) CloseAsync(); else FocusOverlay();' in overlay_source
    assert 'bool fieldSave = kind == "field_confirm";' in overlay_source
    assert '_fieldCompleted = true;' in overlay_source


def test_native_capture_feedback_stays_inside_easycode_surface():
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    assert 'MessageBox.Show' not in overlay_source
    assert 'AutomationProperties.SetName(button, tooltip);' in overlay_source
    assert '再次点击页面按钮继续' in overlay_source


def test_windows_field_capture_uses_low_obstruction_focus_pattern():
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    # Windows keeps its native WPF host, but follows the same capture-session
    # semantics as Android without a conspicuous transition flash.
    assert 'BeginFreezeFlash();' not in overlay_source
    assert 'DrawSelectionFocusMask();' in overlay_source
    assert 'FillRule = FillRule.EvenOdd' in overlay_source
    assert '_fieldMode && TryGetSelectionBounds(out selection)' in overlay_source


def test_capture_selection_visuals_are_quiet_and_number_only_real_multi_selects():
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    assert '(!_fieldMode || _fieldMaxRects > 1)' in overlay_source
    assert 'DrawCornerGuides(x, y, width, height);' in overlay_source
    assert 'double[,] handles' not in overlay_source
    assert 'glyph.Opacity = button.IsEnabled ? 1 : 0.26;' in overlay_source
    assert 'ControlTemplate template = new ControlTemplate(typeof(Button));' in overlay_source
    assert 'Template = template, FocusVisualStyle = null' in overlay_source


def test_capture_pointer_remains_visible_on_light_and_dark_snapshots():
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    assert '_drawing = new Canvas { Background = Brushes.Transparent, Cursor = Cursors.None };' in overlay_source
    assert '_cursorMarker = CreatePointerMarker();' in overlay_source
    assert 'Stroke = Brush("#F26A21"), StrokeThickness = 1.5' in overlay_source
    assert 'Stroke = Brush("#0B0D10"), StrokeThickness = 3.5' in overlay_source
    assert 'UpdatePointerMarker(args);' in overlay_source
    assert '_cursorLayer.Children.Add(_cursorMarker);' in overlay_source


def test_capture_pointer_moves_on_a_cached_composition_layer_without_layout_churn():
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    assert '_cursorMarker.RenderTransform = _cursorTransform;' in overlay_source
    assert '_cursorMarker.CacheMode = new BitmapCache();' in overlay_source
    assert 'Canvas.SetLeft(_cursorMarker' not in overlay_source
    assert 'Canvas.SetTop(_cursorMarker' not in overlay_source
    assert 'VisualTreeHelper.GetDpi(_captureGrid)' in overlay_source
    assert 'Interval = TimeSpan.FromMilliseconds(16)' in overlay_source
    assert '_pendingPointerPosition = args.GetPosition(_captureGrid);' in overlay_source
    assert '_cursorUpdateTimer.Tick += delegate { FlushPointerMarker(); };' in overlay_source


def test_native_field_capture_samples_color_from_the_frozen_frame() -> None:
    overlay_source = (
        NativeCaptureOverlay.source_dir() / 'CaptureOverlayWindow.cs'
    ).read_text(encoding='utf-8')

    assert '_fieldSelectionMode == "color"' in overlay_source
    assert 'action["color"] = SampleColor(_point.Value);' in overlay_source
    assert 'bgra.CopyPixels(new Int32Rect(x, y, 1, 1)' in overlay_source
    assert 'DrawColorLabel(_point.Value);' in overlay_source
    assert 'String.Format("#{0:X2}{1:X2}{2:X2}"' in overlay_source


def test_centered_virtual_capture_uses_only_a_slim_safety_inset():
    source = (NativeCaptureOverlay.source_dir() / 'Program.cs').read_text(encoding='utf-8')

    assert 'const int horizontalMargin = 6;' in source
    assert 'const int verticalMargin = 6;' in source
    assert 'toolbarReserve' not in source


def test_semantic_control_picker_reuses_overlay_and_exposes_parent_only_navigation():
    source_dir = NativeCaptureOverlay.source_dir()
    overlay_source = (source_dir / 'CaptureOverlayWindow.cs').read_text(encoding='utf-8')
    icon_source = (source_dir / 'LucideIcons.cs').read_text(encoding='utf-8')

    assert 'BaseAction("field_control_probe")' in overlay_source
    assert 'SelectParentControl();' in overlay_source
    assert '选择父级控件；再次点击继续向上' in overlay_source
    assert '_controlCandidates[_controlCandidateIndex]' in overlay_source
    assert 'action["selector"]' in overlay_source
    assert '选择子级控件' not in overlay_source
    assert '"corner-up-left"' in icon_source


def test_virtual_target_capture_is_centered_and_scaled_without_losing_pixel_space():
    source_dir = NativeCaptureOverlay.source_dir()
    program_source = (source_dir / 'Program.cs').read_text(encoding='utf-8')
    overlay_source = (source_dir / 'CaptureOverlayWindow.cs').read_text(encoding='utf-8')

    assert 'payload.Presentation, "centered_fit"' in program_source
    assert 'payload.FitInside(target.WorkingArea);' in program_source
    assert 'scale = Math.Min(1.0' in program_source
    assert 'point.X * _payload.Width / Math.Max(1, _captureGrid.ActualWidth)' in overlay_source


def test_native_host_exposes_separate_desktop_shell_mode():
    source_dir = NativeCaptureOverlay.source_dir()
    program_source = (source_dir / 'Program.cs').read_text(encoding='utf-8')
    shell_source = (source_dir / 'DesktopShellWindow.cs').read_text(encoding='utf-8')

    assert '--desktop-shell' in program_source
    assert 'RunDesktopShell' in program_source
    assert 'window-command' in shell_source
    assert 'desktop-shell-ready' in shell_source
    assert 'desktop-window-close-requested' in shell_source
    assert 'close-confirmed' in shell_source
    assert 'close-cancelled' in shell_source
    assert 'Closing += OnClosing' in shell_source
    assert 'WebViewEnvironmentProvider.GetAsync()' in shell_source
    assert 'ResizeMode = ResizeMode.CanResize' in shell_source
    assert 'WmNcHitTest' in shell_source
    assert 'ResizeBorderThickness = new Thickness(10)' in shell_source


def test_native_overlay_transfers_snapshot_as_file_not_base64(tmp_path, monkeypatch):
    overlay = NativeCaptureOverlay()
    target = tmp_path / 'snapshot.png'
    commands = []
    monkeypatch.setattr(overlay, '_snapshot_path', lambda _snapshot_id: str(target))
    monkeypatch.setattr(
        overlay,
        'command',
        lambda kind, payload, timeout: commands.append((kind, payload, timeout)) or {'ok': True},
    )

    result = overlay.show(
        {
            'origin': 'http://127.0.0.1:5173',
            'session_id': 'ide_test',
            'project_path': str(tmp_path),
            'capture_context': {'ports': []},
        },
        {
            'snapshot_id': 'snap_test',
            'width': 2,
            'height': 2,
            'region': [10, 20, 12, 22],
            'backend': 'window',
        },
        b'png-bytes',
    )

    assert result['ok'] is True
    assert target.read_bytes() == b'png-bytes'
    assert commands[0][0] == 'show'
    assert commands[0][1]['snapshot_path'] == str(target)
    assert 'image' not in commands[0][1]


@pytest.mark.skipif(os.name != 'nt', reason='Windows named shared memory only')
def test_native_overlay_uses_shared_bgra_for_live_preview(monkeypatch):
    import mmap
    from PIL import Image

    overlay = NativeCaptureOverlay()
    observed = {}

    def command(kind, payload, timeout):
        observed.update(payload)
        with mmap.mmap(-1, payload['snapshot_stride'] * payload['height'], tagname=payload['snapshot_mapping'], access=mmap.ACCESS_READ) as mapping:
            observed['pixels'] = mapping.read(4)
        return {'ok': True}

    monkeypatch.setattr(overlay, 'command', command)
    result = overlay.show(
        {'origin': 'http://127.0.0.1:5174', 'session_id': 'ide', 'project_path': 'D:/Demo'},
        {
            'snapshot_id': 'snap_shared', 'width': 2, 'height': 2,
            'region': [0, 0, 2, 2], 'backend': 'vnext:windows',
        },
        b'',
        image=Image.new('RGB', (2, 2), (10, 20, 30)),
    )
    try:
        assert result['ok'] is True
        assert observed['snapshot_transport'] == 'shared_bgra'
        assert observed['snapshot_path'] == ''
        assert observed['pixels'] == bytes((30, 20, 10, 255))
        assert result['performance']['shared_memory_preview'] is True
    finally:
        overlay._cleanup_snapshot_file('snap_shared')
