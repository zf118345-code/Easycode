from __future__ import annotations

import threading
import time
from pathlib import Path

from core.vnext.workspace import VNextWorkspaceManager


def test_publish_holds_project_gate_until_artifact_finishes(monkeypatch, tmp_path: Path):
    manager = VNextWorkspaceManager()
    workspace = manager.open(str(tmp_path / 'publish-gate'), initialize=True)['workspace']
    target_revision = manager.target_configuration(
        workspace['workspace_id'], workspace['generation'],
    )['revision']
    entered = threading.Event()
    release = threading.Event()
    mutation_done = threading.Event()
    failures: list[BaseException] = []

    def delayed_build(workspace_id: str, generation: int):
        assert workspace_id == workspace['workspace_id']
        assert generation == workspace['generation']
        entered.set()
        assert release.wait(2)
        return {'created': True, 'path': 'test.ecplayer'}

    monkeypatch.setattr(manager._publishing, '_build_locked', delayed_build)

    def publish():
        try:
            manager.publish_player(workspace['workspace_id'], workspace['generation'])
        except BaseException as exc:  # pragma: no cover - assertion reports worker failure
            failures.append(exc)

    def mutate():
        try:
            manager.save_targets(
                workspace['workspace_id'], workspace['generation'], [], None,
                expected_revision=target_revision,
            )
            mutation_done.set()
        except BaseException as exc:  # pragma: no cover - assertion reports worker failure
            failures.append(exc)

    publishing = threading.Thread(target=publish)
    publishing.start()
    assert entered.wait(1)
    mutation = threading.Thread(target=mutate)
    mutation.start()
    time.sleep(0.08)
    assert mutation_done.is_set() is False

    release.set()
    publishing.join(timeout=2)
    mutation.join(timeout=2)

    assert failures == []
    assert publishing.is_alive() is False
    assert mutation.is_alive() is False
    assert mutation_done.is_set() is True


def test_project_transaction_serializes_capture_style_resource_writes(tmp_path: Path):
    manager = VNextWorkspaceManager()
    workspace = manager.open(str(tmp_path / 'capture-gate'), initialize=True)['workspace']
    mutation_done = threading.Event()

    def mutate():
        manager.create_asset_folder(
            workspace['workspace_id'], workspace['generation'], 'image', 'after-publish',
        )
        mutation_done.set()

    with manager.project_transaction(workspace['workspace_id'], workspace['generation'], writable=True):
        thread = threading.Thread(target=mutate)
        thread.start()
        time.sleep(0.05)
        assert mutation_done.is_set() is False
    thread.join(timeout=2)

    assert mutation_done.is_set() is True
