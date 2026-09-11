"""Build the frozen installer and one self-contained offline Windows media directory."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.windows_installation_v6 import WindowsInstallerMediaV6  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 EasyCode Windows 离线安装介质")
    parser.add_argument("--distribution", required=True, help="已组装的 Player_Bundle 目录")
    parser.add_argument("--output", required=True, help="输出根目录")
    parser.add_argument("--installer-executable", default="", help="复用已冻结的 EasycodeInstaller.exe")
    parser.add_argument("--rebuild-installer", action="store_true", help="重新冻结安装程序")
    parser.add_argument("--work-root", default="D:/EasyCodeBuild/installer-work")
    parser.add_argument("--dist-root", default="D:/EasyCodeBuild/installer-dist")
    args = parser.parse_args(argv)

    installer = Path(args.installer_executable).resolve() if args.installer_executable else Path(args.dist_root).resolve() / "EasycodeInstaller.exe"
    if args.rebuild_installer:
        work_root = Path(args.work_root).resolve()
        dist_root = Path(args.dist_root).resolve()
        work_root.mkdir(parents=True, exist_ok=True)
        dist_root.mkdir(parents=True, exist_ok=True)
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", str(ROOT / "scripts" / "installer.spec"),
            "--clean", "--noconfirm", "--workpath", str(work_root), "--distpath", str(dist_root),
        ], cwd=ROOT)
        installer = dist_root / "EasycodeInstaller.exe"
    if not installer.is_file():
        parser.error(f"找不到冻结安装程序：{installer}；请传入 --installer-executable 或使用 --rebuild-installer")

    result = WindowsInstallerMediaV6.build(
        Path(args.distribution).resolve(),
        Path(args.output).resolve(),
        installer_executable=installer,
    )
    print(f"Windows 安装介质已生成：{result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
