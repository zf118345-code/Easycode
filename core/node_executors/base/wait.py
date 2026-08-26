# core/node_executors/base/wait.py
import time
from datetime import datetime, timedelta

from core.node_executors.base_class import BaseNodeExecutor
from core.registry import NodeExecutorRegistry
from core.utils import resolve_template_string


@NodeExecutorRegistry.register('wait')
class WaitNodeExecutor(BaseNodeExecutor):
    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        normalized = str(value or '').strip().replace('T', ' ')
        if normalized.endswith('Z'):
            normalized = normalized[:-1] + '+00:00'
        try:
            return datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError('请使用 YYYY-MM-DD HH:mm:ss 或 ISO 8601 时间') from exc

    @staticmethod
    def _parse_clock(value: str, now: datetime) -> datetime:
        raw = str(value or '').strip()
        parsed = None
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                parsed = datetime.strptime(raw, fmt).time()
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError('每日时间请使用 HH:mm 或 HH:mm:ss')
        target = datetime.combine(now.date(), parsed, tzinfo=now.tzinfo)
        if target <= now:
            target += timedelta(days=1)
        return target

    @staticmethod
    def _sleep_interruptibly(context, seconds: float, poll_ms: int) -> bool:
        # Lightweight/test contexts without a stop signal retain the original
        # single-sleep behavior.  A real GraphExecutor exposes is_stopped and
        # is polled so long waits can always be cancelled promptly.
        if not hasattr(context, 'is_stopped'):
            time.sleep(max(0.0, float(seconds or 0.0)))
            return True
        deadline = time.monotonic() + max(0.0, float(seconds or 0.0))
        interval = max(0.02, min(1.0, int(poll_ms or 100) / 1000.0))
        while True:
            if bool(getattr(context, 'is_stopped', False)):
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(interval, remaining))

    def execute(self, node, context):
        params = node.params
        mode = str(params.get('wait_mode') or 'duration').strip().lower()
        poll_ms = int(params.get('poll_interval_ms', 100) or 100)
        now = datetime.now().astimezone()
        try:
            if mode == 'duration':
                duration_ms = max(0.0, float(params.get('duration_ms', 1000) or 0))
                target = now + timedelta(milliseconds=duration_ms)
                seconds = duration_ms / 1000.0
                context.log(f'等待 {duration_ms:.0f} ms（可中止）')
            elif mode == 'until_datetime':
                raw = resolve_template_string(params.get('target_datetime', ''), context)
                target = self._parse_datetime(str(raw))
                if target.tzinfo is None:
                    target = target.replace(tzinfo=now.tzinfo)
                else:
                    target = target.astimezone(now.tzinfo)
                seconds = max(0.0, (target - datetime.now().astimezone()).total_seconds())
                context.log(f'等待到 {target.isoformat(sep=" ", timespec="seconds")}')
            elif mode == 'until_clock':
                raw = resolve_template_string(params.get('target_clock', ''), context)
                target = self._parse_clock(str(raw), now)
                seconds = max(0.0, (target - datetime.now().astimezone()).total_seconds())
                context.log(f'等待到下一次 {target.strftime("%Y-%m-%d %H:%M:%S")}')
            else:
                return self.build_result(False, f'不支持的等待模式: {mode}')
        except (TypeError, ValueError) as exc:
            context.log(f'等待参数无效: {exc}', 'error')
            return self.build_result(False, str(exc))

        if not self._sleep_interruptibly(context, seconds, poll_ms):
            return self.build_result(False, '等待已被停止', {'cancelled': True})
        return self.build_result(True, extra={'waited_until': target.isoformat()})
