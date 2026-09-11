"""Bounded resident target drivers for interactive capture.

Interactive capture is a hot path: constructing an Android target driver starts a
scrcpy server and video decoder, while constructing a Windows driver repeats target
discovery.  Runtime executions still own their private drivers; this pool is only
for short authoring/Player capture sessions and serializes access per target.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


CAPTURE_DRIVER_IDLE_TTL_SECONDS = 5 * 60
MAX_CAPTURE_DRIVERS_PER_OWNER = 2


@dataclass
class CaptureTargetEntry:
    key: str
    owner: str
    project_path: str
    target_signature: str
    driver: Any
    last_used_at: float = field(default_factory=time.monotonic)
    lock: threading.RLock = field(default_factory=threading.RLock)


class CaptureTargetPool:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, CaptureTargetEntry] = {}
        self._building: dict[str, threading.Event] = {}

    @staticmethod
    def _signature(target: dict[str, Any]) -> str:
        return json.dumps(target, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _key(cls, owner: str, project_path: str, target: dict[str, Any]) -> str:
        identity = str(target.get("target_id") or target.get("device_serial") or target.get("window_title") or "target")
        return "|".join((
            str(owner or "capture"),
            os.path.normcase(os.path.realpath(project_path)),
            str(target.get("type") or "unknown"),
            identity,
        ))

    @staticmethod
    def _close(entry: CaptureTargetEntry | None) -> None:
        if entry is None:
            return
        try:
            with entry.lock:
                entry.driver.close()
        except Exception:
            # Pool eviction is best effort. The next acquire creates a clean
            # driver and the caller still receives the original capture error.
            pass

    def _expired_locked(self, now: float) -> list[CaptureTargetEntry]:
        expired = [
            entry for entry in self._entries.values()
            if now - entry.last_used_at > CAPTURE_DRIVER_IDLE_TTL_SECONDS
        ]
        for entry in expired:
            self._entries.pop(entry.key, None)
        return expired

    def acquire(
        self,
        owner: str,
        project_path: str,
        target: dict[str, Any],
        *,
        force_new: bool = False,
    ) -> tuple[CaptureTargetEntry, bool]:
        """Return a target-scoped driver and whether it was reused.

        Driver construction happens outside the registry lock because starting a
        device stream can take seconds. Duplicate construction is resolved when
        publishing the candidate and is harmless because capture requests are
        already serialized by each owning service.
        """

        from core.vnext.target_runtime import create_target_driver

        project_path = os.path.abspath(project_path)
        key = self._key(owner, project_path, target)
        signature = self._signature(target)
        while True:
            now = time.monotonic()
            stale: list[CaptureTargetEntry] = []
            with self._lock:
                stale.extend(self._expired_locked(now))
                current = self._entries.get(key)
                if current is not None and (force_new or current.target_signature != signature):
                    self._entries.pop(key, None)
                    stale.append(current)
                    current = None
                    force_new = False
                if current is not None:
                    current.last_used_at = now
                    waiter = None
                    build_here = False
                else:
                    waiter = self._building.get(key)
                    build_here = waiter is None
                    if build_here:
                        waiter = threading.Event()
                        self._building[key] = waiter
            for entry in stale:
                self._close(entry)
            if current is not None:
                return current, True
            if build_here:
                break
            # Prewarm and an immediate user click can overlap. Coalesce them
            # instead of starting a second scrcpy server/WGC provider.
            assert waiter is not None
            if not waiter.wait(15.0):
                raise RuntimeError("捕获目标初始化超时")

        try:
            driver = create_target_driver(project_path, target)
            if driver is None:
                raise RuntimeError("当前目标没有可用的捕获驱动")
        except Exception:
            with self._lock:
                completed = self._building.pop(key, None)
            if completed is not None:
                completed.set()
            raise
        candidate = CaptureTargetEntry(
            key=key,
            owner=str(owner or "capture"),
            project_path=project_path,
            target_signature=signature,
            driver=driver,
        )
        displaced: list[CaptureTargetEntry] = []
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None and existing.target_signature == signature and not force_new:
                existing.last_used_at = now
                selected = existing
                reused = True
                displaced.append(candidate)
            else:
                if existing is not None:
                    displaced.append(existing)
                self._entries[key] = candidate
                selected = candidate
                reused = False
            owned = sorted(
                (entry for entry in self._entries.values() if entry.owner == candidate.owner),
                key=lambda item: item.last_used_at,
            )
            while len(owned) > MAX_CAPTURE_DRIVERS_PER_OWNER:
                victim = owned.pop(0)
                if victim is selected:
                    continue
                self._entries.pop(victim.key, None)
                displaced.append(victim)
            completed = self._building.pop(key, None)
        if completed is not None:
            completed.set()
        for entry in displaced:
            self._close(entry)
        return selected, reused

    def invalidate(self, entry: CaptureTargetEntry) -> None:
        with self._lock:
            current = self._entries.get(entry.key)
            if current is entry:
                self._entries.pop(entry.key, None)
        self._close(entry)

    def close_owner(self, owner: str) -> None:
        with self._lock:
            selected = [entry for entry in self._entries.values() if entry.owner == owner]
            for entry in selected:
                self._entries.pop(entry.key, None)
        for entry in selected:
            self._close(entry)

    def close_all(self) -> None:
        with self._lock:
            selected = list(self._entries.values())
            self._entries.clear()
        for entry in selected:
            self._close(entry)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._entries),
                "owners": sorted({entry.owner for entry in self._entries.values()}),
            }


capture_target_pool = CaptureTargetPool()


__all__ = ["CaptureTargetEntry", "CaptureTargetPool", "capture_target_pool"]
