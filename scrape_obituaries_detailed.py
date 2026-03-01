"""
Enhanced obituary scraper for Lake Shore Funeral Home that stores detailed information.

This version extracts and stores more detailed obituary information including
names, dates, and other details for use in the web UI.
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
from webdriver_manager.firefox import GeckoDriverManager

# Configuration
BASE_URL = 'https://www.lakeshorefuneralhome.com/obituaries/obituary-listings'
STORAGE_FILE = 'obituaries_detailed.json'

def extract_obituary_details(driver, obituary_url: str) -> Dict[str, Any]:
    """Extract detailed information from an individual obituary page."""
    try:
        print(f"  Extracting details from: {obituary_url}")
        driver.get(obituary_url)
        
        # Wait for the page to load
        time.sleep(2)
        
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
        
        # Try to extract name from various possible locations
        name_selectors = [
            'h1',
            '.obituary-name',
            '.obit-name',
            '[class*="name"]',
            'h2',
            'h3'
        ]
        
        for selector in name_selectors:
            name_element = soup.select_one(selector)
            if name_element and name_element.get_text().strip():
                text = name_element.get_text().strip()
                # Clean up common patterns
                if len(text) > 5 and len(text) < 100:  # Reasonable name length
                    details['name'] = text
                    break
        
        # Look for dates in the text
        page_text = soup.get_text()
        
        # Common date patterns
        date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'([A-Za-z]+ \d{1,2}, \d{4})',
            r'(\d{1,2} [A-Za-z]+ \d{4})'
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text)
            dates_found.extend(matches)
        
        if dates_found:
            # Try to identify birth and death dates
            # Usually death date is mentioned first or more prominently
            if len(dates_found) >= 2:
                details['death_date'] = dates_found[0]
                details['birth_date'] = dates_found[1]
            elif len(dates_found) == 1:
                details['death_date'] = dates_found[0]
        
        # Look for age
        age_match = re.search(r'age (\d+)', page_text, re.IGNORECASE)
        if age_match:
            details['age'] = int(age_match.group(1))
        
        # Extract a brief summary (first paragraph that's substantial)
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 50 and len(text) < 500:  # Reasonable summary length
                details['summary'] = text[:200] + ('...' if len(text) > 200 else '')
                break
        
        # Look for service information
        service_keywords = ['service', 'funeral', 'memorial', 'visitation', 'burial']
        for p in paragraphs:
            text = p.get_text().lower()
            if any(keyword in text for keyword in service_keywords):
                details['service_info'] = p.get_text().strip()[:300]
                break
        
        # Look for obituary photo
        photo_selectors = [
            'img[alt*="obituary"]',
            'img[alt*="photo"]',
            'img[src*="obituary"]',
            'img[src*="photo"]',
            '.obituary-photo img',
            '.obit-photo img',
            '.photo img',
            'img[class*="obituary"]',
            'img[class*="photo"]'
        ]
        
        for selector in photo_selectors:
            photo_element = soup.select_one(selector)
            if photo_element and photo_element.get('src'):
                src = photo_element.get('src')
                # Convert relative URLs to absolute
                if src.startswith('/'):
                    details['photo_url'] = f"https://www.lakeshorefuneralhome.com{src}"
                elif src.startswith('http'):
                    details['photo_url'] = src
                elif src:  # Relative path without leading slash
                    details['photo_url'] = urljoin(obituary_url, src)
                break
        
        # If no specific photo found, look for any img in the main content
        if not details['photo_url']:
            # Look for images that are likely to be obituary photos (reasonable size, not icons)
            all_images = soup.find_all('img')
            for img in all_images:
                src = img.get('src', '')
                alt = img.get('alt', '').lower()
                
                # Skip common non-photo images
                if any(skip in src.lower() for skip in ['icon', 'logo', 'banner', 'ad', 'social']):
                    continue
                if any(skip in alt for skip in ['icon', 'logo', 'banner', 'ad', 'social']):
                    continue
                
                # Look for images that might be photos
                if src and (
                    'jpg' in src.lower() or 'jpeg' in src.lower() or 
                    'png' in src.lower() or 'webp' in src.lower()
                ):
                    if src.startswith('/'):
                        details['photo_url'] = f"https://www.lakeshorefuneralhome.com{src}"
                    elif src.startswith('http'):
                        details['photo_url'] = src
                    elif src:
                        details['photo_url'] = urljoin(obituary_url, src)
                    break
        
        print(f"  ✓ Extracted: {details['name']}")
        return details
        
    except Exception as e:
        print(f"  ✗ Error extracting details from {obituary_url}: {e}")
        return {
            'url': obituary_url,
            'scraped_at': datetime.now().isoformat(),
            'name': f'Obituary (Error: {str(e)[:50]})',
            'error': str(e)
        }

def load_seen_obituaries() -> Dict[str, Any]:
    """Load the list of previously seen obituaries."""
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    return {
        'obituaries': {},
        'last_updated': None,
        'total_scraped': 0
    }

def save_obituaries(data: Dict[str, Any]):
    """Save the obituary data to the storage file."""
    data['last_updated'] = datetime.now().isoformat()
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_obituary_id(url: str) -> str:
    """Extract obituary ID from URL."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Try different parameter names that might contain the ID
    for param_name in ['obId', 'obituaryId', 'id']:
        if param_name in query_params:
            return query_params[param_name][0]
    
    # If no query parameters, try to extract from path
    path_parts = parsed.path.split('/')
    for part in reversed(path_parts):
        if part.isdigit():
            return part
    
    # Fallback: use the entire URL as ID (not ideal but works)
    return url

