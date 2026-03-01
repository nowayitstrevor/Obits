"""
Debug script to analyze the structure of specific obituary pages
that are failing validation.
"""

import requests
from bs4 import BeautifulSoup
import json

def analyze_obituary_page(url: str):
    """Analyze the structure of an obituary page."""
    print(f"Analyzing: {url}")
    print("="*60)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print(f"Page title: {soup.title.string if soup.title else 'No title'}")
        print()
        
        # Check common name selectors
        name_selectors = ['h1', '.obituary-title', '.obit-name', '.entry-title', '.name', '.title']
        print("NAME SELECTORS:")
        for selector in name_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  {selector}: {len(elements)} elements")
                for i, elem in enumerate(elements[:3]):  # Show first 3
                    text = elem.get_text(strip=True)[:100]
                    print(f"    [{i}]: {text}")
            else:
                print(f"  {selector}: No elements found")
        print()
        
        # Check common content selectors
        content_selectors = ['.obituary-content', '.obit-content', '.entry-content', '.content', '.description', '.text', '.body']
        print("CONTENT SELECTORS:")
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"  {selector}: {len(elements)} elements")
                for i, elem in enumerate(elements[:2]):  # Show first 2
                    text = elem.get_text(strip=True)[:200]
                    print(f"    [{i}]: {text}...")
            else:
                print(f"  {selector}: No elements found")
        print()
        
        # Look for any large text blocks
        print("LARGEST TEXT BLOCKS:")
        all_elements = soup.find_all(['div', 'p', 'section', 'article'])
        text_blocks = []
        
        for elem in all_elements:
            text = elem.get_text(strip=True)
            if len(text) > 100:  # Only consider substantial text blocks
                # Get class and id for identification
                classes = ' '.join(elem.get('class', []))
                elem_id = elem.get('id', '')
                selector = f"{elem.name}"
                if elem_id:
                    selector += f"#{elem_id}"
                if classes:
                    selector += f".{classes.replace(' ', '.')}"
                
                text_blocks.append((len(text), selector, text[:200]))
        
        # Sort by length and show top 5
        text_blocks.sort(reverse=True)
        for i, (length, selector, text) in enumerate(text_blocks[:5]):
            print(f"  [{i+1}] {length} chars - {selector}")
            print(f"      {text}...")
            print()
            
    except Exception as e:
        print(f"Error analyzing {url}: {e}")

if __name__ == "__main__":
    # Test URLs that we know are failing
    test_urls = [
        "https://www.slctx.com/obituary/Jalailah-Cooper",
        "https://www.slctx.com/obituary/Timothy-Bowie"
    ]
    
    for url in test_urls:
        analyze_obituary_page(url)
        print("\n" + "="*80 + "\n")
