#!/usr/bin/env python3

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Try common funeral home endpoints
test_urls = [
    "https://www.whbfamily.com/obituaries",
    "https://www.whbfamily.com/obituary", 
    "https://www.whbfamily.com/memorials",
    "https://www.whbfamily.com/tributes",
    "https://www.whbfamily.com/current-obituaries",
    "https://www.whbfamily.com/recent-obituaries",
    "https://www.whbfamily.com/robots.txt",
    "https://www.whbfamily.com/sitemap.xml"
]

for url in test_urls:
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"{url} -> {response.status_code}")
        if response.status_code == 200 and 'sitemap' in url:
            print("  Sitemap content preview:")
            print("  " + response.text[:200] + "...")
    except Exception as e:
        print(f"{url} -> ERROR: {e}")
