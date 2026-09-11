"""Canonical standalone Windows Player entry point.

Only Python's standard library is imported before worker dispatch and before
the bundle/trust-root command line is parsed and committed to the environment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import os
import socket
import sys
import threading
import time
import traceback
from contextlib import suppress
from pathlib import Path
from typing import Sequence


_LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}
_FAULT_STREAM = None
_DEFAULT_ENTRY_WARNING = ''


def _application_directory() -> Path:
    """Return the directory beside the launched Player executable/source."""

    if bool(getattr(sys, 'frozen', False)):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _packaged_release_file(name: str) -> Path:
    return _application_directory() / 'release' / name


def _diagnostics_directory() -> Path:
    """Return a user-writable directory available before Player imports."""

    instance_root = str(os.environ.get('EASYCODE_PLAYER_DATA_DIR') or '').strip()
    if instance_root:
        return Path(instance_root).expanduser().resolve() / 'logs'
    local = str(os.environ.get('LOCALAPPDATA') or '').strip()
    base = Path(local) if local else Path.home() / 'AppData' / 'Local'
    return base / 'EasyCode' / 'Player' / 'logs'


def _write_startup_failure(exc: BaseException) -> Path | None:
    """Persist bootstrap failures that a windowed executable cannot print."""

    try:
        directory = _diagnostics_directory()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'startup.log'
        with path.open('a', encoding='utf-8', newline='\n') as stream:
            stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
            stream.write(f'[{stamp}] Player 启动失败\n')
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=stream)
            stream.write('\n')
        return path
    except Exception:
        return None


def _dispatch_worker(argv: Sequence[str]) -> int | None:
    if '--capability-worker' in argv:
        from core.services.capability_worker import main as capability_worker_main

        return int(capability_worker_main() or 0)
    if '--extension-worker' in argv:
        from core.vnext.extension_worker_v6 import main as extension_worker_main

        return int(extension_worker_main() or 0)
    if '--player-hub-agent' in argv:
        from core.vnext.schedule_hub_v6 import main as player_hub_main

        return int(player_hub_main(['agent']) or 0)
    if '--register-installation' in argv or '--disable-installation' in argv:
        command = argparse.ArgumentParser(description='EasyCode Player 安装登记')
        mode = command.add_mutually_exclusive_group(required=True)
        mode.add_argument('--register-installation')
        mode.add_argument('--disable-installation')
        command.add_argument('--instance-name', default='实例 1')
        options = command.parse_args(list(argv))
        from core.vnext.schedule_hub_v6 import get_player_hub_v6, shutdown_player_hub_v6

        hub = get_player_hub_v6()
        try:
            if options.register_installation:
                result = hub.registry.register_distribution(
                    options.register_installation,
                    instance_name=options.instance_name,
                )
            else:
                result = hub.registry.disable_distribution(options.disable_installation)
            if sys.stdout is not None:
                sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\n')
            return 0
        finally:
            shutdown_player_hub_v6()
    return None


def _default_packaged_arguments(argv: Sequence[str]) -> list[str]:
    """Route a directly opened signed distribution into the Player console.

    Explicit invocations keep their exact single-player/worker semantics.  A
    registration failure is recoverable: normal bundle auto-discovery remains
    available and the warning is persisted by the regular Player logger.
    """

    global _DEFAULT_ENTRY_WARNING
    arguments = list(argv)
    if arguments:
        return arguments
    root = _application_directory()
    required = (
        root / 'EasycodePlayer.exe',
        root / 'build_manifest.json',
        root / 'release' / 'project.ecplayer',
        root / 'release' / 'trust-root.json',
    )
    if not all(path.is_file() for path in required):
        return arguments
    from core.vnext.schedule_hub_v6 import get_player_hub_v6, shutdown_player_hub_v6

    try:
        installation = get_player_hub_v6().registry.register_distribution(
            root,
            instance_name='实例 1',
        )
        product_id = str(installation.get('product_id') or '').strip()
        if not product_id:
            raise RuntimeError('Player Hub 登记结果缺少产品身份')
        _DEFAULT_ENTRY_WARNING = ''
        return [
            '--mode', 'prod', '--port', '0', '--player-console',
            '--select-product', product_id,
        ]
    except Exception as exc:
        _DEFAULT_ENTRY_WARNING = f'默认多实例控制台登记失败，已回退单实例 Player：{exc}'
        return arguments
    finally:
        shutdown_player_hub_v6()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='EasyCode 独立 Windows Player')
    parser.add_argument('--mode', choices=['dev', 'prod'], default='prod')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument(
        '--port', type=int, default=None,
        help='本地服务端口；生产模式默认由系统分配，开发模式默认 8000',
    )
    parser.add_argument(
        '--player-console', action='store_true',
        help='打开当前用户的多实例 Player 控制台',
    )
    parser.add_argument('--select-product', default='', help=argparse.SUPPRESS)
    parser.add_argument('--console-worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--runtime-descriptor', default='', help=argparse.SUPPRESS)
    parser.add_argument('--console-origin-file', default='', help=argparse.SUPPRESS)
    parser.add_argument('--console-parent-pid', type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument(
        '--player-bundle', '--bundle',
        dest='player_bundle',
        default=os.environ.get('EASYCODE_PLAYER_BUNDLE', ''),
        help='已签名的 .ecplayer 发布包',
    )
    parser.add_argument(
        '--player-trust-root', '--trust-root',
        dest='player_trust_root',
        default=os.environ.get('EASYCODE_PLAYER_TRUST_ROOT', ''),
        help='安装包固定的发布者信任根 JSON',
    )
    parser.add_argument(
        '--product-metadata',
        default=os.environ.get('EASYCODE_PLAYER_PRODUCT_METADATA', ''),
        help='发布包生成的 Player 名称与图标元数据',
    )
    return parser


def _prepare_environment(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.port is None:
        args.port = 0 if args.mode == 'prod' else 8000
    if args.host not in _LOOPBACK_HOSTS:
        parser.error('独立 Player HTTP 服务只能监听 127.0.0.1、localhost 或 ::1')
    if not 0 <= int(args.port) <= 65535:
        parser.error('端口必须在 0..65535 范围内；0 表示由系统分配空闲端口')
    if args.mode != 'prod' and int(args.port) == 0:
        parser.error('自动分配端口只适用于独立 Player 生产模式')
    if args.player_console:
        if args.console_worker:
            parser.error('Player 控制台不能同时作为实例工作进程启动')
        os.environ['FLAGS_use_mkldnn'] = '0'
        os.environ['FLAGS_enable_pir_api'] = '0'
        return
    if not str(args.player_bundle or '').strip():
        packaged_bundle = _packaged_release_file('project.ecplayer')
        if packaged_bundle.is_file():
            args.player_bundle = os.fspath(packaged_bundle)
    if not str(args.player_trust_root or '').strip():
        packaged_trust_root = _packaged_release_file('trust-root.json')
        if packaged_trust_root.is_file():
            args.player_trust_root = os.fspath(packaged_trust_root)
    if not str(args.product_metadata or '').strip():
        packaged_product_metadata = _packaged_release_file('product.json')
        if packaged_product_metadata.is_file():
            args.product_metadata = os.fspath(packaged_product_metadata)
    bundle = Path(str(args.player_bundle or '')).expanduser()
    trust_root = Path(str(args.player_trust_root or '')).expanduser()
    if not str(args.player_bundle or '').strip() or not bundle.is_file():
        parser.error('--player-bundle 必须指向存在的已签名 .ecplayer 文件')
    if not str(args.player_trust_root or '').strip() or not trust_root.is_file():
        parser.error('--player-trust-root 必须指向存在的固定信任根文件')
    if bundle.suffix.casefold() != '.ecplayer':
        parser.error('--player-bundle 必须使用 .ecplayer 扩展名')
    if args.console_worker:
        descriptor = Path(str(args.runtime_descriptor or '')).expanduser()
        origin_file = Path(str(args.console_origin_file or '')).expanduser()
        if not str(args.runtime_descriptor or '').strip() or descriptor.name != 'worker.json':
            parser.error('控制台工作进程缺少有效的 --runtime-descriptor')
        if not str(args.console_origin_file or '').strip() or origin_file.name != 'console-origin.txt':
            parser.error('控制台工作进程缺少有效的 --console-origin-file')
        if int(args.console_parent_pid or 0) <= 0:
            parser.error('控制台工作进程缺少有效的 --console-parent-pid')
    os.environ['EASYCODE_PLAYER_BUNDLE'] = os.fspath(bundle.resolve())
    os.environ['EASYCODE_PLAYER_TRUST_ROOT'] = os.fspath(trust_root.resolve())
    if str(args.product_metadata or '').strip():
        product_metadata = Path(str(args.product_metadata)).expanduser()
        if product_metadata.is_file():
            os.environ['EASYCODE_PLAYER_PRODUCT_METADATA'] = os.fspath(product_metadata.resolve())
    os.environ['EASYCODE_PLAYER_REQUIRE_TRUST_ROOT'] = '1'
    os.environ['FLAGS_use_mkldnn'] = '0'
    os.environ['FLAGS_enable_pir_api'] = '0'


def _bootstrap_application(argv: Sequence[str]):
    """Parse trust inputs first, then import and create the Player app."""

    parser = _parser()
    args = parser.parse_args(list(argv))
    _prepare_environment(args, parser)

    from core.services.dpi_service import enable_per_monitor_v2

    enable_per_monitor_v2()
    if args.player_console:
        from api.player_app import create_player_console_app, start_player_console_webview

        return args, create_player_console_app(), start_player_console_webview
    from api.player_app import create_player_app, start_webview

    return args, create_player_app(), start_webview


def _configure_process_logging() -> None:
    global _FAULT_STREAM
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except (AttributeError, OSError, ValueError):
            pass
    handlers: list[logging.Handler] = []
    try:
        directory = _diagnostics_directory()
        directory.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(
            directory / 'player.log',
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding='utf-8',
            delay=True,
        ))
        _FAULT_STREAM = (directory / 'native-crash.log').open('a', encoding='utf-8')
        faulthandler.enable(file=_FAULT_STREAM)
    except (OSError, RuntimeError):
        _FAULT_STREAM = None
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers or None,
        force=True,
    )
    if _FAULT_STREAM is None:
        with suppress(Exception):
            faulthandler.enable()


def _reserve_loopback_socket(host: str) -> tuple[socket.socket, int]:
    """Reserve one race-free loopback port for an isolated Player instance."""

    family = socket.AF_INET6 if host == '::1' else socket.AF_INET
    bind_host = '127.0.0.1' if host == 'localhost' else host
    listener = socket.socket(family, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((bind_host, 0))
        listener.listen(2048)
        return listener, int(listener.getsockname()[1])
    except Exception:
        listener.close()
        raise


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')),
        encoding='utf-8',
    )
    os.replace(temporary, path)


def _pid_alive(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name != 'nt':
        try:
            os.kill(process_id, 0)
            return True
        except OSError:
            return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            # Security products and integrity boundaries can deny a harmless
            # process query even when the console is alive.  Treat access
            # denied as "present but uninspectable"; an exited PID reports
            # ERROR_INVALID_PARAMETER instead.
            return int(ctypes.windll.kernel32.GetLastError()) == 5
        try:
            exit_code = ctypes.c_ulong(0)
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return False


def _owner_lease_alive(path: Path, *, grace_seconds: float = 8.0) -> bool:
    """Keep a worker while either its owner PID or recent lease is credible."""

    if _pid_alive(_read_owner_pid(path)):
        return True
    try:
        return max(0.0, time.time() - path.stat().st_mtime) <= max(1.0, float(grace_seconds))
    except OSError:
        return False


def _read_owner_pid(path: Path) -> int:
    try:
        return int(path.read_text(encoding='utf-8-sig').strip())
    except (OSError, TypeError, ValueError):
        return 0


def _run_console_worker(args: argparse.Namespace, actual_port: int, http_server) -> None:
    """Publish the hidden worker and keep active runs alive across console restarts."""

    descriptor = Path(str(args.runtime_descriptor)).resolve()
    owner_path = descriptor.parent / 'owner.pid'
    stop_path = descriptor.parent / 'stop.request'
    origin_path = Path(str(args.console_origin_file)).resolve()
    _atomic_json(descriptor, {
        'schema_version': 1,
        'instance_id': str(os.environ.get('EASYCODE_PLAYER_INSTANCE_ID') or ''),
        'instance_name': str(os.environ.get('EASYCODE_PLAYER_INSTANCE_NAME') or ''),
        'process_id': os.getpid(),
        'port': int(actual_port),
        'console_origin_file': os.fspath(origin_path),
        'started_at': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
    })
    logger = logging.getLogger(__name__)
    logger.info(
        'player.console.worker.started instance_id=%s pid=%s port=%s owner_pid=%s',
        str(os.environ.get('EASYCODE_PLAYER_INSTANCE_ID') or ''),
        os.getpid(),
        int(actual_port),
        int(args.console_parent_pid or 0),
    )
    orphaned_at: float | None = None
    exit_reason = 'http_server_stopped'
    try:
        while not http_server.should_exit:
            if stop_path.is_file():
                exit_reason = 'stop_requested'
                break
            owner_alive = _owner_lease_alive(owner_path)
            if owner_alive:
                orphaned_at = None
            else:
                from core.vnext.runtime import vnext_runtime

                snapshot = vnext_runtime.latest_snapshot()
                status = str((snapshot or {}).get('status') or '')
                if status in {'queued', 'running', 'paused'}:
                    orphaned_at = None
                else:
                    orphaned_at = orphaned_at or time.monotonic()
                    if time.monotonic() - orphaned_at >= 15.0:
                        exit_reason = 'owner_lost_after_grace'
                        break
            time.sleep(0.25)
    finally:
        logger.info(
            'player.console.worker.exiting instance_id=%s pid=%s reason=%s',
            str(os.environ.get('EASYCODE_PLAYER_INSTANCE_ID') or ''),
            os.getpid(),
            exit_reason,
        )
        current = None
        try:
            current = json.loads(descriptor.read_text(encoding='utf-8-sig'))
        except (OSError, json.JSONDecodeError):
            pass
        if isinstance(current, dict) and int(current.get('process_id') or 0) == os.getpid():
            descriptor.unlink(missing_ok=True)
        stop_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        worker_result = _dispatch_worker(arguments)
        if worker_result is not None:
            return worker_result
        arguments = _default_packaged_arguments(arguments)
        args, app, start_webview = _bootstrap_application(arguments)
        _configure_process_logging()
        if _DEFAULT_ENTRY_WARNING:
            logging.getLogger(__name__).warning(_DEFAULT_ENTRY_WARNING)

        import uvicorn

        if args.mode == 'prod':
            listener = None
            actual_port = int(args.port)
            if actual_port == 0:
                listener, actual_port = _reserve_loopback_socket(args.host)
            http_server = uvicorn.Server(uvicorn.Config(
                app=app,
                host=args.host,
                port=actual_port,
                log_level='error',
                log_config=None,
                access_log=False,
            ))
            server_thread = threading.Thread(
                target=(
                    (lambda: http_server.run(sockets=[listener]))
                    if listener is not None else http_server.run
                ),
                daemon=True,
                name='easycode-player-http',
            )
            server_thread.start()
            deadline = time.monotonic() + 10.0
            while (
                server_thread.is_alive()
                and not http_server.started
                and time.monotonic() < deadline
            ):
                time.sleep(0.05)
            if not http_server.started:
                logger = logging.getLogger(__name__)
                logger.error('Player HTTP 服务未能在限定时间内启动')
                http_server.should_exit = True
                server_thread.join(timeout=2)
                if listener is not None:
                    with suppress(OSError):
                        listener.close()
                return 2
            if not args.player_console:
                # The external updater accepts the new directory only after
                # a real packaged Player initialized its local API.
                from core.vnext.windows_update_helper_v6 import write_startup_health_receipt

                write_startup_health_receipt()
            try:
                if args.console_worker:
                    _run_console_worker(args, actual_port, http_server)
                elif args.player_console:
                    start_webview(actual_port, selected_product=str(args.select_product or ''))
                else:
                    start_webview(actual_port)
            finally:
                http_server.should_exit = True
                server_thread.join(timeout=10)
                if listener is not None:
                    with suppress(OSError):
                        listener.close()
            # Every production host reaches this point only after its visible
            # native window/worker loop ended and ASGI lifespan completed.
            # Source-mode production probes can load the same OCR/capture
            # libraries as a frozen build, so they need the same final exit
            # guarantee instead of retaining a headless Python process.
            if args.mode == 'prod':
                # Frozen OCR/capture dependencies may own non-daemon helper
                # threads.  At this point the descriptor is gone, the ASGI
                # lifespan has closed Runtime/Bundle resources, and the HTTP
                # thread was joined; do not let unrelated library threads keep
                # any packaged Player or console process alive without a
                # visible native window.
                os._exit(0)
        else:
            uvicorn.run(
                app,
                host=args.host,
                port=args.port,
                reload=False,
                log_level='warning',
                log_config=None,
            )
        return 0
    except Exception as exc:
        _write_startup_failure(exc)
        raise


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
