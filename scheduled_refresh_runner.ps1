$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logsDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$timestamp = (Get-Date).ToString('yyyy-MM-dd_HH-mm-ss')
$logPath = Join-Path $logsDir ("scheduled_refresh_{0}.log" -f $timestamp)

Set-Location $projectRoot

Write-Output ("[{0}] Starting scheduled obituary data refresh..." -f (Get-Date).ToString('s')) | Tee-Object -FilePath $logPath -Append

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'refresh_and_push_data.ps1') 2>&1 |
        Tee-Object -FilePath $logPath -Append

    if ($LASTEXITCODE -ne 0) {
        throw "refresh_and_push_data.ps1 exited with code $LASTEXITCODE"
    }

    Write-Output ("[{0}] Scheduled refresh completed successfully." -f (Get-Date).ToString('s')) | Tee-Object -FilePath $logPath -Append
}
catch {
    Write-Output ("[{0}] Scheduled refresh failed: {1}" -f (Get-Date).ToString('s'), $_.Exception.Message) | Tee-Object -FilePath $logPath -Append
    exit 1
}
