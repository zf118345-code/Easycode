"""Frontend API adapters must match the FastAPI OpenAPI method/path contract."""

from __future__ import annotations

import re
from pathlib import Path

from api.app import app


API_DIR = Path(__file__).resolve().parents[1] / 'frontend' / 'src' / 'api'
SOURCE_DIR = API_DIR.parent
CALL_RE = re.compile(
    r"client\.(get|post|put|delete|patch)\(\s*([`'\"])(/api/.*?)\2",
    re.DOTALL,
)
DYNAMIC_RE = re.compile(r'\$\{.*?\}')
PARAM_RE = re.compile(r'\{[^/{}]+\}')
DIRECT_GET_RE = re.compile(
    r"(?:new\s+EventSource|window\.open)\(\s*([`'\"])(/api/.*?)\1",
    re.DOTALL,
)


def _shape(path: str) -> str:
    """Normalize JS template values and OpenAPI path params to one shape."""
    route_path = path.split('?', 1)[0]
    return PARAM_RE.sub(':param', DYNAMIC_RE.sub(':param', route_path))


def test_frontend_api_adapters_match_openapi_contract():
    openapi = app.openapi()
    backend = {
        (method.upper(), _shape(path))
        for path, operations in openapi['paths'].items()
        for method in operations
        if method.upper() in {'GET', 'POST', 'PUT', 'DELETE', 'PATCH'}
    }
    frontend = []
    for source in sorted(API_DIR.glob('*.js')):
        text = source.read_text(encoding='utf-8')
        for method, _quote, path in CALL_RE.findall(text):
            frontend.append((source.name, method.upper(), path, _shape(path)))

    assert frontend, '未扫描到任何前端 API 调用'
    missing = [
        f'{source}: {method} {path}'
        for source, method, path, shape in frontend
        if (method, shape) not in backend
    ]
    assert not missing, '前端调用在 FastAPI OpenAPI 中不存在：\n' + '\n'.join(missing)


def test_all_frontend_client_calls_match_openapi_and_do_not_bypass_shared_client():
    openapi = app.openapi()
    backend = {
        (method.upper(), _shape(path))
        for path, operations in openapi['paths'].items()
        for method in operations
        if method.upper() in {'GET', 'POST', 'PUT', 'DELETE', 'PATCH'}
    }
    missing = []
    raw_axios = []
    missing_direct_gets = []
    for source in sorted((*SOURCE_DIR.rglob('*.js'), *SOURCE_DIR.rglob('*.vue'))):
        if '__tests__' in source.parts:
            continue
        # A legacy control registry is GBK encoded; contract scanning only
        # needs ASCII API/import tokens, so replacement decoding is sufficient.
        text = source.read_text(encoding='utf-8', errors='replace')
        if source.name != 'client.js' and re.search(r"from\s+['\"]axios['\"]", text):
            raw_axios.append(str(source.relative_to(SOURCE_DIR)))
        for method, _quote, path in CALL_RE.findall(text):
            if (method.upper(), _shape(path)) not in backend:
                missing.append(f'{source.relative_to(SOURCE_DIR)}: {method.upper()} {path}')
        for _quote, path in DIRECT_GET_RE.findall(text):
            if ('GET', _shape(path)) not in backend:
                missing_direct_gets.append(f'{source.relative_to(SOURCE_DIR)}: GET {path}')

    assert not raw_axios, '业务组件绕过共享 API 客户端，工作区身份与统一错误处理会失效：\n' + '\n'.join(raw_axios)
    assert not missing, '前端直接调用在 FastAPI OpenAPI 中不存在：\n' + '\n'.join(missing)
    assert not missing_direct_gets, 'EventSource/window.open 入口在 FastAPI OpenAPI 中不存在：\n' + '\n'.join(missing_direct_gets)
