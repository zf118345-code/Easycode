from __future__ import annotations

import re
import time
from typing import Any

from core.capabilities.registry import register_capability


def _parse_rows(text: str, columns: list[str], column_pattern: str) -> list[dict[str, Any]]:
    rows = []
    splitter = re.compile(column_pattern or r'\s{2,}|\t+')
    for raw_line in str(text or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        values = [part.strip() for part in splitter.split(line) if part.strip()]
        if columns:
            item = {str(name): values[index] if index < len(values) else '' for index, name in enumerate(columns)}
            if len(values) > len(columns):
                item['_extra'] = values[len(columns):]
        else:
            item = {'text': line}
        rows.append(item)
    return rows


@register_capability(
    'vision.collect_list',
    version='1.0.0',
    name='视觉列表采集',
    description='按区域OCR采集多页视觉列表，滑动、去重并在页面重复时停止。',
    permissions=['screen.read', 'input.gesture'],
    timeout_ms=120000,
    idempotent=False,
    inputs=[
        {'name': 'region', 'type': 'list', 'required': True},
        {'name': 'reference_size', 'type': 'list', 'default': [0, 0]},
        {'name': 'columns', 'type': 'list', 'default': []},
        {'name': 'key_fields', 'type': 'list', 'default': []},
        {'name': 'column_pattern', 'type': 'str', 'default': r'\s{2,}|\t+'},
        {'name': 'max_pages', 'type': 'int', 'default': 20},
        {'name': 'swipe_start', 'type': 'list', 'required': True},
        {'name': 'swipe_end', 'type': 'list', 'required': True},
        {'name': 'swipe_duration_ms', 'type': 'int', 'default': 300},
        {'name': 'hold_after_ms', 'type': 'int', 'default': 80},
        {'name': 'settle_ms', 'type': 'int', 'default': 250},
        {'name': 'gray_scale', 'type': 'bool', 'default': False},
        {'name': 'gray_threshold', 'type': 'int', 'default': 128},
    ],
    outputs=[
        {'name': 'items', 'type': 'list'},
        {'name': 'pages_scanned', 'type': 'int'},
        {'name': 'stop_reason', 'type': 'str'},
    ],
)
def collect_list(context, **inputs):
    region = list(inputs.get('region') or [])
    if len(region) != 4 or int(region[2]) <= 0 or int(region[3]) <= 0:
        return {'success': False, 'code': 'INVALID_REGION', 'message': '列表采集区域必须为 [x, y, 宽, 高]'}
    reference_size = list(inputs.get('reference_size') or [0, 0])
    columns = [str(item) for item in (inputs.get('columns') or [])]
    key_fields = [str(item) for item in (inputs.get('key_fields') or [])]
    max_pages = max(1, min(500, int(inputs.get('max_pages', 20) or 20)))
    swipe_start = list(inputs.get('swipe_start') or [])
    swipe_end = list(inputs.get('swipe_end') or [])
    if len(swipe_start) < 2 or len(swipe_end) < 2:
        return {'success': False, 'code': 'INVALID_SWIPE', 'message': '列表采集需要滑动起点和终点'}
    items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    previous_text = None
    stop_reason = 'max_pages'
    pages_scanned = 0
    for page_index in range(max_pages):
        if context.cancelled:
            return {'success': False, 'code': 'CANCELLED', 'message': '列表采集已被停止', 'data': {'items': items, 'pages_scanned': pages_scanned}}
        text = context.ocr_region(
            region,
            reference_size=reference_size,
            gray_scale=bool(inputs.get('gray_scale', False)),
            gray_threshold=int(inputs.get('gray_threshold', 128) or 128),
        )
        pages_scanned += 1
        if text == previous_text:
            stop_reason = 'repeated_page'
            break
        previous_text = text
        page_rows = _parse_rows(text, columns, str(inputs.get('column_pattern') or r'\s{2,}|\t+'))
        for row in page_rows:
            if key_fields:
                key = '\x1f'.join(str(row.get(field, '')) for field in key_fields)
            else:
                key = repr(sorted(row.items()))
            if key not in seen_keys:
                seen_keys.add(key)
                items.append(row)
        context.report_progress(pages_scanned, max_pages, f'列表采集第 {pages_scanned} 页，累计 {len(items)} 项')
        if page_index + 1 >= max_pages:
            break
        swipe_result = context.swipe(
            swipe_start,
            swipe_end,
            reference_size=reference_size,
            duration_ms=int(inputs.get('swipe_duration_ms', 300) or 300),
            hold_after_ms=int(inputs.get('hold_after_ms', 80) or 0),
        )
        if not swipe_result.get('ok'):
            return {
                'success': False,
                'code': 'SWIPE_FAILED',
                'message': swipe_result.get('message', '列表滑动失败'),
                'data': {'items': items, 'pages_scanned': pages_scanned},
            }
        settle_s = max(0, min(10000, int(inputs.get('settle_ms', 250) or 0))) / 1000.0
        deadline = time.monotonic() + settle_s
        while time.monotonic() < deadline and not context.cancelled:
            time.sleep(min(0.05, deadline - time.monotonic()))
    return {
        'success': True,
        'code': 'LIST_COLLECTED',
        'message': f'列表采集完成，共 {len(items)} 项',
        'data': {'items': items, 'pages_scanned': pages_scanned, 'stop_reason': stop_reason},
    }
