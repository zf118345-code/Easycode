"""api.py - 兼容入口，实际逻辑已拆分到 api/ 包。"""

import sys

if __name__ == '__main__':
    import multiprocessing

    multiprocessing.freeze_support()

# The packaged executable also hosts killable custom-capability workers.
# Branch before importing ``api.app``: importing the full server initializes
# vision, capture and desktop integrations and would make every worker slow and
# unnecessarily coupled to the GUI process.
if __name__ == "__main__" and '--capability-worker' in sys.argv:
    from core.services.capability_worker import main as capability_worker_main

    raise SystemExit(capability_worker_main())

# The reusable frozen Player runtime also hosts the single per-user schedule
# Agent.  Branch before importing FastAPI/pywebview: a background wake process
# must not create an IDE window or bind an HTTP port.
if __name__ == "__main__" and '--player-hub-agent' in sys.argv:
    from core.vnext.schedule_hub_v6 import main as player_hub_main

    raise SystemExit(player_hub_main(['agent']))

from api.app import app, start_webview  # noqa: E402

if __name__ == "__main__":
    import argparse
    import logging
    import os
    import threading
    import uvicorn

    # Windows 后台启动并重定向日志时，Python 可能沿用系统 GBK。运行日志中
    # 包含中文和状态 Emoji，编码失败绝不能中断执行线程。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except (AttributeError, OSError, ValueError):
            # PyInstaller/pywebview 无控制台时流可能为 None 或无有效句柄。
            pass

    parser = argparse.ArgumentParser(description="Easycode 后端引擎")
    parser.add_argument("--mode", type=str, default="dev", choices=["dev", "prod"])
    parser.add_argument("--host", default="127.0.0.1", help="监听地址；局域网协调服务可使用 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--player-bundle", default="", help="要加载的 vNext .ecplayer 运行包")
    parser.add_argument("--player-trust-root", default="", help="Player 固定的发布者信任根")
    args = parser.parse_args()

    if args.player_bundle:
        os.environ['EASYCODE_PLAYER_BUNDLE'] = os.path.abspath(args.player_bundle)
    if args.player_trust_root:
        os.environ['EASYCODE_PLAYER_TRUST_ROOT'] = os.path.abspath(args.player_trust_root)
        os.environ['EASYCODE_PLAYER_REQUIRE_TRUST_ROOT'] = '1'

    if args.host not in {"127.0.0.1", "localhost", "::1"} and not os.environ.get("EASYCODE_COORDINATOR_TOKEN"):
        parser.error("监听非本机地址时必须设置 EASYCODE_COORDINATOR_TOKEN")

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
            uvicorn.run(app, host=args.host, port=args.port, log_level="error")
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        start_webview()
    else:
        print("FastAPI 后端引擎运行中 (开发模式)...")
        # log_level=warning：关闭 uvicorn 访问日志（轮询/请求不再刷屏），
        # 应用日志（捕获活动/错误）由 logging.basicConfig 独立输出，不受影响
        uvicorn.run(app, host=args.host, port=args.port, reload=False, log_level="warning")
