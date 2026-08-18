# tests/test_uia_com_init.py
# ⚡ 回归：UIA 查找在「线程池线程」执行时必须先 CoInitialize。
# 此前 executor/SSE 线程池里直接调 UIA → [WinError -2147221008] 尚未调用 CoInitialize → 控件查找全部失败。
import threading


def test_uia_find_in_pool_thread_no_coiniterror(monkeypatch):
    """线程池线程执行 UIA 查找：不再抛 CoInitialize 错误（_ensure_com 先行）"""
    from core.services import uia_service

    # 模拟 uiautomation 线程初始化入口
    inited_threads = []

    class FakeAuto:
        @staticmethod
        def InitializeUIAutomationInCurrentThread():
            inited_threads.append(threading.get_ident())
            # 模拟真实行为：重复初始化抛 RPC_E_CHANGED_MODE 类错误
            raise OSError(-2147417850, 'RPC_E_CHANGED_MODE')

    import sys
    import types
    fake_mod = types.ModuleType('uiautomation')
    fake_mod.InitializeUIAutomationInCurrentThread = FakeAuto.InitializeUIAutomationInCurrentThread
    monkeypatch.setitem(sys.modules, 'uiautomation', fake_mod)

    # 清掉模块级 tls 缓存（测试间隔离）
    uia_service._com_tls = threading.local()

    results = {}

    def worker():
        try:
            uia_service._ensure_com()
            results['ok'] = True
            results['inited'] = len(inited_threads)
        except Exception as e:
            results['error'] = repr(e)

    # 两个不同线程各自初始化
    t1 = threading.Thread(target=worker)
    t1.start()
    t1.join()
    t2 = threading.Thread(target=worker)
    t2.start()
    t2.join()

    assert 'error' not in results, results
    assert results['ok'] is True
    # 每个线程都尝试过初始化（两次调用两个线程）
    assert len(inited_threads) == 2
