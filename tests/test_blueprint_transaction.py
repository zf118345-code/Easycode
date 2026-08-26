import json
import os
import shutil

import pytest

from core.project_schema import new_project_documents
from core.services.asset_service import AssetService
from core.services.blueprint_service import BlueprintService


def make_project(path):
    for filename, value in new_project_documents('transaction').items():
        (path / filename).write_text(json.dumps(value), encoding='utf-8')
    AssetService.ensure_structure(str(path))


def test_combined_save_rolls_back_every_document_on_replace_failure(tmp_path, monkeypatch):
    make_project(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in ('project.json', 'workflow.json', 'topology.json')}
    real_replace = os.replace

    def fail_topology(source, destination):
        if os.path.abspath(destination) == os.path.abspath(tmp_path / 'topology.json'):
            raise OSError('simulated topology replace failure')
        return real_replace(source, destination)

    monkeypatch.setattr(os, 'replace', fail_topology)
    with pytest.raises(OSError, match='simulated'):
        BlueprintService.save_blueprint(str(tmp_path), {
            'project_name': 'new name',
            'main_graph': {'graph_id': 'main', 'nodes': [], 'edges': [], 'blocks': []},
            'functions': [],
            'function_folders': [],
            'page_map': {'nodes': [], 'edges': [], 'blocks': []},
        })

    assert {name: (tmp_path / name).read_bytes() for name in before} == before


def test_next_load_recovers_an_interrupted_document_transaction(tmp_path):
    make_project(tmp_path)
    transaction = tmp_path / '.easycode' / 'recovery' / 'transactions' / 'txn_interrupted'
    before = transaction / 'before'
    before.mkdir(parents=True)
    shutil.copy2(tmp_path / 'workflow.json', before / 'workflow.json')
    (transaction / 'manifest.json').write_text(json.dumps({
        'schema_version': 1,
        'transaction_id': 'txn_interrupted',
        'filenames': ['workflow.json'],
    }), encoding='utf-8')
    (tmp_path / 'workflow.json').write_text('{broken', encoding='utf-8')

    loaded = BlueprintService.load_workflow(str(tmp_path))

    assert loaded['main_graph']['nodes'] == []
    assert loaded['functions'] == []
    assert not transaction.exists()
