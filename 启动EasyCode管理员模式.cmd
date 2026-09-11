@echo off
setlocal
title EasyCode Administrator Launcher
echo Requesting administrator permission. Select Yes in the Windows prompt.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_easycode_admin.ps1"
if errorlevel 1 (
    echo.
    echo EasyCode administrator startup failed. Keep this window open.
    pause
)
endlocal
