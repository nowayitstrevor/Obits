#!/usr/bin/env python3
"""
Test Lake Shore specific URLs and patterns.
"""

import requests
from bs4 import BeautifulSoup

def test_lakeshore_urls():
    """Test different Lake Shore URL patterns."""
    
    base_urls = [
        "https://www.lakeshorefuneralhome.com",
        "https://www.lakeshorefuneralhome.com/obituaries",
        "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings",
        "https://www.lakeshorefuneralhome.com/obituary-listings",
        "https://www.lakeshorefuneralhome.com/memorials",
        "https://www.lakeshorefuneralhome.com/current-obituaries"
    ]
    
    for url in base_urls:
        print(f"\n🔍 Testing: {url}")
        try:
            response = requests.get(url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find('title')
                if title:
                    print(f"   Title: {title.get_text(strip=True)}")
                
                # Look for any links containing obituary-related terms
                all_links = soup.find_all('a', href=True)
                obituary_links = []
                for link in all_links:
                    href = link.get('href', '').lower()
                    text = link.get_text(strip=True).lower()
                    if any(term in href or term in text for term in ['obituar', 'memorial', 'tribute', 'remembrance']):
                        obituary_links.append((link.get('href'), link.get_text(strip=True)))
                
                if obituary_links:
                    print(f"   Found {len(obituary_links)} potential links:")
                    for href, text in obituary_links[:5]:  # Show first 5
                        print(f"      → '{text}' - {href}")
                else:
                    print("   No obituary-related links found")
                    
        except Exception as e:
            print(f"   Error: {e}")

if __name__ == "__main__":
    test_lakeshore_urls()
