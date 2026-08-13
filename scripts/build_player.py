# scripts/build_player.py
import os
import shutil
import subprocess
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from core.services.export_service import ExportService
from core.builder.exporter import ProjectExporter


def log_step(step_num, title):
    print(f"\n==================================================")
    print(f"[CHECKPOINT {step_num}] {title}")
    print(f"==================================================")


def run_build_pipeline():
    print("开始执行 Easycode Player 客户端全量监控打包流水线...\n")
    os.chdir(root_dir)

    # ==============================================================================
    # 监测点 1：校验项目路径环境变量
    # ==============================================================================
    log_step(1, "校验项目路径环境变量")
    project_path = os.environ.get("EASYCODE_EXPORT_PROJECT_PATH")
    print(f"-> 接收到的项目路径参数: {project_path}")

    if not project_path or not os.path.exists(project_path):
        print(f"[错误] 致命拦截: 找不到有效的项目路径！")
        sys.exit(1)
    print("[通过] 项目路径合法，锁定项目目录。")

    # ==============================================================================
    # 监测点 2：校验前端网页产物 (release/web)
    # ==============================================================================
    log_step(2, "校验前端网页编译产物")
    src_web = os.path.join("release", "web")
    index_html = os.path.join(src_web, "index.html")
    print(f"-> 检查前端目录: {os.path.abspath(src_web)}")

    if not os.path.exists(index_html):
        print(f"[错误] 致命拦截: 找不到前端打包后的 index.html！请先执行 npm run build")
        sys.exit(1)
    print("[通过] 前端精简网页产物完整。")

    # ==============================================================================
    # 监测点 3：PyInstaller 后端引擎内核编译
    # ==============================================================================
    log_step(3, "编译 Python 引擎二进制核心 (.exe)")
    spec_path = os.path.join("scripts", "player.spec")
    if not os.path.exists(spec_path):
        print(f"[错误] 致命拦截: 找不到 PyInstaller 配置文件: {spec_path}")
        sys.exit(1)

    build_cmd = [sys.executable, "-m", "PyInstaller", spec_path, "--clean", "--noconfirm"]
    print(f"-> 执行编译命令: {' '.join(build_cmd)}")

    try:
        subprocess.check_call(build_cmd)
        print("[通过] 后端引擎二进制编译成功。")
    except subprocess.CalledProcessError as e:
        print(f"[错误] 致命拦截: PyInstaller 编译崩溃 (ExitCode: {e.returncode})")
        sys.exit(1)

    # ==============================================================================
    # 监测点 4：使用项目原生的 ProjectExporter 生成合法的 AES 加密密包 (assets.ebp)
    # ==============================================================================
    log_step(4, "生成项目加密资产密包 (assets.ebp)")
    # 优化后 (每个项目拥有独立的交付目录)
    dist_folder = os.path.join(project_path, "dist", "Player_Bundle")
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)
    os.makedirs(dist_folder, exist_ok=True)

    release_dir = os.path.join(dist_folder, "release")
    os.makedirs(release_dir, exist_ok=True)

    target_ebp = os.path.join(release_dir, "assets.ebp")
    print(f"-> 正在调用原生导出器为项目安全生成加密密包: {project_path}")

    try:
        # 获取动态表单 Schema 并直接通过工业级 ProjectExporter 进行 AES 加密打包
        form_schema = ExportService.get_form_schema(project_path)
        ProjectExporter.build_export_bundle(project_path, form_schema, output_dir=release_dir)

        if os.path.exists(target_ebp) and os.path.getsize(target_ebp) > 0:
            print(f"[通过] 正宗的 AES 加密 assets.ebp 密包生成成功！大小: {os.path.getsize(target_ebp)} 字节")
        else:
            # 降级备用：如果指定目录没找到，去全局找
            fallback_src = os.path.join("release", "assets.ebp")
            if os.path.exists(fallback_src):
                shutil.copy2(fallback_src, target_ebp)
                print(f"[通过] 已成功从默认路径挂载加密密包！大小: {os.path.getsize(target_ebp)} 字节")
            else:
                raise Exception("导出执行完毕，但未能落盘生成合法的 assets.ebp 文件。")

    except Exception as e:
        print(f"[错误] 致命拦截: 生成加密密包异常 -> {str(e)}")
        sys.exit(1)

    # ==============================================================================
    # 监测点 5：最终组装与完整性盘点
    # ==============================================================================
    log_step(5, "最终交付目录组装与完整性盘点")

    # 5.1 移动 exe
    exe_src = os.path.join("dist", "EasycodePlayer.exe")
    exe_dst = os.path.join(dist_folder, "EasycodePlayer.exe")
    if os.path.exists(exe_src):
        shutil.move(exe_src, exe_dst)
        print("-> [组装] EasycodePlayer.exe 已就位")
    else:
        print(f"[错误] 致命拦截: 未在 dist 目录找到编译产物: {exe_src}")
        sys.exit(1)

    # 5.2 复制前端网页
    target_web = os.path.join(release_dir, "web")
    if os.path.exists(target_web):
        shutil.rmtree(target_web)
    shutil.copytree(src_web, target_web)
    print("-> [组装] release/web 网页目录已挂载")

    # 5.3 复制 user_config.json 模板（若存在）
    config_src = os.path.join(release_dir, "user_config.json")
    if not os.path.exists(config_src):
        config_src = os.path.join("release", "user_config.json")
        if os.path.exists(config_src):
            shutil.copy2(config_src, os.path.join(release_dir, "user_config.json"))

    # 5.4 创建 bat 引导脚本
    bat_path = os.path.join(dist_folder, "启动脚本助手.bat")
    with open(bat_path, "w", encoding="gbk") as f:
        f.write("@echo off\n")
        f.write("chcp 65001 >nul\n")
        f.write("title Easycode 自动化运行助手\n")
        f.write("echo 正在启动自动化运行引擎与无边框客户端，请稍候...\n")
        f.write("EasycodePlayer.exe --mode prod\n")
    print("-> [组装] 启动脚本助手.bat 已生成")

    print(f"\n==================================================")
    print("【打包成功】所有监控点全部通过！")
    print(f"客户最终交付文件夹: {os.path.abspath(dist_folder)}")
    print(f"==================================================")


if __name__ == "__main__":
    run_build_pipeline()