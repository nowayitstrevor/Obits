#!/usr/bin/env python3
"""
Generic Selenium-based obituary scraper for Tukios/dmAPI funeral homes.
Based on the successful Lake Shore scraper pattern.
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

def setup_selenium_driver():
    """Setup Firefox driver for Selenium with proper configuration."""
    try:
        options = FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver
    except Exception as e:
        print(f"❌ Error setting up Firefox driver: {e}")
        return None

def extract_obituary_details_generic(driver, obituary_url: str, selectors: Dict[str, str], funeral_home_name: str) -> Dict[str, Any]:
    """Extract detailed information from an individual obituary page using configurable selectors."""
    try:
        print(f"    📄 Extracting details from: {obituary_url}")
        driver.get(obituary_url)
        
        # Wait for the page to load
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        details = {
            'url': obituary_url,
            'scraped_at': datetime.now().isoformat(),
            'funeral_home': funeral_home_name,
            'name': 'Unknown',
            'birth_date': None,
            'death_date': None,
            'age': None,
            'summary': None,
            'service_info': None,
            'photo_url': None
        }
        
        # Extract name using Tukios-specific selectors first
        name_selectors = [
            '.tukios--obituary-listing-name',
            'h1.tw-text-2xl', 
            'h3.tukios--obituary-listing-name.tw-text-2xl'
        ] + selectors.get('name_selector', 'h1').split(', ')
        
        for selector in name_selectors:
            try:
                name_elem = soup.select_one(selector.strip())
                if name_elem and name_elem.get_text(strip=True):
                    details['name'] = name_elem.get_text(strip=True)
                    print(f"      ✓ Name: {details['name']}")
                    break
            except Exception:
                continue

        # Extract content/summary using Tukios selectors
        content_selectors = [
            '.tukios--obituary-listing-snippet',
            '.obituary-content',
            '.obit-content'
        ] + selectors.get('content_selector', '.obit-content, .obituary-text').split(', ')
        
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector.strip())
                if content_elem and content_elem.get_text(strip=True):
                    content_text = content_elem.get_text(strip=True)
                    details['summary'] = content_text[:500] + "..." if len(content_text) > 500 else content_text
                    print(f"      ✓ Content length: {len(content_text)} chars")
                    break
            except Exception:
                continue

        # Extract photo using Tukios CDN pattern
        photo_selectors = [
            'img[src*="cdn.tukioswebsites.com"]',
            '.tukios--obituary-listing-image img'
        ] + selectors.get('photo_selector', '.obit-photo img, .memorial-photo img').split(', ')
        
        for selector in photo_selectors:
            try:
                photo_elem = soup.select_one(selector.strip())
                if photo_elem and photo_elem.get('src'):
                    src = photo_elem.get('src')
                    if src.startswith('http'):
                        details['photo_url'] = src
                    elif src.startswith('/'):
                        base_url = f"https://{urlparse(obituary_url).netloc}"
                        details['photo_url'] = f"{base_url}{src}"
                    print(f"      ✓ Photo: {details['photo_url']}")
                    break
            except Exception:
                continue
        
        return details
        
    except Exception as e:
        print(f"    ❌ Error extracting details: {e}")
        return None

def scrape_tukios_funeral_home(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scrape obituaries from a Tukios/dmAPI funeral home using Selenium.
    """
    
    base_url = config['url']
    name = config['name']
    selectors = config.get('custom_selectors', {})
    skip_patterns = config.get('skip_patterns', [])
    
    print(f"\n🚀 Scraping {name} with Selenium")
    print(f"   URL: {base_url}")
    
    driver = setup_selenium_driver()
    if not driver:
        print(f"❌ Could not setup Selenium driver for {name}")
        return []
    
    try:
        # Load the obituaries page
        print(f"📖 Loading obituaries page...")
        driver.get(base_url)
        
        # Wait for JavaScript to load content (Tukios/dmAPI needs time)
        print(f"⏳ Waiting for JavaScript content to load...")
        time.sleep(10)  # Give dmAPI time to load
        
        # Get page source after JavaScript execution
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        page_title = soup.title.string if soup.title else "No title"
        print(f"📄 Page loaded: {page_title}")
        
        # Find obituary links using multiple strategies
        obituary_urls = set()
        
        # Strategy 1: Use Tukios-specific selectors (most reliable)
        tukios_selectors = [
            ".tukios--obituary-listing-item a[href*='/obituaries/']",
            ".tukios--obituary-listing-name a",
            "a[href*='/obituaries/'][href*='/obituaries/']"
        ]
        
        # Strategy 2: Use configured selectors
        link_selectors = [
            selectors.get('obituary_link', ''),
            "a[href*='/obituary/']",
            "a[href*='/memorial/']", 
            "a[href*='/tribute/']"
        ]
        
        # Strategy 3: Look in common containers  
        container_selectors = [
            ".obit-listing a",
            ".obituary-item a", 
            ".memorial-listing a",
            ".tribute-item a"
        ]
        
        all_selectors = tukios_selectors + link_selectors + container_selectors
        
        for selector in all_selectors:
            if selector.strip():
                try:
                    links = soup.select(selector.strip())
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
                except Exception as e:
                    print(f"    ⚠️ Error with selector '{selector}': {e}")
                    continue
        
        print(f"🔍 Found {len(obituary_urls)} unique obituary URLs")
        
        if not obituary_urls:
            print(f"⚠️ No obituary URLs found for {name}")
            # Save debug HTML
            with open(f"{name.lower().replace(' ', '_')}_debug.html", 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"💾 Debug HTML saved for inspection")
            return []
        
        # Show sample URLs found
        sample_urls = list(obituary_urls)[:3]
        for i, url in enumerate(sample_urls):
            print(f"   {i+1}. {url}")
        
        # Extract details from each obituary (limit for testing)
        obituaries = []
        max_obituaries = min(len(obituary_urls), 10)  # Limit to 10 for testing
        
        for i, url in enumerate(list(obituary_urls)[:max_obituaries]):
            print(f"📄 Processing obituary {i+1}/{max_obituaries}")
            
            details = extract_obituary_details_generic(driver, url, selectors, name)
            if details and details['name'] != 'Unknown':
                obituaries.append(details)
                
            # Small delay between requests
            time.sleep(2)
        
        print(f"✅ Successfully scraped {len(obituaries)} obituaries from {name}")
        return obituaries
        
    except Exception as e:
        print(f"❌ Error scraping {name}: {e}")
        return []
        
    finally:
        try:
            driver.quit()
        except:
            pass

def main():
    """Test the generic Selenium scraper with one funeral home."""
    
    # Load the config to get a real funeral home
    try:
        with open('funeral_homes_config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        # Test with Grace Gardens (confirmed Tukios site)
        grace_config = config_data['funeral_homes']['gracegardens']
        
        print("🧪 Testing Generic Selenium Scraper")
        print("=" * 50)
        
        obituaries = scrape_tukios_funeral_home(grace_config)
        
        if obituaries:
            print(f"\n📊 RESULTS:")
            print(f"✅ Found {len(obituaries)} obituaries")
            
            for i, obit in enumerate(obituaries[:3]):  # Show first 3
                print(f"\n{i+1}. {obit['name']}")
                print(f"   URL: {obit['url']}")
                if obit['summary']:
                    print(f"   Summary: {obit['summary'][:100]}...")
            
            # Save results
            with open('generic_selenium_test_results.json', 'w', encoding='utf-8') as f:
                json.dump(obituaries, f, indent=2)
            print(f"\n💾 Results saved to generic_selenium_test_results.json")
            
        else:
            print(f"\n❌ No obituaries found")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
