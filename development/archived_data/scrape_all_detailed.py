"""
Multi-site detailed obituary scraper that processes all configured funeral homes.

This script reads the funeral_homes_config.json and scrapes detailed obituaries
from all active funeral homes, combining the best features of the custom
and enhanced generic scrapers.
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
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuration file path
CONFIG_FILE = 'funeral_homes_config.json'
OUTPUT_FILE = 'obituaries_all_detailed.json'

def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'funeral_homes': {}}

def save_obituaries(obituaries: List[Dict[str, Any]], filename: str = OUTPUT_FILE):
    """Save obituaries to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(obituaries, f, indent=2, ensure_ascii=False)

def load_existing_obituaries(filename: str = OUTPUT_FILE) -> List[Dict[str, Any]]:
    """Load existing obituaries from JSON file."""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return []

def should_skip_url(url: str, skip_patterns: List[str]) -> bool:
    """Check if URL should be skipped based on skip patterns."""
    if not skip_patterns:
        return False
    
    for pattern in skip_patterns:
        if pattern in url.lower():
            return True
    return False

def setup_selenium_driver() -> webdriver.Chrome:
    """Set up Selenium Chrome driver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    return webdriver.Chrome(options=chrome_options)

def extract_text_safely(soup, selector: str, attribute: str = None) -> str:
    """Safely extract text from soup using CSS selector."""
    try:
        element = soup.select_one(selector)
        if element:
            if attribute:
                return element.get(attribute, '').strip()
            return element.get_text(strip=True)
    except Exception:
        pass
    return ''

def extract_dates_enhanced(soup, config: Dict[str, Any]) -> tuple:
    """Enhanced date extraction using custom selectors and patterns."""
    custom_selectors = config.get('custom_selectors', {})
    date_patterns = config.get('date_patterns', [])
    
    birth_date = ''
    death_date = ''
    
    # 1. Try specific birth/death date selectors first
    birth_selectors = custom_selectors.get('birth_date', ['.birth-date', '.born', '.date-birth', 'span.dob'])
    death_selectors = custom_selectors.get('death_date', ['.death-date', '.died', '.date-death', '.passed', 'span.dod'])
    
    # Extract birth date
    if isinstance(birth_selectors, str):
        birth_selectors = [birth_selectors]
    for selector in birth_selectors:
        birth_date = extract_text_safely(soup, selector)
        if birth_date:
            break
    
    # Extract death date
    if isinstance(death_selectors, str):
        death_selectors = [death_selectors]
    for selector in death_selectors:
        death_date = extract_text_safely(soup, selector)
        if death_date:
            break
    
    # 2. Try date container selectors
    if not birth_date or not death_date:
        date_container_selectors = custom_selectors.get('date_container', ['.dates', '.life-dates', '.obit-dates', 'p.lifespan'])
        if isinstance(date_container_selectors, str):
            date_container_selectors = [date_container_selectors]
            
        for selector in date_container_selectors:
            date_text = extract_text_safely(soup, selector)
            if date_text:
                # Try to parse combined date format
                extracted_birth, extracted_death = parse_combined_dates(date_text)
                if extracted_birth and not birth_date:
                    birth_date = extracted_birth
                if extracted_death and not death_date:
                    death_date = extracted_death
                if birth_date and death_date:
                    break
    
    # 3. Use regex patterns from config if available
    if date_patterns and (not birth_date or not death_date):
        full_text = soup.get_text()
        for pattern in date_patterns:
            try:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            match = ' '.join(match)
                        
                        # Try to determine if it's a birth or death date
                        if 'born' in pattern.lower() or 'birth' in pattern.lower():
                            if not birth_date:
                                birth_date = match.strip()
                        elif 'died' in pattern.lower() or 'death' in pattern.lower() or 'passed' in pattern.lower():
                            if not death_date:
                                death_date = match.strip()
                        else:
                            # Default to death date if unclear
                            if not death_date:
                                death_date = match.strip()
            except re.error:
                continue
    
    # 4. Final fallback - look for any date patterns in the text
    if not birth_date and not death_date:
        full_text = soup.get_text()
        # Look for common date patterns
        common_patterns = [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{4}\b',
            r'\b\d{4}-\d{1,2}-\d{1,2}\b'
        ]
        
        for pattern in common_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                # Assume the last date found is the death date
                death_date = matches[-1]
                if len(matches) > 1:
                    birth_date = matches[0]
                break
    
    return birth_date.strip(), death_date.strip()

def parse_combined_dates(date_text: str) -> tuple:
    """Parse combined birth/death date text."""
    birth_date = ''
    death_date = ''
    
    # Handle formats like "Born: Jan 1, 1950 - Died: Dec 31, 2020"
    if 'born' in date_text.lower() and ('died' in date_text.lower() or 'passed' in date_text.lower()):
        birth_match = re.search(r'born[:\s]*([^-–—]+)', date_text, re.IGNORECASE)
        death_match = re.search(r'(?:died|passed)[:\s]*([^,\n]+)', date_text, re.IGNORECASE)
        
        if birth_match:
            birth_date = birth_match.group(1).strip()
        if death_match:
            death_date = death_match.group(1).strip()
    
    # Handle formats like "Jan 1, 1950 - Dec 31, 2020"
    elif ' - ' in date_text or ' – ' in date_text or ' — ' in date_text:
        parts = re.split(r'\s*[-–—]\s*', date_text, 1)
        if len(parts) == 2:
            birth_date = parts[0].strip()
            death_date = parts[1].strip()
    
    # Handle age formats like "Age 70" or "70 years old"
    elif re.search(r'\b(?:age|years?)\s*:?\s*\d+', date_text, re.IGNORECASE):
        # For now, we'll just extract the death date if present
        date_match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', date_text)
        if date_match:
            death_date = date_match.group(0)
    
    return birth_date, death_date

def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ''
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove common artifacts
    text = re.sub(r'\s*\|\s*', ' | ', text)
    text = re.sub(r'\s*-\s*', ' - ', text)
    
    return text.strip()

def parse_date(date_text: str) -> str:
    """Parse various date formats into a standardized format."""
    if not date_text:
        return ''
    
    # Clean the date text
    date_text = re.sub(r'[^\w\s,.-]', '', date_text)
    date_text = ' '.join(date_text.split())
    
    # Common date patterns
    patterns = [
        r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # January 15, 2023 or January 15 2023
        r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',  # 01/15/2023 or 01-15-2023
        r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})',  # 2023/01/15 or 2023-01-15
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_text)
        if match:
            return date_text  # Return the original for now, could normalize later
    
    return date_text

def scrape_lakeshore_detailed(base_url: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Enhanced Lakeshore scraper based on scrape_real_obituaries.py."""
    obituaries = []
    driver = None
    
    try:
        driver = setup_selenium_driver()
        print(f"Scraping Lakeshore Funeral Home: {base_url}")
        
        driver.get(base_url)
        time.sleep(3)
        
        # Wait for obituaries to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".obituary-item, .obit-item, .listing-item"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find obituary links
        obituary_links = soup.find_all('a', href=True)
        valid_obituary_urls = set()
        
        for link in obituary_links:
            href = link.get('href', '').strip()
            if not href:
                continue
                
            full_url = urljoin(base_url, href)
            
            # Lakeshore-specific URL patterns
            if ('/obituary-listings/' in full_url or 
                '/obituaries/' in full_url) and full_url != base_url:
                valid_obituary_urls.add(full_url)
        
        print(f"Found {len(valid_obituary_urls)} obituary URLs for Lakeshore")
        
        # Scrape each obituary
        for i, url in enumerate(valid_obituary_urls, 1):
            try:
                print(f"Scraping obituary {i}/{len(valid_obituary_urls)}: {url}")
                
                driver.get(url)
                time.sleep(2)
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Extract obituary details using Lakeshore-specific selectors
                name = extract_text_safely(soup, 'h1, .obituary-title, .obit-name, .entry-title')
                
                # Try multiple selectors for dates
                birth_date = (extract_text_safely(soup, '.birth-date, .born, .birth') or
                            extract_text_safely(soup, '.dates') or '')
                
                death_date = (extract_text_safely(soup, '.death-date, .died, .death') or
                            extract_text_safely(soup, '.dates') or '')
                
                # If dates are combined, try to split them
                if birth_date and 'born' in birth_date.lower() and 'died' in birth_date.lower():
                    date_parts = birth_date.split()
                    born_idx = next((i for i, word in enumerate(date_parts) if 'born' in word.lower()), -1)
                    died_idx = next((i for i, word in enumerate(date_parts) if 'died' in word.lower()), -1)
                    
                    if born_idx >= 0 and died_idx >= 0:
                        birth_date = ' '.join(date_parts[born_idx+1:died_idx])
                        death_date = ' '.join(date_parts[died_idx+1:])
                
                obituary_text = extract_text_safely(soup, '.obituary-content, .obit-content, .entry-content, .content')
                
                # Extract services information
                services = extract_text_safely(soup, '.services, .service-info, .funeral-service')
                
                # Extract family information
                family = extract_text_safely(soup, '.family, .survivors, .surviving')
                
                if name:
                    obituary = {
                        'url': url,
                        'name': clean_text(name),
                        'birth_date': parse_date(birth_date),
                        'death_date': parse_date(death_date),
                        'obituary_text': clean_text(obituary_text),
                        'services': clean_text(services),
                        'family': clean_text(family),
                        'scraped_date': datetime.now().isoformat(),
                        'funeral_home': 'Lakeshore Funeral Home'
                    }
                    obituaries.append(obituary)
                    print(f"Successfully scraped: {name}")
                else:
                    print(f"Could not extract name from: {url}")
                
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue
                
    except Exception as e:
        print(f"Error scraping Lakeshore: {e}")
    finally:
        if driver:
            driver.quit()
    
    return obituaries

