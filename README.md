# 🕊️ Local Obituary Scraper - Production Ready

A comprehensive obituary scraping system for local funeral homes with website integration.

## 📊 Current Status

**✅ 4 Working Funeral Homes - 40+ Obituaries**
- **Foss Funeral Home**: 12 obituaries
- **Robertson Funeral Home**: 10 obituaries  
- **SLC Texas Funeral Services**: 10 obituaries
- **McDowell Funeral Home**: 8 obituaries

**🌺 Recently Added:**
- **Grace Gardens Funeral Home**: 10 obituaries (manually extracted, ready for automation)

**🎯 Available for Activation:**
- Lake Shore Funeral Home (Selenium ready)
- Aderhold Funeral Home (Generic scraper)
- Pecan Grove Funeral Home (Selenium ready)
- Oak Crest Funeral Home (Selenium ready)
- Waco Funeral Home Memorial Park (Selenium ready)

## 🚀 Production Files

### Core Scrapers
- `scrape_obituaries_detailed.py` - **Main production scraper**
- `generic_selenium_scraper.py` - Selenium scraper for JavaScript sites
- `enhanced_generic_scraper.py` - Enhanced scraper for complex sites
- `scrape_generic_obituaries.py` - Basic generic scraper

### Configuration & Analysis
- `funeral_homes_config.json` - **Main configuration file**
- `analyze_funeral_homes.py` - Status analysis and reporting

### Website Integration
- `bundle_for_website.py` - Creates unified dataset for website
- `website_server.py` - Flask API server for obituary data
- `website_preview.html` - Website preview with responsive design
- `aggregate_obituaries.py` - Data aggregation utilities

## 📁 Repository Structure

```
📂 Obit Scraper/
├── 🚀 Production Files (listed above)
├── 💾 Data Files (obituaries_*.json, website_*.json)
├── 📂 development/
│   ├── 📂 debug_scripts/     - Debug and diagnostic scripts
│   ├── 📂 test_scripts/      - Test and experimental scripts  
│   ├── 📂 html_debug/        - HTML debug files and page sources
│   └── 📂 archived_data/     - Archived scrapers and old configs
└── 📂 templates/             - Web UI templates
```

## ⚙️ Quick Start

### One command (recommended on Windows)
```powershell
& .\run_app.ps1
```

### Refresh data and push JSON to GitHub (for Railway)
```powershell
& .\refresh_and_push_data.ps1
```

### Automate daily refresh via Windows Task Scheduler
```powershell
# Create/update daily task (default 07:00)
& .\register_refresh_task.ps1

# Or pick a custom time (24-hour format)
& .\register_refresh_task.ps1 -Time "18:30"

# Run task immediately
schtasks /Run /TN "ObitScraper-RefreshAndPush"
```

Optional switches:
```powershell
# Skip scraping and only rebuild + push current data files
& .\refresh_and_push_data.ps1 -SkipScrape

# Skip bundling and only push scraper output JSON
& .\refresh_and_push_data.ps1 -SkipBundle

# Custom commit message
& .\refresh_and_push_data.ps1 -CommitMessage "Weekly obituary refresh"
```

Optional switches:
```powershell
# Keep full history in storage (default), rebuild dashboard, do not start server
& .\run_app.ps1 -LookbackDaysForStorage 0 -NoServer

# Start server only with existing data
& .\run_app.ps1 -SkipScrape -SkipBundle
```

### 1. Run the Main Scraper
```bash
py scrape_obituaries_detailed.py
```

### 1b. Scrape configured selected pages (new unified flow)
```bash
py scrape_selected_obituaries.py
# optional: py scrape_selected_obituaries.py --sources foss,robertson,slctx
```

### 1c. Ingest selected scrape output into local SQLite app DB
```bash
py ingest_selected_to_db.py
# optional: py ingest_selected_to_db.py --input obituaries_selected_pages.json --db-path data/app.db
```

### 2. Check Status
```bash
py analyze_funeral_homes.py
```

### 3. Create Website Dataset
```bash
py bundle_for_website.py
```

### 4. Start Website Server
```bash
py website_server.py
# Visit: http://localhost:5000
```

