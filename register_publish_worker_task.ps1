param(
    [string]$TaskName = 'ObitScraper-PublishWorker',
    [int]$PollSeconds = 300,
    [int]$BatchLimit = 25,
    [int]$DeepPreflightIntervalSeconds = 0
)

$ErrorActionPreference = 'Stop'

$PollSeconds = [Math]::Max(30, [Math]::Min(3600, [int]$PollSeconds))
$BatchLimit = [Math]::Max(1, [Math]::Min(200, [int]$BatchLimit))
$DeepPreflightIntervalSeconds = [Math]::Max(0, [Math]::Min(86400, [int]$DeepPreflightIntervalSeconds))

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerPath = Join-Path $projectRoot 'run_publish_worker.ps1'

if (-not (Test-Path $runnerPath)) {
    Write-Host "ERROR: Worker runner script not found: $runnerPath" -ForegroundColor Red
    exit 1
}

Write-Host "Creating/updating scheduled task '$TaskName' to start on boot..." -ForegroundColor Cyan

$argument = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`" -PollSeconds $PollSeconds -BatchLimit $BatchLimit -DeepPreflightIntervalSeconds $DeepPreflightIntervalSeconds"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask) {
        Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -ErrorAction Stop | Out-Null
        Write-Host "Scheduled worker task updated: $TaskName" -ForegroundColor Green
    }
    else {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Run continuous obituary publish worker loop.' -ErrorAction Stop | Out-Null
        Write-Host "Scheduled worker task created: $TaskName" -ForegroundColor Green
    }

    $verifiedTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($null -eq $verifiedTask) {
        throw "Task verification failed after registration."
    }

    Write-Host "Run now: schtasks /Run /TN `"$TaskName`"" -ForegroundColor Yellow
    Write-Host "View details: schtasks /Query /TN `"$TaskName`" /V /FO LIST" -ForegroundColor Yellow
    exit 0
}
catch {
    Write-Host "ERROR: Failed to create/update task '$TaskName'. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
