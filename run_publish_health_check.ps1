param(
    [string]$BaseUrl = 'http://localhost:5000',
    [switch]$Deep
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$logsDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$timestamp = (Get-Date).ToString('yyyy-MM-dd_HH-mm-ss')
$logPath = Join-Path $logsDir ("publish_health_check_{0}.log" -f $timestamp)

function Invoke-JsonApi {
    param(
        [string]$Uri
    )

    try {
        $resp = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 30
        $status = [int]$resp.StatusCode
        $body = $null
        if (-not [string]::IsNullOrWhiteSpace($resp.Content)) {
            $body = $resp.Content | ConvertFrom-Json
        }
        return @{ status = $status; body = $body; raw = $resp.Content }
    }
    catch {
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode.value__
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $raw = $reader.ReadToEnd()
            $reader.Close()
            $body = $null
            if (-not [string]::IsNullOrWhiteSpace($raw)) {
                try { $body = $raw | ConvertFrom-Json } catch { $body = $null }
            }
            return @{ status = $status; body = $body; raw = $raw }
        }
        throw
    }
}

$deepFlag = 'false'
if ($Deep) {
    $deepFlag = 'true'
}

$preflightUri = "{0}/api/db/publish/preflight?deep={1}&initiatedBy=scheduled_health_check" -f $BaseUrl.TrimEnd('/'), $deepFlag
$healthUri = "{0}/api/db/ops/health" -f $BaseUrl.TrimEnd('/')

Write-Output ("[{0}] Running publish preflight check (deep={1})" -f (Get-Date).ToString('s'), $Deep) | Tee-Object -FilePath $logPath -Append
$preflight = Invoke-JsonApi -Uri $preflightUri

if ($preflight.status -ge 400) {
    Write-Output ("[{0}] ERROR preflight HTTP {1}" -f (Get-Date).ToString('s'), $preflight.status) | Tee-Object -FilePath $logPath -Append
    if ($preflight.raw) {
        Write-Output $preflight.raw | Tee-Object -FilePath $logPath -Append
    }
    exit 2
}

if ($null -eq $preflight.body -or -not [bool]$preflight.body.ok) {
    Write-Output ("[{0}] ERROR preflight failed" -f (Get-Date).ToString('s')) | Tee-Object -FilePath $logPath -Append
    if ($preflight.raw) {
        Write-Output $preflight.raw | Tee-Object -FilePath $logPath -Append
    }
    exit 3
}

$summary = $preflight.body.summary
$passed = 0
$failed = 0
$warnings = 0
if ($summary) {
    $passed = [int]$summary.passed
    $failed = [int]$summary.failed
    $warnings = [int]$summary.warnings
}
Write-Output ("[{0}] Preflight passed={1} failed={2} warnings={3}" -f (Get-Date).ToString('s'), $passed, $failed, $warnings) | Tee-Object -FilePath $logPath -Append

Write-Output ("[{0}] Running operational health check" -f (Get-Date).ToString('s')) | Tee-Object -FilePath $logPath -Append
$health = Invoke-JsonApi -Uri $healthUri
if ($health.status -ge 400) {
    Write-Output ("[{0}] ERROR ops health HTTP {1}" -f (Get-Date).ToString('s'), $health.status) | Tee-Object -FilePath $logPath -Append
    if ($health.raw) {
        Write-Output $health.raw | Tee-Object -FilePath $logPath -Append
    }
    exit 4
}

if ($null -eq $health.body) {
    Write-Output ("[{0}] ERROR ops health returned empty body" -f (Get-Date).ToString('s')) | Tee-Object -FilePath $logPath -Append
    exit 5
}

$alertCount = 0
$errorCount = 0
if ($health.body.alerts) {
    foreach ($alert in @($health.body.alerts)) {
        $alertCount += 1
        if ([string]$alert.severity -eq 'error') {
            $errorCount += 1
        }
    }
}

Write-Output ("[{0}] Ops health ok={1} alerts={2} errors={3}" -f (Get-Date).ToString('s'), [bool]$health.body.ok, $alertCount, $errorCount) | Tee-Object -FilePath $logPath -Append
if ($health.raw) {
    Write-Output $health.raw | Tee-Object -FilePath $logPath -Append
}

if (-not [bool]$health.body.ok -or $errorCount -gt 0) {
    exit 6
}

exit 0
