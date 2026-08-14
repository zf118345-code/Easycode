"""统一 API 响应格式工具"""

from typing import Any

from fastapi.responses import JSONResponse

from core.error_codes import ERROR_MESSAGES, ErrorCode


def success(data: Any = None, message: str = 'success') -> dict:
    """构建统一成功响应"""
    return {'code': ErrorCode.SUCCESS, 'data': data, 'message': message}


def error(code: int, message: str | None = None, data: Any = None) -> dict:
    """构建统一错误响应"""
    return {'code': code, 'data': data, 'message': message or ERROR_MESSAGES.get(code, '未知错误')}


def error_response(code: int, message: str | None = None, status_code: int = 400, data: Any = None) -> JSONResponse:
    """构建错误 JSONResponse（用于 FastAPI 路由直接返回）"""
    return JSONResponse(
        status_code=status_code,
        content=error(code, message, data),
    )
