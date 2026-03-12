$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$logDir = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

$timestamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
$logFile = Join-Path $logDir ("local_scrape_to_neon_{0}.log" -f $timestamp)

Write-Host "Running scheduled local scrape -> Neon. Log: $logFile"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'run_local_scrape_to_neon.ps1') *>&1 | Tee-Object -FilePath $logFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Scheduled run failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path $pythonExe) {
    $summaryScriptPath = Join-Path $projectRoot '__neon_post_run_summary.py'
    @'
from env_bootstrap import load_env_file
import db_pipeline

load_env_file()
print('--- Neon Post-Run Summary ---')
print('provider', db_pipeline.get_db_provider())

with db_pipeline.get_connection() as conn:
    latest = conn.execute(
        """
        SELECT id, status, source_count, total_obituaries, created_at
        FROM scrape_runs
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if latest:
        print(
            'latest_scrape_run',
            {
                'id': latest['id'],
                'status': latest['status'],
                'source_count': latest['source_count'],
                'total_obituaries': latest['total_obituaries'],
                'created_at': latest['created_at'],
            },
        )
    else:
        print('latest_scrape_run', None)

    source_counts = conn.execute(
        """
        SELECT source_key, COUNT(*) AS c
        FROM obituaries
        GROUP BY source_key
        ORDER BY c DESC, source_key ASC
        """
    ).fetchall()

    print('obituaries_by_source_count', len(source_counts))
    for row in source_counts:
        print(row['source_key'], row['c'])
'@ | Set-Content -Path $summaryScriptPath -Encoding UTF8

    try {
        & $pythonExe $summaryScriptPath *>&1 | Tee-Object -FilePath $logFile -Append
    }
    finally {
        if (Test-Path $summaryScriptPath) {
            Remove-Item $summaryScriptPath -Force
        }
    }
}
else {
    "--- Neon Post-Run Summary ---`nSkipped: .venv python executable not found." | Tee-Object -FilePath $logFile -Append
}

Write-Host 'Scheduled run completed successfully.' -ForegroundColor Green
