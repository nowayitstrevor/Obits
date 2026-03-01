#!/usr/bin/env python3
"""
Debug Aderhold Funeral Home specifically.
"""

import requests
from bs4 import BeautifulSoup

def debug_aderhold():
    """Debug Aderhold Funeral Home."""
    
    url = "https://www.aderholdfuneralhome.com"
    
    print(f"🔍 DEBUGGING: Aderhold Funeral Home")
    print(f"🌐 URL: {url}")
    print("=" * 60)
    
    try:
        # Test basic connectivity
        print("1️⃣ Testing basic connectivity...")
        response = requests.get(url, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check for obituary-related links
            print("\n2️⃣ Looking for obituary-related content...")
            
            # Common obituary link patterns
            obituary_patterns = [
                'a[href*="obituary"]',
                'a[href*="obituaries"]', 
                'a[href*="memorial"]',
                'a[href*="tribute"]',
                'a[href*="remembrance"]'
            ]
            
            found_links = []
            for pattern in obituary_patterns:
                links = soup.select(pattern)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if href and text:
                        found_links.append((href, text, pattern))
            
            if found_links:
                print(f"   ✅ Found {len(found_links)} potential obituary links:")
                for href, text, pattern in found_links[:10]:  # Show first 10
                    print(f"      🔗 '{text}' → {href}")
                    print(f"          (matched by: {pattern})")
            else:
                print("   ❌ No obvious obituary links found")
            
            # Check page title and content for clues
            print(f"\n3️⃣ Page analysis:")
            title = soup.find('title')
            if title:
                print(f"   Title: {title.get_text(strip=True)}")
            
            # Look for navigation menus
            nav_elements = soup.select('nav, .nav, .menu, .navigation')
            if nav_elements:
                print(f"\n4️⃣ Navigation analysis:")
                for i, nav in enumerate(nav_elements[:3], 1):
                    nav_links = nav.find_all('a')
                    nav_texts = [a.get_text(strip=True) for a in nav_links if a.get_text(strip=True)]
                    print(f"   Nav {i}: {nav_texts[:8]}")  # First 8 nav items
                    
            # Check for any forms or search functionality
            print(f"\n5️⃣ Looking for forms/search:")
            forms = soup.find_all('form')
            if forms:
                for i, form in enumerate(forms[:3], 1):
                    action = form.get('action', 'No action')
                    method = form.get('method', 'GET')
                    print(f"   Form {i}: {method} → {action}")
            
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    debug_aderhold()