def scrape_generic_detailed(base_url: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Enhanced generic scraper for other funeral homes."""
    obituaries = []
    funeral_home_name = config.get('name', 'Unknown Funeral Home')
    
    try:
        print(f"Scraping {funeral_home_name}: {base_url}")
        
        # Get skip patterns from config
        skip_patterns = config.get('skip_patterns', [])
        
        # Make request with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        response = requests.get(base_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find obituary links using multiple strategies
        obituary_links = []
        
        # Strategy 1: Look for links with obituary-related keywords
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            text = link.get_text(strip=True).lower()
            
            if any(keyword in href.lower() or keyword in text for keyword in 
                   ['obituary', 'obituaries', 'obit', 'memorial', 'tribute']):
                full_url = urljoin(base_url, href)
                if not should_skip_url(full_url, skip_patterns):
                    obituary_links.append(full_url)
        
        # Strategy 2: Use custom selectors if provided
        custom_selectors = config.get('custom_selectors', {})
        if custom_selectors.get('obituary_links'):
            for selector in custom_selectors['obituary_links']:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    if href:
                        full_url = urljoin(base_url, href)
                        if not should_skip_url(full_url, skip_patterns):
                            obituary_links.append(full_url)
        
        # Remove duplicates
        valid_obituary_urls = list(set(obituary_links))
        print(f"Found {len(valid_obituary_urls)} potential obituary URLs for {funeral_home_name}")
        
        # Scrape each obituary
        for i, url in enumerate(valid_obituary_urls[:50], 1):  # Limit to 50 for safety
            try:
                print(f"Scraping obituary {i}/{min(len(valid_obituary_urls), 50)}: {url}")
                
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract obituary details using custom selectors if available
                name_selectors = custom_selectors.get('name', ['h1', '.obituary-title', '.obit-name', '.entry-title'])
                # Add site-specific selectors we discovered
                if not custom_selectors.get('name'):
                    name_selectors.extend(['.deceased-name', '.tribute-name', '.name', '.title'])
                
                name = ''
                for selector in name_selectors:
                    name = extract_text_safely(soup, selector)
                    if name:
                        break
                
                # Extract dates using enhanced extraction
                birth_date, death_date = extract_dates_enhanced(soup, config)
                
                # Extract content - try custom selectors first, then fallback to common ones
                content_selectors = custom_selectors.get('content', [])
                if not content_selectors:
                    # Default selectors + site-specific ones we discovered
                    content_selectors = [
                        '.obituary-content', '.obit-content', '.entry-content', '.content',
                        '.container-body',  # SLCTX specific
                        '[class*="body"]',  # SLCTX fallback  
                        '.obitV3-page',     # SLCTX page container
                        '.tribute-content', '.bio', '.biography', '.story',
                        'main', 'article', '.main-content'
                    ]
                
                obituary_text = ''
                for selector in content_selectors:
                    obituary_text = extract_text_safely(soup, selector)
                    if obituary_text and len(obituary_text) > 50:  # Must have substantial content
                        break
                
                # Validation rules
                validation_rules = config.get('validation_rules', {})
                min_name_length = validation_rules.get('min_name_length', 3)
                min_content_length = validation_rules.get('min_content_length', 50)
                
                if (name and len(name) >= min_name_length and 
                    obituary_text and len(obituary_text) >= min_content_length):
                    
                    obituary = {
                        'url': url,
                        'name': clean_text(name),
                        'birth_date': parse_date(birth_date),
                        'death_date': parse_date(death_date),
                        'obituary_text': clean_text(obituary_text),
                        'services': '',  # Could be enhanced
                        'family': '',    # Could be enhanced
                        'scraped_date': datetime.now().isoformat(),
                        'funeral_home': funeral_home_name
                    }
                    obituaries.append(obituary)
                    print(f"Successfully scraped: {name}")
                else:
                    print(f"Validation failed for: {url}")
                    print(f"  Name: '{name}' (length: {len(name) if name else 0}, min: {min_name_length})")
                    print(f"  Content length: {len(obituary_text) if obituary_text else 0} (min: {min_content_length})")
                    if obituary_text:
                        print(f"  Content preview: {obituary_text[:100]}...")
                    print(f"  Selectors tried for content: {content_selectors}")
                    print()
                
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue
                
    except Exception as e:
        print(f"Error scraping {funeral_home_name}: {e}")
    
    return obituaries

def main():
    """Main scraping function."""
    print("Starting detailed scraping for all funeral homes...")
    
    # Load configuration
    config = load_config()
    funeral_homes = config.get('funeral_homes', {})
    
    if not funeral_homes:
        print("No funeral homes found in configuration!")
        return
    
    print(f"Found {len(funeral_homes)} funeral homes in configuration")
    
    all_obituaries = []
    
    # Process each active funeral home
    for home_id, home_config in funeral_homes.items():
        print(f"Checking {home_config.get('name', home_id)}...")
        if not home_config.get('active', False):
            print(f"  -> SKIPPING: Inactive funeral home")
            continue
        
        print(f"  -> ACTIVE: Will process")
        
        base_url = home_config.get('url', '')
        if not base_url:
            print(f"No URL found for funeral home: {home_config.get('name', home_id)}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing: {home_config.get('name', home_id)}")
        print(f"URL: {base_url}")
        print(f"{'='*60}")
        
        try:
            # Use custom scraper for Lakeshore, enhanced generic for others
            if home_id.lower() == 'lakeshore':
                obituaries = scrape_lakeshore_detailed(base_url, home_config)
            else:
                obituaries = scrape_generic_detailed(base_url, home_config)
            
            print(f"Scraped {len(obituaries)} obituaries from {home_config.get('name', home_id)}")
            all_obituaries.extend(obituaries)
            
        except Exception as e:
            print(f"Error processing {home_config.get('name', home_id)}: {e}")
            continue
        
        # Short pause between funeral homes
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"Total obituaries scraped: {len(all_obituaries)}")
    print(f"{'='*60}")
    
    # Save all obituaries
    if all_obituaries:
        save_obituaries(all_obituaries)
        print(f"Obituaries saved to: {OUTPUT_FILE}")
        
        # Print summary by funeral home
        funeral_home_counts = {}
        for obit in all_obituaries:
            fh = obit.get('funeral_home', 'Unknown')
            funeral_home_counts[fh] = funeral_home_counts.get(fh, 0) + 1
        
        print("\nSummary by Funeral Home:")
        for fh, count in funeral_home_counts.items():
            print(f"  {fh}: {count} obituaries")
    else:
        print("No obituaries were scraped!")

if __name__ == "__main__":
    main()
