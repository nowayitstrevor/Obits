"""
Simple Selenium test to check if Chrome driver works.
"""

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    
    print("Testing Selenium Chrome setup...")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    print("1. Chrome options configured")
    
    # Try to get the driver
    print("2. Installing/finding ChromeDriver...")
    driver_path = ChromeDriverManager().install()
    print(f"   ChromeDriver path: {driver_path}")
    
    print("3. Starting Chrome browser...")
    driver = webdriver.Chrome(
        service=webdriver.chrome.service.Service(driver_path),
        options=chrome_options
    )
    print("   Chrome browser started successfully")
    
    # Test with a simple page first
    print("4. Testing with Google...")
    driver.get("https://www.google.com")
    print(f"   Page title: {driver.title}")
    print(f"   Page source length: {len(driver.page_source)}")
    
    # Now test with the obituary page
    print("5. Testing with obituary page...")
    url = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"
    driver.get(url)
    print(f"   Page title: {driver.title}")
    
    # Wait a bit for content to load
    print("6. Waiting for content to load...")
    time.sleep(5)
    
    page_source = driver.page_source
    print(f"   Page source length: {len(page_source)}")
    
    # Check for obituary content
    if "obituary" in page_source.lower():
        print("   ✓ Found 'obituary' text in page source")
    else:
        print("   ✗ No 'obituary' text found in page source")
    
    # Look for links
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_source, "html.parser")
    all_links = soup.find_all("a", href=True)
    print(f"   Found {len(all_links)} anchor tags")
    
    # Look for obituary-specific links
    obit_links = [a for a in all_links if a.get("href") and ("obituar" in a.get("href").lower() or "obId" in a.get("href"))]
    print(f"   Found {len(obit_links)} obituary-related links")
    
    for i, link in enumerate(obit_links[:5]):  # Show first 5
        href = link.get("href")
        text = link.get_text(strip=True)[:50]
        print(f"     {i+1}. {href} - '{text}'")
    
    # Save the selenium-rendered source
    with open("selenium_page_source.html", "w", encoding="utf-8") as f:
        f.write(page_source)
    print("   Saved Selenium page source to selenium_page_source.html")
    
    driver.quit()
    print("7. Test completed successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
