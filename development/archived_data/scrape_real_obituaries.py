"""
Fixed obituary scraper for Lake Shore Funeral Home based on actual website analysis.

This version is specifically designed to work with the real lakeshorefuneralhome.com structure.
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
        
        # Get page text for debugging
        page_text = soup.get_text()
        print(f"    Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Extract name - try multiple approaches for Lake Shore website
        name_found = False
        
        # Method 1: Look for common name selectors
        name_selectors = [
            'h1',
            'h2', 
            '.obit-name',
            '.deceased-name',
            '.obituary-name',
            '.tribute-name',
            '[data-testid="deceased-name"]',
            '.entry-title'
        ]
        
        for selector in name_selectors:
            name_element = soup.select_one(selector)
            if name_element:
                text = name_element.get_text().strip()
                # Clean and validate the name
                if (5 <= len(text) <= 100 and 
                    not any(skip in text.lower() for skip in ['obituary', 'memorial', 'funeral', 'tribute']) and
                    any(c.isalpha() for c in text)):
                    details['name'] = text
                    name_found = True
                    print(f"    ✓ Name found via {selector}: {text}")
                    break
        
        # Method 2: If no name found, try extracting from URL or page structure
        if not name_found:
            # Try to extract from URL path (Lake Shore often uses name in URL)
            url_parts = obituary_url.split('/')
            for part in url_parts:
                if '-' in part and len(part) > 5:
                    # Convert URL slug to name (e.g., "John-Smith" -> "John Smith")
                    potential_name = part.replace('-', ' ').title()
                    if any(c.isalpha() for c in potential_name):
                        details['name'] = potential_name
                        name_found = True
                        print(f"    ✓ Name extracted from URL: {potential_name}")
                        break
        
        # Method 3: Try to find name in page text using patterns
        if not name_found:
            # Look for patterns like "In memory of [Name]" or similar
            name_patterns = [
                r'in memory of ([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'obituary for ([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*) obituary',
                r'([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\d{1,2}[/-]\d{1,2}[/-]\d{4}'
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()
                    if 5 <= len(potential_name) <= 100:
                        details['name'] = potential_name
                        name_found = True
                        print(f"    ✓ Name found via pattern: {potential_name}")
                        break
        
        # Enhanced date extraction for Lake Shore website
        print(f"    Looking for dates in page content...")
        
        # Look for structured date information first
        date_elements = soup.find_all(['time', 'span', 'div'], attrs={'class': re.compile(r'date|birth|death', re.I)})
        for elem in date_elements:
            date_text = elem.get_text().strip()
            if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}|\w+ \d{1,2}, \d{4}', date_text):
                print(f"    Found date element: {date_text}")
        
        # Enhanced date patterns specifically for funeral home websites
        date_patterns = [
            r'(\w+ \d{1,2}, \d{4})',  # "January 1, 2025"
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',  # "1/1/2025" or "1-1-2025"
            r'(\d{1,2} \w+ \d{4})',  # "1 January 2025"
            r'(\w+\s+\d{1,2},?\s+\d{4})'  # Flexible month day year
        ]
        
        all_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                clean_date = match.strip().replace(',', ', ')  # Normalize commas
                if clean_date not in all_dates:
                    all_dates.append(clean_date)
        
        print(f"    Found {len(all_dates)} potential dates: {all_dates[:5]}")
        
        # Try to categorize dates as birth/death using context
        birth_keywords = ['born', 'birth', 'b.', 'b:', 'entered this world']
        death_keywords = ['died', 'death', 'passed', 'went home', 'd.', 'd:', 'entered eternal rest', 'called home']
        
        for date in all_dates:
            # Find the context around this date
            date_index = page_text.lower().find(date.lower())
            if date_index > -1:
                # Get context (100 chars before and after)
                start = max(0, date_index - 100)
                end = min(len(page_text), date_index + len(date) + 100)
                context = page_text[start:end].lower()
                
                is_birth = any(keyword in context for keyword in birth_keywords)
                is_death = any(keyword in context for keyword in death_keywords)
                
                if is_birth and not details['birth_date']:
                    details['birth_date'] = date
                    print(f"    ✓ Birth date: {date}")
                elif is_death and not details['death_date']:
                    details['death_date'] = date
                    print(f"    ✓ Death date: {date}")
        
        # If we have dates but haven't categorized them, use heuristics
        if all_dates and (not details['birth_date'] or not details['death_date']):
            # Simple chronological sorting - just use the first two dates found
            if len(all_dates) >= 2:
                if not details['birth_date']:
                    details['birth_date'] = all_dates[0]
                    print(f"    ✓ Assumed birth date: {all_dates[0]}")
                if not details['death_date']:
                    details['death_date'] = all_dates[1]
                    print(f"    ✓ Assumed death date: {all_dates[1]}")
            elif len(all_dates) == 1:
                # Single date is usually death date
                if not details['death_date']:
                    details['death_date'] = all_dates[0]
                    print(f"    ✓ Single date (assumed death): {all_dates[0]}")
        
        # Extract age with better patterns and calculation
        age_patterns = [
            r'age (\d+)',
            r'aged (\d+)',
            r'(\d+) years old',
            r'(\d+) years of age',
            r'at the age of (\d+)',
            r'\b(\d{2,3})\b.*years'  # Two or three digit number followed by years
        ]
        
        # First try to find age in text
        for pattern in age_patterns:
            age_match = re.search(pattern, page_text, re.IGNORECASE)
            if age_match:
                age = int(age_match.group(1))
                if 0 <= age <= 120:  # Reasonable age range
                    details['age'] = age
                    print(f"    ✓ Age found in text: {age}")
                    break
        
        # If no age found in text, calculate from birth and death dates
        if not details['age'] and details['birth_date'] and details['death_date']:
            try:
                from datetime import datetime
                import re
                
                # Parse birth date
                birth_str = details['birth_date']
                death_str = details['death_date']
                
                # Clean up date strings
                birth_clean = re.sub(r'\s+', ' ', birth_str.strip())
                death_clean = re.sub(r'\s+', ' ', death_str.strip())
                
                # Try different date formats
                date_formats = [
                    '%B %d, %Y',      # "March 6, 1947"
                    '%b %d, %Y',      # "Mar 6, 1947"
                    '%m/%d/%Y',       # "3/6/1947"
                    '%m-%d-%Y',       # "3-6-1947"
                    '%Y-%m-%d'        # "1947-03-06"
                ]
                
                birth_date = None
                death_date = None
                
                # Parse birth date
                for fmt in date_formats:
                    try:
                        birth_date = datetime.strptime(birth_clean, fmt)
                        break
                    except ValueError:
                        continue
                
                # Parse death date
                for fmt in date_formats:
                    try:
                        death_date = datetime.strptime(death_clean, fmt)
                        break
                    except ValueError:
                        continue
                
                # Calculate age if both dates parsed
                if birth_date and death_date:
                    age = death_date.year - birth_date.year
                    
                    # Adjust if birthday hasn't occurred yet in death year
                    if (death_date.month, death_date.day) < (birth_date.month, birth_date.day):
                        age -= 1
                    
                    if 0 <= age <= 120:  # Sanity check
                        details['age'] = age
                        print(f"    ✓ Age calculated from dates: {age} ({birth_clean} to {death_clean})")
                    else:
                        print(f"    ⚠ Calculated age {age} seems unreasonable")
                else:
                    print(f"    ⚠ Could not parse dates for age calculation: birth='{birth_clean}', death='{death_clean}'")
                    
            except Exception as e:
                print(f"    ⚠ Error calculating age: {e}")
        
        # Extract biography/summary with better filtering
        print(f"    Looking for biography/summary...")
        
        # Try structured content first
        bio_selectors = [
            '.obituary-text',
            '.biography', 
            '.tribute-text',
            '.content-text',
            '.obit-content',
            'main p',
            '.entry-content p'
        ]
        
        for selector in bio_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                # Filter out non-biographical content
                if (100 <= len(text) <= 1000 and 
                    not any(skip in text.lower() for skip in [
                        'service will be', 'funeral home', 'visitation', 
                        'in lieu of flowers', 'memorial donations', 'guestbook'
                    ]) and
                    any(indicator in text.lower() for indicator in [
                        'born', 'lived', 'worked', 'family', 'survived', 
                        'preceded', 'beloved', 'devoted', 'loving'
                    ])):
                    details['summary'] = text[:400] + ('...' if len(text) > 400 else '')
                    print(f"    ✓ Summary found: {text[:50]}...")
                    break
            if details['summary']:
                break
        
        # Extract service information
        service_keywords = ['service', 'funeral', 'memorial', 'visitation', 'burial', 'celebration', 'mass']
        
        # Look for service information in structured elements
        service_selectors = [
            '.service-info',
            '.funeral-info',
            '.service-details',
            'p'
        ]
        
        for selector in service_selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text().strip()
                if (any(keyword in text.lower() for keyword in service_keywords) and 
                    len(text) > 30 and
                    any(indicator in text.lower() for indicator in [
                        'will be held', 'scheduled', 'at', 'pm', 'am', 'church', 'chapel'
                    ])):
                    details['service_info'] = text[:500] + ('...' if len(text) > 500 else '')
                    print(f"    ✓ Service info found: {text[:50]}...")
                    break
            if details['service_info']:
                break
        
        # Extract photo with Lake Shore specific pattern detection
        photo_found = False
        
        # Lake Shore uses a specific CloudFront pattern for obituary photos
        # Pattern: https://d1q40j6jx1d8h6.cloudfront.net/Obituaries/{obituary_id}/Thumbnail.webp
        obituary_id = extract_obituary_id(obituary_url)
        if obituary_id:
            potential_photo_url = f"https://d1q40j6jx1d8h6.cloudfront.net/Obituaries/{obituary_id}/Thumbnail.webp"
            print(f"    Testing Lake Shore photo pattern: {potential_photo_url}")
            
            # Test if this photo URL exists by making a quick HEAD request
            try:
                import requests
                response = requests.head(potential_photo_url, timeout=5)
                if response.status_code == 200:
                    details['photo_url'] = potential_photo_url
                    photo_found = True
                    print(f"    ✓ Found Lake Shore photo: {potential_photo_url}")
                else:
                    print(f"    ⚠ Lake Shore photo not found (HTTP {response.status_code})")
            except Exception as e:
                print(f"    ⚠ Error checking Lake Shore photo: {e}")
        
        # If Lake Shore pattern didn't work, try finding photos in the page
        if not photo_found:
            photo_selectors = [
                'img[alt*="obituary"]',
                'img[alt*="memorial"]',
                'img[src*="obituary"]',
                'img[src*="memorial"]',
                'img[src*="tribute"]',
                '.obituary-photo img',
                '.memorial-photo img',
                '.deceased-photo img',
                'main img',
                'img'
            ]
            
            # Common placeholder image patterns to skip
            placeholder_patterns = [
                'tree100x100',
                'spin_wh.svg',
                'obituaryimage_big.webp',
                'cross/obituaryimage',
                'religious/cross',
                'themes/religious',
                'default_obituary',
                'placeholder',
                'no-photo',
                'logo',
                'icon',
                'banner', 
                'flower',
                'candle',
                'background',
                'decoration',
                'loading',
                'spinner',
                'userway.org',
                'cloudfront.net/Shared/images',
                'cloudfront.net/themes',
                'indoor-garden',
                'basket',
                'arrangement',
                'bouquet',
                'thumbs/',
                'products/',
                'catalog/',
                'shop/',
                'store/'
            ]
            
            for selector in photo_selectors:
                img_elements = soup.select(selector)
                for img in img_elements:
                    src = img.get('src', '')
                    alt = img.get('alt', '').lower()
                    
                    # Skip empty or very short URLs
                    if not src or len(src) < 10:
                        continue
                    
                    # Check if this is a placeholder image
                    is_placeholder = False
                    for pattern in placeholder_patterns:
                        if pattern.lower() in src.lower() or pattern.lower() in alt:
                            is_placeholder = True
                            print(f"    ⚠ Skipping placeholder image: {src}")
                            break
                    
                    if is_placeholder:
                        continue
                    
                    # Look for real obituary photos - they usually have specific patterns
                    real_photo_indicators = [
                        '/uploads/',
                        '/photos/',
                        '/images/obituaries/',
                        '/obituary-photos/',
                        '/memorial-photos/',
                        '/portraits/',
                        '/headshots/',
                        'portrait',
                        'headshot',
                        'obituary',
                        'memorial',
                        'cloudfront.net/obituaries',  # Lake Shore specific
                        '/thumbnail.webp',
                        '.jpg',
                        '.jpeg',
                        '.png'
                    ]
                    
                    # Check if this looks like a real photo
                    has_photo_indicator = any(indicator in src.lower() for indicator in real_photo_indicators)
                    
                    # Additional checks: the URL should contain the person's name or be in a personal photo directory
                    person_name_parts = details['name'].lower().split() if details['name'] != 'Unknown' else []
                    has_name_in_url = any(part in src.lower() for part in person_name_parts if len(part) > 2)
                    
                    # Check image dimensions or other attributes that suggest it's a real photo
                    width = img.get('width', '')
                    height = img.get('height', '')
                    
                    # Real photos usually have reasonable dimensions
                    is_reasonable_size = True
                    try:
                        if width and height:
                            w, h = int(width), int(height)
                            # Skip very small images (likely icons) or very large banners
                            if w < 80 or h < 80 or w > 600 or h > 600:
                                is_reasonable_size = False
                    except:
                        pass
                    
                    # More strict criteria for accepting as a real photo
                    photo_score = 0
                    if has_photo_indicator:
                        photo_score += 1
                    if has_name_in_url:
                        photo_score += 2  # Higher weight for name in URL
                    if is_reasonable_size:
                        photo_score += 1
                    if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png']):
                        photo_score += 1
                    
                    # Only accept if we have good confidence it's a real photo
                    if photo_score >= 2:
                        if src.startswith('/'):
                            details['photo_url'] = f"https://www.lakeshorefuneralhome.com{src}"
                        elif src.startswith('http'):
                            details['photo_url'] = src
                        else:
                            details['photo_url'] = urljoin(obituary_url, src)
                        
                        print(f"    ✓ Real photo found: {details['photo_url']}")
                        photo_found = True
                        break
                if photo_found:
                    break
        
        # If no real photo found, set to None instead of placeholder
        if not photo_found:
            details['photo_url'] = None
            print(f"    ⚠ No real obituary photo found")
        
        print(f"  ✓ Extraction complete: {details['name']} ({details.get('birth_date', '?')} - {details.get('death_date', '?')})")
        return details
        
    except Exception as e:
        print(f"  ✗ Error extracting details from {obituary_url}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'url': obituary_url,
            'scraped_at': datetime.now().isoformat(),
            'name': f'Error extracting obituary',
            'error': str(e)
        }

def scrape_obituaries_with_details() -> List[Dict[str, Any]]:
    """
    Scrape obituary listings from Lake Shore Funeral Home with detailed information.
    """
    
    print(f"Starting real obituary scrape from: {BASE_URL}")
    
    # Configure Firefox options
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.add_argument("--window-size=1920,1080")
    firefox_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
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
        
        # Wait for the page to load completely
        print("Waiting for page content to load...")
        time.sleep(5)
        
        # Parse the loaded page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        print(f"Page loaded. Content length: {len(driver.page_source)} characters")
        
        # Find obituary links using the patterns we saw in the webpage
        obituary_links = []
        
        # Look for links with obId parameter (this is what we saw in the real data)
        all_links = driver.find_elements(By.TAG_NAME, "a")
        
        for link_element in all_links:
            try:
                href = link_element.get_attribute('href')
                if href and 'obId=' in href:
                    obituary_links.append(href)
                    print(f"Found obituary link: {href}")
            except:
                continue
        
        # Also try with BeautifulSoup
        soup_links = soup.find_all('a', href=True)
        for link in soup_links:
            href = link.get('href')
            if href and 'obId=' in href:
                full_url = urljoin(BASE_URL, href)
                if full_url not in obituary_links:
                    obituary_links.append(full_url)
                    print(f"Found obituary link (soup): {full_url}")
        
        print(f"Total obituary links found: {len(obituary_links)}")
        
        if not obituary_links:
            print("❌ No obituary links found!")
            print("Page title:", driver.title)
            print("Searching for any links containing 'obituar'...")
            
            # Debug: look for any obituary-related content
            page_text = driver.page_source.lower()
            if 'obituar' in page_text:
                print("✓ Found 'obituar' text in page")
            else:
                print("✗ No 'obituar' text found in page")
            
            # Try to find the actual link pattern
            all_hrefs = [elem.get_attribute('href') for elem in all_links if elem.get_attribute('href')]
            print(f"Sample hrefs found: {all_hrefs[:10]}")
            
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
                
                # Small delay between requests
                time.sleep(2)
            else:
                print(f"  Obituary {obituary_id} already seen, skipping details extraction")
        
        # Update statistics
        data['total_scraped'] = len(data['obituaries'])
        
        # Save updated data
        save_obituaries(data)
        
        print(f"\n✅ Scraping complete!")
        print(f"Total obituaries in database: {len(data['obituaries'])}")
        print(f"New obituaries found: {len(new_obituaries)}")
        
        if new_obituaries:
            print("\nNew obituaries:")
            for obit in new_obituaries:
                print(f"  - {obit['name']} (ID: {obit['id']})")
        
        return new_obituaries
        
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if driver:
            driver.quit()
            print("Firefox driver closed")

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
    
    # Try obId first (this is what Lake Shore uses)
    if 'obId' in query_params:
        return query_params['obId'][0]
    
    # Try other parameter names
    for param_name in ['obituaryId', 'id']:
        if param_name in query_params:
            return query_params[param_name][0]
    
    # Fallback: try to extract from path
    path_parts = parsed.path.split('/')
    for part in reversed(path_parts):
        if part.isdigit():
            return part
    
    # Last resort: use a hash of the URL
    return str(hash(url))[-8:]

def main():
    """Main function to run the fixed obituary scraper."""
    try:
        new_obituaries = scrape_obituaries_with_details()
        
        if new_obituaries:
            print(f"\n🆕 Found {len(new_obituaries)} new obituaries!")
            for obituary in new_obituaries:
                print(f"   • {obituary['name']} (ID: {obituary['id']})")
        else:
            print("\n✅ No new obituaries found (or scraping failed).")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
