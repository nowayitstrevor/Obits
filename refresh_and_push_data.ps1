param(
    [switch]$SkipScrape,
    [switch]$SkipBundle,
    [int]$LookbackDaysForStorage = 0,
    [string]$CommitMessage = ""
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host 'ERROR: Python virtual environment not found at .venv\Scripts\python.exe' -ForegroundColor Red
    exit 1
}

$null = git rev-parse --is-inside-work-tree 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: This folder is not a git repository.' -ForegroundColor Red
    exit 1
}

Write-Host 'Data Refresh + Git Push' -ForegroundColor Cyan
Write-Host ('=' * 50)

if (-not $SkipScrape) {
    Write-Host ("`nRunning scrape_selected_obituaries.py (lookback: {0} days)..." -f $LookbackDaysForStorage) -ForegroundColor Green
    & $pythonExe 'scrape_selected_obituaries.py' '--lookback-days' "$LookbackDaysForStorage"
}
else {
    Write-Host "`nSkipping scrape step" -ForegroundColor Yellow
}

if (-not $SkipBundle) {
    Write-Host "`nRunning bundle_for_website.py..." -ForegroundColor Green
    & $pythonExe 'bundle_for_website.py'
}
else {
    Write-Host "`nSkipping bundle step" -ForegroundColor Yellow
}

$dataFiles = @(
    'obituaries_selected_pages.json',
    'website_obituaries.json',
    'obituaries_for_website.json',
    'obituaries_gracegardens.json'
)

$existingFiles = @()
foreach ($file in $dataFiles) {
    if (Test-Path $file) {
        $existingFiles += $file
    }
}

if ($existingFiles.Count -eq 0) {
    Write-Host "`nNo tracked data files found to commit." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nStaging data files..." -ForegroundColor Green
& git add -- $existingFiles

& git diff --cached --quiet -- $existingFiles
if ($LASTEXITCODE -eq 0) {
    Write-Host 'No JSON data changes detected. Nothing to commit.' -ForegroundColor Yellow
    exit 0
}

if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')
    $CommitMessage = "Refresh obituary data ($timestamp UTC)"
}

Write-Host "`nCommitting JSON updates..." -ForegroundColor Green
& git commit -m $CommitMessage -- $existingFiles

Write-Host "`nPushing to origin/main..." -ForegroundColor Green
& git push origin main

Write-Host "`nDone. Railway can now redeploy from the updated JSON in GitHub." -ForegroundColor Cyan
