$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$logDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$timestamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
$logFile = Join-Path $logDir ("local_scrape_to_neon_{0}.log" -f $timestamp)

Write-Host "Running scheduled local scrape -> Neon. Log: $logFile"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'run_local_scrape_to_neon.ps1') *>&1 | Tee-Object -FilePath $logFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Scheduled run failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host 'Scheduled run completed successfully.' -ForegroundColor Green
