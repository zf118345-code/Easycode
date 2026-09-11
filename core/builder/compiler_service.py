# core/builder/compiler_service.py
import logging
import os
import subprocess
import sys

from fastapi import HTTPException

from core.services.process_lifecycle import terminate_process_tree

logger = logging.getLogger(__name__)


class CompilerService:
    """
    工业级客户端编译调度服务
    负责安全地在独立子进程中触发 PyInstaller 编译管线，并实时回显日志
    """

    @classmethod
    def compile_player_exe(cls, project_path: str) -> dict:
        """
        触发编译打包 EasycodePlayer.exe 并组装分发目录
        """
        # 1. 强校验 project_path
        if not project_path:
            raise HTTPException(status_code=400, detail='编译失败：前端未传递 project_path 参数！')
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f'编译失败：项目路径不存在 -> {project_path}')

        from core.services.export_service import ExportService
        from core.services.preflight_service import PreflightService

        report = PreflightService.check(project_path, ExportService.get_form_schema(project_path))
        if report['counts']['error']:
            raise HTTPException(status_code=422, detail={'message': '发布前检查未通过', 'preflight': report})

        # 定位根目录下的 scripts/build_player.py
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        build_script = os.path.join(root_dir, 'scripts', 'build_player.py')

        if not os.path.exists(build_script):
            raise HTTPException(status_code=404, detail=f'找不到编译脚本: {build_script}')

        snapshot = None
        process: subprocess.Popen[str] | None = None
        try:
            # Build only from a fixed project revision.  The live workspace is
            # never read again by the child process while the build is running.
            from core.services.build_snapshot_service import BuildSnapshotService

            snapshot = BuildSnapshotService.create(project_path)
            env = os.environ.copy()
            env['EASYCODE_EXPORT_PROJECT_PATH'] = snapshot['path']
            env['EASYCODE_OUTPUT_PROJECT_PATH'] = os.path.abspath(project_path)

            print(f'\n[CompilerService] 正在触发子进程编译，目标项目: {project_path}')

            # 启动子进程
            process = subprocess.Popen(
                [sys.executable, build_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=root_dir,
                env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )

            stdout, stderr = process.communicate(timeout=300)

            # ⚡ 关键增强：无论成功与否，把子进程的输出强制打印到 PyCharm 控制台！
            if stdout:
                print('--- [Build Script STDOUT] ---')
                print(stdout)
            if stderr:
                print('--- [Build Script STDERR] ---')
                print(stderr)

            if process.returncode != 0:
                raise Exception(f'子进程编译返回码非 0 ({process.returncode})。\n错误详情见上方日志。')

            dist_bundle_dir = os.path.join(project_path, 'dist', 'Player_Bundle')
            history_dir = os.path.join(project_path, 'dist', 'history')
            history_zips = []
            if os.path.isdir(history_dir):
                history_zips = sorted(
                    (os.path.join(history_dir, name) for name in os.listdir(history_dir) if name.lower().endswith('.zip')),
                    key=os.path.getmtime,
                    reverse=True,
                )
            if not os.path.isfile(os.path.join(dist_bundle_dir, 'EasycodePlayer.exe')):
                raise Exception(f'编译进程结束，但交付目录不完整: {dist_bundle_dir}')
            from core.services.snapshot_service import SnapshotService

            SnapshotService.capture_current(project_path, 'build_exe')
            return {
                'success': True,
                'message': 'Player 客户端编译打包与资产组装成功！',
                'output_dir': os.path.abspath(dist_bundle_dir),
                'history_zip': os.path.abspath(history_zips[0]) if history_zips else None,
                'project_id': snapshot['project_id'],
                'revision': snapshot['revision'],
                'logs': stdout[-500:],
            }
        except subprocess.TimeoutExpired as exc:
            cleanup = terminate_process_tree(process)
            logger.error(
                'player.build.timeout',
                extra={
                    'event': 'player.build.timeout',
                    'project_path': os.path.abspath(project_path),
                    'child_pid': int(getattr(process, 'pid', 0) or 0),
                    'cleanup': cleanup,
                },
            )
            raise HTTPException(
                status_code=504,
                detail='编译超时（超过 5 分钟），已终止 PyInstaller 进程树，请检查构建环境',
            ) from exc
        except Exception as e:
            print(f'[CompilerService Error] {str(e)}')
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            if process is not None and process.poll() is None:
                terminate_process_tree(process)
            if snapshot:
                from core.services.build_snapshot_service import BuildSnapshotService

                BuildSnapshotService.remove(snapshot)