def scrape_obituaries_with_details() -> List[Dict[str, Any]]:
    """
    Scrape obituary listings from Lake Shore Funeral Home with detailed information.
    
    Returns:
        List of obituary dictionaries with detailed information
    """
    
    print(f"Starting detailed obituary scrape from: {BASE_URL}")
    
    # Configure Firefox options for headless browsing
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--window-size=1920,1080")
    
    driver = None
    try:
        # Initialize Firefox driver
        print("Initializing Firefox driver...")
        driver = webdriver.Firefox(
            service=webdriver.firefox.service.Service(GeckoDriverManager().install()),
            options=firefox_options
        )
        print("Firefox driver initialized successfully")
        
        # Navigate to the page
        print(f"Loading page: {BASE_URL}")
        driver.get(BASE_URL)
        print("Page loaded successfully")
        
        # Wait for the page to load and content to be populated
        wait = WebDriverWait(driver, 15)
        
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/obituaries/') or contains(@href, '/obit')]")))
            print("Obituary content detected, proceeding with parsing...")
        except TimeoutException:
            print("Timeout waiting for obituary content. Proceeding with current page state...")
        
        # Additional wait to ensure all dynamic content is loaded
        time.sleep(3)
        
        # Parse the loaded page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all obituary links
        obituary_links = []
        
        # Try multiple patterns to find obituary links
        patterns = [
            "//a[contains(@href, '/obituaries/obituary')]",
            "//a[contains(@href, '/obit')]",
            "//a[contains(@href, 'obId=')]",
            "//a[contains(@href, 'obituaryId=')]"
        ]
        
        for pattern in patterns:
            try:
                elements = driver.find_elements(By.XPATH, pattern)
                for element in elements:
                    href = element.get_attribute('href')
                    if href and href not in obituary_links:
                        obituary_links.append(href)
            except Exception as e:
                print(f"Error with pattern {pattern}: {e}")
                continue
        
        # Also check with BeautifulSoup as backup
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(BASE_URL, href)
            
            if ('/obituaries/' in href or '/obit' in href) and full_url not in obituary_links:
                obituary_links.append(full_url)
        
        print(f"Found {len(obituary_links)} obituary links")
        
        if not obituary_links:
            print("No obituary links found. The page structure may have changed.")
            return []
        
        # Load existing data
        data = load_seen_obituaries()
        new_obituaries = []
        
        # Process each obituary link
        for i, url in enumerate(obituary_links, 1):
            obituary_id = extract_obituary_id(url)
            print(f"Processing obituary {i}/{len(obituary_links)}: ID {obituary_id}")
            
            if obituary_id not in data['obituaries']:
                # This is a new obituary, extract details
                details = extract_obituary_details(driver, url)
                details['id'] = obituary_id
                details['funeral_home'] = 'Lake Shore Funeral Home'
                
                data['obituaries'][obituary_id] = details
                new_obituaries.append(details)
                
                # Small delay between requests to be respectful
                time.sleep(1)
            else:
                print(f"  Obituary {obituary_id} already seen, skipping details extraction")
        
        # Update statistics
        data['total_scraped'] = len(data['obituaries'])
        
        # Save updated data
        save_obituaries(data)
        
        print(f"\nScraping complete!")
        print(f"Total obituaries in database: {len(data['obituaries'])}")
        print(f"New obituaries found: {len(new_obituaries)}")
        
        if new_obituaries:
            print("\nNew obituaries:")
            for obit in new_obituaries:
                print(f"  - {obit['name']} (ID: {obit['id']})")
        
        return new_obituaries
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        raise
    finally:
        if driver:
            driver.quit()
            print("Firefox driver closed")

def main():
    """Main function to run the detailed obituary scraper."""
    try:
        new_obituaries = scrape_obituaries_with_details()
        
        if new_obituaries:
            print(f"\n🆕 Found {len(new_obituaries)} new obituaries!")
            for obituary in new_obituaries:
                print(f"   • {obituary['name']} (ID: {obituary['id']})")
        else:
            print("\n✅ No new obituaries found.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
