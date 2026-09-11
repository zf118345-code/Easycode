from core.vnext.control_defaults import parameter_ui_for_type


def test_color_defaults_to_shared_typed_editor_and_capture_action() -> None:
    metadata = parameter_ui_for_type('color')
    assert metadata == {
        'control': 'color',
        'actions': [{
            'id': 'pick-color',
            'capture_kind': 'color',
            'platforms': ['android_adb', 'android_local', 'windows'],
        }],
        'player_supported': True,
    }


def test_control_reference_defaults_to_cross_platform_control_capture() -> None:
    for value_type in ("control_ref", "control_ref<button>", "control_selector", "selector"):
        metadata = parameter_ui_for_type(value_type)
        assert metadata["control"] == "control-selector"
        assert metadata["actions"] == [{
            "id": "capture-control",
            "capture_kind": "control",
            "platforms": ["android_adb", "android_local", "windows"],
        }]


def test_file_and_directory_defaults_keep_all_player_hosts() -> None:
    read = parameter_ui_for_type("file_ref<read>")
    write = parameter_ui_for_type("file_ref<write>")
    directory = parameter_ui_for_type("directory_ref<list>")

    assert [item["id"] for item in read["actions"]] == ["choose-file-read"]
    assert [item["id"] for item in write["actions"]] == ["choose-file-save"]
    assert [item["id"] for item in directory["actions"]] == ["choose-directory"]
    assert all(
        set(action["platforms"]) == {"windows", "android_adb", "android_local"}
        for metadata in (read, write, directory)
        for action in metadata["actions"]
    )
