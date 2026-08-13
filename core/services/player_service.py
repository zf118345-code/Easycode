# core/services/player_service.py
# P0 修复：停止机制（实际下发停止信号）、线程安全缓存（加锁）

import os
import json
import threading
from typing import Dict, Any, List
from fastapi import HTTPException, BackgroundTasks
from core.player.loader import PlayerAssetLoader
from core.player.providers import SystemDataProvider
from core.services.execution_service import ExecutionService
from core.security.licensing import LicenseManager
from core.security.crypto import SecureAssetCrypto


class PlayerService:
    """
    Player 客户端解密与运行期管理服务
    P0 修复：线程安全缓存、停止机制
    """

    _MEMORY_CACHE: Dict[str, Any] = {
        "blueprint": None,
        "form_schema": None,
        "user_config": None,
        "templates": {},
        "license_info": {}
    }

    # P0 修复：缓存读写锁
    _cache_lock = threading.Lock()

    # P0 修复：当前运行的 execution_id
    _current_execution_id: str = None

    @classmethod
    def get_machine_code(cls) -> str:
        return LicenseManager.get_machine_code()

    @classmethod
    def init_session(
        cls,
        ebp_path: str,
        config_path: str,
        license_path: str = None,
        public_key_pem: str = None
    ) -> dict:
        if not ebp_path or not os.path.exists(ebp_path):
            raise HTTPException(
                status_code=404,
                detail=f"Player 内存解密失败: 未在目标路径找到脚本资源密包: {ebp_path}"
            )

        if not license_path:
            license_path = os.path.join(os.path.dirname(ebp_path), "license.lic")

        license_payload = {}
        if os.path.exists(license_path) and public_key_pem:
            try:
                with open(license_path, "r", encoding="utf-8") as f:
                    lic_str = f.read().strip()
                is_valid, err_msg, payload = LicenseManager.verify_license_payload(lic_str, public_key_pem)
                if not is_valid:
                    raise HTTPException(status_code=403, detail=f"卡密授权校验失败: {err_msg}")
                license_payload = payload
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=403, detail=f"解析授权证书失败: {e}")

        machine_code = cls.get_machine_code()
        derived_key = SecureAssetCrypto.derive_key_from_machine(
            PlayerAssetLoader.DEFAULT_MASTER_KEY,
            machine_code
        )

        try:
            blueprint_data, form_schema, user_config, templates = PlayerAssetLoader.load_bundle_from_ebp(
                ebp_path, config_path, key=derived_key
            )
        except Exception:
            try:
                blueprint_data, form_schema, user_config, templates = PlayerAssetLoader.load_bundle_from_ebp(
                    ebp_path, config_path, key=PlayerAssetLoader.DEFAULT_MASTER_KEY
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Player 内存解密失败: {e}")

        # P0 修复：加锁写入缓存
        with cls._cache_lock:
            cls._MEMORY_CACHE["blueprint"] = blueprint_data
            cls._MEMORY_CACHE["form_schema"] = form_schema
            cls._MEMORY_CACHE["user_config"] = user_config
            cls._MEMORY_CACHE["templates"] = templates
            cls._MEMORY_CACHE["license_info"] = license_payload

        return {
            "status": "success",
            "machine_code": machine_code,
            "form_schema": form_schema,
            "user_config": user_config,
            "templates_count": len(templates),
            "license_info": license_payload
        }

    @classmethod
    def get_provider_options(cls, provider_key: str) -> List[Dict[str, str]]:
        return SystemDataProvider.resolve_provider(provider_key)

    @classmethod
    def save_user_config(cls, user_config: dict, config_path: str = "release/user_config.json") -> dict:
        if not user_config:
            raise HTTPException(status_code=400, detail="缺少 user_config 数据")

        with cls._cache_lock:
            cls._MEMORY_CACHE["user_config"] = user_config

        if not os.path.exists(os.path.dirname(config_path)):
            config_path = "user_config.json"

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(user_config, f, ensure_ascii=False, indent=2)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存 user_config 失败: {e}")

    @classmethod
    def run_script(cls, background_tasks: BackgroundTasks) -> dict:
        """从解密后的内存对象倒灌参数并将内存模板打包注入给引擎"""
        with cls._cache_lock:
            blueprint_data = cls._MEMORY_CACHE.get("blueprint")
            user_config = cls._MEMORY_CACHE.get("user_config") or {}
            memory_templates = cls._MEMORY_CACHE.get("templates") or {}

        if not blueprint_data:
            raise HTTPException(status_code=400, detail="Player Session 未初始化，请先调用 init_session")

        # 1. 深度拷贝蓝图数据
        runtime_blueprint = json.loads(json.dumps(blueprint_data))
        if "variables" not in runtime_blueprint:
            runtime_blueprint["variables"] = {}

        # 2. 执行三阶参数倒灌
        for vk, vv in user_config.get("vars", {}).items():
            runtime_blueprint["variables"][vk] = vv
        for ck, cv in user_config.get("ctx", {}).items():
            runtime_blueprint["variables"][f"$ctx.{ck}"] = cv

        # 3. 将内存模板打入 runtime_blueprint
        runtime_blueprint["_memory_templates"] = memory_templates

        # 4. 提取首个任务组作为启动入口
        tasks = runtime_blueprint.get("tasks", [])
        if not tasks:
            raise HTTPException(status_code=400, detail="密包中不包含有效的任务组")

        first_task_id = tasks[0].get("task_id")
        project_path = os.getcwd()

        exec_result = ExecutionService.run_task(project_path, first_task_id, None, runtime_blueprint, background_tasks)

        if isinstance(exec_result, dict):
            exec_id = exec_result.get("execution_id") or exec_result.get("data", {}).get("execution_id")
            if exec_id:
                exec_result["execution_id"] = exec_id
                # P0 修复：记录当前 execution_id 供 stop_script 使用
                cls._current_execution_id = exec_id

        return exec_result

    @classmethod
    def stop_script(cls) -> dict:
        """P0 修复：实际下发停止信号"""
        exec_id = cls._current_execution_id
        if exec_id:
            result = ExecutionService.stop_execution(exec_id)
            cls._current_execution_id = None
            return result
        return {"status": "warning", "message": "当前没有正在运行的脚本"}
