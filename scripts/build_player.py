# scripts/build_player.py
import os
import shutil
import subprocess
import sys
import json
from datetime import datetime, timezone

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

def log_step(step_num, title):
    print(f"\n==================================================")
    print(f"[CHECKPOINT {step_num}] {title}")
    print(f"==================================================")


def safe_rmtree(path, allowed_root):
    resolved = os.path.abspath(path)
    root = os.path.abspath(allowed_root)
    if os.path.commonpath([resolved, root]) != root or resolved == root:
        raise RuntimeError(f"拒绝删除不安全路径: {resolved}")
    if os.path.exists(resolved):
        shutil.rmtree(resolved)


def verify_delivery_bundle(bundle_dir):
    """Fail the release before replacing latest when any runtime boundary is incomplete."""
    required = [
        'EasycodePlayer.exe',
        os.path.join('_internal', 'native', 'CaptureOverlay', 'EasycodeCaptureOverlay.exe'),
        os.path.join('_internal', 'native', 'CaptureOverlay', 'Microsoft.Web.WebView2.Core.dll'),
        os.path.join('_internal', 'native', 'CaptureOverlay', 'Microsoft.Web.WebView2.WinForms.dll'),
        os.path.join('_internal', 'native', 'CaptureOverlay', 'WebView2Loader.dll'),
        os.path.join('_internal', 'uiautomation', 'bin', 'UIAutomationClient_VC140_X64.dll'),
        os.path.join('_internal', 'uiautomation', 'bin', 'UIAutomationClient_VC140_X86.dll'),
        os.path.join('release', 'assets.ebp'),
        os.path.join('release', 'web', 'index.html'),
        os.path.join('release', 'web', 'player.html'),
        os.path.join('release', 'web', 'capture.html'),
    ]
    missing = [relative for relative in required if not os.path.isfile(os.path.join(bundle_dir, relative))]
    leaked_profile = os.path.join(
        bundle_dir,
        '_internal',
        'native',
        'CaptureOverlay',
        'EasycodeCaptureOverlay.exe.WebView2',
    )
    if missing:
        raise RuntimeError(f"交付包缺少必要文件: {', '.join(missing)}")
    if os.path.exists(leaked_profile):
        raise RuntimeError(f'交付包混入 WebView2 用户数据: {leaked_profile}')
    return required


