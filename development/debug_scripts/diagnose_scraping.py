"""
Diagnostic script to test Lake Shore Funeral Home obituary scraping.
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
import time

def test_requests_approach():
    """Test basic requests approach."""
    print("🔍 Testing basic HTTP requests approach...")
    
    url = 'https://www.lakeshorefuneralhome.com/obituaries/obituary-listings'
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for various link patterns
        all_links = soup.find_all('a', href=True)
        obituary_links = []
        
        for link in all_links:
            href = link.get('href', '')
            if any(term in href.lower() for term in ['obituar', 'obit']):
                obituary_links.append(href)
        
        print(f"Found {len(obituary_links)} obituary-related links")
        for i, link in enumerate(obituary_links[:5], 1):
            print(f"  {i}. {link}")
        
        # Check for JavaScript indicators
        script_tags = soup.find_all('script')
        print(f"Found {len(script_tags)} script tags")
        
        # Look for common content management indicators
        if 'react' in response.text.lower():
            print("⚠️ React detected - likely needs JavaScript rendering")
        if 'angular' in response.text.lower():
            print("⚠️ Angular detected - likely needs JavaScript rendering")
        if 'vue' in response.text.lower():
            print("⚠️ Vue detected - likely needs JavaScript rendering")
            
        return len(obituary_links) > 0
        
    except Exception as e:
        print(f"❌ Error with requests: {e}")
        return False

def test_selenium_approach():
    """Test Selenium with Firefox approach."""
    print("\n🔍 Testing Selenium with Firefox approach...")
    
    url = 'https://www.lakeshorefuneralhome.com/obituaries/obituary-listings'
    
    # Configure Firefox options
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--disable-gpu")
    firefox_options.add_argument("--no-sandbox")
    
    driver = None
    try:
        print("Initializing Firefox driver...")
        driver = webdriver.Firefox(
            service=webdriver.firefox.service.Service(GeckoDriverManager().install()),
            options=firefox_options
        )
        
        print(f"Loading page: {url}")
        driver.get(url)
        
        # Wait for page to load
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Check page title and content
        print(f"Page title: {driver.title}")
        page_source = driver.page_source
        print(f"Page source length: {len(page_source)} characters")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Look for obituary links with various patterns
        obituary_patterns = [
            "//a[contains(@href, '/obituaries/obituary')]",
            "//a[contains(@href, '/obit')]",
            "//a[contains(@href, 'obId=')]",
            "//a[contains(@href, 'obituaryId=')]",
            "//a[contains(text(), 'obituary')]",
            "//a[contains(@class, 'obituary')]"
        ]
        
        total_links = 0
        for pattern in obituary_patterns:
            try:
                elements = driver.find_elements(By.XPATH, pattern)
                if elements:
                    print(f"Pattern '{pattern}' found {len(elements)} matches")
                    for i, elem in enumerate(elements[:3], 1):
                        href = elem.get_attribute('href')
                        text = elem.text.strip()[:50]
                        print(f"  {i}. {href} - '{text}'")
                    total_links += len(elements)
            except Exception as e:
                print(f"Pattern '{pattern}' failed: {e}")
        
        # Also check with BeautifulSoup
        soup_links = soup.find_all('a', href=True)
        soup_obituary_links = [
            link for link in soup_links 
            if any(term in str(link.get('href', '')).lower() for term in ['obituar', 'obit'])
        ]
        
        print(f"\nBeautifulSoup found {len(soup_obituary_links)} obituary links")
        
        # Look for any structured data
        if 'json-ld' in page_source:
            print("Found JSON-LD structured data")
        
        # Check for specific funeral home content
        if 'lake shore' in page_source.lower():
            print("✅ Lake Shore content detected")
        else:
            print("⚠️ Lake Shore content not clearly detected")
            
        return total_links > 0 or len(soup_obituary_links) > 0
        
    except Exception as e:
        print(f"❌ Error with Selenium: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()

def main():
    """Run diagnostic tests."""
    print("🏠 Lake Shore Funeral Home Obituary Scraper Diagnostics")
    print("=" * 60)
    
    requests_success = test_requests_approach()
    selenium_success = test_selenium_approach()
    
    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY:")
    print(f"Requests approach: {'✅ Success' if requests_success else '❌ Failed'}")
    print(f"Selenium approach: {'✅ Success' if selenium_success else '❌ Failed'}")
    
    if not (requests_success or selenium_success):
        print("\n💡 TROUBLESHOOTING SUGGESTIONS:")
        print("1. The website structure may have changed")
        print("2. The site may require authentication or specific headers")
        print("3. The obituary listing page may have moved")
        print("4. The site may be blocking automated access")
        print("5. Try accessing the site manually to verify it's working")

if __name__ == "__main__":
    main()
