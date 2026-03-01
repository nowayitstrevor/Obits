#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Test the Grace Gardens obituaries page
url = "https://www.gracegardensfh.com/obituaries"
print(f"Testing Grace Gardens obituaries page: {url}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else "No title"
    print(f"Title: {title}")
    
    # Save HTML for inspection
    with open('grace_gardens_obituaries.html', 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))
    print("HTML saved to grace_gardens_obituaries.html")
    
    # Look for individual obituary links
    all_links = soup.find_all('a', href=True)
    obituary_links = []
    
    for link in all_links:
        href = link.get('href')
        text = link.get_text(strip=True)
        
        if href and (
            '/obituary/' in href.lower() or
            '/memorial/' in href.lower() or
            '/tribute/' in href.lower()
        ):
            full_url = urljoin(url, href)
            obituary_links.append({
                'url': full_url,
                'text': text,
                'href': href
            })
    
    print(f"\nFound {len(obituary_links)} individual obituary links:")
    for i, link in enumerate(obituary_links[:10]):  # Show first 10
        print(f"{i+1}. '{link['text']}' -> {link['url']}")
    
    # Test one obituary if found
    if obituary_links:
        test_url = obituary_links[0]['url']
        print(f"\nTesting obituary page: {test_url}")
        
        test_response = requests.get(test_url, headers=headers)
        print(f"Obituary status: {test_response.status_code}")
        
        if test_response.status_code == 200:
            test_soup = BeautifulSoup(test_response.content, 'html.parser')
            test_title = test_soup.title.string if test_soup.title else "No title"
            print(f"Obituary title: {test_title}")
            
            # Try to find the name
            name_selectors = ['h1', '.deceased-name', '.obit-name', '.name', '.title']
            for selector in name_selectors:
                name_elem = test_soup.select_one(selector)
                if name_elem and name_elem.get_text(strip=True):
                    print(f"Name found (via {selector}): {name_elem.get_text(strip=True)}")
                    break
    else:
        print("\nNo individual obituary links found. Checking for JavaScript loading...")
        
        # Check for JavaScript that might load content
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and ('obituar' in script.string.lower() or 'api' in script.string.lower()):
                print("Found script with 'obituar' or 'api':")
                print(script.string[:200] + "..." if len(script.string) > 200 else script.string)
                
else:
    print("Failed to fetch obituaries page")
