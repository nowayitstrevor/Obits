#!/usr/bin/env python3
"""
Test Aderhold with different request headers to bypass 403.
"""

import requests
from bs4 import BeautifulSoup

def test_aderhold_with_headers():
    """Test Aderhold with different headers."""
    
    url = "https://www.aderholdfuneralhome.com"
    
    headers_list = [
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        },
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    ]
    
    for i, headers in enumerate(headers_list, 1):
        print(f"\n🔍 Attempt {i} with headers:")
        print(f"   User-Agent: {headers.get('User-Agent', 'Not set')}")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.find('title')
                if title:
                    print(f"   ✅ Title: {title.get_text(strip=True)}")
                
                # Look for obituary links
                obituary_links = soup.select('a[href*="obituar"], a[href*="memorial"], a[href*="tribute"]')
                if obituary_links:
                    print(f"   ✅ Found {len(obituary_links)} obituary-related links")
                    for link in obituary_links[:3]:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        print(f"      → '{text}' - {href}")
                else:
                    print("   ❌ No obituary links found")
                    
                # Check navigation
                nav_text = []
                nav_elements = soup.select('nav a, .nav a, .menu a')
                for nav_link in nav_elements[:10]:
                    text = nav_link.get_text(strip=True)
                    if text:
                        nav_text.append(text)
                if nav_text:
                    print(f"   📋 Navigation: {', '.join(nav_text)}")
                
                break  # Success, stop trying
                
            elif response.status_code == 403:
                print(f"   ❌ Still getting 403 Forbidden")
            else:
                print(f"   ❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_aderhold_with_headers()
