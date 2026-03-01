"""
Test the enhanced configurations for SLCTX and WacoFHMP
"""

import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def test_slctx_filtering():
    """Test SLCTX with enhanced filtering."""
    print("Testing SLCTX Enhanced Filtering")
    print("=" * 40)
    
    url = "https://www.slctx.com/listings"
    
    # Enhanced skip patterns
    skip_patterns = [
        '/send-flowers', '/plant-tree', '/sympathy', '/share', 
        '/guestbook', '/guest-book', '/print', '/directions',
        '/flowers', '/gifts', '/memory'
    ]
    
    response = requests.get(url, timeout=30)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all obituary links
    all_links = soup.find_all('a', href=True)
    obituary_links = []
    skipped_links = []
    
    for link in all_links:
        href = link.get('href')
        text = link.get_text().strip()
        
        if href and '/obituary/' in href:
            full_url = urljoin(url, href)
            
            # Check if should be skipped
            should_skip = any(pattern in href.lower() for pattern in skip_patterns)
            
            if should_skip:
                skipped_links.append({
                    'url': full_url,
                    'text': text,
                    'reason': 'Matches skip pattern'
                })
            else:
                obituary_links.append({
                    'url': full_url,
                    'text': text
                })
    
    print(f"Total obituary links found: {len(obituary_links)}")
    print(f"Links skipped by filtering: {len(skipped_links)}")
    
    print("\\nValid obituary links (first 10):")
    for link in obituary_links[:10]:
        print(f"  ✅ {link['text']}: {link['url']}")
    
    print("\\nSkipped links (first 10):")
    for link in skipped_links[:10]:
        print(f"  ❌ {link['text']}: {link['url']} ({link['reason']})")
    
    # Test content validation on first obituary
    if obituary_links:
        test_url = obituary_links[0]['url']
        print(f"\\nTesting content validation on: {test_url}")
        
        try:
            resp = requests.get(test_url, timeout=30)
            test_soup = BeautifulSoup(resp.content, 'html.parser')
            content = test_soup.get_text().strip()
            
            # Check for forbidden content
            forbidden_content = [
                'send flowers', 'plant tree', 'share memory', 'guest book',
                'sympathy gifts', 'memorial gifts'
            ]
            
            found_forbidden = []
            for forbidden in forbidden_content:
                if forbidden.lower() in content.lower():
                    found_forbidden.append(forbidden)
            
            print(f"  Content length: {len(content)} characters")
            
            if found_forbidden:
                print(f"  ⚠️  Found forbidden content: {found_forbidden}")
                print("  ❌ Would be filtered out by content validation")
            else:
                print(f"  ✅ Content validation passed")
                
        except Exception as e:
            print(f"  ❌ Error testing content: {e}")

def test_waco_structure():
    """Test Waco site structure."""
    print("\\n\\nTesting Waco Funeral Home Structure")
    print("=" * 40)
    
    url = "https://www.wacofhmp.com/obituaries"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.text)} characters")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for potential obituary containers
        selectors_to_try = [
            '.obituary-listing', '.obit-card', '.memorial-listing',
            '.obituary', '.memorial', '.listing', '.tribute', 
            '.card', '.item', '.entry'
        ]
        
        found_containers = []
        for selector in selectors_to_try:
            elements = soup.select(selector)
            if elements:
                found_containers.append({
                    'selector': selector,
                    'count': len(elements),
                    'sample_text': elements[0].get_text().strip()[:100] if elements else ''
                })
        
        print(f"\\nFound potential containers:")
        for container in found_containers:
            print(f"  {container['selector']}: {container['count']} elements")
            print(f"    Sample: {container['sample_text'][:50]}...")
        
        # Look for obituary-related links
        all_links = soup.find_all('a', href=True)
        obituary_related = []
        
        for link in all_links:
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()
            
            if any(keyword in href or keyword in text for keyword in ['obituary', 'obituaries', 'memorial', 'tribute']):
                obituary_related.append({
                    'href': link.get('href'),
                    'text': link.get_text().strip()[:50]
                })
        
        print(f"\\nObituary-related links found: {len(obituary_related)}")
        for link in obituary_related[:10]:
            print(f"  • {link['text']}: {link['href']}")
        
        # Check if JavaScript is heavily used
        scripts = soup.find_all('script')
        js_heavy_indicators = ['react', 'vue', 'angular', 'ajax', 'fetch']
        js_content = ' '.join([script.get_text() for script in scripts if script.get_text()])
        
        js_indicators_found = [indicator for indicator in js_heavy_indicators if indicator in js_content.lower()]
        
        if js_indicators_found:
            print(f"\\n⚠️  JavaScript frameworks detected: {js_indicators_found}")
            print("  This site likely requires Selenium for full content")
        else:
            print(f"\\n✅ No heavy JavaScript frameworks detected")
            
    except Exception as e:
        print(f"Error testing Waco site: {e}")

if __name__ == "__main__":
    test_slctx_filtering()
    test_waco_structure()
