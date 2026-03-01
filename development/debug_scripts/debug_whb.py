#!/usr/bin/env python3
"""
Debug WHB Family Funeral Home.
"""

import requests
from bs4 import BeautifulSoup

def debug_whb():
    """Debug WHB Family Funeral Home."""
    
    url = "https://www.whbfamily.com"
    
    print(f"🔍 DEBUGGING: WHB Family Funeral Home")
    print(f"🌐 URL: {url}")
    print("=" * 60)
    
    # Use proper headers since Aderhold needed them
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Test basic connectivity
        print("1️⃣ Testing basic connectivity...")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check page title
            title = soup.find('title')
            if title:
                print(f"   Title: {title.get_text(strip=True)}")
            
            # Check for obituary-related links
            print("\n2️⃣ Looking for obituary-related content...")
            
            obituary_links = soup.select('a[href*="obituar"], a[href*="memorial"], a[href*="tribute"]')
            if obituary_links:
                print(f"   ✅ Found {len(obituary_links)} obituary-related links:")
                for link in obituary_links[:5]:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    print(f"      🔗 '{text}' → {href}")
            else:
                print("   ❌ No obvious obituary links found")
            
            # Check navigation
            print(f"\n3️⃣ Navigation analysis:")
            nav_elements = soup.select('nav a, .nav a, .menu a, header a')
            nav_texts = []
            for nav_link in nav_elements[:15]:
                text = nav_link.get_text(strip=True)
                href = nav_link.get('href', '')
                if text and href:
                    nav_texts.append(f"'{text}' → {href}")
            
            if nav_texts:
                print("   Navigation links:")
                for nav_text in nav_texts:
                    print(f"      {nav_text}")
            
            # Test different potential obituary URLs
            print(f"\n4️⃣ Testing potential obituary URLs:")
            test_urls = [
                f"{url}/obituaries",
                f"{url}/obituary",
                f"{url}/memorials",
                f"{url}/tributes",
                f"{url}/current-obituaries"
            ]
            
            for test_url in test_urls:
                try:
                    test_response = requests.get(test_url, headers=headers, timeout=5)
                    if test_response.status_code == 200:
                        test_soup = BeautifulSoup(test_response.content, 'html.parser')
                        test_title = test_soup.find('title')
                        title_text = test_title.get_text(strip=True) if test_title else "No title"
                        print(f"   ✅ {test_url} → {test_response.status_code} | {title_text}")
                    else:
                        print(f"   ❌ {test_url} → {test_response.status_code}")
                except:
                    print(f"   ❌ {test_url} → Error")
            
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    debug_whb()
