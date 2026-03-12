# Secret Rotation Runbook (Facebook Sandbox Publish)

Use this runbook when tokens expire, permissions drift, or you suspect runtime credentials do not match the intended Facebook page.

## Scope

This runbook covers:
- `FB_PUBLISH_PROVIDER`
- `FB_PAGE_ID`
- `FB_PAGE_ACCESS_TOKEN`
- restart and verification sequence

## Key Rule

- `FB_PAGE_ACCESS_TOKEN` must be a PAGE token for the same page ID configured in `FB_PAGE_ID`.
- Query `me/accounts` with a fresh USER token, then write the selected PAGE token into `.env`.

## Preconditions

- Publishing provider should be `facebook_sandbox`.
- `.env` must stay out of source control.
- No active due-publish batch should be running.

## Rotation and Refresh Steps

1. Stop running API/worker processes and free port 5000.

```powershell
$targets = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -match 'website_server\.py' -or $_.CommandLine -match 'publish_worker\.py') }
if ($targets) {
  $targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
$conn = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}
```

2. Acquire a fresh USER token (Meta tooling) and list available pages.

```powershell
$userToken = 'PASTE_FRESH_USER_TOKEN_HERE'
$pages = (Invoke-RestMethod -Method Get -Uri 'https://graph.facebook.com/v20.0/me/accounts' -Body @{ access_token = $userToken }).data
$pages | Select-Object id,name
```

3. Select target page and extract page credentials.

```powershell
$page = @($pages)[0]
$pageId = [string]$page.id
$pageToken = [string]$page.access_token
```

4. Update `.env` with a matching page ID + page token pair.

```powershell
$envPath = Join-Path $PWD '.env'
$lines = Get-Content $envPath

function Set-Or-AddEnvLine([string[]]$src, [string]$key, [string]$value) {
  $pattern = '^\s*' + [Regex]::Escape($key) + '\s*='
  $updated = $false
  for ($i = 0; $i -lt $src.Count; $i++) {
    if ($src[$i] -match $pattern) {
      $src[$i] = "$key=$value"
      $updated = $true
      break
    }
  }
  if (-not $updated) { $src += "$key=$value" }
  return ,$src
}

$updated = [string[]]$lines
$updated = Set-Or-AddEnvLine $updated 'FB_PUBLISH_PROVIDER' 'facebook_sandbox'
$updated = Set-Or-AddEnvLine $updated 'FB_PAGE_ID' $pageId
$updated = Set-Or-AddEnvLine $updated 'FB_PAGE_ACCESS_TOKEN' $pageToken
$updated = Set-Or-AddEnvLine $updated 'FB_SANDBOX_ALLOW_COMMENT_FALLBACK' 'false'
Set-Content -Path $envPath -Value $updated -Encoding UTF8
```

5. Restart the app.

```powershell
& .\run_app.ps1 -SkipScrape -SkipBundle
```

6. Validate runtime secrets and preflight.

```powershell
Invoke-WebRequest 'http://localhost:5000/api/db/secrets/status' -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest 'http://localhost:5000/api/db/publish/preflight?deep=true' -UseBasicParsing | Select-Object -ExpandProperty Content
```

Success criteria:
- `ok=true` on secrets endpoint
- provider is `facebook_sandbox`
- deep preflight has zero blocking failures (`failed=0`)

7. Run strict end-to-end publish smoke test.

```powershell
& .\smoke_test_facebook_sandbox.ps1 -BaseUrl 'http://localhost:5000' -ScheduleDelaySeconds 15
```

Success criteria:
- target publish result is successful
- `commentFallbackApplied` is `False`

8. Resume automation once checks pass.

## Quick Triage (Before Full Rotation)

```powershell
Invoke-WebRequest 'http://localhost:5000/api/db/secrets/status' -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest 'http://localhost:5000/api/db/publish/preflight' -UseBasicParsing | Select-Object -ExpandProperty Content
```

If either endpoint indicates missing credentials, token mismatch, or permission failures, run the full rotation steps above.

## Incident Notes Template

Record each event with:
- Timestamp (UTC)
- Operator
- Trigger (routine, token expiry, incident)
- Token fingerprint before/after
- Preflight results (light and deep)
- Smoke test result
- Follow-up actions
