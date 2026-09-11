param(
    [string]$ProjectPath = '',
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSCommandPath
$statusPath = Join-Path $env:TEMP 'easycode-admin-restart-status.json'
if (-not $ProjectPath) {
    $defaultProjectName = -join @([char]0x8D85, [char]0x80FD, [char]0x4E16, [char]0x754C)
    $ProjectPath = Join-Path (Split-Path -Parent $projectRoot) $defaultProjectName
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    $arguments = @(
        '-NoProfile'
        '-ExecutionPolicy', 'Bypass'
        '-File', ('"{0}"' -f $PSCommandPath)
        '-ProjectPath', ('"{0}"' -f $ProjectPath)
    )
    if ($NonInteractive) { $arguments += '-NonInteractive' }
    try {
        # Do not wait on the elevated bootstrap process.  Windows may keep the
        # non-elevated launcher attached to redirected child handles even
        # after startup completed, which leaves a misleading "hung" window.
        # The elevated process writes the authoritative status file below.
        Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -WindowStyle Normal | Out-Null
        exit 0
    }
    catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        if (-not $NonInteractive) {
            Read-Host 'Press Enter to close this window'
        }
        exit 1
    }
}

trap {
    $message = $_.Exception.Message
    [ordered]@{
        ok = $false
        administrator = $true
        failed_at = (Get-Date).ToString('o')
        error = $message
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
    Write-Host ''
    Write-Host 'EasyCode administrator restart failed:' -ForegroundColor Red
    Write-Host $message -ForegroundColor Yellow
    Write-Host ''
    if (-not $NonInteractive) {
        Read-Host 'Press Enter to close this window'
    }
    exit 1
}

function Stop-EasyCodeListener {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($processId in @($connections | Select-Object -ExpandProperty OwningProcess -Unique)) {
        if (-not $processId) { continue }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
        if (-not $process) { continue }

        $commandLine = [string]$process.CommandLine
        $isBackend = $Port -eq 8000 -and $process.Name -eq 'python.exe' -and $commandLine -match '(^|[\\/\s])api\.py($|\s)'
        $isFrontend = $Port -in @(5173, 5174) -and $process.Name -eq 'node.exe' -and $commandLine -match '[\\/]Easycode[\\/]frontend[\\/]node_modules[\\/]'
        if (-not ($isBackend -or $isFrontend)) {
            throw "Port $Port belongs to a non-EasyCode process (PID $processId). Restart aborted."
        }
        # 一个进程可能同时留下多条监听记录，也可能在校验后自行退出。
        # 目标已经消失等价于停止成功，不能让整个管理员重启因此中断。
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-EasyCodeCaptureOverlay {
    $overlayPath = [System.IO.Path]::GetFullPath(
        (Join-Path $projectRoot 'build\native\CaptureOverlay\EasycodeCaptureOverlay.exe'))
    $processes = Get-CimInstance Win32_Process -Filter "Name='EasycodeCaptureOverlay.exe'" -ErrorAction SilentlyContinue
    foreach ($process in @($processes)) {
        if (-not $process.ExecutablePath) { continue }
        $candidate = [System.IO.Path]::GetFullPath([string]$process.ExecutablePath)
        if (-not [String]::Equals($candidate, $overlayPath, [StringComparison]::OrdinalIgnoreCase)) { continue }
        Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction SilentlyContinue
    }
}

foreach ($port in @(5173, 5174, 8000)) {
    Stop-EasyCodeListener -Port $port
}
Stop-EasyCodeCaptureOverlay
Start-Sleep -Milliseconds 800

$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$npmPath = (Get-Command 'npm.cmd' -ErrorAction Stop).Source

$backend = Start-Process -FilePath $pythonPath `
    -ArgumentList 'api.py' `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput (Join-Path $projectRoot 'backend.log') `
    -RedirectStandardError (Join-Path $projectRoot 'backend.err.log') `
    -WindowStyle Hidden `
    -PassThru

$frontend = Start-Process -FilePath $npmPath `
    -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173') `
    -WorkingDirectory $frontendRoot `
    -RedirectStandardOutput (Join-Path $projectRoot 'frontend.log') `
    -RedirectStandardError (Join-Path $projectRoot 'frontend.err.log') `
    -WindowStyle Hidden `
    -PassThru

$deadline = (Get-Date).AddSeconds(30)
do {
    Start-Sleep -Milliseconds 500
    $backendReady = [bool](Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    $frontendReady = [bool](Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)
} while ((-not $backendReady -or -not $frontendReady) -and (Get-Date) -lt $deadline)

if (-not $backendReady -or -not $frontendReady) {
    throw "EasyCode startup timed out: frontend=$frontendReady, backend=$backendReady. Check frontend.err.log and backend.err.log."
}

if ($ProjectPath -and (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
    $body = @{ path = $ProjectPath; initialize = $false; project_name = '' } | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/vnext/workspaces/open' -Method Post -ContentType 'application/json; charset=utf-8' -Body $body | Out-Null
}

[ordered]@{
    ok = $true
    administrator = $true
    restarted_at = (Get-Date).ToString('o')
    frontend_url = 'http://localhost:5173'
    frontend_process_id = $frontend.Id
    backend_process_id = $backend.Id
    project_path = $ProjectPath
} | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
