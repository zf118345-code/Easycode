from pathlib import Path

from core.params import ALL_PARAMS, PARAM_MODULES, load_all_params


def test_explicit_param_module_manifest_matches_source_modules():
    base = Path(__file__).resolve().parents[1] / 'core' / 'params' / 'base'
    discovered = {
        path.stem
        for path in base.glob('*.py')
        if path.stem != '__init__' and not path.name.startswith('_')
    }
    assert set(PARAM_MODULES) == discovered


def test_explicit_param_modules_load_without_physical_directory_scan():
    loaded = load_all_params()
    assert loaded is ALL_PARAMS
    assert loaded
    assert 'click' in loaded
