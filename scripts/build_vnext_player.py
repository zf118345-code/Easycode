"""Build/reuse the frozen runtime, then assemble one source-free vNext Player."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.distribution import (  # noqa: E402
    DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME,
    VNextDistributionAssembler,
    write_player_runtime_contract,
)


def _replace_runtime_template(source: Path, destination: Path) -> None:
    """Atomically refresh the reusable frozen Runtime after a successful build.

    Published Players built without ``--rebuild-runtime`` consume this canonical
    template.  Keeping it in sync prevents a later package from silently falling
    back to an older import graph (for example the former legacy OCR boundary).
    """

    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    staging = destination.with_name(f'{destination.name}.staging-{nonce}')
    backup = destination.with_name(f'{destination.name}.backup-{nonce}')
    shutil.copytree(source, staging)
    moved_existing = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_existing = True
        os.replace(staging, destination)
    except Exception:
        if not destination.exists() and moved_existing and backup.exists():
            os.replace(backup, destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description='构建 vNext EasyCode Player')
    parser.add_argument('--bundle', required=True, help='已发布的 .ecplayer 文件')
    parser.add_argument('--output', required=True, help='项目 dist 目录')
    parser.add_argument('--rebuild-runtime', action='store_true', help='先用 PyInstaller 重建通用运行时')
    parser.add_argument('--rebuild-web', action='store_true', help='先构建仅含 Player/Capture 的前端产物')
    parser.add_argument('--runtime-root', default='', help='复用指定的冻结 EasycodePlayer 目录')
    parser.add_argument('--build-root', default='D:/EasyCodeBuild/player-runtime', help='冻结 Runtime 的 D 盘工作根')
    args = parser.parse_args()
    if args.rebuild_web:
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        if not npm:
            parser.error('未找到 npm，无法构建 Player-only Web')
        subprocess.check_call(
            [npm, 'run', 'build:player'],
            cwd=ROOT / 'frontend',
        )
    if args.rebuild_runtime:
        build_root = Path(args.build_root).resolve()
        work_root = build_root / 'work'
        dist_root = build_root / 'dist'
        work_root.mkdir(parents=True, exist_ok=True)
        dist_root.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([
            sys.executable, '-m', 'PyInstaller', str(ROOT / 'scripts' / 'player.spec'),
            '--clean', '--noconfirm', '--workpath', str(work_root), '--distpath', str(dist_root),
        ], cwd=ROOT)
        subprocess.check_call([
            sys.executable, '-m', 'PyInstaller', str(ROOT / 'scripts' / 'windows_update_helper.spec'),
            '--clean', '--noconfirm', '--workpath', str(work_root), '--distpath', str(dist_root),
        ], cwd=ROOT)
        shutil.copy2(
            dist_root / 'EasycodeUpdateHelper.exe',
            dist_root / 'EasycodePlayer' / 'EasycodeUpdateHelper.exe',
        )
        built_runtime = dist_root / 'EasycodePlayer'
        write_player_runtime_contract(built_runtime)
        runtime_root = ROOT / 'dist' / DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME
        _replace_runtime_template(built_runtime, runtime_root)
    elif args.runtime_root:
        runtime_root = Path(args.runtime_root).resolve()
    else:
        runtime_root = ROOT / 'dist' / DEFAULT_PLAYER_RUNTIME_TEMPLATE_NAME
    if not (runtime_root / 'EasycodePlayer.exe').is_file():
        parser.error(f'冻结 Runtime 不存在：{runtime_root}；请传入 --runtime-root 或使用 --rebuild-runtime')
    assembler = VNextDistributionAssembler(
        runtime_root, ROOT / 'release' / 'player-web',
        require_current_runtime=True,
    )
    result = assembler.assemble(args.bundle, args.output)
    print(f'Player 已生成：{result["path"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
