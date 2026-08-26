"""Small HTTP error boundary shared by API routers."""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException


def internal_http_error(operation: str, exc: Exception) -> HTTPException:
    """Log an unexpected exception and return a safe, traceable response.

    Expected domain/user errors must remain explicit ``HTTPException`` values
    and bypass this helper.  Unexpected Python exception text may contain
    absolute paths, command lines or secret values, so it belongs in the local
    backend log rather than the browser response.
    """
    error_id = uuid.uuid4().hex[:12]
    logging.getLogger('easycode.api').error(
        '%s [error_id=%s]: %s',
        operation,
        error_id,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return HTTPException(
        status_code=500,
        detail={
            'message': f'{operation}，请查看后端日志',
            'error_id': error_id,
        },
    )
