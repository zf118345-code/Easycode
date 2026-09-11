# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

root = Path(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), '..')))

a = Analysis(
    [str(root / 'installer.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=['win32com.client', 'win32com.shell', 'pythoncom', 'pywintypes'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['numpy', 'cv2', 'paddle', 'rapidocr_onnxruntime'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='EasycodeInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
)
