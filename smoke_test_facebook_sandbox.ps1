param(
    [string]$BaseUrl = 'http://localhost:5000',
    [string]$ObituaryId = '',
    [int]$ScheduleDelaySeconds = 30,
    [int]$RunLimit = 10,
    [switch]$SkipRunDue,
    [switch]$SkipPreflight,
    [switch]$AllowNonSandboxProvider,
    [switch]$AllowCommentFallback
)

$ErrorActionPreference = 'Stop'

$ScheduleDelaySeconds = [Math]::Max(15, [Math]::Min(600, [int]$ScheduleDelaySeconds))
$RunLimit = [Math]::Max(1, [Math]::Min(200, [int]$RunLimit))
$BaseUrl = ($BaseUrl.Trim()).TrimEnd('/')

function Invoke-ApiJson {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null
    )

    $params = @{
        Method = $Method
        Uri = $Uri
        UseBasicParsing = $true
        TimeoutSec = 20
    }

    if ($null -ne $Body) {
        $params['ContentType'] = 'application/json'
        $params['Body'] = ($Body | ConvertTo-Json -Depth 8)
    }

    try {
        $response = Invoke-WebRequest @params
        $rawText = [string]$response.Content
        $parsed = $null
        if (-not [string]::IsNullOrWhiteSpace($rawText)) {
            try {
                $parsed = $rawText | ConvertFrom-Json
            }
            catch {
                $parsed = $null
            }
        }

        return @{
            ok = $true
            statusCode = [int]$response.StatusCode
            body = $parsed
            raw = $rawText
            error = $null
        }
    }
    catch {
        $statusCode = -1
        $rawText = ''
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode.value__
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $rawText = $reader.ReadToEnd()
            $reader.Close()
        }

        $parsed = $null
        if (-not [string]::IsNullOrWhiteSpace($rawText)) {
            try {
                $parsed = $rawText | ConvertFrom-Json
            }
            catch {
                $parsed = $null
            }
        }

        return @{
            ok = $false
            statusCode = $statusCode
            body = $parsed
            raw = $rawText
            error = $_.Exception.Message
        }
    }
}

function Require-ApiSuccess {
    param(
        [hashtable]$Result,
        [string]$Step
    )

    if (-not $Result.ok) {
        throw "$Step failed (HTTP $($Result.statusCode)): $($Result.error)`n$($Result.raw)"
    }

    if ($null -ne $Result.body -and $Result.body.PSObject.Properties.Name -contains 'ok') {
        if (-not [bool]$Result.body.ok) {
            $apiError = ''
            if ($Result.body.PSObject.Properties.Name -contains 'error') {
                $apiError = [string]$Result.body.error
            }
            throw "$Step returned ok=false: $apiError"
        }
    }
}

Write-Host "Checking publish provider and API health..." -ForegroundColor Cyan
$publishStatus = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/publish/status"
Require-ApiSuccess -Result $publishStatus -Step 'Get publish status'

$provider = [string]$publishStatus.body.status.provider
if ([string]::IsNullOrWhiteSpace($provider)) {
    $provider = 'unknown'
}
Write-Host "Active provider: $provider" -ForegroundColor Yellow

if ((-not $AllowNonSandboxProvider) -and $provider -ne 'facebook_sandbox') {
    throw "Provider is '$provider'. Set FB_PUBLISH_PROVIDER=facebook_sandbox in the server process before running this script, or re-run with -AllowNonSandboxProvider."
}

$fallbackAllowed = $false
if ($publishStatus.body.status.PSObject.Properties.Name -contains 'commentFallbackAllowed') {
    $fallbackAllowed = [bool]$publishStatus.body.status.commentFallbackAllowed
}
if ((-not $AllowCommentFallback) -and $fallbackAllowed) {
    throw "FB_SANDBOX_ALLOW_COMMENT_FALLBACK is enabled. Strict two-step validation requires fallback disabled. Set FB_SANDBOX_ALLOW_COMMENT_FALLBACK=false and retry, or re-run with -AllowCommentFallback."
}

if ($SkipPreflight) {
    Write-Host 'Skipping publish preflight because -SkipPreflight was provided.' -ForegroundColor Yellow
}
else {
    Write-Host 'Running publish preflight checks...' -ForegroundColor Cyan
    $preflight = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/publish/preflight?deep=true"
    if (-not $preflight.ok) {
        throw "Publish preflight endpoint failed (HTTP $($preflight.statusCode)): $($preflight.error)`n$($preflight.raw)"
    }

    if ($null -eq $preflight.body) {
        throw 'Publish preflight returned an empty response body.'
    }

    $passedChecks = 0
    $failedChecks = 0
    $warningChecks = 0
    if ($preflight.body.summary) {
        $passedChecks = [int]($preflight.body.summary.passed)
        $failedChecks = [int]($preflight.body.summary.failed)
        $warningChecks = [int]($preflight.body.summary.warnings)
    }
    Write-Host ("Preflight summary: passed=$passedChecks failed=$failedChecks warnings=$warningChecks") -ForegroundColor Yellow

    if (-not [bool]$preflight.body.ok) {
        $blockingDetails = @()
        if ($preflight.body.checks) {
            foreach ($check in @($preflight.body.checks)) {
                if ([bool]$check.ok) {
                    continue
                }
                if ([string]$check.severity -eq 'warning') {
                    continue
                }
                $name = [string]$check.name
                $detail = [string]$check.detail
                $blockingDetails += ("$($name): $detail")
            }
        }

        if ($blockingDetails.Count -gt 0) {
            throw ("Publish preflight failed: " + ($blockingDetails -join '; '))
        }

        $apiError = ''
        if ($preflight.body.PSObject.Properties.Name -contains 'error') {
            $apiError = [string]$preflight.body.error
        }
        throw ("Publish preflight failed: " + $apiError)
    }
}

