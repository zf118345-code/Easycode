from api.workspace_context import mutates_project_files, project_mutation_documents


def test_project_file_mutations_are_explicitly_classified():
    assert mutates_project_files('POST', '/api/workflow/save') is True
    assert mutates_project_files('PUT', '/api/functions/function_1') is True
    assert mutates_project_files('POST', '/api/templates/move') is True
    assert mutates_project_files('POST', '/api/capture/assets') is True
    assert mutates_project_files('POST', '/api/context') is True


def test_runtime_commands_do_not_trigger_workspace_fingerprint_scans():
    assert mutates_project_files('POST', '/api/capture/session/register') is False
    assert mutates_project_files('POST', '/api/capture/prewarm') is False
    assert mutates_project_files('POST', '/api/run') is False
    assert mutates_project_files('POST', '/api/execution/session-1/pause') is False
    assert mutates_project_files('POST', '/api/workspaces/acknowledge') is False
    assert mutates_project_files('GET', '/api/templates/move') is False


def test_hot_save_routes_expose_incremental_fingerprint_documents():
    assert project_mutation_documents('POST', '/api/workflow/save') == ('project.json', 'workflow.json')
    assert project_mutation_documents('PUT', '/api/functions/function_1') == ('project.json', 'workflow.json')
    assert project_mutation_documents('POST', '/api/exporter/schema') == ('project.json', 'form_schema.json')
    assert project_mutation_documents('POST', '/api/templates/move') is None
    assert project_mutation_documents('POST', '/api/run') == ()
