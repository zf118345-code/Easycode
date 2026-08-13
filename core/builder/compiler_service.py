# core/builder/compiler_service.py
import os
import subprocess
import sys
from fastapi import HTTPException


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
            raise HTTPException(status_code=400, detail="编译失败：前端未传递 project_path 参数！")
        if not os.path.exists(project_path):
            raise HTTPException(status_code=404, detail=f"编译失败：项目路径不存在 -> {project_path}")

        # 定位根目录下的 scripts/build_player.py
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        build_script = os.path.join(root_dir, "scripts", "build_player.py")

        if not os.path.exists(build_script):
            raise HTTPException(status_code=404, detail=f"找不到编译脚本: {build_script}")

        try:
            # 通过环境变量将项目路径传递给打包脚本
            env = os.environ.copy()
            env["EASYCODE_EXPORT_PROJECT_PATH"] = project_path

            print(f"\n[CompilerService] 正在触发子进程编译，目标项目: {project_path}")

            # 启动子进程
            process = subprocess.Popen(
                [sys.executable, build_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=root_dir,
                env=env
            )

            stdout, stderr = process.communicate(timeout=300)

            # ⚡ 关键增强：无论成功与否，把子进程的输出强制打印到 PyCharm 控制台！
            if stdout:
                print("--- [Build Script STDOUT] ---")
                print(stdout)
            if stderr:
                print("--- [Build Script STDERR] ---")
                print(stderr)

            if process.returncode != 0:
                raise Exception(f"子进程编译返回码非 0 ({process.returncode})。\n错误详情见上方日志。")

            dist_bundle_dir = os.path.join(root_dir, "dist", "EasycodePlayer_Bundle")
            return {
                "success": True,
                "message": "Player 客户端编译打包与资产组装成功！",
                "output_dir": os.path.abspath(dist_bundle_dir),
                "logs": stdout[-500:]
            }
        except subprocess.TimeoutExpired:
            process.kill()
            raise HTTPException(status_code=500, detail="编译超时（超过 5 分钟），请检查 PyInstaller 环境")
        except Exception as e:
            print(f"[CompilerService Error] {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))