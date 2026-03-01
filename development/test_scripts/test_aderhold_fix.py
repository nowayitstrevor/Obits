#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup

# Test Aderhold with the custom headers we added
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

url = "https://www.aderholdfuneralhome.com/obituaries"
print(f"Testing Aderhold with custom headers: {url}")

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else "No title"
    print(f"Title: {title}")
    
    # Look for obituary links
    obituary_links = soup.select("a[href*='/obituary/']")
    print(f"Found {len(obituary_links)} obituary links")
    
    if obituary_links:
        for i, link in enumerate(obituary_links[:3]):
            print(f"  {i+1}. {link.get_text(strip=True)} -> {link.get('href')}")
        print("✅ Aderhold appears to be working!")
    else:
        print("❌ No obituary links found")
        # Check if it might be a dmAPI site too
        if 'dmAPI' in response.text:
            print("⚠️  Aderhold also uses dmAPI - may need Selenium")
else:
    print(f"❌ Failed to access Aderhold: {response.status_code}")
