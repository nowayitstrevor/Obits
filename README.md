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

## 🔧 Configuration

The `funeral_homes_config.json` file contains all funeral home configurations:

- **Active Funeral Homes**: Currently configured and working
- **Scraper Types**: `generic`, `selenium`, `enhanced_generic`, `listings`
- **Custom Selectors**: Site-specific CSS selectors for data extraction
- **Skip Patterns**: URLs to avoid during scraping

## 📊 Data Files

- `obituaries_[home].json` - Individual funeral home data
- `website_obituaries.json` - Complete dataset with metadata
- `obituaries_for_website.json` - Optimized for website integration

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
