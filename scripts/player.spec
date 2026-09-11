# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import importlib.util
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

# 定位项目根目录
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, ".."))
scrcpy_server_path = os.path.join(root_dir, 'native', 'android', 'scrcpy-server-v4.1')
if not os.path.isfile(scrcpy_server_path):
    raise RuntimeError(f'Android高速采帧依赖缺失: {scrcpy_server_path}')
native_host_dir = os.path.join(root_dir, "build", "native", "CaptureOverlay")
native_host_files = []
for native_name in (
    'EasycodeCaptureOverlay.exe',
    'Microsoft.Web.WebView2.Core.dll',
    'Microsoft.Web.WebView2.WinForms.dll',
    'WebView2Loader.dll',
):
    native_path = os.path.join(native_host_dir, native_name)
    if not os.path.isfile(native_path):
        raise RuntimeError(f'原生桌面宿主依赖缺失: {native_path}')
    native_host_files.append((native_path, 'native/CaptureOverlay'))

uia_spec = importlib.util.find_spec('uiautomation')
uia_dir = os.path.dirname(uia_spec.origin) if uia_spec and uia_spec.origin else ''
uia_binaries = []
for dll_name in ('UIAutomationClient_VC140_X64.dll', 'UIAutomationClient_VC140_X86.dll'):
    dll_path = os.path.join(uia_dir, 'bin', dll_name)
    if not os.path.isfile(dll_path):
        raise RuntimeError(f'UIA 原生依赖缺失: {dll_path}')
    uia_binaries.append((dll_path, 'uiautomation/bin'))

# Standalone Player manifest.  Keep this explicit: whole-package collection of
# legacy executors/conditions/Player/params or core.vnext would silently turn
# the runtime back into the IDE package.
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'cryptography',
    'tzdata',
    'cv2',
    'numpy',
    'PIL',
    'win32gui',
    'win32con',
    'win32api',
    'win32process',
    'win32job',
    'win32com.client',
    'pyautogui',
    'av',
    # Worker/capture/runtime closures selected dynamically at run time.
    'core.services.capability_worker',
    'core.services.player_capture_session',
    'core.services.capture_mode',
    'core.services.native_capture_overlay',
    'core.services.native_desktop_shell',
    'core.services.uia_service',
    'core.services.background_input',
    'core.services.android_stream',
    'core.vision.ocr_engine',
    'core.vnext.execution_worker',
    'core.vnext.extension_worker_v6',
    'core.vnext.extension_runtime_v6',
    'core.vnext.target_runtime',
    'core.vnext.file_runtime_v6',
    'core.vnext.message_runtime_v6',
    'core.vnext.network_runtime_v6',
    'core.vnext.platform_runtime_v6',
    'core.vnext.standard_functions_v6',
    'core.vnext.schedule_v6',
    'core.vnext.schedule_hub_v6',
    'core.vnext.schedule_registry_v6',
    'core.vnext.player_console_v1',
    'api.routers.vnext_player_console_router',
    'core.vnext.lan_control_v6',
    'core.vnext.lan_schedule_v6',
    'core.vnext.update_client_v6',
    'core.vnext.windows_update_helper_v6',
]

hiddenimports += collect_submodules('rapidocr_onnxruntime')
hiddenimports += collect_submodules(
    'ddddocr',
    filter=lambda name: not name.startswith(('ddddocr.api', 'ddddocr.__main__')),
)
hiddenimports += collect_submodules('tzdata')

ocr_datas = (
    collect_data_files('rapidocr_onnxruntime')
    + collect_data_files('ddddocr')
)
ocr_binaries = collect_dynamic_libs('onnxruntime')
timezone_datas = collect_data_files('tzdata')

datas = [
    (scrcpy_server_path, 'native/android'),
] + native_host_files + ocr_datas + timezone_datas

a = Analysis(
    ['../player.py'],
    pathex=[root_dir],
    binaries=uia_binaries + collect_dynamic_libs('av') + ocr_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # onnxruntime exposes optional transformer/dev integrations that pull an
    # entire scientific/ML toolchain into PyInstaller. Easycode OCR uses only
    # the core ONNX runtime, OpenCV, NumPy, Pillow and RapidOCR/ddddocr models.
    excludes=[
        # tkinter is the frozen Windows Player's native file/directory picker.
        # Android uses SAF and does not consume this runtime.
        'matplotlib', 'unittest', 'test', 'pydoc',
        'pytest', '_pytest',
        'torch', 'torchvision', 'torchaudio',
        'tensorflow',
        'scipy', 'pandas', 'openpyxl', 'sqlalchemy',
        'networkx', 'fsspec', 'sympy',
        'onnxruntime.transformers',
        # Authoring/IDE modules are forbidden even if a future dependency
        # accidentally starts importing them.
        'api.app',
        'api.contracts.vnext',
        'api.routers.vnext_router',
        'api.routers.vnext_update_router',
        'api.routers.build_router',
        'api.routers.project_workspace_router',
        'api.routers.workspace_router',
        'api.routers.execution_router',
        'api.routers.vision_router',
        'api.routers.capture_router',
        'api.routers.ui_control_router',
        'core.vnext.workspace',
        'core.vnext.publish',
        'core.vnext.publish_service',
        'core.vnext.program_compiler',
        'core.vnext.program_repository',
        'core.vnext.program_service_v6',
        'core.vnext.extensions',
        'core.builder',
        'core.player',
        'core.conditions',
        'core.params',
        'core.services.project_workspace_service',
        'core.services.capture_session_service',
        'core.services.execution_service',
        'core.services.frame_recording_service',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='EasycodePlayer',
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_excludes=[],
    runtime_tmpdir=None,
    console=False,
    # Windows automation may target elevated desktop applications. Request
    # elevation once when Player starts so individual workflow runs never try
    # to cross the UIPI boundary halfway through execution.
    uac_admin=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EasycodePlayer',
)
