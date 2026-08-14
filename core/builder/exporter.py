# core/builder/exporter.py
import io
import json
import os
import zipfile
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class ProjectExporter:
    """
    工业级脚本打包与加密导出器
    负责将 IDE 项目（project_blueprint.json, templates/*.png, context.json, form_schema.json）
    打造成带 DRM 加密的单文件二进制资产包 (.ebp)
    """

    # 默认固化的资产包导出专用对称加密 Key (实际生产可由特定机器码/卡密派生)
    DEFAULT_MASTER_KEY = b'EasycodeDRMMasterKey2026AES256!!'  # 32 bytes

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

        # ⚡ 兼容适配：工业级蓝图路径寻址（优先寻找 project_blueprint.json，兼容 blueprint.json）
        blueprint_path = os.path.join(project_dir, 'project_blueprint.json')
        if not os.path.exists(blueprint_path):
            blueprint_path = os.path.join(project_dir, 'blueprint.json')

        if not os.path.exists(blueprint_path):
            raise FileNotFoundError(f'缺少关键拓扑文件 (project_blueprint.json 或 blueprint.json): {project_dir}')

        if not output_dir:
            output_dir = os.path.join(project_dir, 'release')
        os.makedirs(output_dir, exist_ok=True)

        # 1. 内存中构建标准的无密码 zip 压缩流
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # A. 读取项目蓝图并统一命名为 blueprint.json 写入密包内供 Player 运行时加载
            with open(blueprint_path, encoding='utf-8') as f:
                bp_content = f.read()
            zf.writestr('blueprint.json', bp_content)

            # B. 写入客户表单 Schema (form_schema.json)
            zf.writestr('form_schema.json', json.dumps(form_schema, ensure_ascii=False, indent=2))

            # C. 写入上下文配置 context.json (如果有)
            ctx_path = os.path.join(project_dir, 'context.json')
            if os.path.exists(ctx_path):
                with open(ctx_path, encoding='utf-8') as f:
                    ctx_content = f.read()
                zf.writestr('context.json', ctx_content)

            # D. 打包收集 templates/ 目录下所有识图图片
            templates_dir = os.path.join(project_dir, 'templates')
            if os.path.exists(templates_dir):
                for root, _, files in os.walk(templates_dir):
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            abs_file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_file_path, templates_dir)

                            # 关键修正 (Python 3.10 兼容)：提取 replace 逻辑，避免在 f-string {} 内使用反斜杠
                            normalized_rel_path = rel_path.replace('\\', '/')
                            zip_target_path = f'templates/{normalized_rel_path}'
                            zf.write(abs_file_path, zip_target_path)

            # E. 写入区域坐标记录 regions.json (如果有)
            regions_path = os.path.join(project_dir, 'regions.json')
            if os.path.exists(regions_path):
                with open(regions_path, encoding='utf-8') as f:
                    zf.writestr('regions.json', f.read())

        # 2. 对内解压后的原始 Zip 字节流进行 AES-256 整体加密
        raw_zip_bytes = zip_buffer.getvalue()
        encrypted_ebp_bytes = cls.encrypt_data(raw_zip_bytes)

        # 3. 写出密包 assets.ebp 到 release 目录
        ebp_file_path = os.path.join(output_dir, 'assets.ebp')
        with open(ebp_file_path, 'wb') as f:
            f.write(encrypted_ebp_bytes)

        # 4. 生成默认的客户运行配置文件 user_config.json 模版
        user_config_path = os.path.join(output_dir, 'user_config.json')
        if not os.path.exists(user_config_path):
            default_user_config = {'vars': {}, 'ctx': {}, 'env': {}}
            # 自动提取 form_schema 中定义的默认值填充初始 user_config.json
            for group in form_schema.get('groups', []):
                for field in group.get('fields', []):
                    target = field.get('target', '')
                    default_val = field.get('default')
                    if target.startswith('$var.'):
                        default_user_config['vars'][target[5:]] = default_val
                    elif target.startswith('$ctx.'):
                        default_user_config['ctx'][target[5:]] = default_val
                    elif target.startswith('$env.'):
                        default_user_config['env'][target[5:]] = default_val

            with open(user_config_path, 'w', encoding='utf-8') as f:
                json.dump(default_user_config, f, ensure_ascii=False, indent=2)

        return {
            'success': True,
            'export_dir': output_dir,
            'ebp_file': ebp_file_path,
            'user_config_file': user_config_path,
            'ebp_size_bytes': len(encrypted_ebp_bytes),
        }
