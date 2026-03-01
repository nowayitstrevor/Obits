#!/usr/bin/env python3
"""
Generic Selenium scraper for Tukios/dmAPI-based funeral homes.
These sites load obituaries via JavaScript after the page loads.
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import requests

def test_tukios_site_with_selenium(site_name, obituary_url):
    """Test a Tukios/dmAPI site with Selenium to load JavaScript content."""
    
    driver = None
    try:
        # Setup Firefox with headless mode
        options = FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Firefox(options=options)
        
        print(f"\n🚀 Testing {site_name} with Selenium: {obituary_url}")
        
        driver.get(obituary_url)
        print("⏳ Waiting for JavaScript to load obituaries...")
        
        # Wait longer for JavaScript content to load
        time.sleep(8)  # Give time for dmAPI to load content
        
        # Get the page source after JavaScript execution
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        print(f"📄 Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Look for obituary links that might have been loaded via JavaScript
        obituary_links = []
        
        # Try various selectors for obituary links
        link_selectors = [
            "a[href*='/obituary/']",
            "a[href*='/memorial/']", 
            "a[href*='/tribute/']",
            ".obituary-item a",
            ".obit-listing a",
            ".memorial-listing a"
        ]
        
        for selector in link_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                text = link.get_text(strip=True)
                if href and text:
                    obituary_links.append({
                        'url': href if href.startswith('http') else f"https://{obituary_url.split('/')[2]}{href}",
                        'text': text,
                        'selector': selector
                    })
        
        print(f"🔍 Found {len(obituary_links)} potential obituary links after JavaScript execution:")
        for i, link in enumerate(obituary_links[:5]):  # Show first 5
            print(f"   {i+1}. '{link['text']}' -> {link['url']} (via {link['selector']})")
        
        if obituary_links:
            print(f"✅ {site_name} appears to be working with Selenium!")
            
            # Test accessing one obituary
            test_url = obituary_links[0]['url']
            print(f"\n🧪 Testing individual obituary: {test_url}")
            
            driver.get(test_url)
            time.sleep(3)  # Wait for obituary page to load
            
            obit_soup = BeautifulSoup(driver.page_source, 'html.parser')
            obit_title = obit_soup.title.string if obit_soup.title else "No title"
            print(f"   Obituary page title: {obit_title}")
            
            # Try to find the deceased's name
            name_selectors = ['h1', '.deceased-name', '.obit-name', '.memorial-name', '.name']
            for selector in name_selectors:
                name_elem = obit_soup.select_one(selector)
                if name_elem and name_elem.get_text(strip=True):
                    print(f"   Name found (via {selector}): {name_elem.get_text(strip=True)}")
                    break
            
            return True, len(obituary_links)
        else:
            print(f"❌ {site_name} - No obituary links found even with Selenium")
            
            # Save HTML for debugging
            debug_file = f"{site_name.lower().replace(' ', '_')}_selenium_debug.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            print(f"💾 Saved debug HTML to {debug_file}")
            
            return False, 0
            
    except Exception as e:
        print(f"❌ Error testing {site_name} with Selenium: {e}")
        return False, 0
        
    finally:
        if driver:
            driver.quit()

def main():
    """Test all the Tukios/dmAPI funeral homes with Selenium."""
    
    # Funeral homes that use Tukios/dmAPI platform
    tukios_sites = [
        ("WHB Family Funeral Home", "https://www.whbfamily.com/obituaries"),
        ("Grace Gardens Funeral Home", "https://www.gracegardensfh.com/obituaries"), 
        ("Pecan Grove Funeral Home", "https://www.pecangrovefuneral.com/obituaries"),
        ("Oak Crest Funeral Home", "https://www.oakcrestwaco.com/obituaries"),
        ("Waco Funeral Home Memorial Park", "https://www.wacofhmp.com/obituaries")
    ]
    
    print("🧪 Testing Tukios/dmAPI funeral homes with Selenium")
    print("=" * 60)
    
    results = []
    
    for site_name, url in tukios_sites:
        success, count = test_tukios_site_with_selenium(site_name, url)
        results.append({
            'name': site_name,
            'url': url, 
            'success': success,
            'obituary_count': count
        })
        
        print("-" * 40)
    
    # Summary
    print(f"\n📊 RESULTS SUMMARY:")
    print("=" * 40)
    
    working_sites = [r for r in results if r['success']]
    failed_sites = [r for r in results if not r['success']]
    
    print(f"✅ Working with Selenium: {len(working_sites)}")
    for site in working_sites:
        print(f"   • {site['name']}: {site['obituary_count']} obituaries")
    
    print(f"❌ Still not working: {len(failed_sites)}")
    for site in failed_sites:
        print(f"   • {site['name']}")
    
    if working_sites:
        print(f"\n🎯 Next step: Update funeral_homes_config.json to use Selenium for these {len(working_sites)} sites")

if __name__ == "__main__":
    main()
