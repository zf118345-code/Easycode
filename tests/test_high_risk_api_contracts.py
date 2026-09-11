from __future__ import annotations


def test_high_risk_mutations_reject_unknown_fields(client):
    cases = [
        ('/api/workspaces/open', {'path': 'D:/project', 'initialise': True}),
        ('/api/templates/mkdir', {
            'project_path': 'D:/project', 'parent_path': '', 'folder_name': 'image', 'overwrite': True,
        }),
        ('/api/platform/messages', {
            'channel': 'jobs', 'payload': {}, 'ttl_second': 60,
        }),
    ]

    for endpoint, payload in cases:
        response = client.post(endpoint, json=payload)
        assert response.status_code == 422, (endpoint, response.text)


def test_high_risk_openapi_models_are_strict(client):
    schemas = client.get('/openapi.json').json()['components']['schemas']
    for name in (
        'ProjectWorkspaceOpenRequest',
        'TemplateFolderCreateRequest',
        'MessagePublishRequest',
        'LeaseMutationRequest',
        'RemoteLeaseMutationRequest',
    ):
        assert schemas[name]['additionalProperties'] is False
