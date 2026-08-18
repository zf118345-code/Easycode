# 重启 Easycode 后端：先杀占用 8000 端口的进程，再以隐藏窗口启动
# 日志输出到 backend.log / backend.err.log
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $conn | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}
Start-Process -FilePath 'D:\PycharmProjects\Easycode\.venv\Scripts\python.exe' -ArgumentList 'api.py' -WorkingDirectory 'D:\PycharmProjects\Easycode' -RedirectStandardOutput 'D:\PycharmProjects\Easycode\backend.log' -RedirectStandardError 'D:\PycharmProjects\Easycode\backend.err.log' -WindowStyle Hidden
Start-Sleep -Seconds 4
