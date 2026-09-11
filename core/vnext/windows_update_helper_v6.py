"""Crash-recoverable Windows application package and external update helper.

The helper is deliberately independent from the running Player process.  A
package is verified and extracted beside the installation, then an external
worker waits for the old process to exit, swaps complete directories, and
requires an explicit startup-health receipt before retaining the new slot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

PACKAGE_FORMAT = "easycode-windows-application-v1"
MANIFEST_NAME = "easycode-update-package.json"
MAX_FILES = 100_000
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


class WindowsUpdateHelperError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(dict(value)) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_relative(raw: str) -> str:
    normalized = str(raw or "").replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or ":" in path.parts[0]
        or any(not part or part in {".", ".."} for part in path.parts)
    ):
        raise WindowsUpdateHelperError("UPD-WIN-PATH-001", "更新包包含越界路径")
    return path.as_posix()


def _safe_remove_tree(path: Path, parent: Path) -> None:
    resolved, boundary = path.resolve(), parent.resolve()
    if resolved == boundary or boundary not in resolved.parents:
        raise WindowsUpdateHelperError("UPD-WIN-PATH-001", f"拒绝清理越界目录：{resolved}")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


class WindowsApplicationPackage:
    @staticmethod
    def build(source: str | Path, output: str | Path, *, release_id: str, entrypoint: str) -> dict[str, Any]:
        root = Path(source).resolve()
        destination = Path(output).resolve()
        entry = _safe_relative(entrypoint)
        if not root.is_dir() or not (root / Path(*PurePosixPath(entry).parts)).is_file():
            raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-001", "Windows 更新目录或入口不存在")
        files = sorted(path for path in root.rglob("*") if path.is_file())
        if not files or len(files) > MAX_FILES:
            raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-001", "Windows 更新文件数量无效")
        records: list[dict[str, Any]] = []
        total = 0
        for path in files:
            relative = _safe_relative(path.relative_to(root).as_posix())
            if relative == MANIFEST_NAME:
                raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-001", f"源目录保留了内部文件名：{MANIFEST_NAME}")
            size, digest = _sha256(path)
            total += size
            if total > MAX_TOTAL_BYTES:
                raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-001", "Windows 更新解包体积超过上限")
            records.append({"path": relative, "length": size, "sha256": digest})
        manifest = {
            "schema_version": 1,
            "format": PACKAGE_FORMAT,
            "release_id": str(release_id),
            "entrypoint": entry,
            "files": records,
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr(MANIFEST_NAME, canonical_json_bytes(manifest))
                for path, record in zip(files, records, strict=True):
                    archive.write(path, record["path"])
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        size, digest = _sha256(destination)
        return {"path": str(destination), "length": size, "sha256": digest, "manifest": manifest}

    @staticmethod
    def inspect(archive_path: str | Path, *, expected_release_id: str = "") -> dict[str, Any]:
        path = Path(archive_path).resolve()
        try:
            with zipfile.ZipFile(path, "r") as archive:
                entries = [item for item in archive.infolist() if not item.is_dir()]
                if len(entries) < 2 or len(entries) > MAX_FILES + 1:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新包文件数量无效")
                names = [_safe_relative(item.filename) for item in entries]
                if len(names) != len(set(name.casefold() for name in names)) or MANIFEST_NAME not in names:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新包包含重复路径或缺少清单")
                if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in entries):
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新包不得包含符号链接")
                manifest = json.loads(archive.read(MANIFEST_NAME))
                expected_fields = {"schema_version", "format", "release_id", "entrypoint", "files"}
                if not isinstance(manifest, dict) or set(manifest) != expected_fields:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新清单字段无效")
                if manifest["schema_version"] != 1 or manifest["format"] != PACKAGE_FORMAT:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新清单版本无效")
                if expected_release_id and manifest["release_id"] != expected_release_id:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新包 release_id 不匹配")
                records = manifest["files"]
                if not isinstance(records, list) or not records:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新清单没有文件")
                by_name: dict[str, zipfile.ZipInfo] = {item.filename.replace("\\", "/"): item for item in entries}
                listed: set[str] = set()
                total = 0
                for record in records:
                    if not isinstance(record, dict) or set(record) != {"path", "length", "sha256"}:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新文件记录无效")
                    name = _safe_relative(record["path"])
                    length = record["length"]
                    digest = str(record["sha256"])
                    if name == MANIFEST_NAME or name in listed or name not in by_name:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新文件清单与归档不一致")
                    if isinstance(length, bool) or not isinstance(length, int) or length < 0 or len(digest) != 64:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新文件约束无效")
                    info = by_name[name]
                    if info.file_size != length:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新文件大小不一致")
                    total += length
                    if total > MAX_TOTAL_BYTES:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新解包体积超过上限")
                    calculated = hashlib.sha256()
                    with archive.open(info) as stream:
                        while chunk := stream.read(1024 * 1024):
                            calculated.update(chunk)
                    if calculated.hexdigest() != digest:
                        raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新文件哈希不一致")
                    listed.add(name)
                if set(names) != listed | {MANIFEST_NAME}:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新包存在未列入清单的文件")
                entrypoint = _safe_relative(manifest["entrypoint"])
                if entrypoint not in listed:
                    raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", "Windows 更新入口未列入文件清单")
                return {"manifest": manifest, "total_bytes": total, "file_count": len(listed)}
        except WindowsUpdateHelperError:
            raise
        except (OSError, zipfile.BadZipFile, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise WindowsUpdateHelperError("UPD-WIN-PACKAGE-002", f"Windows 更新包无法验证：{exc}") from exc

    @staticmethod
    def extract(archive_path: str | Path, destination: str | Path, *, expected_release_id: str) -> dict[str, Any]:
        inspected = WindowsApplicationPackage.inspect(archive_path, expected_release_id=expected_release_id)
        target = Path(destination).resolve()
        target.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(Path(archive_path).resolve(), "r") as archive:
                for record in inspected["manifest"]["files"]:
                    output = target / Path(*PurePosixPath(record["path"]).parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(record["path"]) as source, output.open("xb") as sink:
                        shutil.copyfileobj(source, sink, length=1024 * 1024)
                        sink.flush()
                        os.fsync(sink.fileno())
            return inspected
        except Exception:
            _safe_remove_tree(target, target.parent)
            raise


def load_handoff(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WindowsUpdateHelperError("UPD-WIN-HANDOFF-001", f"更新交接记录无法读取：{exc}") from exc
    required = {
        "schema_version", "action", "artifact_path", "artifact_sha256", "artifact_length",
        "release_id", "release_sequence", "install_boundary", "install_root", "restart_command",
        "parent_pid", "handoff_root",
    }
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != 2:
        raise WindowsUpdateHelperError("UPD-WIN-HANDOFF-001", "更新交接记录字段或版本无效")
    if value["action"] not in {"stage", "apply"} or value["install_boundary"] not in {"windows_update_helper"}:
        raise WindowsUpdateHelperError("UPD-WIN-HANDOFF-001", "更新交接动作或边界无效")
    if not isinstance(value["restart_command"], list) or not value["restart_command"]:
        raise WindowsUpdateHelperError("UPD-WIN-HANDOFF-001", "更新后启动命令无效")
    return value


class WindowsUpdateHelper:
    def __init__(self, handoff_path: str | Path) -> None:
        self.handoff_path = Path(handoff_path).resolve()
        self.value = load_handoff(self.handoff_path)
        self.install_root = Path(self.value["install_root"]).resolve()
        self.handoff_root = Path(self.value["handoff_root"]).resolve()
        self.release_id = str(self.value["release_id"])
        self.release_key = hashlib.sha256(self.release_id.encode("utf-8")).hexdigest()
        self.artifact = Path(self.value["artifact_path"]).resolve()
        self.staging_parent = self.install_root.parent / f".{self.install_root.name}-update-staging"
        self.staging = self.staging_parent / self.release_key
        self.backup = self.install_root.parent / f".{self.install_root.name}-previous"
        self.failed = self.install_root.parent / f".{self.install_root.name}-failed-{self.release_key[:12]}"
        self.receipt = self.handoff_root / "receipts" / f"{self.release_key}.json"
        self.probe = self.handoff_root / "probes" / f"{self.release_key}.json"

    def verify_artifact(self) -> dict[str, Any]:
        length, digest = _sha256(self.artifact)
        if length != int(self.value["artifact_length"]) or digest != str(self.value["artifact_sha256"]):
            raise WindowsUpdateHelperError("UPD-WIN-ARTIFACT-001", "Windows 应用更新产物大小或哈希不一致")
        return WindowsApplicationPackage.inspect(self.artifact, expected_release_id=self.release_id)

    def stage(self) -> None:
        self.receipt.unlink(missing_ok=True)
        self.probe.unlink(missing_ok=True)
        self.verify_artifact()
        self.staging_parent.mkdir(parents=True, exist_ok=True)
        _safe_remove_tree(self.staging, self.staging_parent)
        inspected = WindowsApplicationPackage.extract(
            self.artifact, self.staging, expected_release_id=self.release_id,
        )
        _atomic_json(self.staging / ".easycode-staged.json", {
            "schema_version": 1,
            "release_id": self.release_id,
            "artifact_sha256": self.value["artifact_sha256"],
            "entrypoint": inspected["manifest"]["entrypoint"],
        })

    def _write_result(self, status: str, *, code: str = "", message: str = "") -> None:
        _atomic_json(self.receipt, {
            "schema_version": 1,
            "release_id": self.release_id,
            "release_sequence": int(self.value["release_sequence"]),
            "artifact_sha256": self.value["artifact_sha256"],
            "status": status,
            "code": code,
            "message": message,
        })

    def spawn_apply_worker(self, command: Sequence[str]) -> None:
        if not self.staging.is_dir():
            raise WindowsUpdateHelperError("UPD-WIN-STAGE-001", "Windows 应用更新尚未完整暂存")
        flags = 0
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen(
            [*map(str, command), "--execute-handoff", str(self.handoff_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                timeout=3, check=False, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return str(pid) in result.stdout
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def execute(self, *, wait_seconds: float = 300, health_seconds: float = 30) -> None:
        deadline = time.monotonic() + wait_seconds
        parent_pid = int(self.value["parent_pid"])
        while self._pid_alive(parent_pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        if self._pid_alive(parent_pid):
            raise WindowsUpdateHelperError("UPD-WIN-BUSY-001", "等待旧进程退出超时，未替换任何文件")
        self.verify_artifact()
        marker = json.loads((self.staging / ".easycode-staged.json").read_text(encoding="utf-8"))
        if marker.get("release_id") != self.release_id or marker.get("artifact_sha256") != self.value["artifact_sha256"]:
            raise WindowsUpdateHelperError("UPD-WIN-STAGE-001", "Windows 暂存目录与交接记录不一致")
        restart = [str(item) for item in self.value["restart_command"]]
        if marker.get("entrypoint") != _safe_relative(restart[0]):
            raise WindowsUpdateHelperError("UPD-WIN-STAGE-001", "更新包入口与本机启动入口不一致")
        executable = self.install_root / _safe_relative(restart[0])
        token = secrets.token_urlsafe(32)
        self.receipt.unlink(missing_ok=True)
        self.probe.unlink(missing_ok=True)
        self.probe.parent.mkdir(parents=True, exist_ok=True)
        _safe_remove_tree(self.failed, self.install_root.parent)
        if self.backup.exists():
            _safe_remove_tree(self.backup, self.install_root.parent)
        swapped_old = False
        try:
            if self.install_root.exists():
                os.replace(self.install_root, self.backup)
                swapped_old = True
            os.replace(self.staging, self.install_root)
            environment = os.environ.copy()
            environment["EASYCODE_WINDOWS_UPDATE_RECEIPT"] = str(self.probe)
            environment["EASYCODE_WINDOWS_UPDATE_TOKEN"] = token
            try:
                process = subprocess.Popen(
                    [str(executable), *restart[1:]], cwd=self.install_root, env=environment,
                    close_fds=True, creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
                )
            except OSError as exc:
                raise WindowsUpdateHelperError(
                    "UPD-WIN-START-001", "新版本进程无法启动，正在恢复上一版本",
                ) from exc
            health_deadline = time.monotonic() + health_seconds
            healthy = False
            while time.monotonic() < health_deadline:
                if self.probe.is_file():
                    record = json.loads(self.probe.read_text(encoding="utf-8-sig"))
                    healthy = record.get("token") == token and record.get("status") == "healthy"
                    if healthy:
                        break
                if process.poll() is not None:
                    break
                time.sleep(0.2)
            if not healthy:
                if process.poll() is None:
                    process.terminate()
                raise WindowsUpdateHelperError("UPD-HEALTH-001", "新版本未在限定时间内确认启动健康")
            _atomic_json(self.receipt, {
                "schema_version": 1,
                "release_id": self.release_id,
                "release_sequence": int(self.value["release_sequence"]),
                "artifact_sha256": self.value["artifact_sha256"],
                "status": "healthy",
                "token": token,
            })
        except Exception as exc:
            if self.install_root.exists():
                os.replace(self.install_root, self.failed)
            if swapped_old and self.backup.exists():
                os.replace(self.backup, self.install_root)
                old_executable = self.install_root / _safe_relative(restart[0])
                if old_executable.is_file():
                    subprocess.Popen([str(old_executable), *restart[1:]], cwd=self.install_root, close_fds=True)
            code = exc.code if isinstance(exc, WindowsUpdateHelperError) else "UPD-WIN-INSTALL-001"
            self._write_result("rolled_back", code=code, message=str(exc))
            raise


def write_startup_health_receipt() -> bool:
    raw_path = str(os.environ.get("EASYCODE_WINDOWS_UPDATE_RECEIPT") or "").strip()
    token = str(os.environ.get("EASYCODE_WINDOWS_UPDATE_TOKEN") or "").strip()
    if not raw_path or not token:
        return False
    path = Path(raw_path).resolve()
    _atomic_json(path, {"schema_version": 1, "status": "healthy", "token": token, "pid": os.getpid()})
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EasyCode Windows 更新助手")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--handoff")
    group.add_argument("--execute-handoff")
    args = parser.parse_args(list(argv) if argv is not None else None)
    path = args.handoff or args.execute_handoff
    try:
        helper = WindowsUpdateHelper(path)
        if args.execute_handoff:
            helper.execute()
            return 0
        if helper.value["action"] == "stage":
            helper.stage()
            print("Windows 更新已验证并完整暂存")
            return 0
        # A frozen helper is self-contained. During source tests the executable
        # command is supplied by the caller and this path is not used.
        if getattr(sys, "frozen", False):
            worker = helper.handoff_root / "workers" / f"update-helper-{helper.release_key}.exe"
            worker.parent.mkdir(parents=True, exist_ok=True)
            temporary = worker.with_suffix(".tmp")
            shutil.copy2(sys.executable, temporary)
            os.replace(temporary, worker)
            command = [str(worker)]
        else:
            command = [sys.executable, "-m", "core.vnext.windows_update_helper_v6"]
        helper.spawn_apply_worker(command)
        print("将在当前程序关闭后完成更新并重新启动")
        return 10
    except WindowsUpdateHelperError as exc:
        if args.execute_handoff and "helper" in locals():
            helper._write_result("rolled_back", code=exc.code, message=str(exc))
        print(str(exc), file=sys.stderr)
        return 2


__all__ = [
    "WindowsApplicationPackage", "WindowsUpdateHelper", "WindowsUpdateHelperError",
    "load_handoff", "write_startup_health_receipt", "main",
]


if __name__ == "__main__":
    multiprocessing = __import__("multiprocessing")
    multiprocessing.freeze_support()
    raise SystemExit(main())
