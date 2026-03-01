#!/usr/bin/env python3
"""
Debug a specific funeral home to understand why it's not populating obituaries.
"""

import requests
from bs4 import BeautifulSoup
import json

def debug_funeral_home(url: str, name: str):
    """Debug a specific funeral home website."""
    
    print(f"🔍 DEBUGGING: {name}")
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
            
        else:
            print(f"   ❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Test Lake Shore Funeral Home first
debug_funeral_home("https://www.lakeshorefuneralhome.com", "Lake Shore Funeral Home")
