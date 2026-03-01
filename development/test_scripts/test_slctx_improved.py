"""
Simple test to verify the improved SLCTX scraping is working.
"""

import sys
import json
from scrape_all_detailed import load_config, scrape_generic_detailed

def test_slctx():
    config = load_config()
    slctx_config = config['funeral_homes']['slctx']
    
    print("Testing SLCTX with improved selectors...")
    print(f"URL: {slctx_config['url']}")
    print()
    
    obituaries = scrape_generic_detailed(slctx_config['url'], slctx_config)
    
    print(f"\nRESULTS:")
    print(f"Successfully scraped: {len(obituaries)} obituaries")
    
    if obituaries:
        print("\nSample obituaries:")
        for i, obit in enumerate(obituaries[:3]):
            print(f"  {i+1}. {obit['name']}")
            print(f"     URL: {obit['url']}")
            print(f"     Content: {len(obit['obituary_text'])} chars")
            print(f"     Preview: {obit['obituary_text'][:150]}...")
            print()

if __name__ == "__main__":
    test_slctx()