### 5. Query DB-backed Phase 1 endpoints
```bash
# Recent obituaries from SQLite feed
http://localhost:5000/api/db/obituaries/recent

# Full DB feed (up to 200)
http://localhost:5000/api/db/obituaries

# Per-source health summary (green/yellow/red)
http://localhost:5000/api/db/source-health

# Sources requiring scraper reprogramming/action
http://localhost:5000/api/db/source-health/action-required
```

## Publish Worker And Sandbox Runbook

### Register/start the publish worker task (Windows)
```powershell
# register or update startup task
& .\register_publish_worker_task.ps1 -PollSeconds 300 -BatchLimit 25 -DeepPreflightIntervalSeconds 3600

# start immediately
schtasks /Run /TN "ObitScraper-PublishWorker"

# verify task details
schtasks /Query /TN "ObitScraper-PublishWorker" /V /FO LIST
```

### Check publish worker API status
```powershell
Invoke-WebRequest "http://localhost:5000/api/db/publish/status" -UseBasicParsing | Select-Object -ExpandProperty Content
```

### Check operational health and latest preflight telemetry
```powershell
Invoke-WebRequest "http://localhost:5000/api/db/ops/health" -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest "http://localhost:5000/api/db/publish/preflight/latest" -UseBasicParsing | Select-Object -ExpandProperty Content
```

### Schedule recurring health checks (Windows Task Scheduler)
```powershell
# run deep preflight + ops health every 30 minutes
& .\register_publish_health_task.ps1 -IntervalMinutes 30 -Deep

# run now
schtasks /Run /TN "ObitScraper-PublishHealthCheck"
```

### Run publish preflight checks
```powershell
# lightweight preflight
Invoke-WebRequest "http://localhost:5000/api/db/publish/preflight" -UseBasicParsing | Select-Object -ExpandProperty Content

# deep preflight (creates unpublished probe post/comment and then cleans both up)
Invoke-WebRequest "http://localhost:5000/api/db/publish/preflight?deep=true" -UseBasicParsing | Select-Object -ExpandProperty Content
```

### Facebook provider mode
Set these in the server/worker environment before publishing:

- `FB_PUBLISH_PROVIDER`:
	- `mock` for local safe testing
	- `facebook_sandbox` for Graph API sandbox posting
- `FB_PAGE_ID` (required for `facebook_sandbox`)
- `FB_PAGE_ACCESS_TOKEN` (required for `facebook_sandbox`)
- `FB_SANDBOX_ALLOW_COMMENT_FALLBACK` (optional, default `false` for strict two-step publish)
- `FB_GRAPH_API_VERSION` (optional, default `v20.0`)
- `FB_GRAPH_API_BASE_URL` (optional override)
- `FB_PUBLISH_TIMEOUT_SECONDS` (optional, default `20`)
- `PUBLISH_PREFLIGHT_DEEP_INTERVAL_SECONDS` (optional, default `0`; enable periodic deep checks in worker loop)
- `PUBLISH_WORKER_STALE_MULTIPLIER` (optional, default `3`)
- `PUBLISH_WORKER_STALE_MIN_SECONDS` (optional, default `600`)

Use environment variables only for credentials. Start from `.env.example` and keep `.env` local (ignored by git). The server and worker now load `.env` directly at startup (without overriding already exported environment values).

If credentials were exposed, rotate immediately before any further publishing:
- Rotate Meta app secret
- Regenerate user token with `pages_manage_posts` + `pages_manage_engagement`
- Regenerate page access token
- Update local env vars and restart server/worker processes

Detailed credential procedure: `SECRET_ROTATION_RUNBOOK.md`

### Run direct sandbox smoke test (API-only)
```powershell
# auto-selects a staged/new record, schedules it, runs due publish, then prints counts/status
& .\smoke_test_facebook_sandbox.ps1 -BaseUrl "http://localhost:5000" -ScheduleDelaySeconds 30

# optional: target a specific obituary id
& .\smoke_test_facebook_sandbox.ps1 -BaseUrl "http://localhost:5000" -ObituaryId "some-obituary-id" -ScheduleDelaySeconds 30
```

