param([switch]$ElevatedAttempt)

# 重启 EasyCode 后端。窗口管理必须与目标程序处于相同权限级别；
# 普通终端启动时先通过 UAC 将本脚本自身提升为管理员。
$isAdministrator = $false
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($null -ne $identity) {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        $isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
} catch {
    # 无交互宿主偶尔拿不到 WindowsIdentity；按非管理员处理并走 UAC，
    # 不能继续执行后半段后再静默失败。
    $isAdministrator = $false
}

if (-not $isAdministrator -and -not $ElevatedAttempt) {
    $elevatedArguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath),
        '-ElevatedAttempt'
    )
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList $elevatedArguments `
        -Verb RunAs `
        -WindowStyle Hidden
    return
}

# 日志输出到 backend.log / backend.err.log。
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $conn | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        # api.py may own native capture/worker children. Kill only the exact
        # listener tree so no detached EasyCode helper can retain the port.
        & taskkill.exe /PID $_ /T /F 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
        }
    }
    $deadline = (Get-Date).AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
        $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    } while ($conn -and (Get-Date) -lt $deadline)
    if ($conn) {
        throw 'The previous EasyCode backend did not release port 8000.'
    }
}
Start-Process -FilePath 'D:\PycharmProjects\Easycode\.venv\Scripts\python.exe' -ArgumentList 'api.py' -WorkingDirectory 'D:\PycharmProjects\Easycode' -RedirectStandardOutput 'D:\PycharmProjects\Easycode\backend.log' -RedirectStandardError 'D:\PycharmProjects\Easycode\backend.err.log' -WindowStyle Hidden
Start-Sleep -Seconds 4
