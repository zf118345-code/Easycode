import importlib

ALL_PARAMS = {}

# Keep registration explicit so frozen Player builds can import the modules
# from PyInstaller's bytecode archive without shipping EasyCode ``.py`` files
# as loose data.  The regression test requires this list to match base/*.py.
PARAM_MODULES = (
    'branch',
    'call_function',
    'click',
    'control',
    'defaults',
    'drag',
    'function_contract',
    'image_recognition',
    'log',
    'logic_check',
    'ocr_recognition',
    'script_call',
    'scroll',
    'set_window',
    'smart_jump',
    'text_input',
    'topology',
    'variable_op',
    'wait',
)


def load_all_params():
    global ALL_PARAMS
    ALL_PARAMS.clear()
    for module_name in PARAM_MODULES:
        package = f'core.params.base.{module_name}'
        try:
            module = importlib.import_module(package)
            if hasattr(module, 'PARAM_DEFINITIONS'):
                ALL_PARAMS.update(module.PARAM_DEFINITIONS)
        except Exception as exc:
            print(f'加载参数模块 {package} 失败: {exc}')

    return ALL_PARAMS


load_all_params()
