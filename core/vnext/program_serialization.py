"""Deterministic JSON helpers shared by ProgramDocument and ECIR."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: BaseModel | dict[str, Any] | list[Any]) -> bytes:
    """Serialize a model to stable UTF-8 JSON with one trailing newline."""

    payload: Any = value.model_dump(mode='json') if isinstance(value, BaseModel) else value
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return (text + '\n').encode('utf-8')


def content_revision(content: bytes) -> str:
    return f'sha256:{hashlib.sha256(content).hexdigest()}'


__all__ = ['canonical_json_bytes', 'content_revision']

