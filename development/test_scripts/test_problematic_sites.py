"""
Quick tester for problematic funeral home websites.

This script helps diagnose and test specific issues with SLCTX and WacoFHMP.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json

def test_slctx():
    """Test SLC Texas website structure."""
    print("Testing SLC Texas (https://www.slctx.com/listings)")
    print("-" * 50)
    
    try:
        response = requests.get("https://www.slctx.com/listings", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        print(f"Total links found: {len(all_links)}")
        
        # Filter for obituary links
        obituary_links = []
        problematic_links = []
        
        for link in all_links:
            href = link.get('href')
            text = link.get_text().strip()
            
            if href and '/obituary/' in href:
                full_url = urljoin("https://www.slctx.com/listings", href)
                
                # Check if it's a problematic link
                if any(bad in href.lower() for bad in ['send-flowers', 'plant-tree', 'sympathy']):
                    problematic_links.append({
                        'url': full_url,
                        'text': text,
                        'href': href
                    })
                else:
                    obituary_links.append({
                        'url': full_url,
                        'text': text,
                        'href': href
                    })
        
        print(f"\\nValid obituary links: {len(obituary_links)}")
        for link in obituary_links[:5]:
            print(f"  • {link['text']}: {link['href']}")
        
        print(f"\\nProblematic links: {len(problematic_links)}")
        for link in problematic_links[:5]:
            print(f"  ❌ {link['text']}: {link['href']}")
        
        # Test one obituary page
        if obituary_links:
            print(f"\\nTesting first obituary page...")
            test_url = obituary_links[0]['url']
            test_response = requests.get(test_url, timeout=30)
            test_soup = BeautifulSoup(test_response.content, 'html.parser')
            
            # Extract name
            name_candidates = []
            for selector in ['h1', 'h2', '.deceased-name', '.tribute-name']:
                elements = test_soup.select(selector)
                for elem in elements:
                    name_candidates.append(elem.get_text().strip())
            
            print(f"Name candidates: {name_candidates[:3]}")
            
            # Check content length
            content = test_soup.get_text().strip()
            print(f"Content length: {len(content)} characters")
            
            # Check for problematic content
            problematic_content = ['send flowers', 'plant tree', 'share memory']
            found_issues = [issue for issue in problematic_content if issue in content.lower()]
            if found_issues:
                print(f"⚠️  Found problematic content: {found_issues}")
            else:
                print("✅ No problematic content detected")
    
    except Exception as e:
        print(f"Error testing SLCTX: {e}")

def test_wacofhmp():
    """Test Waco Funeral Home Memorial Park website."""
    print("\\n\\nTesting Waco Funeral Home Memorial Park (https://www.wacofhmp.com/obituaries)")
    print("-" * 70)
    
    try:
        response = requests.get("https://www.wacofhmp.com/obituaries", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        content = soup.get_text().strip()
        
        print(f"Page content length: {len(content)} characters")
        
        # Check if JavaScript is likely required
        if len(content) < 1000 or 'loading' in content.lower():
            print("⚠️  Likely requires JavaScript")
        else:
            print("✅ Sufficient static content")
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        print(f"Total links found: {len(all_links)}")
        
        # Look for obituary-related links
        obituary_related = []
        for link in all_links:
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()
            
            if any(keyword in href or keyword in text for keyword in ['obituary', 'obituaries', 'memorial', 'tribute']):
                obituary_related.append({
                    'href': link.get('href'),
                    'text': link.get_text().strip()
                })
        
        print(f"\\nObituary-related links: {len(obituary_related)}")
        for link in obituary_related[:10]:
            print(f"  • {link['text']}: {link['href']}")
        
        # Check page title and meta
        title = soup.find('title')
        if title:
            print(f"\\nPage title: {title.get_text().strip()}")
        
        # Look for specific selectors that might contain obituaries
        selectors = ['.obituary', '.memorial', '.listing', '.tribute', '.card', '.item']
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"Found {len(elements)} elements with selector '{selector}'")
    
    except Exception as e:
        print(f"Error testing WacoFHMP: {e}")

def test_enhanced_filtering():
    """Test the enhanced filtering logic."""
    print("\\n\\nTesting Enhanced Filtering Logic")
    print("-" * 40)
    
    # Test URLs that should be filtered out
    test_urls = [
        "https://www.slctx.com/obituary/Michael-Gomez",  # Valid
        "https://www.slctx.com/obituary/Michael-Gomez/send-flowers",  # Should be filtered
        "https://www.slctx.com/obituary/Jazsima-Davis/plant-tree",  # Should be filtered
        "https://www.wacofhmp.com/obituaries",  # Valid listing page
        "https://www.google.com/search?q=waco-memorial-park",  # Should be filtered
    ]
    
    # Default skip patterns
    skip_patterns = [
        '/send-flowers', '/flowers', '/sympathy', '/plant-tree',
        '/share', '/guestbook', '/guest-book', '/print', '/pdf',
        '/directions', '/contact', '/about', '/staff', '/services',
        'javascript:', 'mailto:', 'tel:', '#', 'facebook.com', 'twitter.com',
        'google.com'
    ]
    
    def should_skip_url(url):
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)
    
    print("URL Filtering Test:")
    for url in test_urls:
        should_skip = should_skip_url(url)
        status = "❌ SKIP" if should_skip else "✅ KEEP"
        print(f"  {status}: {url}")

if __name__ == "__main__":
    test_slctx()
    test_wacofhmp()
    test_enhanced_filtering()
    
    print("\\n\\n" + "="*70)
    print("RECOMMENDATIONS:")
    print("="*70)
    print("1. For SLCTX: Use enhanced filtering to exclude /send-flowers, /plant-tree URLs")
    print("2. For WacoFHMP: Likely needs JavaScript/Selenium due to dynamic content")
    print("3. Both sites: Implement content validation to exclude auxiliary pages")
    print("4. Test with the enhanced_generic_scraper.py using the configurations in enhanced_configs.json")
    print("\\nNext steps:")
    print("  1. Run: python website_analyzer.py https://www.slctx.com/listings")
    print("  2. Run: python website_analyzer.py https://www.wacofhmp.com/obituaries")
    print("  3. Test enhanced scraper with improved configurations")
