#!/usr/bin/env python3
"""
Test individual Grace Gardens obituary parsing
"""

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from bs4 import BeautifulSoup
import time
from datetime import datetime
from urllib.parse import urlparse

def test_individual_obituary():
    """Test parsing a specific obituary from Grace Gardens."""
    
    print("🧪 Testing individual obituary parsing")
    print("=" * 50)
    
    # Setup Firefox
    options = FirefoxOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    
    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(30)
    
    try:
        # Test with the Vernon Hoppe obituary from the debug HTML
        url = "https://www.gracegardensfh.com/obituaries/vernon-hoppe"
        print(f"🌐 Loading: {url}")
        
        driver.get(url)
        time.sleep(5)  # Wait for JavaScript
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        print(f"📄 Title: {soup.title.string if soup.title else 'No title'}")
        
        details = {
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'funeral_home': 'Grace Gardens Funeral Home',
            'name': 'Unknown',
            'summary': None,
            'photo_url': None
        }
        
        # Extract name using Tukios-specific selectors
        name_selectors = [
            '.tukios--obituary-listing-name',
            'h1.tw-text-2xl', 
            'h3.tukios--obituary-listing-name.tw-text-2xl',
            'h1',
            'h2',
            'h3'
        ]
        
        for selector in name_selectors:
            try:
                name_elem = soup.select_one(selector.strip())
                if name_elem and name_elem.get_text(strip=True):
                    details['name'] = name_elem.get_text(strip=True)
                    print(f"      ✓ Name found with '{selector}': {details['name']}")
                    break
            except Exception as e:
                print(f"      ❌ Error with selector '{selector}': {e}")
                continue

        # Extract content/summary using Tukios selectors
        content_selectors = [
            '.tukios--obituary-listing-snippet',
            '.obituary-content',
            '.obit-content',
            'p',
            'div'
        ]
        
        for selector in content_selectors:
            try:
                content_elem = soup.select_one(selector.strip())
                if content_elem and content_elem.get_text(strip=True):
                    content_text = content_elem.get_text(strip=True)
                    if len(content_text) > 50:  # Substantial content
                        details['summary'] = content_text[:200] + "..." if len(content_text) > 200 else content_text
                        print(f"      ✓ Content found with '{selector}': {len(content_text)} chars")
                        break
            except Exception as e:
                print(f"      ❌ Error with selector '{selector}': {e}")
                continue

        # Extract photo using Tukios CDN pattern
        photo_selectors = [
            'img[src*="cdn.tukioswebsites.com"]',
            '.tukios--obituary-listing-image img',
            'img'
        ]
        
        for selector in photo_selectors:
            try:
                photo_elem = soup.select_one(selector.strip())
                if photo_elem and photo_elem.get('src'):
                    src = photo_elem.get('src')
                    if src.startswith('http'):
                        details['photo_url'] = src
                    elif src.startswith('/'):
                        base_url = f"https://{urlparse(url).netloc}"
                        details['photo_url'] = f"{base_url}{src}"
                    print(f"      ✓ Photo found with '{selector}': {details['photo_url']}")
                    break
            except Exception as e:
                print(f"      ❌ Error with selector '{selector}': {e}")
                continue
        
        print(f"\n📊 EXTRACTED DETAILS:")
        print(f"   Name: {details['name']}")
        print(f"   Summary: {details['summary'][:100]}..." if details['summary'] else "   Summary: None")
        print(f"   Photo: {details['photo_url']}" if details['photo_url'] else "   Photo: None")
        
        # Save debug HTML for this specific obituary
        with open('vernon_hoppe_debug.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"\n💾 Debug HTML saved to vernon_hoppe_debug.html")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_individual_obituary()
