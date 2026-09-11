from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pydantic import ValidationError

from api.contracts.vnext import PlayerFormRequest, VNEXT_CONTRACT_VERSION, VisionPreviewRequest
from api.routers.vnext_router import create_vnext_router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_vnext_router())
    return TestClient(app)


def test_openapi_exposes_program_contracts_and_retired_source_boundary():
    api = client()
    document = api.get("/openapi.json").json()
    schemas = document["components"]["schemas"]

    assert schemas["ProgramCommandRequest"]["additionalProperties"] is False
    assert "SourceDocumentRequest" not in schemas
    assert "ApiErrorResponse" in schemas
    assert document["paths"]["/api/vnext/analyze"]["post"]["responses"]["410"]["content"]
    assert api.get("/api/vnext/meta").json()["api_contract_version"] == VNEXT_CONTRACT_VERSION
    assert "/api/vnext/player/android-package" in document["paths"]
    assert "post" in document["paths"]["/api/vnext/operation-recording/start"]


def test_every_format5_source_entry_returns_structured_410_even_for_old_payloads():
    api = client()
    cases = (
        ("post", "/api/vnext/analyze"),
        ("post", "/api/vnext/compile"),
        ("post", "/api/vnext/edit/call-argument"),
        ("post", "/api/vnext/run"),
        ("post", "/api/vnext/run-project"),
        ("get", "/api/vnext/sources"),
        ("put", "/api/vnext/sources"),
        ("post", "/api/vnext/sources/create"),
        ("get", "/api/vnext/functions/function_old/references"),
        ("patch", "/api/vnext/functions/function_old"),
        ("delete", "/api/vnext/functions/function_old"),
    )

    for method, path in cases:
        response = api.request(method, path, json={"legacy": "payload"})
        assert response.status_code == 410, (method, path, response.text)
        assert response.json()["detail"]["code"] == "source_api_retired"
        assert response.json()["detail"]["recovery"]["action"] == "fix_request"


def test_vision_preview_request_is_strict_and_bounds_runtime_tuning_values():
    request = VisionPreviewRequest(
        target_id='target.windows',
        function_id='official.text.recognize',
        region=[1, 2, 30, 40],
        preprocess={'ocr_preprocess.field.threshold': 127},
    )
    assert request.region == [1, 2, 30, 40]

    for payload in (
        {'target_id': 'target.windows', 'function_id': 'official.image.find', 'region': [1, 2, 3]},
        {'target_id': 'target.windows', 'function_id': 'official.image.find', 'similarity': 1.2},
        {'target_id': 'target.windows', 'function_id': 'official.text.recognize', 'unexpected': True},
    ):
        try:
            VisionPreviewRequest(**payload)
        except ValidationError:
            pass
        else:
            raise AssertionError(f'expected strict validation failure for {payload!r}')


def test_player_form_request_accepts_the_versioned_recording_feature():
    request = PlayerFormRequest.model_validate({
        'schema_version': 3,
        'title': 'Player',
        'features': {'recording': True},
        'pages': [],
        'bindings': [],
    })

    assert request.features.recording is True
    assert request.model_dump()['features'] == {'recording': True}

    defaulted = PlayerFormRequest.model_validate({
        'schema_version': 3,
        'pages': [],
    })
    assert defaulted.features.recording is False
