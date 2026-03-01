# Website Onboarding Guide for Obituary Scraper

## Overview
This guide outlines the systematic approach for adding new funeral home websites to our obituary scraping system.

## Phase 1: Website Analysis & Reconnaissance

### 1.1 Manual Website Exploration
Before writing any code, manually explore the target website:

1. **Find the obituaries section**
   - Look for "Obituaries", "Obituary Listings", "Current Obituaries", "Memorials"
   - Note the exact URL structure
   - Check if it requires pagination

2. **Analyze the listing page structure**
   - Right-click → "View Page Source" 
   - Look for patterns in HTML structure
   - Note CSS classes and IDs used for obituary cards/listings
   - Check if JavaScript is required for content loading

3. **Examine individual obituary pages**
   - Click on 2-3 obituaries to understand the detail page structure
   - Note how names, dates, photos, and content are structured
   - Check URL patterns (e.g., `/obituary/Name`, `/obituaries/ID`, etc.)

### 1.2 Website Classification
Classify the website into one of these categories:

- **Static HTML**: Content loads immediately, no JavaScript required
- **JavaScript SPA**: Single Page Application, requires browser automation
- **Hybrid**: Some content static, some requires JavaScript
- **Third-party Platform**: Uses services like Tribute, FrontRunner, etc.

## Phase 2: Technical Implementation Strategy

### 2.1 Choose Scraping Approach

#### Option A: Generic Scraper Enhancement (Recommended first try)
Use `scrape_generic_obituaries.py` with custom configuration:

```python
# Add to funeral_homes_config.json
{
  "funeral_home_id": {
    "name": "Funeral Home Name",
    "url": "https://example.com/obituaries",
    "scraper_type": "generic_enhanced",
    "custom_selectors": {
      "obituary_list": ".obituary-card, .obit-listing, article.obituary",
      "obituary_link": "a[href*='obituary'], a.obit-link",
      "name_selector": "h1, .deceased-name, .obit-title",
      "date_container": ".dates, .obit-dates, .life-span",
      "photo_selector": ".photo img, .obit-photo img, .deceased-photo"
    },
    "url_patterns": {
      "obituary_page": "/obituary/",
      "skip_patterns": ["/send-flowers", "/share", "/guestbook", "/print"]
    }
  }
}
```

#### Option B: Custom Site-Specific Scraper (For complex sites)
Create a dedicated scraper file like `scrape_[funeral_home].py`:

```python
"""
Custom scraper for [Funeral Home Name]
"""

class CustomFuneralHomeScraper:
    def __init__(self):
        self.base_url = "https://example.com/obituaries"
        self.funeral_home_name = "Example Funeral Home"
    
    def get_obituary_links(self):
        # Site-specific logic for finding obituary links
        pass
    
    def scrape_obituary_details(self, url):
        # Site-specific logic for extracting details
        pass
```

### 2.2 Website-Specific Patterns

#### Pattern 1: Direct Listing Pages
- URL: `/obituaries`, `/obituary-listings`
- Structure: List of cards/items linking to individual pages
- Strategy: Find container, extract links, filter for obituary URLs

#### Pattern 2: JavaScript-Loaded Content
- Indicators: Empty source code, "Loading..." text, API calls in Network tab
- Strategy: Use Selenium WebDriver, wait for content to load
- Tools: WebDriverWait, expected_conditions

#### Pattern 3: Third-Party Platforms
- **Tribute**: Look for `tribute.com` in source or network requests
- **FrontRunner**: Often has `/frontrunnerpro/` in URLs
- **Batesville**: Uses `batesville.com` iframe or API
- Strategy: Each platform has specific API patterns

## Phase 3: Implementation Steps

### 3.1 Create Site Analyzer Tool
Create a diagnostic tool to analyze websites:

```python
def analyze_website(url):
    """
    Analyze a funeral home website and provide recommendations
    """
    analysis = {
        'url': url,
        'requires_javascript': False,
        'platform': 'custom',
        'obituary_indicators': [],
        'suggested_selectors': {},
        'challenges': []
    }
    # Analysis logic here
    return analysis
```

### 3.2 Incremental Testing Approach

1. **Test with generic scraper first**
   - Add to config with `scraper_type: "generic"`
   - Run single scrape: `/api/scrape/funeral_home_id`
   - Check results in JSON file

2. **Analyze and refine**
   - Check what was scraped vs. what should have been scraped
   - Identify false positives (wrong pages) and false negatives (missed obituaries)
   - Adjust selectors and filters

3. **Custom enhancements if needed**
   - Add custom selectors to config
   - Create site-specific scraper if generic approach fails

### 3.3 Quality Validation Checklist

For each new site, validate:

- [ ] **Correct obituary identification**: No auxiliary pages (flowers, guestbook, etc.)
- [ ] **Name extraction**: Names are properly extracted and cleaned
- [ ] **Date parsing**: Birth/death dates identified when available
- [ ] **Photo extraction**: Photos load correctly (check URLs)
- [ ] **No duplicates**: Same obituary not scraped multiple times
- [ ] **Rate limiting**: Respectful scraping intervals (1-2 seconds between requests)

## Phase 4: Maintenance & Monitoring

### 4.1 Error Monitoring
- Track scraping success rates per site
- Monitor for structure changes (empty results, errors)
- Set up alerts for consecutive failures

### 4.2 Website Change Detection
- Quarterly reviews of site structures
- Automated testing for obituary count anomalies
- Version control for scraper configurations

## Site-Specific Solutions for Current Issues

### SLCTX (SLC Texas) - https://www.slctx.com/listings
**Problem**: Picking up auxiliary pages like "send-flowers"

**Solution**:
```python
# Add to config
"skip_patterns": [
  "/send-flowers", 
  "/plant-tree", 
  "/sympathy",
  "/share",
  "/guestbook"
],
"obituary_validation": {
  "min_content_length": 200,
  "required_elements": ["name", "dates_or_age"]
}
```

### Waco Funeral Home Memorial Park - https://www.wacofhmp.com/obituaries
**Problem**: Not finding individual obituary pages

**Solution**: Likely needs Selenium for JavaScript content or different URL pattern
```python
# Investigate these patterns:
- /obituaries/[name]
- /obituary/[id]
- /tribute/[name]
```

## Tools & Resources

### Development Tools
1. **Browser Developer Tools**: Inspect element, Network tab
2. **Selenium**: For JavaScript-heavy sites
3. **Postman**: Test API endpoints if discovered
4. **Website Scrapers**: Consider `scrapy` for complex sites

### Testing Strategy
1. **Unit tests** for each scraper function
2. **Integration tests** for full scraping workflow  
3. **Validation tests** for data quality
4. **Performance tests** for scraping speed/efficiency

## Success Metrics

- **Coverage**: % of local funeral homes successfully onboarded
- **Accuracy**: % of scraped content that is valid obituaries
- **Reliability**: % uptime/success rate over time
- **Freshness**: How quickly new obituaries are detected
