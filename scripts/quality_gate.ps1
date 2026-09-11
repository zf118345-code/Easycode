param(
    [switch]$Quick,
    [switch]$SkipFrontend,
    [switch]$SkipBackend
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $projectRoot '.venv312\Scripts\python.exe'
$ruffExe = Join-Path $projectRoot '.venv312\Scripts\ruff.exe'
$banditExe = Join-Path $projectRoot '.venv312\Scripts\bandit.exe'

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    Write-Host "`n==> $Label" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit code: $LASTEXITCODE)"
    }
}

Invoke-Checked 'Patch whitespace check' { git -C $projectRoot diff --check }

if (-not $SkipFrontend) {
    Invoke-Checked 'Frontend lint' { npm --prefix $frontendRoot run lint:check }
    Invoke-Checked 'Frontend typecheck' { npm --prefix $frontendRoot run typecheck }
    Invoke-Checked 'Frontend tests' { npm --prefix $frontendRoot test -- --run }
    if (-not $Quick) {
        Invoke-Checked 'Frontend production build' { npm --prefix $frontendRoot run build }
    }
}

if (-not $SkipBackend) {
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        throw "Project Python environment was not found: $pythonExe"
    }
    Invoke-Checked 'Backend correctness lint' {
        & $ruffExe check (Join-Path $projectRoot 'api') (Join-Path $projectRoot 'core') --select E9,F,B --ignore B008
    }
    Invoke-Checked 'vNext API contract drift' {
        & $pythonExe (Join-Path $projectRoot 'scripts\generate_vnext_contracts.py') --check
    }
    if (-not $Quick) {
        Invoke-Checked 'Backend security scan' {
            & $banditExe -q -r (Join-Path $projectRoot 'api') (Join-Path $projectRoot 'core') -ll
        }
    }
    Invoke-Checked 'Backend tests' {
        & $pythonExe -m pytest (Join-Path $projectRoot 'tests') -q -p no:cacheprovider
    }
}

Write-Host "`nEasyCode quality gate passed." -ForegroundColor Green
