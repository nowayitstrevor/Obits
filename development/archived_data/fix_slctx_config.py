"""
Quick fix script to update the existing SLCTX configuration
in funeral_homes_config.json with enhanced filtering
"""

import json

def update_slctx_config():
    """Update the SLCTX configuration with enhanced filtering."""
    
    # Load existing config
    with open('funeral_homes_config.json', 'r') as f:
        config = json.load(f)
    
    # Enhanced SLCTX configuration
    enhanced_slctx = {
        "name": "SLC Texas Funeral Services",
        "url": "https://www.slctx.com/listings",
        "address": "Unknown",
        "scraper_type": "enhanced_generic",
        "script": "enhanced_generic_scraper.py",
        "storage_file": "obituaries_slctx.json",
        "active": True,
        "priority": 7,
        "requires_javascript": False,
        "custom_selectors": {
            "obituary_list": ".sitemapsubitem, .sitemapitem",
            "obituary_link": "a[href*='/obituary/']",
            "name_selector": "h1, .deceased-name, .tribute-name",
            "date_container": ".dates, .life-span, .tribute-dates",
            "photo_selector": ".photo img, .tribute-photo img"
        },
        "url_patterns": {
            "obituary_indicators": ["/obituary/"],
            "obituary_page": "/obituary/"
        },
        "skip_patterns": [
            "/send-flowers", "/plant-tree", "/sympathy", "/share", 
            "/guestbook", "/guest-book", "/print", "/directions",
            "/flowers", "/gifts", "/memory", "/tribute-store", "/candles"
        ],
        "validation_rules": {
            "min_content_length": 200,
            "required_elements": ["name"],
            "forbidden_content": [
                "contact us", "about us", "our staff", "staff directory",
                "our services", "services overview", "directions to"
            ]
        }
    }
    
    # Update the SLCTX configuration
    config['funeral_homes']['slctx'] = enhanced_slctx
    
    # Save updated config
    with open('funeral_homes_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("✅ Updated SLCTX configuration with enhanced filtering")
    print("   - Added skip patterns to exclude /send-flowers, /plant-tree, etc.")
    print("   - Improved content validation")
    print("   - Added custom selectors based on site analysis")

if __name__ == "__main__":
    update_slctx_config()
