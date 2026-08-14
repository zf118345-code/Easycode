"""路径安全与原子写入单元测试

验证：
- assert_safe_path 拒绝目录穿越攻击
- assert_safe_path 允许合法子路径
- atomic_write_json 原子写入并读取回环
"""

import json
import os

import pytest

from core.security import assert_safe_path, atomic_write_json


class TestAssertSafePath:
    def test_valid_subpath_ok(self, tmp_path):
        """合法子路径应通过"""
        base = str(tmp_path)
        target = str(tmp_path / 'subdir' / 'file.json')
        result = assert_safe_path(base, target)
        assert result == target

    def test_path_traversal_blocked(self, tmp_path):
        """目录穿越 ../ 应被拒绝"""
        base = str(tmp_path / 'project')
        os.makedirs(base, exist_ok=True)
        evil = str(tmp_path / 'project' / '..' / '..' / 'etc' / 'passwd')
        with pytest.raises(ValueError, match='安全违规'):
            assert_safe_path(base, evil)

    def test_exact_base_path_ok(self, tmp_path):
        """恰好等于 base 路径应通过"""
        base = str(tmp_path)
        result = assert_safe_path(base, base)
        assert result == base

    def test_empty_base_returns_target(self):
        """空 base 应直接返回 target（不校验）"""
        assert assert_safe_path('', '/some/path') == '/some/path'

    def test_empty_target_returns_target(self, tmp_path):
        """空 target 应直接返回"""
        assert assert_safe_path(str(tmp_path), '') == ''

    def test_sibling_dir_blocked(self, tmp_path):
        """同层兄弟目录应被拒绝（前缀相似但不同目录，防止 startswith 碰撞）"""
        base = str(tmp_path / 'demo')
        os.makedirs(base, exist_ok=True)
        sibling = str(tmp_path / 'demo_evil')
        os.makedirs(sibling, exist_ok=True)
        with pytest.raises(ValueError, match='安全违规'):
            assert_safe_path(base, sibling)


class TestAtomicWriteJson:
    def test_write_and_read_roundtrip(self, tmp_path):
        """写入后读取应一致"""
        file_path = str(tmp_path / 'data.json')
        data = {'name': '测试', 'count': 42, 'items': [1, 2, 3]}
        atomic_write_json(file_path, data)
        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_overwrite_existing(self, tmp_path):
        """覆盖已存在文件应成功"""
        file_path = str(tmp_path / 'data.json')
        atomic_write_json(file_path, {'v': 1})
        atomic_write_json(file_path, {'v': 2})
        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == {'v': 2}

    def test_creates_parent_dir(self, tmp_path):
        """目标目录不存在时应自动创建"""
        file_path = str(tmp_path / 'deep' / 'nested' / 'dir' / 'data.json')
        atomic_write_json(file_path, {'ok': True})
        assert os.path.exists(file_path)

    def test_unicode_content(self, tmp_path):
        """Unicode 内容应正确写入"""
        file_path = str(tmp_path / 'unicode.json')
        data = {'中文': '测试内容', 'emoji': 'hello', 'nested': {'键': '值'}}
        atomic_write_json(file_path, data)
        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded == data

    def test_strips_transient_fields(self, tmp_path):
        """以 _ 开头的瞬态私有字段应被过滤"""
        file_path = str(tmp_path / 'clean.json')
        data = {'public': 1, '_private_runtime': 2, 'nested': {'keep': 3, '_drop': 4}}
        atomic_write_json(file_path, data)
        with open(file_path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert 'public' in loaded
        assert '_private_runtime' not in loaded
        assert loaded['nested']['keep'] == 3
        assert '_drop' not in loaded['nested']
