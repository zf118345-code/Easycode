# core/builder/exporter.py
import io
import json
import os
import zipfile
from copy import deepcopy
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from core.player.schema import build_user_config, normalize_form_schema


class ProjectExporter:
    """
    工业级脚本打包与加密导出器
    负责将 IDE 项目（五份版本化项目文档、templates 资源与脚本）
    打造成带 DRM 加密的单文件二进制资产包 (.ebp)
    """

    # 默认固化的资产包导出专用对称加密 Key (实际生产可由特定机器码/卡密派生)
    DEFAULT_MASTER_KEY = b'EasycodeDRMMasterKey2026AES256!!'  # 32 bytes

    @staticmethod
    def _node_asset_references(value: Any) -> set[str]:
        references: set[str] = set()
        if isinstance(value, dict):
            for child in value.values():
                references.update(ProjectExporter._node_asset_references(child))
        elif isinstance(value, list):
            for child in value:
                references.update(ProjectExporter._node_asset_references(child))
        elif isinstance(value, str) and value.startswith('asset://'):
            references.add(value)
        return references

    @staticmethod
    def _called_functions(graph: dict[str, Any]) -> set[str]:
        return {
            str((node.get('params') or {}).get('function_id') or '').strip()
            for node in graph.get('nodes') or []
            if isinstance(node, dict) and node.get('node_type') == 'call_function'
            and str((node.get('params') or {}).get('function_id') or '').strip()
        }

    @classmethod
    def _trim_blueprint(cls, blueprint: dict[str, Any], form_schema: dict[str, Any]) -> dict[str, Any]:
        """Create the minimal, executable v3 release closure.

        The main graph is the only Player root.  Referenced functions are kept
        transitively; page-map data is kept only when an included graph can use
        Smart Jump.  Functions whose nodes are deliberately exposed in the
        Player form are also retained so declared overrides never become
        dangling after packaging.
        """
        main_graph = deepcopy(blueprint.get('main_graph') or {})
        functions = {
            str(item.get('function_id')): item
            for item in blueprint.get('functions') or []
            if isinstance(item, dict) and item.get('function_id')
        }
        required = set(cls._called_functions(main_graph))

        exposed_node_ids = set()
        for group in form_schema.get('groups') or []:
            for field in group.get('fields') or []:
                target = str(field.get('target') or '') if isinstance(field, dict) else ''
                if target.startswith('$node.'):
                    parts = target.split('.', 2)
                    if len(parts) == 3 and parts[1]:
                        exposed_node_ids.add(parts[1])
        for function_id, function in functions.items():
            node_ids = {
                str(node.get('node_id')) for node in (function.get('graph') or {}).get('nodes') or []
                if isinstance(node, dict) and node.get('node_id')
            }
            if node_ids & exposed_node_ids:
                required.add(function_id)

        selected: set[str] = set()
        pending = list(required)
        while pending:
            function_id = pending.pop()
            if function_id in selected:
                continue
            function = functions.get(function_id)
            if function is None:
                raise ValueError(f'调用函数不存在，无法发布: {function_id}')
            selected.add(function_id)
            pending.extend(cls._called_functions(function.get('graph') or {}) - selected)

        included_functions = [deepcopy(item) for item in blueprint.get('functions') or [] if item.get('function_id') in selected]
        included_graphs = [main_graph, *[(item.get('graph') or {}) for item in included_functions]]
        page_map = blueprint.get('page_map') if isinstance(blueprint.get('page_map'), dict) else {}
        exposed_page_map_node_ids = {
            str(node.get('node_id'))
            for node in page_map.get('nodes') or []
            if isinstance(node, dict) and node.get('node_id') and str(node.get('node_id')) in exposed_node_ids
        }
        needs_page_map = bool(exposed_page_map_node_ids) or any(
            node.get('node_type') == 'smart_jump'
            for graph in included_graphs
            for node in graph.get('nodes') or []
            if isinstance(node, dict)
        )
        included_folder_ids = {str(item.get('folder_id')) for item in included_functions if item.get('folder_id')}
        result = {
            key: deepcopy(value)
            for key, value in blueprint.items()
            if key not in {'main_graph', 'functions', 'function_folders', 'page_map'}
        }
        result.update({
            'main_graph': main_graph,
            'functions': included_functions,
            'function_folders': [
                deepcopy(item) for item in blueprint.get('function_folders') or []
                if str(item.get('folder_id')) in included_folder_ids
            ],
            'page_map': deepcopy(page_map) if needs_page_map else {
                'schema_version': 3, 'nodes': [], 'edges': [],
            },
        })
        return result

    @classmethod
    def _asset_files(cls, project_dir: str, blueprint: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
        from core.services.asset_service import AssetService

        registry = AssetService.load_registry(project_dir)
        references = cls._node_asset_references(blueprint)
        files: dict[str, str] = {}
        assets: dict[str, Any] = {}
        for reference in sorted(references):
            resolved = AssetService.resolve(project_dir, reference)
            asset_id = str(resolved.get('asset_id') or '')
            if not asset_id:
                raise ValueError(f'发布只接受稳定资源引用，发现旧路径引用: {reference}')
            relative = str(resolved['relative_path']).replace('\\', '/')
            files[f'templates/{relative}'] = str(resolved['full_path'])
            assets[asset_id] = deepcopy(registry.get('assets', {}).get(asset_id) or resolved.get('record') or {})
        return files, {
            'schema_version': registry.get('schema_version', 2),
            'assets': assets,
            'tombstones': {},
        }

    @classmethod
    def encrypt_data(cls, raw_data: bytes, key: bytes = None) -> bytes:
        """使用 AES-256-CBC 对二进制数据流进行加密"""
        if not key:
            key = cls.DEFAULT_MASTER_KEY

        # 生成 16 字节随机 IV
        iv = os.urandom(16)

        # PKCS7 填充
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(raw_data) + padder.finalize()

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(padded_data) + encryptor.finalize()

        # 将 IV 拼接到加密数据头部
        return iv + encrypted_bytes

    @classmethod
    def build_export_bundle(
        cls, project_dir: str, form_schema: dict[str, Any], output_dir: str = None
    ) -> dict[str, Any]:
        """
        构建打包资产包全流程
        :param project_dir: 项目绝对路径
        :param form_schema: 开发者配置的客户动态表单 Schema
        :param output_dir: 导出输出目录（默认导出到项目根目录下的 release/）
        """
        if not os.path.exists(project_dir):
            raise FileNotFoundError(f'项目目录不存在: {project_dir}')

        if not output_dir:
            output_dir = os.path.join(project_dir, 'release')
        os.makedirs(output_dir, exist_ok=True)
        form_schema = normalize_form_schema(form_schema)

        # 1. 内存中构建标准的无密码 zip 压缩流
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # A. 读取三文件蓝图（合并视图）并统一命名为 blueprint.json 写入密包内供 Player 运行时加载
            from core.services.blueprint_service import BlueprintService

            full_blueprint = BlueprintService.load_blueprint(project_dir)
            bp_dict = cls._trim_blueprint(full_blueprint, form_schema)
            zf.writestr('blueprint.json', json.dumps(bp_dict, ensure_ascii=False, indent=2))

            # B. 写入客户表单 Schema (form_schema.json)
            zf.writestr('form_schema.json', json.dumps(form_schema, ensure_ascii=False, indent=2))

            # C. 写入上下文配置 context.json (如果有)
            ctx_path = os.path.join(project_dir, 'context.json')
            if os.path.exists(ctx_path):
                with open(ctx_path, encoding='utf-8') as f:
                    ctx_content = f.read()
                zf.writestr('context.json', ctx_content)

            # D. 打包视觉图片与稳定资源注册表。目录结构原样保留，Player
            # 通过 assets.json 将 asset://ID 映射到对应内存矩阵。
            asset_files, release_registry = cls._asset_files(project_dir, bp_dict)
            zf.writestr('templates/assets.json', json.dumps(release_registry, ensure_ascii=False, indent=2))
            for archive_path, source_path in asset_files.items():
                zf.write(source_path, archive_path)

            # E. 只打包蓝图真实引用的项目/共享能力及旧式脚本。内置能力随
            # 引擎交付，无需重复进入密包；缺失能力在发布阶段直接失败。
            from core.services.capability_packaging_service import CapabilityPackagingService

            for archive_path, source_path in CapabilityPackagingService.collect_files(project_dir, bp_dict).items():
                zf.write(str(source_path), archive_path)

        # 2. 对内解压后的原始 Zip 字节流进行 AES-256 整体加密
        raw_zip_bytes = zip_buffer.getvalue()
        encrypted_ebp_bytes = cls.encrypt_data(raw_zip_bytes)

        # 3. 写出密包 assets.ebp 到 release 目录
        ebp_file_path = os.path.join(output_dir, 'assets.ebp')
        with open(ebp_file_path, 'wb') as f:
            f.write(encrypted_ebp_bytes)

        # 4. 生成默认的客户运行配置文件 user_config.json 模版
        user_config_path = os.path.join(output_dir, 'user_config.json')
        current_user_config = {}
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, encoding='utf-8') as f:
                    current_user_config = json.load(f)
            except Exception:
                current_user_config = {}
        default_user_config = build_user_config(form_schema, current_user_config)
        with open(user_config_path, 'w', encoding='utf-8') as f:
            json.dump(default_user_config, f, ensure_ascii=False, indent=2)

        return {
            'success': True,
            'export_dir': output_dir,
            'ebp_file': ebp_file_path,
            'user_config_file': user_config_path,
            'ebp_size_bytes': len(encrypted_ebp_bytes),
        }
