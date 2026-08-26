# main.py
import argparse
import logging
from pathlib import Path
from core.services.dpi_service import enable_per_monitor_v2

enable_per_monitor_v2()

from core.executor import GraphExecutor
from core.project_loader import load_project
import core.node_executors  # 触发节点注册

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(description="Easycode 自动化脚本 CLI 执行器")
    parser.add_argument("--project", required=True, help="EasyCode 项目文件夹的绝对路径")
    parser.add_argument("--task", required=True, help="要运行的任务 ID")
    args = parser.parse_args()

    setup_logging()

    supplied = Path(args.project).expanduser()
    if not supplied.is_absolute():
        logging.error("--project 必须是绝对路径；CLI 不会扫描工作目录或 projects 文件夹")
        return
    project_dir = str(supplied.resolve())
    if not Path(project_dir).is_dir():
        logging.error(f"项目目录不存在: {project_dir}")
        return

    try:
        project = load_project(project_dir)
        executor = GraphExecutor(
            project,
            project_dir=project_dir,
            text_log_enabled=True,
            image_log_enabled=True
        )
        executor.run(args.task)
    except Exception as e:
        logging.error(f"执行任务失败: {e}", exc_info=True)

if __name__ == "__main__":
    main()
