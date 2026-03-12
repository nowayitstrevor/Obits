param(
    [int]$PollSeconds = 300,
    [int]$BatchLimit = 25,
    [int]$DeepPreflightIntervalSeconds = 0
)

$ErrorActionPreference = 'Stop'

function Import-DotEnvIfPresent {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($rawLine in (Get-Content $Path -ErrorAction SilentlyContinue)) {
        $line = [string]$rawLine
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $trimmed = $line.Trim()
        if ($trimmed.StartsWith('#')) {
            continue
        }

        if ($trimmed.StartsWith('export ')) {
            $trimmed = $trimmed.Substring(7).Trim()
        }

        $equalsIndex = $trimmed.IndexOf('=')
        if ($equalsIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $equalsIndex).Trim()
        if ([string]::IsNullOrWhiteSpace($key)) {
            continue
        }

        $value = $trimmed.Substring($equalsIndex + 1).Trim()
        if ($value.Length -ge 2 -and (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            )) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        else {
            $commentIndex = $value.IndexOf(' #')
            if ($commentIndex -ge 0) {
                $value = $value.Substring(0, $commentIndex).Trim()
            }
        }

        $existing = [Environment]::GetEnvironmentVariable($key, 'Process')
        if ([string]::IsNullOrWhiteSpace($existing)) {
            [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
Import-DotEnvIfPresent -Path (Join-Path $projectRoot '.env')

$logsDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host 'ERROR: Python virtual environment not found at .venv\Scripts\python.exe' -ForegroundColor Red
    exit 1
}

$PollSeconds = [Math]::Max(30, [Math]::Min(3600, [int]$PollSeconds))
$BatchLimit = [Math]::Max(1, [Math]::Min(200, [int]$BatchLimit))
$DeepPreflightIntervalSeconds = [Math]::Max(0, [Math]::Min(86400, [int]$DeepPreflightIntervalSeconds))

$env:PUBLISH_WORKER_ENABLED = '1'
$env:PUBLISH_POLL_SECONDS = [string]$PollSeconds
$env:PUBLISH_WORKER_BATCH_LIMIT = [string]$BatchLimit
$env:PUBLISH_PREFLIGHT_DEEP_INTERVAL_SECONDS = [string]$DeepPreflightIntervalSeconds
if ([string]::IsNullOrWhiteSpace($env:FB_PUBLISH_PROVIDER)) {
    $env:FB_PUBLISH_PROVIDER = 'mock'
}

$timestamp = (Get-Date).ToString('yyyy-MM-dd_HH-mm-ss')
$logPath = Join-Path $logsDir ("publish_worker_{0}.log" -f $timestamp)

Write-Output ("[{0}] Starting publish worker (poll={1}s, batch={2}, provider={3}, deep_preflight_interval={4}s)" -f (Get-Date).ToString('s'), $PollSeconds, $BatchLimit, $env:FB_PUBLISH_PROVIDER, $DeepPreflightIntervalSeconds) | Tee-Object -FilePath $logPath -Append

& $pythonExe 'publish_worker.py' 2>&1 | Tee-Object -FilePath $logPath -Append
$exitCode = $LASTEXITCODE

Write-Output ("[{0}] Publish worker exited with code {1}" -f (Get-Date).ToString('s'), $exitCode) | Tee-Object -FilePath $logPath -Append
exit $exitCode
