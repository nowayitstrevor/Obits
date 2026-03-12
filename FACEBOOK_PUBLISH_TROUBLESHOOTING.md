# Facebook Publish Troubleshooting and Token Refresh

This document is the exact flow for when Facebook publish starts failing because credentials drifted or token refresh is needed.

## Most Common Failure Signals

- `code 190` (invalid/expired session token)
- Deep preflight failures (`deepPostCreate`, `deepCommentCreate`, or page membership checks)
- `/api/db/secrets/status` fingerprint does not match expected token lifecycle

## Important Token Rule

- `FB_PAGE_ACCESS_TOKEN` in `.env` must be a PAGE token for the same `FB_PAGE_ID`.
- `me/accounts` must be queried with a USER token that has page permissions.
- Do not assume the token currently in `.env` is valid for `me/accounts` during refresh incidents.

## Fast Refresh Runbook

### 1) Stop server/worker and free port 5000

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

### 2) Get a fresh USER token and list pages

Set a temporary variable from Meta tooling (Graph API Explorer or your token flow):

```powershell
$userToken = 'PASTE_FRESH_USER_TOKEN_HERE'
$pages = (Invoke-RestMethod -Method Get -Uri 'https://graph.facebook.com/v20.0/me/accounts' -Body @{ access_token = $userToken }).data
$pages | Select-Object id,name
```

Select the target page (example picks first row):

```powershell
$page = @($pages)[0]
$pageId = [string]$page.id
$pageToken = [string]$page.access_token
```

### 3) Update `.env` with matching page ID + PAGE token

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
Set-Content -Path $envPath -Value $updated -Encoding UTF8
```

### 4) Restart using normal app path

```powershell
& .\run_app.ps1 -SkipScrape -SkipBundle
```

### 5) Validate runtime secrets and preflight

```powershell
Invoke-WebRequest 'http://localhost:5000/api/db/secrets/status' -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest 'http://localhost:5000/api/db/publish/preflight?deep=true' -UseBasicParsing | Select-Object -ExpandProperty Content
```

Expected:

- `secrets/status` returns `ok=true`
- `status.provider` is `facebook_sandbox`
- Deep preflight summary has `failed=0`

### 6) Run end-to-end publish smoke test

```powershell
& .\smoke_test_facebook_sandbox.ps1 -BaseUrl 'http://localhost:5000' -ScheduleDelaySeconds 15
```

Expected:

- `Publish result ... ok: True`
- `commentFallbackApplied: False`
- queue `posted` increments

## Quick Checks Before Full Rotation

```powershell
Invoke-WebRequest 'http://localhost:5000/api/db/secrets/status' -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest 'http://localhost:5000/api/db/publish/preflight' -UseBasicParsing | Select-Object -ExpandProperty Content
```

If either endpoint reports missing/invalid credentials or page mismatch, run the full refresh flow above.

## Notes

- Avoid printing full tokens to logs, docs, or terminal history where possible.
- Process restart is required after `.env` updates so the runtime picks up refreshed credentials.
- If refresh still fails with permission errors, verify the USER token includes page scopes and that `FB_PAGE_ID` belongs to the same page returned by `me/accounts`.
