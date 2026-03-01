#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Test Grace Gardens Funeral Home
url = "https://www.gracegardensfh.com"
print(f"Testing Grace Gardens Funeral Home: {url}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Test the main URL
response = requests.get(url, headers=headers)
print(f"Main page status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else "No title"
    print(f"Page title: {title}")
    
    # Look for obituary-related links
    obituary_links = []
    
    # Check all links for obituary-related URLs
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href')
        text = link.get_text(strip=True).lower()
        
        if href and (
            'obituar' in href.lower() or 
            'memorial' in href.lower() or
            'tribute' in href.lower() or
            'obituar' in text or
            'memorial' in text or
            'recent' in text
        ):
            full_url = urljoin(url, href)
            obituary_links.append({
                'url': full_url,
                'text': link.get_text(strip=True),
                'href': href
            })
    
    print(f"\nFound {len(obituary_links)} potential obituary links:")
    for i, link in enumerate(obituary_links):
        print(f"{i+1}. '{link['text']}' -> {link['url']}")
    
    # Test common obituary endpoints
    test_endpoints = [
        "/obituaries",
        "/obituary", 
        "/memorials",
        "/current-obituaries",
        "/recent-obituaries",
        "/tributes"
    ]
    
    print(f"\nTesting common obituary endpoints:")
    for endpoint in test_endpoints:
        test_url = urljoin(url, endpoint)
        try:
            test_response = requests.get(test_url, headers=headers)
            print(f"  {test_url} -> {test_response.status_code}")
            
            if test_response.status_code == 200:
                test_soup = BeautifulSoup(test_response.content, 'html.parser')
                test_title = test_soup.title.string if test_soup.title else "No title"
                print(f"    Title: {test_title}")
                
                # Look for obituary entries on this page
                obit_links = test_soup.find_all('a', href=True)
                individual_obits = []
                for olink in obit_links:
                    ohref = olink.get('href')
                    if ohref and '/obituary' in ohref.lower():
                        individual_obits.append(urljoin(test_url, ohref))
                
                if individual_obits:
                    print(f"    Found {len(individual_obits)} individual obituaries!")
                    
        except Exception as e:
            print(f"  {test_url} -> ERROR: {e}")
            
else:
    print(f"Failed to access main page: {response.status_code}")
