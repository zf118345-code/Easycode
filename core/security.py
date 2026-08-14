# core/security.py
import contextlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

# 全局线程锁：防止多线程并发原子写入同一个文件引发文件冲突
_write_lock = threading.Lock()


def assert_safe_path(base_path: str, target_path: str) -> str:
    """
    校验目标路径是否处于项目基础目录内部，防止目录穿越攻击
    针对 Windows 盘符大小写、斜杠以及未创建路径进行了彻底规范化处理
    """
    if not base_path or not target_path:
        return target_path
    try:
        # 使用 abspath + normcase 统一转为绝对路径与小写，彻底避免 Windows 盘符大小写与 realpath 差异
        norm_base = os.path.normcase(os.path.abspath(base_path))
        norm_target = os.path.normcase(os.path.abspath(target_path))

        # 确保 base 路径结尾带有路径分隔符，防止 prefix 误判 (例如 /demo 与 /demo_2)
        base_prefix = norm_base if norm_base.endswith(os.sep) else norm_base + os.sep

        if norm_target != norm_base and not norm_target.startswith(base_prefix):
            raise HTTPException(status_code=400, detail='非法路径越界操作')

        return str(target_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'路径校验失败: {str(e)}') from e


def atomic_write_json(file_path: str, data: Any, indent: int = 2, max_retries: int = 5):
    """
    带 Windows 重试机制与线程安全锁的原子 JSON 写入函数
    """
    target_path = Path(file_path).resolve()
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    with _write_lock:
        temp_file = None
        try:
            # 1. 在目标文件同目录下创建临时文件
            temp_file = tempfile.NamedTemporaryFile(mode='w', dir=str(target_dir), delete=False, encoding='utf-8')  # noqa: SIM115
            temp_name = temp_file.name

            # 2. 写入 JSON 数据
            json.dump(data, temp_file, ensure_ascii=False, indent=indent)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()  # 必须显式关闭临时文件句柄，否则 Windows 下 os.replace 会报拒绝访问

            # 3. 带重试机制的原子替换 (专门解决 Windows 下 WinError 5 拒绝访问)
            for attempt in range(max_retries):
                try:
                    os.replace(temp_name, str(target_path))
                    break  # 替换成功，退出重试循环
                except (PermissionError, OSError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.05 * (attempt + 1))  # 递增休眠 50ms, 100ms...
                    else:
                        raise e

        except Exception as e:
            # 如果中途报错，清理残留的临时文件
            if temp_file and os.path.exists(temp_file.name):
                with contextlib.suppress(Exception):
                    os.remove(temp_file.name)
            raise OSError(f'原子写入文件失败 [{file_path}]: {str(e)}') from e
