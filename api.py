"""api.py - 兼容入口，实际逻辑已拆分到 api/ 包"""
from api.app import app, start_webview

if __name__ == "__main__":
    import argparse
    import threading
    import uvicorn

    parser = argparse.ArgumentParser(description="Easycode 后端引擎")
    parser.add_argument("--mode", type=str, default="dev", choices=["dev", "prod"])
    args = parser.parse_args()

    if args.mode == "prod":
        def run_server():
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview()
    else:
        print("FastAPI 后端引擎运行中 (开发模式)...")
        uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
