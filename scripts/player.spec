# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# 定位项目根目录与 core/params 路径
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, ".."))
params_dir = os.path.join(root_dir, "core", "params")

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
    'pyautogui'
]

hiddenimports += collect_submodules('core.node_executors')
hiddenimports += collect_submodules('core.conditions')
hiddenimports += collect_submodules('core.player')
hiddenimports += collect_submodules('core.security')
hiddenimports += collect_submodules('core.params')

# ⚡ 工业级修复：显式将 core/params 物理文件夹实体整体打包入 _MEIxxxx/core/params
datas = [
    (params_dir, 'core/params')
]

a = Analysis(
    ['../api.py'],
    pathex=[root_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'unittest', 'test', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EasycodePlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_excludes=[],
    runtime_tmpdir=None,
    console=True,  # 客户端运行可保留控制台以便查看关键日志（发布时可改为 False）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)