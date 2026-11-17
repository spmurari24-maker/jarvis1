$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonCommand = $null
$pythonPrefix = @()

$pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyLauncher) {
    try {
        & $pyLauncher.Source -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonCommand = $pyLauncher.Source
            $pythonPrefix = @("-3.11")
        }
    } catch { }
}

if (-not $pythonCommand) {
    foreach ($candidate in @((Join-Path $projectRoot ".tools\python311\python.exe"),
                             "C:\Python311\python.exe", "C:\Program Files\Python311\python.exe",
                             "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
        if (Test-Path -LiteralPath $candidate) {
            try {
                $version = & $candidate --version 2>$null
                if ($LASTEXITCODE -eq 0 -and $version -match "^Python 3\.11\.") {
                    $pythonCommand = $candidate
                    break
                }
            } catch { }
        }
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    if (-not $pythonCommand) {
        Write-Error "Python 3.11 is required. Install Python 3.11 from https://www.python.org/downloads/ and run start_jarvis.ps1 again."
        exit 1
    }
    & $pythonCommand @pythonPrefix -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create JARVIS's Python environment." }
    & $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Could not install JARVIS requirements. Check your internet connection and try again." }
} else {
    & $venvPython -c "import fastapi, uvicorn, yaml"
    if ($LASTEXITCODE -ne 0) { throw "JARVIS dependencies are missing. Remove .venv and run this file again to reinstall them." }
}

$url = "http://127.0.0.1:8765/"
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 2
    if ($health.status -eq "ready") {
        Write-Host "JARVIS is already running at $url"
        exit 0
    }
} catch { }

$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) { throw "Port 8765 is already in use by another program. Close that program and run this file again." }

$logDirectory = Join-Path $projectRoot "storage\logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$stdout = Join-Path $logDirectory "server.log"
$stderr = Join-Path $logDirectory "server-error.log"
$server = Start-Process -FilePath $venvPython `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8765") `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr -PassThru

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 2
        if ($health.status -eq "ready") {
            Write-Host "JARVIS is running at $url"
            Write-Host "Refresh the open browser tab if it still shows a connection error."
            exit 0
        }
    } catch { }
    if ($server.HasExited) { break }
}

$errorTail = if (Test-Path -LiteralPath $stderr) { (Get-Content -LiteralPath $stderr -Tail 12) -join [Environment]::NewLine } else { "No startup log was created." }
throw "JARVIS did not start successfully. Check storage\logs\server-error.log. $errorTail"
