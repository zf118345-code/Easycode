"""Build and deliver the native vNext Android Player without shell interpolation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.android_delivery_v6 import (  # noqa: E402
    AndroidDeliveryError,
    android_delivery_service_v6,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description='EasyCode vNext Android APK / ADB bridge')
    commands = value.add_subparsers(dest='command', required=True)

    build = commands.add_parser('build', help='构建并验证真实 APK')
    build.add_argument('--bundle', required=True)
    build.add_argument('--trust-root', required=True)
    build.add_argument(
        '--variant', choices=sorted(android_delivery_service_v6.VARIANTS),
        default='productionDebug',
    )
    build.add_argument('--output')
    build.add_argument('--verify-reproducible', action='store_true')

    commands.add_parser('devices', help='列出 ADB 设备及真实授权状态')

    install = commands.add_parser('install', help='校验并安装 APK')
    install.add_argument('--serial', required=True)
    install.add_argument('--apk', required=True)

    launch = commands.add_parser('launch', help='启动 Android Player Activity')
    launch.add_argument('--serial', required=True)
    launch.add_argument('--package', required=True)

    push = commands.add_parser('push-bundle', help='传入签名内容包，下次启动原子导入')
    push.add_argument('--serial', required=True)
    push.add_argument('--package', required=True)
    push.add_argument('--bundle', required=True)
    push.add_argument('--trust-root', required=True)

    logs = commands.add_parser('logs', help='读取 Player 进程或设备尾部日志')
    logs.add_argument('--serial', required=True)
    logs.add_argument('--package', required=True)
    logs.add_argument('--lines', type=int, default=400)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = android_delivery_service_v6
    try:
        if args.command == 'build':
            result = service.build(
                args.bundle,
                args.trust_root,
                variant=args.variant,
                output_path=args.output,
                verify_reproducible=args.verify_reproducible,
            )
        elif args.command == 'devices':
            result = {'devices': service.devices()}
        elif args.command == 'install':
            result = service.install(args.serial, args.apk)
        elif args.command == 'launch':
            result = service.launch(args.serial, args.package)
        elif args.command == 'push-bundle':
            result = service.push_bundle(
                args.serial, args.package, args.bundle, args.trust_root,
            )
        elif args.command == 'logs':
            result = service.logs(args.serial, args.package, lines=args.lines)
        else:  # pragma: no cover - argparse owns the command set
            raise AssertionError(args.command)
    except AndroidDeliveryError as exc:
        print(json.dumps({
            'ok': False,
            'error': {'code': exc.code, 'message': str(exc), 'diagnostics': exc.diagnostics},
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
