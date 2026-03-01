"""
Generic Obituary Scraper for Multiple Funeral Home Websites

This script provides a flexible framework for scraping obituaries from various
funeral home websites using different strategies based on the site structure.
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

class GenericObituaryScraper:
    def __init__(self, base_url: str, funeral_home_name: str = None):
        self.base_url = base_url
        self.funeral_home_name = funeral_home_name or self.extract_funeral_home_name(base_url)
        self.storage_file = f"obituaries_{self.get_safe_filename(self.funeral_home_name)}.json"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def extract_funeral_home_name(self, url: str) -> str:
        """Extract funeral home name from URL."""
        domain = urlparse(url).netloc.replace('www.', '')
        name = domain.split('.')[0]
        return name.replace('-', ' ').replace('_', ' ').title()
    
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
    
    def detect_site_structure(self, html_content: str) -> Dict[str, Any]:
        """Analyze site structure to determine scraping strategy."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        structure = {
            'has_obituary_list': False,
            'list_selectors': [],
            'pagination_present': False,
            'requires_javascript': False,
            'content_type': 'unknown'
        }
        
        # Common obituary list indicators
        obituary_indicators = [
            'obituary', 'obit', 'memorial', 'tribute', 'listing',
            'deceased', 'death', 'funeral', 'service'
        ]
        
        # Look for obituary list containers
        for indicator in obituary_indicators:
            # Check for class names containing indicator
            elements = soup.find_all(class_=re.compile(indicator, re.I))
            if elements:
                structure['has_obituary_list'] = True
                for elem in elements[:3]:  # Limit to first 3 matches
                    if elem.name in ['div', 'ul', 'ol', 'section', 'article']:
                        structure['list_selectors'].append(f".{' '.join(elem.get('class', []))}")
            
            # Check for ID containing indicator
            elements = soup.find_all(id=re.compile(indicator, re.I))
            if elements:
                structure['has_obituary_list'] = True
                for elem in elements[:3]:
                    structure['list_selectors'].append(f"#{elem.get('id')}")
        
        # Check for pagination
        pagination_indicators = ['page', 'next', 'prev', 'more', 'load']
        for indicator in pagination_indicators:
            if soup.find(class_=re.compile(indicator, re.I)) or soup.find(id=re.compile(indicator, re.I)):
                structure['pagination_present'] = True
                break
        
        # Check if JavaScript is required (minimal content or loading indicators)
        text_content = soup.get_text().strip()
        if len(text_content) < 500 or 'loading' in text_content.lower() or 'javascript' in text_content.lower():
            structure['requires_javascript'] = True
        
        # Determine content type
        if '/obituaries' in self.base_url or 'obituary' in text_content.lower():
            structure['content_type'] = 'obituaries'
        elif '/listings' in self.base_url or 'listing' in text_content.lower():
            structure['content_type'] = 'listings'
        elif 'memorial' in text_content.lower() or 'tribute' in text_content.lower():
            structure['content_type'] = 'memorials'
        
        return structure
    
    def extract_obituary_links(self, soup: BeautifulSoup, structure: Dict[str, Any]) -> List[str]:
        """Extract obituary links from the page."""
        links = []
        
        # Try different link extraction strategies
        strategies = [
            self.extract_links_by_selectors,
            self.extract_links_by_keywords,
            self.extract_links_by_structure
        ]
        
        for strategy in strategies:
            try:
                strategy_links = strategy(soup, structure)
                if strategy_links:
                    links.extend(strategy_links)
                    break  # Use first successful strategy
            except Exception as e:
                print(f"Strategy failed: {e}")
                continue
        
        # Clean and deduplicate links
        clean_links = []
        for link in links:
            if link and not link in clean_links:
                # Convert relative URLs to absolute
                if link.startswith('/'):
                    link = urljoin(self.base_url, link)
                elif not link.startswith('http'):
                    link = urljoin(self.base_url, link)
                clean_links.append(link)
        
        return clean_links[:50]  # Limit to first 50 obituaries
    
    def extract_links_by_selectors(self, soup: BeautifulSoup, structure: Dict[str, Any]) -> List[str]:
        """Extract links using detected selectors."""
        links = []
        
        for selector in structure.get('list_selectors', []):
            try:
                container = soup.select_one(selector)
                if container:
                    # Find all links within the container
                    link_elements = container.find_all('a', href=True)
                    for link_elem in link_elements:
                        href = link_elem.get('href')
                        if href and self.is_obituary_link(href, link_elem.get_text()):
                            links.append(href)
            except Exception as e:
                print(f"Selector {selector} failed: {e}")
                continue
        
        return links
    
    def extract_links_by_keywords(self, soup: BeautifulSoup, structure: Dict[str, Any]) -> List[str]:
        """Extract links by looking for obituary-related keywords."""
        links = []
        obituary_keywords = ['obituary', 'obit', 'memorial', 'tribute', 'view', 'read more']
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href')
            text = link.get_text().lower().strip()
            
            # Check if link text contains obituary keywords
            if any(keyword in text for keyword in obituary_keywords):
                if self.is_obituary_link(href, text):
                    links.append(href)
            
            # Check if URL contains obituary indicators
            elif href and any(keyword in href.lower() for keyword in ['obituary', 'obit', 'memorial']):
                if self.is_obituary_link(href, text):
                    links.append(href)
        
        return links
    
    def extract_links_by_structure(self, soup: BeautifulSoup, structure: Dict[str, Any]) -> List[str]:
        """Extract links by analyzing page structure."""
        links = []
        
        # Look for common structural patterns
        patterns = [
            {'tag': 'div', 'class': re.compile(r'card|item|entry|post', re.I)},
            {'tag': 'article'},
            {'tag': 'li', 'class': re.compile(r'obit|memorial|listing', re.I)},
        ]
        
        for pattern in patterns:
            elements = soup.find_all(**pattern)
            for elem in elements:
                # Find links within each element
                link = elem.find('a', href=True)
                if link:
                    href = link.get('href')
                    text = elem.get_text().strip()[:100]  # First 100 chars for context
                    
                    if self.is_obituary_link(href, text):
                        links.append(href)
        
        return links
    
    def is_obituary_link(self, href: str, text: str) -> bool:
        """Determine if a link is likely to be an obituary."""
        if not href:
            return False
        
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Skip obviously non-obituary links
        skip_indicators = [
            'contact', 'about', 'home', 'service', 'location', 'staff',
            'javascript:', 'mailto:', '#', 'tel:', 'ftp:'
        ]
        
        if any(indicator in href_lower for indicator in skip_indicators):
            return False
        
        # Positive indicators
        positive_indicators = [
            'obituary', 'obit', 'memorial', 'tribute', 'deceased',
            '/death/', '/listing/', '/view/', '/details/'
        ]
        
        # Check URL
        if any(indicator in href_lower for indicator in positive_indicators):
            return True
        
        # Check text content for names (basic heuristic)
        if text and len(text.split()) >= 2:  # At least two words (likely a name)
            # Look for common title patterns
            title_patterns = [
                r'\\b[A-Z][a-z]+ [A-Z][a-z]+\\b',  # First Last
                r'\\b[A-Z][a-z]+, [A-Z][a-z]+\\b',  # Last, First
            ]
            
            for pattern in title_patterns:
                if re.search(pattern, text):
                    return True
        
        return False
    
    def scrape_obituary_details(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape details from an individual obituary page."""
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
            
            # Extract name (usually in title or main heading)
            name = self.extract_name(soup)
            if name:
                obituary['name'] = name
            
            # Extract dates
            dates = self.extract_dates(soup)
            obituary.update(dates)
            
            # Extract photo
            photo_url = self.extract_photo(soup, url)
            if photo_url:
                obituary['photo_url'] = photo_url
            
            # Extract summary/text
            summary = self.extract_summary(soup)
            if summary:
                obituary['summary'] = summary
            
            return obituary
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the deceased person's name."""
        # Try different strategies
        strategies = [
            lambda: soup.find('h1'),
            lambda: soup.find('title'),
            lambda: soup.find(class_=re.compile(r'name|title|deceased', re.I)),
            lambda: soup.find(id=re.compile(r'name|title|deceased', re.I)),
        ]
        
        for strategy in strategies:
            try:
                element = strategy()
                if element:
                    text = element.get_text().strip()
                    # Clean up the text (remove common prefixes/suffixes)
                    text = re.sub(r'^(obituary|memorial|tribute)\\s*[-:]?\\s*', '', text, flags=re.I)
                    text = re.sub(r'\\s*[-:]?\\s*(obituary|memorial|tribute)$', '', text, flags=re.I)
                    
                    if text and len(text) < 100:  # Reasonable name length
                        return text
            except:
                continue
        
        return None
    
    def extract_dates(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract birth and death dates."""
        dates = {}
        
        # Common date patterns
        date_patterns = [
            r'(\\d{1,2}[/-]\\d{1,2}[/-]\\d{4})',  # MM/DD/YYYY or MM-DD-YYYY
            r'(\\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},?\\s+\\d{4}\\b)',
            r'(\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\.?\\s+\\d{1,2},?\\s+\\d{4}\\b)',
        ]
        
        # Get all text content
        text_content = soup.get_text()
        
        # Look for date ranges
        range_patterns = [
            r'(\\d{4})\\s*[-–]\\s*(\\d{4})',  # 1950 - 2025
            r'([A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4})\\s*[-–]\\s*([A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4})',
        ]
        
        for pattern in range_patterns:
            matches = re.findall(pattern, text_content)
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
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                all_dates.extend(matches)
            
            if all_dates:
                # Assume the last date is death date
                dates['death_date'] = all_dates[-1]
                if len(all_dates) > 1:
                    dates['birth_date'] = all_dates[0]
        
        # Calculate age if both dates available
        if dates.get('birth_date') and dates.get('death_date'):
            try:
                age = self.calculate_age(dates['birth_date'], dates['death_date'])
                if age:
                    dates['age'] = age
            except:
                pass
        
        return dates
    
    def calculate_age(self, birth_date: str, death_date: str) -> Optional[int]:
        """Calculate age from birth and death dates."""
        try:
            # Extract years from date strings
            birth_year = re.search(r'\\b(19|20)\\d{2}\\b', birth_date)
            death_year = re.search(r'\\b(19|20)\\d{2}\\b', death_date)
            
            if birth_year and death_year:
                return int(death_year.group()) - int(birth_year.group())
        except:
            pass
        
        return None
    
    def extract_photo(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract photo URL."""
        # Look for images in common locations
        selectors = [
            'img[class*="photo"]',
            'img[class*="image"]',
            'img[alt*="photo"]',
            'img[src*="photo"]',
            'img[src*="image"]',
            '.photo img',
            '.image img',
            '.picture img'
        ]
        
        for selector in selectors:
            try:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    src = img.get('src')
                    # Convert relative URL to absolute
                    if src.startswith('/'):
                        src = urljoin(base_url, src)
                    elif not src.startswith('http'):
                        src = urljoin(base_url, src)
                    
                    # Basic validation
                    if self.is_valid_photo_url(src):
                        return src
            except:
                continue
        
        return None
    
    def is_valid_photo_url(self, url: str) -> bool:
        """Check if URL is likely a valid photo."""
        if not url:
            return False
        
        # Check file extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if any(url.lower().endswith(ext) for ext in valid_extensions):
            return True
        
        # Check for image keywords in URL
        image_keywords = ['photo', 'image', 'picture', 'pic', 'img']
        return any(keyword in url.lower() for keyword in image_keywords)
    
    def extract_summary(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract obituary summary text."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Look for main content areas
        content_selectors = [
            '.content',
            '.main-content',
            '.obituary-content',
            '.text',
            '.description',
            'article',
            '.body'
        ]
        
        for selector in content_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    # Clean up the text
                    text = re.sub(r'\\s+', ' ', text)  # Replace multiple whitespace with single space
                    
                    if len(text) > 100:  # Substantial content
                        return text[:500] + ('...' if len(text) > 500 else '')
            except:
                continue
        
        # Fallback to body text
        body_text = soup.get_text().strip()
        if body_text:
            body_text = re.sub(r'\\s+', ' ', body_text)
            if len(body_text) > 100:
                return body_text[:500] + ('...' if len(body_text) > 500 else '')
        
        return None
    
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
        """Main scraping method."""
        print(f"Starting scrape of {self.funeral_home_name} ({self.base_url})")
        
        try:
            # First, try with requests
            response = self.session.get(self.base_url, timeout=30)
            if response.status_code != 200:
                print(f"HTTP error: {response.status_code}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
            
            html_content = response.text
            
            # Analyze site structure
            structure = self.detect_site_structure(html_content)
            print(f"Site structure: {structure}")
            
            # If JavaScript is required, use Selenium
            if structure['requires_javascript']:
                print("JavaScript required, switching to Selenium...")
                driver = self.setup_selenium_driver()
                try:
                    driver.get(self.base_url)
                    time.sleep(3)  # Wait for JavaScript to load
                    html_content = driver.page_source
                    structure = self.detect_site_structure(html_content)
                finally:
                    driver.quit()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract obituary links
            obituary_links = self.extract_obituary_links(soup, structure)
            print(f"Found {len(obituary_links)} potential obituary links")
            
            if not obituary_links:
                return {
                    'success': False,
                    'error': 'No obituary links found',
                    'structure': structure
                }
            
            # Load existing data
            data = self.load_existing_data()
            new_count = 0
            updated_count = 0
            
            # Scrape each obituary
            for i, link in enumerate(obituary_links):
                print(f"Scraping {i+1}/{len(obituary_links)}: {link}")
                
                # Generate ID from URL
                obituary_id = self.generate_obituary_id(link)
                
                # Check if already exists
                if obituary_id in data['obituaries']:
                    print(f"  Already exists, skipping...")
                    continue
                
                # Scrape details
                obituary_details = self.scrape_obituary_details(link)
                if obituary_details:
                    data['obituaries'][obituary_id] = obituary_details
                    new_count += 1
                    print(f"  Added: {obituary_details.get('name', 'Unknown')}")
                else:
                    print(f"  Failed to scrape details")
                
                # Rate limiting
                time.sleep(1)
            
            # Save data
            if self.save_data(data):
                return {
                    'success': True,
                    'new_count': new_count,
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
        # Extract meaningful parts from URL
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        if path_parts:
            # Use last meaningful part of path
            last_part = path_parts[-1]
            # Remove common file extensions
            last_part = re.sub(r'\\.(html?|php|asp|jsp)$', '', last_part)
            return last_part
        
        # Fallback to hash of URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]

def main():
    """Main function to run the scraper."""
    if len(sys.argv) < 2:
        print("Usage: python scrape_generic_obituaries.py <funeral_home_url>")
        print("Example: python scrape_generic_obituaries.py https://www.example-funeral-home.com")
        return
    
    funeral_home_url = sys.argv[1]
    
    scraper = GenericObituaryScraper(funeral_home_url)
    result = scraper.scrape_obituaries()
    
    if result['success']:
        print(f"\\nScraping completed successfully!")
        print(f"Funeral Home: {result['funeral_home']}")
        print(f"New obituaries: {result['new_count']}")
        print(f"Total obituaries: {result['total_count']}")
    else:
        print(f"\\nScraping failed: {result['error']}")

if __name__ == "__main__":
    main()
