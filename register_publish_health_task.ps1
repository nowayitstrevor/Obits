param(
    [string]$TaskName = 'ObitScraper-PublishHealthCheck',
    [string]$BaseUrl = 'http://localhost:5000',
    [int]$IntervalMinutes = 30,
    [switch]$Deep
)

$ErrorActionPreference = 'Stop'

$IntervalMinutes = [Math]::Max(5, [Math]::Min(1440, [int]$IntervalMinutes))

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerPath = Join-Path $projectRoot 'run_publish_health_check.ps1'

if (-not (Test-Path $runnerPath)) {
    Write-Host "ERROR: Health check runner script not found: $runnerPath" -ForegroundColor Red
    exit 1
}

$deepArg = ''
if ($Deep) {
    $deepArg = ' -Deep'
}

Write-Host "Creating/updating scheduled task '$TaskName' to run every $IntervalMinutes minute(s)..." -ForegroundColor Cyan

$argument = "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`" -BaseUrl `"$BaseUrl`"$deepArg"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
$startAt = (Get-Date).Date.AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $startAt -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask) {
        Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -ErrorAction Stop | Out-Null
        Write-Host "Scheduled health task updated: $TaskName" -ForegroundColor Green
    }
    else {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Run obituary publish deep preflight and operational health checks.' -ErrorAction Stop | Out-Null
        Write-Host "Scheduled health task created: $TaskName" -ForegroundColor Green
    }

    Write-Host "Run now: schtasks /Run /TN `"$TaskName`"" -ForegroundColor Yellow
    Write-Host "View details: schtasks /Query /TN `"$TaskName`" /V /FO LIST" -ForegroundColor Yellow
    exit 0
}
catch {
    Write-Host "ERROR: Failed to create/update task '$TaskName'. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
