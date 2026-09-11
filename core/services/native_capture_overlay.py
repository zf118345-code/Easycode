"""Persistent native Windows capture overlay.

The overlay is deliberately kept outside Python's GUI stack.  Python owns the
immutable capture bytes and starts one long-lived WPF process; all mouse,
keyboard, layout and window messages stay on the WPF dispatcher thread.
"""

from __future__ import annotations

import atexit
import io
import importlib.util
import json
import logging
import mmap
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class NativeCaptureOverlay:
    """Build, prewarm and command the resident WPF overlay process."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._ready = threading.Event()
        self._pending: dict[str, dict[str, Any]] = {}
        self._last_error = ''
        self._snapshot_files: dict[str, str] = {}
        self._snapshot_maps: dict[str, mmap.mmap] = {}
        self._last_show_performance: dict[str, float] = {}
        self._registered_atexit = False

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @classmethod
    def source_dir(cls) -> Path:
        return cls._repo_root() / 'native' / 'CaptureOverlay'

    @classmethod
    def binary_path(cls) -> Path:
        if getattr(sys, 'frozen', False):
            bundle_root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
            return bundle_root / 'native' / 'CaptureOverlay' / 'EasycodeCaptureOverlay.exe'
        return cls._repo_root() / 'build' / 'native' / 'CaptureOverlay' / 'EasycodeCaptureOverlay.exe'

    @staticmethod
    def _framework_root() -> Path:
        windir = Path(os.environ.get('WINDIR') or r'C:\Windows')
        return windir / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319'

    @staticmethod
    def _gac_assembly(name: str, architecture: str = 'GAC_MSIL') -> Path | None:
        windir = Path(os.environ.get('WINDIR') or r'C:\Windows')
        root = windir / 'Microsoft.NET' / 'assembly' / architecture / name
        if not root.is_dir():
            return None
        matches = sorted(root.glob('v4.0_*/*.dll'))
        return matches[-1] if matches else None

    @classmethod
    def _webview2_dependency_sources(cls) -> dict[str, Path]:
        """Locate WebView2 assemblies already shipped with pywebview.

        The capture overlay uses WebView2 only for the shared Vue FileBrowser;
        screenshot display and selection stay native WPF. pywebview is already
        a required project dependency, so no second browser runtime/package is
        introduced here.
        """
        spec = importlib.util.find_spec('webview')
        roots = list(spec.submodule_search_locations or []) if spec else []
        if not roots and spec and spec.origin:
            roots = [os.fspath(Path(spec.origin).parent)]
        # The IDE may be repaired or tested with a bundled Python while the
        # workspace's .venv interpreter itself is unavailable.  Its installed
        # WebView2 runtime remains a valid build input, so discover it directly.
        local_webview = cls._repo_root() / '.venv' / 'Lib' / 'site-packages' / 'webview'
        if local_webview.is_dir() and os.fspath(local_webview) not in roots:
            roots.append(os.fspath(local_webview))
        if not roots:
            raise RuntimeError('未找到项目现有的 pywebview/WebView2 依赖')
        lib = Path(roots[0]) / 'lib'
        sources = {
            'Microsoft.Web.WebView2.Core.dll': lib / 'Microsoft.Web.WebView2.Core.dll',
            'Microsoft.Web.WebView2.WinForms.dll': lib / 'Microsoft.Web.WebView2.WinForms.dll',
            'WebView2Loader.dll': lib / 'runtimes' / 'win-x64' / 'native' / 'WebView2Loader.dll',
        }
        missing = [str(path) for path in sources.values() if not path.is_file()]
        if missing:
            raise RuntimeError(f'现有 WebView2 依赖不完整: {", ".join(missing)}')
        return sources

    @classmethod
    def _copy_webview2_dependencies(cls, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, source in cls._webview2_dependency_sources().items():
            target = target_dir / name
            if not target.is_file() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)

    @classmethod
    def _compiler_command(cls, output: Path) -> list[str]:
        framework = cls._framework_root()
        compiler = framework / 'csc.exe'
        if not compiler.is_file():
            raise RuntimeError('Windows .NET Framework C# 编译器不可用')
        sources = sorted(cls.source_dir().glob('*.cs'))
        if not sources:
            raise RuntimeError('原生捕获宿主源码缺失')
        presentation_core = cls._gac_assembly('PresentationCore', 'GAC_64')
        presentation_framework = cls._gac_assembly('PresentationFramework')
        windows_base = cls._gac_assembly('WindowsBase')
        windows_forms_integration = cls._gac_assembly('WindowsFormsIntegration')
        webview2 = cls._webview2_dependency_sources()
        references = [
            presentation_core,
            presentation_framework,
            windows_base,
            windows_forms_integration,
            framework / 'System.Xaml.dll',
            framework / 'System.Net.Http.dll',
            framework / 'System.Web.Extensions.dll',
            framework / 'System.Windows.Forms.dll',
            framework / 'System.Drawing.dll',
            webview2['Microsoft.Web.WebView2.Core.dll'],
            webview2['Microsoft.Web.WebView2.WinForms.dll'],
        ]
        missing = [str(path) for path in references if path is None or not path.is_file()]
        if missing:
            raise RuntimeError(f'原生捕获宿主缺少系统程序集: {", ".join(missing)}')
        return [
            str(compiler),
            '/nologo',
            '/target:winexe',
            '/platform:x64',
            '/optimize+',
            '/utf8output',
            f'/out:{output}',
            *(f'/reference:{path}' for path in references if path is not None),
            *(str(path) for path in sources),
        ]

    @classmethod
    def ensure_binary(cls) -> Path:
        output = cls.binary_path()
        if getattr(sys, 'frozen', False):
            if not output.is_file():
                raise RuntimeError('安装包缺少原生捕获宿主')
            return output
        sources = sorted(cls.source_dir().glob('*.cs'))
        newest_source = max((path.stat().st_mtime for path in sources), default=0)
        if output.is_file() and output.stat().st_mtime >= newest_source:
            cls._copy_webview2_dependencies(output.parent)
            return output
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f'{output.stem}.{uuid.uuid4().hex}.tmp.exe')
        command = cls._compiler_command(temporary)
        result = subprocess.run(
            command,
            cwd=str(cls._repo_root()),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            detail = (result.stdout or result.stderr or '').strip()[-1800:]
            raise RuntimeError(f'原生捕获宿主编译失败: {detail or result.returncode}')
        try:
            os.replace(temporary, output)
        finally:
            # Windows keeps a running executable locked. If replacement is
            # attempted before the resident host has stopped, do not leave a
            # compiled *.tmp.exe artifact behind.
            temporary.unlink(missing_ok=True)
        cls._copy_webview2_dependencies(output.parent)
        return output

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @property
    def process(self) -> subprocess.Popen[str] | None:
        with self._lock:
            return self._process

    @property
    def process_id(self) -> int:
        with self._lock:
            process = self._process
            return int(process.pid) if process and process.poll() is None else 0

    def is_alive(self) -> bool:
        with self._lock:
            return bool(self._process and self._process.poll() is None and self._ready.is_set())

    def _set_failed(self, message: str) -> None:
        with self._lock:
            self._last_error = message
            pending = list(self._pending.values())
            self._pending.clear()
        for item in pending:
            item['result'] = {'ok': False, 'message': message}
            item['event'].set()

    def _read_loop(self, process: subprocess.Popen[str]) -> None:
        stream = process.stdout
        if stream is None:
            self._set_failed('原生捕获宿主没有可用的响应管道')
            return
        try:
            for raw in stream:
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    logger.info('[NativeCaptureOverlay] %s', line)
                    continue
                if message.get('event') == 'ready':
                    self._ready.set()
                    continue
                request_id = str(message.get('request_id') or '')
                if request_id:
                    with self._lock:
                        pending = self._pending.get(request_id)
                    if pending is not None:
                        pending['result'] = message
                        pending['event'].set()
                        continue
                if message.get('event') == 'closed':
                    self._cleanup_snapshot_file(str(message.get('snapshot_id') or ''))
                elif message.get('event') == 'log':
                    logger.info('[NativeCaptureOverlay] %s', message.get('message') or '')
        except Exception as exc:
            self._set_failed(f'原生捕获宿主响应异常: {exc}')
        finally:
            if process.poll() is not None:
                self._set_failed(f'原生捕获宿主已退出（代码 {process.returncode}）')

    def start(self, timeout: float = 8.0) -> bool:
        with self._lock:
            if self._process and self._process.poll() is None:
                process = self._process
            else:
                self._ready.clear()
                self._last_error = ''
                try:
                    binary = self.ensure_binary()
                    process = subprocess.Popen(
                        [str(binary)],
                        cwd=str(binary.parent),
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                    )
                except Exception as exc:
                    self._last_error = str(exc)
                    return False
                self._process = process
                self._reader = threading.Thread(
                    target=self._read_loop,
                    args=(process,),
                    daemon=True,
                    name='native-capture-overlay-output',
                )
                self._reader.start()
                if not self._registered_atexit:
                    atexit.register(self.shutdown)
                    self._registered_atexit = True
        if self._ready.wait(timeout):
            return True
        if process.poll() is not None:
            self._set_failed(f'原生捕获宿主启动后退出（代码 {process.returncode}）')
        else:
            self._set_failed('原生捕获宿主启动超时')
        return False

    def prewarm(self) -> bool:
        if self.is_alive():
            return True
        return self.start(timeout=12.0)

    def warm_resource_manager(self, origin: str) -> dict[str, Any]:
        """Initialize the shared WebView and load the slim capture entry once."""
        clean_origin = str(origin or '').rstrip('/')
        if not clean_origin.startswith(('http://', 'https://')):
            return {'ok': False, 'message': '资源管理器预热地址无效'}
        return self.command('warm', {'origin': clean_origin}, timeout=12.0)

    def command(self, kind: str, payload: dict[str, Any] | None = None, timeout: float = 4.0) -> dict[str, Any]:
        if not self.start():
            return {'ok': False, 'message': self.last_error or '原生捕获宿主不可用'}
        request_id = f'native_{uuid.uuid4().hex}'
        waiter = {'event': threading.Event(), 'result': None}
        with self._lock:
            self._pending[request_id] = waiter
            process = self._process
        message = {'command': kind, 'request_id': request_id, **(payload or {})}
        try:
            if process is None or process.stdin is None:
                raise RuntimeError('原生捕获宿主管道未建立')
            with self._write_lock:
                process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(',', ':')) + '\n')
                process.stdin.flush()
            if not waiter['event'].wait(max(0.5, timeout)):
                return {'ok': False, 'message': f'原生捕获宿主未响应 {kind} 命令'}
            return waiter['result'] or {'ok': False, 'message': '原生捕获宿主返回空结果'}
        except Exception as exc:
            self._set_failed(f'原生捕获宿主通信失败: {exc}')
            return {'ok': False, 'message': self.last_error}
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def _snapshot_path(self, snapshot_id: str) -> str:
        folder = Path(tempfile.gettempdir()) / 'Easycode' / 'CaptureOverlay'
        folder.mkdir(parents=True, exist_ok=True)
        return os.fspath(folder / f'{snapshot_id}.png')

    def _cleanup_snapshot_file(self, snapshot_id: str) -> None:
        with self._lock:
            path = self._snapshot_files.pop(snapshot_id, '')
            mapping = self._snapshot_maps.pop(snapshot_id, None)
        if mapping is not None:
            try:
                mapping.close()
            except (BufferError, OSError):
                pass
        if path:
            try:
                os.remove(path)
            except OSError:
                pass

    def show(
        self,
        session: dict[str, Any],
        snapshot: dict[str, Any],
        png: bytes,
        *,
        image: Any = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        snapshot_id = str(snapshot.get('snapshot_id') or '')
        path = ''
        transport = 'png_file'
        mapping_name = ''
        stride = 0
        if image is not None and os.name == 'nt':
            try:
                rgba = image.convert('RGBA')
                pixels = rgba.tobytes('raw', 'BGRA')
                mapping_name = f'Local\\EasycodeCapture_{uuid.uuid4().hex}'
                mapping = mmap.mmap(-1, len(pixels), tagname=mapping_name, access=mmap.ACCESS_WRITE)
                mapping.write(pixels)
                mapping.seek(0)
                stride = int(rgba.width) * 4
                with self._lock:
                    self._snapshot_maps[snapshot_id] = mapping
                transport = 'shared_bgra'
            except Exception as exc:
                logger.warning('冻结帧共享内存准备失败，回退 PNG 文件: %s', exc)
                mapping_name = ''
                stride = 0
        if transport == 'png_file':
            if not png and image is not None:
                buffer = io.BytesIO()
                image.save(buffer, format='PNG', optimize=False, compress_level=1)
                png = buffer.getvalue()
            path = self._snapshot_path(snapshot_id)
            temporary = f'{path}.{uuid.uuid4().hex}.tmp'
            Path(temporary).write_bytes(png)
            os.replace(temporary, path)
            with self._lock:
                self._snapshot_files[snapshot_id] = path
        written_at = time.perf_counter()
        result = self.command('show', {
            'origin': str(session.get('origin') or '').rstrip('/'),
            'snapshot_path': path,
            'snapshot_transport': transport,
            'snapshot_mapping': mapping_name,
            'snapshot_stride': stride,
            'snapshot_id': snapshot_id,
            'session_id': str(session.get('session_id') or ''),
            'project_path': str(session.get('project_path') or ''),
            'project_name': str(session.get('project_name') or ''),
            'target_name': str(session.get('target_name') or ''),
            'width': int(snapshot.get('width') or 0),
            'height': int(snapshot.get('height') or 0),
            'region': list(snapshot.get('region') or []),
            'backend': str(snapshot.get('backend') or ''),
            'presentation': str(snapshot.get('presentation') or 'target_aligned'),
            'capture_context': session.get('capture_context') or {},
        }, timeout=5.0)
        completed_at = time.perf_counter()
        performance = {
            'snapshot_write_ms': round((written_at - started_at) * 1000, 1),
            'native_show_ms': round((completed_at - written_at) * 1000, 1),
            'shared_memory_preview': transport == 'shared_bgra',
        }
        with self._lock:
            self._last_show_performance = performance
        result = {**result, 'performance': performance}
        if not result.get('ok'):
            self._cleanup_snapshot_file(snapshot_id)
        return result

    @property
    def last_show_performance(self) -> dict[str, float]:
        with self._lock:
            return dict(self._last_show_performance)

    def focus(self) -> bool:
        return bool(self.command('focus', timeout=2.0).get('ok'))

    def hide(self, snapshot_id: str = '') -> None:
        if self.is_alive():
            self.command('hide', {'snapshot_id': snapshot_id}, timeout=2.0)
        self._cleanup_snapshot_file(snapshot_id)

    def shutdown(self) -> None:
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            try:
                self.command('shutdown', timeout=1.5)
            except Exception:
                pass
            try:
                process.wait(timeout=1.5)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
        with self._lock:
            snapshot_ids = list(self._snapshot_files)
            self._process = None
            self._ready.clear()
        for snapshot_id in snapshot_ids:
            self._cleanup_snapshot_file(snapshot_id)


native_capture_overlay = NativeCaptureOverlay()
