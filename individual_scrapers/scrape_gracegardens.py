#!/usr/bin/env python3
"""
Individual Scraper for Grace Gardens
Focused scraper for https://www.gracegardenstx.com (Tukios platform)
"""

import json
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import re
from pathlib import Path
from urllib.parse import urljoin
import time

class GraceGardensScraper:
    def __init__(self):
        self.base_url = "https://www.gracegardenstx.com"
        self.funeral_home_name = "Grace Gardens"
        self.output_file = Path(__file__).parent.parent / "obituaries_gracegardens.json"
        
        self.obituaries = []
        self.driver = None

    def setup_selenium_driver(self):
        """Setup Firefox WebDriver with proper configuration."""
        
        print("🌐 Setting up Firefox WebDriver...")
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            self.driver = webdriver.Firefox(options=options)
            self.driver.set_page_load_timeout(30)
            
            # Set implicit wait
            self.driver.implicitly_wait(10)
            
            print("  ✅ Firefox WebDriver initialized")
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to initialize WebDriver: {e}")
            return False

    def find_obituary_listings(self):
        """Find all obituary listing pages on Tukios platform."""
        
        print(f"🔍 Finding obituary listings for {self.funeral_home_name}...")
        
        # Tukios sites typically have obituaries at /obituaries
        listing_url = urljoin(self.base_url, "/obituaries")
        
        try:
            self.driver.get(listing_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check if page loaded successfully
            if "obituaries" in self.driver.current_url.lower():
                print(f"  ✅ Found listing page: {listing_url}")
                return [listing_url]
            else:
                print(f"  ❌ Obituary listing page not found")
                return []
                
        except Exception as e:
            print(f"  ❌ Error accessing listing page: {e}")
            return []

    def extract_obituary_links(self, listing_url: str):
        """Extract individual obituary links from Tukios listing page."""
        
        print(f"🔗 Extracting obituary links from: {listing_url}")
        
        try:
            self.driver.get(listing_url)
            
            # Wait for obituary items to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".tukios--obituary-listing-item, .obituary-item, .obit-listing"))
            )
            
            # Tukios-specific selectors
            link_selectors = [
                ".tukios--obituary-listing-item a[href*='/obituaries/']",
                ".obituary-item a",
                ".obit-listing a",
                "a[href*='/obituary/']"
            ]
            
            obituary_links = set()
            
            for selector in link_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        href = element.get_attribute('href')
                        if href and self.is_obituary_link(href):
                            obituary_links.add(href)
                except NoSuchElementException:
                    continue
            
            print(f"  📄 Found {len(obituary_links)} obituary links")
            return list(obituary_links)
            
        except TimeoutException:
            print(f"  ⏰ Timeout waiting for obituary listings to load")
            return []
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
        obituary_indicators = ['/obituaries/', '/obituary/', '/memorial/', '/tribute/']
        return any(indicator in url.lower() for indicator in obituary_indicators)

    def scrape_obituary_details(self, obituary_url: str) -> dict:
        """Scrape details from individual obituary page."""
        
        try:
            self.driver.get(obituary_url)
            
            # Wait for page content to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extract name using Tukios-specific selectors
            name_selectors = [
                ".tukios--obituary-listing-name",
                "h1",
                ".deceased-name",
                ".obit-name",
                ".memorial-name"
            ]
            
            name = self.extract_text_by_selectors(name_selectors) or "Unknown"
            
            # Clean name (remove dates, pipes, etc.)
            name = name.split('|')[0].strip()
            name = re.sub(r'\d{4}\s*-\s*\d{4}', '', name).strip()
            
            # Extract dates
            birth_date = self.extract_birth_date()
            death_date = self.extract_death_date()
            
            # Calculate age
            age = self.calculate_age(birth_date, death_date)
            
            # Extract obituary text
            content_selectors = [
                ".tukios--obituary-content",
                ".obituary-text",
                ".obit-content",
                ".memorial-content",
                ".obituary-body"
            ]
            
            obituary_text = self.extract_text_by_selectors(content_selectors) or ""
            
            # Extract photo - Tukios sites often use CDN
            photo_selectors = [
                "img[src*='cdn.tukioswebsites.com']",
                ".tukios--obituary-photo img",
                ".obit-photo img",
                ".memorial-photo img",
                ".deceased-photo img"
            ]
            
            photo_url = self.extract_image_by_selectors(photo_selectors)
            
            # Extract service information
            services = self.extract_service_info()
            
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

    def extract_text_by_selectors(self, selectors: list) -> str:
        """Extract text using first matching selector."""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element:
                    return element.text.strip()
            except NoSuchElementException:
                continue
        return ""

    def extract_image_by_selectors(self, selectors: list) -> str:
        """Extract image URL using first matching selector."""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element:
                    src = element.get_attribute('src')
                    if src:
                        return src
            except NoSuchElementException:
                continue
        return ""

    def extract_birth_date(self) -> str:
        """Extract birth date from obituary page."""
        try:
            text = self.driver.find_element(By.TAG_NAME, "body").text
            
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
        except:
            pass
        
        return ""

    def extract_death_date(self) -> str:
        """Extract death date from obituary page."""
        try:
            text = self.driver.find_element(By.TAG_NAME, "body").text
            
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
        except:
            pass
        
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

    def extract_service_info(self) -> str:
        """Extract service/funeral information."""
        service_selectors = [
            ".tukios--service-info",
            ".service-info",
            ".funeral-info", 
            ".memorial-service",
            ".services"
        ]
        
        return self.extract_text_by_selectors(service_selectors)

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

    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            self.driver.quit()

    def run(self):
        """Main scraping process."""
        
        print(f"🚀 Starting scrape for {self.funeral_home_name}")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            # Setup Selenium WebDriver
            if not self.setup_selenium_driver():
                return
            
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
                
                # Rate limiting for politeness
                time.sleep(2)
            
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
        finally:
            self.cleanup()

if __name__ == "__main__":
    scraper = GraceGardensScraper()
    scraper.run()
