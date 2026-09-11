from __future__ import annotations

import importlib.util

import pytest

from core.services.recording_replay_service import RecordingReplayService
from core.vnext.target_runtime import TargetDriver
from core.vnext.workspace import VNextWorkspaceManager

RETIRED_MODULES = (
    "core.vnext.compiler",
    "core.vnext.editing",
    "core.vnext.function_service",
    "core.vnext.language",
    "core.vnext.language_service",
    "core.vnext.navigation",
    "core.vnext.semantic_edits",
    "core.vnext.source_service",
    "core.vnext.topology",
)


@pytest.mark.parametrize("module_name", RETIRED_MODULES)
def test_format5_source_and_page_modules_are_not_importable(module_name: str):
    assert importlib.util.find_spec(module_name) is None


def test_workspace_manager_does_not_expose_format5_source_services():
    manager = VNextWorkspaceManager()

    for attribute in (
        "sources",
        "functions",
        "list_sources",
        "project_functions",
        "read_source",
        "save_source",
        "create_source",
        "link_project",
    ):
        assert not hasattr(manager, attribute), attribute


def test_current_target_driver_has_no_page_navigation_runtime_surface():
    assert not hasattr(TargetDriver, "configure_topology")
    assert not hasattr(TargetDriver, "execute_page")
    assert not hasattr(RecordingReplayService, "analyze_frame")
    assert not hasattr(RecordingReplayService, "analyze_session")


def test_target_driver_does_not_keep_format5_display_name_opcodes() -> None:
    retired = {
        'vision.wait_image',
        'vision.find_image',
        'vision.image_exists',
        'vision.wait_absent',
        'vision.click_once',
        'vision.click_until_absent',
        'text.contains',
        'text.wait',
        'input.tap',
        'input.drag_path',
    }

    assert not {opcode for opcode in retired if TargetDriver.supports(opcode)}
