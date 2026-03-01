#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin

# Test WHB Family scraping with new config
funeral_homes_config = json.load(open('funeral_homes_config.json'))
whb_config = funeral_homes_config['funeral_homes']['whbfamily']

print(f"Testing: {whb_config['name']}")
print(f"URL: {whb_config['url']}")

# Use headers to avoid blocks
headers = whb_config.get('custom_headers', {})
selectors = whb_config.get('custom_selectors', {})

response = requests.get(whb_config['url'], headers=headers)
print(f"Status Code: {response.status_code}")
print(f"Page Title: {BeautifulSoup(response.content, 'html.parser').title.string if response.status_code == 200 else 'N/A'}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Look for obituary links using selectors
    obituary_links = []
    
    # Try different selectors for obituary links
    link_selectors = [
        selectors.get('obituary_link', ''),
        "a[href*='/obituary/']",
        "a[href*='/obituaries/']", 
        "a[href*='/memorial/']",
        ".obit-listing a",
        ".obituary-item a"
    ]
    
    for selector in link_selectors:
        if selector:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and not any(skip in href for skip in whb_config['skip_patterns']):
                    full_url = urljoin(whb_config['url'], href)
                    obituary_links.append({
                        'url': full_url,
                        'text': link.get_text(strip=True),
                        'found_by': selector
                    })
    
    print(f"\nFound {len(obituary_links)} potential obituary links:")
    for i, link in enumerate(obituary_links[:10]):  # Show first 10
        print(f"{i+1}. {link['text']} -> {link['url']} (via {link['found_by']})")
    
    # Test one obituary page if we found any
    if obituary_links:
        test_url = obituary_links[0]['url']
        print(f"\nTesting obituary page: {test_url}")
        
        test_response = requests.get(test_url, headers=headers)
        print(f"Obituary page status: {test_response.status_code}")
        
        if test_response.status_code == 200:
            test_soup = BeautifulSoup(test_response.content, 'html.parser')
            
            # Try to extract name
            name_selectors = [
                selectors.get('name_selector', ''),
                "h1",
                ".deceased-name",
                ".obit-name"
            ]
            
            for name_sel in name_selectors:
                if name_sel:
                    name_elem = test_soup.select_one(name_sel)
                    if name_elem:
                        print(f"Found name via '{name_sel}': {name_elem.get_text(strip=True)}")
                        break
                        
else:
    print("Failed to fetch page")
