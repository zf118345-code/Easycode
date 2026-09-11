"""Stable API error policy shared by routers and global handlers."""

from __future__ import annotations

from typing import Any

from api.request_context import current_request_id

_STATUS_POLICY: dict[int, tuple[str, bool, str]] = {
    400: ('bad_request', False, 'fix_request'),
    401: ('unauthorized', False, 'none'),
    403: ('forbidden', False, 'none'),
    404: ('not_found', False, 'none'),
    408: ('request_timeout', True, 'retry'),
    409: ('state_conflict', True, 'retry'),
    422: ('validation_error', False, 'fix_request'),
    429: ('rate_limited', True, 'retry'),
    500: ('internal_error', True, 'retry'),
    502: ('upstream_error', True, 'retry'),
    503: ('service_unavailable', True, 'retry'),
    504: ('upstream_timeout', True, 'retry'),
}


def status_policy(status_code: int) -> tuple[str, bool, str]:
    """Return stable code, retryability and recovery action for an HTTP status."""

    if status_code in _STATUS_POLICY:
        return _STATUS_POLICY[status_code]
    if status_code >= 500:
        return 'internal_error', True, 'retry'
    if status_code >= 400:
        return 'request_failed', False, 'none'
    return 'unknown', False, 'none'


def error_message(detail: Any, fallback: str = '请求失败') -> str:
    if isinstance(detail, dict):
        return str(detail.get('message') or fallback)
    return str(detail or fallback)


def failure_detail(
    code: str,
    message: str,
    *,
    request_id: str = '',
    retryable: bool | None = None,
    action: str = 'none',
    recovery_message: str = '',
    fields: list[dict[str, Any]] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        'code': str(code or 'request_failed'),
        'message': str(message or '请求失败'),
        'request_id': str(request_id or current_request_id()),
        'fields': fields or [],
        'recovery': {
            'retryable': bool(action == 'retry' if retryable is None else retryable),
            'action': str(action or 'none'),
            'message': str(recovery_message or ''),
        },
        'diagnostics': diagnostics or [],
    }


def detail_for_status(
    status_code: int,
    message: str,
    *,
    code: str = '',
    request_id: str = '',
    fields: list[dict[str, Any]] | None = None,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    default_code, retryable, action = status_policy(status_code)
    return failure_detail(
        code or default_code,
        message,
        request_id=request_id,
        retryable=retryable,
        action=action,
        fields=fields,
        diagnostics=diagnostics,
    )


def legacy_error_envelope(status_code: int, detail: Any, request_id: str) -> dict[str, Any]:
    """Add recoverable metadata without changing legacy ``detail`` semantics."""

    normalized = detail_for_status(status_code, error_message(detail), request_id=request_id)
    return {
        'detail': detail,
        'code': normalized['code'],
        'message': normalized['message'],
        'request_id': normalized['request_id'],
        'recovery': normalized['recovery'],
    }
