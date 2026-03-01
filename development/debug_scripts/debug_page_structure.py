#!/usr/bin/env python3
"""
Debug script to examine the actual HTML structure of problematic pages.
"""

import requests
from bs4 import BeautifulSoup

def debug_page_structure(url: str, funeral_home: str):
    """Debug the HTML structure of a page to understand date extraction issues."""
    print(f"\n{'='*60}")
    print(f"DEBUGGING: {funeral_home}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract and show the full text
            full_text = soup.get_text()
            
            # Show name/title section
            title = soup.find('h1')
            if title:
                print(f"Title (H1): {title.get_text(strip=True)}")
            
            # Look for any elements containing dates
            import re
            date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{1,2}/\d{4}|\d{4})\b'
            
            # Find all elements that contain potential dates
            elements_with_dates = soup.find_all(lambda tag: tag.string and re.search(date_pattern, tag.get_text(), re.IGNORECASE))
            
            print(f"\nElements containing potential dates:")
            for i, elem in enumerate(elements_with_dates[:10]):  # Limit to first 10
                text = elem.get_text(strip=True)
                if text and len(text) < 200:  # Skip very long text blocks
                    print(f"  {i+1}. <{elem.name}> {elem.get('class', [])} '{text}'")
            
            # Look for specific patterns in the full text
            print(f"\nDate patterns found in full text:")
            date_matches = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', full_text)
            year_matches = re.findall(r'\b\d{4}\b', full_text)
            dash_patterns = re.findall(r'\b\d{4}\s*[-–—]\s*\d{4}\b', full_text)
            
            print(f"  Month/Day/Year: {date_matches[:5]}")  # Show first 5
            print(f"  Year patterns: {list(set(year_matches))[:10]}")  # Show unique years
            print(f"  Range patterns (YYYY-YYYY): {dash_patterns}")
            
        else:
            print(f"HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

# Test the problematic cases
test_cases = [
    ("https://www.fossfuneralhome.com/obituary/morris-henderson", "Foss Funeral Home"),
    ("https://www.robertsonfh.com/obituary/JARRETT-HAWKINS", "Robertson Funeral Home"),
    ("https://www.mcdowellfuneralhome.com/obituary/Larry-Turner", "McDowell Funeral Home")
]

for url, funeral_home in test_cases:
    debug_page_structure(url, funeral_home)
