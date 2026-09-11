"""One-shot worker process for explicitly trusted extension code.

The worker isolates lifetime, crashes, logging and serialization.  It is not a
security sandbox: trusted Python still runs with the current OS user's access.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

# Importing trusted development code must never mutate the signed package by
# creating __pycache__.  The Worker is one-shot, so bytecode caching provides
# no useful speed-up and would invalidate the exact package signature closure.
sys.dont_write_bytecode = True


class WorkerContext:
    def __init__(self, variables: dict[str, Any] | None = None) -> None:
        self.variables = dict(variables or {})
        self.logs: list[dict[str, str]] = []

    @property
    def is_stopped(self) -> bool:
        # Cancellation is enforced by terminating this one-shot process.  The
        # property exists so well-behaved extensions can share IDE/runtime code.
        return False

    def log(self, message: Any, level: str = "info") -> None:
        self.logs.append({"level": str(level or "info"), "message": str(message)})


def _load_source(path: Path):
    if path.suffix.casefold() != ".py" or not path.is_file() or path.is_symlink():
        raise ValueError("开发入口必须是普通 Python 文件")
    module_name = f"easycode_extension_{os.getpid()}"
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ValueError("扩展开发入口无法加载")
    module = importlib.util.module_from_spec(specification)
    sys.path.insert(0, str(path.parent))
    specification.loader.exec_module(module)
    return module


def _load_sealed(artifact: Path):
    if not artifact.is_file() or artifact.is_symlink():
        raise ValueError("密封运行产物不存在")
    temporary = Path(tempfile.mkdtemp(prefix="EasyCodeExtension-"))
    try:
        with zipfile.ZipFile(artifact, "r") as archive:
            descriptor = json.loads(archive.read("ecx-runtime.json"))
            module_path = str(descriptor.get("module") or "")
            parsed = PurePosixPath(module_path)
            if (
                not module_path
                or parsed.is_absolute()
                or ".." in parsed.parts
                or parsed.suffix.casefold() != ".pyc"
            ):
                raise ValueError("密封运行模块无效")
            target = temporary.joinpath(*parsed.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(module_path))
        module_name = f"easycode_sealed_extension_{os.getpid()}"
        loader = importlib.machinery.SourcelessFileLoader(module_name, str(target))
        specification = importlib.util.spec_from_loader(module_name, loader)
        if specification is None:
            raise ValueError("密封运行模块无法加载")
        module = importlib.util.module_from_spec(specification)
        sys.path.insert(0, str(target.parent))
        loader.exec_module(module)
        return module
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(temporary / "runtime"))
        shutil.rmtree(temporary, ignore_errors=True)


def _response(payload: dict[str, Any]) -> None:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        encoded = json.dumps({
            "ok": False,
            "error": {"code": "extension.result_not_serializable", "message": str(exc)},
            "logs": payload.get("logs") or [],
        }, ensure_ascii=False)
    sys.stdout.write(encoded)
    sys.stdout.flush()


def main() -> int:
    context: WorkerContext | None = None
    try:
        request = json.loads(sys.stdin.read())
        if not isinstance(request, dict):
            raise ValueError("Worker 请求必须是 JSON 对象")
        mode = str(request.get("mode") or "")
        module = (
            _load_source(Path(str(request.get("entry_path") or "")).resolve())
            if mode == "development"
            else _load_sealed(Path(str(request.get("artifact_path") or "")).resolve())
            if mode == "sealed"
            else None
        )
        if module is None:
            raise ValueError("Worker 运行模式无效")
        entrypoint = str(request.get("entrypoint") or "")
        implementation = getattr(module, entrypoint, None)
        if not callable(implementation):
            raise ValueError(f"扩展入口不存在：{entrypoint}")
        arguments = request.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("扩展参数必须是 JSON 对象")
        context = WorkerContext(request.get("variables") if isinstance(request.get("variables"), dict) else {})
        result = implementation(context, **arguments)
        _response({"ok": True, "result": result, "logs": context.logs})
        return 0
    except Exception as exc:
        _response({
            "ok": False,
            "error": {
                "code": "extension.worker_failed",
                "message": str(exc) or exc.__class__.__name__,
                "exception_type": exc.__class__.__name__,
                "traceback": traceback.format_exc(limit=8),
            },
            "logs": context.logs if context is not None else [],
        })
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
