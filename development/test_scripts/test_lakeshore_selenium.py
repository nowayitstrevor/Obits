#!/usr/bin/env python3
"""
Test Lake Shore with Selenium to see if JavaScript is required.
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup
import time

def test_lakeshore_with_selenium():
    """Test Lake Shore with Selenium to handle JavaScript."""
    
    driver = None
    try:
        # Setup Firefox with headless mode
        options = FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(options=options)
        
        url = "https://www.lakeshorefuneralhome.com/obituaries"
        print(f"🚀 Testing with Selenium: {url}")
        
        driver.get(url)
        print("⏳ Waiting for page to load...")
        time.sleep(5)  # Give time for JavaScript to load
        
        # Try to find any content that might indicate obituaries
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        print(f"📄 Page title: {driver.title}")
        print(f"📊 Content length: {len(driver.page_source)} characters")
        
        # Look for various patterns that might indicate obituary content
        potential_selectors = [
            '.obituary', '.memorial', '.tribute',
            '.obit', '.deceased', '.listing',
            '[class*="obituar"]', '[class*="memorial"]',
            '[id*="obituar"]', '[id*="memorial"]',
            'article', '.post', '.entry'
        ]
        
        found_elements = []
        for selector in potential_selectors:
            elements = soup.select(selector)
            if elements:
                found_elements.append((selector, len(elements)))
                
        if found_elements:
            print("🎯 Found potential content containers:")
            for selector, count in found_elements:
                print(f"   {selector}: {count} elements")
                
            # Look at the first few elements in detail
            first_selector = found_elements[0][0]
            elements = soup.select(first_selector)
            print(f"\n🔍 Sample content from {first_selector}:")
            for i, elem in enumerate(elements[:3], 1):
                text = elem.get_text(strip=True)[:100]
                print(f"   {i}. {text}...")
        else:
            print("❌ No obvious obituary content found")
            
        # Check if there are any links that appeared after JavaScript
        all_links = soup.find_all('a', href=True)
        obituary_links = []
        for link in all_links:
            href = link.get('href', '').lower()
            text = link.get_text(strip=True).lower()
            if any(term in href or term in text for term in ['obituar', 'memorial', 'tribute']):
                obituary_links.append((link.get('href'), link.get_text(strip=True)))
                
        if obituary_links:
            print(f"\n🔗 Found {len(obituary_links)} obituary-related links:")
            for href, text in obituary_links[:5]:
                print(f"   → '{text}' - {href}")
        
        # Save page source for manual inspection
        with open('lakeshore_debug.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("\n💾 Saved page source to lakeshore_debug.html for inspection")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_lakeshore_with_selenium()
