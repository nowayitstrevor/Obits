"""
Debug script to test the detailed scraper for one funeral home at a time.
"""

import json
import sys

# Import our functions
from scrape_all_detailed import load_config, scrape_lakeshore_detailed, scrape_generic_detailed

def test_single_funeral_home(home_id):
    """Test scraping a single funeral home."""
    config = load_config()
    funeral_homes = config.get('funeral_homes', {})
    
    if home_id not in funeral_homes:
        print(f"Funeral home '{home_id}' not found in configuration!")
        print(f"Available homes: {list(funeral_homes.keys())}")
        return
    
    home_config = funeral_homes[home_id]
    
    if not home_config.get('active', False):
        print(f"Funeral home '{home_id}' is not active!")
        return
    
    print(f"Testing: {home_config.get('name', home_id)}")
    print(f"URL: {home_config.get('url', '')}")
    print(f"Type: {home_config.get('scraper_type', 'unknown')}")
    
    base_url = home_config.get('url', '')
    
    try:
        if home_id.lower() == 'lakeshore':
            obituaries = scrape_lakeshore_detailed(base_url, home_config)
        else:
            obituaries = scrape_generic_detailed(base_url, home_config)
        
        print(f"Successfully scraped {len(obituaries)} obituaries")
        
        if obituaries:
            print("Sample obituary:")
            sample = obituaries[0]
            print(f"  Name: {sample.get('name', 'N/A')}")
            print(f"  URL: {sample.get('url', 'N/A')}")
            print(f"  Content length: {len(sample.get('obituary_text', ''))}")
        
        return obituaries
        
    except Exception as e:
        print(f"Error scraping {home_config.get('name', home_id)}: {e}")
        return []

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_single_scraper.py <funeral_home_id>")
        print("Example: python debug_single_scraper.py lakeshore")
        sys.exit(1)
    
    home_id = sys.argv[1]
    test_single_funeral_home(home_id)
