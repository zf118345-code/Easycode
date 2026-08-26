from core.services.project_workspace_service import project_workspace_manager


def test_choose_file_dialog_api_forwards_title_and_extensions(client, monkeypatch):
    received = {}

    def choose_file(title, extensions):
        received.update(title=title, extensions=extensions)
        return r'D:\packages\demo.ebt'

    monkeypatch.setattr(project_workspace_manager, 'choose_file', choose_file)
    response = client.post('/api/workspaces/choose-file', json={
        'title': '选择任务包',
        'extensions': ['.ebt'],
    })

    assert response.status_code == 200
    assert response.json()['path'].endswith('demo.ebt')
    assert received == {'title': '选择任务包', 'extensions': ['.ebt']}
