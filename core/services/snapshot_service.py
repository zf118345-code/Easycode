# core/services/snapshot_service.py
# 蓝图自动版本快照服务：history 文件夹备份 + SHA256 哈希校验
import os
import json
import hashlib
import shutil
import logging
from datetime import datetime
from core.security import atomic_write_json, assert_safe_path

logger = logging.getLogger(__name__)

MAX_SNAPSHOTS = 20  # 最大保留快照数


class SnapshotService:
    """蓝图版本快照管理"""

    @staticmethod
    def get_history_dir(project_path: str) -> str:
        return os.path.join(project_path, "history")

    @staticmethod
    def compute_hash(data: dict) -> str:
        """计算蓝图数据的 SHA256 哈希"""
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def create_snapshot(project_path: str, blueprint_data: dict) -> dict:
        """创建蓝图版本快照
        Returns: { snapshot_id, hash, timestamp, path }
        """
        history_dir = SnapshotService.get_history_dir(project_path)
        os.makedirs(history_dir, exist_ok=True)

        # 计算哈希
        content_hash = SnapshotService.compute_hash(blueprint_data)

        # 检查是否与最近一次快照相同（避免无变化时重复备份）
        snapshots = SnapshotService.list_snapshots(project_path)
        if snapshots:
            latest = snapshots[-1]
            if latest.get("hash") == content_hash:
                logger.info(f"快照跳过：内容哈希未变化 ({content_hash[:8]})")
                return latest

        # 生成快照文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snapshot_{timestamp}_{content_hash[:8]}"
        snapshot_path = os.path.join(history_dir, f"{snapshot_id}.json")

        # 写入快照（包含元数据）
        snapshot_data = {
            "snapshot_id": snapshot_id,
            "hash": content_hash,
            "timestamp": datetime.now().isoformat(),
            "project_name": blueprint_data.get("project_name", ""),
            "blueprint": blueprint_data
        }
        atomic_write_json(snapshot_path, snapshot_data)
        logger.info(f"快照已创建: {snapshot_id}")

        # 清理旧快照
        SnapshotService._cleanup_old_snapshots(project_path)

        return {
            "snapshot_id": snapshot_id,
            "hash": content_hash,
            "timestamp": snapshot_data["timestamp"],
            "path": snapshot_path
        }

    @staticmethod
    def list_snapshots(project_path: str) -> list:
        """列出所有快照（按时间排序）"""
        history_dir = SnapshotService.get_history_dir(project_path)
        if not os.path.exists(history_dir):
            return []

        snapshots = []
        for fname in os.listdir(history_dir):
            if not fname.startswith("snapshot_") or not fname.endswith(".json"):
                continue
            fpath = os.path.join(history_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                snapshots.append({
                    "snapshot_id": data.get("snapshot_id", fname),
                    "hash": data.get("hash", ""),
                    "timestamp": data.get("timestamp", ""),
                    "project_name": data.get("project_name", ""),
                    "path": fpath
                })
            except Exception as e:
                logger.warning(f"读取快照失败: {fname}: {e}")

        snapshots.sort(key=lambda s: s.get("timestamp", ""))
        return snapshots

    @staticmethod
    def load_snapshot(project_path: str, snapshot_id: str) -> dict:
        """加载指定快照的蓝图数据"""
        history_dir = SnapshotService.get_history_dir(project_path)
        snapshot_path = os.path.join(history_dir, f"{snapshot_id}.json")
        assert_safe_path(history_dir, snapshot_path)

        if not os.path.exists(snapshot_path):
            raise FileNotFoundError(f"快照不存在: {snapshot_id}")

        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 哈希校验
        blueprint = data.get("blueprint", {})
        computed_hash = SnapshotService.compute_hash(blueprint)
        if computed_hash != data.get("hash"):
            raise ValueError(f"快照哈希校验失败: {snapshot_id}")

        return blueprint

    @staticmethod
    def restore_snapshot(project_path: str, snapshot_id: str) -> dict:
        """恢复到指定快照（先创建当前状态的快照）"""
        # 先备份当前状态
        from core.services.blueprint_service import BlueprintService
        try:
            current = BlueprintService.load_blueprint(project_path)
            SnapshotService.create_snapshot(project_path, current)
        except Exception as e:
            logger.warning(f"恢复前备份失败: {e}")

        # 加载并恢复快照
        blueprint = SnapshotService.load_snapshot(project_path, snapshot_id)
        BlueprintService.save_blueprint(project_path, blueprint)
        logger.info(f"已恢复到快照: {snapshot_id}")
        return blueprint

    @staticmethod
    def delete_snapshot(project_path: str, snapshot_id: str) -> bool:
        """删除指定快照"""
        history_dir = SnapshotService.get_history_dir(project_path)
        snapshot_path = os.path.join(history_dir, f"{snapshot_id}.json")
        assert_safe_path(history_dir, snapshot_path)

        if os.path.exists(snapshot_path):
            os.remove(snapshot_path)
            return True
        return False

    @staticmethod
    def verify_blueprint(project_path: str) -> dict:
        """校验当前蓝图完整性"""
        from core.services.blueprint_service import BlueprintService
        blueprint = BlueprintService.load_blueprint(project_path)
        content_hash = SnapshotService.compute_hash(blueprint)
        return {
            "valid": True,
            "hash": content_hash,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def _cleanup_old_snapshots(project_path: str):
        """清理旧快照，保留最近 MAX_SNAPSHOTS 个"""
        snapshots = SnapshotService.list_snapshots(project_path)
        if len(snapshots) <= MAX_SNAPSHOTS:
            return

        to_delete = snapshots[:len(snapshots) - MAX_SNAPSHOTS]
        for snap in to_delete:
            try:
                os.remove(snap["path"])
                logger.info(f"已清理旧快照: {snap['snapshot_id']}")
            except Exception as e:
                logger.warning(f"清理快照失败: {snap['snapshot_id']}: {e}")
