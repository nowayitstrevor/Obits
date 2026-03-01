param(
    [string]$TaskName = 'ObitScraper-RefreshAndPush',
    [string]$Time = '07:00'
)

$ErrorActionPreference = 'Stop'

if ($Time -notmatch '^(?:[01]\d|2[0-3]):[0-5]\d$') {
    Write-Host 'ERROR: -Time must be 24-hour format HH:mm (example: 07:00).' -ForegroundColor Red
    exit 1
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerPath = Join-Path $projectRoot 'scheduled_refresh_runner.ps1'

if (-not (Test-Path $runnerPath)) {
    Write-Host "ERROR: Runner script not found: $runnerPath" -ForegroundColor Red
    exit 1
}

Write-Host "Creating/updating scheduled task '$TaskName' at $Time daily..." -ForegroundColor Cyan

$taskTime = [datetime]::ParseExact($Time, 'HH:mm', $null)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`""
$trigger = New-ScheduledTaskTrigger -Daily -At $taskTime
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $existingTask) {
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings | Out-Null
}
else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Refresh obituary data JSON and push to GitHub.' | Out-Null
}

Write-Host "Scheduled task created: $TaskName" -ForegroundColor Green
Write-Host "Run now: schtasks /Run /TN `"$TaskName`"" -ForegroundColor Yellow
Write-Host "View details: schtasks /Query /TN `"$TaskName`" /V /FO LIST" -ForegroundColor Yellow
