#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup

# Get the page HTML to see the structure
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

response = requests.get("https://www.whbfamily.com/obituaries", headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all links that might be obituaries
    all_links = soup.find_all('a', href=True)
    obituary_links = []
    
    for link in all_links:
        href = link.get('href')
        text = link.get_text(strip=True)
        
        # Look for obituary-related links
        if href and any(keyword in href.lower() for keyword in ['/obituary', '/memorial', '/tribute']):
            obituary_links.append({
                'href': href,
                'text': text,
                'parent_class': link.parent.get('class') if link.parent else None
            })
    
    print(f"\nFound {len(obituary_links)} obituary-related links:")
    for i, link in enumerate(obituary_links[:10]):
        print(f"{i+1}. '{link['text']}' -> {link['href']}")
        if link['parent_class']:
            print(f"   Parent class: {link['parent_class']}")
    
    # Also check for any divs or sections that might contain obituary listings
    print("\n--- Looking for potential obituary containers ---")
    containers = soup.find_all(['div', 'section', 'article'], class_=True)
    for container in containers:
        class_name = ' '.join(container.get('class', []))
        if any(word in class_name.lower() for word in ['obit', 'memorial', 'tribute', 'listing']):
            print(f"Container found: {container.name} with class '{class_name}'")
            links_in_container = container.find_all('a', href=True)
            print(f"  Contains {len(links_in_container)} links")
            
else:
    print("Failed to fetch page")
