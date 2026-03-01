# Enhanced Waco Area Obituary Aggregator

A comprehensive web-based system for monitoring and managing obituary listings from multiple funeral homes in the Waco, Texas area.

## New Features

### 🏢 Multi-Funeral Home Support
- **12 pre-configured funeral homes** including:
  - Lake Shore Funeral Home (Active)
  - Aderhold Funeral Home
  - Grace Gardens Funeral Home
  - McDowell Funeral Home
  - Pecan Grove Funeral Home
  - And 7 more regional funeral homes

### 🔍 Search & Filter Capabilities
- **Real-time search** across all obituaries
- **Filter by funeral home** to focus on specific locations
- **Search archived obituaries** separately
- **Keyword matching** on names, dates, and content

### 📁 Archive Management
- **Archive old obituaries** to keep current listings clean
- **Separate archive view** for historical records
- **Automatic archiving** options (configurable)
- **Restore archived obituaries** if needed

### ⚙️ Funeral Home Management
- **Add new funeral homes** through the web interface
- **Enable/disable funeral homes** without deletion
- **Edit funeral home details** (name, URL, address)
- **Delete funeral homes** with confirmation
- **Track last scrape times** for each location

### 📊 Enhanced Statistics
- **Total obituary counts** across all sources
- **Active vs inactive funeral homes**
- **Archive statistics**
- **Last scrape times** for monitoring

### 🎨 Improved User Interface
- **Tabbed navigation** for different functions
- **Responsive design** for mobile and desktop
- **Modal dialogs** for management tasks
- **Status indicators** and progress feedback
- **Enhanced card layouts** with action buttons

## Installation & Setup

### Prerequisites
- Python 3.7 or higher
- Firefox browser (for web scraping)

### Quick Start
1. **Extract files** to your desired directory
2. **Run the setup script**:
   ```
   start_enhanced_ui.bat
   ```
3. **Open your browser** to http://localhost:5000

### Manual Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install flask flask-cors requests beautifulsoup4 selenium webdriver-manager

# Run the application
python enhanced_web_ui.py
```

## Usage Guide

### Managing Funeral Homes
1. Go to the **"Funeral Homes"** tab
2. Click **"Add Funeral Home"** to add new sources
3. Use **"Activate"/"Deactivate"** to control which homes are scraped
4. Click **"Scrape Now"** to manually trigger scraping for specific homes

### Searching Obituaries
1. Stay on the **"Obituaries"** tab
2. Use the **search box** to find specific people or content
3. Use the **funeral home filter** to narrow results
4. Click **"Clear"** to reset filters

### Archiving Obituaries
1. Click the **"Archive"** button on any obituary card
2. Archived obituaries move to the **"Archive"** tab
3. Use the archive search to find historical records

### Scraping Data
- **"Refresh List"**: Updates the display from existing data
- **"Scrape All Active"**: Runs scrapers for all enabled funeral homes
- **"Scrape Now"**: Runs scraper for a specific funeral home

## Technical Details

### File Structure
```
Obit Scraper/
├── enhanced_web_ui.py          # Main web application
├── scrape_generic_obituaries.py # Universal scraper for new sites
├── scrape_real_obituaries.py    # Lake Shore specific scraper
├── funeral_homes_config.json    # Funeral home configuration
├── templates/
│   └── index.html               # Web interface
├── obituaries_*.json           # Data files for each funeral home
└── start_enhanced_ui.bat       # Quick start script
```

### Configuration Files
- **funeral_homes_config.json**: Central configuration for all funeral homes
- **obituaries_[name].json**: Individual data files for each funeral home
- **archived_obituaries.json**: Archived obituary storage

### Scraping Strategy
The system uses a multi-strategy approach:
1. **Site structure detection** to identify obituary listings
2. **Multiple extraction methods** (CSS selectors, keywords, structure analysis)
3. **JavaScript handling** with Selenium when needed
4. **Photo validation** and URL processing
5. **Date parsing** and age calculation

## Supported Funeral Homes

| Name | Website | Status | Location |
|------|---------|---------|----------|
| Lake Shore Funeral Home | lakeshorefuneralhome.com | Active | Waco, TX |
| Aderhold Funeral Home | aderholdfuneralhome.com | Ready | West, TX |
| Grace Gardens Funeral Home | gracegardensfh.com | Ready | Waco, TX |
| McDowell Funeral Home | mcdowellfuneralhome.com | Ready | Waco, TX |
| Pecan Grove Funeral Home | pecangrovefuneral.com | Ready | Waco, TX |
| WHB Family Funeral Home | whbfamily.com | Ready | - |
| SLC Texas Funeral Services | slctx.com | Ready | - |
| Oak Crest Funeral Home | oakcrestwaco.com | Ready | Waco, TX |
| Foss Funeral Home | fossfuneralhome.com | Ready | - |
| Robertson Funeral Home | robertsonfh.com | Ready | - |
| Waco Funeral Home Memorial Park | wacofhmp.com | Ready | Waco, TX |

## Troubleshooting

### Common Issues
1. **Scraping fails**: Check if the website structure has changed
2. **No obituaries found**: Some sites may require manual activation
3. **Photos not loading**: CloudFront URLs may have changed
4. **JavaScript errors**: Clear browser cache and refresh

### Logging
- Enable **"Show/Hide Logs"** to see detailed scraping output
- Check the console for JavaScript errors
- Review individual funeral home scrape results

### Performance
- Scrapers include **rate limiting** to be respectful to websites
- **Background processing** prevents UI blocking
- **Incremental updates** only add new obituaries

## Future Enhancements

### Planned Features
- **Email notifications** for new obituaries
- **RSS feed generation** for external consumption
- **Export capabilities** (CSV, PDF)
- **Advanced search filters** (date ranges, age, location)
- **Bulk archive operations**
- **Automated scheduling** for regular scraping

### Customization
- **Add custom scrapers** for specific website types
- **Modify extraction rules** for better data quality
- **Configure archive policies** for automatic cleanup
- **Customize UI themes** and layouts

## Support

For technical issues or feature requests:
1. Check the troubleshooting guide above
2. Review log outputs for error details
3. Test with individual funeral homes to isolate issues
4. Consider site structure changes for scraping problems

## License

This project is for educational and personal use. Please respect website terms of service and implement appropriate rate limiting when scraping external sites.
