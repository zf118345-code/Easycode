from pathlib import Path

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


def test_field_capture_uses_lucide_check_and_closes_after_success():
    source_dir = NativeCaptureOverlay.source_dir()
    overlay_source = (source_dir / 'CaptureOverlayWindow.cs').read_text(encoding='utf-8')
    icon_source = (source_dir / 'LucideIcons.cs').read_text(encoding='utf-8')

    assert 'ToolButton("check", "确认并回填 (Enter)"' in overlay_source
    assert '{ "check", new[] { "M20,6 L9,17 L4,12" } }' in icon_source
    assert 'if (closeAfter) CloseAsync(); else FocusOverlay();' in overlay_source
    assert 'bool fieldSave = kind == "field_confirm";' in overlay_source
    assert '_fieldCompleted = true;' in overlay_source


def test_native_host_exposes_separate_desktop_shell_mode():
    source_dir = NativeCaptureOverlay.source_dir()
    program_source = (source_dir / 'Program.cs').read_text(encoding='utf-8')
    shell_source = (source_dir / 'DesktopShellWindow.cs').read_text(encoding='utf-8')

    assert '--desktop-shell' in program_source
    assert 'RunDesktopShell' in program_source
    assert 'window-command' in shell_source
    assert 'desktop-shell-ready' in shell_source
    assert 'WebViewEnvironmentProvider.GetAsync()' in shell_source


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