$targetId = [string]$ObituaryId
if ([string]::IsNullOrWhiteSpace($targetId)) {
    Write-Host "Selecting a target obituary..." -ForegroundColor Cyan
    $stagedFeed = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/queue/staged?limit=1"
    Require-ApiSuccess -Result $stagedFeed -Step 'Load staged queue'

    if ($stagedFeed.body.obituaries -and $stagedFeed.body.obituaries.Count -gt 0) {
        $targetId = [string]$stagedFeed.body.obituaries[0].id
        Write-Host "Using staged obituary: $targetId" -ForegroundColor Green
    }
    else {
        $newFeed = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/queue/new?limit=1"
        Require-ApiSuccess -Result $newFeed -Step 'Load new queue'

        if (-not $newFeed.body.obituaries -or $newFeed.body.obituaries.Count -lt 1) {
            throw 'No staged or new obituary records available for smoke test.'
        }

        $targetId = [string]$newFeed.body.obituaries[0].id
        Write-Host "No staged records found. Moving new obituary to staged: $targetId" -ForegroundColor Yellow
        $toStaged = Invoke-ApiJson -Method 'POST' -Uri "$BaseUrl/api/db/queue/$targetId/transition" -Body @{
            toStatus = 'staged'
            initiatedBy = 'facebook_sandbox_smoke_test'
        }
        Require-ApiSuccess -Result $toStaged -Step 'Transition new to staged'
    }
}

if ([string]::IsNullOrWhiteSpace($targetId)) {
    throw 'Unable to determine target obituary ID for smoke test.'
}

$scheduledFor = (Get-Date).ToUniversalTime().AddSeconds($ScheduleDelaySeconds).ToString('o')
Write-Host "Scheduling $targetId for $scheduledFor ..." -ForegroundColor Cyan
$toScheduled = Invoke-ApiJson -Method 'POST' -Uri "$BaseUrl/api/db/queue/$targetId/transition" -Body @{
    toStatus = 'scheduled'
    scheduledFor = $scheduledFor
    initiatedBy = 'facebook_sandbox_smoke_test'
}
Require-ApiSuccess -Result $toScheduled -Step 'Transition staged to scheduled'

if ($SkipRunDue) {
    Write-Host 'Skipping run-due trigger because -SkipRunDue was provided.' -ForegroundColor Yellow
    Write-Host "Target obituary is now scheduled: $targetId" -ForegroundColor Green
    exit 0
}

$waitSeconds = $ScheduleDelaySeconds + 5
Write-Host "Waiting $waitSeconds seconds for due time..." -ForegroundColor Cyan
Start-Sleep -Seconds $waitSeconds

Write-Host 'Running due publish endpoint...' -ForegroundColor Cyan
$runDue = Invoke-ApiJson -Method 'POST' -Uri "$BaseUrl/api/db/publish/run-due" -Body @{
    limit = $RunLimit
    initiatedBy = 'facebook_sandbox_smoke_test'
}
Require-ApiSuccess -Result $runDue -Step 'Run due publish'

$results = @()
if ($runDue.body.results) {
    $results = @($runDue.body.results)
}

$targetResult = $results | Where-Object { [string]$_.obituaryId -eq $targetId } | Select-Object -First 1
if ($null -eq $targetResult) {
    Write-Host "WARNING: No publish result found for target obituary $targetId in this run." -ForegroundColor Yellow
}
else {
    Write-Host "Publish result for $targetId" -ForegroundColor Green
    Write-Host ("  ok: " + [bool]$targetResult.ok)
    if ($targetResult.publish) {
        Write-Host ("  provider: " + [string]$targetResult.publish.provider)
        Write-Host ("  facebookPostId: " + [string]$targetResult.publish.facebookPostId)
        Write-Host ("  commentUrl: " + [string]$targetResult.publish.commentUrl)

        $providerResponse = $targetResult.publish.providerResponse
        if ($providerResponse) {
            $commentFallbackApplied = [bool]$providerResponse.comment_fallback_applied
            Write-Host ("  commentFallbackApplied: " + $commentFallbackApplied)
            if ((-not $AllowCommentFallback) -and $commentFallbackApplied) {
                throw "Strict two-step validation failed: comment fallback was applied for obituary $targetId. Ensure token includes pages_manage_engagement and fallback is disabled."
            }
        }
    }
}

$counts = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/queue/counts"
Require-ApiSuccess -Result $counts -Step 'Load queue counts'

$statusAfter = Invoke-ApiJson -Method 'GET' -Uri "$BaseUrl/api/db/publish/status"
Require-ApiSuccess -Result $statusAfter -Step 'Load publish status after run'

Write-Host 'Queue counts after smoke test:' -ForegroundColor Cyan
Write-Host ($counts.raw)

Write-Host 'Publish status after smoke test:' -ForegroundColor Cyan
Write-Host ($statusAfter.raw)

Write-Host 'Facebook sandbox smoke test completed.' -ForegroundColor Green
