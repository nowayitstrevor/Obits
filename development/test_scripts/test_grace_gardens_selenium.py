#!/usr/bin/env python3
"""
Test Grace Gardens obituaries page with Selenium
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from bs4 import BeautifulSoup
import time

def test_grace_gardens_selenium():
    """Test Grace Gardens obituaries page with Selenium."""
    
    print("🧪 Testing Grace Gardens with Selenium")
    print("=" * 50)
    
    # Setup Firefox
    options = FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(30)
    
    try:
        url = "https://www.gracegardensfh.com/obituaries"
        print(f"🌐 Loading: {url}")
        
        driver.get(url)
        print(f"✅ Page loaded")
        
        # Check initial content
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        print(f"📄 Title: {soup.title.string if soup.title else 'No title'}")
        
        # Wait for JavaScript to load content
        print(f"⏳ Waiting 15 seconds for JavaScript content...")
        time.sleep(15)
        
        # Check content after wait
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Look for obituary links with multiple selectors
        selectors_to_try = [
            "a[href*='/obituary/']",
            "a[href*='/memorial/']", 
            "a[href*='/tribute/']",
            ".obit-listing a",
            ".obituary-item a",
            ".memorial-listing a",
            ".tribute-item a"
        ]
        
        total_obituary_links = 0
        for selector in selectors_to_try:
            links = soup.select(selector)
            if links:
                print(f"🔍 Selector '{selector}': {len(links)} links found")
                for i, link in enumerate(links[:3]):  # Show first 3
                    href = link.get('href', 'No href')
                    text = link.get_text(strip=True)
                    print(f"     {i+1}. {href} -> {text}")
                total_obituary_links += len(links)
        
        print(f"\n📊 Total obituary links found: {total_obituary_links}")
        
        # If no specific obituary links, look for any links that might be obituaries
        if total_obituary_links == 0:
            print(f"\n🔍 No obituary links found, checking all links:")
            all_links = soup.select('a[href]')
            print(f"   Total links on page: {len(all_links)}")
            
            potential_obituaries = []
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Skip obvious non-obituary links
                skip_patterns = [
                    '/obituaries',
                    '/search',
                    '/contact',
                    '/about',
                    '/services',
                    '/send-flowers',
                    '/guestbook',
                    'mailto:',
                    '#',
                    'javascript:'
                ]
                
                if not any(pattern in href for pattern in skip_patterns) and href:
                    if href.startswith('/') or 'gracegardensfh.com' in href:
                        potential_obituaries.append((href, text))
            
            print(f"   Potential obituary links: {len(potential_obituaries)}")
            for i, (href, text) in enumerate(potential_obituaries[:10]):
                print(f"     {i+1}. {href} -> {text[:50]}...")
        
        # Save debug HTML
        with open('grace_gardens_selenium_debug.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"\n💾 Full page HTML saved to grace_gardens_selenium_debug.html")
        
        # Check for Tukios/dmAPI specific content
        page_html = driver.page_source.lower()
        tukios_indicators = ['dmapi', 'tukios', 'tribute-technology']
        print(f"\n🔍 Tukios/dmAPI indicators:")
        for indicator in tukios_indicators:
            count = page_html.count(indicator)
            if count > 0:
                print(f"   '{indicator}': found {count} times")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_grace_gardens_selenium()
