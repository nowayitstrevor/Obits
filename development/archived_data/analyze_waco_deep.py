"""
Deep dive into Waco Funeral Home website structure
This script tries different approaches to find obituary content
"""

import requests
from bs4 import BeautifulSoup
import time
import json

def analyze_waco_deep():
    """Deep analysis of Waco Funeral Home website."""
    
    # More comprehensive headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    base_urls = [
        "https://www.wacofhmp.com/obituaries",
        "https://www.wacofhmp.com/",
        "https://www.wacofhmp.com/current-obituaries",
        "https://www.wacofhmp.com/obituary-listings"
    ]
    
    for url in base_urls:
        print(f"\\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for any divs or sections that might contain obituaries
                potential_containers = []
                
                # Check for common obituary-related class names and IDs
                for element in soup.find_all(['div', 'section', 'article', 'ul', 'ol']):
                    classes = element.get('class', [])
                    id_attr = element.get('id', '')
                    
                    # Convert to strings for searching
                    class_str = ' '.join(classes).lower()
                    id_str = id_attr.lower()
                    
                    # Look for obituary-related keywords
                    keywords = ['obit', 'memorial', 'tribute', 'deceased', 'listing', 'current']
                    
                    if any(keyword in class_str or keyword in id_str for keyword in keywords):
                        text_content = element.get_text().strip()[:200]
                        potential_containers.append({
                            'tag': element.name,
                            'classes': classes,
                            'id': id_attr,
                            'text_preview': text_content
                        })
                
                if potential_containers:
                    print(f"\\nFound potential obituary containers:")
                    for container in potential_containers[:5]:
                        print(f"  <{container['tag']} class='{container['classes']}' id='{container['id']}'>")
                        print(f"    Text: {container['text_preview'][:100]}...")
                else:
                    print(f"\\nNo obvious obituary containers found")
                
                # Look for any links that might lead to obituaries
                all_links = soup.find_all('a', href=True)
                interesting_links = []
                
                for link in all_links:
                    href = link.get('href')
                    text = link.get_text().strip()
                    
                    # Skip empty or very short text
                    if not text or len(text) < 3:
                        continue
                    
                    # Look for names (2-4 words, contains letters)
                    words = text.split()
                    if 2 <= len(words) <= 4 and any(c.isalpha() for c in text):
                        # Skip obvious navigation items
                        skip_words = ['home', 'about', 'contact', 'services', 'staff', 'cemetery', 'pre-planning', 'resources']
                        if not any(skip in text.lower() for skip in skip_words):
                            interesting_links.append({
                                'text': text,
                                'href': href
                            })
                
                if interesting_links:
                    print(f"\\nFound interesting links (potential names):")
                    for link in interesting_links[:10]:
                        print(f"  {link['text']}: {link['href']}")
                else:
                    print(f"\\nNo interesting links found")
                
                # Check page title and meta description
                title = soup.find('title')
                if title:
                    print(f"\\nPage title: {title.get_text()}")
                
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    print(f"Meta description: {meta_desc.get('content', '')}")
                
                # Look for JavaScript that might load content dynamically
                scripts = soup.find_all('script')
                js_clues = []
                
                for script in scripts:
                    script_text = script.get_text()
                    if any(keyword in script_text.lower() for keyword in ['obituary', 'ajax', 'fetch', 'api']):
                        js_clues.append(script_text[:100])
                
                if js_clues:
                    print(f"\\nJavaScript clues found:")
                    for clue in js_clues[:3]:
                        print(f"  {clue[:80]}...")
                
            else:
                print(f"❌ HTTP {response.status_code} error")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(2)  # Be respectful

if __name__ == "__main__":
    analyze_waco_deep()
