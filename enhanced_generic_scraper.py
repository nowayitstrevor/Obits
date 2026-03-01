"""
Enhanced Generic Obituary Scraper with Site-Specific Configurations

This enhanced version allows for site-specific customization while maintaining
the generic framework. It addresses issues with false positives and provides
better filtering and validation.
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
import json
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
from urllib.parse import urljoin, urlparse

class EnhancedObituaryScraper:
    def __init__(self, config: Dict[str, Any]):
        """Initialize with site-specific configuration."""
        self.config = config
        self.base_url = config['url']
        self.funeral_home_name = config['name']
        self.storage_file = config.get('storage_file', f"obituaries_{self.get_safe_filename(self.funeral_home_name)}.json")
        
        # Site-specific configurations
        self.custom_selectors = config.get('custom_selectors', {})
        self.url_patterns = config.get('url_patterns', {})
        self.skip_patterns = config.get('skip_patterns', [])
        self.validation_rules = config.get('validation_rules', {})
        
        # Default skip patterns that apply to all sites
        self.default_skip_patterns = [
            '/send-flowers', '/flowers', '/sympathy', '/plant-tree',
            '/share', '/guestbook', '/guest-book', '/print', '/pdf',
            '/directions', '/contact', '/about', '/staff', '/services',
            'javascript:', 'mailto:', 'tel:', '#', 'facebook.com', 'twitter.com'
        ]
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def get_safe_filename(self, name: str) -> str:
        """Convert name to safe filename."""
        return re.sub(r'[^a-zA-Z0-9]', '', name.lower().replace(' ', ''))
    
    def setup_selenium_driver(self) -> webdriver.Firefox:
        """Setup Firefox WebDriver for JavaScript-heavy sites."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
        driver.implicitly_wait(10)
        
        return driver
    
    def should_skip_url(self, url: str, text: str = '') -> bool:
        """Determine if URL should be skipped based on patterns."""
        if not url:
            return True
            
        url_lower = url.lower()
        text_lower = text.lower() if text else ''
        
        # Check default skip patterns
        for pattern in self.default_skip_patterns:
            if pattern in url_lower:
                return True
        
        # Check site-specific skip patterns
        for pattern in self.skip_patterns:
            if pattern.lower() in url_lower:
                return True
        
        # Skip if text indicates non-obituary content
        skip_text_indicators = [
            'send flowers', 'plant tree', 'share memory', 'guest book',
            'directions', 'contact us', 'about us', 'staff'
        ]
        
        for indicator in skip_text_indicators:
            if indicator in text_lower:
                return True
        
        return False
    
    def is_valid_obituary_url(self, url: str) -> bool:
        """Validate if URL is likely an obituary page."""
        if not url:
            return False
        
        # Check for positive obituary indicators
        obituary_indicators = self.url_patterns.get('obituary_indicators', [
            '/obituary/', '/obituaries/', '/memorial/', '/tribute/',
            '/deceased/', '/obit/', '/listing/'
        ])
        
        url_lower = url.lower()
        
        # Must contain at least one obituary indicator
        if not any(indicator in url_lower for indicator in obituary_indicators):
            return False
        
        # Should not contain skip patterns
        if self.should_skip_url(url):
            return False
        
        return True
    
    def extract_obituary_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract obituary links using enhanced site-specific logic."""
        links = []
        
        # Try custom selectors first if provided
        if self.custom_selectors.get('obituary_list'):
            list_containers = soup.select(self.custom_selectors['obituary_list'])
            for container in list_containers:
                link_elements = container.find_all('a', href=True)
                for link_elem in link_elements:
                    href = link_elem.get('href')
                    text = link_elem.get_text().strip()
                    
                    if href and not self.should_skip_url(href, text):
                        # Convert relative to absolute URL
                        if href.startswith('/'):
                            href = urljoin(self.base_url, href)
                        elif not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        
                        if self.is_valid_obituary_url(href):
                            links.append(href)
        
        # Fallback to generic detection if custom selectors don't work
        if not links:
            links = self.generic_link_extraction(soup)
        
        # Remove duplicates while preserving order
        unique_links = []
        seen = set()
        for link in links:
            if link not in seen:
                unique_links.append(link)
                seen.add(link)
        
        return unique_links[:50]  # Limit to prevent overwhelming
    
    def generic_link_extraction(self, soup: BeautifulSoup) -> List[str]:
        """Generic link extraction as fallback."""
        links = []
        
        # Look for links with obituary-related keywords
        obituary_keywords = ['obituary', 'obit', 'memorial', 'tribute', 'view', 'read more']
        
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            # Skip if should be skipped
            if self.should_skip_url(href, text):
                continue
            
            # Check if link text contains obituary keywords
            if any(keyword in text for keyword in obituary_keywords):
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                elif not href.startswith('http'):
                    href = urljoin(self.base_url, href)
                
                if self.is_valid_obituary_url(href):
                    links.append(href)
            
            # Check if URL contains obituary indicators
            elif href and any(keyword in href.lower() for keyword in ['obituary', 'obit', 'memorial']):
                if href.startswith('/'):
                    href = urljoin(self.base_url, href)
                elif not href.startswith('http'):
                    href = urljoin(self.base_url, href)
                
                if self.is_valid_obituary_url(href):
                    links.append(href)
        
        return links
    
    def validate_obituary_content(self, obituary: Dict[str, Any]) -> bool:
        """Validate scraped obituary content using site-specific rules."""
        validation_rules = self.validation_rules
        
        # Check minimum content length
        min_length = validation_rules.get('min_content_length', 100)
        content = obituary.get('summary', '') or ''
        if len(content) < min_length:
            return False
        
        # Check for required elements
        required_elements = validation_rules.get('required_elements', [])
        for element in required_elements:
            if element == 'name' and not obituary.get('name'):
                return False
            elif element == 'dates_or_age' and not (obituary.get('birth_date') or obituary.get('death_date') or obituary.get('age')):
                return False
        
        # Check for forbidden content (indicates wrong page type)
        forbidden_content = validation_rules.get('forbidden_content', [
            'send flowers', 'plant tree', 'share memory', 'guest book',
            'contact us', 'about us', 'staff directory'
        ])
        
        for forbidden in forbidden_content:
            if forbidden.lower() in content.lower():
                return False
        
        return True
    
    def scrape_obituary_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape details from an individual obituary page with enhanced validation."""
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract basic information
            obituary = {
                'url': url,
                'funeral_home': self.funeral_home_name,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Extract name using custom selectors if available
            name = self.extract_name_enhanced(soup)
            if name:
                obituary['name'] = name
            
            # Extract dates
            dates = self.extract_dates_enhanced(soup)
            obituary.update(dates)
            
            # Extract photo
            photo_url = self.extract_photo_enhanced(soup, url)
            if photo_url:
                obituary['photo_url'] = photo_url
            
            # Extract summary/text
            summary = self.extract_summary_enhanced(soup)
            if summary:
                obituary['summary'] = summary
            
            # Validate the extracted content
            if not self.validate_obituary_content(obituary):
                print(f"    Content validation failed for {url}")
                return None
            
            return obituary
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def extract_name_enhanced(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract name using custom selectors and enhanced logic."""
        # Try custom selectors first
        if self.custom_selectors.get('name_selector'):
            elements = soup.select(self.custom_selectors['name_selector'])
            for element in elements:
                text = element.get_text().strip()
                if text and self.is_valid_name(text):
                    return self.clean_name(text)
        
        # Fallback to generic detection
        generic_selectors = ['h1', 'title', '.name', '.deceased-name', '.obituary-name']
        for selector in generic_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if text and self.is_valid_name(text):
                    return self.clean_name(text)
        
        return None
    
    def is_valid_name(self, text: str) -> bool:
        """Validate if text appears to be a person's name."""
        if not text or len(text) < 3 or len(text) > 100:
            return False
        
        # Should contain at least some letters
        if not any(c.isalpha() for c in text):
            return False
        
        # Should not contain common non-name indicators
        non_name_indicators = [
            'obituary', 'memorial', 'tribute', 'funeral', 'send flowers',
            'guest book', 'share', 'print', 'services', 'about'
        ]
        
        text_lower = text.lower()
        if any(indicator in text_lower for indicator in non_name_indicators):
            return False
        
        return True
    
    def clean_name(self, text: str) -> str:
        """Clean and format name text."""
        # Remove common prefixes/suffixes
        text = re.sub(r'^(obituary|memorial|tribute)\\s*[-:]?\\s*', '', text, flags=re.I)
        text = re.sub(r'\\s*[-:]?\\s*(obituary|memorial|tribute)$', '', text, flags=re.I)
        
        return text.strip()
    
    def extract_dates_enhanced(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced date extraction using custom selectors."""
        dates = {}
        
        # Try custom date container first
        if self.custom_selectors.get('date_container'):
            date_elements = soup.select(self.custom_selectors['date_container'])
            for element in date_elements:
                text = element.get_text()
                extracted_dates = self.parse_dates_from_text(text)
                if extracted_dates:
                    dates.update(extracted_dates)
                    break
        
        # Fallback to generic date extraction
        if not dates:
            dates = self.generic_date_extraction(soup)
        
        return dates
    
    def parse_dates_from_text(self, text: str) -> Dict[str, Any]:
        """Parse birth and death dates from text."""
        dates = {}
        
        # Common date patterns
        date_patterns = [
            r'(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4})',  # MM/DD/YYYY
            r'(\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}\\b)',
            r'(\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\.?\\s+\\d{1,2},?\\s+\\d{4}\\b)',
        ]
        
        # Look for date ranges
        range_patterns = [
            r'(\\d{4})\\s*[-–]\\s*(\\d{4})',  # 1950 - 2025
            r'([A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4})\\s*[-–]\\s*([A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4})',
        ]
        
        for pattern in range_patterns:
            matches = re.findall(pattern, text)
            if matches:
                match = matches[0]
                if len(match) == 2:
                    dates['birth_date'] = match[0].strip()
                    dates['death_date'] = match[1].strip()
                    break
        
        # If no range found, look for individual dates
        if not dates:
            all_dates = []
            for pattern in date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                all_dates.extend(matches)
            
            if all_dates:
                dates['death_date'] = all_dates[-1]
                if len(all_dates) > 1:
                    dates['birth_date'] = all_dates[0]
        
        return dates
    
    def generic_date_extraction(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Generic date extraction as fallback."""
        # This would contain the existing generic date extraction logic
        # from the original scraper
        return {}
    
    def extract_photo_enhanced(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Enhanced photo extraction."""
        # Try custom photo selector first
        if self.custom_selectors.get('photo_selector'):
            elements = soup.select(self.custom_selectors['photo_selector'])
            for element in elements:
                src = element.get('src')
                if src and self.is_valid_photo_url(src):
                    return self.make_absolute_url(src, base_url)
        
        # Fallback to generic photo detection
        generic_selectors = [
            'img[class*="photo"]',
            'img[class*="image"]', 
            'img[alt*="photo"]',
            '.photo img',
            '.image img'
        ]
        
        for selector in generic_selectors:
            elements = soup.select(selector)
            for element in elements:
                src = element.get('src')
                if src and self.is_valid_photo_url(src):
                    return self.make_absolute_url(src, base_url)
        
        return None
    
    def is_valid_photo_url(self, url: str) -> bool:
        """Check if URL is likely a valid photo."""
        if not url:
            return False
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if any(url.lower().endswith(ext) for ext in valid_extensions):
            return True
        
        image_keywords = ['photo', 'image', 'picture', 'pic', 'img']
        return any(keyword in url.lower() for keyword in image_keywords)
    
    def make_absolute_url(self, url: str, base_url: str) -> str:
        """Convert relative URL to absolute."""
        if url.startswith('/'):
            return urljoin(base_url, url)
        elif not url.startswith('http'):
            return urljoin(base_url, url)
        return url
    
    def extract_summary_enhanced(self, soup: BeautifulSoup) -> Optional[str]:
        """Enhanced summary extraction."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try custom content selectors
        if self.custom_selectors.get('content_selector'):
            elements = soup.select(self.custom_selectors['content_selector'])
            for element in elements:
                text = element.get_text().strip()
                if len(text) > 100:
                    return self.clean_summary_text(text)
        
        # Fallback to generic content detection
        content_selectors = [
            '.content', '.main-content', '.obituary-content',
            '.text', '.description', 'article', '.body'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text().strip()
                if len(text) > 100:
                    return self.clean_summary_text(text)
        
        return None
    
    def clean_summary_text(self, text: str) -> str:
        """Clean and format summary text."""
        # Replace multiple whitespace with single space
        text = re.sub(r'\\s+', ' ', text)
        
        # Truncate if too long
        if len(text) > 500:
            text = text[:500] + '...'
        
        return text
    
    def load_existing_data(self) -> Dict[str, Any]:
        """Load existing obituary data."""
        if not os.path.exists(self.storage_file):
            return {'obituaries': {}, 'last_updated': None}
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading existing data: {e}")
            return {'obituaries': {}, 'last_updated': None}
    
    def save_data(self, data: Dict[str, Any]) -> bool:
        """Save obituary data."""
        try:
            data['last_updated'] = datetime.now().isoformat()
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False
    
    def scrape_obituaries(self) -> Dict[str, Any]:
        """Main scraping method with enhanced validation."""
        print(f"Starting enhanced scrape of {self.funeral_home_name} ({self.base_url})")
        
        try:
            # Check if JavaScript is required
            requires_js = self.config.get('requires_javascript', False)
            
            if requires_js:
                print("Using Selenium for JavaScript-heavy site...")
                driver = self.setup_selenium_driver()
                try:
                    driver.get(self.base_url)
                    time.sleep(3)
                    html_content = driver.page_source
                finally:
                    driver.quit()
            else:
                response = self.session.get(self.base_url, timeout=30)
                if response.status_code != 200:
                    print(f"HTTP error: {response.status_code}")
                    return {'success': False, 'error': f'HTTP {response.status_code}'}
                html_content = response.text
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract obituary links
            obituary_links = self.extract_obituary_links(soup)
            print(f"Found {len(obituary_links)} potential obituary links")
            
            if not obituary_links:
                return {
                    'success': False,
                    'error': 'No obituary links found'
                }
            
            # Load existing data
            data = self.load_existing_data()
            new_count = 0
            skipped_count = 0
            
            # Scrape each obituary
            for i, link in enumerate(obituary_links):
                print(f"Scraping {i+1}/{len(obituary_links)}: {link}")
                
                # Generate ID from URL
                obituary_id = self.generate_obituary_id(link)
                
                # Check if already exists
                if obituary_id in data['obituaries']:
                    print(f"  Already exists, skipping...")
                    skipped_count += 1
                    continue
                
                # Scrape details with validation
                obituary_details = self.scrape_obituary_details(link)
                if obituary_details:
                    data['obituaries'][obituary_id] = obituary_details
                    new_count += 1
                    print(f"  ✓ Added: {obituary_details.get('name', 'Unknown')}")
                else:
                    print(f"  ✗ Failed validation or scraping")
                
                # Rate limiting
                time.sleep(1)
            
            # Save data
            if self.save_data(data):
                return {
                    'success': True,
                    'new_count': new_count,
                    'skipped_count': skipped_count,
                    'total_count': len(data['obituaries']),
                    'funeral_home': self.funeral_home_name
                }
            else:
                return {'success': False, 'error': 'Failed to save data'}
                
        except Exception as e:
            print(f"Error during scraping: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_obituary_id(self, url: str) -> str:
        """Generate a unique ID for an obituary from its URL."""
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        if path_parts:
            last_part = path_parts[-1]
            last_part = re.sub(r'\\.(html?|php|asp|jsp)$', '', last_part)
            return last_part
        
        # Fallback to hash of URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]

def main():
    """Main function to run the enhanced scraper."""
    if len(sys.argv) < 2:
        print("Usage: python enhanced_generic_scraper.py <config_file_or_funeral_home_id>")
        return
    
    config_input = sys.argv[1]
    
    # Load configuration
    if config_input.endswith('.json'):
        # Load from config file
        with open(config_input, 'r') as f:
            config = json.load(f)
    else:
        # Load from funeral_homes_config.json using funeral home ID
        with open('funeral_homes_config.json', 'r') as f:
            all_configs = json.load(f)
        
        if config_input not in all_configs['funeral_homes']:
            print(f"Funeral home '{config_input}' not found in configuration")
            return
        
        config = all_configs['funeral_homes'][config_input]
    
    scraper = EnhancedObituaryScraper(config)
    result = scraper.scrape_obituaries()
    
    if result['success']:
        print(f"\\nScraping completed successfully!")
        print(f"Funeral Home: {result['funeral_home']}")
        print(f"New obituaries: {result['new_count']}")
        print(f"Skipped (duplicates): {result.get('skipped_count', 0)}")
        print(f"Total obituaries: {result['total_count']}")
    else:
        print(f"\\nScraping failed: {result['error']}")

if __name__ == "__main__":
    main()
