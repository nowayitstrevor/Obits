#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Test Waco Funeral Home Memorial Park
url = "https://www.wacofhmp.com/obituaries"
print(f"Testing Waco Funeral Home Memorial Park: {url}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Test the configured URL directly
response = requests.get(url, headers=headers)
print(f"Obituaries page status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else "No title"
    print(f"Page title: {title}")
    
    # Check for framework type
    if 'dmAPI' in response.text:
        print("⚠️  Uses dmAPI framework - requires API integration")
    elif 'tribute' in response.text.lower():
        print("⚠️  Uses Tribute Technology - requires API integration") 
    else:
        print("✅ Appears to use standard HTML")
        
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
        for i, link in enumerate(obituary_links[:5]):  # Show first 5
            print(f"{i+1}. '{link['text']}' -> {link['url']}")
        
        if obituary_links:
            # Test first obituary
            test_url = obituary_links[0]['url']
            print(f"\nTesting obituary page: {test_url}")
            
            test_response = requests.get(test_url, headers=headers)
            print(f"Obituary status: {test_response.status_code}")
            
            if test_response.status_code == 200:
                test_soup = BeautifulSoup(test_response.content, 'html.parser')
                test_title = test_soup.title.string if test_soup.title else "No title"
                print(f"Obituary title: {test_title}")
                
                # Try to find the name
                name_selectors = ['h1', '.deceased-name', '.obit-name', '.name', '.title', '.entry-title']
                for selector in name_selectors:
                    name_elem = test_soup.select_one(selector)
                    if name_elem and name_elem.get_text(strip=True):
                        print(f"Name found (via {selector}): {name_elem.get_text(strip=True)}")
                        break
            
            print(f"\n✅ Waco FHMP seems to be working with standard HTML!")
        else:
            print("\nNo individual obituary links found")
            # Save HTML for inspection
            with open('waco_fhmp_obituaries.html', 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            print("HTML saved to waco_fhmp_obituaries.html for inspection")

else:
    print(f"Failed to access obituaries page: {response.status_code}")
    
    # Try alternative URLs
    base_url = "https://www.wacofhmp.com"
    test_endpoints = [
        "/obituary", 
        "/memorials",
        "/current-obituaries",
        "/recent-obituaries",
        "/tributes",
        "/listings"
    ]
    
    print(f"\nTrying alternative endpoints on {base_url}:")
    for endpoint in test_endpoints:
        test_url = urljoin(base_url, endpoint)
        try:
            test_response = requests.get(test_url, headers=headers)
            print(f"  {test_url} -> {test_response.status_code}")
            
            if test_response.status_code == 200:
                test_soup = BeautifulSoup(test_response.content, 'html.parser')
                test_title = test_soup.title.string if test_soup.title else "No title"
                print(f"    Title: {test_title}")
                
        except Exception as e:
            print(f"  {test_url} -> ERROR: {e}")