If provider is not `facebook_sandbox`, the smoke test exits by default to prevent accidental provider mismatch.
The smoke test also fails when fallback is enabled, unless explicitly overridden with `-AllowCommentFallback`.
The smoke test runs deep publish preflight checks by default; use `-SkipPreflight` to bypass.

## 🔧 Configuration

The `funeral_homes_config.json` file contains all funeral home configurations:

- **Active Funeral Homes**: Currently configured and working
- **Scraper Types**: `generic`, `selenium`, `enhanced_generic`, `listings`
- **Custom Selectors**: Site-specific CSS selectors for data extraction
- **Skip Patterns**: URLs to avoid during scraping

Phase 2 freshness tuning:
- `SOURCE_NO_NEW_RUNS_RED` (default `3`) marks a source as red/`needs_reprogramming=1` after N consecutive successful runs with no newly discovered obituaries.

## 📊 Data Files

- `obituaries_[home].json` - Individual funeral home data
- `website_obituaries.json` - Complete dataset with metadata
- `obituaries_for_website.json` - Optimized for website integration
- `data/app.db` - Local canonical SQLite store for feed, queue, and scrape status

## PostgreSQL Migration (Neon)

Run this when moving existing SQLite data to Neon Postgres.

1. Create schema in Neon
```sql
-- In Neon SQL Editor, run:
-- development/sql/postgres_bootstrap.sql
```

2. Install Python dependencies (includes Postgres driver)
```powershell
py -m pip install -r requirements.txt
```

3. Make sure `.env` has your Neon connection string
```env
DB_CONNECTION_STRING=postgresql://...
```

4. Run one-time SQLite -> Postgres backfill
```powershell
py development/scripts/sqlite_to_postgres_backfill.py --sqlite-path data/app.db
```

Optional reset-and-reload mode:
```powershell
py development/scripts/sqlite_to_postgres_backfill.py --sqlite-path data/app.db --truncate-target
```

The script prints per-table source row counts and Postgres row counts so you can verify parity quickly.

## Local Scraper To Neon (Recommended Hybrid Setup)

Use this mode when your app runs on Railway but scraping runs on your local Windows machine.

1. Ensure `.env` contains:
	- `DB_CONNECTION_STRING=postgresql://...`
	- `DATABASE_PROVIDER=postgres`
2. Run local pipeline manually:
```powershell
& .\run_local_scrape_to_neon.ps1
```

Optional switches:
```powershell
# only ingest existing selected output JSON into Neon
& .\run_local_scrape_to_neon.ps1 -SkipScrape -SkipBundle

# custom scrape lookback window
& .\run_local_scrape_to_neon.ps1 -LookbackDaysForStorage 7
```

Create a daily scheduled task:
```powershell
& .\register_local_scrape_task.ps1 -Time "07:00"
```

Run scheduled task now:
```powershell
schtasks /Run /TN "ObitScraper-LocalScrapeToNeon"
```

## 🌐 Website Features

- **Responsive Design**: Works on desktop and mobile
- **Interactive Filtering**: Filter by funeral home
- **Rich Content**: Photos, summaries, service information
- **API Endpoints**: RESTful API for external integration
- **Real-time Stats**: Live obituary counts and updates

## 🎯 Next Steps

1. **Activate remaining funeral homes** to reach 80+ total obituaries
2. **Deploy website** to production hosting
3. **Set up automated scheduling** for regular scraping
4. **Add notification system** for new obituaries

## 📈 Technical Details

### Supported Platforms
- **Tukios/dmAPI**: Grace Gardens, Pecan Grove, Oak Crest, Waco FHMP
- **Tribute Technology**: Lake Shore Funeral Home
- **Generic CMS**: Foss, McDowell, Aderhold
- **Custom Platforms**: SLC Texas, Robertson

### Browser Automation
- **Firefox WebDriver** with headless operation
- **JavaScript Support** for dynamic content loading
- **Automatic waiting** for content to fully load
- **Error handling** and retry mechanisms

---

*Last Updated: July 27, 2025 - Repository cleaned and organized for production use*
