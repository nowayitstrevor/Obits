#!/usr/bin/env python3
"""
Test Pecan Grove Funeral Home
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from bs4 import BeautifulSoup
import time

def test_pecan_grove():
    """Test Pecan Grove with basic Selenium."""
    
    print("🧪 Testing Pecan Grove Funeral Home")
    print("=" * 50)
    
    # Setup Firefox
    options = FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    
    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(30)
    
    try:
        url = "https://www.pecangrovefuneral.com/obituaries"
        print(f"🌐 Loading: {url}")
        
        driver.get(url)
        time.sleep(10)  # Wait for JavaScript
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        print(f"📄 Title: {soup.title.string if soup.title else 'No title'}")
        
        # Look for obituary links
        obit_links = soup.select('a[href*="/obituary/"]')
        print(f"🔍 Found {len(obit_links)} obituary links")
        
        for i, link in enumerate(obit_links[:5]):
            href = link.get('href', 'No href')
            text = link.get_text(strip=True)
            print(f"  {i+1}. {href} -> {text}")
        
        # Save debug HTML
        with open('pecan_grove_debug.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"💾 Debug HTML saved to pecan_grove_debug.html")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_pecan_grove()