def run_build_pipeline():
    # Heavy engine imports stay inside the actual build path so delivery-bundle
    # verification remains usable without loading FastAPI/CV/OCR runtimes.
    from core.builder.exporter import ProjectExporter
    from core.services.export_service import ExportService
    from core.services.native_capture_overlay import NativeCaptureOverlay

    print("开始执行 Easycode Player 客户端全量监控打包流水线...\n")
    os.chdir(root_dir)

    # ==============================================================================
    # 监测点 1：校验项目路径环境变量
    # ==============================================================================
    log_step(1, "校验项目路径环境变量")
    project_path = os.environ.get("EASYCODE_EXPORT_PROJECT_PATH")
    output_project_path = os.environ.get("EASYCODE_OUTPUT_PROJECT_PATH")
    print(f"-> 接收到的项目路径参数: {project_path}")

    if not project_path or not os.path.exists(project_path):
        print(f"[错误] 致命拦截: 找不到有效的项目路径！")
        sys.exit(1)
    print("[通过] 项目路径合法，锁定项目目录。")
    if not output_project_path or not os.path.isdir(output_project_path):
        print("[错误] 致命拦截: 找不到有效的交付输出项目路径！")
        sys.exit(1)
    project_path = os.path.abspath(project_path)
    output_project_path = os.path.abspath(output_project_path)

    # ==============================================================================
    # 监测点 2：校验前端网页产物 (release/web)
    # ==============================================================================
    log_step(2, "校验前端网页编译产物")
    src_web = os.path.join("release", "web")
    index_html = os.path.join(src_web, "index.html")
    player_html = os.path.join(src_web, "player.html")
    print(f"-> 检查前端目录: {os.path.abspath(src_web)}")

    if not os.path.exists(index_html) or not os.path.exists(player_html):
        print(f"[错误] 致命拦截: 前端入口不完整（需要 index.html 与 player.html）！请先执行 npm run build")
        sys.exit(1)
    print("[通过] 前端精简网页产物完整。")

    # 原生桌面宿主必须是发布前生成的固定工件；客户端运行时绝不调用编译器。
    log_step(3, "编译并校验原生 WebView2 桌面宿主")
    try:
        native_host = NativeCaptureOverlay.ensure_binary()
        if not native_host.is_file():
            raise RuntimeError(f"宿主编译完成但产物不存在: {native_host}")
        print(f"[通过] 原生桌面宿主已就位: {native_host}")
    except Exception as exc:
        print(f"[错误] 致命拦截: 原生桌面宿主不可发布 -> {exc}")
        sys.exit(1)

    # ==============================================================================
    # 监测点 3：PyInstaller 后端引擎内核编译
    # ==============================================================================
    log_step(4, "编译 Python 引擎二进制核心（onedir）")
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
    log_step(5, "生成项目加密资产密包 (assets.ebp)")
    # 优化后 (每个项目拥有独立的交付目录)
    project_dist = os.path.abspath(os.path.join(output_project_path, "dist"))
    dist_folder = os.path.join(project_dist, "Player_Bundle")
    staging_folder = os.path.join(project_dist, f".Player_Bundle-building-{os.getpid()}")
    backup_folder = os.path.join(project_dist, ".Player_Bundle-previous")
    os.makedirs(project_dist, exist_ok=True)
    safe_rmtree(staging_folder, project_dist)
    os.makedirs(staging_folder, exist_ok=True)

    release_dir = os.path.join(staging_folder, "release")
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
            raise Exception("导出执行完毕，但未能落盘生成合法的 assets.ebp 文件。")

    except Exception as e:
        print(f"[错误] 致命拦截: 生成加密密包异常 -> {str(e)}")
        sys.exit(1)

    # ==============================================================================
    # 监测点 5：最终组装与完整性盘点
    # ==============================================================================
    log_step(6, "最终交付目录组装与完整性盘点")

    # 6.1 复制 onedir 运行时。保留依赖文件可避免 onefile 每次启动解压。
    runtime_src = os.path.join("dist", "EasycodePlayer")
    exe_src = os.path.join(runtime_src, "EasycodePlayer.exe")
    if os.path.isdir(runtime_src) and os.path.exists(exe_src):
        shutil.copytree(runtime_src, staging_folder, dirs_exist_ok=True)
        print("-> [组装] EasycodePlayer onedir 运行时已就位")
    else:
        print(f"[错误] 致命拦截: 未在 dist 目录找到 onedir 编译产物: {runtime_src}")
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
    bat_path = os.path.join(staging_folder, "启动脚本助手.bat")
    with open(bat_path, "w", encoding="gbk") as f:
        f.write("@echo off\n")
        f.write("chcp 65001 >nul\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("title Easycode 自动化运行助手\n")
        f.write("echo 正在启动自动化运行引擎与无边框客户端，请稍候...\n")
        f.write("EasycodePlayer.exe --mode prod\n")
    print("-> [组装] 启动脚本助手.bat 已生成")

    # 5.5 构建清单 + 原子替换 latest；只有完整组装成功后才覆盖上一次可用交付包。
    built_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    manifest = {
        "product": "Easycode Player",
        "project": os.path.basename(output_project_path),
        "built_at": built_at,
        "schema_version": int(form_schema.get("schema_version", 1)),
        "entry": form_schema.get("entry"),
        "package_mode": "onedir",
        "desktop_shell": "native-webview2",
    }
    with open(os.path.join(staging_folder, "build_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    verified_files = verify_delivery_bundle(staging_folder)
    print(f"-> [校验] 交付包 {len(verified_files)} 项运行边界全部通过，且未混入 WebView2 用户数据")

    safe_rmtree(backup_folder, project_dist)
    if os.path.exists(dist_folder):
        os.replace(dist_folder, backup_folder)
    try:
        os.replace(staging_folder, dist_folder)
    except Exception:
        if os.path.exists(backup_folder) and not os.path.exists(dist_folder):
            os.replace(backup_folder, dist_folder)
        raise
    safe_rmtree(backup_folder, project_dist)

    # 5.6 保留带时间戳的 ZIP 历史，latest 始终固定在 dist/Player_Bundle。
    history_dir = os.path.join(project_dist, "history")
    os.makedirs(history_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_base = os.path.join(history_dir, f"Player_Bundle-{stamp}")
    history_zip = shutil.make_archive(archive_base, "zip", root_dir=dist_folder)
    print(f"-> [归档] 已生成版本历史: {history_zip}")

    print(f"\n==================================================")
    print("【打包成功】所有监控点全部通过！")
    print(f"客户最终交付文件夹: {os.path.abspath(dist_folder)}")
    print(f"版本归档文件: {os.path.abspath(history_zip)}")
    print(f"==================================================")


if __name__ == "__main__":
    run_build_pipeline()
