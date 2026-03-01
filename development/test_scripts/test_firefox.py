"""
Selenium version using Firefox instead of Chrome.
"""

try:
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from webdriver_manager.firefox import GeckoDriverManager
    import time
    from bs4 import BeautifulSoup
    
    print("Testing Selenium with Firefox...")
    
    # Set up Firefox options
    firefox_options = Options()
    firefox_options.add_argument("--headless")
    
    print("1. Firefox options configured")
    
    # Try to get the driver
    print("2. Installing/finding GeckoDriver...")
    driver_path = GeckoDriverManager().install()
    print(f"   GeckoDriver path: {driver_path}")
    
    print("3. Starting Firefox browser...")
    driver = webdriver.Firefox(
        service=webdriver.firefox.service.Service(driver_path),
        options=firefox_options
    )
    print("   Firefox browser started successfully")
    
    # Test with the obituary page
    print("4. Loading obituary page...")
    url = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"
    driver.get(url)
    print(f"   Page title: {driver.title}")
    
    # Wait for content to load
    print("5. Waiting for JavaScript content to load...")
    time.sleep(10)  # Give more time for content to load
    
    page_source = driver.page_source
    print(f"   Page source length: {len(page_source)}")
    
    # Parse and look for obituary links
    soup = BeautifulSoup(page_source, "html.parser")
    all_links = soup.find_all("a", href=True)
    print(f"   Found {len(all_links)} anchor tags")
    
    # Look for obituary-specific links
    obit_links = []
    for link in all_links:
        href = link.get("href", "")
        if "obituar" in href.lower() or "obId" in href or "/obit" in href.lower():
            obit_links.append(link)
    
    print(f"   Found {len(obit_links)} potential obituary links")
    
    for i, link in enumerate(obit_links[:10]):  # Show first 10
        href = link.get("href")
        text = link.get_text(strip=True)[:50]
        print(f"     {i+1}. {href} - '{text}'")
    
    # Also search for any content that might contain names/dates
    # Look for common patterns in obituary text
    import re
    date_pattern = re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b|\b\w+ \d{1,2}, \d{4}\b')
    date_matches = date_pattern.findall(page_source)
    print(f"   Found {len(date_matches)} date patterns: {date_matches[:5]}")
    
    # Save the firefox-rendered source
    with open("firefox_page_source.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    print("   Saved Firefox page source to firefox_page_source.html")
    
    driver.quit()
    print("6. Test completed successfully!")
    
except Exception as e:
    print(f"Error with Firefox: {e}")
    print("\nFirefox also not available. You'll need to install either:")
    print("1. Google Chrome browser, OR")
    print("2. Mozilla Firefox browser")
    print("\nThen the Selenium-based scrapers will work.")
    