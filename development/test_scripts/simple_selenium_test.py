#!/usr/bin/env python3
"""
Simple test to see if Selenium can work with one Tukios site.
"""

try:
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from bs4 import BeautifulSoup
    import time
    
    print("🔧 Testing Selenium setup...")
    
    # Setup Firefox with headless mode
    options = FirefoxOptions()
    options.add_argument('--headless')
    
    driver = webdriver.Firefox(options=options)
    
    # Test WHB Family first
    url = "https://www.whbfamily.com/obituaries"
    print(f"🚀 Testing: {url}")
    
    driver.get(url)
    print("⏳ Waiting 5 seconds for page to load...")
    time.sleep(5)
    
    # Get page source
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    print(f"📄 Page title: {soup.title.string if soup.title else 'No title'}")
    print(f"📏 Page content length: {len(page_source)} characters")
    
    # Look for obituary links
    obituary_links = soup.select("a[href*='/obituary/']")
    print(f"🔍 Found {len(obituary_links)} obituary links")
    
    if obituary_links:
        for i, link in enumerate(obituary_links[:3]):
            print(f"   {i+1}. {link.get_text(strip=True)} -> {link.get('href')}")
    
    driver.quit()
    print("✅ Selenium test completed successfully!")
    
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("💡 Try: pip install selenium webdriver-manager")
    
except Exception as e:
    print(f"❌ Selenium error: {e}")
    print("💡 Make sure Firefox is installed on your system")
