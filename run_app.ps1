param(
    [switch]$SkipScrape,
    [switch]$SkipBundle,
    [switch]$SkipIngest,
    [switch]$NoServer,
    [int]$LookbackDaysForStorage = 0
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host 'ERROR: Python virtual environment not found at .venv\Scripts\python.exe' -ForegroundColor Red
    Write-Host 'Create it first, then install dependencies.' -ForegroundColor Yellow
    exit 1
}

Write-Host 'Obit Scraper App Launcher' -ForegroundColor Cyan
Write-Host ('=' * 50)

if (-not $SkipScrape) {
    Write-Host ("`nRunning scraper (storage lookback: {0} days)..." -f $LookbackDaysForStorage) -ForegroundColor Green
    & $pythonExe 'scrape_selected_obituaries.py' '--lookback-days' "$LookbackDaysForStorage"
}
else {
    Write-Host "`nSkipping scrape step" -ForegroundColor Yellow
}

if (-not $SkipBundle) {
    Write-Host "`nBuilding website dataset (dashboard = last 14 days)..." -ForegroundColor Green
    & $pythonExe 'bundle_for_website.py'
}
else {
    Write-Host "`nSkipping bundle step" -ForegroundColor Yellow
}

if (-not $SkipIngest) {
    $selectedOutputPath = Join-Path $projectRoot 'obituaries_selected_pages.json'
    if (Test-Path $selectedOutputPath) {
        Write-Host "`nSyncing selected output into SQLite app DB..." -ForegroundColor Green
        & $pythonExe 'ingest_selected_to_db.py'
    }
    else {
        Write-Host "`nSkipping DB sync: obituaries_selected_pages.json was not found." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`nSkipping DB sync step" -ForegroundColor Yellow
}

if ($NoServer) {
    Write-Host "`nFinished without starting server (NoServer switch)." -ForegroundColor Cyan
    exit 0
}

Write-Host "`nStarting website server at http://localhost:5000" -ForegroundColor Green
& $pythonExe 'website_server.py'
