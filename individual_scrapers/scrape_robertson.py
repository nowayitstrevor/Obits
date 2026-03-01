#!/usr/bin/env python3
"""
Individual Scraper for Robertson Funeral Home
Focused scraper for https://www.robersonfuneralhome.com
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import time

class RobertsonFuneralHomeScraper:
    def __init__(self):
        self.base_url = "https://www.robertsonfh.com"
        self.funeral_home_name = "Robertson Funeral Home"
        self.output_file = Path(__file__).parent.parent / "obituaries_robersonfuneralhome.json"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        self.obituaries = []

    def find_obituary_listings(self):
        """Find all obituary listing pages."""
        
        print(f"🔍 Finding obituary listings for {self.funeral_home_name}...")
        
        # Common paths for obituary listings
        listing_paths = [
            "/obituaries",
            "/obituary-listings", 
            "/current-obituaries",
            "/recent-obituaries",
            "/memorials"
        ]
        
        found_listings = []
        
        for path in listing_paths:
            url = urljoin(self.base_url, path)
            try:
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    print(f"  ✅ Found listing page: {url}")
                    found_listings.append(url)
                    break  # Use first working listing page
            except Exception as e:
                print(f"  ❌ Failed to access {url}: {e}")
        
        if not found_listings:
            # Try homepage for obituary links
            print(f"  🔄 Checking homepage for obituary links...")
            found_listings = [self.base_url]
        
        return found_listings

    def extract_obituary_links(self, listing_url: str):
        """Extract individual obituary links from listing page."""
        
        print(f"🔗 Extracting obituary links from: {listing_url}")
        
        try:
            response = self.session.get(listing_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Common selectors for obituary links
            link_selectors = [
                "a[href*='/obituary/']",
                "a[href*='/memorial/']", 
                "a[href*='/tribute/']",
                ".obituary-link a",
                ".obit-listing a",
                ".memorial-listing a"
            ]
            
            obituary_links = set()
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.base_url, href)
                        # Filter out non-obituary links
                        if self.is_obituary_link(full_url):
                            obituary_links.add(full_url)
            
            print(f"  📄 Found {len(obituary_links)} obituary links")
            return list(obituary_links)
            
        except Exception as e:
            print(f"  ❌ Error extracting links: {e}")
            return []

    def is_obituary_link(self, url: str) -> bool:
        """Check if URL is likely an obituary page."""
        
        skip_patterns = [
            '/send-flowers',
            '/plant-tree',
            '/guestbook', 
            '/directions',
            '/share',
            '/print',
            'mailto:',
            '#',
            'javascript:'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False
        
        # Must contain obituary indicators
        obituary_indicators = ['/obituary/', '/memorial/', '/tribute/']
        return any(indicator in url.lower() for indicator in obituary_indicators)

    def scrape_obituary_details(self, obituary_url: str) -> dict:
        """Scrape details from individual obituary page."""
        
        try:
            response = self.session.get(obituary_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract name
            name_selectors = [
                'h1',
                '.deceased-name',
                '.obit-name',
                '.memorial-name',
                '.tribute-name'
            ]
            
            name = self.extract_text_by_selectors(soup, name_selectors) or "Unknown"
            
            # Clean name (remove dates, pipes, etc.)
            name = name.split('|')[0].strip()
            name = re.sub(r'\d{4}\s*-\s*\d{4}', '', name).strip()
            
            # Extract dates
            birth_date = self.extract_birth_date(soup)
            death_date = self.extract_death_date(soup)
            
            # Calculate age
            age = self.calculate_age(birth_date, death_date)
            
            # Extract obituary text
            content_selectors = [
                '.obit-content',
                '.obituary-text',
                '.memorial-content',
                '.tribute-text',
                '.obituary-body'
            ]
            
            obituary_text = self.extract_text_by_selectors(soup, content_selectors) or ""
            
            # Extract photo
            photo_selectors = [
                '.obit-photo img',
                '.memorial-photo img',
                '.deceased-photo img',
                '.tribute-photo img'
            ]
            
            photo_url = self.extract_image_by_selectors(soup, photo_selectors)
            
            # Extract service information
            services = self.extract_service_info(soup)
            
            obituary = {
                "url": obituary_url,
                "name": name,
                "birth_date": birth_date,
                "death_date": death_date,
                "age": age,
                "obituary_text": obituary_text,
                "photo_url": photo_url,
                "services": services,
                "scraped_date": datetime.now().isoformat(),
                "funeral_home": self.funeral_home_name
            }
            
            print(f"  ✅ Scraped: {name}")
            return obituary
            
        except Exception as e:
            print(f"  ❌ Error scraping {obituary_url}: {e}")
            return None

    def extract_text_by_selectors(self, soup: BeautifulSoup, selectors: list) -> str:
        """Extract text using first matching selector."""
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                return elements[0].get_text(strip=True)
        return ""

    def extract_image_by_selectors(self, soup: BeautifulSoup, selectors: list) -> str:
        """Extract image URL using first matching selector."""
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                src = elements[0].get('src')
                if src:
                    return urljoin(self.base_url, src)
        return ""

    def extract_birth_date(self, soup: BeautifulSoup) -> str:
        """Extract birth date from obituary page."""
        # Look for date patterns in text
        text = soup.get_text()
        
        # Common birth date patterns
        patterns = [
            r'born\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'birth\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})\s*-\s*\d{1,2}/\d{1,2}/\d{4}',
            r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*[-–—]\s*[A-Za-z]+\s+\d{1,2},?\s+\d{4}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""

    def extract_death_date(self, soup: BeautifulSoup) -> str:
        """Extract death date from obituary page."""
        text = soup.get_text()
        
        # Common death date patterns
        patterns = [
            r'died\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'passed\s+(?:away\s+)?(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'death\s*:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
            r'\d{1,2}/\d{1,2}/\d{4}\s*-\s*(\d{1,2}/\d{1,2}/\d{4})',
            r'[A-Za-z]+\s+\d{1,2},?\s+\d{4}\s*[-–—]\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""

    def calculate_age(self, birth_date: str, death_date: str) -> str:
        """Calculate age from birth and death dates."""
        if not birth_date or not death_date:
            return ""
        
        try:
            # Extract years
            birth_year = re.search(r'(\d{4})', birth_date)
            death_year = re.search(r'(\d{4})', death_date)
            
            if birth_year and death_year:
                age = int(death_year.group(1)) - int(birth_year.group(1))
                return str(age)
        except:
            pass
        
        return ""

    def extract_service_info(self, soup: BeautifulSoup) -> str:
        """Extract service/funeral information."""
        service_selectors = [
            '.service-info',
            '.funeral-info', 
            '.memorial-service',
            '.services'
        ]
        
        return self.extract_text_by_selectors(soup, service_selectors)

    def save_obituaries(self):
        """Save obituaries to JSON file."""
        
        # Structure for consistency with other funeral homes
        output_data = {
            "obituaries": {
                f"obituary_{i}": obituary 
                for i, obituary in enumerate(self.obituaries)
            }
        }
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved {len(self.obituaries)} obituaries to {self.output_file}")

    def run(self):
        """Main scraping process."""
        
        print(f"🚀 Starting scrape for {self.funeral_home_name}")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            # Find obituary listing pages
            listing_urls = self.find_obituary_listings()
            
            if not listing_urls:
                print(f"❌ No obituary listing pages found")
                return
            
            # Extract obituary links from listings
            all_obituary_links = []
            for listing_url in listing_urls:
                links = self.extract_obituary_links(listing_url)
                all_obituary_links.extend(links)
            
            # Remove duplicates
            unique_links = list(set(all_obituary_links))
            print(f"📄 Found {len(unique_links)} unique obituary pages")
            
            if not unique_links:
                print(f"❌ No obituary links found")
                return
            
            # Scrape each obituary
            for i, url in enumerate(unique_links):
                print(f"🔄 Scraping obituary {i+1}/{len(unique_links)}")
                
                obituary = self.scrape_obituary_details(url)
                if obituary:
                    self.obituaries.append(obituary)
                
                # Rate limiting
                time.sleep(1)
            
            # Save results
            if self.obituaries:
                self.save_obituaries()
            
            duration = time.time() - start_time
            print(f"✅ Completed in {duration:.1f} seconds")
            print(f"📊 Successfully scraped {len(self.obituaries)} obituaries")
            
        except Exception as e:
            print(f"💥 Error during scraping: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    scraper = RobertsonFuneralHomeScraper()
    scraper.run()
