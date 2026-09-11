"""Per-user Windows Player installation using the frozen application package."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from .windows_update_helper_v6 import WindowsApplicationPackage, WindowsUpdateHelperError


MEDIA_FORMAT = "easycode-windows-installer-media-v1"
MEDIA_MANIFEST = "easycode-installer-media.json"
INSTALL_MARKER = ".easycode-installation.json"
_PRODUCT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class WindowsInstallationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_remove(path: Path, boundary: Path) -> None:
    resolved, parent = path.resolve(), boundary.resolve()
    if resolved == parent or parent not in resolved.parents:
        raise WindowsInstallationError("WIN-INSTALL-PATH-001", f"拒绝清理越界目录：{resolved}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def _read_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WindowsInstallationError(code, f"无法读取 {path.name}：{exc}") from exc
    if not isinstance(value, dict):
        raise WindowsInstallationError(code, f"{path.name} 必须是 JSON 对象")
    return value


class WindowsInstallerMediaV6:
    """Build and inspect an offline installer directory without mutating the machine."""

    @staticmethod
    def build(
        distribution_root: str | Path,
        output_root: str | Path,
        *,
        installer_executable: str | Path,
    ) -> dict[str, Any]:
        source = Path(distribution_root).resolve()
        build_manifest = _read_object(source / "build_manifest.json", "WIN-INSTALL-MEDIA-001")
        product_id = str(build_manifest.get("project_id") or "").strip()
        release_id = str(build_manifest.get("release_id") or "").strip()
        display_name = str(build_manifest.get("project") or build_manifest.get("product") or product_id).strip()
        if not _PRODUCT_ID.fullmatch(product_id) or not release_id or not display_name:
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-001", "交付目录缺少稳定产品或发布身份")
        root = Path(output_root).resolve()
        installer_source = Path(installer_executable).resolve()
        if not installer_source.is_file() or installer_source.is_symlink():
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-001", "缺少真实 EasyCode 安装程序")
        root.mkdir(parents=True, exist_ok=True)
        destination = root / "Windows_Installer"
        staging = root / f".Windows_Installer-building-{os.getpid()}"
        _safe_remove(staging, root)
        staging.mkdir()
        try:
            archive = staging / "application.zip"
            package = WindowsApplicationPackage.build(
                source, archive, release_id=release_id, entrypoint="EasycodePlayer.exe",
            )
            installer = staging / "EasycodeInstaller.exe"
            shutil.copy2(installer_source, installer)
            installer_length, installer_sha256 = _digest(installer)
            manifest = {
                "schema_version": 1,
                "format": MEDIA_FORMAT,
                "product_id": product_id,
                "release_id": release_id,
                "display_name": display_name,
                "archive": archive.name,
                "archive_length": package["length"],
                "archive_sha256": package["sha256"],
                "installer": installer.name,
                "installer_length": installer_length,
                "installer_sha256": installer_sha256,
            }
            _atomic_json(staging / MEDIA_MANIFEST, manifest)
            previous = root / ".Windows_Installer-previous"
            _safe_remove(previous, root)
            if destination.exists():
                os.replace(destination, previous)
            try:
                os.replace(staging, destination)
            except Exception:
                if previous.exists() and not destination.exists():
                    os.replace(previous, destination)
                raise
            _safe_remove(previous, root)
            return {
                "path": str(destination),
                "manifest": manifest,
                "archive": str(destination / archive.name),
                "installer": str(destination / installer.name),
            }
        except Exception:
            _safe_remove(staging, root)
            raise

    @staticmethod
    def inspect(media_root: str | Path) -> dict[str, Any]:
        root = Path(media_root).resolve()
        manifest = _read_object(root / MEDIA_MANIFEST, "WIN-INSTALL-MEDIA-002")
        expected = {
            "schema_version", "format", "product_id", "release_id", "display_name",
            "archive", "archive_length", "archive_sha256",
            "installer", "installer_length", "installer_sha256",
        }
        if set(manifest) != expected or manifest.get("schema_version") != 1 or manifest.get("format") != MEDIA_FORMAT:
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-002", "安装介质清单字段或版本无效")
        product_id = str(manifest.get("product_id") or "")
        archive_name = str(manifest.get("archive") or "")
        installer_name = str(manifest.get("installer") or "")
        if not _PRODUCT_ID.fullmatch(product_id) or archive_name != "application.zip" or installer_name != "EasycodeInstaller.exe":
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-002", "安装介质产品身份或归档位置无效")
        archive = (root / archive_name).resolve()
        if archive.parent != root or not archive.is_file() or archive.is_symlink():
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-002", "安装介质缺少真实应用归档")
        length, digest = _digest(archive)
        if length != manifest["archive_length"] or digest != manifest["archive_sha256"]:
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-003", "应用归档长度或哈希不一致")
        installer = (root / installer_name).resolve()
        if installer.parent != root or not installer.is_file() or installer.is_symlink():
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-002", "安装介质缺少真实安装程序")
        installer_length, installer_digest = _digest(installer)
        if installer_length != manifest["installer_length"] or installer_digest != manifest["installer_sha256"]:
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-003", "安装程序长度或哈希不一致")
        try:
            package = WindowsApplicationPackage.inspect(archive, expected_release_id=str(manifest["release_id"]))
        except WindowsUpdateHelperError as exc:
            raise WindowsInstallationError("WIN-INSTALL-MEDIA-003", str(exc)) from exc
        return {
            "root": str(root), "archive": str(archive), "installer": str(installer),
            "manifest": manifest, "package": package,
        }


class WindowsPerUserInstallerV6:
    """Install one verified media into an exact current-user program boundary."""

    def __init__(self, local_app_data: str | Path | None = None) -> None:
        raw = str(local_app_data) if local_app_data is not None else str(os.environ.get("LOCALAPPDATA") or "")
        if not raw.strip():
            raise WindowsInstallationError("WIN-INSTALL-HOST-001", "当前用户没有 LOCALAPPDATA")
        configured = Path(raw)
        self.local_app_data = configured.expanduser().resolve()
        self.products_root = self.local_app_data / "Programs" / "EasyCode" / "Products"

    def install(self, media_root: str | Path) -> dict[str, Any]:
        inspected = WindowsInstallerMediaV6.inspect(media_root)
        identity = inspected["manifest"]
        target = (self.products_root / identity["product_id"]).resolve()
        if target.parent != self.products_root.resolve():
            raise WindowsInstallationError("WIN-INSTALL-PATH-001", "产品安装目录越界")
        self.products_root.mkdir(parents=True, exist_ok=True)
        staging = self.products_root / f".{identity['product_id']}-installing-{uuid.uuid4().hex}"
        backup = self.products_root / f".{identity['product_id']}-previous"
        _safe_remove(staging, self.products_root)
        _safe_remove(backup, self.products_root)
        try:
            WindowsApplicationPackage.extract(
                inspected["archive"], staging, expected_release_id=identity["release_id"],
            )
            delivered = _read_object(staging / "build_manifest.json", "WIN-INSTALL-IDENTITY-001")
            if delivered.get("project_id") != identity["product_id"] or delivered.get("release_id") != identity["release_id"]:
                raise WindowsInstallationError("WIN-INSTALL-IDENTITY-001", "应用归档与安装介质身份不一致")
            marker = {
                "schema_version": 1,
                "product_id": identity["product_id"],
                "release_id": identity["release_id"],
                "display_name": identity["display_name"],
                "install_root": str(target),
                "data_preserved_by_default": True,
            }
            _atomic_json(staging / INSTALL_MARKER, marker)
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(staging, target)
            except Exception:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
            _safe_remove(backup, self.products_root)
        except Exception:
            _safe_remove(staging, self.products_root)
            raise
        return {
            "installed": True,
            "install_root": str(target),
            "executable": str(target / "EasycodePlayer.exe"),
            "bundle": str(target / "release" / "project.ecplayer"),
            "trust_root": str(target / "release" / "trust-root.json"),
            "product_id": identity["product_id"],
            "release_id": identity["release_id"],
            "display_name": identity["display_name"],
        }

    def uninstall(self, install_root: str | Path) -> dict[str, Any]:
        root = Path(install_root).resolve()
        if root.parent != self.products_root.resolve():
            raise WindowsInstallationError("WIN-INSTALL-PATH-001", "卸载目录不属于当前用户 EasyCode 产品根")
        marker = _read_object(root / INSTALL_MARKER, "WIN-UNINSTALL-MARKER-001")
        if marker.get("install_root") != str(root) or marker.get("product_id") != root.name:
            raise WindowsInstallationError("WIN-UNINSTALL-MARKER-001", "安装标记与卸载目标不一致")
        quarantine = self.products_root / f".{root.name}-uninstalling-{uuid.uuid4().hex}"
        os.replace(root, quarantine)
        try:
            _safe_remove(quarantine, self.products_root)
        except Exception:
            if quarantine.exists() and not root.exists():
                os.replace(quarantine, root)
            raise
        return {"uninstalled": True, "product_id": root.name, "data_preserved": True}


__all__ = [
    "INSTALL_MARKER", "MEDIA_FORMAT", "MEDIA_MANIFEST", "WindowsInstallationError",
    "WindowsInstallerMediaV6", "WindowsPerUserInstallerV6",
]
