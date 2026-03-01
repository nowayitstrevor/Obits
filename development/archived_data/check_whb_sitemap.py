#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Get the sitemap
response = requests.get("https://www.whbfamily.com/sitemap.xml", headers=headers)
print(f"Sitemap status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all URLs in the sitemap
    urls = soup.find_all('loc')
    obituary_urls = []
    
    for url_elem in urls:
        url = url_elem.get_text()
        # Look for obituary-related URLs
        if any(keyword in url.lower() for keyword in ['/obituary', '/memorial', '/tribute']):
            obituary_urls.append(url)
    
    print(f"\nFound {len(obituary_urls)} obituary-related URLs in sitemap:")
    for i, url in enumerate(obituary_urls[:10]):  # Show first 10
        print(f"{i+1}. {url}")
    
    # Test the first obituary URL if any were found
    if obituary_urls:
        test_url = obituary_urls[0]
        print(f"\nTesting first obituary URL: {test_url}")
        
        test_response = requests.get(test_url, headers=headers)
        print(f"Status: {test_response.status_code}")
        
        if test_response.status_code == 200:
            test_soup = BeautifulSoup(test_response.content, 'html.parser')
            title = test_soup.title.string if test_soup.title else "No title"
            print(f"Page title: {title}")
            
            # Look for name in various places
            name_found = False
            for selector in ['h1', '.deceased-name', '.obit-name', '.name']:
                elem = test_soup.select_one(selector)
                if elem and elem.get_text(strip=True):
                    print(f"Name (via {selector}): {elem.get_text(strip=True)}")
                    name_found = True
                    break
            
            if not name_found:
                print("Could not find name using common selectors")
                
else:
    print("Failed to fetch sitemap")
