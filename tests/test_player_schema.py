import pytest

from core.player.schema import build_user_config, normalize_form_schema, validate_user_config


def test_player_schema_rejects_v2_project_documents():
    with pytest.raises(ValueError, match='版本不受支持'):
        normalize_form_schema({'schema_version': 2, 'groups': []})


def test_current_schema_rejects_old_control_types():
    schema = {
        'groups': [{'fields': [{'label': '窗口', 'target': '$env.window', 'ui_type': 'string', 'default': ''}]}]
    }

    with pytest.raises(ValueError, match='控件类型'):
        normalize_form_schema(schema)


def test_defaults_and_field_constraints_share_one_schema():
    schema = {
        'groups': [
            {
                'group_title': '参数',
                'fields': [
                    {'label': '次数', 'target': '$var.count', 'ui_type': 'number', 'default': 3, 'min': 1, 'max': 5},
                    {'label': '账号', 'target': '$ctx.account', 'ui_type': 'str', 'required': True, 'pattern': r'[a-z]+'},
                ],
            }
        ]
    }

    config = build_user_config(schema)
    assert config['vars']['count'] == 3
    errors = validate_user_config(schema, config)
    assert errors == [{'target': '$ctx.account', 'message': '账号 为必填项'}]

    config['ctx']['account'] = 'ABC'
    assert validate_user_config(schema, config) == [{'target': '$ctx.account', 'message': '账号 格式不正确'}]


def test_runtime_override_targets_use_isolated_override_slot():
    schema = {
        'groups': [{'fields': [
            {'label': '日志上限', 'target': '$settings.max_logs', 'ui_type': 'number', 'default': 800},
            {'label': '识别图片', 'target': '$node.node_a.params.image_source', 'ui_type': 'image_asset', 'default': 'asset://demo'},
        ]}]
    }

    config = build_user_config(schema)
    assert config['overrides']['$settings.max_logs'] == 800
    assert config['overrides']['$node.node_a.params.image_source'] == 'asset://demo'
    assert validate_user_config(schema, config) == []
