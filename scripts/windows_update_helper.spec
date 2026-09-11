# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
spec_dir = os.path.dirname(os.path.abspath(SPEC))
root_dir = os.path.abspath(os.path.join(spec_dir, '..'))

a = Analysis(
    ['windows_update_helper.py'],
    pathex=[root_dir],
    binaries=[],
    datas=[],
    hiddenimports=['core.vnext.windows_update_helper_v6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'numpy', 'cv2', 'PIL'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EasycodeUpdateHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
