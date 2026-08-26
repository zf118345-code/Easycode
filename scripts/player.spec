# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import importlib.util
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

# 定位项目根目录与 core/params 路径
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, ".."))
params_dir = os.path.join(root_dir, "core", "params")
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

# 收集加密和后台服务必需的子模块与数据
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
    'cv2',
    'numpy',
    'PIL',
    'win32gui',
    'win32con',
    'pyautogui',
    'av',
]

hiddenimports += collect_submodules('core.node_executors')
hiddenimports += collect_submodules('core.conditions')
hiddenimports += collect_submodules('core.player')
hiddenimports += collect_submodules('core.security')
hiddenimports += collect_submodules('core.params')
hiddenimports += collect_submodules('core.capabilities')
hiddenimports += ['core.services.capability_worker']

# ⚡ 工业级修复：显式将 core/params 物理文件夹实体整体打包入 _MEIxxxx/core/params
datas = [
    (params_dir, 'core/params'),
    (scrcpy_server_path, 'native/android'),
] + native_host_files

a = Analysis(
    ['../api.py'],
    pathex=[root_dir],
    binaries=uia_binaries + collect_dynamic_libs('av'),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # onnxruntime exposes optional transformer/dev integrations that pull an
    # entire scientific/ML toolchain into PyInstaller. Easycode OCR uses only
    # the core ONNX runtime, OpenCV, NumPy, Pillow and RapidOCR/ddddocr models.
    excludes=[
        'tkinter', 'matplotlib', 'unittest', 'test', 'pydoc',
        'pytest', '_pytest',
        'torch', 'torchvision', 'torchaudio',
        'tensorflow',
        'scipy', 'pandas', 'openpyxl', 'sqlalchemy',
        'networkx', 'fsspec', 'sympy',
        'onnxruntime.transformers',
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
