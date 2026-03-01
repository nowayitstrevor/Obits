#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from bs4 import BeautifulSoup
import time

options = FirefoxOptions()
options.add_argument('--headless')
driver = webdriver.Firefox(options=options)

try:
    print('Testing WHB obituaries page directly...')
    driver.get('https://www.whbfamily.com/obituaries')
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    print(f'Title: {soup.title.string if soup.title else "No title"}')
    
    # Look for obituary links
    obit_links = soup.select('a[href*="obituary"]')
    print(f'Found {len(obit_links)} obituary links')
    
    for i, link in enumerate(obit_links[:5]):
        href = link.get('href', 'No href')
        text = link.get_text(strip=True)
        print(f'  {i+1}. {href} -> {text}')
        
    # Check for external redirects
    all_links = soup.select('a[href*="wichmann"]')
    print(f'Found {len(all_links)} Wichmann links (external redirects)')
    
    # Save debug HTML
    with open('whb_obituaries_debug.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print('Debug HTML saved to whb_obituaries_debug.html')
    
finally:
    driver.quit()
