from __future__ import annotations

from api.contracts.capture import CaptureActionRequest, CaptureSessionRegisterRequest, FieldCaptureRequest


def test_native_capture_action_payload_matches_strict_contract():
    payload = CaptureActionRequest.model_validate({
        'session_id': 'ide_1',
        'snapshot_id': 'snap_1',
        'capture_chain_id': 'chain_1',
        'capture_context': {'ports': []},
        'reference_size': [960, 540],
        'port': {'stableId': 'success', 'role': 'success'},
        'operation_id': 'capture_native_1',
        'kind': 'click',
        'point': [320, 240],
    })

    assert payload.point == (320, 240)
    assert payload.reference_size == (960, 540)


def test_capture_session_contract_accepts_legacy_and_vnext_frontends():
    common = {
        'session_id': 'session_1',
        'project_path': 'D:/project',
        'workspace_id': 'workspace_1',
        'workspace_generation': 3,
        'project_name': 'project',
        'capture_context': {},
        'execution_state': 'idle',
        'recording_active': False,
        'origin': 'http://localhost:5173',
    }

    assert CaptureSessionRegisterRequest.model_validate(common).workspace_kind == 'legacy'
    assert CaptureSessionRegisterRequest.model_validate({
        **common,
        'workspace_kind': 'vnext',
        'capture_context': {'workspace_kind': 'vnext', 'target_id': 'target_1'},
    }).workspace_kind == 'vnext'


def test_field_capture_contract_distinguishes_parameter_and_resource_destinations():
    parameter = FieldCaptureRequest.model_validate({
        'request_id': 'field_parameter', 'selection_mode': 'point',
    })
    resource = FieldCaptureRequest.model_validate({
        'request_id': 'field_resource', 'selection_mode': 'asset',
        'category': 'page', 'destination': 'resource',
    })

    assert parameter.destination == 'parameter'
    assert resource.destination == 'resource'


def test_control_capture_contract_accepts_probe_and_exact_selector_confirmation():
    field = FieldCaptureRequest.model_validate({
        'request_id': 'field_control', 'selection_mode': 'control',
    })
    probe = CaptureActionRequest.model_validate({
        'snapshot_id': 'snap', 'reference_size': [800, 600],
        'kind': 'field_control_probe', 'field_request_id': 'field_control',
        'point': [120, 80],
    })
    confirm = CaptureActionRequest.model_validate({
        'snapshot_id': 'snap', 'reference_size': [800, 600],
        'kind': 'field_confirm', 'field_request_id': 'field_control',
        'selector': {'control_selector.field.target_id': 'target'},
    })
    assert field.selection_mode == 'control'
    assert probe.point == (120, 80)
    assert confirm.selector == {'control_selector.field.target_id': 'target'}


def test_color_capture_contract_keeps_four_integer_channels() -> None:
    field = FieldCaptureRequest.model_validate({
        'request_id': 'field_color', 'selection_mode': 'color',
    })
    payload = CaptureActionRequest.model_validate({
        'snapshot_id': 'snap', 'reference_size': [800, 600],
        'kind': 'field_confirm', 'field_request_id': 'field_color',
        'point': [120, 80],
        'color': {'red': 97, 'green': 98, 'blue': 100, 'alpha': 255},
    })

    assert field.selection_mode == 'color'
    assert payload.color == {'red': 97, 'green': 98, 'blue': 100, 'alpha': 255}


def test_capture_http_boundary_rejects_unknown_and_malformed_payloads(client):
    cases = [
        ('/api/capture/trigger', {'field_capture': {
            'request_id': 'field_1', 'selection_mode': 'point', 'max_rects': 33,
        }}),
        ('/api/capture/assets', {
            'snapshot_id': 'snap_1', 'rects': [[0, 0, 20]], 'unexpected': True,
        }),
        ('/api/capture/action', {
            'kind': 'click', 'reference_size': [960, 540], 'point': [10, 20],
        }),
        ('/api/capture/replay', {
            'recording_session_id': '../escape', 'frame_index': 0,
        }),
    ]

    for endpoint, payload in cases:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 422, (endpoint, response.text)


def test_capture_openapi_models_are_strict(client):
    schemas = client.get('/openapi.json').json()['components']['schemas']
    for name in (
        'CaptureActionRequest',
        'CaptureAssetSaveRequest',
        'CaptureSessionRegisterRequest',
        'CaptureTriggerRequest',
    ):
        assert schemas[name]['additionalProperties'] is False
