# core/security.py
import os
import json
import tempfile
from fastapi import HTTPException


def assert_safe_path(base_dir: str, target_path: str) -> str:
    """
    路径校验防护：确保目标绝对路径严格包含在 base_dir 范围内，防止 ../ 跨目录越权访问
    """
    if not base_dir or not target_path:
        raise HTTPException(status_code=400, detail="路径参数不能为空")

    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(os.path.join(base_dir, target_path))

    if not abs_target.startswith(abs_base):
        raise HTTPException(status_code=403, detail="非法路径访问：受限于项目根目录操作")

    return abs_target


def atomic_write_json(file_path: str, data: dict, indent: int = 2):
    """
    文件原子化落盘：先写入临时文件，写入完成后通过 OS 级别 replace 替换，防止写入中断损坏 JSON
    """
    dir_name = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(dir_name, exist_ok=True)

    try:
        with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=indent, ensure_ascii=False)
            temp_name = tf.name

        os.replace(temp_name, file_path)
    except Exception as e:
        if 'temp_name' in locals() and os.path.exists(temp_name):
            os.remove(temp_name)
        raise IOError(f"原子写入文件失败 [{file_path}]: {str(e)}")