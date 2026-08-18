"""api.py - 兼容入口，实际逻辑已拆分到 api/ 包"""
from api.app import app, start_webview

if __name__ == "__main__":
    import argparse
    import logging
    import threading
    import uvicorn

    parser = argparse.ArgumentParser(description="Easycode 后端引擎")
    parser.add_argument("--mode", type=str, default="dev", choices=["dev", "prod"])
    args = parser.parse_args()

    # ⚡ 应用日志必须可见（否则默认 WARNING 级别会吞掉 INFO：捕获活动无迹可查，问题无法定位）
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True)
    # ⚡ 原生崩溃兜底：UIA/COM 偶发 Access Violation 时打印 Python 调用栈（否则进程无声退出无法定位）
    import faulthandler
    faulthandler.enable()

    if args.mode == "prod":
        def run_server():
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview()
    else:
        print("FastAPI 后端引擎运行中 (开发模式)...")
        # log_level=warning：关闭 uvicorn 访问日志（轮询/请求不再刷屏），
        # 应用日志（捕获活动/错误）由 logging.basicConfig 独立输出，不受影响
        uvicorn.run(app, host="127.0.0.1", port=8000, reload=False, log_level="warning")
