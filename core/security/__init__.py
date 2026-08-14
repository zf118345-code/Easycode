# core/security/__init__.py
import json
import os

from core.security.crypto import SecureAssetCrypto
from core.security.licensing import LicenseManager


def atomic_write_json(file_path: str, data: dict) -> None:
    """
    工业级原子文件写入工具
    先写入临时文件，再通过系统原子的 replace 操作覆盖目标文件，防止并发读写或中断导致 JSON 文件损坏
    同时过滤掉所有以 '_' 开头的瞬态私有字段（如 _memory_templates 运行时内存矩阵），防止 ndarray 序列化崩溃
    """
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    def clean_transient_fields(obj):
        if isinstance(obj, dict):
            return {
                k: clean_transient_fields(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith('_'))
            }
        elif isinstance(obj, list):
            return [clean_transient_fields(item) for item in obj]
        return obj

    cleaned_data = clean_transient_fields(data)

    temp_path = f'{file_path}.tmp'
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    if os.path.exists(file_path):
        os.replace(temp_path, file_path)
    else:
        os.rename(temp_path, file_path)


def assert_safe_path(base_dir: str, target_path: str) -> str:
    """
    工业级路径安全断言（防御目录穿越 / Path Traversal 攻击）
    确保目标路径绝对位于基础目录内部

    修复：使用 normcase + 分隔符前缀检查，防止兄弟目录前缀碰撞
    (例如 /demo 与 /demo_evil 被 startswith 误判为父子关系)
    """
    if not base_dir or not target_path:
        return target_path

    norm_base = os.path.normcase(os.path.abspath(base_dir))
    norm_target = os.path.normcase(os.path.abspath(target_path))

    # 确保 base 路径结尾带分隔符，防止 /demo 与 /demo_evil 的前缀碰撞
    base_prefix = norm_base if norm_base.endswith(os.sep) else norm_base + os.sep

    if norm_target != norm_base and not norm_target.startswith(base_prefix):
        raise ValueError(f'安全违规：非法的越权文件路径访问 -> {target_path}')

    return str(target_path)


__all__ = ['LicenseManager', 'SecureAssetCrypto', 'atomic_write_json', 'assert_safe_path']
