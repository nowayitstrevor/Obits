"""
Deep analysis of SLCTX page structure to understand why content extraction is failing.
"""

import requests
from bs4 import BeautifulSoup

def deep_analyze_slctx():
    url = "https://www.slctx.com/obituary/Eddie-Satchell"
    print(f"Deep analysis of: {url}")
    print("="*60)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("HTML STRUCTURE ANALYSIS:")
        print(f"Total page length: {len(str(soup))} characters")
        print(f"Title: {soup.title.string if soup.title else 'No title'}")
        print()
        
        # Check all div elements with classes
        print("ALL DIV ELEMENTS WITH CLASSES:")
        divs = soup.find_all('div', class_=True)
        for div in divs[:20]:  # Show first 20
            classes = ' '.join(div.get('class', []))
            text = div.get_text(strip=True)[:100]
            print(f"  div.{classes}: {len(text)} chars - {text}")
        print()
        
        # Specifically check the col-xs-12-body selector
        print("CHECKING .col-xs-12-body SPECIFICALLY:")
        col_elements = soup.select('.col-xs-12-body')
        for i, elem in enumerate(col_elements):
            text = elem.get_text(strip=True)
            print(f"  Element {i}: {len(text)} characters")
            print(f"  Content: {text[:300]}...")
            print(f"  HTML: {str(elem)[:300]}...")
            print()
        
        # Check alternative selectors
        alt_selectors = [
            '.col-xs-12', '.col-md-12', '.col-lg-12',
            '[class*="col-"]', '[class*="body"]',
            '.main', '.content', '#content', '.page'
        ]
        
        print("TRYING ALTERNATIVE SELECTORS:")
        for selector in alt_selectors:
            elements = soup.select(selector)
            if elements:
                for i, elem in enumerate(elements[:2]):
                    text = elem.get_text(strip=True)
                    if len(text) > 50:
                        print(f"  {selector}[{i}]: {len(text)} chars - {text[:100]}...")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deep_analyze_slctx()
