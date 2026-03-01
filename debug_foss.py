#!/usr/bin/env python3
"""
Debug script to see actual HTML content from Foss Funeral Home
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def debug_foss_website():
    """Debug the Foss Funeral Home website structure."""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    # Try different URL patterns
    urls_to_try = [
        "https://www.fossfuneralhome.com",
        "https://www.fossfuneralhome.com/obituaries",
        "https://www.fossfuneralhome.com/obituary-listings",
        "https://www.fossfuneralhome.com/current-obituaries"
    ]
    
    for url in urls_to_try:
        print(f"\n🔍 Checking: {url}")
        print("=" * 50)
        
        try:
            response = session.get(url, timeout=30)
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"Content Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for links that might be obituaries
                all_links = soup.find_all('a', href=True)
                obituary_links = []
                
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if any(word in href.lower() for word in ['obituary', 'memorial', 'tribute']):
                        obituary_links.append({
                            'href': href,
                            'text': text,
                            'full_url': urljoin(url, href)
                        })
                
                print(f"Found {len(obituary_links)} potential obituary links:")
                for i, link in enumerate(obituary_links[:10]):  # Show first 10
                    print(f"  {i+1}. {link['text'][:50]} -> {link['full_url']}")
                
                # Look for specific elements
                print(f"\nHTML structure analysis:")
                print(f"  - Total links: {len(all_links)}")
                print(f"  - Has .obit-listing: {len(soup.select('.obit-listing'))}")
                print(f"  - Has .obituary-item: {len(soup.select('.obituary-item'))}")
                print(f"  - Has .memorial-item: {len(soup.select('.memorial-item'))}")
                print(f"  - Has a[href*='/obituary/']: {len(soup.select('a[href*=\"/obituary/\"]'))}")
                
                # Show some sample HTML
                print(f"\nSample HTML (first 1000 chars):")
                print(response.text[:1000])
                
            else:
                print(f"❌ Failed to access: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_foss_website()
