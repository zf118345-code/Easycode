# main.py
import sys
import os
import argparse
import logging
from core.models import Project, Task, Node, Jump, ExecutionCondition
from core.executor import GraphExecutor
from core.utils import load_json, resource_path
from core.node_executors import *
from core.project_loader import load_project

def setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="启动可视化UI")
    parser.add_argument("--task", default="main_task", help="要运行的任务ID")
    args = parser.parse_args()

    if args.ui:
        import customtkinter as ctk
        from ui_main import MainUI
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        app = MainUI()
        app.mainloop()
        return

    setup_logging()
    project_dir = os.path.join("projects", "demo")
    if not os.path.exists(project_dir):
        print(f"项目目录不存在: {project_dir}")
        return
    project = load_project(project_dir)
    executor = GraphExecutor(project, text_log_enabled=True, image_log_enabled=True)
    executor.run(args.task)

if __name__ == "__main__":
    main()