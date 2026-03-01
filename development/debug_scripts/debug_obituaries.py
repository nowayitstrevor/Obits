"""
Debug version to analyze what's actually on the obituary page.
"""

import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"

def debug_page_content():
    """Debug what's actually on the page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    print(f"Fetching: {BASE_URL}")
    response = requests.get(BASE_URL, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)} characters")
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find ALL anchor tags
    all_anchors = soup.find_all("a", href=True)
    print(f"\nFound {len(all_anchors)} total anchor tags")
    
    # Show first 10 anchor tags
    print("\nFirst 10 anchor tags:")
    for i, anchor in enumerate(all_anchors[:10]):
        href = anchor.get("href")
        text = anchor.get_text(strip=True)[:50]
        print(f"{i+1:2d}. href='{href}' text='{text}'")
    
    # Look for any links containing "obituary" (case insensitive)
    obit_links = [a for a in all_anchors if a.get("href") and "obituar" in a.get("href").lower()]
    print(f"\nFound {len(obit_links)} links containing 'obituar':")
    for anchor in obit_links:
        href = anchor.get("href")
        text = anchor.get_text(strip=True)[:50]
        print(f"  href='{href}' text='{text}'")
    
    # Look for any links with obId parameter
    obid_links = [a for a in all_anchors if a.get("href") and "obId" in a.get("href")]
    print(f"\nFound {len(obid_links)} links with 'obId' parameter:")
    for anchor in obid_links:
        href = anchor.get("href")
        text = anchor.get_text(strip=True)[:50]
        print(f"  href='{href}' text='{text}'")
    
    # Look for any links with numeric IDs
    id_pattern = re.compile(r"id=\d+")
    id_links = [a for a in all_anchors if a.get("href") and id_pattern.search(a.get("href"))]
    print(f"\nFound {len(id_links)} links with numeric ID parameters:")
    for anchor in id_links:
        href = anchor.get("href")
        text = anchor.get_text(strip=True)[:50]
        print(f"  href='{href}' text='{text}'")
    
    # Check page title and main content
    title = soup.find("title")
    print(f"\nPage title: {title.get_text() if title else 'No title found'}")
    
    # Look for any divs or sections that might contain obituary content
    obituary_containers = soup.find_all(["div", "section", "article"], 
                                       string=re.compile(r"obituar", re.IGNORECASE))
    print(f"\nFound {len(obituary_containers)} containers with 'obituary' text")
    
    # Check if there are any script tags that might load content dynamically
    scripts = soup.find_all("script")
    print(f"\nFound {len(scripts)} script tags (indicating potential JavaScript content loading)")
    
    # Save the raw HTML for manual inspection
    with open("debug_page_source.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"\nSaved raw HTML to debug_page_source.html for manual inspection")

if __name__ == "__main__":
    debug_page_content()
