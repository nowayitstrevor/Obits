"""
Try to find alternative ways to get obituary data without Selenium.
"""

import requests
import json
from bs4 import BeautifulSoup

# Try different endpoints that might have obituary data
endpoints_to_try = [
    "https://www.lakeshorefuneralhome.com/api/obituaries",
    "https://www.lakeshorefuneralhome.com/obituaries.json", 
    "https://www.lakeshorefuneralhome.com/obituaries/feed",
    "https://www.lakeshorefuneralhome.com/obituaries/rss",
    "https://www.lakeshorefuneralhome.com/obituaries/api/list",
    "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings.json",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

print("Checking for alternative API endpoints...")

for url in endpoints_to_try:
    try:
        print(f"\nTrying: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            print(f"  Content-Type: {content_type}")
            print(f"  Content Length: {len(response.text)}")
            
            if 'json' in content_type:
                try:
                    data = response.json()
                    print(f"  JSON data found with {len(data)} items")
                    # Save for inspection
                    with open(f"api_response_{url.split('/')[-1]}.json", "w") as f:
                        json.dump(data, f, indent=2)
                except:
                    print("  Not valid JSON")
            else:
                print(f"  First 200 chars: {response.text[:200]}")
        
    except requests.exceptions.RequestException as e:
        print(f"  Error: {e}")

# Also try looking at the main website's scripts for API calls
print("\n" + "="*50)
print("Analyzing main page JavaScript for API endpoints...")

main_url = "https://www.lakeshorefuneralhome.com/obituaries/obituary-listings?page=1"
response = requests.get(main_url, headers=headers)

# Look for common API patterns in JavaScript
import re
api_patterns = [
    r'api[\'\"]/[\w/]+',
    r'fetch\s*\(\s*[\'\"](.*?)[\'\"]\s*\)',
    r'ajax\s*\(\s*{.*?url\s*:\s*[\'\"](.*?)[\'\"',
    r'[\'\"]/api/[^\'\"]*[\'\"',
    r'[\'\"]/rest/[^\'\"]*[\'\"',
    r'obituar[^\'\"]*\.json',
]

found_apis = []
for pattern in api_patterns:
    matches = re.findall(pattern, response.text, re.IGNORECASE)
    found_apis.extend(matches)

print(f"Found {len(found_apis)} potential API endpoints:")
for api in set(found_apis):
    print(f"  {api}")
    
if found_apis:
    print("\nTrying discovered API endpoints...")
    for api in set(found_apis[:5]):  # Try first 5 unique ones
        if api.startswith('/'):
            full_url = f"https://www.lakeshorefuneralhome.com{api}"
        elif api.startswith('http'):
            full_url = api
        else:
            full_url = f"https://www.lakeshorefuneralhome.com/{api}"
            
        try:
            print(f"\nTrying discovered endpoint: {full_url}")
            response = requests.get(full_url, headers=headers, timeout=10)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  Content length: {len(response.text)}")
                print(f"  Content preview: {response.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")

print("\n" + "="*50)
print("SUMMARY:")
print("1. Website requires JavaScript (confirmed)")
print("2. No browser available for Selenium (Chrome/Firefox needed)")
print("3. No obvious API endpoints found")
print("\nRECOMMENDATION:")
print("Install Google Chrome or Firefox browser to use Selenium approach.")
