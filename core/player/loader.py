# core/player/loader.py
import io
import json
import os
import zipfile
from typing import Any

import cv2
import numpy as np
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from core.player.schema import build_user_config, normalize_form_schema


class PlayerAssetLoader:
    """
    客户端资产包 (assets.ebp) 零落地内存解密与加载器
    彻底隔离磁盘写操作，OpenCV 图像与蓝图数据直接在 RAM 中构建与倒灌
    """

    DEFAULT_MASTER_KEY = b'EasycodeDRMMasterKey2026AES256!!'  # 32 bytes

    @classmethod
    def decrypt_bytes(cls, encrypted_bytes: bytes, key: bytes = None) -> bytes:
        """从二进制密包解密出内存中的原始 zip 字节流"""
        if not key:
            key = cls.DEFAULT_MASTER_KEY

        if len(encrypted_bytes) < 16:
            raise ValueError('密包数据损坏或长度不足')

        # 提取 16 字节 IV 头部
        iv = encrypted_bytes[:16]
        cipher_data = encrypted_bytes[16:]

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(cipher_data) + decryptor.finalize()

        # 去除 PKCS7 填充
        unpadder = padding.PKCS7(128).unpadder()
        raw_data = unpadder.update(padded_data) + unpadder.finalize()
        return raw_data

    @classmethod
    def load_bundle_from_ebp(
        cls, ebp_path: str, user_config_path: str = None, key: bytes = None
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, np.ndarray], dict[str, Any]]:
        """
        全量解密加载密包资产
        :returns: (blueprint_dict, form_schema_dict, merged_user_config, template_matrices_dict, context_dict)
        """
        if not os.path.exists(ebp_path):
            raise FileNotFoundError(f'未找到脚本资源密包: {ebp_path}')

        with open(ebp_path, 'rb') as f:
            encrypted_data = f.read()

        # 1. 内存解密
        raw_zip_bytes = cls.decrypt_bytes(encrypted_data, key)

        # 2. 内存解压提取文件
        zip_stream = io.BytesIO(raw_zip_bytes)
        template_images: dict[str, np.ndarray] = {}
        blueprint_data = {}
        form_schema = {}
        context_data = {}
        asset_registry = {'assets': {}}
        runtime_files: dict[str, bytes] = {}

        with zipfile.ZipFile(zip_stream, 'r') as zf:
            for name in zf.namelist():
                norm_name = name.replace('\\', '/')
                if norm_name == 'blueprint.json':
                    blueprint_data = json.loads(zf.read(name).decode('utf-8'))
                elif norm_name == 'form_schema.json':
                    form_schema = json.loads(zf.read(name).decode('utf-8'))
                elif norm_name == 'context.json':
                    # ⚡ 提取打包时内置的默认上下文（窗口标题/裁剪/目标尺寸）：
                    # player 端窗口预热依赖它（打包目录不再需要散装 context.json）
                    try:
                        context_data = json.loads(zf.read(name).decode('utf-8'))
                    except Exception:
                        context_data = {}
                elif norm_name == 'templates/assets.json':
                    try:
                        asset_registry = json.loads(zf.read(name).decode('utf-8'))
                    except Exception:
                        asset_registry = {'assets': {}}
                elif norm_name.startswith('templates/') and norm_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # 提取纯模板名称 (如 "templates/sub/21.png" -> "sub/21")
                    clean_key = norm_name[10:].replace('\\', '/')
                    if clean_key.lower().endswith('.png'):
                        clean_key = clean_key[:-4]
                    elif clean_key.lower().endswith(('.jpg', 'jpeg')):
                        clean_key = clean_key[:-5]

                    img_bytes = zf.read(name)
                    # 从内存字节解码为 OpenCV BGR Mat 矩阵，绝不落盘
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    mat = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if mat is not None:
                        template_images[clean_key] = mat
                elif (
                    norm_name.startswith('capabilities/')
                    and norm_name.lower().endswith(('.py', '.json'))
                ) or (norm_name.startswith('scripts/') and norm_name.lower().endswith('.py')):
                    payload = zf.read(name)
                    if len(payload) > 8 * 1024 * 1024:
                        raise ValueError(f'运行时代码文件过大: {norm_name}')
                    runtime_files[norm_name] = payload

        for asset_id, record in asset_registry.get('assets', {}).items():
            path = str(record.get('path') or '').replace('\\', '/')
            clean_key = os.path.splitext(path)[0]
            if clean_key in template_images:
                template_images[f'asset://{asset_id}'] = template_images[clean_key]

        # 3. 加载本地客户配置文件 user_config.json 并合并
        user_config = {'vars': {}, 'ctx': {}}
        if user_config_path and os.path.exists(user_config_path):
            try:
                with open(user_config_path, encoding='utf-8') as f:
                    loaded_cfg = json.load(f)
                    user_config = loaded_cfg
            except Exception as e:
                print(f' [Player Loader] 加载本地 user_config.json 异常: {e}')

        form_schema = normalize_form_schema(form_schema)
        user_config = build_user_config(form_schema, user_config)
        context_data['_runtime_files'] = runtime_files

        # 4. 执行参数倒灌 (Ingestion) 到 blueprint_data 的运行状态中
        if 'variables' not in blueprint_data:
            blueprint_data['variables'] = {}

        # 倒灌 $var
        for vk, vv in user_config.get('vars', {}).items():
            blueprint_data['variables'][vk] = vv

        # 倒灌 $ctx
        for ck, cv in user_config.get('ctx', {}).items():
            blueprint_data['variables'][f'$ctx.{ck}'] = cv

        return blueprint_data, form_schema, user_config, template_images, context_data
