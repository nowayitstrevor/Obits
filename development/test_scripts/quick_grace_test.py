#!/usr/bin/env python3
"""
Quick test to verify Grace Gardens obituary detection
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from bs4 import BeautifulSoup
import time

def quick_test_grace_gardens():
    """Quick test to see if we can find obituary links."""
    
    print("🚀 Quick Grace Gardens Test")
    print("=" * 30)
    
    options = FirefoxOptions()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    
    try:
        driver.get("https://www.gracegardensfh.com/obituaries")
        time.sleep(10)  # Wait for JavaScript
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Test our new Tukios selectors
        selectors_to_test = [
            ".tukios--obituary-listing-item a[href*='/obituaries/']",
            ".tukios--obituary-listing-name a",
            "a[href*='/obituaries/'][href*='/obituaries/']"
        ]
        
        total_found = 0
        for selector in selectors_to_test:
            links = soup.select(selector)
            print(f"📍 '{selector}': {len(links)} links")
            total_found += len(links)
            
            for i, link in enumerate(links[:3]):
                href = link.get('href', 'No href')
                text = link.get_text(strip=True)
                print(f"    {i+1}. {href} -> {text}")
        
        print(f"\n✅ Total obituary links found: {total_found}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    quick_test_grace_gardens()
