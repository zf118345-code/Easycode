# main.py
import os
import argparse
import logging
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
    parser.add_argument("--project", default="demo", help="项目名称或绝对路径")
    parser.add_argument("--task", default="main_task", help="要运行的任务 ID")
    args = parser.parse_args()

    setup_logging()

    # 解析项目路径
    if os.path.isabs(args.project) or os.path.exists(args.project):
        project_dir = args.project
    else:
        project_dir = os.path.join("projects", args.project)

    if not os.path.exists(project_dir):
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