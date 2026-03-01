#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

response = requests.get("https://www.whbfamily.com/obituaries", headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Save the HTML for inspection
    with open('whb_obituaries_page.html', 'w', encoding='utf-8') as f:
        f.write(str(soup.prettify()))
    
    print("HTML saved to whb_obituaries_page.html")
    
    # Look for any JavaScript that might load obituaries
    scripts = soup.find_all('script')
    for i, script in enumerate(scripts):
        if script.string and ('obituar' in script.string.lower() or 'ajax' in script.string.lower() or 'api' in script.string.lower()):
            print(f"\nScript {i+1} contains relevant keywords:")
            print(script.string[:500] + "..." if len(script.string) > 500 else script.string)
    
    # Check if there are any iframe elements
    iframes = soup.find_all('iframe')
    if iframes:
        print(f"\nFound {len(iframes)} iframe(s):")
        for iframe in iframes:
            src = iframe.get('src')
            if src:
                print(f"  iframe src: {src}")
    
    # Look for any elements with "data-" attributes that might indicate dynamic loading
    elements_with_data = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
    print(f"\nFound {len(elements_with_data)} elements with data attributes")
    for elem in elements_with_data[:5]:  # Show first 5
        data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith('data-')}
        print(f"  {elem.name}: {data_attrs}")
        
else:
    print("Failed to fetch page")
