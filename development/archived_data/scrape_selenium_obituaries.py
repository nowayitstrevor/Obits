#!/usr/bin/env python3
"""
Selenium-based obituary scraper for Tukios/dmAPI funeral homes.
Based on the successful Lake Shore scraper approach.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from typing import List, Dict, Set, Any
from urllib.parse import urljoin, urlparse, parse_qs
import time
from datetime import datetime
import re

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

def setup_driver():
    """Setup Firefox driver for Selenium."""
    try:
        options = FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"❌ Error setting up Firefox driver: {e}")
        return None

def extract_obituary_details(driver, obituary_url: str, selectors: Dict[str, str]) -> Dict[str, Any]:
    """Extract detailed information from an individual obituary page using Selenium."""
    try:
        print(f"  📄 Extracting details from: {obituary_url}")
        driver.get(obituary_url)
        
        # Wait for the page to load
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        details = {
            'url': obituary_url,
            'scraped_at': datetime.now().isoformat(),
            'name': 'Unknown',
            'birth_date': None,
            'death_date': None,
            'age': None,
            'summary': None,
            'service_info': None,
            'photo_url': None
        }
        
        # Extract name using provided selectors
        name_selectors = selectors.get('name_selector', 'h1').split(', ')
        for selector in name_selectors:
            name_elem = soup.select_one(selector.strip())
            if name_elem and name_elem.get_text(strip=True):
                details['name'] = name_elem.get_text(strip=True)
                break
        
        # Extract content
        content_selectors = selectors.get('content_selector', '.obit-content').split(', ')
        for selector in content_selectors:
            content_elem = soup.select_one(selector.strip())
            if content_elem and content_elem.get_text(strip=True):
                details['summary'] = content_elem.get_text(strip=True)[:500]
                break
        
        # Extract photo
        photo_selectors = selectors.get('photo_selector', '.obit-photo img').split(', ')
        for selector in photo_selectors:
            photo_elem = soup.select_one(selector.strip())
            if photo_elem and photo_elem.get('src'):
                src = photo_elem.get('src')
                if src.startswith('http'):
                    details['photo_url'] = src
                elif src.startswith('/'):
                    base_url = f"https://{urlparse(obituary_url).netloc}"
                    details['photo_url'] = f"{base_url}{src}"
                break
        
        return details
        
    except Exception as e:
        print(f"    ❌ Error extracting details: {e}")
        return None

def scrape_selenium_obituaries(funeral_home_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scrape obituaries from a Tukios/dmAPI funeral home using Selenium.
    """
    
    base_url = funeral_home_config['url']
    name = funeral_home_config['name']
    selectors = funeral_home_config.get('custom_selectors', {})
    skip_patterns = funeral_home_config.get('skip_patterns', [])
    
    print(f"🚀 Scraping {name} with Selenium: {base_url}")
    
    driver = setup_driver()
    if not driver:
        return []
    
    try:
        # Load the obituaries page
        print(f"📖 Loading obituaries page...")
        driver.get(base_url)
        
        # Wait for JavaScript to load content
        print(f"⏳ Waiting for JavaScript content to load...")
        time.sleep(8)  # Give dmAPI time to load
        
        # Get page source after JavaScript execution
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find obituary links
        obituary_urls = set()
        
        # Try multiple selectors for finding obituary links
        link_selectors = [
            selectors.get('obituary_link', ''),
            "a[href*='/obituary/']",
            "a[href*='/memorial/']", 
            "a[href*='/tribute/']",
            ".obituary-item a",
            ".obit-listing a",
            ".memorial-listing a"
        ]
        
        for selector in link_selectors:
            if selector:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            full_url = f"https://{urlparse(base_url).netloc}{href}"
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # Skip unwanted patterns
                        if not any(pattern in full_url for pattern in skip_patterns):
                            obituary_urls.add(full_url)
        
        print(f"🔍 Found {len(obituary_urls)} unique obituary URLs")
        
        if not obituary_urls:
            print(f"⚠️  No obituary URLs found for {name}")
            return []
        
        # Extract details from each obituary
        obituaries = []
        for i, url in enumerate(list(obituary_urls)[:10]):  # Limit to 10 for testing
            print(f"📄 Processing obituary {i+1}/{len(obituary_urls)}: {url}")
            
            details = extract_obituary_details(driver, url, selectors)
            if details:
                details['funeral_home'] = name
                obituaries.append(details)
                
            # Small delay between requests
            time.sleep(1)
        
        print(f"✅ Successfully scraped {len(obituaries)} obituaries from {name}")
        return obituaries
        
    except Exception as e:
        print(f"❌ Error scraping {name}: {e}")
        return []
        
    finally:
        driver.quit()

def main():
    """Test the Selenium scraper with one funeral home."""
    
    # Test with WHB Family
    test_config = {
        "name": "WHB Family Funeral Home",
        "url": "https://www.whbfamily.com/obituaries",
        "custom_selectors": {
            "obituary_link": "a[href*='/obituary/']",
            "name_selector": "h1, .deceased-name, .obit-name",
            "content_selector": ".obit-content, .obituary-text",
            "photo_selector": ".obit-photo img, .memorial-photo img"
        },
        "skip_patterns": [
            "/obituaries",
            "/search",
            "/send-flowers",
            "/guestbook",
            "mailto:",
            "#",
            "javascript:"
        ]
    }
    
    print("🧪 Testing Selenium scraper with WHB Family")
    print("=" * 50)
    
    obituaries = scrape_selenium_obituaries(test_config)
    
    if obituaries:
        print(f"\n📊 RESULTS:")
        print(f"✅ Found {len(obituaries)} obituaries")
        
        for i, obit in enumerate(obituaries[:3]):  # Show first 3
            print(f"\n{i+1}. {obit['name']}")
            print(f"   URL: {obit['url']}")
            if obit['summary']:
                print(f"   Summary: {obit['summary'][:100]}...")
        
        # Save results
        with open('selenium_test_results.json', 'w') as f:
            json.dump(obituaries, f, indent=2)
        print(f"\n💾 Results saved to selenium_test_results.json")
        
    else:
        print(f"\n❌ No obituaries found")

if __name__ == "__main__":
    main()
