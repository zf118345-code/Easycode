# core/security/licensing.py
import os
import sys
import json
import hashlib
import base64
import platform
import subprocess
from datetime import datetime
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend


class LicenseManager:
    """
    工业级硬件指纹提取与 RSA 授权证书校验器
    """

    @classmethod
    def get_machine_code(cls) -> str:
        """
        跨平台提取宿主机硬件唯一指纹 (CPU 序列号 + 主板 UUID + 磁盘 HWID)
        返回 32 位大写 SHA-256 机器码
        """
        raw_hwids = []

        system_name = platform.system()
        if system_name == "Windows":
            try:
                # 提取 CPU 序列号
                cmd_cpu = "wmic cpu get processorid"
                cpu_out = subprocess.check_output(cmd_cpu, shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
                cpu_id = "".join(cpu_out.split()[1:]) if len(cpu_out.split()) > 1 else ""
                raw_hwids.append(cpu_id)

                # 提取主板 UUID
                cmd_board = "wmic csproduct get uuid"
                board_out = subprocess.check_output(cmd_board, shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
                board_uuid = "".join(board_out.split()[1:]) if len(board_out.split()) > 1 else ""
                raw_hwids.append(board_uuid)

                # 提取 C 盘卷标序列号
                cmd_disk = "wmic volume where DriveLetter='C:' get SerialNumber"
                disk_out = subprocess.check_output(cmd_disk, shell=True, stderr=subprocess.DEVNULL).decode("utf-8")
                disk_sn = "".join(disk_out.split()[1:]) if len(disk_out.split()) > 1 else ""
                raw_hwids.append(disk_sn)
            except Exception:
                raw_hwids.append(platform.node())
        else:
            # Linux / macOS 降级探针
            raw_hwids.append(platform.node())
            raw_hwids.append(platform.machine())
            raw_hwids.append(platform.processor())

        raw_str = "|".join(raw_hwids)
        if not raw_str.replace("|", ""):
            raw_str = f"EASYCODE_FALLBACK_{platform.node()}"

        # SHA-256 计算硬件指纹
        sha256 = hashlib.sha256()
        sha256.update(raw_str.encode("utf-8"))
        hash_hex = sha256.hexdigest().upper()

        # 格式化为 32 位八段响亮格式 (如 XXXX-XXXX-XXXX-XXXX)
        return hash_hex[:32]

    @classmethod
    def verify_license_payload(
            cls,
            license_str: str,
            public_key_pem: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        使用 RSA 公钥对客户端输入的 License 进行验签
        :param license_str: 经过 Base64 编码的 Json 授权字符串
        :param public_key_pem: 开发者内置的 RSA 公钥 PEM 字符串
        :returns: (is_valid, err_msg, payload_dict)
        """
        if not license_str or not public_key_pem:
            return False, "授权码或验签公钥为空", {}

        try:
            raw_bytes = base64.b64decode(license_str.encode("utf-8"))
            license_json = json.loads(raw_bytes.decode("utf-8"))

            payload = license_json.get("payload", {})
            signature_b64 = license_json.get("signature", "")

            if not payload or not signature_b64:
                return False, "授权证书格式完整性损坏", {}

            # 1. 校验 RSA 签名
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode("utf-8"),
                backend=default_backend()
            )

            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            signature = base64.b64decode(signature_b64)

            public_key.verify(
                signature,
                payload_bytes,
                asym_padding.PSS(
                    mgf=asym_padding.MGF1(hashes.SHA256()),
                    salt_length=asym_padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # 2. 校验机器码 (硬件锁)
            bound_machine_code = payload.get("machine_code", "")
            current_machine_code = cls.get_machine_code()
            if bound_machine_code and bound_machine_code != "*" and bound_machine_code != current_machine_code:
                return False, f"授权硬件不匹配 (证书绑定: {bound_machine_code}, 本机: {current_machine_code})", payload

            # 3. 校验过期时间
            expire_str = payload.get("expire_time", "")
            if expire_str and expire_str != "never":
                expire_dt = datetime.strptime(expire_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expire_dt:
                    return False, f"授权已于 {expire_str} 过期", payload

            return True, "授权验证通过", payload

        except Exception as e:
            return False, f"签名验证失败或证书已被篡改: {str(e)}", {}