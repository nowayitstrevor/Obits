param(
    [switch]$SkipScrape,
    [switch]$SkipBundle,
    [switch]$SkipIngest,
    [int]$LookbackDaysForStorage = 0
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host 'ERROR: Python virtual environment not found at .venv\Scripts\python.exe' -ForegroundColor Red
    Write-Host 'Create it first and install requirements.' -ForegroundColor Yellow
    exit 1
}

$env:DATABASE_PROVIDER = 'postgres'

Write-Host 'Local Scraper -> Neon Runner' -ForegroundColor Cyan
Write-Host ('=' * 50)
Write-Host 'DATABASE_PROVIDER=postgres' -ForegroundColor Gray

if (-not $SkipScrape) {
    Write-Host ("`nRunning scrape_selected_obituaries.py (lookback: {0} days)..." -f $LookbackDaysForStorage) -ForegroundColor Green
    & $pythonExe 'scrape_selected_obituaries.py' '--lookback-days' "$LookbackDaysForStorage"
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Scrape step failed.' -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
else {
    Write-Host "`nSkipping scrape step" -ForegroundColor Yellow
}

if (-not $SkipBundle) {
    Write-Host "`nRunning bundle_for_website.py..." -ForegroundColor Green
    & $pythonExe 'bundle_for_website.py'
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Bundle step failed.' -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
else {
    Write-Host "`nSkipping bundle step" -ForegroundColor Yellow
}

if (-not $SkipIngest) {
    $selectedOutputPath = Join-Path $projectRoot 'obituaries_selected_pages.json'
    if (Test-Path $selectedOutputPath) {
        Write-Host "`nIngesting selected output into Postgres (Neon)..." -ForegroundColor Green
        & $pythonExe 'ingest_selected_to_db.py'
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'Ingest step failed.' -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
    else {
        Write-Host "`nSkipping ingest: obituaries_selected_pages.json was not found." -ForegroundColor Yellow
    }
}
else {
    Write-Host "`nSkipping ingest step" -ForegroundColor Yellow
}

Write-Host "`nDone: local scrape pipeline synced to Neon." -ForegroundColor Cyan
